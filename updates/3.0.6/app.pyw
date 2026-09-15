from __future__ import annotations
"""TURTO 3.0.6 bootstrap – explicit design row lifecycle release."""
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

VERSION = "3.0.6"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "366d07e254a3ce71854363c7bd4a2b1f59f0ea2e"
INSTALLER_SHA256 = "26d19b1bd09b72cb8da11821fe5892c56b09373d6ee284ba2a3683e02f2b30a2"
RUNTIME_LAYOUT = "37"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
ROOT_MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_MARKER = PROGRAM / ".turto_runtime_3_0_6.ok"
STARTUP_LOG = ROOT / "Logy" / "startup.log"

CRITICAL_PROGRAM_SHA256 = {'app_runtime.pyw': '7818a7e0ea7c4be9e6b2debe4126279eb8b487016d394c5ba2b06e897a2c3301',
 'branding_301.py': 'e45b20aada0d267963a8aaf54139805629f76e06ead4de83e785e199aa97a17f',
 'iso_bulk_301.py': 'eff6e5b0b6c7cfbed756ca4b2109d895f8cb565b7f39e1935a252627b3f1d192',
 'turto_icon_301.png.b64': 'd98c9ae427a9837b038bc3b9352fd13c3e563a98d4e85ff4529fdc7f7d7ed11d',
 'app_runtime_246.pyw': 'f9b7647b35b6d33d1aad7222eda0dd6573cb6ce882f942a71645f90a8ae3a5b9',
 'bulk_import_engine.py': '6b30a9ee4d1e3533799c079d94313cccdf9a067b40bd069e222da170140150f7',
 'bulk_import.py': 'db5977f431867ca2871abf59e538d68b8059000f880d11cae1b6af9bb6e7ad16',
 'catalog_engine.py': '6ef19641918d507791e3e50ce6abf7394769c8ce0c97be3c63239ca9ed5f5b1c',
 'runtime_paths.py': 'd25f98aeed24d866cf6b9f8ed63833d45e65252cf070f06600a91e61ec0e025a',
 'isokorb_xt_parser_243.py': '680f6853fbb62234a440c2a43e8d1b4f0b03e0df2b4d69c4b84b6b52a2a28352',
 'isokorb_xt_resolver_245.py': 'e0a633936c4d901aa9fa88f89b50fa85e55e6eea80a43b2235a743117144dda7',
 'isokorb_xt_resolver_246.py': '3b7407cfc3affd947fd9995a48278e3e97b194d6073111b44eb192e375941218',
 'shear_cover_302.py': '626e762b50e9d9f2562ccfce95560d5cef8af1b7c7917c08cd6f395a14f5fa9c',
 'substitution_workspace.py': 'dcfe3fa70fb4748c29216c35bce610681fe787331908a219a2f7ba9666082301',
 'substitution_guard.py': '81854ebef393b1ca93e51be9d44019caa3815f37482655d2ba3e96223d570486',
 'zvx_tables_303.py': 'f3ecaedb4a0611c8023189a417592f8d22c42f051128d9ce6b44f242e3a263dd',
 'zvx_annex3_303.json.gz.b64': 'd43c34055048041a5e724a7a3b8d50a8d8601932614d2549ab015d9870aa1eb1',
 'hit_core.py': '8d7666fed0e87a7cd06109669090eba060a614f6b34f282e3e61a8c5be334ab1',
 'isokorb_families_304.py': 'dde6ad19e0d0737600fc54ad11306099bef3d8ac3e7b848ffb346eea4bb8615c',
 'pdf_data_304.py': 'efe16150bac44d99ad0af8b62b82830c0311b01b6d7432f24431826bd9744302',
 'pdf_scope.py': '68401d779f3bc97c9473a50c82c91db0c46faa7fc1d64c0b43e982a5d62a748c',
 'pdf_context_240.py': '1556963fc2261fa83e3943283e1ee0509aa73fd602ba60986038672c74caeba1',
 'hit_pdf.py': '62909e7ecbcc5f56d7dca077cf95421cb1ee10931599433557abece32d629ea8',
 'hit_pdf_127.py': '83540371ce6b7995ec26b929e96a1e2d90463fdfa6ac2f891f2f397bd3a94791',
 'hit_pdf_prev.py': 'b3e7072297cb934acb762bcc99425f2669ad6e0b9e50ff87c50280f9230eaece',
 'substitution_pdf_base.py': '74a4cb629ecd39084374b77467413f6402cd638ae10b8f56c256682898c13883',
 'project_model.py': 'dcbf91bb5c8863e90b2f09e5cd93be248a48249e88c3a36bf6ddb292a281786e',
 'pdf_branding_305.py': '70d86c6238d1cffffab69c251c2f45660d23a8dfcd932821811a94e85808bc21',
 'turto_pdf_logo_305.png.b64': '71a0ae5f632a57e7dfe4204d3f0d494071024e53a25a5850e66481b9875c7d40',
 'design_rows_306.py': '1ceb657e4686ad6eeddf45b0152b30a4be8b6999b84530d880126d88567f43dc'}


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
            "app_base.py", "app_runtime_244.pyw", "app_runtime_243.pyw", "app_runtime_242.pyw",
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
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/updates/3.0.6/runtime_installer.py"
    folder = Path(tempfile.mkdtemp(prefix="turto_304_boot_"))
    target = folder / "runtime_installer.py"
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url + f"?turto={time.time_ns()}_{attempt}",
                headers={
                    "User-Agent": "TURTO-3.0.6-Bootstrap",
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
    raise RuntimeError(f"Nelze stáhnout runtime installer 3.0.6.\n{last}")


def _repair_runtime() -> None:
    installer = _download_installer()
    try:
        install = runpy.run_path(str(installer)).get("install_runtime")
        if not callable(install):
            raise RuntimeError("Runtime installer neobsahuje install_runtime().")
        install(ROOT)
        if not PROGRAM_MARKER.is_file():
            raise RuntimeError("Opravený runtime nemá značku verze 3.0.6.")
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
    assert VERSION == "3.0.6" and RUNTIME_LAYOUT == "35"
    assert len(INSTALLER_COMMIT) == 40 and len(INSTALLER_SHA256) == 64
    assert all(len(value) == 64 for value in CRITICAL_PROGRAM_SHA256.values())
    assert "app_runtime_246.pyw" in CRITICAL_PROGRAM_SHA256
    assert "branding_301.py" in CRITICAL_PROGRAM_SHA256
    assert "turto_icon_301.png.b64" in CRITICAL_PROGRAM_SHA256


if __name__ == "__main__":
    raise SystemExit(main())
