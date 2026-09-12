from __future__ import annotations

"""TURTO 2.2.34 – Leviat/HALFEN HSD decoder overlay; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "f045c3f77b8420cd35e966184ce5404e4d2e30d7"
BASE_PATH = "updates/2.2.33/runtime_installer.py"
BASE_SHA256 = "db554cec25ec7b727e44e553044731d45b0d4fdd87779c083cdf70d5fcc15edc"
BASE_APP_RUNTIME_SHA256 = "380e46fe925eca48a44c69e533074ecc434771efbc7eeb16dc53e58bac138291"
RUNTIME_LAYOUT = "21"
PROGRAM_REVISION = ".turto_runtime_2_2_34.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "078e2176c3f3a8f19e181cb59e711e6f1e29256c",
        "updates/2.2.34/app_runtime.pyw",
        "1f2a59d20334c6c71e6b3b60f794010c78a42417eef7b118d9afcc2b54aa4f45",
    ),
    "leviat_hsd.py": (
        "078e2176c3f3a8f19e181cb59e711e6f1e29256c",
        "updates/2.2.34/leviat_hsd.py",
        "683b8eb3e3fc8b307fc1368d97c2e452df3e15eed649a5ac8280d0b89d3f12fd",
    ),
    "hsd_decoder.py": (
        "078e2176c3f3a8f19e181cb59e711e6f1e29256c",
        "updates/2.2.34/hsd_decoder.py",
        "742ae4c19a8a879052c4354daad889654682db1dd47976f7c5470d98eebf00ee",
    ),
}

REQUIRED_SUPPORT = (
    "app_runtime_232.pyw",
    "design_groups_restore.py",
    "schedule_restore.py",
    "thermal_design.py",
    "thermal_design_ui.py",
    "shear_dowels_current.py",
    "shear_ui_227.py",
    "shear_catalogs_227.py",
    "shear_dowels_ui_215.py",
    "hit_workspace.py",
    "unified_schedule.py",
)

CURRENT_REQUIRED = (
    "app_runtime.pyw",
    "app_runtime_233.pyw",
    "leviat_hsd.py",
    "hsd_decoder.py",
    *REQUIRED_SUPPORT,
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def _support_ready(program: Path) -> bool:
    return all((program / name).is_file() for name in REQUIRED_SUPPORT)


def _base_ready(program: Path) -> bool:
    return (
        _support_ready(program)
        and (program / "app_runtime.pyw").is_file()
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
            and marker.read_text(encoding="utf-8").strip() == "2.2.34"
            and all((program / name).is_file() for name in CURRENT_REQUIRED)
            and _sha(program / "app_runtime_233.pyw") == BASE_APP_RUNTIME_SHA256
            and _payloads_match(program)
        )
    except Exception:
        return False


def _install_base(root: Path, temp: Path) -> None:
    program = root / "Program"
    if _base_ready(program):
        return
    installer = temp / "runtime_233.py"
    installer.write_bytes(
        _download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.34-base")
    )
    namespace = runpy.run_path(str(installer))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Installer 2.2.33 neobsahuje install_runtime().")
    install(root)
    if not _base_ready(program):
        raise RuntimeError("Ověřený runtime 2.2.33 se nepodařilo obnovit kompletně.")


def _install_payloads(program: Path, temp: Path) -> None:
    base_runtime = program / "app_runtime.pyw"
    if _sha(base_runtime) != BASE_APP_RUNTIME_SHA256:
        raise RuntimeError("app_runtime.pyw neodpovídá ověřené verzi 2.2.33.")
    saved_base = program / "app_runtime_233.pyw"
    staged_base = saved_base.with_name(saved_base.name + ".turto_new")
    shutil.copy2(base_runtime, staged_base)
    os.replace(staged_base, saved_base)

    downloaded: list[tuple[Path, Path]] = []
    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / ("payload_" + local)
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.34-runtime"))
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

    with tempfile.TemporaryDirectory(prefix="turto_2234_") as temp_name:
        temp = Path(temp_name)
        _install_base(root, temp)
        _install_payloads(program, temp)

        if (
            not _support_ready(program)
            or not (program / "app_runtime_233.pyw").is_file()
            or _sha(program / "app_runtime_233.pyw") != BASE_APP_RUNTIME_SHA256
            or not _payloads_match(program)
        ):
            raise RuntimeError("Runtime 2.2.34 neprošel závěrečnou kontrolou.")

        marker = program / PROGRAM_REVISION
        marker.write_text("2.2.34", encoding="utf-8")
        if not _revision_ok(program):
            raise RuntimeError("Marker runtime 2.2.34 nebyl zapsán správně.")
        for old in program.glob(".turto_runtime_*.ok"):
            if old != marker:
                old.unlink(missing_ok=True)

    if database_before is not None:
        if not database.is_file() or database.read_bytes() != database_before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")


def selftest() -> None:
    assert RUNTIME_LAYOUT == "21"
    assert len(PAYLOADS) == 3
    assert BASE_APP_RUNTIME_SHA256 == "380e46fe925eca48a44c69e533074ecc434771efbc7eeb16dc53e58bac138291"
    assert "shear_catalogs_227.py" in REQUIRED_SUPPORT
    assert "shear_dowels_ui_215.py" in REQUIRED_SUPPORT
    assert all(len(spec[2]) == 64 for spec in PAYLOADS.values())


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
