from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.6"
sys.path.insert(0, str(BASE))

import catalog_engine as engine
import bulk_import_engine as bulk

ROWS = [
    ("EGCOBOX   MXL20-V1-C50-h200-REI120-SW", 16),
    ("EGCOBOX   MXL20-V6±-C30-h200-REI120-SW", 10),
    ("EGCOBOX   MXL20-V6±-C50-h200-REI120-SW", 24),
    ("EGCOBOX   MXL20-VS-C30-h200-REI120-SW", 10),
    ("EGCOBOX   MXL20-VS-C50-h200-REI120-SW", 8),
    ("EGCOBOX   MXL20-VS-C50-h200-REI120-SW - 0,93m", 4),
    ("EGCOBOX   MXL25-V1-C50-h200-REI120-SW", 4),
    ("EGCOBOX   MXL25-VS-C30-h200-REI120-SW", 16),
    ("EGCOBOX   MXL25-VS-C50-h200-REI120-SW", 40),
    ("EGCOBOX   MXL25-VS-C50-h200-REI120-SW - 1m", 8),
    ("EGCOBOX   MXL25-WU280-VS-C30-h200-REI120-SW", 2),
    ("EGCOBOX   MXL35-VS-C30-h200-REI120-SW", 16),
    ("EGCOBOX   MXL50-V1-C30-h200-REI120-SW", 8),
    ("EGCOBOX   MXL50-V2-C50-h200-REI120-SW", 4),
    ("EGCOBOX   MXL50-V2-C50-h200-REI120-SW - 1m", 4),
    ("EGCOBOX VXL Z   48-K-C30-h160-REI120-SW", 8),
    ("EGCOBOX   VXL48-K-C30-h160-REI120-SW", 26),
]


def main() -> None:
    db = engine.CatalogDatabase(BASE / "catalogs")
    print("=== RELEVANT FAMILIES ===")
    for fam in db.families:
        label = " ".join(str(fam.get(k, "")) for k in ("manufacturer", "model", "type", "generation"))
        rec_designations = [str(r.get("designation", "")) for r in fam.get("records", [])]
        if any(x in label.upper() for x in ("MXL-WU", "VXL")) or any("VXL" in d.upper() for d in rec_designations):
            if fam.get("backend") == "matrix":
                moments = db.moment_classes(fam)
                print("MATRIX", label, "| moments=", moments[:30])
            else:
                print("RECORD", label, "| count=", len(rec_designations))
                for r in fam.get("records", []):
                    d = str(r.get("designation", ""))
                    aliases = [str(a) for a in (r.get("aliases") or [])]
                    if "VXL48" in d.upper() or any("VXL48" in a.upper() for a in aliases) or "VXL Z 48" in d.upper() or any("VXL Z 48" in a.upper() for a in aliases):
                        print("   designation=", d)
                        print("   aliases=", aliases)
                        print("   selectors=", {k: r.get(k) for k in ("moment_class", "shear_class", "cover", "height_mm", "concrete_min")})

    print("\n=== DIRECT SUGGESTIONS FOR VXL Z ===")
    for q in (
        "VXL Z 48-K-C30-h160",
        "EGCOBOX VXL Z 48-K-C30-h160-REI120-SW",
        "VXL48-K-C30-h160",
        "EGCOBOX VXL48-K-C30-h160-REI120-SW",
    ):
        values = bulk.dedupe_suggestions(db.suggest_designations(q, preferred_concrete="C25/30", limit=100))
        print(q, "=>", len(values), [v.result.designation for v in values[:12]])

    print("\n=== CURRENT v0.6.6 ANALYSIS ===")
    text = "\n".join(f"{name}\t{qty}" for name, qty in ROWS)
    items, skipped = bulk.analyze_bulk_text(
        db, text, preferred_concrete="C25/30", existing_positions=[], start_position="P001", suggestion_limit=100
    )
    print("skipped", skipped)
    for item in items:
        resolved = item.result.designation if item.result else "-"
        print(f"{item.line_number:02d} | {item.status:9s} | qty={item.quantity:3d} | {item.designation} | => {resolved}")
        print("     message:", item.message)
        if item.candidates:
            print("     candidates:", len(item.candidates), [c.result.designation for c in item.candidates[:8]])
            print("     varying:", item.varying_keys)


if __name__ == "__main__":
    main()
