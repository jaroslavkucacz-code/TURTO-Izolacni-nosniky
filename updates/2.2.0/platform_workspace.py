from __future__ import annotations

"""TURTO 2.2.0 – stabilizovaná multi-domain pracovní plocha."""

from typing import Any
from tkinter import ttk

import platform_workspace_200 as _platform_base
import action_report as _action_report
import shear_dowels_schedule_guard  # noqa: F401 – ochrana jednotek před importem UI
from shear_dowels_current import build_shear_workspace, init_shear_workspace, install_methods

WORKSPACE_VERSION = "2.2.0"

def _walk(root: Any):
    stack=[root]
    while stack:
        widget=stack.pop(); yield widget
        try: stack.extend(widget.winfo_children())
        except Exception: pass

def _fix_decoder_layout(owner: Any) -> None:
    decoder=getattr(owner,"project_tab",None)
    if decoder is None: return
    try:
        decoder.grid_rowconfigure(0,minsize=80,weight=0); decoder.grid_rowconfigure(1,minsize=52,weight=0); decoder.grid_rowconfigure(2,minsize=128,weight=0); decoder.grid_rowconfigure(3,weight=1)
    except Exception: pass
    for child in decoder.winfo_children():
        try:
            row=int(child.grid_info().get("row",-1))
            if row==0: child.grid_configure(pady=(10,8))
            elif row in {1,2}: child.grid_configure(pady=(0,10))
        except Exception: pass

def _update_branding(owner: Any) -> None:
    for widget in _walk(owner):
        try:
            if not isinstance(widget,ttk.Label): continue
            text=str(widget.cget("text"))
            if text.startswith("TURTO 2.") and text.endswith("| Technické prvky"): widget.configure(text=f"TURTO {WORKSPACE_VERSION} | Technické prvky")
            elif text.startswith("PDF je nadřazené produktovým oblastem."): widget.configure(text="PDF je nadřazené produktovým oblastem a zahrnuje izolační nosníky i návrhy smykových trnů.")
        except Exception: pass

def _hide_inactive_domains(owner: Any) -> None:
    notebook=getattr(owner,"product_domain_notebook",None); frames=getattr(owner,"product_domain_tab_by_id",{})
    if notebook is None or not isinstance(frames,dict): return
    for spec in domains():
        if getattr(spec,"enabled",False): continue
        frame=frames.get(spec.id)
        if frame is None: continue
        try: notebook.forget(frame)
        except Exception: pass

def install(app_base: Any) -> None:
    cls=app_base.ThermalConnectorApp
    if getattr(cls,"_turto_platform_workspace_current_installed",False): return
    _platform_base.install(app_base)
    cls=app_base.ThermalConnectorApp; install_methods(cls); _platform_base.export_action_pdf=_action_report.export_action_pdf; original_body=cls._build_body
    def body(self) -> None:
        original_body(self); init_shear_workspace(self); _fix_decoder_layout(self); _update_branding(self)
        frame=getattr(self,"product_domain_tab_by_id",{}).get("shear_dowels")
        if frame is not None:
            for child in list(frame.winfo_children()):
                try: child.destroy()
                except Exception: pass
            build_shear_workspace(self,frame)
        _hide_inactive_domains(self)
        try: self.base_window_title=f"TURTO {WORKSPACE_VERSION} – Technické prvky"; self._update_project_title()
        except Exception: pass
    cls._build_body=body; cls._turto_platform_workspace_current_installed=True

domain=_platform_base.domain
domains=_platform_base.domains
manufacturer=_platform_base.manufacturer
manufacturer_id_from_label=_platform_base.manufacturer_id_from_label
manufacturer_labels=_platform_base.manufacturer_labels
