from __future__ import annotations

"""TURTO 2.2.12 verified runtime overlay; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "d6403d48bd3562e968723d96e1de7f95afa04849"
BASE_PATH = "updates/2.2.11/runtime_installer.py"
BASE_SHA256 = "d56460b48d8d0d77e14b942aac23a3924e9a02c7f9a2541d97fcb7bc30b300ce"
RUNTIME_LAYOUT = "5"
PAYLOADS = {
    "app_runtime.pyw": ("34f3a859e9e86ea72fa889bc915ba9e1e08dee7c", "updates/2.2.12/app_runtime.pyw", "af75005a8b3b9f4c3e5b1567db2f4e0f440bc22246261e7317f0d12bc6410103"),
    "cleanup_stage1.py": ("fe369e16850af276ce83fbf6cd4f07c45ddc0a27", "updates/2.2.12/cleanup_stage1.py", "84d24d68433b5a7042b7278c681f18cad310cec9bf1a27e9a66be5ef223bfda2"),
    "cleanup_stage2.py": ("51427333931aa6faf30f910bc0aaf4c7daa4608f", "updates/2.2.12/cleanup_stage2.py", "9433e089866e9e5cc4b425d9edda7dcdd2bf7026195af6ba0d8d72cb027d926e"),
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
    temp = Path(tempfile.mkdtemp(prefix="turto_2212_", dir=str(root)))
    try:
        base = temp / "base_installer.py"
        base.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.12-base"))
        namespace = runpy.run_path(str(base))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")
        install(root)

        staged: list[tuple[Path, Path]] = []
        for local, (commit, remote, expected) in PAYLOADS.items():
            source = temp / (local + ".new")
            source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.12-runtime"))
            staged.append((source, root / local))
        for source, target in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
