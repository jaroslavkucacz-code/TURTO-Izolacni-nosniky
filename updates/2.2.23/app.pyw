from __future__ import annotations

"""TURTO 2.2.23 bootstrap – shear-dowel startup hotfix with safe release-note ownership."""

import hashlib
import importlib
import importlib.util
import os
import re
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

VERSION = "2.2.23"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "f03e8f4284aeb575f4f47597b3f1e051c0e885a1"
INSTALLER_SHA256 = "f46925d999d12db432bf44206ec16fc5eff79e03b567b0c75ae912efd258679b"
RUNTIME_LAYOUT = "16"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_REVISION = PROGRAM / ".turto_runtime_2_2_23.ok"
CLEANUP_REVISION = ROOT / ".turto_cleanup_2_2_23.ok"
LOG_DIR = ROOT / "Logy"
STARTUP_LOG = LOG_DIR / "startup.log"
CLEANUP_LOG = LOG_DIR / "cleanup.log"

REQUIRED_PROGRAM_FILES = (
    "app_runtime.pyw", "app_runtime_221.pyw", "app_base.py", "runtime_paths.py", "updater.py",
    "cleanup_stage8.py", "platform_workspace.py", "hit_workspace.py", "hit_workspace_base.py",
    "hit_row_extension.py", "hit_virtual_scroll.py", "hit_design_ui.py", "hit_export_ui.py",
    "hit_aux_ui.py", "hit_wt_ui.py", "unified_schedule.py", "supplier_export.py", "hit_pdf.py",
    "shear_movement.py", "shear_dowels_current.py", "shear_dowels_current_221.py",
    "shear_dowels_schedule.py", "shear_dowels_schedule_guard.py", "shear_dowels_ui_214.py",
    "shear_dowels_schedule_215.py", "shear_dowels_ui_215.py", "historical_schoeck_dorn.py",
    "table_polish.py", "wt_safety_guard.py", "substitution_workspace.py",
    "schoeck_dorn_decoder.py", "isokorb_compat.py", "substitution_guard.py",
    "project_ui.py", "project_ui_prev.py", "project_ui_base.py", "action_workspace.py",
    "action_browser.py", "action_browser_123.py", "action_payload.py", "action_payload_200.py",
    "action_payload_127.py", "action_payload_125.py", "action_payload_prev.py", "action_store.py",
    "action_store_127.py", "action_store_125.py", "action_store_prev.py", "platform_registry.py",
    "platform_registry_200.py", "platform_state.py", "platform_state_200.py", "bulk_import.py",
    "bulk_import_engine.py", "hit_decoder_catalog.py", "hit_decoder_catalog_prev.py",
)

os.environ["TURTO_ROOT"] = str(ROOT)
os.environ["TURTO_PROGRAM_DIR"] = str(PROGRAM)
_VERSION_LINE = re.compile(r'^VERSION\s*=\s*["\'](\d+\.\d+\.\d+)["\']\s*$', re.MULTILINE)
_NOTES_LINE = re.compile(r'^TURTO\s+(\d+\.\d+\.\d+)\s*$')


def _runtime_ready() -> bool:
    try:
        return (
            MARKER.is_file() and MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and PROGRAM_REVISION.is_file() and PROGRAM_REVISION.read_text(encoding="utf-8").strip() == VERSION
            and (ROOT / "updater.py").is_file()
            and all((PROGRAM / name).is_file() for name in REQUIRED_PROGRAM_FILES)
        )
    except Exception:
        return False


def _activate_program_imports() -> None:
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
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/updates/2.2.23/runtime_installer.py"
    last = None
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_bootstrap_"))
    target = temp_dir / "runtime_installer.py"
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={"User-Agent": "TURTO-2.2.23-Bootstrap", "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != INSTALLER_SHA256:
                raise RuntimeError(f"Kontrolní součet instalačního modulu nesouhlasí: {actual}")
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
            raise RuntimeError("Runtime revize 2.2.23 nebyla vytvořena.")
        MARKER.write_text(RUNTIME_LAYOUT, encoding="utf-8")
    finally:
        shutil.rmtree(installer.parent, ignore_errors=True)


def _notes_version(path: Path) -> str | None:
    try:
        first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
    except Exception:
        return None
    match = _NOTES_LINE.fullmatch(first)
    return match.group(1) if match else None


def _disk_bootstrap_version() -> str | None:
    try:
        match = _VERSION_LINE.search((ROOT / "app.pyw").read_text(encoding="utf-8", errors="replace"))
        return match.group(1) if match else None
    except Exception:
        return None


def _unique_target(folder: Path, version: str) -> Path:
    target = folder / f"TURTO_{version}.txt"
    if not target.exists():
        return target
    stamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = folder / f"TURTO_{version}_{stamp}.txt"
    index = 2
    while candidate.exists():
        candidate = folder / f"TURTO_{version}_{stamp}_{index}.txt"
        index += 1
    return candidate


def _repair_misfiled_release_notes() -> None:
    folder = ROOT / "Dokumentace" / "Interni" / "Vydani"
    if not folder.is_dir():
        return
    for path in sorted(folder.glob("TURTO_*.txt")):
        if not path.is_file():
            continue
        actual = _notes_version(path)
        if not actual or path.name.startswith(f"TURTO_{actual}"):
            continue
        target = folder / f"TURTO_{actual}.txt"
        try:
            if target.exists() and target.read_bytes() == path.read_bytes():
                path.unlink()
            elif target.exists():
                shutil.move(str(path), str(_unique_target(folder, actual)))
            else:
                shutil.move(str(path), str(target))
        except Exception:
            pass


def _archive_current_release_notes() -> None:
    source = ROOT / "RELEASE_NOTES.txt"
    if not source.is_file() or _notes_version(source) != VERSION:
        return
    folder = ROOT / "Dokumentace" / "Interni" / "Vydani"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"TURTO_{VERSION}.txt"
    if target.exists() and target.read_bytes() == source.read_bytes():
        source.unlink()
    elif target.exists():
        shutil.move(str(source), str(_unique_target(folder, VERSION)))
    else:
        shutil.move(str(source), str(target))


def _post_run_cleanup() -> None:
    if _disk_bootstrap_version() != VERSION:
        return
    try:
        _repair_misfiled_release_notes()
        _archive_current_release_notes()
        for old in ROOT.glob(".turto_cleanup_*.ok"):
            if old != CLEANUP_REVISION:
                old.unlink(missing_ok=True)
        CLEANUP_REVISION.write_text(VERSION, encoding="utf-8")
    except Exception:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with CLEANUP_LOG.open("a", encoding="utf-8") as handle:
                handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] TURTO {VERSION} – archivace poznámek nebyla dokončena\n")
                handle.write(traceback.format_exc() + "\n")
        except Exception:
            pass


def _failure(stage: str, exc: BaseException) -> int:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        STARTUP_LOG.write_text(
            f"TURTO {VERSION} – {stage}\n\n{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8"
        )
    except Exception:
        pass
    try:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("TURTO – chyba při spuštění", f"{exc}\n\nPodrobnosti: {STARTUP_LOG}", parent=root)
        root.destroy()
    except Exception:
        pass
    return 2


def main() -> int:
    try:
        if not _runtime_ready():
            _install_runtime()
        _activate_program_imports()
        _repair_misfiled_release_notes()
    except Exception as exc:
        return _failure("obnova a aktivace runtime Program", exc)

    exit_code = 0
    try:
        _activate_program_imports()
        runpy.run_path(str(PROGRAM / "app_runtime.pyw"), run_name="__main__")
    except SystemExit as exc:
        exit_code = int(exc.code) if isinstance(exc.code, int) else 0
    except BaseException as exc:
        return _failure("spuštění programu", exc)

    if exit_code == 0:
        _post_run_cleanup()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
