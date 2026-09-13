from __future__ import annotations
"""Verified incremental 2.2.38 PDF-logo repair. Never write actions.sqlite3."""

import hashlib
import json
import os
from pathlib import Path
import runpy
import tempfile
import time
import urllib.request

VERSION = "2.2.38"
RUNTIME_LAYOUT = "22"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
PAYLOAD_COMMIT = "484101648ee22a2ea6ed1041a57cddbf08016a39"
BASE_COMMIT = "f05fb5e7ff584dde04bf105b7a6a3021506b949c"
BASE_INSTALLER_SHA256 = "a8e0008e43e43397dcaa7eacf6be4763c7af8bbcc4929f8cfd3113c4fcf977b1"
BASE_RUNTIME_SHA256 = "590f3d4e5595688a85dd3143b2fce05b1bbfb687833f919cff516625b325bf6f"
PAYLOADS = {
    "app_runtime.pyw": "99cd795fbd49ba790737e4ffe03c4e3cf2ae9f23caf12a71a879e7cbb8ee93ba",
    "pdf_logo_guard_238.py": "f2f7359197f025e51b69c513e9e307df2e01537eda69d3af30c13b863ddc3f67",
}
BASE_CRITICAL = {
    "app_runtime_236.pyw": "75e9b1899532d82a7c0562dedd7dfae0110ef616482195fd2f58d3a304fcb8d4",
    "app_runtime_234.pyw": "5576cdae794c9c8fd4f566573acb55bb5e687b5fbcc5c3f1fb521afc0cfcc883",
    "halfen_hsd_2026.py": "805f811bee2a8302c2c8ced979ecd2c26a3c92fbe6fd1024940a28dd98e617be",
    "shear_dowels_hsd_234.py": "299705a9091784ad88be8d38b6fdbdc69c1bc29d4baf813fb69030e1c11aadf7",
    "design_groups_restore.py": "8aa2b4507f96a8b34b2e79d266e9779732d1a38f29050f64b49a7ed75d00aea8",
    "app_runtime_235.pyw": "8e4c7e8b5ec4a56379e8fa7d1b44ac8a9c6bb8a4a94ac322c29ee1079d7b4290",
    "shear_workflow_236.py": "c96f573dafd7893f36bf809d064135ecf56573157895f3051bc97d56a93df7f3",
    "shear_schedule_io_236.py": "5c21aec2b230c8e73d37cf0e3d2f2a27cb0efe42619bbcc618a56ae6051576f4",
    "hsd_windows_ocr.ps1": "b76a281f1b8eef02c7bbfc6aa4d4cc3c3f41b5abef814d49f526b9dff79babf3",
    "shear_substitution_237.py": "300a670ecda75411b05ebfc5ce7adb50c6ace07057824f53ee45d87963175346",
}
MARKER = ".turto_runtime_2_2_38.ok"


def _matches(path: Path, sha: str) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha


def _logo_valid(program: Path) -> bool:
    try:
        data = json.loads((program / "assets" / "turto_logo_vector.json").read_text(encoding="utf-8"))
        return data.get("width") == 942 and data.get("height") == 849 and bool(data.get("shapes"))
    except Exception:
        return False


def _base_ready(program: Path) -> bool:
    runtime_ok = any(
        _matches(program / name, BASE_RUNTIME_SHA256)
        for name in ("app_runtime.pyw", "app_runtime_237.pyw")
    )
    required = (
        "runtime_paths.py",
        "platform_workspace.py",
        "shear_dowels_ui_215.py",
        "shear_dowels_catalog.py",
        "unified_schedule.py",
    )
    return (
        runtime_ok
        and all(_matches(program / name, sha) for name, sha in BASE_CRITICAL.items())
        and all((program / name).is_file() for name in required)
    )


def _revision_ok(program: Path) -> bool:
    return (
        _base_ready(program)
        and _matches(program / "app_runtime_237.pyw", BASE_RUNTIME_SHA256)
        and all(_matches(program / name, sha) for name, sha in PAYLOADS.items())
        and _logo_valid(program)
        and (program / MARKER).is_file()
        and (program / MARKER).read_text(encoding="utf-8").strip() == VERSION
    )


def _download(commit: str, path: str, sha: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "TURTO-2.2.38", "Cache-Control": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest()
            if actual != sha:
                raise RuntimeError(f"Nesouhlasí kontrolní součet: {path} ({actual})")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(attempt + 1)
    raise RuntimeError(f"Stažení ověřeného souboru selhalo: {path}\n{last}")


def install_runtime(root) -> Path:
    root = Path(root).resolve()
    program = root / "Program"
    program.mkdir(parents=True, exist_ok=True)
    if _revision_ok(program):
        return program / "app_runtime.pyw"

    db = root / "actions.sqlite3"
    before = db.read_bytes() if db.exists() else None

    data = {
        name: _download(PAYLOAD_COMMIT, f"updates/{VERSION}/{name}", sha)
        for name, sha in PAYLOADS.items()
    }

    if not _base_ready(program):
        with tempfile.TemporaryDirectory(prefix="turto_2238_base_") as folder:
            base_installer = Path(folder) / "installer.py"
            base_installer.write_bytes(
                _download(
                    BASE_COMMIT,
                    "updates/2.2.37/runtime_installer.py",
                    BASE_INSTALLER_SHA256,
                )
            )
            runpy.run_path(str(base_installer))["install_runtime"](root)
    if not _base_ready(program):
        raise RuntimeError("Základ 2.2.37 se nepodařilo ověřit.")

    if not _matches(program / "app_runtime_237.pyw", BASE_RUNTIME_SHA256):
        source = program / "app_runtime.pyw"
        if not _matches(source, BASE_RUNTIME_SHA256):
            raise RuntimeError("Nelze zmrazit ověřený runtime 2.2.37 pro vrstvu 2.2.38.")
        data["app_runtime_237.pyw"] = source.read_bytes()

    backups = {
        name: (program / name).read_bytes() if (program / name).exists() else None
        for name in data
    }
    logo = program / "assets" / "turto_logo_vector.json"
    logo_before = logo.read_bytes() if logo.exists() else None
    marker = program / MARKER
    marker_before = marker.read_bytes() if marker.exists() else None

    try:
        for name, blob in data.items():
            fd, temp = tempfile.mkstemp(prefix=".pdf238_", dir=program)
            try:
                with os.fdopen(fd, "wb") as file:
                    file.write(blob)
                os.replace(temp, program / name)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)

        ensure_logo = runpy.run_path(str(program / "pdf_logo_guard_238.py"))["ensure_logo"]
        ensure_logo(program)

        if before is not None and db.read_bytes() != before:
            raise RuntimeError("Kontrola ochrany databáze selhala.")

        marker.write_text(VERSION, encoding="utf-8")
        if not _revision_ok(program):
            raise RuntimeError("Ověření runtime 2.2.38 selhalo.")
    except Exception:
        for name, blob in backups.items():
            path = program / name
            if blob is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(blob)
        if logo_before is None:
            logo.unlink(missing_ok=True)
        else:
            logo.parent.mkdir(parents=True, exist_ok=True)
            logo.write_bytes(logo_before)
        if marker_before is None:
            marker.unlink(missing_ok=True)
        else:
            marker.write_bytes(marker_before)
        raise

    return program / "app_runtime.pyw"


def selftest() -> None:
    assert VERSION == "2.2.38"
    assert RUNTIME_LAYOUT == "22"
    assert all(len(sha) == 64 for sha in PAYLOADS.values())
    assert all(len(sha) == 64 for sha in BASE_CRITICAL.values())
    assert "actions.sqlite3" not in PAYLOADS
    assert "pdf_logo_guard_238.py" in PAYLOADS


if __name__ == "__main__":
    selftest()
