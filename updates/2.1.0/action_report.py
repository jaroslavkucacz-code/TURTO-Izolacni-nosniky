from __future__ import annotations
import os,re,webbrowser
from pathlib import Path
from typing import Any
from tkinter import filedialog,messagebox
import hit_export_ui_127 as _thermal
from hit_pdf import ensure_hit_pdf_backend,write_hit_proposal_pdf

def _thermal_rows(owner:Any):
    if hasattr(owner,"recalculate_hit_all"):owner.recalculate_hit_all()
    if hasattr(owner,"recalculate_aux_all"):owner.recalculate_aux_all()
    if hasattr(owner,"recalculate_wt_all"):owner.recalculate_wt_all()
    rows=_thermal.collect_all_hit_rows(owner)
    for r in rows:r["domain_id"]="thermal_breaks";r["domain"]="Izolační nosníky"
    return rows

def _shear_rows(owner:Any):return owner.collect_shear_report_rows() if hasattr(owner,"collect_shear_report_rows") else []
def collect_action_report_rows(owner:Any):return [*_thermal_rows(owner),*_shear_rows(owner)]
def _open(path:Path):
    try:
        if os.name=="nt":os.startfile(str(path))
        else:webbrowser.open(path.resolve().as_uri())
    except Exception:pass

def export_action_pdf(owner:Any)->None:
    try:rows=collect_action_report_rows(owner)
    except Exception as exc:messagebox.showerror("Export PDF AKCE",f"Přepočet podkladů se nezdařil.\n\n{exc}",parent=owner);return
    if not rows:messagebox.showinfo("Export PDF AKCE","AKCE zatím neobsahuje žádný navržený prvek k exportu.",parent=owner);return
    action=str(getattr(owner,"project_name_var",None).get() or getattr(owner.project,"name","AKCE") or "AKCE").strip();safe=re.sub(r'[\\/:*?"<>|]+',"_",action).strip() or "AKCE"
    path=filedialog.asksaveasfilename(parent=owner,title="Uložit PDF výstup celé AKCE",defaultextension=".pdf",initialfile=f"TURTO_AKCE_{safe}.pdf",filetypes=[("PDF","*.pdf")])
    if not path:return
    try:ensure_hit_pdf_backend();target=write_hit_proposal_pdf(Path(path),project_name=action,rows=rows,creator="Vytvořil Ing. Jaroslav Kučera")
    except Exception as exc:messagebox.showerror("Export PDF AKCE se nezdařil",str(exc),parent=owner);return
    try:domains=sorted({r.get("domain","") for r in rows if r.get("domain")});owner.set_status(f"PDF celé AKCE exportováno: {target.name} • "+", ".join(domains))
    except Exception:pass
    _open(target)
