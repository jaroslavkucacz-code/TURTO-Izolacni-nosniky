from __future__ import annotations

"""1.1.25 HIT decoder suggestions including WT wall products."""

import re
from difflib import SequenceMatcher
from catalog_engine import DesignationSuggestion, natural_key
import hit_decoder_suggest_prev as _prev
from hit_decoder_suggest_prev import *  # noqa: F401,F403
from hit_decoder_records import compact, norm, wt_result


def query_type(raw: str) -> str:
    upper = norm(raw)
    if re.search(r"\bWT(?:-|\b)", upper):
        return "WT"
    return _prev.query_type(raw)


def _wt_suggestions(owner, text: str, preferred_concrete: str | None, limit: int):
    upper = norm(text)
    if "WT" not in upper:
        return []
    concrete = str(preferred_concrete or "C25/30")
    if concrete not in ("C20/25", "C25/30", "C30/37"):
        concrete = "C25/30"
    series_values = ["HP"] if "HP" in upper else (["SP"] if "SP" in upper else ["HP", "SP"])
    load = re.search(r"\bWT\s*-?\s*([1-7])\b", upper)
    loads = [int(load.group(1))] if load else list(range(1, 8))
    h = re.search(r"\b(?:H\s*=?\s*)?(1000|1250|1500|1750|2000|2250|2500|2750|3000|3250|3500)\b", upper)
    code_h = re.search(r"\bWT\s*-?\s*[1-7]\s*-\s*(100|125|150|175|200|225|250|275|300|325|350)\b", upper)
    heights = [int(h.group(1))] if h else ([int(code_h.group(1)) * 10] if code_h else [1500])
    b = re.search(r"\bB\s*=?\s*(150|160|170|180|190|200|210|220|230|240|250)\b", upper)
    code_b = re.search(r"\bWT\s*-?\s*[1-7]\s*-\s*\d{3}\s*-\s*(15|16|17|18|19|20|21|22|23|24|25)\b", upper)
    widths = [int(b.group(1))] if b else ([int(code_b.group(1)) * 10] if code_b else [150])
    q = compact(upper)
    out = []
    seen = set()
    for series in series_values:
        for load_range in loads:
            for height in heights:
                for width in widths:
                    try:
                        result = wt_result(series=series, load_range=load_range, wall_height_mm=height, width_mm=width, concrete=concrete)
                    except Exception:
                        continue
                    if result.designation in seen:
                        continue
                    seen.add(result.designation)
                    score = 95 + 95 * SequenceMatcher(None, q, compact(result.designation)).ratio()
                    if series in upper: score += 15
                    if load: score += 20
                    out.append(DesignationSuggestion(result, score, ()))
    out.sort(key=lambda item: (-item.score, natural_key(item.designation)))
    return out[:limit]


def hit_suggestions(owner, text: str, preferred_concrete: str | None, limit: int):
    try:
        exact = owner._parse_exact_hit(text, str(preferred_concrete or "C25/30"))
        if exact is not None:
            return [DesignationSuggestion(exact, 1200.0, ())]
    except Exception:
        pass
    wt = _wt_suggestions(owner, text, preferred_concrete, max(limit, 12))
    ordinary = _prev.hit_suggestions(owner, text, preferred_concrete, max(limit, 12))
    best = {}
    for item in [*wt, *ordinary]:
        key = compact(item.designation)
        if key not in best or item.score > best[key].score:
            best[key] = item
    return sorted(best.values(), key=lambda x: (-x.score, natural_key(x.designation)))[:limit]
