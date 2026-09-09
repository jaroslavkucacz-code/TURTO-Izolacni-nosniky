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
BASE_COMMIT = "ab46e7d2dd52f78e91ffaf640188810bc113ec01"
BASE_PATH = "updates/2.2.8/runtime_installer.py"
BASE_SHA256 = "1a181b981fe42864b8aa0f1cc366b3e5a4442377d471c9e4574644d7c5a585d2"
RUNTIME_LAYOUT = "2"
PAYLOADS = {
    "catalog_browser.py": ("8a1394d71d2ec40c1ebf90c7da265e6a82e680a4", "updates/2.2.9/catalog_browser.py", "6f9c2bd66dbf10b6f7ca62b6a4816495b37d3fe02de41dadc0fcd348a44f208b"),
    "ui_cleanup_229.py": ("0e637f0facebc1bd73cd1dfafd276755ce07f344", "updates/2.2.9/ui_cleanup_229.py", "d8515663254c7833a21872f8143176da7a3817c33bab9b241ab9423fcf8726b1"),
    "platform_workspace.py": ("6af1bd1f5a2cc3f3a1c47fa4fa66cc9983d0512b", "updates/2.2.9/platform_workspace.py", "0a29f6f5ffa3773c2f94be2b2f929cb325f913754e6d0e91d6c85b99a9066003"),
    "app_runtime.pyw": ("3b3b548c72697e94a543a826c2187f2b4f7f4c17", "updates/2.2.9/app_runtime.pyw", "fa220e0cd0aec18fd674456d2a9650983992f7253848ccdfd3c0316a845a8b06"),
    "pdf_scope.py": ("096f65c0b082c826980371ab77e6e4ddbae03082", "updates/2.2.9/pdf_scope.py", "68401d779f3bc97c9473a50c82c91db0c46faa7fc1d64c0b43e982a5d62a748c"),
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
