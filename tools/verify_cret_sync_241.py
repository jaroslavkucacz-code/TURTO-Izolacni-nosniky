from __future__ import annotations
"""Regression checks for TURTO 2.2.41 CRET source VRd propagation."""

import ast
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / "updates" / "2.2.41"
CRET_UPDATE = ROOT / "updates" / "2.2.39"

EXPECTED = {
    "CRET 122 V": 96.3,
    "CRET 124": 122.9,
    "CRET 128": 167.2,
    "CRET 134": 238.9,
    "CRET 140": 353.4,
}

def _text(path: Path) -> str:
    value = path.read_text(encoding="utf-8")
    ast.parse(value, filename=str(path))
    return value

def main() -> None:
    overlay_text = _text(UPDATE / "shear_cret_sync_241.py")
    runtime_text = _text(UPDATE / "app_runtime.pyw")
    installer_text = _text(UPDATE / "runtime_installer.py")

    assert "stale_sync(owner)" in overlay_text
    assert "_repair_cret_rows(owner, only_decoder=True)" in overlay_text
    assert "stale_recalc(owner)" in overlay_text
    assert "_repair_cret_rows(owner)" in overlay_text
    assert "stale_add(owner)" in overlay_text
    assert 'getattr(owner, "_turto_substitution_237", None)' in overlay_text
    assert 'BASE_RUNTIME = PROGRAM / "app_runtime_240.pyw"' in runtime_text
    assert "shear_cret_sync_241.install(_base)" in runtime_text
    assert '"actions.sqlite3" not in PAYLOADS' in installer_text

    ns = runpy.run_path(str(UPDATE / "shear_cret_sync_241.py"), run_name="verify_cret_sync_241")
    ns["selftest"]()

    class Var:
        def get(self):
            return "Ancon"

    class Owner:
        shear_target_manufacturer_var = Var()
        shear_substitution_rows = [{
            "origin": "decoder",
            "source_designation": "CRET 140",
            "source": {"vrd": 347.0},
            "slab_mm": 350,
            "gap_mm": 20,
            "concrete": "C30/37",
        }]
        @staticmethod
        def _turto_substitution_237(row, target):
            data = dict(row)
            data["source"] = {"vrd": 353.4}
            data["target_manufacturer"] = target
            return data

    owner = Owner()
    original_cret_row = ns["_cret_row"]
    ns["_cret_row"] = lambda row: True
    try:
        changed = ns["_repair_cret_rows"](owner, only_decoder=True)
    finally:
        ns["_cret_row"] = original_cret_row
    assert changed == 1
    assert owner.shear_substitution_rows[0]["source"]["vrd"] == 353.4

    sys.path.insert(0, str(CRET_UPDATE))
    try:
        cret = runpy.run_path(str(CRET_UPDATE / "cret_series_100_239.py"), run_name="verify_cret_tables_241")
        for designation, expected in EXPECTED.items():
            cap, error = cret["capacity_for"](designation, 350, 20, "C30/37")
            assert cap is not None, (designation, error)
            assert abs(float(cap["vrd"]) - expected) < 1e-9, (designation, cap["vrd"], expected)
            assert cap["concrete_table"] == "C30/37"
    finally:
        try:
            sys.path.remove(str(CRET_UPDATE))
        except ValueError:
            pass

    print("TURTO 2.2.41 CRET source-VRd propagation checks: OK")

if __name__ == "__main__":
    main()
