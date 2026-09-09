from __future__ import annotations

"""TURTO 2.2.10 verified runtime overlay; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "dac31fb8d9ca17315117880e11e7a628584c311d"
BASE_PATH = "updates/2.2.9/runtime_installer.py"
BASE_SHA256 = "d7c94e58a21babb7df0bb2faab726980f43d8568e9f72fad38900d263388344c"
RUNTIME_LAYOUT = "3"
PAYLOADS = {
    "catalog_browser.py": ("c9daa88e1db075239113b431605cbe27aa13e99b", "updates/2.2.10/catalog_browser.py", "f84c5996914fc22e3af7c1d1c7947c35b5035fe1bacd4d60bba2016859b20bb7"),
    "platform_workspace.py": ("b00811bdc0f2cc23e717902ea1c5141b78e4800a", "updates/2.2.10/platform_workspace.py", "3a705fdcb0700177aa754c56ac4e520ab8be6d6ced12be7889f1fe5ae0ae1d0c"),
    "app_runtime.pyw": ("490939a20b317af0fb3826a4520e4adead27e1b6", "updates/2.2.10/app_runtime.pyw", "0871ba1aed8ee3a1b1b0cfe4226a26302bfc14c6b2c7e59e7f1afb7a10732a0d"),
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
    temp = Path(tempfile.mkdtemp(prefix="turto_2210_", dir=str(root)))
    try:
        base = temp / "base_installer.py"
        base.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.10-base"))
        namespace = runpy.run_path(str(base))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")
        install(root)

        staged: list[tuple[Path, Path]] = []
        for local, (commit, remote, expected) in PAYLOADS.items():
            source = temp / (local + ".new")
            source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.10-runtime"))
            staged.append((source, root / local))
        for source, target in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
