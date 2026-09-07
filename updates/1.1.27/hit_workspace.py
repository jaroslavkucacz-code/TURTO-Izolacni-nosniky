from __future__ import annotations

"""TURTO ISO 1.1.27 – separate supplementary HIT workspace + global outputs."""

from typing import Any
from tkinter import ttk

import hit_workspace_125 as _prev
from hit_workspace_125 import *  # noqa: F401,F403
from hit_aux_ui import AUX_TYPES, install as _install_aux

HIT_MODULE_VERSION = "1.1.27"
STANDARD_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL")

try:
    _prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION
    _prev._prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION  # type: ignore[attr-defined]
    _prev._prev._base.HIT_MODULE_VERSION = HIT_MODULE_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

_install_aux(_prev)

# Restrict the main table to the slab / balcony families. Old actions are
# migrated by action_payload.py before rows are constructed.
_ORIGINAL_ROW_INIT = _prev.HitInputRow.__init__


def _row_init(self, *args, **kwargs) -> None:
    _ORIGINAL_ROW_INIT(self, *args, **kwargs)
    try:
        self.type_combo.configure(values=STANDARD_TYPES)
        if self.connection_type.get().strip().upper() not in STANDARD_TYPES:
            self.connection_type.set("MVX")
            self._apply_type_constraints()
            self.recalculate()

        # Standard slab/balcony types never use NEd, HEd or OTX x. Remove those
        # controls from the actual grid, not merely disable them.
        base_widgets = list(getattr(self, "_hit_base_widgets", []))
        hidden_base_indices = {11, 12, 15, 16, 17}
        if len(base_widgets) >= 25:
            for index in hidden_base_indices:
                try:
                    base_widgets[index].grid_remove()
                except Exception:
                    pass
            self._hit_base_widgets = [
                widget for index, widget in enumerate(base_widgets)
                if index not in hidden_base_indices
            ]
            self.regrid(self.row_no)
    except Exception:
        pass


_prev.HitInputRow.__init__ = _row_init


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _find_button(root: Any, text: str):
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
                return widget
        except Exception:
            pass
    return None


def _compact_standard_headers(owner: Any) -> None:
    frame = getattr(owner, "hit_rows_frame", None)
    if frame is None:
        return
    hidden_columns = {12, 13, 16, 17, 18}
    for child in frame.winfo_children():
        if not isinstance(child, ttk.Label):
            continue
        try:
            info = child.grid_info()
            if int(info.get("row", -1)) != 0:
                continue
            column = int(info.get("column", -1))
        except Exception:
            continue
        if column in hidden_columns:
            try:
                child.grid_remove()
            except Exception:
                pass
            continue
        shift = sum(1 for hidden in hidden_columns if hidden < column)
        try:
            child.grid_configure(column=column - shift)
        except Exception:
            pass
    for column in range(21):
        try:
            frame.columnconfigure(column, weight=1 if column in {0, 14, 19} else 0)
        except Exception:
            pass


def _standard_ribbon(self, parent: ttk.Frame) -> None:
    ribbon = ttk.Frame(parent, style="Card.TFrame", padding=(12, 8))
    ribbon.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    ribbon.columnconfigure(2, weight=1)
    ttk.Label(
        ribbon,
        text="Desky / balkony",
        style="Card.TLabel",
        font=("Calibri", 10, "bold"),
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        ribbon,
        text="MVX · MVXL · ZVX · ZDX · DD · DVL · DDL",
        style="MutedCard.TLabel",
    ).grid(row=0, column=1, sticky="w", padx=(12, 0))
    quick = ttk.Frame(ribbon, style="Card.TFrame")
    quick.grid(row=0, column=3, sticky="e")
    ttk.Button(quick, text="+ MVX", command=lambda: self.add_hit_row_for_type("MVX")).pack(side="left")
    ttk.Button(quick, text="+ MVXL", command=lambda: self.add_hit_row_for_type("MVXL")).pack(side="left", padx=(5, 0))
    ttk.Button(quick, text="+ ZVX", command=lambda: self.add_hit_row_for_type("ZVX")).pack(side="left", padx=(5, 0))
    ttk.Button(quick, text="+ ZDX", command=lambda: self.add_hit_row_for_type("ZDX")).pack(side="left", padx=(5, 0))


_prev.HitWorkspaceMixin._build_hit_group_ribbon = _standard_ribbon
_ORIGINAL_BUILD = _prev.HitWorkspaceMixin._build_hit_tab
_ORIGINAL_ADD_FOR_TYPE = _prev.HitWorkspaceMixin.add_hit_row_for_type


def _add_for_type(self, typ: str) -> None:
    typ = str(typ or "").strip().upper()
    if typ in AUX_TYPES:
        self.add_aux_row_for_type(typ)
        try:
            if hasattr(self, "hit_design_notebook") and hasattr(self, "hit_aux_tab"):
                self.hit_design_notebook.select(self.hit_aux_tab)
        except Exception:
            pass
        return
    if typ not in STANDARD_TYPES:
        typ = "MVX"
    _ORIGINAL_ADD_FOR_TYPE(self, typ)


def _build(self, parent: ttk.Frame) -> None:
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)

    globalbar = ttk.Frame(parent, style="Card.TFrame", padding=(12, 8))
    globalbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    globalbar.columnconfigure(2, weight=1)
    ttk.Label(
        globalbar,
        text="Návrh HIT – výstup celé AKCE",
        style="Card.TLabel",
        font=("Calibri", 10, "bold"),
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        globalbar,
        text="PDF zahrnuje Desky / balkony + Doplňkové prvky + Stěny WT bez ohledu na právě otevřenou podzáložku.",
        style="MutedCard.TLabel",
    ).grid(row=0, column=1, sticky="w", padx=(12, 0))
    ttk.Button(
        globalbar,
        text="Export PDF – všechny prvky",
        style="Accent.TButton",
        command=self.export_hit_pdf,
    ).grid(row=0, column=3, sticky="e")

    content = ttk.Frame(parent, style="App.TFrame")
    content.grid(row=1, column=0, sticky="nsew")
    content.columnconfigure(0, weight=1)
    content.rowconfigure(0, weight=1)
    _ORIGINAL_BUILD(self, content)
    _compact_standard_headers(self)

    notebook = getattr(self, "hit_design_notebook", None)
    if notebook is None:
        return

    aux = ttk.Frame(notebook, style="App.TFrame", padding=(0, 8, 0, 0))
    self.hit_aux_tab = aux
    try:
        notebook.insert(1, aux, text="Doplňkové prvky")
    except Exception:
        notebook.add(aux, text="Doplňkové prvky")
    self._build_aux_tab(aux)

    # The old PDF button was scoped visually to the standard table; hide it so
    # there is exactly one unambiguous global PDF action above all sub-tabs.
    standard = getattr(self, "hit_standard_tab", None)
    if standard is not None:
        button = _find_button(standard, "Export PDF")
        if button is not None:
            try:
                button.grid_remove()
            except Exception:
                pass
        excel = _find_button(standard, "Export Excel")
        if excel is not None:
            try:
                excel.configure(text="Export Excel – desky")
            except Exception:
                pass

    try:
        notebook.tab(self.hit_standard_tab, text="Desky / balkony")
        notebook.tab(self.hit_wt_tab, text="Stěny WT")
    except Exception:
        pass


_prev.HitWorkspaceMixin.add_hit_row_for_type = _add_for_type
_prev.HitWorkspaceMixin._build_hit_tab = _build

HitInputRow = _prev.HitInputRow
HitWorkspaceMixin = _prev.HitWorkspaceMixin
