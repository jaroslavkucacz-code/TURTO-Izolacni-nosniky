from __future__ import annotations
"""TURTO 2.2.41 – CRET 05/2026 source VRd propagation correction."""
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

VERSION = "2.2.41"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "d36b6690d113a4f21f234ee7a178ba5ca1196b8c"
INSTALLER_SHA256 = "5ef470ae5038506916f7105a67c7fc78bf2e8fd57737f25753e58c7fa4200016"
RUNTIME_LAYOUT = "25"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
ROOT_MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_MARKER = PROGRAM / ".turto_runtime_2_2_41.ok"
STARTUP_LOG = ROOT / "Logy" / "startup.log"

CRITICAL_PROGRAM_SHA256 = {
    "app_runtime.pyw": "470bcf416f99f6df4a509510476e0e832f2afc5d5d9ac26ae6a0d4495f0c9314",
    "app_runtime_240.pyw": "d377f8d80711f734344be4744370453ac337d65ba774ac6eb5aeefd47ae66b05",
    "shear_cret_sync_241.py": "075311ff89efd1e7e88207bf3bc98abea3e84e434a7efcba4a55be64332615c2",
    "app_runtime_239.pyw": "6ef5e7799268b56c390156c9bc758481a9528e222442a19a61adb7a84efde5a7",
    "pdf_context_240.py": "1556963fc2261fa83e3943283e1ee0509aa73fd602ba60986038672c74caeba1",
    "shear_substitution_237.py": "300a670ecda75411b05ebfc5ce7adb50c6ace07057824f53ee45d87963175346",
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
        required = ("runtime_paths.py", "platform_workspace.py", "hit_pdf.py", "pdf_scope.py")
        return (
            ROOT_MARKER.is_file() and ROOT_MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and PROGRAM_MARKER.is_file() and PROGRAM_MARKER.read_text(encoding="utf-8").strip() == VERSION
            and all(_matches(PROGRAM / name, sha) for name, sha in CRITICAL_PROGRAM_SHA256.items())
            and all((PROGRAM / name).is_file() for name in required)
            and (PROGRAM / "assets" / "turto_logo_vector.json").is_file()
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
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/updates/2.2.41/runtime_installer.py"
    folder = Path(tempfile.mkdtemp(prefix="turto_2241_boot_"))
    target = folder / "runtime_installer.py"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={time.time_ns()}_{attempt}",
                headers={"User-Agent":"TURTO-2.2.41-Bootstrap","Cache-Control":"no-cache, no-store","Pragma":"no-cache"},
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
    shutil.rmtree(folder, ignore_errors=True)
    raise RuntimeError(f"Nelze stáhnout runtime installer 2.2.41.\n{last}")

def _repair_runtime() -> None:
    installer = _download_installer()
    try:
        install = runpy.run_path(str(installer)).get("install_runtime")
        if not callable(install):
            raise RuntimeError("Runtime installer neobsahuje install_runtime().")
        install(ROOT)
        if not PROGRAM_MARKER.is_file():
            raise RuntimeError("Opravený runtime nemá značku verze 2.2.41.")
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
        messagebox.showerror("TURTO – chyba při spuštění", f"{exc}\n\nPodrobnosti: {STARTUP_LOG}", parent=root)
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
    assert VERSION == "2.2.41" and RUNTIME_LAYOUT == "25"
    assert len(INSTALLER_SHA256) == 64 and all(len(v) == 64 for v in CRITICAL_PROGRAM_SHA256.values())
    assert "shear_cret_sync_241.py" in CRITICAL_PROGRAM_SHA256
    assert "app_runtime_240.pyw" in CRITICAL_PROGRAM_SHA256

if __name__ == "__main__":
    raise SystemExit(main())
