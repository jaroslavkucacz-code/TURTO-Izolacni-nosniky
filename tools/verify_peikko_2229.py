from __future__ import annotations

"""Real-world Peikko decoding / central row contract regression tests."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.29"
sys.path[:0] = [str(RELEASE), str(ROOT / "updates/1.1.17")]
from peikko_thermal_breaks import decode_peikko, normalize_bulk_text, functionally_compatible, compatible_models
from peikko_catalog import make_result, catalog_class, CATALOG_ID, BLOCK_REASON
from project_model import create_project_row, normalize_project_row, query_from_selection, row_status

SAMPLES = [
("e1", "EBEA-100 RS 4x10-2 Ds200 Dt200 SW80 L500 REI120 OQ"),
("e2", "EBEA-100 RS 5x10-4 Ds200 Dt200 SW80 L1000 REI120 OQ"),
("e3", "EBEA-100 RS 7x10-3 Ds200 Dt200 SW80 L1000 REI120 OQ"),
("e4", "EBEA-100 RS 7x10-6 Ds200 Dt200 SW80 L1000 REI120 OQ"),
("e5", "EBEA-100 RS 8x10-7 Ds200 Dt200 SW80 L1000 REI120 OQ"),
("e6", "EBEA-100 RS 10x14-3 Ds200 Dt200 SW80 L1000 REI120 OQ"),
("e7", "EBEA-700 VE1 1x8-2 Ds200 Dt200 SW80 L500 S11=370 REI120 OQ"),
("e8", "EBEA-700 VE1 3x8-4 Ds200 Dt200 SW80 L500 S11=370 REI120 OQ"),
("e9", "EBEA-700 VE1 4x10-3 Ds200 Dt200 SW80 L1000 S11=120 REI120 OQ"),
("e10", "EBEA-700 VE1 4x10-3 Ds200 Dt200 SW80 L1000 S11=370 REI120 OQ"),
("e11", "EBEA-700 VE1 5x10-4 Ds200 Dt200 SW80 L1000 S11=120 REI120 OQ"),
("e12", "GL0945_E12 EBEA-100-B2 VE1 12x10-5 Ds200 Dt200 SW80 L1000 S11=370 REI120"),
("e13", "EBEA-E100 RS 4x10-3 Ds200 Dt200 SW80 L500 REI120 OQ"),
("zs", "EBEA-ZS Ds200 Dt200 SW80 L1000 REI120"),
]


def pasted_samples():
    return "\n\n".join("|     |\n| --- |\n\n" + pos + "\n\n| |\n| --- |\n\n" +
                       text.replace(" Ds", "\n&#x20; Ds").replace("GL0945_E12 ", "GL0945\\_E12\n")
                       for pos, text in SAMPLES)


class Fallback:
    def resolve_designation(self, *args, **kwargs):
        return (args, kwargs)
    def query(self, **kwargs):
        return kwargs
    def suggest_designations(self, *args, **kwargs):
        return ["ordinary"]


class PeikkoTests(unittest.TestCase):
    def test_all_reference_fields(self):
        for pos, text in SAMPLES:
            with self.subTest(pos=pos):
                d = decode_peikko(text)
                self.assertIsNotNone(d)
                self.assertEqual((d.ds_mm, d.dt_mm, d.sw_mm), (200, 200, 80))
                self.assertEqual(d.fire_rating, "REI120")
                self.assertIsNone(d.cover_mm)
                self.assertEqual(d.length_mm, 500 if pos in {"e1", "e7", "e8", "e13"} else 1000)
                self.assertEqual(d.oq, pos not in {"e12", "zs"})
                self.assertFalse(d.unknown_text)
                self.assertEqual(d.configuration_key, decode_peikko(d.canonical).configuration_key)
        self.assertEqual(len({decode_peikko(s).configuration_key for _, s in SAMPLES}), 14)

    def test_reference_and_corner(self):
        d = decode_peikko(SAMPLES[11][1])
        self.assertEqual(d.position_reference, "GL0945_E12")
        self.assertNotIn("GL0945", d.canonical)
        self.assertEqual((d.variant, d.material, d.reinforcement), ("B2", "VE1", "12x10-5"))
        self.assertEqual(decode_peikko(SAMPLES[12][1]).model, "E-100")
        self.assertEqual(decode_peikko(SAMPLES[13][1]).reinforcement, "")

    def test_s11_separation(self):
        a, b = [decode_peikko(SAMPLES[i][1]) for i in (8, 9)]
        self.assertEqual((a.s11_mm, b.s11_mm), (120, 370))
        self.assertNotEqual(a.configuration_key, b.configuration_key)
        self.assertFalse(functionally_compatible(a, b))

    def test_normalized_variants(self):
        text = "EBEA–100 rs 4 × 10 – 2 Ds = 200 mm Dt200 SW = 80 L500 S11 = 370 REI 120 OQ"
        d = decode_peikko(text)
        self.assertEqual((d.material, d.reinforcement, d.s11_mm), ("RS", "4x10-2", 370))
        self.assertEqual(decode_peikko("ebea®-100 Ds200\u00a0Dt200").ds_mm, 200)

    def test_unknown_is_preserved(self):
        a = decode_peikko("EBEA-100 CUSTOM42 SW80")
        b = decode_peikko("EBEA-100 CUSTOM43 SW80")
        self.assertEqual(a.unknown_text, "CUSTOM42")
        self.assertIn("CUSTOM42", a.canonical)
        self.assertNotEqual(a.configuration_key, b.configuration_key)
        self.assertTrue(a.warnings)

    def test_missing_is_not_default_or_zero(self):
        d = decode_peikko("EBEA-100")
        for name in ("ds_mm", "dt_mm", "sw_mm", "length_mm", "cover_mm", "s11_mm"):
            self.assertIsNone(getattr(d, name))
        r = make_result("EBEA-100")
        self.assertEqual(r.moment_text, "—")
        self.assertEqual(r.shear_text, "—")
        self.assertIsNone(r.insulation_thickness_mm)
        self.assertEqual(r.record["height_mm"], "")

    def test_invalid_parameters(self):
        for bad in ("SW80 SW120", "Ds200 Ds220", "L0", "L-500", "S11=", "SW=", "Ds200.5",
                    "RS VE1", "4x10-2 5x10-3", "0x10-2", "L500junk", "SWnan"):
            with self.subTest(bad=bad):
                if bad == "SWnan":
                    self.assertIn(bad.upper(), decode_peikko("EBEA-100 " + bad).unknown_text)
                else:
                    with self.assertRaises(ValueError):
                        decode_peikko("EBEA-100 " + bad)

    def test_different_slabs_and_nonstandard_sw(self):
        d = decode_peikko("EBEA-100 Ds200 Dt240 SW100")
        self.assertEqual((d.ds_mm, d.dt_mm, d.sw_mm), (200, 240, 100))
        self.assertGreaterEqual(len(d.warnings), 2)

    def test_multi_product_rejected(self):
        with self.assertRaises(ValueError):
            decode_peikko("EBEA-100 Ds200 EBEA-700 Dt200")

    def test_bulk_multiline_and_markdown(self):
        lines = normalize_bulk_text(pasted_samples()).splitlines()
        self.assertEqual(len(lines), 14)
        for (expected_pos, expected), line in zip(SAMPLES, lines):
            pos, text = line.split("\t", 1)
            self.assertEqual(pos, expected_pos)
            self.assertEqual(decode_peikko(text).canonical, decode_peikko(expected).canonical)
        self.assertIn("GL0945_E12", lines[11])

    def test_bulk_mixed_quantities_and_notes(self):
        raw = "x1\t7\tHIT-HP MVX\tnote\ne9\t3\t" + SAMPLES[8][1] + "\nL500\nZ1\tother\n"
        # Conflicting dimensions remain explicit, so later decoding refuses them.
        text = normalize_bulk_text(raw)
        self.assertIn("x1\t7\tHIT-HP MVX\tnote", text)
        self.assertIn("e9\t3\t", text)
        self.assertIn("L1000", text)
        self.assertIn("L500", text)
        self.assertEqual(normalize_bulk_text("A\t3\tHIT-HP MVX"), "A\t3\tHIT-HP MVX")

    def test_central_persistence_roundtrip(self):
        db = catalog_class(Fallback)()
        for pos, text in SAMPLES:
            with self.subTest(pos=pos):
                row = create_project_row(db.resolve_designation(text, preferred_concrete="C25/30"),
                    position=pos, quantity=7, source_text=text)
                restored = normalize_project_row(json.loads(json.dumps(row)))
                r = query_from_selection(db, restored["selection"])
                self.assertEqual(r.designation, decode_peikko(text).canonical)
                self.assertEqual(row["snapshot"], restored["snapshot"])
                self.assertEqual(row_status(db, restored)[0], "ok")
                self.assertEqual(restored["quantity"], 7)
                self.assertEqual(r.record["substitution_policy"], "manual")
                self.assertEqual(r.record["substitution_note"], BLOCK_REASON)
                self.assertTrue(all(item.get("kind") not in {"moment", "shear"} for item in r.results))

    def test_strict_explicit_concrete(self):
        db = catalog_class(Fallback)()
        raw = SAMPLES[0][1] + " C30/37"
        with self.assertRaises(ValueError):
            db.resolve_designation(raw, preferred_concrete="C25/30")
        self.assertEqual(db.suggest_designations(raw, preferred_concrete="C25/30"), [])
        self.assertEqual(len(db.suggest_designations(raw, preferred_concrete="C30/37")), 1)

    def test_original_catalog_delegation(self):
        db = catalog_class(Fallback)()
        self.assertEqual(db.resolve_designation("HIT-HP MVX")[0], ("HIT-HP MVX",))
        self.assertEqual(db.suggest_designations("Schöck K"), ["ordinary"])
        self.assertEqual(len(db.suggest_designations(SAMPLES[8][1])), 1)
        self.assertEqual(db.suggest_designations(SAMPLES[8][1], limit=0), [])

    def test_tebea_and_functional_guards(self):
        for model in ("CM-V", "CM-VV", "PVV-S", "V-W", "N", "EA", "EH", "ES"):
            self.assertEqual(decode_peikko("TEBEA " + model).model, model)
        self.assertFalse(functionally_compatible("EBEA-100", "TEBEA CM-V"))
        self.assertFalse(functionally_compatible("EBEA-100", "EBEA-E100"))
        self.assertFalse(functionally_compatible("EBEA-ZS", "EBEA-100"))
        self.assertEqual(compatible_models("TEBEA CM-V SW120 L1000"), ())
        self.assertEqual(len(compatible_models("TEBEA CM-V")), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
