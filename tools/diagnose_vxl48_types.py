from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / "updates" / "1.1.4"
sys.path.insert(0, str(UPDATE))

from bulk_import_engine import preprocess_bulk_designation
from catalog_engine import CatalogDatabase
from project_model import create_project_row
import substitution_workspace as sw


def main() -> None:
    db = CatalogDatabase(UPDATE / "catalogs")
    raws = [
        "EGCOBOX VXL Z 48-K-C30-h160-REI120-SW",
        "EGCOBOX VXL48-K-C30-h160-REI120-SW",
    ]
    for raw in raws:
        print("\n===", raw)
        clean, note = preprocess_bulk_designation(raw)
        print("CLEAN", clean)
        print("NOTE", note)
        try:
            result = db.resolve_designation(clean, preferred_concrete="C25/30")
        except Exception as exc:
            print("RESOLVE_ERROR", type(exc).__name__, exc)
            print("SUGGESTIONS")
            for suggestion in db.suggest_designations(clean, preferred_concrete="C25/30", limit=12):
                print(" -", suggestion.designation, suggestion.context_text, suggestion.values_text)
            continue
        print("RESOLVED", result.designation)
        print("FAMILY", {k: result.family.get(k) for k in ("manufacturer", "model", "type", "generation", "compression_transfer")})
        print("RECORD", {k: result.record.get(k) for k in ("moment_class", "shear_class", "concrete_min", "cover", "height_mm", "compression_transfer", "insulation_thickness_mm")})
        print("RESULTS", result.results)
        print("COMP", result.compression_transfer)
        row = create_project_row(result, position="P001", quantity=1, note=note, source_text=raw)
        meta = sw.source_metadata(row)
        actions, warnings = sw.source_element_actions(row)
        print("META", meta)
        print("ACTIONS", sw.action_values(actions))
        print("ACTION_WARNINGS", warnings)
        print("LENGTH_OPTIONS", sw._target_length_options(int(meta.get("source_length_mm") or 0), {100, 50, 33, 25}))
        print("TYPE_ORDER", sw.hit_type_order(actions, int(meta.get("target_cover_mm") or 0), str(meta.get("geometry_target", ""))))


if __name__ == "__main__":
    main()
