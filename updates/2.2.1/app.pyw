from __future__ import annotations

"""TURTO 2.2.1 – malý stabilní bootstrap s obecnou recovery cestou."""

import hashlib
import runpy
import shutil
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

VERSION = "2.2.1"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "983f536b0c978bc0c9d33c4ff18613ac7b40ae8d"
INSTALLER_SHA256 = "f69bec481d2181df6d426fb5ad35260b264a3304486a344366f1f7fea04adaf8"
RUNTIME_LAYOUT = "2"
ROOT = Path(__file__).resolve().parent
MARKER = ROOT / ".turto_runtime_current.ok"
STARTUP_LOG = ROOT / "startup.log"
REQUIRED_RUNTIME_FILES = (
    "app_runtime.pyw",
    "platform_workspace.py",
    "hit_workspace.py",
    "updater.py",
    "shear_dowels_catalog.py",
    "shear_dowels_ui.py",
    "shear_dowels_current.py",
    "shear_dowels_ui_215.py",
    "schoeck_dorn_decoder.py",
)


def _runtime_ready() -> bool:
    try:
        return (
            MARKER.is_file()
            and MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and all((ROOT / name).is_file() for name in REQUIRED_RUNTIME_FILES)
        )
    except Exception:
        return False


def _download_installer() -> Path:
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/"
        "updates/2.2.1/runtime_installer.py"
    )
    last = None
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_bootstrap_"))
    target = temp_dir / "runtime_installer.py"
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={
                    "User-Agent": "TURTO-2.2.1-Bootstrap",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Stažený instalační soubor je prázdný.")
            actual = hashlib.sha256(data).hexdigest().lower()
            if actual != INSTALLER_SHA256:
                raise RuntimeError(
                    "Kontrolní součet instalačního modulu nesouhlasí.\n"
                    f"Očekáváno: {INSTALLER_SHA256}\nStaženo: {actual}"
                )
            target.write_bytes(data)
            return target
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    shutil.rmtree(temp_dir, ignore_errors=True)
    raise RuntimeError(f"Nelze stáhnout ověřený instalační modul.\n{last}")


def _install_runtime() -> None:
    installer = _download_installer()
    temp_dir = installer.parent
    try:
        namespace = runpy.run_path(str(installer))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Instalační modul neobsahuje install_runtime().")
        install(ROOT)
        MARKER.write_text(RUNTIME_LAYOUT, encoding="utf-8")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _write_log(stage: str, exc: BaseException) -> None:
    try:
        STARTUP_LOG.write_text(
            f"TURTO {VERSION} – {stage}\n\n"
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
    except Exception:
        pass


def _show_failure(title: str, message: str) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:
        pass


def main() -> int:
    try:
        if not _runtime_ready():
            _install_runtime()
    except Exception as exc:
        _write_log("obnova runtime", exc)
        _show_failure(
            "TURTO – oprava runtime",
            "Příprava programu se nezdařila. Databáze AKCÍ nebyla měněna.\n\n"
            + str(exc)
            + f"\n\nPodrobnosti: {STARTUP_LOG}",
        )
        return 2

    target = ROOT / "app_runtime.pyw"
    if not target.is_file():
        exc = RuntimeError("Chybí app_runtime.pyw po obnově runtime.")
        _write_log("kontrola runtime", exc)
        _show_failure("TURTO", str(exc))
        return 3

    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 0
    except BaseException as exc:
        _write_log("spuštění programu", exc)
        _show_failure(
            "TURTO – chyba při spuštění",
            "Program se nepodařilo spustit. Byl uložen úplný traceback.\n\n"
            + str(exc)
            + f"\n\nPodrobnosti: {STARTUP_LOG}",
        )
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
