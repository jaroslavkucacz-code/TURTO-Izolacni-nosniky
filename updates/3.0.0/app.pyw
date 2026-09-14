from __future__ import annotations
"""TURTO 3.0.0 bootstrap – branded major release."""
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

VERSION = "3.0.0"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "930d34506060505b5d692adedf4d0299ccb18f85"
INSTALLER_SHA256 = "2b5235f1d1ee163f68c35014cf7f20e73ad7e354ca6e500cd3f72efd9fc84c1a"
RUNTIME_LAYOUT = "31"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
ROOT_MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_MARKER = PROGRAM / ".turto_runtime_3_0_0.ok"
STARTUP_LOG = ROOT / "Logy" / "startup.log"

CRITICAL_PROGRAM_SHA256 = {
    "app_runtime.pyw": "237408e1c49ee2124bf49215f7c428ca660ad93927046559e55186fd619aea45",
    "app_runtime_246.pyw": "f9b7647b35b6d33d1aad7222eda0dd6573cb6ce882f942a71645f90a8ae3a5b9",
    "branding_300.py": "4e2873a4f8268f2f7c3baf953eb84fd701add04a5dde89d4255fbb83240b9228",
    "turto_logo_300.png": "9466ad8706d3a7f0473b025a9eb2ddd82fb0ae0b2ac06a0665780e28af16820f",
    "isokorb_xt_resolver_245.py": "e0a633936c4d901aa9fa88f89b50fa85e55e6eea80a43b2235a743117144dda7",
    "isokorb_xt_resolver_246.py": "3b7407cfc3affd947fd9995a48278e3e97b194d6073111b44eb192e375941218",
}


def _matches(path: Path, expected: str) -> bool:
    try:
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest().lower() == expected
    except Exception:
        return False


def _runtime_ready() -> bool:
    try:
        required = (
            "runtime_paths.py",
            "platform_workspace.py",
            "bulk_import.py",
            "bulk_import_engine.py",
            "isokorb_xt_parser_243.py",
        )
        return (
            ROOT_MARKER.is_file()
            and ROOT_MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and PROGRAM_MARKER.is_file()
            and PROGRAM_MARKER.read_text(encoding="utf-8").strip() == VERSION
            and all(_matches(PROGRAM / name, sha) for name, sha in CRITICAL_PROGRAM_SHA256.items())
            and all((PROGRAM / name).is_file() for name in required)
        )
    except Exception:
        return False


def _activate_program() -> None:
    p = str(PROGRAM)
    sys.path[:] = [item for item in sys.path if item != p]
    sys.path.insert(0, p)
    sys.path_importer_cache.pop(p, None)
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
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/updates/3.0.0/runtime_installer.py"
    folder = Path(tempfile.mkdtemp(prefix="turto_300_boot_"))
    target = folder / "runtime_installer.py"
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url + f"?turto={time.time_ns()}_{attempt}",
                headers={
                    "User-Agent": "TURTO-3.0.0-Bootstrap",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != INSTALLER_SHA256:
                raise RuntimeError(
                    f"Kontrolní součet installeru nesouhlasí. Očekáváno {INSTALLER_SHA256}, staženo {actual}."
                )
            target.write_bytes(data)
            return target
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    shutil.rmtree(folder, ignore_errors=True)
    raise RuntimeError(f"Nelze stáhnout runtime installer 3.0.0.\n{last}")


def _repair_runtime() -> None:
    installer = _download_installer()
    try:
        install = runpy.run_path(str(installer)).get("install_runtime")
        if not callable(install):
            raise RuntimeError("Runtime installer neobsahuje install_runtime().")
        install(ROOT)
        if not PROGRAM_MARKER.is_file():
            raise RuntimeError("Opravený runtime nemá značku verze 3.0.0.")
        ROOT_MARKER.write_text(RUNTIME_LAYOUT, encoding="utf-8")
        if not _runtime_ready():
            raise RuntimeError("Opravený runtime neprošel závěrečnou kontrolou.")
    finally:
        shutil.rmtree(installer.parent, ignore_errors=True)


def _archive_release_notes() -> None:
    source = ROOT / "RELEASE_NOTES.txt"
    if not source.is_file():
        return
    try:
        if source.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip() != f"TURTO {VERSION}":
            return
        folder = ROOT / "Dokumentace" / "Interni" / "Vydani"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"TURTO_{VERSION}.txt"
        if target.exists() and target.read_bytes() == source.read_bytes():
            source.unlink()
        elif target.exists():
            shutil.move(str(source), str(folder / f"TURTO_{VERSION}_{time.strftime('%Y%m%d_%H%M%S')}.txt"))
        else:
            shutil.move(str(source), str(target))
    except Exception:
        pass


def _failure(stage: str, exc: BaseException) -> int:
    try:
        STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
        STARTUP_LOG.write_text(
            f"TURTO {VERSION} – {stage}\n\n{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
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
    assert VERSION == "3.0.0" and RUNTIME_LAYOUT == "31"
    assert len(INSTALLER_COMMIT) == 40 and len(INSTALLER_SHA256) == 64
    assert all(len(value) == 64 for value in CRITICAL_PROGRAM_SHA256.values())
    assert "app_runtime_246.pyw" in CRITICAL_PROGRAM_SHA256
    assert "branding_300.py" in CRITICAL_PROGRAM_SHA256
    assert "turto_logo_300.png" in CRITICAL_PROGRAM_SHA256


if __name__ == "__main__":
    raise SystemExit(main())
