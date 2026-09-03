from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.7"
sys.path.insert(0, str(BASE))

import bulk_import_engine as bulk
import catalog_engine as engine

ROWS = [
    ("M+D   Nosný tepelně izolační prvek Schöck Isokorb T-ZL-EI120-H180-5.3", "kus", "86,000"),
    ("M+D   Nosný tepelně izolační prvek Schöck Sconnex W-N1-V1H1-B180-1.0", "kus", "2,000"),
    ("M+D   Nosný tepelně izolační prvek Schöck Isokorb T-QP-VV1-REI120-H200-L300-5.0", "kus", "2,000"),
    ("M+D   Nosný tepelně izolační prvekSchöck Isokorb   CXT-AP-MM1-VV1-REI30-LR200-B200-L300-1.0", "kus", "7,000"),
    ("M+D   Nosný tepelně izolační prvek Schöck Isokorb XT-KL-O-M3-V1-REI120-CV1-H250-7.2", "kus", "8,000"),
    ("M+D   Nosný tepelně izolační prvek Schöck Isokorb XT-KL-M6-V3-REI120-CV1-H250-6.2", "kus", "8,000"),
]


def core(text: str) -> str:
    x = re.sub(r"^\s*M\+D\s+", "", text, flags=re.I)
    x = re.sub(r"^Nosný\s+tepelně\s+izolační\s+prvek\s*", "", x, flags=re.I)
    return x.strip()


def main() -> None:
    db = engine.CatalogDatabase(BASE / "catalogs")

    print("=== RELEVANT FAMILIES ===")
    for fam in db.families:
        label = " | ".join(str(fam.get(k, "")) for k in ("manufacturer", "model", "type", "generation"))
        u = label.upper()
        if any(t in u for t in ("ZL", "SCONNEX", "CXT", "KL", "QP")):
            print(label, "records=", len(fam.get("records", [])), "backend=", fam.get("backend"))

    print("\n=== CURRENT 3-COLUMN BULK ANALYSIS ===")
    text = "\n".join("\t".join(row) for row in ROWS)
    items, skipped = bulk.analyze_bulk_text(
        db, text, preferred_concrete="C25/30", existing_positions=[], start_position="P001", suggestion_limit=100
    )
    print("skipped", skipped, "items", len(items))
    for item in items:
        print(item.line_number, item.status, "qty=", item.quantity, "designation=", item.designation, "note=", item.note)
        print(" message=", item.message)

    print("\n=== SUGGESTIONS FOR EXTRACTED DESCRIPTION ===")
    for i, (description, unit, qty) in enumerate(ROWS, start=1):
        query = core(description)
        print(f"\n{i:02d} CORE: {query}")
        for preferred in ("C25/30", None):
            suggestions = db.suggest_designations(query, preferred_concrete=preferred, limit=20)
            print(" preferred=", preferred, "count=", len(suggestions))
            for s in suggestions[:10]:
                r = s.result
                print("  ", s.score, r.designation, "|", r.family.get("manufacturer"), r.family.get("model"), r.family.get("type"), "|", {k:r.record.get(k) for k in ("moment_class","shear_class","concrete_min","cover","height_mm")})

        # Zkus také bez posledního desetinného obchodního/rozpočtového kódu.
        stripped = re.sub(r"-\d+[.,]\d+\s*$", "", query)
        if stripped != query:
            suggestions = db.suggest_designations(stripped, preferred_concrete="C25/30", limit=20)
            print(" stripped suffix:", stripped, "count=", len(suggestions))
            for s in suggestions[:10]:
                print("  ", s.score, s.result.designation, "|", s.result.family.get("model"), s.result.family.get("type"))


if __name__ == "__main__":
    main()
