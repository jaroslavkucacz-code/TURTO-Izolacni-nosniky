from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / "updates" / "1.1.4"
sys.path.insert(0, str(UPDATE))

from bulk_import_engine import preprocess_bulk_designation
from catalog_engine import CatalogDatabase
from project_model import create_project_row
from hit_core import HitDatabase, build_database_from_pdf
import substitution_workspace as sw


def main() -> None:
    source_pdf = ROOT / "_diag_hit_dop.pdf"
    hit_data = ROOT / "_diag_hit_all_2023_v4.json.gz.b64"
    if not source_pdf.exists():
        raise RuntimeError(f"Missing downloaded DoP: {source_pdf}")
    build_database_from_pdf(source_pdf, hit_data)
    hit_db = HitDatabase(hit_data)
    print("HIT", hit_db.schema_version, "ZVX records", len(hit_db.zvx_records))

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

        targets, errors = sw.design_targets(
            hit_db,
            row=row,
            metadata=meta,
            allowed_length_codes={100, 50, 33, 25},
        )
        print("TARGET_COUNT", len(targets))
        for target in targets[:20]:
            print("TARGET", target["designation"], "L", target["length_mm"], "COMP", target["compression_text"], "ETA", target["utilization"], "Velem", target["v_capacity_element"])
        print("ERRORS", errors)

        for code, length in sw._target_length_options(int(meta.get("source_length_mm") or 0), {100, 50, 33, 25}):
            ta, _ = sw.source_actions(row, target_length_mm=length)
            candidates, error, _info = hit_db.proposal_candidates(
                "ZVX", meta["target_series"], meta["target_height_mm"], 30,
                meta["target_concrete"], ta, {code}, False, load_distance_x=0.0,
            )
            print("RAW_ZVX", length, "req", sw.action_values(ta), "count", len(candidates), "error", error)
            for candidate in candidates[:20]:
                print("  ", candidate.designation, candidate.code, candidate.v1, candidate.physical_length_mm, sw._candidate_compression_text(candidate), "okcomp", sw._compression_compatible(meta["source_compression_category"], candidate))


if __name__ == "__main__":
    main()
