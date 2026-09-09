from __future__ import annotations

"""TURTO 2.2.9 – multi-selection PDF, catalogue access and workspace cleanup."""

from typing import Any
from tkinter import ttk

import platform_workspace_200 as _platform_base
import shear_dowels_schedule_guard  # noqa: F401
from shear_dowels_current import init_shear_workspace as _base_init_shear, install_methods as _base_install_methods
from shear_ui_227 import build_shear_workspace, init_shear_workspace, install_methods as install_shear_227
from shear_autocomplete import attach as attach_shear_autocomplete
from ui_help import compact_inline_help, install as install_help
from table_controls import install as install_table_controls
from ui_consistency import apply as apply_ui_consistency
from ui_layout import apply as apply_ui_layout
from ui_visibility import apply as apply_ui_visibility
from ui_cleanup_227 import apply as apply_ui_cleanup_227
from ui_cleanup_228 import apply as apply_ui_cleanup_228
from pdf_scope import export_pdf_dialog
from catalog_access_229 import apply_catalog_access

WORKSPACE_VERSION = "2.2.9"


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _update_branding(owner: Any) -> None:
    for widget in _walk(owner):
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text"))
                if text.startswith("TURTO 2.") and text.endswith("| Technické prvky"):
                    widget.configure(text=f"TURTO {WORKSPACE_VERSION} | Technické prvky")
        except Exception:
            pass


def _hide_inactive_domains(owner: Any) -> None:
    notebook = getattr(owner, "product_domain_notebook", None)
    frames = getattr(owner, "product_domain_tab_by_id", {})
    if notebook is None or not isinstance(frames, dict):
        return
    for spec in domains():
        if getattr(spec, "enabled", False):
            continue
        frame = frames.get(spec.id)
        if frame is not None:
            try:
                notebook.forget(frame)
            except Exception:
                pass


def install(app_base: Any) -> None:
    cls = app_base.ThermalConnectorApp
    if getattr(cls, "_turto_platform_workspace_229_installed", False):
        return

    _platform_base.install(app_base)
    install_help(app_base)
    # The 2.0 workspace resolves this global when it builds the PDF button.
    _platform_base.export_action_pdf = export_pdf_dialog

    cls = app_base.ThermalConnectorApp
    _base_install_methods(cls)
    install_shear_227(cls)
    original_body = cls._build_body

    def body(self) -> None:
        original_body(self)
        _base_init_shear(self)
        init_shear_workspace(self)
        _update_branding(self)

        frame = getattr(self, "product_domain_tab_by_id", {}).get("shear_dowels")
        if frame is not None:
            for child in list(frame.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            build_shear_workspace(self, frame)
            attach_shear_autocomplete(self)

        _hide_inactive_domains(self)
        compact_inline_help(self)
        install_table_controls(self)
        apply_ui_consistency(self)
        apply_ui_layout(self)
        apply_ui_visibility(self)
        apply_ui_cleanup_227(self)
        apply_ui_cleanup_228(self)
        apply_catalog_access(self)

        try:
            self.base_window_title = f"TURTO {WORKSPACE_VERSION} – Technické prvky"
            self._update_project_title()
        except Exception:
            pass

    cls._build_body = body
    cls._turto_platform_workspace_229_installed = True


domain = _platform_base.domain
domains = _platform_base.domains
manufacturer = _platform_base.manufacturer
manufacturer_id_from_label = _platform_base.manufacturer_id_from_label
manufacturer_labels = _platform_base.manufacturer_labels
