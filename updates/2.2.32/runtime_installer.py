from __future__ import annotations

"""TURTO 2.2.32 – restore schedule import over the verified 2.2.31 runtime."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "90134c808538d5d4946b71bf71c46bce4d01f287"
BASE_PATH = "updates/2.2.31/runtime_installer.py"
BASE_SHA256 = "b70c61b775185afbb198ab13335fef306bcbd94d1f5ec380f22882246d9668a3"
BASE_APP_RUNTIME_SHA256 = "186a327b161b03cac8b612a097cf480e1e650df3b3b04c67bef8a0ddaa60c4e2"
RUNTIME_LAYOUT = "21"
PROGRAM_REVISION = ".turto_runtime_2_2_32.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "f7b7208d1e91260978ec035f5cddd0ffc65d446b",
        "updates/2.2.32/app_runtime.pyw",
        "56540f96213666734a527ddc208ac1ff6150cb78a114be05646ffdf8d6bcdb3f",
    ),
    "schedule_restore.py": (
        "f7b7208d1e91260978ec035f5cddd0ffc65d446b",
        "updates/2.2.32/schedule_restore.py",
        "986b0190134ef6ad54c92cb7aaf2f883a99292997e03bc498f55732404444e2f",
    ),
}


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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def _base_ready(program: Path) -> bool:
    required = ("app_runtime.pyw", "thermal_design_ui.py", "unified_schedule.py")
    return (
        all((program / name).is_file() for name in required)
        and _sha(program / "app_runtime.pyw") == BASE_APP_RUNTIME_SHA256
    )


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
            and marker.read_text(encoding="utf-8").strip() == "2.2.32"
            and (program / "app_runtime_231.pyw").is_file()
            and _sha(program / "app_runtime_231.pyw") == BASE_APP_RUNTIME_SHA256
            and _payloads_match(program)
        )
    except Exception:
        return False


def _install_base(root: Path, temp: Path) -> None:
    program = root / "Program"
    if _base_ready(program):
        return
    installer = temp / "runtime_231.py"
    installer.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.32-base"))
    namespace = runpy.run_path(str(installer))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Installer 2.2.31 neobsahuje install_runtime().")
    install(root)
    if not _base_ready(program):
        raise RuntimeError("Ověřený runtime 2.2.31 se nepodařilo obnovit kompletně.")


def _install_overlay(program: Path, temp: Path) -> None:
    # Preserve the exact 2.2.31 runtime as the executable base for 2.2.32.
    base_runtime = program / "app_runtime.pyw"
    if _sha(base_runtime) != BASE_APP_RUNTIME_SHA256:
        raise RuntimeError("app_runtime.pyw neodpovídá ověřené verzi 2.2.31.")
    saved_base = program / "app_runtime_231.pyw"
    staged_base = saved_base.with_name(saved_base.name + ".turto_new")
    shutil.copy2(base_runtime, staged_base)
    os.replace(staged_base, saved_base)

    downloaded: list[tuple[Path, Path]] = []
    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / ("payload_" + local)
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.32-runtime"))
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

    with tempfile.TemporaryDirectory(prefix="turto_2232_") as temp_name:
        temp = Path(temp_name)
        _install_base(root, temp)
        _install_overlay(program, temp)

        if not (program / "app_runtime_231.pyw").is_file() or _sha(program / "app_runtime_231.pyw") != BASE_APP_RUNTIME_SHA256 or not _payloads_match(program):
            raise RuntimeError("Runtime 2.2.32 neprošel závěrečnou kontrolou.")

        marker = program / PROGRAM_REVISION
        marker.write_text("2.2.32", encoding="utf-8")
        if not _revision_ok(program):
            raise RuntimeError("Marker runtime 2.2.32 nebyl zapsán správně.")
        for old in program.glob(".turto_runtime_*.ok"):
            if old != marker:
                old.unlink(missing_ok=True)

    if database_before is not None:
        if not database.is_file() or database.read_bytes() != database_before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")


def selftest() -> None:
    assert RUNTIME_LAYOUT == "21"
    assert len(PAYLOADS) == 2
    assert BASE_APP_RUNTIME_SHA256 == "186a327b161b03cac8b612a097cf480e1e650df3b3b04c67bef8a0ddaa60c4e2"
    assert all(len(spec[2]) == 64 for spec in PAYLOADS.values())


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
