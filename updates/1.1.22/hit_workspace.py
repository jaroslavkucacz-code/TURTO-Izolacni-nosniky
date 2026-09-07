from __future__ import annotations

"""TURTO ISO 1.1.22 direct HIT workspace compatibility layer.

The verified 1.1.17 calculation workspace remains the calculation base. This
layer adds quantity, virtualized scrolling, local proposal storage, PDF/XLSX
exports and the 1.1.22 bulk-import extension without changing the HIT
calculation core or catalogue data.
"""

from typing import Any
from tkinter import ttk

import hit_workspace_base as _base
from hit_workspace_base import *  # noqa: F401,F403 - preserve public API
from hit_row_extension import install as _install_rows
from hit_virtual_scroll import install as _install_scroll
from hit_design_ui import install as _install_design
from hit_export_ui import install as _install_export

HIT_MODULE_VERSION = "1.1.22"
_base.HIT_MODULE_VERSION = HIT_MODULE_VERSION

# Patches are deliberately layered: row lifecycle -> virtual viewport -> design
# database -> exports. The final toolbar wrapper is applied last.
_install_rows(_base)
_install_scroll(_base)
_install_design(_base)
_install_export(_base)

_ORIGINAL_BUILD_HIT_TAB = _base.HitWorkspaceMixin._build_hit_tab


def _find_button(root: Any, text: str):
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
                return widget
            stack.extend(widget.winfo_children())
        except Exception:
            continue
    return None


def _patched_build_hit_tab(self, parent: ttk.Frame) -> None:
    _ORIGINAL_BUILD_HIT_TAB(self, parent)
    anchor = _find_button(parent, "Kopírovat výsledky")
    if anchor is None:
        return
    toolbar = anchor.master

    pdf_button = ttk.Button(toolbar, text="Export PDF", style="Accent.TButton", command=self.export_hit_pdf)
    pdf_button.grid(row=0, column=10, padx=(12, 0))
    excel_button = ttk.Button(toolbar, text="Export Excel", command=self.export_hit_excel)
    excel_button.grid(row=0, column=11, padx=(7, 0))
    save_button = ttk.Button(toolbar, text="Uložit návrh", command=self.save_hit_design)
    save_button.grid(row=0, column=12, padx=(12, 0))
    database_button = ttk.Button(toolbar, text="Návrhy…", command=self.open_hit_design_browser)
    database_button.grid(row=0, column=13, padx=(7, 0))

    self.hit_pdf_button = pdf_button
    self.hit_excel_button = excel_button
    self.hit_design_save_button = save_button
    self.hit_design_browser_button = database_button


_base.HitWorkspaceMixin._build_hit_tab = _patched_build_hit_tab

# Keep the public names identical to the verified implementation objects.
HitInputRow = _base.HitInputRow
HitWorkspaceMixin = _base.HitWorkspaceMixin
