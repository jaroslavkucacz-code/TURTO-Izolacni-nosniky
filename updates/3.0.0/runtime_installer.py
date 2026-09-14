from __future__ import annotations

"""Verified TURTO 3.0.0 branding installer. Never writes actions.sqlite3."""

import hashlib
import os
from pathlib import Path
import runpy
import tempfile
import time
import urllib.request

VERSION = "3.0.0"
RUNTIME_LAYOUT = "31"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"

BASE_COMMIT = "00fce83b4abd9912dbf26c113b798c6670fa9241"
BASE_PATH = "updates/2.2.46/runtime_installer.py"
BASE_SHA256 = "9c9a435923c0cb4514dedeaaf06a10fb743c3b4201ed999d36b63ee617b2bad2"
BASE_RUNTIME_SHA256 = "f9b7647b35b6d33d1aad7222eda0dd6573cb6ce882f942a71645f90a8ae3a5b9"

PAYLOADS = {
    "app_runtime.pyw": (
        "8e2bc4bb6bcdf4c499111a2aa7791c6074935923",
        "updates/3.0.0/app_runtime.pyw",
        "237408e1c49ee2124bf49215f7c428ca660ad93927046559e55186fd619aea45",
    ),
    "branding_300.py": (
        "5f723b15712d6f39e68f03fda14fe966077da33c",
        "updates/3.0.0/branding_300.py",
        "4e2873a4f8268f2f7c3baf953eb84fd701add04a5dde89d4255fbb83240b9228",
    ),
    "turto_logo_300.png": (
        "5f723b15712d6f39e68f03fda14fe966077da33c",
        "updates/3.0.0/turto_logo_300.png",
        "9466ad8706d3a7f0473b025a9eb2ddd82fb0ae0b2ac06a0665780e28af16820f",
    ),
}
MARKER = ".turto_runtime_3_0_0.ok"


def _matches(path: Path, expected: str) -> bool:
    try:
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest().lower() == expected.lower()
    except Exception:
        return False


def _base_ready(program: Path) -> bool:
    return (
        (
            _matches(program / "app_runtime_246.pyw", BASE_RUNTIME_SHA256)
            or _matches(program / "app_runtime.pyw", BASE_RUNTIME_SHA256)
        )
        and (program / "isokorb_xt_resolver_245.py").is_file()
        and (program / "isokorb_xt_resolver_246.py").is_file()
        and (program / "bulk_import.py").is_file()
        and (program / "bulk_import_engine.py").is_file()
    )


def _revision_ok(program: Path) -> bool:
    marker = program / MARKER
    return (
        _base_ready(program)
        and _matches(program / "app_runtime_246.pyw", BASE_RUNTIME_SHA256)
        and all(_matches(program / name, item[2]) for name, item in PAYLOADS.items())
        and marker.is_file()
        and marker.read_text(encoding="utf-8").strip() == VERSION
    )


def _download(commit: str, path: str, expected: str, agent: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url + f"?turto={time.time_ns()}_{attempt}",
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
                raise RuntimeError(
                    f"Nesouhlasí kontrolní součet: {path}; očekáváno {expected}, staženo {actual}."
                )
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Stažení ověřeného souboru selhalo: {path}\n{last}")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".turto_300_", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def install_runtime(root) -> Path:
    root = Path(root).resolve()
    program = root / "Program"
    program.mkdir(parents=True, exist_ok=True)
    if _revision_ok(program):
        return program / "app_runtime.pyw"

    database = root / "actions.sqlite3"
    database_before = database.read_bytes() if database.is_file() else None

    if not _base_ready(program):
        with tempfile.TemporaryDirectory(prefix="turto_300_base_") as folder:
            base_installer = Path(folder) / "runtime_installer_2246.py"
            base_installer.write_bytes(
                _download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-3.0.0-base")
            )
            install = runpy.run_path(str(base_installer)).get("install_runtime")
            if not callable(install):
                raise RuntimeError("Ověřený installer 2.2.46 neobsahuje install_runtime().")
            install(root)

    if not _base_ready(program):
        raise RuntimeError("Ověřený runtime 2.2.46 se nepodařilo připravit.")

    if not _matches(program / "app_runtime_246.pyw", BASE_RUNTIME_SHA256):
        source = program / "app_runtime.pyw"
        if not _matches(source, BASE_RUNTIME_SHA256):
            raise RuntimeError("Nelze zmrazit ověřený runtime 2.2.46.")
        _atomic_write(program / "app_runtime_246.pyw", source.read_bytes())

    payload = {
        name: _download(commit, remote, expected, "TURTO-3.0.0-runtime")
        for name, (commit, remote, expected) in PAYLOADS.items()
    }
    targets = [program / name for name in payload]
    backups = {path: path.read_bytes() if path.is_file() else None for path in targets}
    marker = program / MARKER
    marker_before = marker.read_bytes() if marker.is_file() else None

    try:
        for name, data in payload.items():
            _atomic_write(program / name, data)
        marker.write_text(VERSION, encoding="utf-8")

        if database_before is not None:
            if not database.is_file() or database.read_bytes() != database_before:
                raise RuntimeError("actions.sqlite3 se během aktualizace změnila.")

        if not _revision_ok(program):
            raise RuntimeError("Ověření runtime 3.0.0 po instalaci selhalo.")
    except Exception:
        for path, data in backups.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, data)
        if marker_before is None:
            marker.unlink(missing_ok=True)
        else:
            _atomic_write(marker, marker_before)
        raise

    return program / "app_runtime.pyw"


def selftest() -> None:
    assert VERSION == "3.0.0"
    assert RUNTIME_LAYOUT == "31"
    assert len(BASE_COMMIT) == 40
    assert len(BASE_SHA256) == 64
    assert len(BASE_RUNTIME_SHA256) == 64
    assert PAYLOADS
    assert all(len(item) == 3 for item in PAYLOADS.values())
    assert all(len(item[0]) == 40 and len(item[2]) == 64 for item in PAYLOADS.values())
    assert "actions.sqlite3" not in PAYLOADS


if __name__ == "__main__":
    selftest()
