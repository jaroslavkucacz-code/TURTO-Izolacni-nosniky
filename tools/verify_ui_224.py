from __future__ import annotations

import hashlib
import py_compile
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.4"
FILES = (
    "table_controls.py",
    "ui_consistency.py",
    "platform_workspace.py",
    "app_runtime.pyw",
    "RELEASE_NOTES.txt",
)

for stream in (sys.stdout, sys.stderr):
    try: stream.reconfigure(encoding="utf-8")
    except Exception: pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    sys.path.insert(0, str(RELEASE))
    for name in FILES:
        path = RELEASE / name
        if not path.is_file(): raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        print(f"SHA256 {name} {sha(path)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    for name in ("table_controls.py", "ui_consistency.py"):
        module = runpy.run_path(str(RELEASE / name), run_name=f"verify_{name}")
        test = module.get("selftest")
        if callable(test): test()

    tables = (RELEASE / "table_controls.py").read_text(encoding="utf-8")
    consistency = (RELEASE / "ui_consistency.py").read_text(encoding="utf-8")
    platform = (RELEASE / "platform_workspace.py").read_text(encoding="utf-8")
    for token in ("Nastavit všechny sloupce", "Skrýt tento sloupec", "Seřadit", "displaycolumns"):
        assert token in tables
    for token in ("Export CSV", "Aktualizovat z Dekodéru", "Aktualizovat katalog", "Otevřít zdroj", "Vymazat vše", "Export Excel…", "Sloupce…"):
        assert token in consistency
    assert "install_table_controls" in platform and "apply_ui_consistency" in platform

    print("OK: TURTO 2.2.4 – jednotné tabulky, tlačítka a workflow záložek")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
