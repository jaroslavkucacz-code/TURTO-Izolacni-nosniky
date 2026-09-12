from __future__ import annotations

"""TURTO 2.2.33 – restore all verified Leviat HIT design groups in shared Návrh."""

import hashlib
import importlib
import importlib.util
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

VERSION = "2.2.33"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "f045c3f77b8420cd35e966184ce5404e4d2e30d7"
INSTALLER_SHA256 = "db554cec25ec7b727e44e553044731d45b0d4fdd87779c083cdf70d5fcc15edc"
RUNTIME_LAYOUT = "21"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
ROOT_MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_MARKER = PROGRAM / ".turto_runtime_2_2_33.ok"
STARTUP_LOG = ROOT / "Logy" / "startup.log"

CRITICAL_PROGRAM_SHA256 = {
    "app_runtime.pyw": "380e46fe925eca48a44c69e533074ecc434771efbc7eeb16dc53e58bac138291",
    "app_runtime_232.pyw": "56540f96213666734a527ddc208ac1ff6150cb78a114be05646ffdf8d6bcdb3f",
    "design_groups_restore.py": "8aa2b4507f96a8b34b2e79d266e9779732d1a38f29050f64b49a7ed75d00aea8",
    "schedule_restore.py": "986b0190134ef6ad54c92cb7aaf2f883a99292997e03bc498f55732404444e2f",
}


def _critical_runtime_valid() -> bool:
    try:
        return all(
            (PROGRAM / name).is_file()
            and hashlib.sha256((PROGRAM / name).read_bytes()).hexdigest().lower() == expected
            for name, expected in CRITICAL_PROGRAM_SHA256.items()
        )
    except Exception:
        return False


def _runtime_ready() -> bool:
    try:
        required = (
            "runtime_paths.py",
            "unified_schedule.py",
            "thermal_design_ui.py",
            "hit_workspace.py",
            "hit_aux_ui.py",
            "hit_wt_ui.py",
        )
        return (
            ROOT_MARKER.is_file()
            and ROOT_MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and PROGRAM_MARKER.is_file()
            and PROGRAM_MARKER.read_text(encoding="utf-8").strip() == VERSION
            and all((PROGRAM / name).is_file() for name in required)
            and _critical_runtime_valid()
        )
    except Exception:
        return False


def _activate_program() -> None:
    program_text = str(PROGRAM)
    sys.path[:] = [item for item in sys.path if item != program_text]
    sys.path.insert(0, program_text)
    sys.path_importer_cache.pop(program_text, None)
    importlib.invalidate_caches()

    runtime_paths = PROGRAM / "runtime_paths.py"
    if not runtime_paths.is_file():
        raise RuntimeError(f"Chybí runtime_paths.py: {runtime_paths}")
    spec = importlib.util.spec_from_file_location("runtime_paths", runtime_paths)
    if spec is None or spec.loader is None:
        raise RuntimeError("Nelze připravit runtime_paths.py.")
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
        "updates/2.2.33/runtime_installer.py"
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_2233_boot_"))
    target = temp_dir / "runtime_installer.py"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={time.time_ns()}_{attempt}",
                headers={
                    "User-Agent": "TURTO-2.2.33-Bootstrap",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != INSTALLER_SHA256:
                raise RuntimeError(
                    f"Kontrolní součet installeru nesouhlasí. "
                    f"Očekáváno {INSTALLER_SHA256}, staženo {actual}."
                )
            target.write_bytes(data)
            return target
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    shutil.rmtree(temp_dir, ignore_errors=True)
    raise RuntimeError(f"Nelze stáhnout runtime installer 2.2.33.\n{last}")


def _repair_runtime() -> None:
    installer = _download_installer()
    try:
        namespace = runpy.run_path(str(installer))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Runtime installer neobsahuje install_runtime().")
        install(ROOT)
        if not PROGRAM_MARKER.is_file() or not _critical_runtime_valid():
            raise RuntimeError("Opravený runtime neprošel závěrečnou kontrolou.")
        ROOT_MARKER.write_text(RUNTIME_LAYOUT, encoding="utf-8")
    finally:
        shutil.rmtree(installer.parent, ignore_errors=True)


def _archive_release_notes() -> None:
    source = ROOT / "RELEASE_NOTES.txt"
    if not source.is_file():
        return
    try:
        first = source.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
        if first != f"TURTO {VERSION}":
            return
        folder = ROOT / "Dokumentace" / "Interni" / "Vydani"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"TURTO_{VERSION}.txt"
        if target.exists() and target.read_bytes() == source.read_bytes():
            source.unlink()
        elif target.exists():
            stamp = time.strftime("%Y%m%d_%H%M%S")
            shutil.move(str(source), str(folder / f"TURTO_{VERSION}_{stamp}.txt"))
        else:
            shutil.move(str(source), str(target))
    except Exception:
        pass


def _failure(stage: str, exc: BaseException) -> int:
    try:
        STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
        STARTUP_LOG.write_text(
            f"TURTO {VERSION} – {stage}\n\n"
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
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
            _repair_runtime()
        _activate_program()
    except Exception as exc:
        return _failure("obnova runtime", exc)

    try:
        runpy.run_path(str(PROGRAM / "app_runtime.pyw"), run_name="__main__")
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 0
        if code == 0:
            _archive_release_notes()
        return code
    except BaseException as exc:
        return _failure("spuštění programu", exc)

    _archive_release_notes()
    return 0


def selftest() -> None:
    assert VERSION == "2.2.33"
    assert RUNTIME_LAYOUT == "21"
    assert all(len(value) == 64 for value in CRITICAL_PROGRAM_SHA256.values())
    assert len(INSTALLER_SHA256) == 64
    assert "design_groups_restore.py" in CRITICAL_PROGRAM_SHA256
    assert "schedule_restore.py" in CRITICAL_PROGRAM_SHA256


if __name__ == "__main__":
    raise SystemExit(main())
