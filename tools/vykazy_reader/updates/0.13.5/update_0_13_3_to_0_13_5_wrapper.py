from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

PATCH_URL = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/e66674e774111a6a1623f050748c6eed3809be0e/tools/vykazy_reader/updates/0.13.5/update_0_13_3_to_0_13_5.py"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not (root / "app.py").exists():
        raise RuntimeError("Ve zvolené složce nebyl nalezen app.py.")
    req = urllib.request.Request(
        PATCH_URL,
        headers={
            "User-Agent": "TURTO-Vykazy-0135-Wrapper",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = response.read()
    fd, name = tempfile.mkstemp(prefix="turto_vykazy_0135_exact_", suffix=".py")
    os.close(fd)
    temp = Path(name)
    try:
        temp.write_bytes(payload)
        proc = subprocess.run(
            [sys.executable, str(temp), str(root)],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "neznámá chyba").strip()
            raise RuntimeError(detail)
    finally:
        try:
            temp.unlink()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
