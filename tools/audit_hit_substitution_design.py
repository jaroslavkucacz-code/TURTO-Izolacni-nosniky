from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "updates" / "1.1.0"
sys.path.insert(0, str(VERSION))

from catalog_engine import CatalogDatabase
from hit_core import DirectionalActions, HitDatabase, build_database_from_pdf

DOP_URL = "https://downloads.halfen.com/catalogues/de/media/declarationofperformance/reinforcementsystems/CONF-DOP_HIT-HP_SP_07-23-E.pdf"

EXAMPLES = [
    ("EGCOBOX MXL20-V1-C50-h200-REI120-SW", "HIT-SP MVX-0405-20-100-50"),
    ("EGCOBOX MXL20-V6±-C30-h200-REI120-SW", "HIT-SP MVX-0404-20-100-30"),
    ("EGCOBOX MXL20-V6±-C50-h200-REI120-SW", "HIT-SP MVX-0404-20-100-50"),
    ("EGCOBOX MXL20-VS-C30-h200-REI120-SW", "HIT-SP MVX-0404-20-100-30"),
    ("EGCOBOX MXL20-VS-C50-h200-REI120-SW", "HIT-SP MVX-0404-20-100-50"),
    ("EGCOBOX MXL25-V1-C50-h200-REI120-SW", "HIT-SP MVX-0505-20-100-50"),
    ("EGCOBOX MXL25-VS-C30-h200-REI120-SW", "HIT-SP MVX-0504-20-100-30"),
    ("EGCOBOX MXL25-VS-C50-h200-REI120-SW", "HIT-SP MVX-0504-20-100-50"),
    ("EGCOBOX MXL25-WU280-VS-C30-h200-REI120-SW", "HIT-SP MVX-0504-20-100-30-OU280"),
    ("EGCOBOX MXL35-VS-C30-h200-REI120-SW", "HIT-SP MVX-0704-20-100-30"),
    ("EGCOBOX MXL50-V1-C30-h200-REI120-SW", "HIT-SP MVX-0806-20-100-30"),
    ("EGCOBOX MXL50-V2-C50-h200-REI120-SW", "HIT-SP MVX-0807-20-100-50"),
]


def actions_from_result(result) -> DirectionalActions:
    values = dict(m_pos=0.0, m_neg=0.0, n_pos=0.0, n_neg=0.0, v_pos=0.0, v_neg=0.0)
    for item in result.results:
        kind = str(item.get("kind", "")).lower()
        prefix = {"moment": "m", "shear": "v", "normal": "n"}.get(kind)
        if not prefix:
            continue
        if item.get("positive") is not None:
            values[prefix + "_pos"] = max(values[prefix + "_pos"], abs(float(item["positive"])))
        if item.get("negative") is not None:
            values[prefix + "_neg"] = max(values[prefix + "_neg"], abs(float(item["negative"])))
        if item.get("value") is not None:
            value = float(item["value"])
            values[prefix + ("_neg" if value < 0 else "_pos")] = max(
                values[prefix + ("_neg" if value < 0 else "_pos")], abs(value)
            )
    return DirectionalActions(**values)


def main() -> None:
    cache = ROOT / ".audit-cache"
    cache.mkdir(exist_ok=True)
    pdf_path = cache / "CONF-DOP_HIT-HP_SP_07-23-E.pdf"
    db_path = cache / "hit_all_2023_v4.json.gz.b64"
    if not pdf_path.exists():
        print("Downloading DoP...")
        urllib.request.urlretrieve(DOP_URL, pdf_path)
    if not db_path.exists():
        print("Building HIT database...")
        build_database_from_pdf(pdf_path, db_path)
    hit = HitDatabase(db_path)
    catalog = CatalogDatabase(VERSION / "catalogs")

    for source_text, expected in EXAMPLES:
        suggestions = catalog.suggest_designations(source_text, preferred_concrete="C25/30", limit=3)
        print("\nSOURCE", source_text)
        if not suggestions:
            print("NO_SOURCE")
            continue
        result = suggestions[0].result
        actions = actions_from_result(result)
        cover = int(str(result.record.get("cover", "C35")).upper().replace("C", ""))
        height = int(result.record.get("height_mm", 0))
        series = "SP" if result.insulation_thickness_mm == 120 else "HP"
        candidates, error, info = hit.proposal_candidates(
            "MVX", series, height, cover, "C25/30", actions, {100}, True, load_distance_x=0.0
        )
        print("CANONICAL", result.designation)
        print("ACTIONS", json.dumps(actions.__dict__, ensure_ascii=False))
        print("SERIES/COVER/H", series, cover, height)
        print("ERROR", error)
        print("EXPECTED", expected)
        print("TOP")
        for candidate in candidates[:12]:
            print(candidate.designation, round(candidate.utilization * 100, 3), candidate.mode)
        exact = next((c for c in candidates if c.designation == expected), None)
        print("EXPECTED_IN_CANDIDATES", bool(exact), round(exact.utilization * 100, 3) if exact else None)


if __name__ == "__main__":
    main()
