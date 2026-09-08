from __future__ import annotations

"""TURTO 2.1.1 small immutable bootstrap."""

import runpy
import tempfile
import time
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

VERSION = "2.1.1"
INSTALLER_COMMIT = "2e9d373094174e329a3c09d9b9c705f93945325e"
RUNTIME_COMMIT = "c2a7cf01b3d795b64de4df1b517a819768cf91b9"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
ROOT = Path(__file__).resolve().parent
MARKER = ROOT / ".turto_runtime_2_1_1.ok"


def _runtime_ready() -> bool:
    try:
        return (
            MARKER.is_file()
            and MARKER.read_text(encoding="utf-8").strip() == RUNTIME_COMMIT
            and (ROOT / "app_runtime.pyw").is_file()
            and (ROOT / "shear_dowels_catalog.py").is_file()
            and (ROOT / "shear_dowels_catalog_210.py").is_file()
        )
    except Exception:
        return False


def _download_installer() -> Path:
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/updates/2.1.1/runtime_installer.py"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={"User-Agent": "TURTO-2.1.1", "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Stažený instalační soubor je prázdný.")
            target = Path(tempfile.mkdtemp(prefix="turto_bootstrap_")) / "runtime_installer.py"
            target.write_bytes(data)
            return target
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout instalační modul.\n{last}")


def _install_runtime() -> None:
    ns = runpy.run_path(str(_download_installer()))
    install = ns.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Stažený instalační modul neobsahuje install_runtime().")
    install(ROOT)
    MARKER.write_text(RUNTIME_COMMIT, encoding="utf-8")


def _show_failure(exc: Exception) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Aktualizace TURTO 2.1.1",
            "Dokončení aktualizace se nezdařilo. Databáze AKCÍ ani katalogy nebyly měněny.\n\n"
            + str(exc)
            + "\n\nZkuste program spustit znovu; instalace se zopakuje z pevně připnutého vydání.",
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
    if not target.is_file():
        _show_failure(RuntimeError("Chybí app_runtime.pyw po aktualizaci."))
        return 3
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
