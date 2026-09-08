from __future__ import annotations

"""TURTO 2.1.3 thermal-break UI.

Keeps the verified 2.0.2 workspace behaviour, but a new HIT design starts with
an empty table. Rows are created only by the user's explicit + Přidat řádek
action (or by imports / loading an existing AKCE).
"""

from typing import Any
from tkinter import ttk

import hit_workspace_201 as _prev
import hit_workspace_200 as _base200
from hit_workspace_201 import *  # noqa: F401,F403

HIT_MODULE_VERSION = "2.1.3"
try:
    _prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION
    _prev._prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION  # type: ignore[attr-defined]
except Exception:
    pass


def _postprocess(self, parent: ttk.Frame) -> None:
    old_pdf = _base200._button(parent, "Export PDF – všechny prvky")
    if old_pdf is not None:
        _base200._forget(old_pdf.master)

    standard = getattr(self, "hit_standard_tab", None)
    aux = getattr(self, "hit_aux_tab", None)
    wt = getattr(self, "hit_wt_tab", None)

    if standard is not None:
        for text in ("+ MVX", "+ MVXL", "+ ZVX", "+ ZDX"):
            button = _base200._button(standard, text)
            if button is not None:
                _base200._forget(button)
        schedule = _base200._button(standard, "Vložit výkaz…")
        if schedule is not None:
            _base200._forget(schedule.master)
        for text in ("Export Excel – desky", "Export Excel"):
            button = _base200._button(standard, text)
            if button is not None:
                _base200._forget(button)
        for text in ("Načíst / obnovit data z DoP", "Otevřít zdrojové DoP"):
            button = _base200._button(standard, text)
            if button is not None:
                _base200._forget(button)
        _base200._set_label(standard, "Návrh nosníků Leviat HIT", "Desky / balkony – Leviat HIT")
        for widget in _base200._walk(standard):
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
        primary = _base200._button(aux, "+ HT")
        if primary is not None:
            try:
                primary.configure(
                    text="+ Přidat řádek",
                    command=lambda: self.add_aux_row_for_type("HT"),
                )
            except Exception:
                pass
        for text in ("+ AT", "+ FT", "+ OTX"):
            button = _base200._button(aux, text)
            if button is not None:
                _base200._forget(button)
        _base200._set_label(aux, "Doplňkové prvky HIT", "Doplňkové prvky – Leviat HIT")

    if wt is not None:
        button = _base200._button(wt, "+ Přidat WT")
        if button is not None:
            try:
                button.configure(text="+ Přidat řádek")
            except Exception:
                pass


# 2.0.0 _build() resolves this module global at runtime.
_base200._postprocess = _postprocess

_ORIGINAL_BUILD_HIT_TAB = _prev.HitWorkspaceMixin._build_hit_tab


def _is_generated_empty_row(row: Any) -> bool:
    """True only for the automatic blank row created by the legacy builder."""
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


def _build_hit_tab(self, parent: ttk.Frame) -> None:
    _ORIGINAL_BUILD_HIT_TAB(self, parent)
    _remove_generated_initial_row(self)


def _clear_hit_rows(self) -> None:
    """Clear means empty; do not silently create a replacement row."""
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


_prev.HitWorkspaceMixin._build_hit_tab = _build_hit_tab
_prev.HitWorkspaceMixin.clear_hit_rows = _clear_hit_rows

HitInputRow = _prev.HitInputRow
HitWorkspaceMixin = _prev.HitWorkspaceMixin
