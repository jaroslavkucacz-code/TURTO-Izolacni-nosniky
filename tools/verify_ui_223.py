from __future__ import annotations

import hashlib
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.3"
FILES = (
    "isokorb_compat.py",
    "shear_autocomplete.py",
    "ui_help.py",
    "platform_workspace.py",
    "app_runtime.pyw",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for name in FILES:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Missing {path.relative_to(ROOT)}")
        print(f"SHA256 {name} {sha(path)}")

    for name in ("isokorb_compat.py", "shear_autocomplete.py", "ui_help.py"):
        module = runpy.run_path(str(RELEASE / name), run_name=f"verify_{name}")
        test = module.get("selftest")
        if callable(test):
            test()

    print("OK: TURTO 2.2.3 UI/Isokorb selftests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
