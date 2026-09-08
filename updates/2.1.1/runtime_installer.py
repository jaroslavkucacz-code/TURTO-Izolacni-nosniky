from __future__ import annotations

"""TURTO 2.1.1 pinned overlay installer.

Installs the verified 2.1.0 runtime first, preserves its runtime modules as
explicit *_210 compatibility aliases, then overlays only the 2.1.1 decoder
changes. No AKCE database or catalogue file in AppData is modified.
"""

import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
import tkinter as tk

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_INSTALLER_COMMIT = "db23c1787e493f5dc4aa4fbf79282f45708f2bd8"
RUNTIME_COMMIT = "c2a7cf01b3d795b64de4df1b517a819768cf91b9"

OVERLAY = {
    "app_runtime.pyw": "updates/2.1.1/app_runtime.pyw",
    "shear_dowels_catalog.py": "updates/2.1.1/shear_dowels_catalog.py",
    "shear_dowels_ui.py": "updates/2.1.1/shear_dowels_ui.py",
}


def _download(url: str, user_agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={"User-Agent": user_agent, "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Stažený soubor je prázdný.")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout {url}\n{last}")


def _install_base(root: Path) -> None:
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/{BASE_INSTALLER_COMMIT}/"
        "updates/2.1.0/runtime_installer.py"
    )
    temp = Path(tempfile.mkdtemp(prefix="turto_210_base_")) / "runtime_installer.py"
    temp.write_bytes(_download(url, "TURTO-2.1.1-base"))
    ns = runpy.run_path(str(temp))
    install = ns.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Základní instalační modul 2.1.0 neobsahuje install_runtime().")
    install(root)


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    _install_base(root)

    # Preserve the verified 2.1.0 modules before replacing their public names.
    aliases = {
        "app_runtime.pyw": "app_runtime_210.pyw",
        "shear_dowels_catalog.py": "shear_dowels_catalog_210.py",
        "shear_dowels_ui.py": "shear_dowels_ui_210.py",
    }
    for source_name, alias_name in aliases.items():
        source = root / source_name
        if not source.is_file():
            raise RuntimeError(f"Po instalaci 2.1.0 chybí {source_name}.")
        shutil.copy2(source, root / alias_name)

    temp_root = Path(tempfile.mkdtemp(prefix="turto_211_", dir=str(root)))
    win = tk.Tk()
    win.title("TURTO 2.1.1 – aktualizace")
    win.geometry("690x190")
    win.resizable(False, False)
    win.configure(background="#F3F6F9")
    tk.Label(win, text="Připravuji TURTO 2.1.1", font=("Calibri", 15, "bold"), bg="#F3F6F9", fg="#17324D").pack(anchor="w", padx=22, pady=(22, 8))
    status = tk.Label(win, text="Doplňuji historické značení Schöck do Dekodéru…", font=("Calibri", 10), bg="#F3F6F9", fg="#172230")
    status.pack(anchor="w", padx=22)
    counter = tk.Label(win, text="", font=("Calibri", 9), bg="#F3F6F9", fg="#5C6878")
    counter.pack(anchor="w", padx=22, pady=(8, 0))
    win.update()
    downloaded = []
    try:
        for index, (local, remote) in enumerate(OVERLAY.items(), 1):
            status.configure(text=f"Stahuji: {local}")
            counter.configure(text=f"{index} / {len(OVERLAY)}")
            win.update()
            url = f"https://raw.githubusercontent.com/{REPOSITORY}/{RUNTIME_COMMIT}/{remote}"
            target = temp_root / local
            target.write_bytes(_download(url, "TURTO-2.1.1"))
            downloaded.append((target, root / local))
        status.configure(text="Instaluji rozšíření Dekodéru…")
        win.update()
        for source, target in downloaded:
            os.replace(source, target)
    finally:
        try:
            win.destroy()
        except Exception:
            pass
        shutil.rmtree(temp_root, ignore_errors=True)
