from __future__ import annotations

"""TURTO 2.1.4 multi-domain workspace.

2.1.4 sjednocuje pracovní postup smykových trnů s oblastí izolačních nosníků,
ale zachovává společnou platformu AKCE z TURTO 2.0.
"""

from typing import Any
from tkinter import ttk

import platform_workspace_200 as _prev
import action_report as _action_report
import shear_dowels_schedule_guard  # noqa: F401 - installs schedule unit guard before UI import
from shear_dowels_ui_214 import build_shear_workspace, init_shear_workspace, install_methods


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _fix_decoder_layout(owner: Any) -> None:
    decoder = getattr(owner, "project_tab", None)
    if decoder is None:
        return
    try:
        decoder.grid_rowconfigure(0, minsize=80, weight=0)
        decoder.grid_rowconfigure(1, minsize=52, weight=0)
        decoder.grid_rowconfigure(2, minsize=128, weight=0)
        decoder.grid_rowconfigure(3, weight=1)
    except Exception:
        pass
    for child in decoder.winfo_children():
        try:
            row = int(child.grid_info().get("row", -1))
            if row == 0:
                child.grid_configure(pady=(10, 8))
            elif row in {1, 2}:
                child.grid_configure(pady=(0, 10))
        except Exception:
            pass


def _update_branding(owner: Any) -> None:
    for widget in _walk(owner):
        try:
            if not isinstance(widget, ttk.Label):
                continue
            text = str(widget.cget("text"))
            if text in {
                "TURTO 2.0 | Technické prvky",
                "TURTO 2.1.2 | Technické prvky",
                "TURTO 2.1.3 | Technické prvky",
            }:
                widget.configure(text="TURTO 2.1.4 | Technické prvky")
            elif text.startswith("PDF je nadřazené produktovým oblastem."):
                widget.configure(
                    text="PDF je nadřazené produktovým oblastem a zahrnuje "
                         "izolační nosníky i návrhy smykových trnů."
                )
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
    if getattr(cls, "_turto_platform_workspace_214_installed", False):
        return

    # Nejdříve společný multi-domain shell, potom produktové adaptéry.
    _prev.install(app_base)

    cls = app_base.ThermalConnectorApp
    install_methods(cls)
    _prev.export_action_pdf = _action_report.export_action_pdf
    original_body = cls._build_body

    def body(self) -> None:
        original_body(self)
        init_shear_workspace(self)
        _fix_decoder_layout(self)
        _update_branding(self)

        frame = getattr(self, "product_domain_tab_by_id", {}).get("shear_dowels")
        if frame is not None:
            for child in list(frame.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            build_shear_workspace(self, frame)

        _hide_inactive_domains(self)
        try:
            self.base_window_title = "TURTO 2.1.4 – Technické prvky"
            self._update_project_title()
        except Exception:
            pass

    cls._build_body = body
    cls._turto_platform_workspace_214_installed = True


domain = _prev.domain
domains = _prev.domains
manufacturer = _prev.manufacturer
manufacturer_id_from_label = _prev.manufacturer_id_from_label
manufacturer_labels = _prev.manufacturer_labels
