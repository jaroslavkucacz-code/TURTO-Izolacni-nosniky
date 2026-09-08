from __future__ import annotations

import hashlib
import py_compile
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.6"
FILES = (
    "substitution_guard.py",
    "ui_visibility.py",
    "platform_workspace.py",
    "app_runtime.pyw",
    "runtime_installer.py",
    "RELEASE_NOTES.txt",
)

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    sys.path.insert(0, str(RELEASE))
    for name in FILES:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        print(f"SHA256 {name} {sha(path)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    for name in ("substitution_guard.py", "ui_visibility.py"):
        module = runpy.run_path(str(RELEASE / name), run_name=f"verify_{name}")
        test = module.get("selftest")
        if callable(test):
            test()

    guard = (RELEASE / "substitution_guard.py").read_text(encoding="utf-8")
    for token in (
        '"OU", "K-O"',
        '"OD", "K-U"',
        '"OU", "K-WO"',
        '"OD", "K-WU"',
        "required_bx",
        "geometry_origin",
        "unsupported",
        "CL|C",
        "K-ID",
        "-F",
        "w ≥ … mm",
        "unsafe_mapping",
    ):
        assert token in guard, token

    visibility = (RELEASE / "ui_visibility.py").read_text(encoding="utf-8")
    for token in (
        "Beton AKCE",
        "Použít na řádky",
        "Kontrola rozhraní",
        "ui_visibility.log",
        "winfo_ismapped",
    ):
        assert token in visibility, token

    installer = (RELEASE / "runtime_installer.py").read_text(encoding="utf-8")
    for token in ('"substitution_guard.py"', '"ui_visibility.py"', '"app_runtime.pyw"', '"platform_workspace.py"'):
        assert token in installer, token

    # The existing calculation engine must still keep its independent safety
    # checks. 2.2.6 adds geometry guards; it does not replace these controls.
    base = ROOT / "updates" / "1.1.17" / "substitution_workspace.py"
    base_text = base.read_text(encoding="utf-8")
    for token in (
        "_length_is_allowed",
        "_compression_compatible",
        "_component_ok",
        "source_element_actions",
        "substitution_policy",
        "target_series",
        "target_cover_mm",
        "target_height_mm",
        "target_concrete",
    ):
        assert token in base_text, token

    notes = (RELEASE / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    assert "KL-O" in notes and "MVX-OU" in notes and "skutečná tloušťka" in notes

    print("OK: TURTO 2.2.6 – geometrie záměn, KL-O/KL-U, bx a viditelnost UI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
