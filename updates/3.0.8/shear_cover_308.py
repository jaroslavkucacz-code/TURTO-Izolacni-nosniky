from __future__ import annotations

"""Extend the verified fixed HIT cover policy to Schöck T QP-VV 5.0.

Only the policy eligibility changes. The 3.0.2 wrappers still validate live
metadata, restrict targets to ZDX and preserve capacity, concrete, geometry,
length and pressure-bearing checks. Source CV stays unspecified; target
cnom=30 is the documented ZDX detail (HALFEN HIT 20.2-EN, p.77).
"""
from functools import wraps
import math
import re

import isokorb_families_304 as families
import shear_cover_302 as shear
import substitution_workspace as sub
from shear_cover_302 import _blank, _norm

VERSION = "3.0.8"


def t_qp_target_type(row, meta):
    """Resolve target cover only for a consistent T QP-VV 5.0 source."""
    selection = row.get("selection") or {}
    snapshot = row.get("snapshot") or {}
    if not isinstance(selection, dict) or not isinstance(snapshot, dict):
        return None
    source = str(row.get("source_text") or snapshot.get("designation", ""))
    parsed = families.parse(source)
    if (parsed is None or (parsed.model, parsed.family, parsed.fields["generation"]) != ("T", "QP", "5.0")
            or not re.fullmatch(r"VV(?:[1-9]|10)", parsed.fields["shear"])
            or parsed.fields["fire"] != "120"):
        return None
    if _norm(selection.get("manufacturer")) not in {"SCHOCK", "SCHOECK"}:
        return None
    model = re.sub(r"\s+TYP(?:E)?$", "", _norm(selection.get("model")))
    if (model != "T" or _norm(selection.get("type_name")) != parsed.family
            or _norm(selection.get("generation")) != parsed.fields["generation"]):
        return None
    if (meta.get("source_cover_mm") is not None or meta.get("source_insulation_mm") != 80
            or meta.get("geometry_target") or meta.get("geometry_origin") == "invalid"):
        return None
    if (meta.get("source_height_mm") != int(parsed.fields["height"])
            or meta.get("source_length_mm") != int(parsed.fields["length"])):
        return None
    selected_shear = selection.get("shear_class")
    if _blank(selected_shear):
        selected_shear = selection.get("moment_class")
    if _norm(selected_shear) != parsed.fields["shear"]:
        return None
    # In the legacy catalogue, QP's selection.cover stores element length, not CV.
    raw_cover = selection.get("cover")
    if not _blank(raw_cover):
        length = re.fullmatch(r"L\s*=?\s*(\d+)\s*(?:MM)?", _norm(raw_cover))
        if length is None or str(int(length.group(1))) != parsed.fields.get("length"):
            return None
    for data in (selection, snapshot, (row.get("mapping") or {}).get("source_overrides") or {}):
        for key in ("source_cover_mm", "target_cover_mm", "cover_mm", "cnom", "cnom_mm", "concrete_cover_mm"):
            if not _blank(data.get(key)):
                return None
    # Never override a cover requirement deliberately supplied in a note.
    if re.search(r"(?<![A-Z])(?:CV|CNOM|C_NOM|KRYTI|COVER|C\s*=)", _norm(row.get("note"))):
        return None
    actions, warnings = sub.source_actions(row)
    values = sub.action_values(actions)
    if warnings or not all(math.isfinite(x) for x in values.values()):
        return None
    if any(values[k] > sub._TOL for k in ("m_pos", "m_neg", "n_pos", "n_neg")):
        return None
    # Do not let the legacy float parser silently discard malformed load values.
    for result in snapshot.get("results", []):
        if not isinstance(result, dict):
            return None
        if result.get("kind") not in {"moment", "normal", "shear"}:
            continue
        for key in ("value", "positive", "negative"):
            if result.get(key) not in (None, ""):
                try:
                    if not math.isfinite(float(str(result[key]).replace(",", "."))):
                        return None
                except (ValueError, TypeError):
                    return None
    if values["v_pos"] <= sub._TOL or values["v_neg"] <= sub._TOL:
        return None
    if meta.get("source_compression_category") != "bearing":
        return None
    return "ZDX"


def install(_base=None):
    if getattr(shear, "_turto_t_qp_308", False):
        return
    previous = shear.fixed_target_type

    @wraps(previous)
    def fixed_target_type(row, meta):
        return previous(row, meta) or t_qp_target_type(row, meta)

    shear.fixed_target_type = fixed_target_type
    shear._turto_t_qp_308 = True


def selftest():
    assert VERSION == "3.0.8"
    assert getattr(shear, "_turto_t_qp_308", False)
