from __future__ import annotations

"""TURTO 2.0 thermal-break design UI compatibility layer.

Keeps the verified 1.1.27 calculations and three design sub-tables, but removes
manufacturer-specific shortcut clutter. Manufacturer selection and unified
schedule/export actions live one level above these tables in platform_workspace.
"""

from typing import Any
from tkinter import ttk

import hit_workspace_127 as _prev
from hit_workspace_127 import *  # noqa: F401,F403
from unified_schedule import open_unified_schedule
from supplier_export import export_supplier_excel

HIT_MODULE_VERSION = "2.0.0"
try:
    _prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION
    _prev._prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

_ORIGINAL_BUILD = _prev.HitWorkspaceMixin._build_hit_tab


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


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
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
                return widget
        except Exception:
            pass
    return None


def _set_label(root: Any, old: str, new: str) -> None:
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("text")) == old:
                widget.configure(text=new)
        except Exception:
            pass


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
                        widget.configure(text=f"HIT-HP/SP • MVX / MVXL / ZVX / ZDX / DD / DVL / DDL • modul {HIT_MODULE_VERSION}")
                    elif text.startswith("Vstupy se zamykají podle typu. HIT-HT"):
                        widget.configure(text="Deskové a balkonové typy používají MEd/VEd v kNm/m a kN/m. Doplňkové prvky a WT jsou v samostatných podzáložkách.")
            except Exception:
                pass

    if aux is not None:
        found = []
        for text in ("+ HT", "+ AT", "+ FT", "+ OTX"):
            button = _button(aux, text)
            if button is not None:
                found.append(button)
        if found:
            bar = found[0].master
            for button in found:
                _forget(button)
            generic = ttk.Button(bar, text="+ Přidat řádek", style="Accent.TButton", command=self.add_aux_row)
            generic.pack(side="left")
        _set_label(aux, "Doplňkové prvky HIT", "Doplňkové prvky – Leviat HIT")

    if wt is not None:
        button = _button(wt, "+ Přidat WT")
        if button is not None:
            try:
                button.configure(text="+ Přidat řádek")
            except Exception:
                pass


def _build(self, parent: ttk.Frame) -> None:
    _ORIGINAL_BUILD(self, parent)
    _postprocess(self, parent)


def _open_schedule(self) -> None:
    open_unified_schedule(self)


def _export_excel(self) -> None:
    export_supplier_excel(self)


_prev.HitWorkspaceMixin._build_hit_tab = _build
_prev.HitWorkspaceMixin.open_hit_schedule = _open_schedule
_prev.HitWorkspaceMixin.export_hit_excel = _export_excel

HitInputRow = _prev.HitInputRow
HitWorkspaceMixin = _prev.HitWorkspaceMixin
