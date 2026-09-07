from __future__ import annotations

"""1.1.25 Decoder ISO extension for exact Leviat HIT-WT products."""

from typing import Any
from catalog_engine import QueryResult
import hit_decoder_records_prev as _prev
from hit_decoder_records_prev import *  # noqa: F401,F403
from hit_wt import SOURCE as WT_SOURCE, candidate_dict, design_wt


def wt_result(*, series: str, load_range: int, wall_height_mm: int, width_mm: int, concrete: str) -> QueryResult:
    series = str(series or "").strip().upper()
    load_range = int(load_range)
    wall_height_mm = int(wall_height_mm)
    width_mm = int(width_mm)
    # Ask the verified WT table for the selected load range by applying a tiny
    # non-zero action. This keeps all geometry/concrete validation in one place.
    rows, error = design_wt(
        series=series,
        wall_height_mm=wall_height_mm,
        width_mm=width_mm,
        concrete=concrete,
        med_neg=1e-6,
        ved_vertical=0.0,
        ved_horizontal=0.0,
    )
    if error and not rows:
        raise ValueError(error)
    row = next((item for item in rows if int(item.load_range) == load_range), None)
    if row is None:
        raise ValueError(f"HIT-{series} WT-{load_range} není pro zadanou geometrii katalogově dostupný.")
    data = candidate_dict(row)
    designation = row.designation
    page = int(row.page)
    results = [
        {"key": "m_rd", "label": "MRd", "kind": "moment", "value": float(row.mrd), "unit": "kNm/prvek"},
        {"key": "v_rd_vertical", "label": "VRd,v+", "kind": "shear", "value": float(row.vrd_vertical), "unit": "kN/prvek"},
        {"key": "v_rd_horizontal", "label": "VRd,h", "kind": "horizontal", "positive": float(row.vrd_horizontal), "negative": -float(row.vrd_horizontal), "unit": "kN/prvek"},
        {"key": "joint_spacing", "label": "s_joint max.", "kind": "other", "value": float(row.joint_spacing_m), "unit": "m"},
    ]
    catalog = {
        "id": HIT_CATALOG_ID,
        "manufacturer": "Leviat",
        "edition": "HALFEN HIT 20.2-EN 2023",
        "publication_label": "HIT-WT – wall connection",
        "publication_date": "2023-01-01",
        "source_filename": "HIT 20.2-EN",
    }
    family = {
        "catalog_id": HIT_CATALOG_ID,
        "manufacturer": "Leviat",
        "brand": "HIT",
        "model": f"HIT-{series}",
        "type": "WT",
        "generation": HIT_GENERATION,
        "source_pages": [page],
        "insulation_thickness_mm": 80 if series == "HP" else 120,
        "compression_transfer": "tlačené pruty",
    }
    record = {
        "moment_class": f"WT-{load_range}",
        "shear_class": f"B{width_mm}",
        "concrete_min": str(concrete),
        "cover": "—",
        "height_mm": str(wall_height_mm),
        "designation": designation,
        "aliases": [designation.replace("HIT-", "Leviat HIT-")],
        "results": results,
        "source_pages": [page],
        "insulation_thickness_mm": 80 if series == "HP" else 120,
        "compression_transfer": "tlačené pruty",
        "element_width_mm": width_mm,
        "wall_height_mm": wall_height_mm,
        "substitution_policy": "none",
        "substitution_note": "Prvek je již Leviat HIT; další záměna za HIT se neprovádí.",
        "notes": [
            f"{WT_SOURCE}; WT přenáší M−, kladný svislý smyk a vodorovný smyk ±. "
            "MRd závisí na výšce stěny; B = 150–250 mm."
        ],
        "wt": data,
    }
    family["records"] = [record]
    return QueryResult(catalog, family, record)
