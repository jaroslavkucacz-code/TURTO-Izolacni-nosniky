from __future__ import annotations

"""TURTO ISO 1.1.27 immutable runtime bootstrap."""

import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

VERSION = "1.1.27"
PINNED_COMMIT = "206e22d1c2c645e163f0bbdf167e7574c2af060e"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
ROOT = Path(__file__).resolve().parent
MARKER = ROOT / ".turto_runtime_1_1_27.ok"

FILES = {'app_runtime.pyw': 'updates/1.1.27/app_runtime.pyw', 'app_runtime_prev.pyw': 'updates/1.1.25/app_runtime.pyw', 'app_central_prev.pyw': 'updates/1.1.23/app.pyw', 'app_base.py': 'updates/1.1.17/app.pyw', 'project_ui.py': 'updates/1.1.25/project_ui.py', 'project_ui_prev.py': 'updates/1.1.23/project_ui.py', 'project_ui_base.py': 'updates/1.1.17/project_ui.py', 'action_store.py': 'updates/1.1.27/action_store.py', 'action_store_125.py': 'updates/1.1.25/action_store.py', 'action_store_prev.py': 'updates/1.1.23/action_store.py', 'action_payload.py': 'updates/1.1.27/action_payload.py', 'action_payload_125.py': 'updates/1.1.25/action_payload.py', 'action_payload_prev.py': 'updates/1.1.23/action_payload.py', 'action_browser.py': 'updates/1.1.23/action_browser.py', 'action_workspace.py': 'updates/1.1.23/action_workspace.py', 'decoder_detail.py': 'updates/1.1.23/decoder_detail.py', 'hit_decoder_records.py': 'updates/1.1.25/hit_decoder_records.py', 'hit_decoder_records_prev.py': 'updates/1.1.23/hit_decoder_records.py', 'hit_decoder_suggest.py': 'updates/1.1.25/hit_decoder_suggest.py', 'hit_decoder_suggest_prev.py': 'updates/1.1.23/hit_decoder_suggest.py', 'hit_decoder_catalog.py': 'updates/1.1.25/hit_decoder_catalog.py', 'hit_decoder_catalog_prev.py': 'updates/1.1.23/hit_decoder_catalog.py', 'hit_wt.py': 'updates/1.1.25/hit_wt.py', 'hit_wt_ui.py': 'updates/1.1.25/hit_wt_ui.py', 'wt_safety_guard.py': 'updates/1.1.25/wt_safety_guard.py', 'table_polish.py': 'updates/1.1.25/table_polish.py', 'hit_aux_ui.py': 'updates/1.1.27/hit_aux_ui.py', 'hit_workspace.py': 'updates/1.1.27/hit_workspace.py', 'hit_workspace_125.py': 'updates/1.1.25/hit_workspace.py', 'hit_workspace_prev.py': 'updates/1.1.22/hit_workspace.py', 'hit_workspace_base.py': 'updates/1.1.17/hit_workspace.py', 'hit_design_store.py': 'updates/1.1.21/hit_design_store.py', 'hit_design_ui.py': 'updates/1.1.21/hit_design_ui.py', 'hit_excel.py': 'updates/1.1.21/hit_excel.py', 'hit_export_ui.py': 'updates/1.1.27/hit_export_ui.py', 'hit_export_ui_prev.py': 'updates/1.1.21/hit_export_ui.py', 'hit_pdf.py': 'updates/1.1.27/hit_pdf.py', 'hit_pdf_prev.py': 'updates/1.1.20/hit_pdf.py', 'hit_row_extension.py': 'updates/1.1.22/hit_row_extension.py', 'hit_schedule.py': 'updates/1.1.27/hit_schedule.py', 'hit_schedule_126.py': 'updates/1.1.26/hit_schedule.py', 'hit_schedule_prev.py': 'updates/1.1.22/hit_schedule.py', 'hit_schedule_base.py': 'updates/1.1.17/hit_schedule.py', 'hit_virtual_scroll.py': 'updates/1.1.21/hit_virtual_scroll.py', 'hit_core.py': 'updates/1.1.17/hit_core.py', 'hit_ht.py': 'updates/1.1.17/hit_ht.py', 'hit_special.py': 'updates/1.1.17/hit_special.py', 'project_model.py': 'updates/1.1.17/project_model.py', 'substitution_workspace.py': 'updates/1.1.17/substitution_workspace.py', 'substitution_review.py': 'updates/1.1.17/substitution_review.py', 'substitution_pdf.py': 'updates/1.1.19/substitution_pdf.py', 'substitution_pdf_base.py': 'updates/1.1.17/substitution_pdf.py', 'catalog_engine.py': 'updates/1.1.17/catalog_engine.py', 'autocomplete.py': 'updates/1.1.17/autocomplete.py', 'bulk_import.py': 'updates/1.1.17/bulk_import.py', 'bulk_import_engine.py': 'updates/1.1.17/bulk_import_engine.py', 'ui_utils.py': 'updates/1.1.17/ui_utils.py', 'xlsx_export.py': 'updates/1.1.17/xlsx_export.py'}


def _url(repo_path: str) -> str:
    return "https://raw.githubusercontent.com/" + REPOSITORY + "/" + PINNED_COMMIT + "/" + repo_path


def _download(url: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            suffix = "?turto=" + str(int(time.time() * 1000)) + "_" + str(attempt)
            req = urllib.request.Request(
                url + suffix,
                headers={
                    "User-Agent": "TURTO-ISO-1.1.27",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=40) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Stažený soubor je prázdný.")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1.0 + attempt)
    raise RuntimeError(f"Nelze stáhnout {url}\n{last}")


def _runtime_ready() -> bool:
    if not MARKER.exists():
        return False
    try:
        if MARKER.read_text(encoding="utf-8").strip() != PINNED_COMMIT:
            return False
    except Exception:
        return False
    return all((ROOT / local).is_file() for local in FILES)


def _install_runtime() -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="turto_1127_", dir=str(ROOT)))
    window = tk.Tk()
    window.title("TURTO ISO – dokončení aktualizace")
    window.geometry("660x190")
    window.resizable(False, False)
    window.configure(background="#F3F6F9")
    try:
        window.eval("tk::PlaceWindow . center")
    except Exception:
        pass
    tk.Label(
        window,
        text="Dokončuji aktualizaci TURTO ISO 1.1.27",
        font=("Calibri", 15, "bold"),
        bg="#F3F6F9",
        fg="#17324D",
    ).pack(anchor="w", padx=22, pady=(22, 8))
    status = tk.Label(
        window,
        text="Připravuji pracovní prostředí…",
        font=("Calibri", 10),
        bg="#F3F6F9",
        fg="#172230",
        justify="left",
        wraplength=610,
    )
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
            downloaded.append((temp_path, ROOT / local))

        status.configure(text="Instaluji ověřenou sadu souborů…")
        window.update()
        for source, target in downloaded:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
        MARKER.write_text(PINNED_COMMIT, encoding="utf-8")
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        shutil.rmtree(temp_root, ignore_errors=True)


def _show_failure(exc: Exception) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Aktualizace TURTO ISO",
            "Dokončení aktualizace 1.1.27 se nezdařilo. Centrální databáze AKCÍ ani katalogy nebyly měněny.\n\n"
            + str(exc)
            + "\n\nZkuste program spustit znovu; stažení se zopakuje z neměnného Git commitu.",
            parent=root,
        )
        root.destroy()
    except Exception:
        pass


def main() -> int:
    try:
        if not _runtime_ready():
            _install_runtime()
    except Exception as exc:
        _show_failure(exc)
        return 2
    target = ROOT / "app_runtime.pyw"
    if not target.exists():
        _show_failure(RuntimeError("Chybí app_runtime.pyw po dokončení aktualizace."))
        return 3
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
