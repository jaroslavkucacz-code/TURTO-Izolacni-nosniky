from __future__ import annotations
from typing import Any
from tkinter import ttk
import platform_workspace_200 as _prev
import action_report as _action_report
from shear_dowels_ui import build_shear_workspace,init_shear_workspace,install_methods

def _walk(root:Any):
    stack=[root]
    while stack:
        w=stack.pop();yield w
        try:stack.extend(w.winfo_children())
        except Exception:pass

def _fix_decoder_layout(owner:Any)->None:
    decoder=getattr(owner,"project_tab",None)
    if decoder is None:return
    try:
        decoder.grid_rowconfigure(0,minsize=80,weight=0);decoder.grid_rowconfigure(1,minsize=52,weight=0);decoder.grid_rowconfigure(2,minsize=128,weight=0);decoder.grid_rowconfigure(3,weight=1)
    except Exception:pass
    for child in decoder.winfo_children():
        try:
            row=int(child.grid_info().get("row",-1))
            if row==0:child.grid_configure(pady=(10,8))
            elif row in {1,2}:child.grid_configure(pady=(0,10))
        except Exception:pass

def _update_report_banner(owner:Any)->None:
    for w in _walk(owner):
        try:
            if isinstance(w,ttk.Label) and str(w.cget("text")).startswith("PDF je nadřazené produktovým oblastem."):w.configure(text="PDF je nadřazené produktovým oblastem a zahrnuje aktuálně izolační nosníky i návrhy smykových trnů.")
        except Exception:pass

def install(app_base:Any)->None:
    cls=app_base.ThermalConnectorApp;install_methods(cls);_prev.export_action_pdf=_action_report.export_action_pdf;original_body=cls._build_body
    def body(self)->None:
        original_body(self);init_shear_workspace(self);_fix_decoder_layout(self);_update_report_banner(self);frame=getattr(self,"product_domain_tab_by_id",{}).get("shear_dowels")
        if frame is not None:
            for child in list(frame.winfo_children()):
                try:child.destroy()
                except Exception:pass
            build_shear_workspace(self,frame)
        try:self.base_window_title="TURTO 2.1 – Technické prvky";self._update_project_title()
        except Exception:pass
    cls._build_body=body

domain=_prev.domain
domains=_prev.domains
manufacturer=_prev.manufacturer
manufacturer_id_from_label=_prev.manufacturer_id_from_label
manufacturer_labels=_prev.manufacturer_labels
