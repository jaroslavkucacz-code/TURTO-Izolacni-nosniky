from __future__ import annotations

"""Regression checks for the finalized Leviat/HALFEN HSD decoder release 2.2.35."""

import hashlib
import py_compile
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RELEASE = ROOT / "updates" / "2.2.34"
RELEASE = ROOT / "updates" / "2.2.35"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for path in (
        DATA_RELEASE / "halfen_hsd_2026.py",
        DATA_RELEASE / "shear_dowels_hsd_234.py",
        RELEASE / "app_runtime.pyw",
        RELEASE / "runtime_installer.py",
        RELEASE / "app.pyw",
        RELEASE / "release_contract.json",
        RELEASE / "RELEASE_NOTES.txt",
    ):
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        print(f"SHA256 {path.relative_to(ROOT)} {sha(path)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    sys.path.insert(0, str(DATA_RELEASE))
    data = runpy.run_path(str(DATA_RELEASE / "halfen_hsd_2026.py"), run_name="verify_hsd_data_2235")
    data["selftest"]()
    decode = data["decode_designation"]
    capacity = data["capacity_for"]

    # Decoder coverage – heavy complete systems, single complete SETs and components.
    assert decode("HSD-CRET 124")["movement"] == "axial"
    assert decode("HSD-CRET-124 V")["movement"] == "transverse"
    assert decode("HSD-CRET 145")["hmin_mm"] == 420
    assert decode("HSD-CRET 150 V")["hmin_mm"] == 600
    assert decode("HSD-CRET 155")["hmin_mm"] == 650
    assert decode("HSD-SET 22-A4")["family"] == "HSD-SET"
    assert decode("HSD-SET 22 V-A4")["family"] == "HSD-SET V"
    assert decode("HSD-D 22-A4")["component_only"] is True
    assert decode("HSD-S 22")["component_only"] is True
    assert decode("HSD-SV 22")["movement"] == "transverse"
    assert decode("HSD-P 22")["movement"] == "axial"

    # Exact anchors copied from HSD EC 10-E tables, deliberately without interpolation.
    row, error = capacity("HSD-CRET 124", 280, 30, "C25/30")
    assert not error and row and row["vrd"] == 108.8
    row, error = capacity("HSD-CRET 124 V", 280, 30, "C25/30")
    assert not error and row and row["vrd"] == 101.4
    row, error = capacity("HSD-CRET 122", 200, 10, "C20/25")
    assert not error and row and row["vrd"] == 61.3
    row, error = capacity("HSD-CRET 140 V", 400, 60, "C25/30")
    assert not error and row and row["vrd"] == 240.0

    # Conservative lookup: slab thickness rounds down, joint width rounds up.
    row, error = capacity("HSD-CRET 124", 270, 15, "C25/30")
    assert not error and row
    assert row["slab_table_mm"] == 260 and row["gap_table_mm"] == 20
    assert row["vrd"] == 125.6

    # Catalogue explicitly says C30/37 and higher use the C25/30 table.
    row, error = capacity("HSD-CRET 124", 280, 30, "C40/50")
    assert not error and row
    assert row["concrete_table"] == "C25/30" and row["vrd"] == 108.8

    # HSD-CRET 145/150/155 are decoded, but no resistance is fabricated.
    for size, h in ((145, 420), (150, 600), (155, 650)):
        row, error = capacity(f"HSD-CRET {size}", h, 20, "C25/30")
        assert row is None and "vyžádání" in error
        row, error = capacity(f"HSD-CRET {size} V", h, 20, "C25/30")
        assert row is None and "vyžádání" in error

    # Single HSD-D complete sets: VRd = min(VRd,s; VRd,c), cnom = 30 mm.
    row, error = capacity("HSD-SET 22-A4", 240, 30, "C25/30")
    assert not error and row and row["vrd"] == 9.3
    row, error = capacity("HSD-SET 25 V-A4", 240, 30, "C25/30")
    assert not error and row and row["vrd"] == 11.8
    row, error = capacity("HSD-SET 30 V-A4", 320, 20, "C25/30")
    assert not error and row and row["vrd"] == 24.7

    # Blank concrete-table cells remain unavailable; component-only records get no system VRd.
    row, error = capacity("HSD-SET 20 V-A4", 160, 10, "C25/30")
    assert row is None and "První použitelná" in error
    row, error = capacity("HSD-D 22-A4", 200, 20, "C25/30")
    assert row is None and "komponenta" in error

    overlay = (DATA_RELEASE / "shear_dowels_hsd_234.py").read_text(encoding="utf-8")
    for token in (
        "original_build_decoder",
        "tree.heading(\"vrd\", text=\"VRd katalog [kN]\")",
        "Leviat/HALFEN HSD-CRET",
        "hsd_capacity",
        "component_only",
        "_turto_hsd_234_installed",
    ):
        assert token in overlay, token
    assert "main_notebook.add" not in overlay
    assert "main_notebook.insert" not in overlay

    installer = (RELEASE / "runtime_installer.py").read_text(encoding="utf-8")
    for token in (
        '"halfen_hsd_2026.py"',
        '"shear_dowels_hsd_234.py"',
        'HSD_DATA_SHA256',
        'HSD_UI_SHA256',
        'actions.sqlite3',
    ):
        assert token in installer, token

    contract = (RELEASE / "release_contract.json").read_text(encoding="utf-8")
    assert '"manifest_root_only": true' in contract
    assert '"actions.sqlite3"' in contract
    assert '"new_main_tab": false' in contract

    print(
        "OK 2.2.35: HSD-CRET/HSD-CRET V/HSD-SET/component decoding, exact VRd anchors, "
        "conservative table lookup, unavailable 145/150/155 resistance and Program-only release contract."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
