from __future__ import annotations

"""TURTO 2.0.2 thermal-break UI hotfix.

Fixes the remaining startup regression from 2.0.0/2.0.1: the generic
supplementary-row button was created with ``pack()`` inside a toolbar already
managed by ``grid()``. Tkinter does not allow mixing geometry managers in one
parent. Instead of creating a new widget, this layer reuses the existing +HT
button, renames it to "+ Přidat řádek" and changes its command to create a
new HT row whose type can then be changed in the row selector.

No calculation, catalogue, AKCE persistence or substitution logic is changed.
"""

from typing import Any
from tkinter import ttk

import hit_workspace_201 as _prev
import hit_workspace_200 as _base200
from hit_workspace_201 import *  # noqa: F401,F403

HIT_MODULE_VERSION = "2.0.2"
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
                        widget.configure(text=f"HIT-HP/SP • MVX / MVXL / ZVX / ZDX / DD / DVL / DDL • modul {HIT_MODULE_VERSION}")
                    elif text.startswith("Vstupy se zamykají podle typu. HIT-HT"):
                        widget.configure(text="Deskové a balkonové typy používají MEd/VEd v kNm/m a kN/m. Doplňkové prvky a WT jsou v samostatných podzáložkách.")
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


# 2.0.0 _build() looks up this module global at runtime, so replacing it fixes
# startup before the bad pack() call can be reached.
_base200._postprocess = _postprocess

HitInputRow = _prev.HitInputRow
HitWorkspaceMixin = _prev.HitWorkspaceMixin
