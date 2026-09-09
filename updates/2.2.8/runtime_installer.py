from __future__ import annotations

"""TURTO 2.2.8 verified runtime overlay; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "bf3851ecbb791c5cfd2955c1493d9dd0d0f6aa4c"
BASE_PATH = "updates/2.2.7/runtime_installer.py"
BASE_SHA256 = "990362be0e27df55b3e20c233761cc1ea04a151af73c449cf5888d183866eace"
RUNTIME_LAYOUT = "2"
PAYLOADS = {
    "app_runtime.pyw": ("7f6760dc8881fb920a3a5139d2658a187eadf048", "updates/2.2.8/app_runtime.pyw", "419d0aa0f3ea87db3ed417bf0eada0015d8ba9fbb204a59cdf0fce979365bda7"),
    "platform_workspace.py": ("fc9ff1e1724e09af3e39f9021c5a53a88ce043bf", "updates/2.2.8/platform_workspace.py", "186bcfe77c3c0da690d58593ec08ba4b2d4acedbdaa11da89a9864e92885dabd"),
    "pdf_scope.py": ("3fe84d29c85ca58806447e68f4c005aa1da2ed8c", "updates/2.2.8/pdf_scope.py", "79dde5a7485a1a6503a9d43ef07fb959c03f20268a6e2807484522530f006898"),
    "ui_cleanup_228.py": ("f52b69831fa6dbaf2f2c0fb3fc8f2fac00f34413", "updates/2.2.8/ui_cleanup_228.py", "f62874ba09baecd0a608d3f7556197c69cf1a6007c50e64e941e344b1a59824a"),
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
    temp = Path(tempfile.mkdtemp(prefix="turto_228_", dir=str(root)))
    try:
        base = temp / "base_installer.py"
        base.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.8-base"))
        namespace = runpy.run_path(str(base))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")
        install(root)

        staged: list[tuple[Path, Path]] = []
        for local, (commit, remote, expected) in PAYLOADS.items():
            source = temp / (local + ".new")
            source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.8-runtime"))
            staged.append((source, root / local))
        for source, target in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
