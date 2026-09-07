"""Catalog-based HIT-HT1..HT3 checks for horizontal forces.

The 2023 HIT 20.2-EN catalogue gives HRd values in kN/element.
HT4/HT5 are intentionally not auto-selected here because the catalogue limits
their lifting-moment resistance to combinations with HIT-MVX; that coupled
check belongs in a dedicated design path.
"""
from __future__ import annotations

from typing import Any

from hit_core import Candidate, TOL

HIT_HT_SOURCE = "HALFEN HIT Insulated Connection ©2023, HIT 20.2-EN"
HT_WIDTH_MM = {"HP": 100, "SP": 150}
HT_WIDTH_CODE = {"HP": 10, "SP": 15}
HT_PAGE = {"HT1": 121, "HT2": 122, "HT3": 123}

# Table values are given for C20/25 and >= C25/30.
# C30/37 therefore uses the >= C25/30 design values.
HT_CAPACITIES = {
    "C20/25": {
        "HT1": (9.9, 0.0),
        "HT2": (0.0, 18.2),
        "HT3": (9.9, 18.2),
    },
    "C25/30": {
        "HT1": (11.5, 0.0),
        "HT2": (0.0, 21.2),
        "HT3": (11.5, 21.2),
    },
    "C30/37": {
        "HT1": (11.5, 0.0),
        "HT2": (0.0, 21.2),
        "HT3": (11.5, 21.2),
    },
}


def expected_ht_width_mm(series: str) -> int:
    key = str(series or "").strip().upper()
    if key not in HT_WIDTH_MM:
        raise ValueError("Řada HT musí být HP nebo SP.")
    return HT_WIDTH_MM[key]


def validate_ht_width(required_width_mm: str | int | None, series: str) -> int:
    expected = expected_ht_width_mm(series)
    text = str(required_width_mm or "").strip()
    if not text:
        return expected
    try:
        value = int(text)
        if str(value) != text or value <= 0:
            raise ValueError()
    except ValueError:
        raise ValueError("B požadované pro HT: zadejte kladné celé mm.") from None
    if value != expected:
        other = "HIT-SP HT má B = 150 mm." if expected == 100 else "HIT-HP HT má B = 100 mm."
        raise ValueError(
            f"HIT-{str(series).strip().upper()} HT má katalogovou šířku B = {expected} mm, "
            f"ale výkaz požaduje {value} mm. {other}"
        )
    return expected


def design_ht_candidates(
    series: str,
    height: int,
    concrete: str,
    h_parallel: float,
    h_perpendicular: float,
    required_width_mm: str | int | None = None,
) -> tuple[list[Candidate], str, dict[str, Any]]:
    """Return verified HT1..HT3 candidates.

    H actions are design forces per element [kN/element], not line loads.
    For HT3 the catalogue provides the same independent HRd values as HT1 and
    HT2 with both reinforcement systems present; both components are checked
    independently and the larger utilization governs.
    """
    series = str(series or "").strip().upper()
    concrete = str(concrete or "").strip()
    try:
        height = int(height)
    except (TypeError, ValueError):
        return [], "Výška HT musí být celé číslo v mm.", {}
    if series not in HT_WIDTH_MM:
        return [], "Řada HT musí být HP nebo SP.", {}
    if concrete not in HT_CAPACITIES:
        return [], f"Beton {concrete} není pro automatický návrh HT podporován.", {}
    if height < 160 or height > 350 or height % 10:
        return [], "HIT-HT má katalogový rozsah h = 160–350 mm po 10 mm.", {}
    try:
        width = validate_ht_width(required_width_mm, series)
        hp = abs(float(h_parallel or 0.0))
        ht = abs(float(h_perpendicular or 0.0))
    except ValueError as exc:
        return [], str(exc), {}
    if hp <= TOL and ht <= TOL:
        return [], "Zadejte HEd∥ nebo HEd⊥ v kN/prvek.", {}

    # HT1/HT2 are the simple one-direction variants; HT3 carries both systems.
    if hp > TOL and ht > TOL:
        types = ("HT3",)
    elif hp > TOL:
        types = ("HT1", "HT3")
    else:
        types = ("HT2", "HT3")

    rows: list[Candidate] = []
    capacities = HT_CAPACITIES[concrete]
    for typ in types:
        hrd_parallel, hrd_perp = capacities[typ]
        if hp > TOL and hrd_parallel <= TOL:
            continue
        if ht > TOL and hrd_perp <= TOL:
            continue
        u_parallel = 0.0 if hp <= TOL else hp / hrd_parallel
        u_perp = 0.0 if ht <= TOL else ht / hrd_perp
        utilization = max(u_parallel, u_perp)
        if utilization > 1.0 + TOL:
            continue
        if hp > TOL and ht > TOL:
            mode = (
                f"HT3: samostatně H∥ {u_parallel*100:.1f} % / "
                f"H⊥ {u_perp*100:.1f} %; rozhoduje horší směr"
            )
        elif hp > TOL:
            mode = f"{typ}: H∥ {u_parallel*100:.1f} %"
        else:
            mode = f"{typ}: H⊥ {u_perp*100:.1f} %"
        rows.append(
            Candidate(
                series=series,
                connection_type="HT",
                code=typ,
                length_code=HT_WIDTH_CODE[series],
                suffix="",
                h_table=height,
                concrete=concrete,
                m1=hrd_parallel,
                v1=hrd_perp,
                m2=0.0,
                v2=0.0,
                page=f"HIT20.2 p.{HT_PAGE[typ]}",
                cover=0,
                height=height,
                utilization=utilization,
                mode=mode,
                source_note=(
                    f"{HIT_HT_SOURCE}; HRd in kN/element. "
                    "HT4/HT5 are not auto-selected without a dedicated MVX/lifting-moment check."
                ),
            )
        )
    rows.sort(key=lambda c: (c.code == "HT3", -c.utilization, c.code))
    info = {
        "preferred_type": "HT",
        "primary_available": bool(rows),
        "alternative_type": "",
        "alternative_count": max(0, len(rows) - 1),
        "mode": "catalog_ht",
        "note": f"B = {width} mm; HEd v kN/prvek; HT4/HT5 vyžadují samostatnou vazbu na MVX.",
    }
    if rows:
        return rows, "", info

    strongest = "HT3"
    p, q = capacities[strongest]
    return [], (
        f"HT1–HT3 nevyhovují: HEd∥ = {hp:g} kN/prvek (HT3 HRd∥ {p:g}), "
        f"HEd⊥ = {ht:g} kN/prvek (HT3 HRd⊥ {q:g}). "
        "HT4/HT5 mohou mít vyšší vodorovnou únosnost, ale katalog je váže na MVX; "
        "program je proto bez kontroly této vazby automaticky nevybere."
    ), info
