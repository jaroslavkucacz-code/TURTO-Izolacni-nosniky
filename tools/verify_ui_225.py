from __future__ import annotations

import hashlib
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.5"
FILES = (
    "ui_layout.py",
    "platform_workspace.py",
    "app_runtime.pyw",
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

    text = (RELEASE / "ui_layout.py").read_text(encoding="utf-8")
    for token in (
        "Detail prvku",
        "Detail záměny",
        "Převést do Záměn",
        "Složka katalogů",
        "Kontrola katalogů",
        "Export PDF",
        "Kopírovat pro Excel",
        "Export Excel…",
        "<Double-1>",
        "<<TreeviewSelect>>",
        "<Delete>",
        "TableRowDetailDialog",
        "_normalize_iso_substitution",
        "_normalize_shear",
    ):
        assert token in text, token

    platform = (RELEASE / "platform_workspace.py").read_text(encoding="utf-8")
    assert "apply_ui_layout" in platform
    notes = (RELEASE / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    assert "Dvojklik" in notes and "Nápověda > Data a zdroje" in notes

    print("OK: TURTO 2.2.5 – hierarchie záložek, detail, aktivní stavy a úklid hlavičky")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
