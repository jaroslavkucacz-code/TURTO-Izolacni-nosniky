from __future__ import annotations

"""TURTO 2.2.27 – main-window restore guard; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "bf8d867d81f3afdbb76355a15fe843c0f52f1d3d"
BASE_PATH = "updates/2.2.26/runtime_installer.py"
BASE_SHA256 = "12ccc855b45397c30946385f10bb16817e209b307ccf5d730973c77a2a9e0df7"
RUNTIME_LAYOUT = "20"
PROGRAM_REVISION = ".turto_runtime_2_2_27.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "e9120f430223b6e7a914c192755b7a4893ea23ea",
        "updates/2.2.27/app_runtime.pyw",
        "db384a8c7434f2443ad53e5ac75729301bffc942cf8be29a036d01486e452f8d",
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
    "shear_dowels_current_221.py", "shear_dowels_schedule.py", "shear_dowels_schedule_guard.py",
    "shear_dowels_ui_214.py", "shear_dowels_schedule_215.py", "shear_dowels_ui_215.py",
    "historical_schoeck_dorn.py", "shear_ui_227.py", "shear_catalogs_227.py",
    "shear_dowels_current_224.py", "shear_dowels_current_225.py", "hit_workspace_219.py",
)

CURRENT_REQUIRED = PREVIOUS_REQUIRED


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


def _revision_ok(program: Path) -> bool:
    try:
        marker = program / PROGRAM_REVISION
        return (
            marker.is_file()
            and marker.read_text(encoding="utf-8").strip() == "2.2.27"
            and _complete(program, CURRENT_REQUIRED)
            and _payloads_match(program)
        )
    except Exception:
        return False


def _install_base(root: Path, temp: Path) -> None:
    installer = temp / "runtime_226.py"
    installer.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.27-base"))
    namespace = runpy.run_path(str(installer))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Installer 2.2.26 neobsahuje install_runtime().")
    install(root)
    program = root / "Program"
    if not _complete(program, PREVIOUS_REQUIRED):
        raise RuntimeError("Ověřený runtime 2.2.26 se nepodařilo obnovit kompletně.")


def _install_payloads(program: Path, temp: Path) -> None:
    downloaded: list[tuple[Path, Path]] = []
    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / ("payload_" + local)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.27-runtime"))
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

    with tempfile.TemporaryDirectory(prefix="turto_2227_") as temp_name:
        temp = Path(temp_name)
        _install_base(root, temp)
        program.mkdir(parents=True, exist_ok=True)
        _install_payloads(program, temp)

        if not _complete(program, CURRENT_REQUIRED):
            raise RuntimeError("Runtime 2.2.27 není po aktualizaci kompletní.")
        if not _payloads_match(program):
            raise RuntimeError("Kontrola runtime 2.2.27 po instalaci selhala.")

        marker = program / PROGRAM_REVISION
        marker.write_text("2.2.27", encoding="utf-8")
        for old in program.glob(".turto_runtime_*.ok"):
            if old != marker:
                old.unlink(missing_ok=True)

    if database_before is not None:
        if not database.is_file() or database.read_bytes() != database_before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")


def selftest() -> None:
    assert RUNTIME_LAYOUT == "20"
    assert len(PAYLOADS) == 1
    assert "shear_movement.py" in CURRENT_REQUIRED
    assert "hit_workspace_219.py" in CURRENT_REQUIRED
    assert all(len(spec[2]) == 64 for spec in PAYLOADS.values())


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
