from __future__ import annotations
"""Verified TURTO 2.2.44 maintenance installer. Preserves the 2.2.43 runtime and never writes actions.sqlite3."""

import hashlib
import os
from pathlib import Path
import runpy
import tempfile
import time
import urllib.request

VERSION = "2.2.44"
RUNTIME_LAYOUT = "28"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"

BASE_COMMIT = "b194cfd7c25937ea25317dc236b85ba0fc06be26"
BASE_PATH = "updates/2.2.43/runtime_installer.py"
BASE_SHA256 = "8f1a570370c7e47a68641d916b33a5d17007b6859983c32c902c0f714451f5ed"
BASE_RUNTIME_SHA256 = "fd527e691770a5547f387e1cb47c535aae06df8dc063f07917bdcfd88a07f752"
XT_PARSER_SHA256 = "680f6853fbb62234a440c2a43e8d1b4f0b03e0df2b4d69c4b84b6b52a2a28352"

PAYLOAD_COMMIT = "a80c2dd2b0177c4107b097ecfb81382bc1748e02"
NEW_RUNTIME_SHA256 = "815ba2950af3145552c0d40ed2771bd3448c0c00d6feab580c321ee9410b4627"
PAYLOADS = {
    "app_runtime.pyw": (
        PAYLOAD_COMMIT,
        "updates/2.2.44/app_runtime.pyw",
        NEW_RUNTIME_SHA256,
    ),
}
MARKER = ".turto_runtime_2_2_44.ok"


def _matches(path: Path, expected: str) -> bool:
    try:
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest().lower() == expected
    except Exception:
        return False


def _base_ready(program: Path) -> bool:
    runtime243 = (
        _matches(program / "app_runtime_243.pyw", BASE_RUNTIME_SHA256)
        or _matches(program / "app_runtime.pyw", BASE_RUNTIME_SHA256)
    )
    required = (
        "runtime_paths.py",
        "platform_workspace.py",
        "hit_pdf.py",
        "pdf_scope.py",
        "app_runtime_242.pyw",
        "app_runtime_240.pyw",
        "shear_cret_sync_242.py",
        "shear_substitution_237.py",
        "shear_cret_239.py",
        "cret_series_100_239.py",
        "cret_series_100_239_data1.py",
        "cret_series_100_239_data2.py",
        "cret_series_100_239_data3.py",
        "cret_series_100_239_data4.py",
        "pdf_context_240.py",
    )
    return (
        runtime243
        and _matches(program / "isokorb_xt_parser_243.py", XT_PARSER_SHA256)
        and all((program / name).is_file() for name in required)
    )


def _revision_ok(program: Path) -> bool:
    marker = program / MARKER
    return (
        _base_ready(program)
        and _matches(program / "app_runtime_243.pyw", BASE_RUNTIME_SHA256)
        and _matches(program / "app_runtime.pyw", NEW_RUNTIME_SHA256)
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
    fd, temp_name = tempfile.mkstemp(prefix=".turto_2244_", dir=path.parent)
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
        with tempfile.TemporaryDirectory(prefix="turto_2244_base_") as folder:
            installer = Path(folder) / "runtime_installer_243.py"
            installer.write_bytes(
                _download(
                    BASE_COMMIT,
                    BASE_PATH,
                    BASE_SHA256,
                    "TURTO-2.2.44-base",
                )
            )
            namespace = runpy.run_path(str(installer))
            install = namespace.get("install_runtime")
            if not callable(install):
                raise RuntimeError("Ověřený installer 2.2.43 neobsahuje install_runtime().")
            install(root)

    if not _base_ready(program):
        raise RuntimeError("Ověřený runtime 2.2.43 se nepodařilo připravit.")

    payload_commit, payload_path, payload_sha = PAYLOADS["app_runtime.pyw"]
    new_runtime = _download(
        payload_commit,
        payload_path,
        payload_sha,
        "TURTO-2.2.44-runtime",
    )

    targets = (program / "app_runtime_243.pyw", program / "app_runtime.pyw")
    backups = {
        path: path.read_bytes() if path.is_file() else None
        for path in targets
    }
    marker = program / MARKER
    marker_before = marker.read_bytes() if marker.is_file() else None

    try:
        if not _matches(program / "app_runtime_243.pyw", BASE_RUNTIME_SHA256):
            source = program / "app_runtime.pyw"
            if not _matches(source, BASE_RUNTIME_SHA256):
                raise RuntimeError("Nelze zmrazit ověřený runtime 2.2.43.")
            _atomic_write(program / "app_runtime_243.pyw", source.read_bytes())

        _atomic_write(program / "app_runtime.pyw", new_runtime)
        marker.write_text(VERSION, encoding="utf-8")

        if database_before is not None:
            if not database.is_file() or database.read_bytes() != database_before:
                raise RuntimeError("actions.sqlite3 se během aktualizace změnila.")

        if not _revision_ok(program):
            raise RuntimeError("Ověření runtime 2.2.44 po instalaci selhalo.")
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
    assert VERSION == "2.2.44"
    assert RUNTIME_LAYOUT == "28"
    assert len(BASE_COMMIT) == 40
    assert len(PAYLOAD_COMMIT) == 40
    assert len(BASE_SHA256) == 64
    assert len(BASE_RUNTIME_SHA256) == 64
    assert len(XT_PARSER_SHA256) == 64
    assert len(NEW_RUNTIME_SHA256) == 64
    assert "actions.sqlite3" not in (
        BASE_PATH,
        PAYLOADS["app_runtime.pyw"][1],
    )


if __name__ == "__main__":
    selftest()
