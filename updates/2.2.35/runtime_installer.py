from __future__ import annotations

"""TURTO 2.2.35 – final HSD decoder release; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "51024386356d7596ba0518518db24f37b8fcfc72"
BASE_PATH = "updates/2.2.34/runtime_installer.py"
BASE_SHA256 = "48e73e1813296bcb16ff9fc1e9a2a040a7dab35650b9196d96d59a225aa834fe"
BASE_APP_RUNTIME_SHA256 = "5576cdae794c9c8fd4f566573acb55bb5e687b5fbcc5c3f1fb521afc0cfcc883"
HSD_DATA_SHA256 = "805f811bee2a8302c2c8ced979ecd2c26a3c92fbe6fd1024940a28dd98e617be"
HSD_UI_SHA256 = "299705a9091784ad88be8d38b6fdbdc69c1bc29d4baf813fb69030e1c11aadf7"
PAYLOAD_COMMIT = "c83e26bdb47c666e66d4bc2ef47b8aca3cb4e76d"
RUNTIME_LAYOUT = "21"
PROGRAM_REVISION = ".turto_runtime_2_2_35.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        PAYLOAD_COMMIT,
        "updates/2.2.35/app_runtime.pyw",
        "8e4c7e8b5ec4a56379e8fa7d1b44ac8a9c6bb8a4a94ac322c29ee1079d7b4290",
    ),
}

BASE_REQUIRED = (
    "design_groups_restore.py",
    "schedule_restore.py",
    "thermal_design_ui.py",
    "platform_workspace.py",
    "shear_dowels_ui.py",
    "shear_dowels_ui_215.py",
    "shear_dowels_catalog.py",
    "halfen_hsd_2026.py",
    "shear_dowels_hsd_234.py",
)

CURRENT_REQUIRED = (
    "app_runtime.pyw",
    "app_runtime_234.pyw",
    *BASE_REQUIRED,
)


def _raw(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def _download(commit: str, path: str, expected: str, agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                _raw(commit, path) + f"?turto={time.time_ns()}_{attempt}",
                headers={"User-Agent": agent, "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != expected.lower():
                raise RuntimeError(
                    f"Kontrolní součet nesouhlasí: {path}\nOčekáváno: {expected}\nStaženo: {actual}"
                )
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout {path}\n{last}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def _base_ready(program: Path) -> bool:
    try:
        return (
            (program / "app_runtime.pyw").is_file()
            and _sha(program / "app_runtime.pyw") == BASE_APP_RUNTIME_SHA256
            and all((program / name).is_file() for name in BASE_REQUIRED)
            and _sha(program / "halfen_hsd_2026.py") == HSD_DATA_SHA256
            and _sha(program / "shear_dowels_hsd_234.py") == HSD_UI_SHA256
        )
    except OSError:
        return False


def _payloads_match(program: Path) -> bool:
    try:
        return all(
            (program / local).is_file() and _sha(program / local) == expected.lower()
            for local, (_commit, _remote, expected) in PAYLOADS.items()
        )
    except OSError:
        return False


def _revision_ok(program: Path) -> bool:
    try:
        marker = program / PROGRAM_REVISION
        return (
            marker.is_file()
            and marker.read_text(encoding="utf-8").strip() == "2.2.35"
            and all((program / name).is_file() for name in CURRENT_REQUIRED)
            and _sha(program / "app_runtime_234.pyw") == BASE_APP_RUNTIME_SHA256
            and _sha(program / "halfen_hsd_2026.py") == HSD_DATA_SHA256
            and _sha(program / "shear_dowels_hsd_234.py") == HSD_UI_SHA256
            and _payloads_match(program)
        )
    except Exception:
        return False


def _install_base(root: Path, temp: Path) -> None:
    program = root / "Program"
    if _base_ready(program):
        return
    installer = temp / "runtime_234.py"
    installer.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.35-base"))
    namespace = runpy.run_path(str(installer))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Installer 2.2.34 neobsahuje install_runtime().")
    install(root)
    if not _base_ready(program):
        raise RuntimeError("Ověřený runtime 2.2.34 se nepodařilo obnovit kompletně.")


def _install_payloads(program: Path, temp: Path) -> None:
    base_runtime = program / "app_runtime.pyw"
    if _sha(base_runtime) != BASE_APP_RUNTIME_SHA256:
        raise RuntimeError("app_runtime.pyw neodpovídá ověřené verzi 2.2.34.")
    saved_base = program / "app_runtime_234.pyw"
    staged_base = saved_base.with_name(saved_base.name + ".turto_new")
    shutil.copy2(base_runtime, staged_base)
    os.replace(staged_base, saved_base)

    downloaded: list[tuple[Path, Path]] = []
    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / ("payload_" + local)
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.35-runtime"))
        downloaded.append((source, program / local))

    backups: list[tuple[Path, Path | None]] = []
    try:
        for source, target in downloaded:
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
                elif backup is None and target.exists():
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

    with tempfile.TemporaryDirectory(prefix="turto_2235_") as temp_name:
        temp = Path(temp_name)
        _install_base(root, temp)
        _install_payloads(program, temp)

        if (
            not all((program / name).is_file() for name in CURRENT_REQUIRED)
            or _sha(program / "app_runtime_234.pyw") != BASE_APP_RUNTIME_SHA256
            or _sha(program / "halfen_hsd_2026.py") != HSD_DATA_SHA256
            or _sha(program / "shear_dowels_hsd_234.py") != HSD_UI_SHA256
            or not _payloads_match(program)
        ):
            raise RuntimeError("Runtime 2.2.35 neprošel závěrečnou kontrolou.")

        marker = program / PROGRAM_REVISION
        marker.write_text("2.2.35", encoding="utf-8")
        if not _revision_ok(program):
            raise RuntimeError("Marker runtime 2.2.35 nebyl zapsán správně.")
        for old in program.glob(".turto_runtime_*.ok"):
            if old != marker:
                old.unlink(missing_ok=True)

    if database_before is not None:
        if not database.is_file() or database.read_bytes() != database_before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")


def selftest() -> None:
    assert RUNTIME_LAYOUT == "21"
    assert len(PAYLOADS) == 1
    assert len(HSD_DATA_SHA256) == 64 and len(HSD_UI_SHA256) == 64
    assert BASE_APP_RUNTIME_SHA256 == "5576cdae794c9c8fd4f566573acb55bb5e687b5fbcc5c3f1fb521afc0cfcc883"
    assert all(len(spec[2]) == 64 for spec in PAYLOADS.values())


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
