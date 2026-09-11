from __future__ import annotations

"""TURTO 2.2.26 – responsive UI overlay; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "9b539b2b9f50ab3cf8ef6f6e20504d57cd3ce53d"
BASE_PATH = "updates/2.2.25/runtime_installer.py"
BASE_SHA256 = "0282e173037ff55226ece2bd34392332267126dce9cabcc797738dbb0d80a75b"
RUNTIME_LAYOUT = "19"
PROGRAM_REVISION = ".turto_runtime_2_2_26.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "53aa1ba23bd966e5f677ded99be633c31b6da0d0",
        "updates/2.2.26/app_runtime.pyw",
        "74886b1044aa6b30b9001fd9646190344d1f328730cd7ce6c46a894a1d046609",
    ),
    "shear_dowels_current_225.py": (
        "064d8442b43004a1eff2faa62e1a6d2fe4025fb5",
        "updates/2.2.25/shear_dowels_current.py",
        "3bb7faeb1abd13b3161e8b4c16804c20fd7f3ef90857a89a30f146d05857764f",
    ),
    "shear_dowels_current.py": (
        "ff556044da358d2decea970e3a0ea195fd5442fb",
        "updates/2.2.26/shear_dowels_current.py",
        "acaaba65ae78489f02b7e713f299a32b4f87ae1e7dee0ad6941a108c143538c5",
    ),
    "hit_workspace_219.py": (
        "9286a3ac155a1c06a14e8c76be549818d4cdabdb",
        "updates/2.2.19/hit_workspace.py",
        "b4e2a68c90f8a78cd0e01d8669bcbdcae58e0a4608f4609b64ecc0c2038a4c9b",
    ),
    "hit_workspace.py": (
        "3595511979010a67aefa07aa215241a450e529de",
        "updates/2.2.26/hit_workspace.py",
        "d142f1086fe64bcabec9ffe9c8aff7c1763d48cf36dea2cb977598041ce52d71",
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
    "shear_dowels_current_224.py",
)

CURRENT_REQUIRED = (
    *PREVIOUS_REQUIRED,
    "shear_dowels_current_225.py",
    "hit_workspace_219.py",
)


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
            and marker.read_text(encoding="utf-8").strip() == "2.2.26"
            and _complete(program, CURRENT_REQUIRED)
            and _payloads_match(program)
        )
    except Exception:
        return False


def _install_base(root: Path, temp: Path) -> None:
    installer = temp / "runtime_225.py"
    installer.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.26-base"))
    namespace = runpy.run_path(str(installer))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Installer 2.2.25 neobsahuje install_runtime().")
    install(root)
    program = root / "Program"
    if not _complete(program, PREVIOUS_REQUIRED):
        raise RuntimeError("Ověřený runtime 2.2.25 se nepodařilo obnovit kompletně.")


def _install_payloads(program: Path, temp: Path) -> None:
    downloaded: list[tuple[Path, Path]] = []
    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / ("payload_" + local)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.26-runtime"))
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

    with tempfile.TemporaryDirectory(prefix="turto_2226_") as temp_name:
        temp = Path(temp_name)
        _install_base(root, temp)
        program.mkdir(parents=True, exist_ok=True)
        _install_payloads(program, temp)

        if not _complete(program, CURRENT_REQUIRED):
            raise RuntimeError("Runtime 2.2.26 není po aktualizaci kompletní.")
        if not _payloads_match(program):
            raise RuntimeError("Kontrola runtime 2.2.26 po instalaci selhala.")

        marker = program / PROGRAM_REVISION
        marker.write_text("2.2.26", encoding="utf-8")
        for old in program.glob(".turto_runtime_*.ok"):
            if old != marker:
                old.unlink(missing_ok=True)

    if database_before is not None:
        if not database.is_file() or database.read_bytes() != database_before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")


def selftest() -> None:
    assert RUNTIME_LAYOUT == "19"
    assert len(PAYLOADS) == 5
    assert "shear_dowels_current_225.py" in CURRENT_REQUIRED
    assert "hit_workspace_219.py" in CURRENT_REQUIRED
    assert "shear_movement.py" in CURRENT_REQUIRED
    assert all(len(spec[2]) == 64 for spec in PAYLOADS.values())


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
