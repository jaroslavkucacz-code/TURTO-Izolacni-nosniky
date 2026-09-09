from __future__ import annotations

"""TURTO 2.2.9 verified runtime overlay; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "6d4eeb0ef380f959a742baeb124a43c8ee466f23"
BASE_PATH = "updates/2.2.8/runtime_installer.py"
BASE_SHA256 = "1a181b981fe42864b8aa0f1cc366b3e5a4442377d471c9e4574644d7c5a585d2"
RUNTIME_LAYOUT = "2"
PAYLOADS = {
    "app_runtime.pyw": ("ba54fcf13f6c2648326e7dbf437c3ee0cbdf6a7b", "updates/2.2.9/app_runtime.pyw", "90938857629e43bd09c9f85172aa9e359f73a07e38b6e37d2ca500993e7fa5ba"),
    "platform_workspace.py": ("2cb1648202b8ee73d502ac3ec01a5cc41a9846c0", "updates/2.2.9/platform_workspace.py", "0177b0b5983aa058932d0c7fa80a0c3bdb65a269d7322b15a8dbbc0ace336dd4"),
    "pdf_scope.py": ("ad72f505e63cde9cab52355a475809f5daa8ddd4", "updates/2.2.9/pdf_scope.py", "cec956fd55216827b7fb7fee9612c14d1e85f20580ce4e2d32d4ba4c3518e7ec"),
    "catalog_links_229.py": ("5801dfef66616a408cdb4fe827b4c8354f91152b", "updates/2.2.9/catalog_links_229.py", "8c78bb0cdd157a95492edf0bb618fed7070414087f720eda1bf96cf8154f387b"),
    "catalog_access_229.py": ("5f127aff5dab60b77496f5bd7fe3a793b912ffab", "updates/2.2.9/catalog_access_229.py", "b607eebc2e8b7f1bf59b8f4e13559b0fbd45b7922cfc136ae98068fc6bd883a0"),
}


def _url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def _download(commit: str, path: str, expected: str, agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                _url(commit, path) + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={"User-Agent": agent, "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=45) as response:
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


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    temp = Path(tempfile.mkdtemp(prefix="turto_229_", dir=str(root)))
    try:
        base = temp / "base_installer.py"
        base.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.9-base"))
        namespace = runpy.run_path(str(base))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")
        install(root)

        staged: list[tuple[Path, Path]] = []
        for local, (commit, remote, expected) in PAYLOADS.items():
            source = temp / (local + ".new")
            source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.9-runtime"))
            staged.append((source, root / local))
        for source, target in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
