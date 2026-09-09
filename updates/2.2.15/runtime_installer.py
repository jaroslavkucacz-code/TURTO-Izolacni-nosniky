from __future__ import annotations

"""TURTO 2.2.15 runtime cleanup installer; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "ec8623bc640e6a0a6f7ef5f0b12097552e16d426"
BASE_PATH = "updates/2.2.14/runtime_installer.py"
BASE_SHA256 = "82f9e03d6a49217ab6d09d3465d8615144e910ad3f897a4d926ad640aedd26ee"
RUNTIME_LAYOUT = "8"
PROGRAM_REVISION = ".turto_runtime_2_2_15.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "738725bec38cd4534b9111710ce4c4104bc4341f",
        "updates/2.2.15/app_runtime.pyw",
        "5f7aed6309655c00338864939b614a2c3d39b40890e9415afa13db0f6c8e94c7",
    ),
    "cleanup_stage4.py": (
        "0ae1ed661071fb2d1251b979c9565b89da6f5a84",
        "updates/2.2.15/cleanup_stage4.py",
        "caedad59ef6faac4ee1373381ee14b8c36255597974fb80a04a6f19b529e46c0",
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
    with tempfile.TemporaryDirectory(prefix="turto_2215_") as temp_name:
        temp = Path(temp_name)
        base = temp / "base_installer.py"
        base.write_bytes(
            _download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.15-base")
        )
        namespace = runpy.run_path(str(base))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")

        install(root)
        if not program.is_dir():
            raise RuntimeError("Po obnově runtime chybí složka Program.")

        for local, (commit, remote, expected) in PAYLOADS.items():
            target = program / local
            staged = temp / (Path(local).name + ".new")
            staged.write_bytes(
                _download(commit, remote, expected, "TURTO-2.2.15-runtime")
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)

        current_marker = program / PROGRAM_REVISION
        for old_marker in program.glob(".turto_runtime_*.ok"):
            if old_marker == current_marker:
                continue
            try:
                old_marker.unlink()
            except Exception:
                pass
        current_marker.write_text("2.2.15", encoding="utf-8")

        if not (program / "cleanup_stage4.py").is_file():
            raise RuntimeError("Runtime 2.2.15 neobsahuje cleanup_stage4.py.")


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
