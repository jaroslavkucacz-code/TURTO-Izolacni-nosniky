from __future__ import annotations

"""TURTO 2.2.23 startup hotfix installer; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "0c7616459c0d26ee49fd67b031f0a29d128fc60a"
BASE_PATH = "updates/2.2.22/runtime_installer.py"
BASE_SHA256 = "40f96de2f20e3b2c1540a99d17df0da39dcdc5f10cb541f24e3d06e9e3151bfa"
RUNTIME_LAYOUT = "16"
PREVIOUS_REVISION = ".turto_runtime_2_2_22.ok"
PROGRAM_REVISION = ".turto_runtime_2_2_23.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "c1409102eef710b527ba91fe6b8ab304836fc0ab",
        "updates/2.2.23/app_runtime.pyw",
        "8b2ccc9c9881137e4f9a33947a2c5d716568fbb687c79bc97548203da386c78f",
    ),
    "shear_dowels_current_221.py": (
        "3c4ebb0720f6db8e40bb59d697523b77fd3d53ca",
        "updates/2.2.21/shear_dowels_current.py",
        "de150f895f7be451a6f0dc46d05918ef75254604c3eb2557d4211ac7e4a01318",
    ),
    "shear_dowels_current.py": (
        "03a908174ce5c2e26e428266d80926aff5ca8cf3",
        "updates/2.2.23/shear_dowels_current.py",
        "53971b15c53b9ca4126ab94ecd6a339075326d1bb366a915c7b8eedcb8f4cd25",
    ),
    "shear_dowels_schedule.py": (
        "b198cbb7bf0720d694dfda5e9baf66c07d9bc23e",
        "updates/2.1.4/shear_dowels_schedule.py",
        "72ac97981f2d1952fc508ecb1b47fef21b7f45199259f72f40d5812eb2374cfa",
    ),
    "shear_dowels_schedule_guard.py": (
        "b198cbb7bf0720d694dfda5e9baf66c07d9bc23e",
        "updates/2.1.4/shear_dowels_schedule_guard.py",
        "c9b09cdc563de7622a5fa900e15f056c6b5d25d281c5bbd47dfc27e387b7e786",
    ),
    "shear_dowels_ui_214.py": (
        "b198cbb7bf0720d694dfda5e9baf66c07d9bc23e",
        "updates/2.1.4/shear_dowels_ui_214.py",
        "ece048d76888dbdb398ea9b6c67ef4bcb2765a0904987ae358cc59765a069813",
    ),
    "shear_dowels_schedule_215.py": (
        "58f5bcd6b322b85446672270c5881630e89cd172",
        "updates/2.1.5/shear_dowels_schedule_215.py",
        "83553525a96dedd11484c63e52f81957441fc58abae0401fd256543c562e96f5",
    ),
    "shear_dowels_ui_215.py": (
        "58f5bcd6b322b85446672270c5881630e89cd172",
        "updates/2.1.5/shear_dowels_ui_215.py",
        "e510f974ac9f98320e563424da924a00c5dd9868fa5c836338ea2fac136ae265",
    ),
    "historical_schoeck_dorn.py": (
        "58f5bcd6b322b85446672270c5881630e89cd172",
        "updates/2.1.5/historical_schoeck_dorn.py",
        "b1e1b18903a0af04111829fe68d878a665a9cf5eef3ec57bba7c3dc334ab8e2c",
    ),
}

PREVIOUS_REQUIRED = (
    "app_runtime.pyw", "app_runtime_221.pyw", "app_base.py", "runtime_paths.py", "updater.py",
    "cleanup_stage8.py", "platform_workspace.py", "hit_workspace.py", "hit_workspace_base.py",
    "hit_row_extension.py", "hit_virtual_scroll.py", "hit_design_ui.py", "hit_export_ui.py",
    "hit_aux_ui.py", "hit_wt_ui.py", "unified_schedule.py", "supplier_export.py", "hit_pdf.py",
    "shear_movement.py", "shear_dowels_current.py", "table_polish.py", "wt_safety_guard.py",
    "substitution_workspace.py", "schoeck_dorn_decoder.py", "isokorb_compat.py", "substitution_guard.py",
    "project_ui.py", "project_ui_prev.py", "project_ui_base.py", "action_workspace.py",
    "action_browser.py", "action_browser_123.py", "action_payload.py", "action_payload_200.py",
    "action_payload_127.py", "action_payload_125.py", "action_payload_prev.py", "action_store.py",
    "action_store_127.py", "action_store_125.py", "action_store_prev.py", "platform_registry.py",
    "platform_registry_200.py", "platform_state.py", "platform_state_200.py", "bulk_import.py",
    "bulk_import_engine.py", "hit_decoder_catalog.py", "hit_decoder_catalog_prev.py",
)

CURRENT_REQUIRED = (
    *PREVIOUS_REQUIRED,
    "shear_dowels_current_221.py",
    "shear_dowels_schedule.py",
    "shear_dowels_schedule_guard.py",
    "shear_dowels_ui_214.py",
    "shear_dowels_schedule_215.py",
    "shear_dowels_ui_215.py",
    "historical_schoeck_dorn.py",
)


def _url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def _download(commit: str, path: str, expected: str, agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                _url(commit, path) + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={
                    "User-Agent": agent,
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != expected.lower():
                raise RuntimeError(f"SHA-256 nesouhlasí pro {path}: {actual}")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout {path}: {last}")


def _complete(program: Path, required: tuple[str, ...]) -> bool:
    return program.is_dir() and all((program / name).is_file() for name in required)


def _revision(program: Path, marker: str, expected: str) -> bool:
    try:
        path = program / marker
        return path.is_file() and path.read_text(encoding="utf-8").strip() == expected
    except Exception:
        return False


def _ensure_previous(root: Path, program: Path, temp: Path) -> None:
    if _revision(program, PREVIOUS_REVISION, "2.2.22") and _complete(program, PREVIOUS_REQUIRED):
        return
    base = temp / "base_installer.py"
    base.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.23-base"))
    namespace = runpy.run_path(str(base))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Ověřený installer 2.2.22 neobsahuje install_runtime().")
    install(root)
    if not (_revision(program, PREVIOUS_REVISION, "2.2.22") and _complete(program, PREVIOUS_REQUIRED)):
        raise RuntimeError("Ověřený runtime 2.2.22 se nepodařilo obnovit.")


def _apply_overlay(program: Path, temp: Path) -> None:
    staged: dict[str, Path] = {}
    backups: dict[str, Path | None] = {}
    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / f"payload_{Path(local).name}"
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.23-runtime"))
        staged[local] = source

    try:
        for local, source in staged.items():
            target = program / local
            target.parent.mkdir(parents=True, exist_ok=True)
            saved = None
            if target.exists():
                saved = temp / f"backup_{Path(local).name}"
                shutil.copy2(target, saved)
            backups[local] = saved
            replacement = target.with_name(target.name + ".turto_new")
            shutil.copy2(source, replacement)
            os.replace(replacement, target)
    except Exception:
        for local in reversed(tuple(staged)):
            target = program / local
            saved = backups.get(local)
            try:
                if saved is not None and saved.exists():
                    restore = target.with_name(target.name + ".turto_restore")
                    shutil.copy2(saved, restore)
                    os.replace(restore, target)
                elif local in backups and target.exists():
                    target.unlink()
            except Exception:
                pass
        raise


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    program = root / "Program"
    if _revision(program, PROGRAM_REVISION, "2.2.23") and _complete(program, CURRENT_REQUIRED):
        return

    database = root / "actions.sqlite3"
    database_before = database.read_bytes() if database.is_file() else None

    with tempfile.TemporaryDirectory(prefix="turto_2223_") as temp_name:
        temp = Path(temp_name)
        _ensure_previous(root, program, temp)
        _apply_overlay(program, temp)
        if not _complete(program, CURRENT_REQUIRED):
            raise RuntimeError("Runtime 2.2.23 není po aktualizaci kompletní.")

        current_marker = program / PROGRAM_REVISION
        current_marker.write_text("2.2.23", encoding="utf-8")
        for old_marker in program.glob(".turto_runtime_*.ok"):
            if old_marker != current_marker:
                old_marker.unlink(missing_ok=True)

    if database_before is not None and (
        not database.is_file() or database.read_bytes() != database_before
    ):
        raise RuntimeError("actions.sqlite3 se během instalace změnila.")


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
