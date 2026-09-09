from __future__ import annotations

import hashlib
import py_compile
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.8"
FILES = (
    "pdf_scope.py",
    "ui_cleanup_228.py",
    "platform_workspace.py",
    "app_runtime.pyw",
    "RELEASE_NOTES.txt",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for name in FILES:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        print(f"SHA256 {name} {sha(path)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    scope = runpy.run_path(str(RELEASE / "pdf_scope.py"), run_name="verify_pdf_scope_228")
    scope["selftest"]()
    ids = {item.id for item in scope["SCOPES"]}
    expected = {
        "all",
        "iso.all", "iso.decoder", "iso.design", "iso.substitution",
        "shear.all", "shear.decoder", "shear.design", "shear.substitution",
    }
    assert ids == expected

    cleanup = (RELEASE / "ui_cleanup_228.py").read_text(encoding="utf-8")
    for token in (
        "PDF je nadřazené produktovým oblastem",
        "Dekodér pracuje se všemi katalogy",
        "Export PDF…",
        "Ancon/Leviat:",
    ):
        assert token in cleanup, token

    platform = (RELEASE / "platform_workspace.py").read_text(encoding="utf-8")
    assert "export_pdf_dialog" in platform
    assert "apply_ui_cleanup_228" in platform

    notes = (RELEASE / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    assert "Smykové trny → Záměny" in notes
    assert "Dekodér / Návrh / Záměny" in notes
    print("OK: TURTO 2.2.8 – selectable PDF scope and workspace cleanup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
