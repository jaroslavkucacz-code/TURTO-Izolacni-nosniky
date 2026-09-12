from __future__ import annotations

"""Regression checks for Leviat/HALFEN HSD integration in TURTO 2.2.34."""

import hashlib
import py_compile
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.34"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeTree:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, str]] = {"0": {}}
        self.tags: dict[str, tuple[str, ...]] = {"0": ()}
        self.headings: dict[str, str] = {}
        self.tag_styles: dict[str, dict] = {}

    def heading(self, column: str, **kwargs):
        if "text" in kwargs:
            self.headings[column] = str(kwargs["text"])

    def tag_configure(self, tag: str, **kwargs):
        self.tag_styles[tag] = dict(kwargs)

    def exists(self, iid: str) -> bool:
        return iid in self.values

    def set(self, iid: str, column: str, value=None):
        if value is None:
            return self.values[iid].get(column, "")
        self.values[iid][column] = str(value)

    def item(self, iid: str, option=None, **kwargs):
        if option == "tags":
            return self.tags.get(iid, ())
        if "tags" in kwargs:
            self.tags[iid] = tuple(kwargs["tags"])
        return {"tags": self.tags.get(iid, ())}


def main() -> int:
    files = (
        "leviat_hsd.py", "hsd_decoder.py", "app_runtime.pyw",
        "runtime_installer.py", "app.pyw", "release_contract.json", "RELEASE_NOTES.txt",
    )
    for name in files:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        print(f"SHA256 {name} {sha(path)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    # Direct reviewed HSD dataset checks.
    sys.path.insert(0, str(ROOT / "updates" / "2.1.0"))
    sys.path.insert(0, str(ROOT / "updates" / "2.2.7"))
    sys.path.insert(0, str(RELEASE))

    data = runpy.run_path(str(RELEASE / "leviat_hsd.py"), run_name="verify_leviat_hsd_2234")
    data["selftest"]()
    decode = data["decode_hsd"]
    capacity = data["hsd_capacity"]

    assert decode("HSD-CRET 124")["family"] == "HSD-CRET"
    assert decode("HSD-CRET 124 V")["movement"] == "transverse"
    assert decode("HSD-CRET 150")["decoder_only"] is True
    assert decode("HSD-D 22-A4 + HSD-SV 22")["movement"] == "transverse"
    assert decode("HSD-D 22-FV + HSD-P 22")["socket"] == "P"
    assert decode("HSD-D 22-A4 + HSD-P 22")["decoder_only"] is True
    assert decode("HSD-F-CRET 124 V-30")["base_family"] == "HSD-F"

    row, error = capacity("HSD-CRET 124", slab_mm=280, gap_mm=30, concrete="C25/30")
    assert not error and row and row["vrd"] == 108.8
    row, error = capacity("HSD-CRET 124 V", slab_mm=280, gap_mm=30, concrete="C25/30")
    assert not error and row and row["vrd"] == 101.4
    row, error = capacity("HSD-CRET 124", slab_mm=270, gap_mm=15, concrete="C25/30")
    assert not error and row and row["slab_table_mm"] == 260 and row["gap_table_mm"] == 20 and row["vrd"] == 125.6
    row, error = capacity("HSD-CRET 124", slab_mm=280, gap_mm=30, concrete="C40/50")
    assert not error and row and row["concrete_table"] == "C25/30" and row["vrd"] == 108.8
    row, error = capacity("HSD-CRET 150", slab_mm=650, gap_mm=20, concrete="C25/30")
    assert row is None and "145/150/155" in error
    row, error = capacity("HSD-SET 22-A4", slab_mm=240, gap_mm=30, concrete="C25/30")
    assert not error and row and row["vrd"] == 9.3
    row, error = capacity("HSD-SET 30 V-A4", slab_mm=320, gap_mm=20, concrete="C25/30")
    assert not error and row and row["vrd"] == 24.7
    row, error = capacity("HSD-SET 20 V-A4", slab_mm=160, gap_mm=10, concrete="C25/30")
    assert row is None and error

    # Verify the adapter wraps the current catalogue without becoming a target engine.
    import shear_catalogs_227 as catalog
    targets_before = tuple(catalog.TARGET_MANUFACTURERS)
    import hsd_decoder
    hsd_decoder.install_catalog_hooks()
    assert tuple(catalog.TARGET_MANUFACTURERS) == targets_before == ("Ancon", "Schöck", "PohlCon", "MAX FRANK")
    info = catalog.decode_dowel("HSD-CRET 124 V")
    assert info and info["manufacturer"] == "Leviat" and info["movement"] == "transverse"
    candidate, error = catalog.capacity_from_designation(
        "HSD-CRET 124", slab_mm=280, gap_mm=30, concrete="C25/30", cover_mm=30,
    )
    assert not error and candidate and candidate.manufacturer == "Leviat" and candidate.vrd == 108.8
    assert "HSD-CRET" in catalog.catalog_summary()

    # Decoder rendering: reviewed VRd is visible, unpublished values stay explicit.
    owner = SimpleNamespace(
        colors={"accent": "accent", "text": "text", "danger": "danger"},
        shear_decoder_rows=[{
            "designation": "HSD-CRET 124 V", "slab_mm": 280.0, "gap_mm": 30.0,
            "concrete": "C25/30", "manufacturer": "", "family": "", "size": "",
            "movement": "axial",
        }],
        shear_decoder_tree=FakeTree(),
    )
    hsd_decoder._decorate_decoder(owner)
    assert owner.shear_decoder_rows[0]["manufacturer"] == "Leviat"
    assert owner.shear_decoder_rows[0]["hsd_vrd"] == 101.4
    assert owner.shear_decoder_tree.values["0"]["vrd"] == "101,4"
    assert "HSD EC 10-E" in owner.shear_decoder_tree.values["0"]["source"]

    owner2 = SimpleNamespace(
        colors=owner.colors,
        shear_decoder_rows=[{
            "designation": "HSD-CRET 150", "slab_mm": 650.0, "gap_mm": 20.0,
            "concrete": "C25/30", "manufacturer": "", "family": "", "size": "",
            "movement": "axial",
        }],
        shear_decoder_tree=FakeTree(),
    )
    hsd_decoder._decorate_decoder(owner2)
    assert owner2.shear_decoder_rows[0]["hsd_vrd"] is None
    assert owner2.shear_decoder_tree.values["0"]["vrd"] == "—"
    assert "na vyžádání" in owner2.shear_decoder_tree.values["0"]["source"]

    installer = (RELEASE / "runtime_installer.py").read_text(encoding="utf-8")
    bootstrap = (RELEASE / "app.pyw").read_text(encoding="utf-8")
    notes = (RELEASE / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    for token in ('"leviat_hsd.py"', '"hsd_decoder.py"', 'actions.sqlite3'):
        assert token in installer or token in notes, token
    assert "shear_autocomplete.py" not in installer
    assert "shear_autocomplete.py" not in bootstrap
    assert "Našeptávač" not in notes
    assert "HSD-CRET 145 / 150 / 155" in notes

    print("OK 2.2.34: Leviat/HALFEN HSD decoding, reviewed VRd tables, conservative lookup and decoder rendering.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
