from __future__ import annotations

"""TURTO 2.2.17 HIT workspace – flattened 1.1.27/2.0.0/2.0.1 compatibility layers."""

from typing import Any
from tkinter import ttk

import hit_workspace_125 as _base125
from hit_workspace_125 import *  # noqa: F401,F403
from hit_aux_ui import AUX_TYPES, install as _install_aux
from unified_schedule import open_unified_schedule
from supplier_export import export_supplier_excel

HIT_MODULE_VERSION = "2.2.17"
STANDARD_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL")
_prev = _base125  # compatibility for callers that propagate module version one layer down

try:
    _base125.HIT_MODULE_VERSION = HIT_MODULE_VERSION
    if hasattr(_base125, "_prev"):
        _base125._prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

# 1.1.27 supplementary-element integration. The installer works on the shared
# classes exported by 1.1.25, so the intermediate 1.1.27 module is unnecessary.
_install_aux(_base125)

# ---------------------------------------------------------------------------
# 1.1.27 behavior: standard table restrictions + separate auxiliary workspace.
# ---------------------------------------------------------------------------
_ORIGINAL_ROW_INIT = _base125.HitInputRow.__init__


def _row_init(self, *args, **kwargs) -> None:
    _ORIGINAL_ROW_INIT(self, *args, **kwargs)
    try:
        self.type_combo.configure(values=STANDARD_TYPES)
        if self.connection_type.get().strip().upper() not in STANDARD_TYPES:
            self.connection_type.set("MVX")
            self._apply_type_constraints()
            self.recalculate()

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


_base125.HitInputRow.__init__ = _row_init


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


_ORIGINAL_BUILD_125 = _base125.HitWorkspaceMixin._build_hit_tab
_ORIGINAL_ADD_FOR_TYPE = _base125.HitWorkspaceMixin.add_hit_row_for_type


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


def _build_127(self, parent: ttk.Frame) -> None:
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
    _ORIGINAL_BUILD_125(self, content)
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


# ---------------------------------------------------------------------------
# 2.0.0 / 2.0.1 behavior: platform actions and simplified manufacturer UI.
# ---------------------------------------------------------------------------
def _forget(widget: Any) -> None:
    try:
        manager = widget.winfo_manager()
        if manager == "grid":
            widget.grid_remove()
        elif manager == "pack":
            widget.pack_forget()
        elif manager == "place":
            widget.place_forget()
    except Exception:
        pass


def _button(root: Any, text: str):
    return _find_button(root, text)


def _set_label(root: Any, old: str, new: str) -> None:
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("text")) == old:
                widget.configure(text=new)
        except Exception:
            pass


def _add_aux_row(self):
    return self.add_aux_row_for_type("HT")


def _open_schedule(self) -> None:
    open_unified_schedule(self)


def _export_excel(self) -> None:
    export_supplier_excel(self)


# ---------------------------------------------------------------------------
# 2.1.3 final post-processing. This supersedes the 2.0.0 generic-row toolbar.
# ---------------------------------------------------------------------------
def _postprocess(self, parent: ttk.Frame) -> None:
    old_pdf = _button(parent, "Export PDF – všechny prvky")
    if old_pdf is not None:
        _forget(old_pdf.master)

    standard = getattr(self, "hit_standard_tab", None)
    aux = getattr(self, "hit_aux_tab", None)
    wt = getattr(self, "hit_wt_tab", None)

    if standard is not None:
        for text in ("+ MVX", "+ MVXL", "+ ZVX", "+ ZDX"):
            button = _button(standard, text)
            if button is not None:
                _forget(button)
        schedule = _button(standard, "Vložit výkaz…")
        if schedule is not None:
            _forget(schedule.master)
        for text in ("Export Excel – desky", "Export Excel"):
            button = _button(standard, text)
            if button is not None:
                _forget(button)
        for text in ("Načíst / obnovit data z DoP", "Otevřít zdrojové DoP"):
            button = _button(standard, text)
            if button is not None:
                _forget(button)
        _set_label(standard, "Návrh nosníků Leviat HIT", "Desky / balkony – Leviat HIT")
        for widget in _walk(standard):
            try:
                if isinstance(widget, ttk.Label):
                    text = str(widget.cget("text"))
                    if "HIT-HP/SP • MVX / MVXL / ZVX / ZDX / DD / DVL / DDL / AT / FT / OTX" in text:
                        widget.configure(
                            text=f"HIT-HP/SP • MVX / MVXL / ZVX / ZDX / DD / DVL / DDL • modul {HIT_MODULE_VERSION}"
                        )
                    elif text.startswith("Vstupy se zamykají podle typu. HIT-HT"):
                        widget.configure(
                            text="Deskové a balkonové typy používají MEd/VEd v kNm/m a kN/m. "
                                 "Doplňkové prvky a WT jsou v samostatných podzáložkách."
                        )
            except Exception:
                pass

    if aux is not None:
        primary = _button(aux, "+ HT")
        if primary is not None:
            try:
                primary.configure(
                    text="+ Přidat řádek",
                    command=lambda: self.add_aux_row_for_type("HT"),
                )
            except Exception:
                pass
        for text in ("+ AT", "+ FT", "+ OTX"):
            button = _button(aux, text)
            if button is not None:
                _forget(button)
        _set_label(aux, "Doplňkové prvky HIT", "Doplňkové prvky – Leviat HIT")

    if wt is not None:
        button = _button(wt, "+ Přidat WT")
        if button is not None:
            try:
                button.configure(text="+ Přidat řádek")
            except Exception:
                pass


def _is_generated_empty_row(row: Any) -> bool:
    try:
        effective = row.effective_action_texts()
        if any(str(value or "").strip() for value in effective.values()):
            return False
        if str(row.required_length.get() or "").strip():
            return False
        if str(row.product.get() or "").strip() not in {"", "—"}:
            return False
        if str(row.name.get() or "").strip() not in {"", "N1"}:
            return False
        return True
    except Exception:
        return False


def _remove_generated_initial_row(self) -> None:
    rows = list(getattr(self, "hit_rows", []))
    if len(rows) != 1 or not _is_generated_empty_row(rows[0]):
        return
    row = rows[0]
    try:
        row.destroy()
    except Exception:
        return
    try:
        self.hit_rows.clear()
        self._on_hit_rows_configure()
        self.update_hit_status()
        if hasattr(self, "hit_status_var"):
            self.hit_status_var.set("0 řádků • řádek přidejte tlačítkem + Přidat řádek")
    except Exception:
        pass


def _build_final(self, parent: ttk.Frame) -> None:
    _build_127(self, parent)
    _postprocess(self, parent)
    _remove_generated_initial_row(self)


def _clear_hit_rows(self) -> None:
    for row in list(getattr(self, "hit_rows", [])):
        try:
            row.destroy()
        except Exception:
            pass
    try:
        self.hit_rows.clear()
        self._on_hit_rows_configure()
        self.update_hit_status()
        if hasattr(self, "hit_status_var"):
            self.hit_status_var.set("Zadání HIT bylo vymazáno • nový řádek vložte tlačítkem + Přidat řádek")
    except Exception:
        pass


# Apply final composition to the one shared class object.
_base125.HitWorkspaceMixin.add_hit_row_for_type = _add_for_type
_base125.HitWorkspaceMixin._build_hit_group_ribbon = _standard_ribbon
_base125.HitWorkspaceMixin.add_aux_row = _add_aux_row
_base125.HitWorkspaceMixin.open_hit_schedule = _open_schedule
_base125.HitWorkspaceMixin.export_hit_excel = _export_excel
_base125.HitWorkspaceMixin._build_hit_tab = _build_final
_base125.HitWorkspaceMixin.clear_hit_rows = _clear_hit_rows

HitInputRow = _base125.HitInputRow
HitWorkspaceMixin = _base125.HitWorkspaceMixin


def selftest() -> None:
    assert HIT_MODULE_VERSION == "2.2.17"
    assert HitWorkspaceMixin is _base125.HitWorkspaceMixin
    assert HitInputRow is _base125.HitInputRow
    assert callable(getattr(HitWorkspaceMixin, "add_aux_row", None))
    assert callable(getattr(HitWorkspaceMixin, "clear_hit_rows", None))


if __name__ == "__main__":
    selftest()
