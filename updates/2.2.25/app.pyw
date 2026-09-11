from __future__ import annotations

"""TURTO 2.2.25 – restore manual shear-dowel design controls."""

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

VERSION = "2.2.25"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "9b539b2b9f50ab3cf8ef6f6e20504d57cd3ce53d"
INSTALLER_SHA256 = "0282e173037ff55226ece2bd34392332267126dce9cabcc797738dbb0d80a75b"
RUNTIME_LAYOUT = "18"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
ROOT_MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_MARKER = PROGRAM / ".turto_runtime_2_2_25.ok"
STARTUP_LOG = ROOT / "Logy" / "startup.log"

CRITICAL_PROGRAM_SHA256 = {
    "app_runtime.pyw": "77bf4f4926bbabcc7c61a6ae57cae9be0e353ae73d38499fef3c67c38f89a8a9",
    "shear_dowels_current.py": "3bb7faeb1abd13b3161e8b4c16804c20fd7f3ef90857a89a30f146d05857764f",
    "shear_dowels_current_224.py": "42025cb2bcf5e5bdb8d6ccd6f098bffb9ae49a10632e8da3d660c2d54200b35f",
    "shear_dowels_current_221.py": "de150f895f7be451a6f0dc46d05918ef75254604c3eb2557d4211ac7e4a01318",
    "shear_ui_227.py": "c73e459a7ad8340d54d0fdc6990c5be936bcf55d3896fb4bd719d7c7180bd94d",
    "shear_catalogs_227.py": "b1e59c850451ae662e2bfc065db04ac8038f1dc3d2137776e9fcb314324ab44f",
    "shear_dowels_ui_215.py": "e510f974ac9f98320e563424da924a00c5dd9868fa5c836338ea2fac136ae265",
    "shear_dowels_ui_214.py": "ece048d76888dbdb398ea9b6c67ef4bcb2765a0904987ae358cc59765a069813",
}

os.environ["TURTO_ROOT"] = str(ROOT)
os.environ["TURTO_PROGRAM_DIR"] = str(PROGRAM)


def _critical_runtime_valid() -> bool:
    try:
        for name, expected in CRITICAL_PROGRAM_SHA256.items():
            path = PROGRAM / name
            if not path.is_file():
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest().lower() != expected:
                return False
        return True
    except Exception:
        return False


def _runtime_ready() -> bool:
    try:
        return (
            ROOT_MARKER.is_file()
            and ROOT_MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and PROGRAM_MARKER.is_file()
            and PROGRAM_MARKER.read_text(encoding="utf-8").strip() == VERSION
            and (PROGRAM / "runtime_paths.py").is_file()
            and _critical_runtime_valid()
        )
    except Exception:
        return False


def _activate_program() -> None:
    if not PROGRAM.is_dir():
        raise RuntimeError(f"Chybí runtime složka: {PROGRAM}")
    program_text = str(PROGRAM)
    sys.path[:] = [item for item in sys.path if item != program_text]
    sys.path.insert(0, program_text)
    sys.path_importer_cache.pop(program_text, None)
    importlib.invalidate_caches()

    runtime_paths = PROGRAM / "runtime_paths.py"
    if not runtime_paths.is_file():
        raise RuntimeError(f"Chybí runtime_paths.py: {runtime_paths}")

    loaded = sys.modules.get("runtime_paths")
    try:
        loaded_path = Path(str(getattr(loaded, "__file__", ""))).resolve() if loaded else None
    except Exception:
        loaded_path = None
    if loaded_path == runtime_paths.resolve():
        return

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
        "updates/2.2.25/runtime_installer.py"
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_2225_boot_"))
    target = temp_dir / "runtime_installer.py"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={time.time_ns()}_{attempt}",
                headers={
                    "User-Agent": "TURTO-2.2.25-Bootstrap",
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
    raise RuntimeError(f"Nelze stáhnout runtime installer 2.2.25.\n{last}")


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
        if target.exists():
            if target.read_bytes() == source.read_bytes():
                source.unlink()
            else:
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
    assert VERSION == "2.2.25"
    assert RUNTIME_LAYOUT == "18"
    assert all(len(value) == 64 for value in CRITICAL_PROGRAM_SHA256.values())
    assert "shear_dowels_current_224.py" in CRITICAL_PROGRAM_SHA256


if __name__ == "__main__":
    raise SystemExit(main())
