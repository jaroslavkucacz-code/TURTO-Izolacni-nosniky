from __future__ import annotations
"""Verified TURTO 2.2.45 Schöck XT resolver installer. Never writes actions.sqlite3."""
import hashlib
import os
from pathlib import Path
import runpy
import tempfile
import time
import urllib.request

VERSION = "2.2.45"
RUNTIME_LAYOUT = "29"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"

BASE_COMMIT = "35211cdb9cfa06a06bdf19c4fdeb093f255444b5"
BASE_PATH = "updates/2.2.44/runtime_installer.py"
BASE_SHA256 = "c48e5209e605dce8c46ed571754bc3bf10670460f3d706f792d1f70e7074bb14"
BASE_RUNTIME_SHA256 = "815ba2950af3145552c0d40ed2771bd3448c0c00d6feab580c321ee9410b4627"

PAYLOAD_COMMIT = "0294a83eae710d21b99f226e90c51fbcea75797c"
PAYLOADS = {
    "app_runtime.pyw": "8a6b3dc73bef1c6f55ea365016bf8c77ac190e54c0727c7ad415cad9f0582c79",
    "isokorb_xt_resolver_245.py": "193b6f360f80b3136af557197208607442ec263cfab59780a2fbc147658bbe49",
}
MARKER = ".turto_runtime_2_2_45.ok"

def _matches(path: Path, expected: str) -> bool:
    try:
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest().lower() == expected.lower()
    except Exception:
        return False

def _base_ready(program: Path) -> bool:
    return (
        (_matches(program / "app_runtime_244.pyw", BASE_RUNTIME_SHA256)
         or _matches(program / "app_runtime.pyw", BASE_RUNTIME_SHA256))
        and (program / "isokorb_xt_parser_243.py").is_file()
        and (program / "bulk_import_engine.py").is_file()
    )

def _revision_ok(program: Path) -> bool:
    marker = program / MARKER
    return (
        _base_ready(program)
        and _matches(program / "app_runtime_244.pyw", BASE_RUNTIME_SHA256)
        and all(_matches(program / name, sha) for name, sha in PAYLOADS.items())
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
                headers={"User-Agent": agent, "Cache-Control":"no-cache, no-store", "Pragma":"no-cache"},
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != expected.lower():
                raise RuntimeError(f"Nesouhlasí kontrolní součet: {path}; očekáváno {expected}, staženo {actual}.")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Stažení ověřeného souboru selhalo: {path}\n{last}")

def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".turto_2245_", dir=path.parent)
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
        with tempfile.TemporaryDirectory(prefix="turto_2245_base_") as folder:
            base_installer = Path(folder) / "runtime_installer_244.py"
            base_installer.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.45-base"))
            install = runpy.run_path(str(base_installer)).get("install_runtime")
            if not callable(install):
                raise RuntimeError("Ověřený installer 2.2.44 neobsahuje install_runtime().")
            install(root)

    if not _base_ready(program):
        raise RuntimeError("Ověřený runtime 2.2.44 se nepodařilo připravit.")

    if not _matches(program / "app_runtime_244.pyw", BASE_RUNTIME_SHA256):
        source = program / "app_runtime.pyw"
        if not _matches(source, BASE_RUNTIME_SHA256):
            raise RuntimeError("Nelze zmrazit ověřený runtime 2.2.44.")
        _atomic_write(program / "app_runtime_244.pyw", source.read_bytes())

    payload = {
        name: _download(PAYLOAD_COMMIT, f"updates/{VERSION}/{name}", sha, "TURTO-2.2.45-runtime")
        for name, sha in PAYLOADS.items()
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
            raise RuntimeError("Ověření runtime 2.2.45 po instalaci selhalo.")
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
    assert VERSION == "2.2.45" and RUNTIME_LAYOUT == "29"
    assert len(BASE_COMMIT) == 40 and len(PAYLOAD_COMMIT) == 40
    assert len(BASE_SHA256) == 64 and len(BASE_RUNTIME_SHA256) == 64
    assert all(len(x) == 64 for x in PAYLOADS.values())
    assert "actions.sqlite3" not in PAYLOADS

if __name__ == "__main__":
    selftest()
