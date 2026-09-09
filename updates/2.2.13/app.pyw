from __future__ import annotations

"""TURTO 2.2.13 verified bootstrap for the clean Program\ runtime layout."""

import hashlib
import os
import runpy
import shutil
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

VERSION = "2.2.13"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "0a8fa46839d4f8b55fa6c3dc18ca9eee9fed3d81"
INSTALLER_SHA256 = "6a43fbcc6afe8dc8147ec77e3c28987618b97af6d3c753f3dfb54c30e23babc3"
RUNTIME_LAYOUT = "6"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
MARKER = ROOT / ".turto_runtime_current.ok"
LOG_DIR = ROOT / "Logy"
BACKUP_DIR = ROOT / "Zaloha"
DOCS_DIR = ROOT / "Dokumentace"
STARTUP_LOG = LOG_DIR / "startup.log"
CLEANUP_LOG = LOG_DIR / "cleanup.log"

REQUIRED_PROGRAM_FILES = (
    "app_runtime.pyw",
    "app_runtime_202.pyw",
    "app_runtime_200.pyw",
    "app_runtime_127.pyw",
    "app_base.py",
    "platform_workspace.py",
    "action_store.py",
    "catalog_browser.py",
    "catalog_browser_2210.py",
    "runtime_paths.py",
    "updater.py",
    "cleanup_stage3.py",
    "hit_workspace.py",
    "hit_pdf.py",
    "shear_movement.py",
    "shear_dowels_current.py",
)

os.environ["TURTO_ROOT"] = str(ROOT)
os.environ["TURTO_PROGRAM_DIR"] = str(PROGRAM)
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


def _runtime_ready() -> bool:
    try:
        return (
            MARKER.is_file()
            and MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and (ROOT / "updater.py").is_file()
            and all((PROGRAM / name).is_file() for name in REQUIRED_PROGRAM_FILES)
        )
    except Exception:
        return False


def _download_installer() -> Path:
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/"
        "updates/2.2.13/runtime_installer.py"
    )
    last = None
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_bootstrap_"))
    target = temp_dir / "runtime_installer.py"
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={
                    "User-Agent": "TURTO-2.2.13-Bootstrap",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != INSTALLER_SHA256:
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
    try:
        namespace = runpy.run_path(str(installer))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Instalační modul neobsahuje install_runtime().")
        install(ROOT)
        if not all((PROGRAM / name).is_file() for name in REQUIRED_PROGRAM_FILES):
            raise RuntimeError("Nová složka Program nebyla vytvořena kompletně.")
        MARKER.write_text(RUNTIME_LAYOUT, encoding="utf-8")
    finally:
        shutil.rmtree(installer.parent, ignore_errors=True)


def _run_cleanup() -> None:
    """Run cleanup only after Program is complete; cleanup must never block startup."""
    if not _runtime_ready():
        return
    try:
        from cleanup_stage1 import cleanup_stage1
        cleanup_stage1(ROOT, MARKER, LOG_DIR, BACKUP_DIR, DOCS_DIR, CLEANUP_LOG)
    except Exception:
        pass
    try:
        from cleanup_stage3 import cleanup_stage3
        cleanup_stage3(ROOT, PROGRAM, REQUIRED_PROGRAM_FILES, LOG_DIR, CLEANUP_LOG)
    except Exception:
        pass


def _failure(stage: str, exc: BaseException) -> int:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        STARTUP_LOG.write_text(
            f"TURTO {VERSION} – {stage}\n\n{type(exc).__name__}: {exc}\n\n"
            f"{traceback.format_exc()}",
            encoding="utf-8",
        )
    except Exception:
        pass
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "TURTO – chyba při spuštění",
            f"{exc}\n\nPodrobnosti: {STARTUP_LOG}",
            parent=root,
        )
        root.destroy()
    except Exception:
        pass
    return 2


def main() -> int:
    try:
        if not _runtime_ready():
            _install_runtime()
    except Exception as exc:
        return _failure("obnova runtime do složky Program", exc)

    _run_cleanup()

    try:
        runpy.run_path(str(PROGRAM / "app_runtime.pyw"), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 0
    except BaseException as exc:
        return _failure("spuštění programu", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
