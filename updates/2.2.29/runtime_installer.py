from __future__ import annotations

"""TURTO 2.2.29 – Peikko EBEA/TEBEA overlay; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = 'fe70411f90d697d5092ad54ead0caf6ad217591f'
BASE_PATH = 'updates/2.2.28/runtime_installer.py'
BASE_SHA256 = '8ea77d63573109cc9725646723906d7b375061c71cf4cccd4cbc7719ec63a1d3'
RUNTIME_LAYOUT = "21"
PROGRAM_REVISION = ".turto_runtime_2_2_29.ok"

PAYLOADS = {'app_runtime.pyw': ('5f38de20ab8ebff5afd8d47669813a3e3461346d', 'updates/2.2.29/app_runtime.pyw', '2f39aa0d0e3a462a5e507d50df9e0bc964ddf584c722b730a099863c11145430'), 'peikko_thermal_breaks.py': ('5f38de20ab8ebff5afd8d47669813a3e3461346d', 'updates/2.2.29/peikko_thermal_breaks.py', '2992f45e882ddddebcb99a78e8e9f73e6fb20d687a5233efd5df8249fca41b88'), 'peikko_catalog.py': ('5f38de20ab8ebff5afd8d47669813a3e3461346d', 'updates/2.2.29/peikko_catalog.py', '7cdf51221345b49bea2fe765a508ed877ffa5af16780e75455ed728238757c34'), 'peikko_workspace.py': ('5f38de20ab8ebff5afd8d47669813a3e3461346d', 'updates/2.2.29/peikko_workspace.py', 'cc9298d8a6b65eaef8bffe93e1ca43443872e4c3cef3dad9f9319ba6a8a6ccd1')}

PREVIOUS_REQUIRED = ('app_runtime.pyw', 'app_runtime_221.pyw', 'app_base.py', 'runtime_paths.py', 'updater.py', 'cleanup_stage8.py', 'platform_workspace.py', 'hit_workspace.py', 'hit_workspace_base.py', 'hit_row_extension.py', 'hit_virtual_scroll.py', 'hit_design_ui.py', 'hit_export_ui.py', 'hit_aux_ui.py', 'hit_wt_ui.py', 'unified_schedule.py', 'supplier_export.py', 'hit_pdf.py', 'shear_movement.py', 'shear_dowels_current.py', 'table_polish.py', 'wt_safety_guard.py', 'substitution_workspace.py', 'schoeck_dorn_decoder.py', 'isokorb_compat.py', 'substitution_guard.py', 'project_ui.py', 'project_ui_prev.py', 'project_ui_base.py', 'action_workspace.py', 'action_browser.py', 'action_browser_123.py', 'action_payload.py', 'action_payload_200.py', 'action_payload_127.py', 'action_payload_125.py', 'action_payload_prev.py', 'action_store.py', 'action_store_127.py', 'action_store_125.py', 'action_store_prev.py', 'platform_registry.py', 'platform_registry_200.py', 'platform_state.py', 'platform_state_200.py', 'bulk_import.py', 'bulk_import_engine.py', 'hit_decoder_catalog.py', 'hit_decoder_catalog_prev.py', 'shear_dowels_current_221.py', 'shear_dowels_schedule.py', 'shear_dowels_schedule_guard.py', 'shear_dowels_ui_214.py', 'shear_dowels_schedule_215.py', 'shear_dowels_ui_215.py', 'historical_schoeck_dorn.py', 'shear_ui_227.py', 'shear_catalogs_227.py', 'shear_dowels_current_224.py', 'shear_dowels_current_225.py', 'hit_workspace_219.py', 'app_runtime_227.pyw', 'peikko_thermal_breaks.py', 'peikko_workspace.py')

CURRENT_REQUIRED = ('app_runtime.pyw', 'app_runtime_221.pyw', 'app_base.py', 'runtime_paths.py', 'updater.py', 'cleanup_stage8.py', 'platform_workspace.py', 'hit_workspace.py', 'hit_workspace_base.py', 'hit_row_extension.py', 'hit_virtual_scroll.py', 'hit_design_ui.py', 'hit_export_ui.py', 'hit_aux_ui.py', 'hit_wt_ui.py', 'unified_schedule.py', 'supplier_export.py', 'hit_pdf.py', 'shear_movement.py', 'shear_dowels_current.py', 'table_polish.py', 'wt_safety_guard.py', 'substitution_workspace.py', 'schoeck_dorn_decoder.py', 'isokorb_compat.py', 'substitution_guard.py', 'project_ui.py', 'project_ui_prev.py', 'project_ui_base.py', 'action_workspace.py', 'action_browser.py', 'action_browser_123.py', 'action_payload.py', 'action_payload_200.py', 'action_payload_127.py', 'action_payload_125.py', 'action_payload_prev.py', 'action_store.py', 'action_store_127.py', 'action_store_125.py', 'action_store_prev.py', 'platform_registry.py', 'platform_registry_200.py', 'platform_state.py', 'platform_state_200.py', 'bulk_import.py', 'bulk_import_engine.py', 'hit_decoder_catalog.py', 'hit_decoder_catalog_prev.py', 'shear_dowels_current_221.py', 'shear_dowels_schedule.py', 'shear_dowels_schedule_guard.py', 'shear_dowels_ui_214.py', 'shear_dowels_schedule_215.py', 'shear_dowels_ui_215.py', 'historical_schoeck_dorn.py', 'shear_ui_227.py', 'shear_catalogs_227.py', 'shear_dowels_current_224.py', 'shear_dowels_current_225.py', 'hit_workspace_219.py', 'app_runtime_227.pyw', 'peikko_thermal_breaks.py', 'peikko_workspace.py', 'peikko_catalog.py')


def _raw(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def _download(commit: str, path: str, expected: str, agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                _raw(commit, path) + f"?turto={time.time_ns()}_{attempt}",
                headers={
                    "User-Agent": agent,
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != expected.lower():
                raise RuntimeError(
                    f"Kontrolní součet nesouhlasí: {path}\n"
                    f"Očekáváno: {expected}\nStaženo: {actual}"
                )
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout {path}\n{last}")


def _complete(program: Path, required: tuple[str, ...]) -> bool:
    return program.is_dir() and all((program / name).is_file() for name in required)


def _payloads_match(program: Path) -> bool:
    try:
        for local, (_commit, _remote, expected) in PAYLOADS.items():
            path = program / local
            if not path.is_file():
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest().lower() != expected.lower():
                return False
        return True
    except Exception:
        return False


BASELINE_SHA256 = {'app_runtime_227.pyw': 'db384a8c7434f2443ad53e5ac75729301bffc942cf8be29a036d01486e452f8d', 'shear_dowels_current.py': 'acaaba65ae78489f02b7e713f299a32b4f87ae1e7dee0ad6941a108c143538c5', 'shear_dowels_current_225.py': '3bb7faeb1abd13b3161e8b4c16804c20fd7f3ef90857a89a30f146d05857764f', 'shear_dowels_current_224.py': '42025cb2bcf5e5bdb8d6ccd6f098bffb9ae49a10632e8da3d660c2d54200b35f', 'shear_dowels_current_221.py': 'de150f895f7be451a6f0dc46d05918ef75254604c3eb2557d4211ac7e4a01318', 'shear_ui_227.py': 'c73e459a7ad8340d54d0fdc6990c5be936bcf55d3896fb4bd719d7c7180bd94d', 'shear_catalogs_227.py': 'b1e59c850451ae662e2bfc065db04ac8038f1dc3d2137776e9fcb314324ab44f', 'shear_dowels_ui_215.py': 'e510f974ac9f98320e563424da924a00c5dd9868fa5c836338ea2fac136ae265', 'shear_dowels_ui_214.py': 'ece048d76888dbdb398ea9b6c67ef4bcb2765a0904987ae358cc59765a069813', 'hit_workspace.py': 'd142f1086fe64bcabec9ffe9c8aff7c1763d48cf36dea2cb977598041ce52d71', 'hit_workspace_219.py': 'b4e2a68c90f8a78cd0e01d8669bcbdcae58e0a4608f4609b64ecc0c2038a4c9b'}


def _baseline_valid(program: Path) -> bool:
    try:
        return all((program / name).is_file() and
                   hashlib.sha256((program / name).read_bytes()).hexdigest() == expected
                   for name, expected in BASELINE_SHA256.items())
    except OSError:
        return False


def _revision_ok(program: Path) -> bool:
    try:
        marker = program / PROGRAM_REVISION
        return (
            marker.is_file()
            and marker.read_text(encoding="utf-8").strip() == "2.2.29"
            and _complete(program, CURRENT_REQUIRED)
            and _payloads_match(program)
            and _baseline_valid(program)
        )
    except Exception:
        return False


def _install_base(root: Path, temp: Path) -> None:
    program = root / "Program"
    if _complete(program, PREVIOUS_REQUIRED) and _baseline_valid(program):
        return
    installer = temp / "runtime_228.py"
    installer.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.29-base"))
    namespace = runpy.run_path(str(installer))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Installer 2.2.28 neobsahuje install_runtime().")
    install(root)
    program = root / "Program"
    if not _complete(program, PREVIOUS_REQUIRED):
        raise RuntimeError("Ověřený runtime 2.2.28 se nepodařilo obnovit kompletně.")


def _install_payloads(program: Path, temp: Path) -> None:
    downloaded: list[tuple[Path, Path]] = []
    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / ("payload_" + local)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.29-runtime"))
        downloaded.append((source, program / local))

    backups: list[tuple[Path, Path | None]] = []
    try:
        for source, target in downloaded:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if target.exists():
                backup = temp / ("backup_" + target.name)
                shutil.copy2(target, backup)
            backups.append((target, backup))
            staged = target.with_name(target.name + ".turto_new")
            shutil.copy2(source, staged)
            os.replace(staged, target)
    except Exception:
        for target, backup in reversed(backups):
            try:
                if backup is not None and backup.exists():
                    staged = target.with_name(target.name + ".turto_restore")
                    shutil.copy2(backup, staged)
                    os.replace(staged, target)
                elif target.exists():
                    target.unlink()
            except Exception:
                pass
        raise


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    program = root / "Program"
    if _revision_ok(program):
        return

    database = root / "actions.sqlite3"
    database_before = database.read_bytes() if database.is_file() else None

    with tempfile.TemporaryDirectory(prefix="turto_2229_") as temp_name:
        temp = Path(temp_name)
        _install_base(root, temp)
        program.mkdir(parents=True, exist_ok=True)
        _install_payloads(program, temp)

        if not _complete(program, CURRENT_REQUIRED):
            raise RuntimeError("Runtime 2.2.29 není po aktualizaci kompletní.")
        if not _payloads_match(program):
            raise RuntimeError("Kontrola runtime 2.2.29 po instalaci selhala.")

        marker = program / PROGRAM_REVISION
        marker.write_text("2.2.29", encoding="utf-8")
        for old in program.glob(".turto_runtime_*.ok"):
            if old != marker:
                old.unlink(missing_ok=True)

    if database_before is not None:
        if not database.is_file() or database.read_bytes() != database_before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")


def selftest() -> None:
    assert RUNTIME_LAYOUT == "21"
    assert len(PAYLOADS) == 4
    assert "app_runtime_227.pyw" in CURRENT_REQUIRED
    assert "peikko_thermal_breaks.py" in CURRENT_REQUIRED
    assert "peikko_workspace.py" in CURRENT_REQUIRED
    assert "peikko_catalog.py" in CURRENT_REQUIRED
    assert all(len(spec[2]) == 64 for spec in PAYLOADS.values())


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
