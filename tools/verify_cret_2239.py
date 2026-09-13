from __future__ import annotations

"""Regression checks for TURTO 2.2.39 Aschwanden CRET 05/2026."""

import hashlib
import json
import py_compile
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / "updates" / "2.2.39"
FILES = (
    "cret_series_100_239.py",
    "cret_series_100_239_data1.py",
    "cret_series_100_239_data2.py",
    "cret_series_100_239_data3.py",
    "cret_series_100_239_data4.py",
    "shear_cret_239.py",
    "app_runtime.pyw",
    "runtime_installer.py",
    "app.pyw",
    "RELEASE_NOTES.txt",
    "release_contract.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def main() -> None:
    for name in FILES:
        assert (UPDATE / name).is_file(), f"missing 2.2.39 payload: {name}"

    for name in (
        "cret_series_100_239.py",
        "cret_series_100_239_data1.py",
        "cret_series_100_239_data2.py",
        "cret_series_100_239_data3.py",
        "cret_series_100_239_data4.py",
        "shear_cret_239.py",
        "app_runtime.pyw",
        "runtime_installer.py",
        "app.pyw",
    ):
        py_compile.compile(str(UPDATE / name), doraise=True)

    sys.path.insert(0, str(UPDATE))
    import cret_series_100_239 as cret
    import shear_cret_239 as overlay

    cret.selftest()
    overlay.selftest()

    row_count = sum(
        len(gaps)
        for heights in cret.TABLE.values()
        for gaps in heights.values()
    )
    assert row_count == 781, row_count
    assert tuple(cret.SIZE_ORDER) == ("122", "124", "128", "134", "140", "145", "150", "155")
    assert cret.CATALOG_EDITION == "CHD | CHF PDF 05/26"

    checks = (
        ("CRET-122", 220, 20, "C30/37", 96.3),
        ("CRET-145", 420, 20, "C30/37", 449.7),
        ("CRET-150", 600, 20, "C25/30", 575.4),
        ("CRET-155", 780, 10, "C25/30", 758.2),
    )
    for designation, h, gap, concrete, expected in checks:
        value, error = cret.capacity_for(designation, h, gap, concrete)
        assert not error and value, (designation, error)
        assert abs(float(value["vrd"]) - expected) < 1e-9, (designation, value["vrd"], expected)

    value, error = cret.capacity_for("CRET-122", 220, 20, "C35/45")
    assert value is None and "C25/30 a C30/37" in error

    info = cret.decode_designation("CRET 145 V42")
    assert info and info["manufacturer"] == "Leviat / Aschwanden"
    assert info["movement"] == "transverse"
    assert cret.decode_designation("HSD-CRET 145") is None

    info500 = cret.decode_designation("CRET-504A V20")
    assert info500 and info500["decoder_only"] is True
    value, error = cret.capacity_for(info500, 300, 20, "C30/37")
    assert value is None and "pouze v produktovém přehledu" in error

    candidates, error = cret.design_cret(
        ved=440, slab_mm=420, gap_mm=20, concrete="C30/37", movement="axial"
    )
    assert not error and candidates and candidates[0].designation == "CRET-145"

    candidates, error = cret.design_cret(
        ved=90, slab_mm=220, gap_mm=20, concrete="C30/37", movement="transverse"
    )
    assert not error and candidates and candidates[0].designation == "CRET-122 V25"

    text = (UPDATE / "shear_cret_239.py").read_text(encoding="utf-8")
    for marker in (
        "Aschwanden CRET",
        "ss237.evaluate",
        "design_cret",
        "_turto_cret_239",
    ):
        assert marker in text, marker

    core_text = (UPDATE / "cret_series_100_239.py").read_text(encoding="utf-8")
    assert "CRET Série 500" in core_text and "CRET Seismic" in core_text and "CRET Magnet" in core_text

    runtime = (UPDATE / "app_runtime.pyw").read_text(encoding="utf-8")
    assert 'APP_VERSION = "2.2.39"' in runtime
    assert 'BASE_RUNTIME = PROGRAM / "app_runtime_238.pyw"' in runtime
    assert "shear_cret_239.install(_base)" in runtime

    installer = runpy.run_path(str(UPDATE / "runtime_installer.py"), run_name="verify_installer_2239")
    installer["selftest"]()
    assert installer["VERSION"] == "2.2.39"
    assert installer["RUNTIME_LAYOUT"] == "23"
    assert "actions.sqlite3" not in installer["PAYLOADS"]
    assert set(installer["PAYLOADS"]) == {
        "app_runtime.pyw",
        "cret_series_100_239.py",
        "cret_series_100_239_data1.py",
        "cret_series_100_239_data2.py",
        "cret_series_100_239_data3.py",
        "cret_series_100_239_data4.py",
        "shear_cret_239.py",
    }
    for name, expected in installer["PAYLOADS"].items():
        assert sha(UPDATE / name) == expected, (name, sha(UPDATE / name), expected)

    app = runpy.run_path(str(UPDATE / "app.pyw"), run_name="verify_app_2239")
    app["selftest"]()
    assert app["VERSION"] == "2.2.39"
    assert app["RUNTIME_LAYOUT"] == "23"
    assert app["INSTALLER_SHA256"] == sha(UPDATE / "runtime_installer.py")

    contract = json.loads((UPDATE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["version"] == "2.2.39"
    assert contract["manifest_root_only"] is True
    assert contract["runtime_directory"] == "Program"
    assert contract["runtime_layout"] == "23"
    assert "actions.sqlite3" in contract["preserve"]

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2.2.39"
    assert str(manifest["runtime_layout"]) == "23"

    notes = (UPDATE / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    assert notes.startswith("TURTO 2.2.39")
    assert "05/2026" in notes and "HSD-CRET" in notes

    print("TURTO 2.2.39 CRET 05/2026: 781 exact table rows and integration checks OK")


if __name__ == "__main__":
    main()
