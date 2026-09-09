from __future__ import annotations

"""TURTO 2.2.16 incremental runtime installer; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "c51b5ad3803cf5049dbd467a8f23b9d1f24006e5"
BASE_PATH = "updates/2.2.15/runtime_installer.py"
BASE_SHA256 = "7f7d3509de69a1598878b391f05eefcc0d9142c52359e0a64e66c5d4bac9f943"
RUNTIME_LAYOUT = "9"
PREVIOUS_REVISION = ".turto_runtime_2_2_15.ok"
PROGRAM_REVISION = ".turto_runtime_2_2_16.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "f13eab497645112d3972ab0769ec18dd59208f05",
        "updates/2.2.16/app_runtime.pyw",
        "68b980cd899a68e95c0b22401d4a05a7e1744d4c192571b73751940450145a5e",
    ),
    "cleanup_stage5.py": (
        "20f362723de0dd25fc8847a1b3dc1ce4f2028967",
        "updates/2.2.16/cleanup_stage5.py",
        "24b399936bebf1a3d082b4f6e418f9b62b60e6774c56422ea7b67f37600b976d",
    ),
}

# Existing 2.2.15 installations can be upgraded in place. A missing/corrupt
# prerequisite intentionally falls back to the fully verified 2.2.15 installer.
PREVIOUS_REQUIRED = (
    "app_runtime.pyw",
    "app_runtime_202.pyw",
    "app_runtime_200.pyw",
    "app_runtime_127.pyw",
    "app_runtime_prev.pyw",
    "app_central_prev.pyw",
    "app_base.py",
    "runtime_paths.py",
    "updater.py",
    "cleanup_stage3.py",
    "cleanup_stage4.py",
    "platform_workspace.py",
    "hit_workspace.py",
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
    "platform_workspace.py",
    "hit_workspace.py",
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
    if _revision(program, PREVIOUS_REVISION, "2.2.15") and _complete(program, PREVIOUS_REQUIRED):
        return

    base = temp / "base_installer.py"
    base.write_bytes(
        _download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.16-base")
    )
    namespace = runpy.run_path(str(base))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")
    install(root)
    if not (_revision(program, PREVIOUS_REVISION, "2.2.15") and _complete(program, PREVIOUS_REQUIRED)):
        raise RuntimeError("Předchozí ověřený runtime 2.2.15 se nepodařilo kompletně obnovit.")


def _apply_incremental_overlay(program: Path, temp: Path) -> None:
    staged: dict[str, Path] = {}
    backups: dict[str, Path | None] = {}

    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / f"payload_{Path(local).name}"
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.16-runtime"))
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

    if _revision(program, PROGRAM_REVISION, "2.2.16") and _complete(program, CURRENT_REQUIRED):
        return

    with tempfile.TemporaryDirectory(prefix="turto_2216_") as temp_name:
        temp = Path(temp_name)
        _ensure_previous_runtime(root, program, temp)
        _apply_incremental_overlay(program, temp)

        current_marker = program / PROGRAM_REVISION
        for old_marker in program.glob(".turto_runtime_*.ok"):
            if old_marker == current_marker:
                continue
            try:
                old_marker.unlink()
            except Exception:
                pass
        current_marker.write_text("2.2.16", encoding="utf-8")

        if not _complete(program, CURRENT_REQUIRED):
            raise RuntimeError("Runtime 2.2.16 není po inkrementální aktualizaci kompletní.")


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
