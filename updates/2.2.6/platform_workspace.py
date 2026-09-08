from __future__ import annotations

"""TURTO 2.2.6 – visibility and substitution-safety workspace."""

from typing import Any
from tkinter import ttk

import platform_workspace_200 as _platform_base
import action_report as _action_report
import shear_dowels_schedule_guard  # noqa: F401 – unit guard before UI imports
from shear_dowels_current import build_shear_workspace, init_shear_workspace, install_methods
from shear_autocomplete import attach as attach_shear_autocomplete
from ui_help import compact_inline_help, install as install_help
from table_controls import install as install_table_controls
from ui_consistency import apply as apply_ui_consistency
from ui_layout import apply as apply_ui_layout
from ui_visibility import apply as apply_ui_visibility

WORKSPACE_VERSION = "2.2.6"


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
            if not isinstance(widget, ttk.Label):
                continue
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
        if frame is None:
            continue
        try:
            notebook.forget(frame)
        except Exception:
            pass


def install(app_base: Any) -> None:
    cls = app_base.ThermalConnectorApp
    if getattr(cls, "_turto_platform_workspace_226_installed", False):
        return

    _platform_base.install(app_base)
    install_help(app_base)

    cls = app_base.ThermalConnectorApp
    install_methods(cls)
    _platform_base.export_action_pdf = _action_report.export_action_pdf
    original_body = cls._build_body

    def body(self) -> None:
        original_body(self)
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

        try:
            self.base_window_title = f"TURTO {WORKSPACE_VERSION} – Technické prvky"
            self._update_project_title()
        except Exception:
            pass

    cls._build_body = body
    cls._turto_platform_workspace_226_installed = True


domain = _platform_base.domain
domains = _platform_base.domains
manufacturer = _platform_base.manufacturer
manufacturer_id_from_label = _platform_base.manufacturer_id_from_label
manufacturer_labels = _platform_base.manufacturer_labels
