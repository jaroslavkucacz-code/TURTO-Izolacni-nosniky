from __future__ import annotations

"""Pinned runtime installer for TURTO 2.0.2.

This file is only used by the small bootstrap app.pyw. Runtime files are read
from one immutable Git commit, so a clean 1.1.x installation can jump directly
to 2.0.2 without mixing files from different releases.
"""

import os
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
import tkinter as tk

RUNTIME_COMMIT = "52d1586bec59e55870fc0bd6db6d49bacb690af8"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"

FILES = {
    "app_runtime.pyw": "updates/2.0.2/app_runtime.pyw",
    "hit_workspace.py": "updates/2.0.2/hit_workspace.py",
    "hit_workspace_201.py": "updates/2.0.1/hit_workspace.py",
    "app_runtime_200.pyw": "updates/2.0.0/app_runtime.pyw",
    "hit_workspace_200.py": "updates/2.0.0/hit_workspace.py",
    "platform_registry.py": "updates/2.0.0/platform_registry.py",
    "platform_state.py": "updates/2.0.0/platform_state.py",
    "platform_workspace.py": "updates/2.0.0/platform_workspace.py",
    "action_report.py": "updates/2.0.0/action_report.py",
    "supplier_export.py": "updates/2.0.0/supplier_export.py",
    "unified_schedule.py": "updates/2.0.0/unified_schedule.py",
    "action_payload.py": "updates/2.0.0/action_payload.py",
    "action_browser.py": "updates/2.0.0/action_browser.py",
    "app_runtime_127.pyw": "updates/1.1.27/app_runtime.pyw",
    "app_runtime_prev.pyw": "updates/1.1.25/app_runtime.pyw",
    "app_central_prev.pyw": "updates/1.1.23/app.pyw",
    "app_base.py": "updates/1.1.17/app.pyw",
    "project_ui.py": "updates/1.1.25/project_ui.py",
    "project_ui_prev.py": "updates/1.1.23/project_ui.py",
    "project_ui_base.py": "updates/1.1.17/project_ui.py",
    "action_store.py": "updates/1.1.27/action_store.py",
    "action_store_125.py": "updates/1.1.25/action_store.py",
    "action_store_prev.py": "updates/1.1.23/action_store.py",
    "action_payload_127.py": "updates/1.1.27/action_payload.py",
    "action_payload_125.py": "updates/1.1.25/action_payload.py",
    "action_payload_prev.py": "updates/1.1.23/action_payload.py",
    "action_browser_123.py": "updates/1.1.23/action_browser.py",
    "action_workspace.py": "updates/1.1.23/action_workspace.py",
    "decoder_detail.py": "updates/1.1.23/decoder_detail.py",
    "hit_decoder_records.py": "updates/1.1.25/hit_decoder_records.py",
    "hit_decoder_records_prev.py": "updates/1.1.23/hit_decoder_records.py",
    "hit_decoder_suggest.py": "updates/1.1.25/hit_decoder_suggest.py",
    "hit_decoder_suggest_prev.py": "updates/1.1.23/hit_decoder_suggest.py",
    "hit_decoder_catalog.py": "updates/1.1.25/hit_decoder_catalog.py",
    "hit_decoder_catalog_prev.py": "updates/1.1.23/hit_decoder_catalog.py",
    "hit_wt.py": "updates/1.1.25/hit_wt.py",
    "hit_wt_ui.py": "updates/1.1.25/hit_wt_ui.py",
    "wt_safety_guard.py": "updates/1.1.25/wt_safety_guard.py",
    "table_polish.py": "updates/1.1.25/table_polish.py",
    "hit_aux_ui.py": "updates/1.1.27/hit_aux_ui.py",
    "hit_workspace_127.py": "updates/1.1.27/hit_workspace.py",
    "hit_workspace_125.py": "updates/1.1.25/hit_workspace.py",
    "hit_workspace_prev.py": "updates/1.1.22/hit_workspace.py",
    "hit_workspace_base.py": "updates/1.1.17/hit_workspace.py",
    "hit_design_store.py": "updates/1.1.21/hit_design_store.py",
    "hit_design_ui.py": "updates/1.1.21/hit_design_ui.py",
    "hit_excel.py": "updates/1.1.21/hit_excel.py",
    "hit_export_ui.py": "updates/1.1.27/hit_export_ui.py",
    "hit_export_ui_127.py": "updates/1.1.27/hit_export_ui.py",
    "hit_export_ui_prev.py": "updates/1.1.21/hit_export_ui.py",
    "hit_pdf.py": "updates/1.1.27/hit_pdf.py",
    "hit_pdf_127.py": "updates/1.1.27/hit_pdf.py",
    "hit_pdf_prev.py": "updates/1.1.20/hit_pdf.py",
    "hit_row_extension.py": "updates/1.1.22/hit_row_extension.py",
    "hit_schedule.py": "updates/1.1.27/hit_schedule.py",
    "hit_schedule_127.py": "updates/1.1.27/hit_schedule.py",
    "hit_schedule_126.py": "updates/1.1.26/hit_schedule.py",
    "hit_schedule_prev.py": "updates/1.1.22/hit_schedule.py",
    "hit_schedule_base.py": "updates/1.1.17/hit_schedule.py",
    "hit_virtual_scroll.py": "updates/1.1.21/hit_virtual_scroll.py",
    "hit_core.py": "updates/1.1.17/hit_core.py",
    "hit_ht.py": "updates/1.1.17/hit_ht.py",
    "hit_special.py": "updates/1.1.17/hit_special.py",
    "project_model.py": "updates/1.1.17/project_model.py",
    "substitution_workspace.py": "updates/1.1.17/substitution_workspace.py",
    "substitution_review.py": "updates/1.1.17/substitution_review.py",
    "substitution_pdf.py": "updates/1.1.19/substitution_pdf.py",
    "substitution_pdf_base.py": "updates/1.1.17/substitution_pdf.py",
    "catalog_engine.py": "updates/1.1.17/catalog_engine.py",
    "autocomplete.py": "updates/1.1.17/autocomplete.py",
    "bulk_import.py": "updates/1.1.17/bulk_import.py",
    "bulk_import_engine.py": "updates/1.1.17/bulk_import_engine.py",
    "ui_utils.py": "updates/1.1.17/ui_utils.py",
    "xlsx_export.py": "updates/1.1.17/xlsx_export.py",
}


def _url(repo_path: str) -> str:
    return "https://raw.githubusercontent.com/" + REPOSITORY + "/" + RUNTIME_COMMIT + "/" + repo_path


def _download(url: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            suffix = "?turto=" + str(int(time.time() * 1000)) + "_" + str(attempt)
            request = urllib.request.Request(
                url + suffix,
                headers={
                    "User-Agent": "TURTO-2.0.2",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Stažený soubor je prázdný.")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1.0 + attempt)
    raise RuntimeError(f"Nelze stáhnout {url}\n{last}")


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    temp_root = Path(tempfile.mkdtemp(prefix="turto_202_", dir=str(root)))
    window = tk.Tk()
    window.title("TURTO 2.0.2 – dokončení opravy")
    window.geometry("690x200")
    window.resizable(False, False)
    window.configure(background="#F3F6F9")
    try:
        window.eval("tk::PlaceWindow . center")
    except Exception:
        pass
    tk.Label(window, text="Připravuji TURTO 2.0.2", font=("Calibri", 15, "bold"), bg="#F3F6F9", fg="#17324D").pack(anchor="w", padx=22, pady=(22, 8))
    status = tk.Label(window, text="Instaluji opravenou platformu…", font=("Calibri", 10), bg="#F3F6F9", fg="#172230", justify="left", wraplength=640)
    status.pack(anchor="w", padx=22)
    counter = tk.Label(window, text="", font=("Calibri", 9), bg="#F3F6F9", fg="#5C6878")
    counter.pack(anchor="w", padx=22, pady=(8, 0))
    window.update()

    downloaded = []
    try:
        total = len(FILES)
        for index, (local, remote) in enumerate(FILES.items(), 1):
            status.configure(text=f"Stahuji: {local}")
            counter.configure(text=f"{index} / {total}")
            window.update()
            data = _download(_url(remote))
            temp_path = temp_root / local
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(data)
            downloaded.append((temp_path, root / local))
        status.configure(text="Instaluji opravenou sadu souborů…")
        window.update()
        for source, target in downloaded:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        shutil.rmtree(temp_root, ignore_errors=True)
