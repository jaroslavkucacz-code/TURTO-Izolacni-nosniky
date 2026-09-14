from __future__ import annotations
"""TURTO 2.2.45 – family-aware Schöck Isokorb XT bulk candidate resolver."""

from collections import defaultdict
import re

import bulk_import_engine as _engine
from isokorb_xt_parser_243 import parse_xt_designation

VERSION = "2.2.45"

_RELEVANT = {
    "KL": ("manufacturer","model","type","generation","moment_class","shear_class","cover","height_mm","insulation"),
    "QL": ("manufacturer","model","type","generation","shear_class","height_mm","insulation"),
    "QP": ("manufacturer","model","type","generation","shear_class","height_mm","length_mm","insulation"),
    "QP-Z": ("manufacturer","model","type","generation","shear_class","height_mm","length_mm","insulation"),
    "ZL": ("manufacturer","model","type","generation","height_mm","insulation"),
}
_IRRELEVANT = {
    "QL": {"moment_class","cover","compression"},
    "QP": {"moment_class","cover","compression"},
    "QP-Z": {"moment_class","cover","compression"},
    "ZL": {"moment_class","shear_class","cover","compression"},
}

def _value(result, key: str) -> str:
    if key == "length_mm":
        for name in ("length_mm","length","element_length_mm","L_mm"):
            value = result.record.get(name, "")
            if value not in (None, ""):
                return str(value)
        return ""
    return str(_engine.selector_value(result, key) or "")

def _surface(result) -> str:
    values = [str(result.designation or "")]
    aliases = result.record.get("aliases", [])
    if isinstance(aliases, list):
        values.extend(map(str, aliases))
    values.extend(str(v) for v in result.family.values())
    return " | ".join(values).upper().replace("−","-").replace("–","-").replace("—","-")

def _family_match(result, family: str) -> bool:
    s = _surface(result)
    if family == "QP-Z":
        return bool(re.search(r"\bQP\s*-\s*Z(?:\s*-|\b)", s))
    if family == "QP":
        return bool(re.search(r"\bQP(?:\s*-|\b)", s)) and not re.search(r"\bQP\s*-\s*Z(?:\s*-|\b)", s)
    return bool(re.search(rf"\b{re.escape(family)}(?:\s*-|\b)", s))

def _token_match(result, token: str) -> bool:
    if not token:
        return True
    s = re.sub(r"\s+", "", _surface(result))
    t = token.upper().replace(",", ".")
    return bool(re.search(rf"(?<![A-Z0-9]){re.escape(t)}(?![A-Z0-9])", s))

def _height_ok(result, wanted: str) -> bool:
    if not wanted:
        return True
    try:
        h = int(wanted)
    except Exception:
        return True
    values = [_value(result,"height_mm"), _surface(result)]
    joined = " | ".join(values).upper().replace(" ", "")
    if re.search(rf"(?:H)?{h}(?!\d)", joined):
        return True
    for m in re.finditer(r"(?:≥|>=)(\d+)", joined):
        if h >= int(m.group(1)):
            return True
    for m in re.finditer(r"(?:≤|<=)(\d+)", joined):
        if h <= int(m.group(1)):
            return True
    nums = [int(x) for x in re.findall(r"\d+", _value(result,"height_mm"))]
    return not nums

def _candidate_matches(suggestion, parsed) -> bool:
    result = suggestion.result
    f = parsed.fields
    if not _family_match(result, parsed.family):
        return False
    checks = []
    if parsed.family == "KL":
        checks += ["M"+f.get("moment",""), f.get("shear",""), "CV"+f.get("cover",""), f.get("generation","")]
    elif parsed.family == "QL":
        checks += [f.get("shear",""), f.get("generation","")]
    elif parsed.family in {"QP","QP-Z"}:
        checks += [f.get("shear",""), "L"+f.get("length",""), f.get("generation","")]
    elif parsed.family == "ZL":
        checks += [f.get("generation","")]
    if any(token and not _token_match(result, token) for token in checks):
        return False
    return _height_ok(result, f.get("height",""))

def _identity(suggestion, parsed) -> tuple[str, ...]:
    r = suggestion.result
    # For these XT families the commercial designation is the product identity.
    # The catalogue may contain several statical rows for the same order type;
    # those rows must not be presented as different products.
    designation = _engine.normalize_designation_text(str(r.designation or ""))
    if designation:
        return ("designation", designation)
    return ("fields",) + tuple(_value(r, key).casefold() for key in _RELEVANT[parsed.family])

def _refine(candidates, parsed):
    matched = [x for x in candidates if _candidate_matches(x, parsed)]
    # Safety first: never infer from a failed family/token filter. This is
    # essential for KL-VV1, which must not silently collapse to KL-V1.
    if not matched:
        return list(candidates)
    groups = defaultdict(list)
    for item in matched:
        groups[_identity(item, parsed)].append(item)
    return [items[0] for items in groups.values()]

def _varying(candidates, parsed):
    allowed = set(_RELEVANT[parsed.family])
    keys = []
    for key in allowed:
        values = {_value(x.result, key) for x in candidates}
        if len(values) > 1:
            keys.append(key)
    return tuple(key for key, _label in _engine.SELECTOR_FIELDS if key in keys)

def install(_base=None) -> None:
    if getattr(_engine, "_turto_isokorb_xt_245", False):
        return
    original = _engine.analyze_bulk_text

    def analyze_bulk_text(database, text, **kwargs):
        items, skipped = original(database, text, **kwargs)
        for item in items:
            if item.status != "review" or not item.candidates:
                continue
            parsed = parse_xt_designation(item.designation)
            if parsed is None or parsed.family not in _RELEVANT:
                continue
            candidates = _refine(item.candidates, parsed)
            item.candidates = candidates
            if len(candidates) == 1:
                item.result = candidates[0].result
                item.varying_keys = ()
                item.status = "exact" if _engine.is_exact_designation(item.designation, item.result) else "unique"
                item.message = ("Úplné označení odpovídá právě jednomu katalogovému prvku."
                                if item.status == "exact" else
                                "Chybějící údaj byl jednoznačně doplněn z katalogu; neexistuje jiná platná varianta.")
            elif len(candidates) > 1:
                item.varying_keys = _varying(candidates, parsed)
                if item.varying_keys:
                    labels = ", ".join(_engine.SELECTOR_LABELS[k] for k in item.varying_keys)
                    item.message = f"Nutno upřesnit: {labels}."
                else:
                    item.message = "Nalezeno více skutečně odlišných katalogových možností; zvolte správnou variantu."
        return items, skipped

    _engine.analyze_bulk_text = analyze_bulk_text
    _engine._turto_isokorb_xt_245 = True

_REGRESSION = (
"KL-M3-V2-REI120-CV1-H240-6.2","KL-M3-V2-REI120-CV1-H250-6.2","KL-M3-VV1-REI120-CV1-H240-6.2",
"KL-M4-V2-REI120-CV1-H240-6.2","KL-M4-V2-REI120-CV1-H250-6.2","KL-M5-V2-REI120-CV1-H240-6.2",
"KL-M5-V2-REI120-CV1-H250-6.2","KL-M6-V2-REI120-CV1-H240-6.2","KL-M7-V1-REI120-CV1-H240-6.2",
"KL-M7-V2-REI120-CV1-H240-6.2","KL-M8-V1-REI120-CV1-H240-6.2","KL-M8-V1-REI120-CV1-H250-6.2",
"KL-M8-VV1-REI120-CV1-H240-6.2","QL-VV1-REI120-H240-6.0","QL-VV3-REI120-H240-6.0",
"QL-VV4-REI120-H240-6.0","QL-VV5-REI120-H240-6.0","QL-VV5-REI120-H250-6.0",
"QL-VV6-REI120-H240-6.0","QL-VV7-REI120-H240-6.0","QP-V10-REI120-H240-L500-5.0",
"QP-V1-REI120-H240-L300-5.0","QP-V2-REI120-H240-L400-5.0","QP-V3-REI120-H240-L500-5.0",
"QP-V5-REI120-H240-L400-5.0","QP-V7-REI120-H240-L400-5.0","QP-V7-REI120-H250-L400-5.0",
"QP-Z-V7-REI120-H240-L400-5.0","ZL-EI120-H240-5.3","ZL-EI120-H250-5.3",
)

def selftest() -> None:
    assert VERSION == "2.2.45"
    assert len(_REGRESSION) == 30 and len(set(_REGRESSION)) == 30
    parsed = [parse_xt_designation(x) for x in _REGRESSION]
    assert all(parsed)
    assert [x.family for x in parsed].count("KL") == 13
    assert [x.family for x in parsed].count("QL") == 7
    assert [x.family for x in parsed].count("QP") == 7
    assert [x.family for x in parsed].count("QP-Z") == 1
    assert [x.family for x in parsed].count("ZL") == 2
    assert "moment_class" not in _RELEVANT["QL"]
    assert "moment_class" not in _RELEVANT["QP"]
    assert "shear_class" not in _RELEVANT["ZL"]
