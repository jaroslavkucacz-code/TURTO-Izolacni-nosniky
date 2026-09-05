from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "updates" / "1.1.0"
sys.path.insert(0, str(VERSION))

from catalog_engine import CatalogDatabase
from project_model import create_project_row
from substitution_workspace import action_values, source_actions

EXAMPLES = [
    "EGCOBOX MXL20-V1-C50-h200-REI120-SW",
    "EGCOBOX MXL20-V6±-C30-h200-REI120-SW",
    "EGCOBOX MXL20-V6±-C50-h200-REI120-SW",
    "EGCOBOX MXL20-VS-C30-h200-REI120-SW",
    "EGCOBOX MXL20-VS-C50-h200-REI120-SW",
    "EGCOBOX MXL25-V1-C50-h200-REI120-SW",
    "EGCOBOX MXL25-VS-C30-h200-REI120-SW",
    "EGCOBOX MXL25-VS-C50-h200-REI120-SW",
    "EGCOBOX MXL25-WU280-VS-C30-h200-REI120-SW",
    "EGCOBOX MXL35-VS-C30-h200-REI120-SW",
    "EGCOBOX MXL50-V1-C30-h200-REI120-SW",
    "EGCOBOX MXL50-V2-C50-h200-REI120-SW",
]


def main() -> None:
    db = CatalogDatabase(VERSION / "catalogs")
    print("catalogs", len(db.catalogs), "families", len(db.families))
    for index, text in enumerate(EXAMPLES, start=1):
        print("\n===", index, text)
        result = None
        try:
            result = db.resolve_designation(text, preferred_concrete="C25/30")
        except Exception as exc:
            print("RESOLVE_ERROR", type(exc).__name__, str(exc).split("\n", 1)[0])
            suggestions = db.suggest_designations(text, preferred_concrete="C25/30", limit=5)
            for s in suggestions:
                print("SUGGEST", s.designation, s.score)
            if suggestions:
                result = suggestions[0].result
                print("USING_FIRST_SUGGESTION")
        if result is None:
            continue
        print("RESOLVED", result.designation)
        print("FAMILY", json.dumps({k: result.family.get(k) for k in ("manufacturer", "model", "type", "generation", "backend", "insulation_thickness_mm", "compression_transfer")}, ensure_ascii=False))
        print("RECORD", json.dumps({k: result.record.get(k) for k in ("moment_class", "shear_class", "concrete_min", "cover", "height_mm", "insulation_thickness_mm", "compression_transfer", "source_pages")}, ensure_ascii=False))
        print("RESULTS", json.dumps(result.results, ensure_ascii=False))
        row = create_project_row(result, position=f"P{index:03d}")
        actions, warnings = source_actions(row)
        print("ACTIONS", json.dumps(action_values(actions), ensure_ascii=False))
        print("WARNINGS", json.dumps(warnings, ensure_ascii=False))


if __name__ == "__main__":
    main()
