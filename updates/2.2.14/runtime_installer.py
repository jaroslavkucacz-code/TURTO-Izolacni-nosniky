from __future__ import annotations

"""TURTO 2.2.14 runtime hotfix; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "22770186353228567423b5fbd619dce5c5b880d3"
BASE_PATH = "updates/2.2.13/runtime_installer.py"
BASE_SHA256 = "bc13cde76502e9fab19e02ce1e730f13b49e4d243faa6bc724fbba64c59eda48"
RUNTIME_LAYOUT = "7"
PROGRAM_REVISION = ".turto_runtime_2_2_14.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "65d93976b0c6dc4a4a91e66549134411aeb3be4f",
        "updates/2.2.14/app_runtime.pyw",
        "82427f2e52ef25275047f2a95558d25f180eb31ea1cc116fb4c2ea270d348637",
    ),
}


def _url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def _download(commit: str, path: str, expected: str, agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                _url(commit, path) + f"?turto={int(time.time()*1000)}_{attempt}",
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
                raise RuntimeError(f"SHA-256 nesouhlasí pro {path}: {actual}")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout {path}: {last}")


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    program = root / "Program"
    with tempfile.TemporaryDirectory(prefix="turto_2214_") as temp_name:
        temp = Path(temp_name)
        base = temp / "base_installer.py"
        base.write_bytes(
            _download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.14-base")
        )
        namespace = runpy.run_path(str(base))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")

        # Rebuild the already verified 2.2.13 Program layout first.
        install(root)

        if not program.is_dir():
            raise RuntimeError("Po obnově runtime chybí složka Program.")

        for local, (commit, remote, expected) in PAYLOADS.items():
            target = program / local
            staged = temp / (Path(local).name + ".new")
            staged.write_bytes(
                _download(commit, remote, expected, "TURTO-2.2.14-runtime")
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)

        (program / PROGRAM_REVISION).write_text("2.2.14", encoding="utf-8")


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
