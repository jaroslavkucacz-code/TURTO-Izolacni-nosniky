from __future__ import annotations
import os, shutil, tempfile, time, urllib.request
from pathlib import Path
import tkinter as tk
RUNTIME_COMMIT="259c59c73854ade7f1e668f49e03a6e9b59fd8f9"
REPOSITORY="jaroslavkucacz-code/TURTO-Izolacni-nosniky"
FILES={
"app_runtime.pyw":"updates/2.1.0/app_runtime.pyw","shear_dowels_catalog.py":"updates/2.1.0/shear_dowels_catalog.py","shear_dowels_ui.py":"updates/2.1.0/shear_dowels_ui.py","platform_registry.py":"updates/2.1.0/platform_registry.py","platform_state.py":"updates/2.1.0/platform_state.py","platform_workspace.py":"updates/2.1.0/platform_workspace.py","action_payload.py":"updates/2.1.0/action_payload.py","action_report.py":"updates/2.1.0/action_report.py","action_store.py":"updates/2.1.0/action_store.py","hit_pdf.py":"updates/2.1.0/hit_pdf.py",
"app_runtime_202.pyw":"updates/2.0.2/app_runtime.pyw","app_runtime_200.pyw":"updates/2.0.0/app_runtime.pyw","hit_workspace.py":"updates/2.0.2/hit_workspace.py","hit_workspace_201.py":"updates/2.0.1/hit_workspace.py","hit_workspace_200.py":"updates/2.0.0/hit_workspace.py","platform_registry_200.py":"updates/2.0.0/platform_registry.py","platform_state_200.py":"updates/2.0.0/platform_state.py","platform_workspace_200.py":"updates/2.0.0/platform_workspace.py","action_payload_200.py":"updates/2.0.0/action_payload.py","action_store_127.py":"updates/1.1.27/action_store.py","action_browser.py":"updates/2.0.0/action_browser.py","supplier_export.py":"updates/2.0.0/supplier_export.py","unified_schedule.py":"updates/2.0.0/unified_schedule.py",
"app_runtime_127.pyw":"updates/1.1.27/app_runtime.pyw","app_runtime_prev.pyw":"updates/1.1.25/app_runtime.pyw","app_central_prev.pyw":"updates/1.1.23/app.pyw","app_base.py":"updates/1.1.17/app.pyw","project_ui.py":"updates/1.1.25/project_ui.py","project_ui_prev.py":"updates/1.1.23/project_ui.py","project_ui_base.py":"updates/1.1.17/project_ui.py","action_store_125.py":"updates/1.1.25/action_store.py","action_store_prev.py":"updates/1.1.23/action_store.py","action_payload_127.py":"updates/1.1.27/action_payload.py","action_payload_125.py":"updates/1.1.25/action_payload.py","action_payload_prev.py":"updates/1.1.23/action_payload.py","action_browser_123.py":"updates/1.1.23/action_browser.py","action_workspace.py":"updates/1.1.23/action_workspace.py","decoder_detail.py":"updates/1.1.23/decoder_detail.py","hit_decoder_records.py":"updates/1.1.25/hit_decoder_records.py","hit_decoder_records_prev.py":"updates/1.1.23/hit_decoder_records.py","hit_decoder_suggest.py":"updates/1.1.25/hit_decoder_suggest.py","hit_decoder_suggest_prev.py":"updates/1.1.23/hit_decoder_suggest.py","hit_decoder_catalog.py":"updates/1.1.25/hit_decoder_catalog.py","hit_decoder_catalog_prev.py":"updates/1.1.23/hit_decoder_catalog.py","hit_wt.py":"updates/1.1.25/hit_wt.py","hit_wt_ui.py":"updates/1.1.25/hit_wt_ui.py","wt_safety_guard.py":"updates/1.1.25/wt_safety_guard.py","table_polish.py":"updates/1.1.25/table_polish.py","hit_aux_ui.py":"updates/1.1.27/hit_aux_ui.py","hit_workspace_127.py":"updates/1.1.27/hit_workspace.py","hit_workspace_125.py":"updates/1.1.25/hit_workspace.py","hit_workspace_prev.py":"updates/1.1.22/hit_workspace.py","hit_workspace_base.py":"updates/1.1.17/hit_workspace.py","hit_design_store.py":"updates/1.1.21/hit_design_store.py","hit_design_ui.py":"updates/1.1.21/hit_design_ui.py","hit_excel.py":"updates/1.1.21/hit_excel.py","hit_export_ui.py":"updates/1.1.27/hit_export_ui.py","hit_export_ui_127.py":"updates/1.1.27/hit_export_ui.py","hit_export_ui_prev.py":"updates/1.1.21/hit_export_ui.py","hit_pdf_127.py":"updates/1.1.27/hit_pdf.py","hit_pdf_prev.py":"updates/1.1.20/hit_pdf.py","hit_row_extension.py":"updates/1.1.22/hit_row_extension.py","hit_schedule.py":"updates/1.1.27/hit_schedule.py","hit_schedule_127.py":"updates/1.1.27/hit_schedule.py","hit_schedule_126.py":"updates/1.1.26/hit_schedule.py","hit_schedule_prev.py":"updates/1.1.22/hit_schedule.py","hit_schedule_base.py":"updates/1.1.17/hit_schedule.py","hit_virtual_scroll.py":"updates/1.1.21/hit_virtual_scroll.py","hit_core.py":"updates/1.1.17/hit_core.py","hit_ht.py":"updates/1.1.17/hit_ht.py","hit_special.py":"updates/1.1.17/hit_special.py","project_model.py":"updates/1.1.17/project_model.py","substitution_workspace.py":"updates/1.1.17/substitution_workspace.py","substitution_review.py":"updates/1.1.17/substitution_review.py","substitution_pdf.py":"updates/1.1.19/substitution_pdf.py","substitution_pdf_base.py":"updates/1.1.17/substitution_pdf.py","catalog_engine.py":"updates/1.1.17/catalog_engine.py","autocomplete.py":"updates/1.1.17/autocomplete.py","bulk_import.py":"updates/1.1.17/bulk_import.py","bulk_import_engine.py":"updates/1.1.17/bulk_import_engine.py","ui_utils.py":"updates/1.1.17/ui_utils.py","xlsx_export.py":"updates/1.1.17/xlsx_export.py"}
def _url(path):return f"https://raw.githubusercontent.com/{REPOSITORY}/{RUNTIME_COMMIT}/{path}"
def _download(url):
    last=None
    for attempt in range(4):
        try:
            req=urllib.request.Request(url+f"?turto={int(time.time()*1000)}_{attempt}",headers={"User-Agent":"TURTO-2.1.0","Cache-Control":"no-cache, no-store","Pragma":"no-cache"})
            with urllib.request.urlopen(req,timeout=45) as r:data=r.read()
            if not data:raise RuntimeError("Stažený soubor je prázdný.")
            return data
        except Exception as exc:
            last=exc
            if attempt<3:time.sleep(1+attempt)
    raise RuntimeError(f"Nelze stáhnout {url}\n{last}")
def install_runtime(root):
    root=Path(root).resolve();tmp=Path(tempfile.mkdtemp(prefix="turto_210_",dir=str(root)));win=tk.Tk();win.title("TURTO 2.1 – aktualizace");win.geometry("690x200");win.resizable(False,False);win.configure(background="#F3F6F9")
    tk.Label(win,text="Připravuji TURTO 2.1",font=("Calibri",15,"bold"),bg="#F3F6F9",fg="#17324D").pack(anchor="w",padx=22,pady=(22,8));status=tk.Label(win,text="Instaluji modul smykových trnů…",font=("Calibri",10),bg="#F3F6F9",fg="#172230");status.pack(anchor="w",padx=22);counter=tk.Label(win,text="",font=("Calibri",9),bg="#F3F6F9",fg="#5C6878");counter.pack(anchor="w",padx=22,pady=(8,0));win.update();files=[]
    try:
        for i,(local,remote) in enumerate(FILES.items(),1):
            status.configure(text=f"Stahuji: {local}");counter.configure(text=f"{i} / {len(FILES)}");win.update();p=tmp/local;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(_download(_url(remote)));files.append((p,root/local))
        status.configure(text="Instaluji ověřenou sadu souborů…");win.update()
        for src,dst in files:dst.parent.mkdir(parents=True,exist_ok=True);os.replace(src,dst)
    finally:
        try:win.destroy()
        except Exception:pass
        shutil.rmtree(tmp,ignore_errors=True)
