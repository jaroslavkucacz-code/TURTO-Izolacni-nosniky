from __future__ import annotations

"""TURTO ISO 1.1.25 HIT workspace grouping and WT integration."""

from typing import Any
import tkinter as tk
from tkinter import ttk

import hit_workspace_prev as _prev
from hit_workspace_prev import *  # noqa: F401,F403
from hit_wt_ui import install as _install_wt

HIT_MODULE_VERSION = "1.1.25"
try:
    _prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION
    _prev._base.HIT_MODULE_VERSION = HIT_MODULE_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

_install_wt(_prev)

# Align data cells with header anchors in the existing grid.
_ORIGINAL_ROW_INIT = _prev.HitInputRow.__init__


def _row_init(self, *args, **kwargs) -> None:
    _ORIGINAL_ROW_INIT(self, *args, **kwargs)
    for widget in getattr(self, "widgets", []):
        if isinstance(widget, (ttk.Entry, ttk.Combobox)):
            try: widget.configure(justify="center")
            except Exception: pass
    base_widgets = list(getattr(self, "_hit_base_widgets", []))
    if base_widgets:
        try: base_widgets[0].configure(justify="left")  # Pozice
        except Exception: pass
    try: self.product_combo.configure(justify="left")
    except Exception: pass


_prev.HitInputRow.__init__ = _row_init

_ORIGINAL_BUILD = _prev.HitWorkspaceMixin._build_hit_tab

_HEADER_TEXT = {
    0: ("Pozice", "w"),
    1: ("Ks", "center"),
    2: ("Řada", "center"),
    3: ("Typ HIT", "center"),
    4: ("Provedení MVX", "center"),
    5: ("bx [mm]", "center"),
    6: ("h [mm]", "center"),
    7: ("L / B požad. [mm]", "center"),
    8: ("cnom [mm]", "center"),
    9: ("Beton", "center"),
    10: ("MEd+ [kNm/m]", "center"),
    11: ("MEd− [kNm/m]", "center"),
    12: ("NEd+ [kN/m]", "center"),
    13: ("NEd− [kN/m]", "center"),
    14: ("VEd+ [kN/m]", "center"),
    15: ("VEd− [kN/m]", "center"),
    16: ("HEd∥ [kN/prv.]", "center"),
    17: ("HEd⊥ [kN/prv.]", "center"),
    18: ("x [mm]", "center"),
    19: ("Navržený HIT", "w"),
    20: ("Varianty", "center"),
    21: ("Využití", "center"),
    22: ("a max [m]", "center"),
    23: ("Zdroj", "center"),
    24: ("Výsledek / kontrola", "w"),
    25: ("", "center"),
}


def _polish_headers(owner: Any) -> None:
    frame = getattr(owner, "hit_rows_frame", None)
    if frame is None:
        return
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
        spec = _HEADER_TEXT.get(column)
        if spec is None:
            continue
        text, anchor = spec
        try:
            child.configure(text=text, anchor=("w" if anchor == "w" else "center"))
        except Exception:
            pass


def _add_type(self, typ: str) -> None:
    self.add_hit_row()
    if not self.hit_rows:
        return
    row = self.hit_rows[-1]
    row.connection_type.set(str(typ))
    try: row._apply_type_constraints()
    except Exception: pass
    try: row.recalculate()
    except Exception: pass


def _build_group_ribbon(self, parent: ttk.Frame) -> None:
    ribbon = ttk.Frame(parent, style="Card.TFrame", padding=(12, 8))
    ribbon.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    ribbon.columnconfigure(3, weight=1)
    ttk.Label(ribbon, text="Skupiny prvků:", style="Card.TLabel", font=("Calibri", 10, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(
        ribbon,
        text="Desky / balkony: MVX · MVXL · ZVX · ZDX · DD · DVL · DDL",
        style="MutedCard.TLabel",
    ).grid(row=0, column=1, sticky="w", padx=(12, 0))
    ttk.Label(
        ribbon,
        text="Doplňky: HT   |   Parapety / konzoly: AT · FT · OTX",
        style="MutedCard.TLabel",
    ).grid(row=0, column=2, sticky="w", padx=(18, 0))
    quick = ttk.Frame(ribbon, style="Card.TFrame")
    quick.grid(row=0, column=4, sticky="e")
    ttk.Button(quick, text="+ MVX", command=lambda: self.add_hit_row_for_type("MVX")).pack(side="left")
    ttk.Button(quick, text="+ HT", command=lambda: self.add_hit_row_for_type("HT")).pack(side="left", padx=(5, 0))
    ttk.Button(quick, text="+ AT", command=lambda: self.add_hit_row_for_type("AT")).pack(side="left", padx=(5, 0))
    ttk.Button(quick, text="+ FT", command=lambda: self.add_hit_row_for_type("FT")).pack(side="left", padx=(5, 0))
    ttk.Button(quick, text="+ OTX", command=lambda: self.add_hit_row_for_type("OTX")).pack(side="left", padx=(5, 0))


def _build(self, parent: ttk.Frame) -> None:
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)

    notebook = ttk.Notebook(parent, style="Workspace.TNotebook")
    notebook.grid(row=0, column=0, sticky="nsew")
    standard = ttk.Frame(notebook, style="App.TFrame", padding=(0, 8, 0, 0))
    wt = ttk.Frame(notebook, style="App.TFrame", padding=(0, 8, 0, 0))
    notebook.add(standard, text="Desky / balkonové a doplňkové prvky")
    notebook.add(wt, text="Stěny WT")
    self.hit_design_notebook = notebook
    self.hit_standard_tab = standard
    self.hit_wt_tab = wt

    standard.columnconfigure(0, weight=1)
    standard.rowconfigure(1, weight=1)
    self._build_hit_group_ribbon(standard)
    content = ttk.Frame(standard, style="App.TFrame")
    content.grid(row=1, column=0, sticky="nsew")
    content.columnconfigure(0, weight=1); content.rowconfigure(2, weight=1)
    _ORIGINAL_BUILD(self, content)
    _polish_headers(self)
    self._build_wt_tab(wt)


_prev.HitWorkspaceMixin.add_hit_row_for_type = _add_type
_prev.HitWorkspaceMixin._build_hit_group_ribbon = _build_group_ribbon
_prev.HitWorkspaceMixin._build_hit_tab = _build

HitInputRow = _prev.HitInputRow
HitWorkspaceMixin = _prev.HitWorkspaceMixin
