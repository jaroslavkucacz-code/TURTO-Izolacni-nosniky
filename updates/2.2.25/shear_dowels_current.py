from __future__ import annotations

"""TURTO 2.2.25 – restore the visible manual shear-dowel design form.

The 2.2.21 alternatives panel was accidentally placed into the same grid cell
(row 2) as the manual design form from the stable 2.1.4 UI.  The later widget
covered VEd / geometry inputs and the "Navrhnout a přidat" button.

This layer keeps all 2.2.24 Ancon ED/ESD logic and only repairs the layout:
- row 2 = manual design inputs,
- row 4 = primary design table,
- row 5 = passing alternatives.
"""

from typing import Any
from tkinter import ttk

import shear_dowels_current_224 as _base
import shear_ui_227 as _ui227

ED_EXPLANATION = _base.ED_EXPLANATION

DESIGN_FORM_ROW = 2
DESIGN_TABLE_ROW = 4
ALTERNATIVES_GRID_ROW = 5


def _design_tab(owner: Any):
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return None
    try:
        tabs = notebook.tabs()
        return notebook.nametowidget(tabs[1]) if len(tabs) > 1 else None
    except Exception:
        return None


def _alternatives_card(owner: Any, tab: Any):
    tree = getattr(owner, "shear_design_alternatives_tree", None)
    if tree is None or tab is None:
        return None
    try:
        card = tree.master.master
        return card if getattr(card, "master", None) is tab else None
    except Exception:
        return None


def _fix_design_layout(owner: Any) -> None:
    """Keep the manual proposal form visible and put alternatives below results."""
    tab = _design_tab(owner)
    if tab is None:
        return

    card = _alternatives_card(owner, tab)
    if card is not None:
        try:
            card.grid_configure(
                row=ALTERNATIVES_GRID_ROW,
                column=0,
                sticky="nsew",
                pady=(8, 0),
            )
            owner._turto_design_alternatives_card_225 = card
        except Exception:
            pass

    try:
        tab.rowconfigure(0, weight=0)
        tab.rowconfigure(1, weight=0)
        tab.rowconfigure(DESIGN_FORM_ROW, weight=0)
        tab.rowconfigure(3, weight=0)
        tab.rowconfigure(DESIGN_TABLE_ROW, weight=3)
        tab.rowconfigure(ALTERNATIVES_GRID_ROW, weight=2)
    except Exception:
        pass


def init_shear_workspace(owner: Any) -> None:
    _base.init_shear_workspace(owner)


def build_shear_workspace(owner: Any, parent: ttk.Frame) -> None:
    _base.build_shear_workspace(owner, parent)
    _fix_design_layout(owner)


def install_methods(cls: Any) -> None:
    if getattr(cls, "_turto_shear_225_installed", False):
        return
    _base.install_methods(cls)
    cls._turto_shear_225_installed = True


# platform_workspace imports these public symbols through shear_ui_227.
_ui227.build_shear_workspace = build_shear_workspace
_ui227.init_shear_workspace = init_shear_workspace
_ui227.install_methods = install_methods


__all__ = (
    "ED_EXPLANATION",
    "build_shear_workspace",
    "init_shear_workspace",
    "install_methods",
)


def selftest() -> None:
    assert DESIGN_FORM_ROW == 2
    assert DESIGN_TABLE_ROW == 4
    assert ALTERNATIVES_GRID_ROW == 5
    assert ALTERNATIVES_GRID_ROW not in {DESIGN_FORM_ROW, DESIGN_TABLE_ROW}


if __name__ == "__main__":
    selftest()
