from __future__ import annotations

"""TURTO 2.2.16 bootstrap – incremental Program runtime and one-shot housekeeping."""

import hashlib
import importlib
import importlib.util
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

VERSION = "2.2.16"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "c17ab156e01d84f71ff70f1cdcb4c5f50ee49517"
INSTALLER_SHA256 = "15f86f62aed72967d2552410b0dea1af9eae8f056fa890b1beb77813b7c6a66a"
RUNTIME_LAYOUT = "9"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_REVISION = PROGRAM / ".turto_runtime_2_2_16.ok"
CLEANUP_REVISION = ROOT / ".turto_cleanup_2_2_16.ok"
LOG_DIR = ROOT / "Logy"
BACKUP_DIR = ROOT / "Zaloha"
DOCS_DIR = ROOT / "Dokumentace"
STARTUP_LOG = LOG_DIR / "startup.log"
CLEANUP_LOG = LOG_DIR / "cleanup.log"

REQUIRED_PROGRAM_FILES = (
    "app_runtime.pyw",
    "app_central_prev.pyw",
    "app_base.py",
    "runtime_paths.py",
    "updater.py",
    "cleanup_stage3.py",
    "cleanup_stage4.py",
    "cleanup_stage5.py",
    "platform_workspace.py",
    "hit_workspace.py",
    "hit_pdf.py",
    "shear_movement.py",
    "shear_dowels_current.py",
    "table_polish.py",
    "wt_safety_guard.py",
    "substitution_workspace.py",
    "schoeck_dorn_decoder.py",
    "isokorb_compat.py",
    "substitution_guard.py",
)

os.environ["TURTO_ROOT"] = str(ROOT)
os.environ["TURTO_PROGRAM_DIR"] = str(PROGRAM)


def _runtime_ready() -> bool:
    try:
        return (
            MARKER.is_file()
            and MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and PROGRAM_REVISION.is_file()
            and PROGRAM_REVISION.read_text(encoding="utf-8").strip() == VERSION
            and (ROOT / "updater.py").is_file()
            and all((PROGRAM / name).is_file() for name in REQUIRED_PROGRAM_FILES)
        )
    except Exception:
        return False


def _activate_program_imports() -> None:
    """Make Program imports deterministic even after an incremental runtime update."""
    if not PROGRAM.is_dir():
        raise RuntimeError(f"Chybí runtime složka: {PROGRAM}")

    program_text = str(PROGRAM)
    sys.path[:] = [item for item in sys.path if item != program_text]
    sys.path.insert(0, program_text)
    sys.path_importer_cache.pop(program_text, None)
    importlib.invalidate_caches()

    runtime_paths_file = PROGRAM / "runtime_paths.py"
    if not runtime_paths_file.is_file():
        raise RuntimeError(f"Chybí runtime_paths.py: {runtime_paths_file}")

    loaded = sys.modules.get("runtime_paths")
    try:
        loaded_file = Path(str(getattr(loaded, "__file__", ""))).resolve() if loaded else None
    except Exception:
        loaded_file = None
    if loaded_file == runtime_paths_file.resolve():
        return

    spec = importlib.util.spec_from_file_location("runtime_paths", runtime_paths_file)
    if spec is None or spec.loader is None:
        raise RuntimeError("Nelze připravit modul runtime_paths.")
    module = importlib.util.module_from_spec(spec)
    sys.modules["runtime_paths"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("runtime_paths", None)
        raise


def _download_installer() -> Path:
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/"
        "updates/2.2.16/runtime_installer.py"
    )
    last = None
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_bootstrap_"))
    target = temp_dir / "runtime_installer.py"
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={
                    "User-Agent": "TURTO-2.2.16-Bootstrap",
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
        if not PROGRAM_REVISION.is_file():
            raise RuntimeError("Runtime revize 2.2.16 nebyla vytvořena.")
        MARKER.write_text(RUNTIME_LAYOUT, encoding="utf-8")
    finally:
        shutil.rmtree(installer.parent, ignore_errors=True)


def _cleanup_needed() -> bool:
    try:
        if not CLEANUP_REVISION.is_file() or CLEANUP_REVISION.read_text(encoding="utf-8").strip() != VERSION:
            return True
    except Exception:
        return True
    if (ROOT / "RELEASE_NOTES.txt").exists() or (ROOT / ".update_backup").exists():
        return True
    if any(ROOT.glob(".recovery_backup_*")):
        return True
    if (ROOT / "Archiv" / "Runtime_pred_2.2.13").exists():
        return True
    for name in ("app_runtime_202.pyw", "app_runtime_200.pyw", "app_runtime_127.pyw", "app_runtime_prev.pyw"):
        if (PROGRAM / name).is_file():
            return True
    return False


def _run_cleanup() -> None:
    if not _runtime_ready() or not _cleanup_needed():
        return

    completed = True
    try:
        from cleanup_stage1 import cleanup_stage1
        cleanup_stage1(ROOT, MARKER, LOG_DIR, BACKUP_DIR, DOCS_DIR, CLEANUP_LOG)
    except Exception:
        completed = False
    try:
        from cleanup_stage3 import cleanup_stage3
        cleanup_stage3(ROOT, PROGRAM, REQUIRED_PROGRAM_FILES, LOG_DIR, CLEANUP_LOG)
    except Exception:
        completed = False
    try:
        from cleanup_stage4 import cleanup_stage4
        cleanup_stage4(ROOT, LOG_DIR, CLEANUP_LOG)
    except Exception:
        completed = False
    try:
        from cleanup_stage5 import cleanup_stage5
        cleanup_stage5(ROOT, PROGRAM, LOG_DIR, CLEANUP_LOG)
    except Exception:
        completed = False

    if completed:
        try:
            for old in ROOT.glob(".turto_cleanup_*.ok"):
                if old != CLEANUP_REVISION:
                    old.unlink(missing_ok=True)
            CLEANUP_REVISION.write_text(VERSION, encoding="utf-8")
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
        _activate_program_imports()
    except Exception as exc:
        return _failure("obnova a aktivace runtime Program", exc)

    _run_cleanup()

    try:
        _activate_program_imports()
        runpy.run_path(str(PROGRAM / "app_runtime.pyw"), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 0
    except BaseException as exc:
        return _failure("spuštění programu", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
