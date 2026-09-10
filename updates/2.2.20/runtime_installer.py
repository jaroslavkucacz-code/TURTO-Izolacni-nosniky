from __future__ import annotations

"""TURTO 2.2.20 central-layer installer; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "c17ab156e01d84f71ff70f1cdcb4c5f50ee49517"
BASE_PATH = "updates/2.2.16/runtime_installer.py"
BASE_SHA256 = "15f86f62aed72967d2552410b0dea1af9eae8f056fa890b1beb77813b7c6a66a"
RUNTIME_LAYOUT = "13"
PREVIOUS_REVISION = ".turto_runtime_2_2_19.ok"
BASE_REVISION = ".turto_runtime_2_2_16.ok"
PROGRAM_REVISION = ".turto_runtime_2_2_20.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "3cc7aaabaa5784716d346f86340ef3bc8d3b2cb0",
        "updates/2.2.20/app_runtime.pyw",
        "4515bdc19e93a2c77156f5aa8f213bf4b743921ae236eb4c94edd3a4593cd300",
    ),
    "hit_workspace.py": (
        "9286a3ac155a1c06a14e8c76be549818d4cdabdb",
        "updates/2.2.19/hit_workspace.py",
        "b4e2a68c90f8a78cd0e01d8669bcbdcae58e0a4608f4609b64ecc0c2038a4c9b",
    ),
    "cleanup_stage8.py": (
        "3778f7aaff545d9edd8f44448619411e48b728a4",
        "updates/2.2.20/cleanup_stage8.py",
        "f10dd8421c98bc13ba4b6e1145739934add85adbc42ba7714f53289896f250cb",
    ),
}

CENTRAL_SUPPORT_REQUIRED = (
    "project_ui.py",
    "project_ui_prev.py",
    "project_ui_base.py",
    "action_workspace.py",
    "action_browser.py",
    "action_browser_123.py",
    "action_payload.py",
    "action_payload_200.py",
    "action_payload_127.py",
    "action_payload_125.py",
    "action_payload_prev.py",
    "action_store.py",
    "action_store_127.py",
    "action_store_125.py",
    "action_store_prev.py",
    "platform_registry.py",
    "platform_registry_200.py",
    "platform_state.py",
    "platform_state_200.py",
    "bulk_import.py",
    "bulk_import_engine.py",
    "hit_decoder_catalog.py",
    "hit_decoder_catalog_prev.py",
)

BASE_REQUIRED = (
    "app_base.py",
    "app_central_prev.pyw",
    "runtime_paths.py",
    "updater.py",
    "platform_workspace.py",
    "hit_workspace.py",
    "hit_workspace_base.py",
    "hit_row_extension.py",
    "hit_virtual_scroll.py",
    "hit_design_ui.py",
    "hit_export_ui.py",
    "hit_aux_ui.py",
    "hit_wt_ui.py",
    "unified_schedule.py",
    "supplier_export.py",
    "hit_pdf.py",
    "shear_movement.py",
    "shear_dowels_current.py",
    "table_polish.py",
    "wt_safety_guard.py",
    "substitution_workspace.py",
    "schoeck_dorn_decoder.py",
    "isokorb_compat.py",
    "substitution_guard.py",
    *CENTRAL_SUPPORT_REQUIRED,
)

PREVIOUS_REQUIRED = (
    "app_runtime.pyw",
    "cleanup_stage7.py",
    *BASE_REQUIRED,
)

CURRENT_REQUIRED = (
    "app_runtime.pyw",
    "app_base.py",
    "runtime_paths.py",
    "updater.py",
    "cleanup_stage8.py",
    "platform_workspace.py",
    "hit_workspace.py",
    "hit_workspace_base.py",
    "hit_row_extension.py",
    "hit_virtual_scroll.py",
    "hit_design_ui.py",
    "hit_export_ui.py",
    "hit_aux_ui.py",
    "hit_wt_ui.py",
    "unified_schedule.py",
    "supplier_export.py",
    "hit_pdf.py",
    "shear_movement.py",
    "shear_dowels_current.py",
    "table_polish.py",
    "wt_safety_guard.py",
    "substitution_workspace.py",
    "schoeck_dorn_decoder.py",
    "isokorb_compat.py",
    "substitution_guard.py",
    *CENTRAL_SUPPORT_REQUIRED,
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


def _ensure_baseline(root: Path, program: Path, temp: Path) -> None:
    if (
        _revision(program, PREVIOUS_REVISION, "2.2.19")
        and _complete(program, PREVIOUS_REQUIRED)
    ):
        return

    base = temp / "base_installer.py"
    base.write_bytes(
        _download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.20-base")
    )
    namespace = runpy.run_path(str(base))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Ověřený základní installer neobsahuje install_runtime().")
    install(root)

    if not (
        _revision(program, BASE_REVISION, "2.2.16")
        and _complete(program, BASE_REQUIRED)
    ):
        raise RuntimeError("Ověřený úplný runtime 2.2.16 se nepodařilo obnovit.")


def _apply_incremental_overlay(program: Path, temp: Path) -> None:
    staged: dict[str, Path] = {}
    backups: dict[str, Path | None] = {}

    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / f"payload_{Path(local).name}"
        source.write_bytes(
            _download(commit, remote, expected, "TURTO-2.2.20-runtime")
        )
        staged[local] = source

    try:
        for local, source in staged.items():
            target = program / local
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                saved = temp / f"backup_{Path(local).name}"
                shutil.copy2(target, saved)
                backups[local] = saved
            else:
                backups[local] = None

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

    if (
        _revision(program, PROGRAM_REVISION, "2.2.20")
        and _complete(program, CURRENT_REQUIRED)
    ):
        return

    database = root / "actions.sqlite3"
    database_before = database.read_bytes() if database.is_file() else None

    with tempfile.TemporaryDirectory(prefix="turto_2220_") as temp_name:
        temp = Path(temp_name)
        _ensure_baseline(root, program, temp)
        _apply_incremental_overlay(program, temp)

        if not _complete(program, CURRENT_REQUIRED):
            raise RuntimeError("Runtime 2.2.20 není po inkrementální aktualizaci kompletní.")

        current_marker = program / PROGRAM_REVISION
        current_marker.write_text("2.2.20", encoding="utf-8")
        for old_marker in program.glob(".turto_runtime_*.ok"):
            if old_marker == current_marker:
                continue
            try:
                old_marker.unlink()
            except Exception:
                pass

    if database_before is not None:
        if not database.is_file() or database.read_bytes() != database_before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
