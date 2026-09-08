from __future__ import annotations

import hashlib
import py_compile
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.7"
BASE_SHEAR = ROOT / "updates" / "2.1.0"

FILES = (
    "shear_catalogs_227.py",
    "shear_ui_227.py",
    "ui_cleanup_227.py",
    "platform_workspace.py",
    "app_runtime.pyw",
    "runtime_installer.py",
    "app.pyw",
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

    sys.path.insert(0, str(BASE_SHEAR))
    sys.path.insert(0, str(RELEASE))
    module = runpy.run_path(str(RELEASE / "shear_catalogs_227.py"), run_name="verify_shear_catalogs_227")
    module["selftest"]()

    # Published-table anchors: intentionally exact to catch column shifts.
    hed = module["_hed_rows"](0.0, 200, 20, "C25/30", "axial", "stainless")
    hed25 = next(c for c in hed if c.size == "25")
    assert abs(hed25.vrd - 17.1) < 1e-9

    jdsdq = module["_jdsd_rows"](0.0, 240, 40, "C25/30", "transverse")
    j60 = next(c for c in jdsdq if c.size == "60 HF")
    assert abs(j60.vrd - 90.2) < 1e-9
    assert j60.status == "KONTROLA DESKY"

    mf = module["_egcodorn_rows"](0.0, 230, 60, "C25/30", "transverse")
    mf120 = next(c for c in mf if c.size == "120")
    assert abs(mf120.vrd - 100.5) < 1e-9

    dubel = module["_egcodubel_rows"](0.0, 220, 30, "C25/30", "transverse")
    d27 = next(c for c in dubel if c.size == "27")
    assert abs(d27.vrd - 50.5) < 1e-9
    assert d27.status == "KONTROLA DESKY"

    ui = (RELEASE / "shear_ui_227.py").read_text(encoding="utf-8")
    for token in (
        'TARGET_MANUFACTURERS',
        '"PohlCon"',
        '"MAX FRANK"',
        'Navržený trn',
        'design_manufacturer',
        'target_manufacturer',
        'Egcodorn® DND',
    ):
        assert token in ui, token

    cleanup = (RELEASE / "ui_cleanup_227.py").read_text(encoding="utf-8")
    assert "project_path_var" in cleanup
    assert "grid_rowconfigure(0, minsize=0)" in cleanup

    installer = (RELEASE / "runtime_installer.py").read_text(encoding="utf-8")
    for token in (
        '"shear_catalogs_227.py"',
        '"shear_ui_227.py"',
        '"ui_cleanup_227.py"',
        '"platform_workspace.py"',
        '"app_runtime.pyw"',
        'TURTO-2.2.7-runtime',
    ):
        assert token in installer, token

    bootstrap = (RELEASE / "app.pyw").read_text(encoding="utf-8")
    for token in (
        'VERSION = "2.2.7"',
        'INSTALLER_COMMIT = "bf3851ecbb791c5cfd2955c1493d9dd0d0f6aa4c"',
        'INSTALLER_SHA256 = "990362be0e27df55b3e20c233761cc1ea04a151af73c449cf5888d183866eace"',
        '"shear_catalogs_227.py"',
        '"shear_ui_227.py"',
        '"ui_cleanup_227.py"',
    ):
        assert token in bootstrap, token

    notes = (RELEASE / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    for token in ("HED", "JDSD", "Egcodorn", "Egcodubel", "KONTROLA DESKY"):
        assert token in notes, token

    print("OK: TURTO 2.2.7 – PohlCon/MAX FRANK shear-dowel catalogs and Decoder ISO cleanup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
