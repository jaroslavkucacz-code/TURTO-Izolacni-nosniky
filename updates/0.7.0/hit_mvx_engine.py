from __future__ import annotations

import base64
import lzma
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

DATA_FILE = "leviat_hit_mvx_07_23.json.xz.b64"
RATIO_MIN_M = 0.15
TOL = 1e-9


class HitDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckResult:
    passes: bool
    in_scope: bool
    utilization: float | None
    allowed_v_kn_m: float | None
    ratio_m: float | None
    source_rounding_note: str | None = None


@dataclass(frozen=True)
class Candidate:
    designation: str
    alternatives: tuple[str, ...]
    series: str
    code: str
    length_mm: int
    height_mm: int
    cover_mm: int
    h_minus_cnom_mm: int
    concrete: str
    mrd1_knm_m: float
    vrd1_kn_m: float
    mrd2_knm_m: float
    vrd2_kn_m: float
    source_page: int
    check: CheckResult


def _decode_payload(path: Path) -> dict[str, Any]:
    try:
        encoded = path.read_bytes()
        raw = lzma.decompress(base64.b64decode(encoded, validate=True))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HitDataError(f"Nelze načíst databázi HIT: {exc}") from exc
    if payload.get("schema_version") != 1 or not isinstance(payload.get("records"), list):
        raise HitDataError("Databáze HIT má nepodporovaný formát.")
    return payload


@lru_cache(maxsize=4)
def load_payload(path_text: str) -> dict[str, Any]:
    return _decode_payload(Path(path_text))


def load_records(data_path: Path) -> list[dict[str, Any]]:
    return list(load_payload(str(data_path.resolve()))["records"])


def _effective_points(record: dict[str, Any]) -> tuple[float, float, float, float, str | None]:
    m1 = abs(float(record["mrd1_knm_m"]))
    v1 = abs(float(record["vrd1_kn_m"]))
    m2 = abs(float(record["mrd2_knm_m"]))
    v2 = abs(float(record["vrd2_kn_m"]))
    note = None

    # V jednom místě zdrojové tabulky (SP MVX-0508, h-cnom 270, C25/30)
    # je MRd,2 o 0,1 kNm/m nižší než MRd,1 při shodném VRd. Graf na str. 3
    # předpokládá pořadí bilančních bodů zleva doprava. Pokud je smyk shodný a
    # rozdíl momentu je jen zaokrouhlovací, bereme společnou vodorovnou hranu do
    # větší z obou uvedených momentových hodnot. Zdrojové hodnoty zůstávají v UI.
    if m2 + TOL < m1:
        if abs(v2 - v1) <= 1e-6 and (m1 - m2) <= 0.11:
            m2 = m1
            note = "Zdrojová tabulka obsahuje zaokrouhlovací nesoulad MRd,1/MRd,2; obálka je normalizována na společnou vodorovnou hranu."
        else:
            note = "Zdrojová tabulka má neobvyklé pořadí bilančních bodů; výsledek vyžaduje ruční kontrolu."
    return m1, v1, m2, v2, note


def allowed_v_at_m(record: dict[str, Any], m_abs: float) -> tuple[float | None, str | None]:
    m1, v1, m2, v2, note = _effective_points(record)
    m = max(0.0, float(m_abs))
    if m <= m1 + TOL:
        return v1, note
    if m > m2 + TOL:
        return None, note
    if m2 <= m1 + TOL:
        return min(v1, v2), note
    t = (m - m1) / (m2 - m1)
    return v1 + t * (v2 - v1), note


def _inside_envelope(record: dict[str, Any], m_abs: float, v_abs: float) -> bool:
    m = max(0.0, float(m_abs))
    v = max(0.0, float(v_abs))
    if m <= TOL and v <= TOL:
        return True
    if v > TOL and m / v < RATIO_MIN_M - 1e-12:
        return False
    allowed, _ = allowed_v_at_m(record, m)
    return allowed is not None and v <= allowed + 1e-8


def _radial_utilization(record: dict[str, Any], m_abs: float, v_abs: float) -> float | None:
    m = max(0.0, float(m_abs))
    v = max(0.0, float(v_abs))
    if m <= TOL and v <= TOL:
        return 0.0
    if v > TOL and m / v < RATIO_MIN_M - 1e-12:
        return None
    m1, v1, m2, _v2, _ = _effective_points(record)
    # Simple safe upper bound for scaling the current load ray.
    bounds = []
    if m > TOL:
        bounds.append(m2 / m if m2 > 0 else 0.0)
    if v > TOL:
        bounds.append(v1 / v if v1 > 0 else 0.0)
    hi = max(0.0, min(bounds) if bounds else 1.0)
    if hi <= TOL:
        return math.inf
    # hi is on or outside the conservative envelope; binary search the radial boundary.
    lo = 0.0
    # Numeric rounding can make the upper bound slightly inside. Expand a little, while respecting
    # that the envelope cannot exceed the M2/V1 rectangle.
    hi *= 1.0000005
    for _ in range(70):
        mid = (lo + hi) / 2.0
        if _inside_envelope(record, m * mid, v * mid):
            lo = mid
        else:
            hi = mid
    if lo <= TOL:
        return math.inf
    return 1.0 / lo


def check_record(record: dict[str, Any], m_ed_knm_m: float, v_ed_kn_m: float) -> CheckResult:
    m = abs(float(m_ed_knm_m))
    v = abs(float(v_ed_kn_m))
    ratio = None if v <= TOL else m / v
    if v > TOL and ratio is not None and ratio < RATIO_MIN_M - 1e-12:
        return CheckResult(False, False, None, None, ratio)
    allowed_v, note = allowed_v_at_m(record, m)
    passes = allowed_v is not None and v <= allowed_v + 1e-8
    util = _radial_utilization(record, m, v)
    return CheckResult(passes, True, util, allowed_v, ratio, note)


def _designation(template: str, height_mm: int, cover_mm: int) -> str:
    return template.replace("-hh-", f"-{height_mm:03d}-").replace("-cc", f"-{cover_mm:02d}")


def _variant_for_length(variants: Iterable[dict[str, Any]], preferred_length_mm: int | None) -> dict[str, Any]:
    variants = list(variants)
    if preferred_length_mm is not None:
        exact = [v for v in variants if int(v["length_mm"]) == int(preferred_length_mm)]
        if exact:
            return exact[0]
    # Default: prefer 1000 mm, otherwise the longest available variant.
    return sorted(variants, key=lambda v: (int(v["length_mm"]) != 1000, -int(v["length_mm"]), v["code"]))[0]


def available_h_minus_cnom(data_path: Path, series: str, concrete: str) -> list[int]:
    vals = {
        int(r["h_minus_cnom_mm"])
        for r in load_records(data_path)
        if r["series"] == series and r["concrete"] == concrete
    }
    return sorted(vals)


def propose(
    data_path: Path,
    *,
    series: str,
    height_mm: int,
    cover_mm: int,
    concrete: str,
    m_ed_knm_m: float,
    v_ed_kn_m: float,
    preferred_length_mm: int | None = None,
    include_failing: bool = False,
) -> list[Candidate]:
    series = series.upper().strip()
    h_eff = int(height_mm) - int(cover_mm)
    out: list[Candidate] = []
    for r in load_records(data_path):
        if r["series"] != series or r["concrete"] != concrete or int(r["h_minus_cnom_mm"]) != h_eff:
            continue
        variants = list(r["variants"])
        if preferred_length_mm is not None and not any(int(v["length_mm"]) == preferred_length_mm for v in variants):
            continue
        chosen = _variant_for_length(variants, preferred_length_mm)
        designation = _designation(str(chosen["template"]), int(height_mm), int(cover_mm))
        alternatives = tuple(
            _designation(str(v["template"]), int(height_mm), int(cover_mm))
            for v in variants
            if v is not chosen
        )
        check = check_record(r, m_ed_knm_m, v_ed_kn_m)
        if include_failing or check.passes:
            out.append(Candidate(
                designation=designation,
                alternatives=alternatives,
                series=series,
                code=str(chosen["code"]),
                length_mm=int(chosen["length_mm"]),
                height_mm=int(height_mm),
                cover_mm=int(cover_mm),
                h_minus_cnom_mm=h_eff,
                concrete=concrete,
                mrd1_knm_m=float(r["mrd1_knm_m"]),
                vrd1_kn_m=float(r["vrd1_kn_m"]),
                mrd2_knm_m=float(r["mrd2_knm_m"]),
                vrd2_kn_m=float(r["vrd2_kn_m"]),
                source_page=int(r["source_page"]),
                check=check,
            ))
    # Most structurally utilized passing solution first. Equivalent shorter variants are already grouped.
    def key(c: Candidate):
        u = c.check.utilization
        if c.check.passes:
            return (0, -(u if u is not None and math.isfinite(u) else -1.0), c.length_mm != 1000, c.code)
        return (1, (u if u is not None and math.isfinite(u) else 999.0), c.length_mm != 1000, c.code)
    out.sort(key=key)
    return out


def nearest_heights(data_path: Path, series: str, concrete: str, cover_mm: int, requested_height_mm: int, limit: int = 4) -> list[int]:
    hs = [x + int(cover_mm) for x in available_h_minus_cnom(data_path, series, concrete)]
    hs = sorted(set(hs), key=lambda x: (abs(x - int(requested_height_mm)), x))
    return sorted(hs[:limit])
