from __future__ import annotations
"""Verified incremental TURTO 2.2.40 PDF-context update. Never write actions.sqlite3."""
import hashlib
import os
from pathlib import Path
import runpy
import tempfile
import time
import urllib.request

VERSION = "2.2.40"
RUNTIME_LAYOUT = "24"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
PAYLOAD_COMMIT = "d5506d8a43aaa36c61e6c7bc7ccced70f4927c8b"
BASE_COMMIT = "7bf86fd34a4dab31a56672863731a2367a446af0"
BASE_INSTALLER_SHA256 = "f857f1b1f860f1d655d57174741d38de747826691965acb9410b2b410559dae5"
BASE_RUNTIME_SHA256 = "6ef5e7799268b56c390156c9bc758481a9528e222442a19a61adb7a84efde5a7"
PAYLOADS = {
    "app_runtime.pyw": "d377f8d80711f734344be4744370453ac337d65ba774ac6eb5aeefd47ae66b05",
    "pdf_context_240.py": "1556963fc2261fa83e3943283e1ee0509aa73fd602ba60986038672c74caeba1",
}
MARKER = ".turto_runtime_2_2_40.ok"


def _matches(path: Path, sha: str) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest().lower() == sha


def _base_ready(program: Path) -> bool:
    runtime_ok = any(_matches(program / name, BASE_RUNTIME_SHA256) for name in ("app_runtime.pyw", "app_runtime_239.pyw"))
    required = ("runtime_paths.py", "platform_workspace.py", "hit_pdf.py", "pdf_scope.py", "shear_substitution_237.py")
    return runtime_ok and all((program / name).is_file() for name in required)


def _revision_ok(program: Path) -> bool:
    return (
        _base_ready(program)
        and _matches(program / "app_runtime_239.pyw", BASE_RUNTIME_SHA256)
        and all(_matches(program / name, sha) for name, sha in PAYLOADS.items())
        and (program / MARKER).is_file()
        and (program / MARKER).read_text(encoding="utf-8").strip() == VERSION
    )


def _download(commit: str, path: str, sha: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "TURTO-2.2.40", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
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
    data = {name: _download(PAYLOAD_COMMIT, f"updates/{VERSION}/{name}", sha) for name, sha in PAYLOADS.items()}

    if not _base_ready(program):
        with tempfile.TemporaryDirectory(prefix="turto_2240_base_") as folder:
            installer = Path(folder) / "installer.py"
            installer.write_bytes(_download(BASE_COMMIT, "updates/2.2.39/runtime_installer.py", BASE_INSTALLER_SHA256))
            runpy.run_path(str(installer))["install_runtime"](root)
    if not _base_ready(program):
        raise RuntimeError("Základ 2.2.39 se nepodařilo ověřit.")

    if not _matches(program / "app_runtime_239.pyw", BASE_RUNTIME_SHA256):
        source = program / "app_runtime.pyw"
        if not _matches(source, BASE_RUNTIME_SHA256):
            raise RuntimeError("Nelze zmrazit ověřený runtime 2.2.39 pro vrstvu 2.2.40.")
        data["app_runtime_239.pyw"] = source.read_bytes()

    backups = {name: (program / name).read_bytes() if (program / name).exists() else None for name in data}
    marker = program / MARKER
    marker_before = marker.read_bytes() if marker.exists() else None
    try:
        for name, blob in data.items():
            fd, temp = tempfile.mkstemp(prefix=".pdf240_", dir=program)
            try:
                with os.fdopen(fd, "wb") as file:
                    file.write(blob)
                os.replace(temp, program / name)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        if before is not None and db.read_bytes() != before:
            raise RuntimeError("Kontrola ochrany databáze selhala.")
        marker.write_text(VERSION, encoding="utf-8")
        if not _revision_ok(program):
            raise RuntimeError("Ověření runtime 2.2.40 selhalo.")
    except Exception:
        for name, blob in backups.items():
            path = program / name
            if blob is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(blob)
        if marker_before is None:
            marker.unlink(missing_ok=True)
        else:
            marker.write_bytes(marker_before)
        raise
    return program / "app_runtime.pyw"


def selftest() -> None:
    assert VERSION == "2.2.40" and RUNTIME_LAYOUT == "24"
    assert all(len(value) == 64 for value in PAYLOADS.values())
    assert len(BASE_INSTALLER_SHA256) == 64 and len(BASE_RUNTIME_SHA256) == 64
    assert "actions.sqlite3" not in PAYLOADS
    assert "pdf_context_240.py" in PAYLOADS


if __name__ == "__main__":
    selftest()
