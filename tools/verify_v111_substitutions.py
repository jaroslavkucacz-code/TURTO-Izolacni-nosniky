from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "updates" / "1.1.1"
sys.path.insert(0, str(VERSION))

from bulk_import_engine import preprocess_bulk_designation
from catalog_engine import CatalogDatabase
from hit_core import HitDatabase, build_database_from_pdf
from project_model import create_project_row
from substitution_workspace import action_values, design_targets, source_actions, source_metadata

DOP_URL = "https://downloads.halfen.com/catalogues/de/media/declarationofperformance/reinforcementsystems/CONF-DOP_HIT-HP_SP_07-23-E.pdf"

EXAMPLES = [
    ("EGCOBOX MXL20-V1-C50-h200-REI120-SW", "HIT-SP MVX-0405-20-100-50"),
    ("EGCOBOX MXL20-V6±-C30-h200-REI120-SW", "HIT-SP MVX-0404-20-100-30"),
    ("EGCOBOX MXL20-V6±-C50-h200-REI120-SW", "HIT-SP MVX-0404-20-100-50"),
    ("EGCOBOX MXL20-VS-C30-h200-REI120-SW", "HIT-SP MVX-0404-20-100-30"),
    ("EGCOBOX MXL20-VS-C50-h200-REI120-SW", "HIT-SP MVX-0404-20-100-50"),
    ("EGCOBOX MXL20-VS-C50-h200-REI120-SW - 0,93m", "HIT-SP MVX-0404-20-100-50"),
    ("EGCOBOX MXL25-V1-C50-h200-REI120-SW", "HIT-SP MVX-0505-20-100-50"),
    ("EGCOBOX MXL25-VS-C30-h200-REI120-SW", "HIT-SP MVX-0504-20-100-30"),
    ("EGCOBOX MXL25-VS-C50-h200-REI120-SW", "HIT-SP MVX-0504-20-100-50"),
    ("EGCOBOX MXL25-VS-C50-h200-REI120-SW - 1m", "HIT-SP MVX-0504-20-100-50"),
    # Zdrojový katalog pro WU280 uvádí MRd = -32,1 kNm/element; 0504 má při
    # h=200/cnom=30 nedostatečný samostatný momentový limit, proto je 0604 bezpečná oprava tabulky.
    ("EGCOBOX MXL25-WU280-VS-C30-h200-REI120-SW", "HIT-SP MVX-0604-20-100-30-OU280"),
    ("EGCOBOX MXL35-VS-C30-h200-REI120-SW", "HIT-SP MVX-0704-20-100-30"),
    ("EGCOBOX MXL50-V1-C30-h200-REI120-SW", "HIT-SP MVX-0806-20-100-30"),
    ("EGCOBOX MXL50-V2-C50-h200-REI120-SW", "HIT-SP MVX-0807-20-100-50"),
    ("EGCOBOX MXL50-V2-C50-h200-REI120-SW - 1m", "HIT-SP MVX-0807-20-100-50"),
]


def main() -> None:
    cache = ROOT / ".verify-v111"
    cache.mkdir(exist_ok=True)
    pdf_path = cache / "CONF-DOP_HIT-HP_SP_07-23-E.pdf"
    database_path = cache / "hit_all_2023_v4.json.gz.b64"
    if not pdf_path.exists():
        urllib.request.urlretrieve(DOP_URL, pdf_path)
    if not database_path.exists():
        build_database_from_pdf(pdf_path, database_path)

    hit = HitDatabase(database_path)
    catalog = CatalogDatabase(VERSION / "catalogs")
    mismatches: list[str] = []
    for index, (raw, expected) in enumerate(EXAMPLES, start=1):
        lookup, note = preprocess_bulk_designation(raw)
        suggestions = catalog.suggest_designations(lookup, preferred_concrete="C25/30", limit=10)
        if not suggestions:
            raise AssertionError(f"{raw}: source catalog record not found after preprocessing: {lookup}")
        result = suggestions[0].result
        row = create_project_row(result, position=f"P{index:03d}", note=note, source_text=raw)
        actions, warnings = source_actions(row)
        if warnings:
            raise AssertionError(f"{raw}: source warnings: {warnings}")
        metadata = source_metadata(row)
        if metadata["errors"]:
            raise AssertionError(f"{raw}: metadata errors: {metadata['errors']}")
        targets, errors = design_targets(hit, actions, metadata=metadata)
        if not targets:
            raise AssertionError(f"{raw}: no target, errors={errors}")
        actual = str(targets[0]["designation"])
        print(
            f"{raw} -> {actual} | expected {expected} | eta={targets[0]['utilization'] * 100:.3f}% "
            f"| actions={action_values(actions)} | geometry={metadata.get('geometry_display','')}"
        )
        if actual != expected:
            print("  TOP ALTERNATIVES:")
            for target in targets[:10]:
                print(
                    f"    {target['designation']} | eta={target['utilization'] * 100:.3f}% "
                    f"| M={target.get('m_capacity')} V={target.get('v_capacity')}"
                )
            mismatches.append(f"{raw}: expected {expected}, got {actual}")
        assert targets[0]["cover_mm"] == metadata["source_cover_mm"]
        assert targets[0]["height_mm"] == metadata["source_height_mm"]
        assert targets[0]["series"] == metadata["target_series"]
    if mismatches:
        raise AssertionError("\n".join(mismatches))
    print(f"Verified {len(EXAMPLES)} Egcobox -> HIT substitutions")


if __name__ == "__main__":
    main()
