from __future__ import annotations
"""TURTO 3.0.22 bootstrap – visible startup and unified Schöck decoder."""
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

VERSION = "3.0.22"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = '7a58a08e78e064133b5e77b0b52480815a3b976f'
INSTALLER_SHA256 = '5bfe888a138ce550521388d5bfec17d8a54dd50a448c48eb29ccc8e14c4b2344'
RUNTIME_LAYOUT = "53"

ROOT = Path(__file__).resolve().parent
PROGRAM = ROOT / "Program"
ROOT_MARKER = ROOT / ".turto_runtime_current.ok"
PROGRAM_MARKER = PROGRAM / ".turto_runtime_3_0_22.ok"
STARTUP_LOG = ROOT / "Logy" / "startup.log"

CRITICAL_PROGRAM_SHA256 = {'app_runtime.pyw': '481d29d868f49fc9d69fe851a93caa8da78a985a7c7c2cefd400d76839990a6e',
 'branding_301.py': 'c1bccb41ea87278a4598b4de80370da3e8f207d577e79be2d29a6630094a92f3',
 'iso_bulk_301.py': 'eff6e5b0b6c7cfbed756ca4b2109d895f8cb565b7f39e1935a252627b3f1d192',
 'turto_icon_301.png.b64': 'd98c9ae427a9837b038bc3b9352fd13c3e563a98d4e85ff4529fdc7f7d7ed11d',
 'app_runtime_246.pyw': 'f9b7647b35b6d33d1aad7222eda0dd6573cb6ce882f942a71645f90a8ae3a5b9',
 'bulk_import_engine.py': 'd26ba8c33a1a053c6c733ed6898f10155dfd1caf0d9c0d3390e701b6ea126dec',
 'bulk_import.py': '51ba55af391918560077af5ebc3b6d44e344dd0bdd40d38b79447f2b2724462e',
 'catalog_engine.py': 'cfa49b857cf2223ea5161be3fbca3054378bf4c0a7361d1d5aa243956427d67b',
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
 'pdf_data_304.py': '35d2b42ace3483fc88f56c6e364ff4b464e982aefc7511e74a3b9e4c322f7ce7',
 'pdf_scope.py': '68401d779f3bc97c9473a50c82c91db0c46faa7fc1d64c0b43e982a5d62a748c',
 'pdf_context_240.py': '1556963fc2261fa83e3943283e1ee0509aa73fd602ba60986038672c74caeba1',
 'hit_pdf.py': '62909e7ecbcc5f56d7dca077cf95421cb1ee10931599433557abece32d629ea8',
 'hit_pdf_127.py': 'be2c61ca04a838643573fdb756eb34bb471fdd4ff100b412bb475fee1ce69490',
 'hit_pdf_prev.py': 'b3e7072297cb934acb762bcc99425f2669ad6e0b9e50ff87c50280f9230eaece',
 'substitution_pdf_base.py': '74a4cb629ecd39084374b77467413f6402cd638ae10b8f56c256682898c13883',
 'project_model.py': 'cada7064a452365d119ca813aecedc267152f2009ecde4e05e08e7024fa8efb3',
 'pdf_branding_305.py': '70d86c6238d1cffffab69c251c2f45660d23a8dfcd932821811a94e85808bc21',
 'turto_pdf_logo_305.png.b64': '71a0ae5f632a57e7dfe4204d3f0d494071024e53a25a5850e66481b9875c7d40',
 'design_rows_306.py': '1ceb657e4686ad6eeddf45b0152b30a4be8b6999b84530d880126d88567f43dc',
 'isokorb_qp_307.py': 'f7acace87edcf462add4e803e116e281d4b97f2a8c7f68bf627ce0992931b88b',
 'schoeck_t_qp_307.json': '018c43c96eca6825606a930a6ef354e6d0dbee57b74efedc2d5f14ec9079b4ee',
 'shear_cover_308.py': 'c74a879a7ade048589f4feb02245fe342395b7ec75ed446063f04e5c006cc13a',
 'hit_choice_309.py': '893ebe7a38a78ebc87f845ebd987f0555c2416e94a49f2252cb811bff1863f6b',
 'hit_units_310.py': '8c90d24c0d8cf9bc55001b7825d166916fb9c49c5fd9ddb18675c1a6d7306f61',
 'hit_excel.py': 'c9462e64aefefb0a94c10f6cff54f3424fbcf97d2de1e25cbc072ca32421f626',
 'ui_responsiveness_311.py': 'fd116665eb11c4b9e2001b28de607e9d0b4a1ef587c6210528806e9adfbd87ec',
 'table_controls.py': '41754408ca0d031a1b607b86efec1b192043924101d0693031227524ede0a039',
 'hit_virtual_scroll.py': '13f5599d870e01aa1d6bf1a37c5fc5757ee53d9e4d04fa83e2be4bd9721addd0',
 'decoder_315.py': 'd6d28bf0d291108661ca7bdb42413dbaf5cdb811f0e30bbf5f93a85fd98b066f',
 'isopro_2018_en.json.gz.b64': '560d7f70f90e93285cd4010a05633afc87da6dd0afa5700c20d9b1c8c83c4b0f',
 'schoeck_cz_2024_1_2024_09.json.gz.b64': 'd90cd37a97bc3b2f955b6ffdf4c6c4d25f1d3715b332625a58e7f90f8be94043',
 'shear_dowels_catalog.py': '2eac1519f8f98f01f722c8a5c2d4dbf8cb549346475bff2e1ce89bb2dc03be94',
 'schoeck_dorn_decoder.py': 'd517c335219ebc68de705e4e43ce9bf70e089dde4bf3c5732911409539a1df1d',
 'shear_capacity_317.py': '7614155706abab32c195aa32bf468351ec3b7ce9b6dd1626596cf5388eb8fb00',
 'workspace_controls_317.py': '205cfe7631a2c4b98b0481861e783ae646db1d8f8347c8530b9fda9bcb18bc7d',
 'shear_workflow_236.py': '6b76b22e75912470632b802d4c368c24d4f154bffee7e1a43c27e6a95e8503b0',
 'shear_schedule_io_236.py': 'b3063e5754c15389cee95783755b2827be997a304c1999742a212408134dde31',
 'shear_choice_318.py': '49b1119614edc750fe441616c4331f45f092a81eccc17a9d696cf0160ea2a596',
 'hit_wt.py': '640fbe9d73dea2ae31c64d9e3e00507ba2c44c31c77b5232b88ecdf06f0800d8',
 'hit_wt_ui.py': '6eda7d6f66c4094534f4d4ffb49a9a8a544a0d65884428bcab10fb7c84cc1aed',
 'hit_export_ui_127.py': '3bc63343df01f0836c07d62a588088bd64d3e9307102c6f1981592df155f9cad',
 'st_workspace_319.py': 'd35dcd346d92d7eb386dbfafff7cb7bf2f38e517eb9c99fdeff8f7cd7d9efefe',
 'readability_319.py': '6fa64aaf406234ff2d0d69351a6de32ea2f3bcd86ce0e5dbd9f8608312d5d5ea',
 'decoder_length_320.py': 'e92acf38687dc2fb94399c09dc14e9990b1a14a2ff1d15a8766eaba87ee8bf07',
 'decoder_detail.py': 'fb6a6c0de4206ead6bd333fea175cc8393727571b0a36ef9a219cbb20485db76',
 'project_ui_prev.py': 'e929e4585cac89e4e2f482e578abea312eabe4c9e44dae6d5991f0d257e4fdcc',
 'project_ui_base.py': 'ced1ac409c3ac130184afb6ac5d8400afd1d652d390d702ac4aac3d4cbc65b81',
 'designation_format_321.py': 'e19003c94484f5edc86f37ecc6afb55e1c240c44bce67b4e4467bebb02d9278f',
 'archive_catalog_322.py': 'a444522628e71b5aeda7aafb5663bd9a251d190cc64eae5fb95fe4f3e0b3cecc',
 'schoeck_t_kl_20_322.json': 'a94e182f5b2359eb27a28fec311de036d6d37071678a2c063f55a5f43fc62d2d',
 'catalog_browser_2210.py': '064814670fda55caafff86fc10a68e09caaa9916fbfe3c5c7d76fd2da58c64b0'}


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
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/updates/{VERSION}/runtime_installer.py"
    folder = Path(tempfile.mkdtemp(prefix="turto_315_boot_"))
    target = folder / "runtime_installer.py"
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url + f"?turto={time.time_ns()}_{attempt}",
                headers={
                    "User-Agent": f"TURTO-{VERSION}-Bootstrap",
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
    raise RuntimeError(f"Nelze stáhnout runtime installer {VERSION}.\n{last}")


def _repair_runtime() -> None:
    installer = _download_installer()
    try:
        install = runpy.run_path(str(installer)).get("install_runtime")
        if not callable(install):
            raise RuntimeError("Runtime installer neobsahuje install_runtime().")
        install(ROOT)
        if not PROGRAM_MARKER.is_file():
            raise RuntimeError(f"Opravený runtime nemá značku verze {VERSION}.")
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
    loading = sys.modules.get('_turto_startup_feedback')
    if loading:
        loading.close()
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


def _run() -> int:
    try:
        loading = sys.modules.get('_turto_startup_feedback')
        if loading:
            loading.message('Kontroluji soubory programu…')
        if not _runtime_ready():
            if loading:
                loading.message('Připravuji aktualizaci programu…')
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


STARTUP_UI_SHA256 = "14d2ac307cff18412d5710203876b0a29122c38e5ddb71c652cff8df3d4e907d"


def main() -> int:
    loading = None
    try:
        source = ROOT / "startup_window.py"
        if _matches(source, STARTUP_UI_SHA256):
            loading = runpy.run_path(str(source))["LoadingWindow"]().start()
            sys.modules['_turto_startup_feedback'] = loading
        return _run()
    finally:
        if loading:
            loading.close()
        sys.modules.pop('_turto_startup_feedback', None)


def selftest() -> None:
    assert VERSION == "3.0.22" and RUNTIME_LAYOUT == "53"
    assert len(INSTALLER_COMMIT) == 40 and len(INSTALLER_SHA256) == 64
    assert all(len(value) == 64 for value in CRITICAL_PROGRAM_SHA256.values())
    assert "app_runtime_246.pyw" in CRITICAL_PROGRAM_SHA256
    assert "branding_301.py" in CRITICAL_PROGRAM_SHA256
    assert "turto_icon_301.png.b64" in CRITICAL_PROGRAM_SHA256


if __name__ == "__main__":
    raise SystemExit(main())
