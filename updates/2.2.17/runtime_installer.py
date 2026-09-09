from __future__ import annotations

"""TURTO 2.2.17 incremental HIT-flatten installer; actions.sqlite3 is never modified."""

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
RUNTIME_LAYOUT = "10"
PREVIOUS_REVISION = ".turto_runtime_2_2_16.ok"
PROGRAM_REVISION = ".turto_runtime_2_2_17.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "abfdd5389ed8067a44876247583188c5c0c1069a",
        "updates/2.2.17/app_runtime.pyw",
        "6a211656fb69663d80544e163be3d175756f0963d06226f51eaf2224c43ac4ea",
    ),
    "hit_workspace.py": (
        "a5a937b4260be0d7783f8f2bf49d6e9316dcc8e9",
        "updates/2.2.17/hit_workspace.py",
        "603739226ac9b20b75da2d97964f42fc518b2177c4c7fc8bda9b0898d39be968",
    ),
    "cleanup_stage6.py": (
        "bbd2a760ce719b4ff3b42f51be3babbd7b9e94f7",
        "updates/2.2.17/cleanup_stage6.py",
        "27e8ad0444f1252369b902342023e2d799aef3f584e3838845731df6708175d4",
    ),
}

PREVIOUS_REQUIRED = (
    "app_runtime.pyw",
    "app_central_prev.pyw",
    "app_base.py",
    "runtime_paths.py",
    "updater.py",
    "cleanup_stage3.py",
    "cleanup_stage4.py",
    "cleanup_stage5.py",
    "platform_workspace.py",
    "hit_workspace.py",
    "hit_workspace_125.py",
    "hit_workspace_prev.py",
    "hit_workspace_base.py",
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
)

CURRENT_REQUIRED = (
    "app_runtime.pyw",
    "app_central_prev.pyw",
    "app_base.py",
    "runtime_paths.py",
    "updater.py",
    "cleanup_stage3.py",
    "cleanup_stage4.py",
    "cleanup_stage5.py",
    "cleanup_stage6.py",
    "platform_workspace.py",
    "hit_workspace.py",
    "hit_workspace_125.py",
    "hit_workspace_prev.py",
    "hit_workspace_base.py",
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


def _ensure_previous_runtime(root: Path, program: Path, temp: Path) -> None:
    if _revision(program, PREVIOUS_REVISION, "2.2.16") and _complete(program, PREVIOUS_REQUIRED):
        return

    base = temp / "base_installer.py"
    base.write_bytes(
        _download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.17-base")
    )
    namespace = runpy.run_path(str(base))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")
    install(root)
    if not (_revision(program, PREVIOUS_REVISION, "2.2.16") and _complete(program, PREVIOUS_REQUIRED)):
        raise RuntimeError("Předchozí ověřený runtime 2.2.16 se nepodařilo kompletně obnovit.")


def _apply_incremental_overlay(program: Path, temp: Path) -> None:
    staged: dict[str, Path] = {}
    backups: dict[str, Path | None] = {}

    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / f"payload_{Path(local).name}"
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.17-runtime"))
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

    if _revision(program, PROGRAM_REVISION, "2.2.17") and _complete(program, CURRENT_REQUIRED):
        return

    with tempfile.TemporaryDirectory(prefix="turto_2217_") as temp_name:
        temp = Path(temp_name)
        _ensure_previous_runtime(root, program, temp)
        _apply_incremental_overlay(program, temp)

        current_marker = program / PROGRAM_REVISION
        current_marker.write_text("2.2.17", encoding="utf-8")
        for old_marker in program.glob(".turto_runtime_*.ok"):
            if old_marker == current_marker:
                continue
            try:
                old_marker.unlink()
            except Exception:
                pass

        if not _complete(program, CURRENT_REQUIRED):
            raise RuntimeError("Runtime 2.2.17 není po inkrementální aktualizaci kompletní.")


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
