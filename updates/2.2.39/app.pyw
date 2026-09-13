from __future__ import annotations
"""TURTO 2.2.39 – Leviat / Aschwanden CRET Series 100 (05/2026)."""

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

VERSION = "2.2.39"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "7bf86fd34a4dab31a56672863731a2367a446af0"
INSTALLER_SHA256 = "f857f1b1f860f1d655d57174741d38de747826691965acb9410b2b410559dae5"
RUNTIME_LAYOUT = "23"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
ROOT_MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_MARKER = PROGRAM / ".turto_runtime_2_2_39.ok"
STARTUP_LOG = ROOT / "Logy" / "startup.log"

CRITICAL_PROGRAM_SHA256 = {
    "app_runtime.pyw": "6ef5e7799268b56c390156c9bc758481a9528e222442a19a61adb7a84efde5a7",
    "app_runtime_238.pyw": "99cd795fbd49ba790737e4ffe03c4e3cf2ae9f23caf12a71a879e7cbb8ee93ba",
    "app_runtime_237.pyw": "590f3d4e5595688a85dd3143b2fce05b1bbfb687833f919cff516625b325bf6f",
    "app_runtime_236.pyw": "75e9b1899532d82a7c0562dedd7dfae0110ef616482195fd2f58d3a304fcb8d4",
    "app_runtime_235.pyw": "8e4c7e8b5ec4a56379e8fa7d1b44ac8a9c6bb8a4a94ac322c29ee1079d7b4290",
    "app_runtime_234.pyw": "5576cdae794c9c8fd4f566573acb55bb5e687b5fbcc5c3f1fb521afc0cfcc883",
    "pdf_logo_guard_238.py": "f2f7359197f025e51b69c513e9e307df2e01537eda69d3af30c13b863ddc3f67",
    "shear_substitution_237.py": "300a670ecda75411b05ebfc5ce7adb50c6ace07057824f53ee45d87963175346",
    "shear_workflow_236.py": "c96f573dafd7893f36bf809d064135ecf56573157895f3051bc97d56a93df7f3",
    "shear_schedule_io_236.py": "5c21aec2b230c8e73d37cf0e3d2f2a27cb0efe42619bbcc618a56ae6051576f4",
    "hsd_windows_ocr.ps1": "b76a281f1b8eef02c7bbfc6aa4d4cc3c3f41b5abef814d49f526b9dff79babf3",
    "halfen_hsd_2026.py": "805f811bee2a8302c2c8ced979ecd2c26a3c92fbe6fd1024940a28dd98e617be",
    "shear_dowels_hsd_234.py": "299705a9091784ad88be8d38b6fdbdc69c1bc29d4baf813fb69030e1c11aadf7",
    "design_groups_restore.py": "8aa2b4507f96a8b34b2e79d266e9779732d1a38f29050f64b49a7ed75d00aea8",
    "cret_series_100_239.py": "70f4d4064613188a2dc68b985effae53da671da321b9a41bbfeaae3bc26b5ceb",
    "cret_series_100_239_data1.py": "23a22c1b6a09181109120639a5d0fb10ada8faa5c13c4021eaa9e91e35879e9e",
    "cret_series_100_239_data2.py": "1bad7aed0efe72b386df16599dff612f964c648e75215f60ff2da86a7029e5b4",
    "cret_series_100_239_data3.py": "e12083a49d9c16e970eceb4d570c8af08eed1359c197cca37370fd5dbe0f0c9e",
    "cret_series_100_239_data4.py": "d1f19448871355961c6784dbd3f34ce5ae62678236660632ba41bfa0f5708136",
    "shear_cret_239.py": "fc70804efe1dba44498f26e483d62fd5711d55b761a76d93312b685c0b0b1099",
}


def _matches(path: Path, expected: str) -> bool:
    try:
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest().lower() == expected
    except Exception:
        return False


def _runtime_ready() -> bool:
    try:
        return (
            ROOT_MARKER.is_file()
            and ROOT_MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and PROGRAM_MARKER.is_file()
            and PROGRAM_MARKER.read_text(encoding="utf-8").strip() == VERSION
            and all(_matches(PROGRAM / name, sha) for name, sha in CRITICAL_PROGRAM_SHA256.items())
            and (PROGRAM / "runtime_paths.py").is_file()
            and (PROGRAM / "platform_workspace.py").is_file()
            and (PROGRAM / "assets" / "turto_logo_vector.json").is_file()
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
        "updates/2.2.39/runtime_installer.py"
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_2239_boot_"))
    target = temp_dir / "runtime_installer.py"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={time.time_ns()}_{attempt}",
                headers={
                    "User-Agent": "TURTO-2.2.39-Bootstrap",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
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
    shutil.rmtree(temp_dir, ignore_errors=True)
    raise RuntimeError(f"Nelze stáhnout runtime installer 2.2.39.\n{last}")


def _repair_runtime() -> None:
    installer = _download_installer()
    try:
        namespace = runpy.run_path(str(installer))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Runtime installer neobsahuje install_runtime().")
        install(ROOT)
        if not PROGRAM_MARKER.is_file():
            raise RuntimeError("Opravený runtime nemá značku verze 2.2.39.")
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
    assert VERSION == "2.2.39"
    assert RUNTIME_LAYOUT == "23"
    assert len(INSTALLER_SHA256) == 64
    assert all(len(value) == 64 for value in CRITICAL_PROGRAM_SHA256.values())
    assert "cret_series_100_239.py" in CRITICAL_PROGRAM_SHA256
    assert "shear_cret_239.py" in CRITICAL_PROGRAM_SHA256


if __name__ == "__main__":
    raise SystemExit(main())
