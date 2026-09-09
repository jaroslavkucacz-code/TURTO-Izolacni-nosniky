from __future__ import annotations

"""TURTO 2.2.10 – local PDF catalog library and continued workspace cleanup."""

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
from ui_cleanup_229 import apply as apply_ui_cleanup_229
from pdf_scope import export_pdf_dialog
from catalog_browser import open_catalog_browser

WORKSPACE_VERSION = "2.2.10"


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


def _install_catalog_button(owner: Any) -> None:
    if getattr(owner, "_turto_catalog_button_229", None) is not None:
        return
    export_button = None
    for widget in _walk(owner):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) in {"Export PDF…", "Export PDF AKCE"}:
                export_button = widget
                break
        except Exception:
            pass
    if export_button is None:
        return
    parent = export_button.master
    button = ttk.Button(parent, text="Katalogy…", command=lambda: open_catalog_browser(owner))
    try:
        info = export_button.grid_info()
        if info:
            column = int(info.get("column", 0))
            row = int(info.get("row", 0))
            button.grid(row=row, column=column + 1, sticky="e", padx=(7, 0))
            try:
                parent.columnconfigure(column + 1, weight=0)
            except Exception:
                pass
        else:
            button.pack(side="right", padx=(7, 0))
    except Exception:
        button.pack(side="right", padx=(7, 0))
    owner._turto_catalog_button_229 = button


def install(app_base: Any) -> None:
    cls = app_base.ThermalConnectorApp
    if getattr(cls, "_turto_platform_workspace_230_installed", False):
        return

    _platform_base.install(app_base)
    install_help(app_base)
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
        apply_ui_cleanup_229(self)
        _install_catalog_button(self)

        try:
            self.base_window_title = f"TURTO {WORKSPACE_VERSION} – Technické prvky"
            self._update_project_title()
        except Exception:
            pass

    cls._build_body = body
    cls._turto_platform_workspace_230_installed = True


domain = _platform_base.domain
domains = _platform_base.domains
manufacturer = _platform_base.manufacturer
manufacturer_id_from_label = _platform_base.manufacturer_id_from_label
manufacturer_labels = _platform_base.manufacturer_labels
