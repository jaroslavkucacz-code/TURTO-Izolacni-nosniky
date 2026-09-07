from __future__ import annotations

"""Verified HIT-WT wall-connector design values from HALFEN HIT 20.2-EN (2023).

WT is intentionally kept outside the slab-oriented HitInputRow calculation path.
The catalogue gives capacities per element and a wall-height-dependent MRd table.
No undocumented combined interaction is invented here: MEd-, VEd,v and VEd,h
are checked separately against their published design values and the governing
utilization is reported.
"""

from dataclasses import dataclass
from typing import Any

TOL = 1e-9
SOURCE = "HALFEN HIT Insulated Connection ©2023, HIT 20.2-EN"
SOURCE_PAGES = {"overview": 161, "HP14": 162, "HP57": 163, "SP14": 164, "SP57": 165}
SERIES = ("HP", "SP")
CONCRETES = ("C20/25", "C25/30", "C30/37")

# Values are (C20/25, >=C25/30)
_VV = {
    1: (45.7, 52.2), 2: (80.0, 92.7), 3: (132.1, 144.9), 4: (179.9, 208.8),
    5: (53.3, 61.8), 6: (119.9, 139.1), 7: (164.4, 189.3),
}
_VH = {
    "HP": {
        1: (17.2, 20.0), 2: (17.2, 20.0), 3: (17.2, 20.0), 4: (17.2, 20.0),
        5: (22.9, 26.6), 6: (22.9, 26.6), 7: (22.9, 26.6),
    },
    "SP": {
        1: (14.1, 16.4), 2: (14.1, 16.4), 3: (14.1, 16.4), 4: (14.1, 16.4),
        5: (18.8, 21.9), 6: (18.8, 21.9), 7: (18.8, 21.9),
    },
}

# MRd tables. Each row stores (C20 WT1, C25 WT1, C20 WT2, C25 WT2, ...).
_M_HP_14 = {
    1250:(44.8,54.2,79.6,96.3,124.4,148.9,176.4,213.8),
    1500:(55.4,66.3,98.5,117.9,154.0,182.6,218.4,262.3),
    1750:(66.0,78.5,117.5,139.5,183.7,216.4,260.6,311.0),
    2000:(76.7,90.7,136.5,161.2,213.4,250.3,302.8,359.9),
    2250:(87.4,102.9,155.6,183.0,243.2,284.3,345.0,408.8),
    2500:(98.1,115.2,174.6,204.7,273.0,318.3,387.3,452.9),
    2750:(108.8,127.4,193.7,226.5,302.8,352.3,425.1,493.5),
    3000:(119.5,139.7,212.7,248.2,329.4,386.4,459.9,533.9),
    3250:(130.2,151.9,231.8,270.0,354.2,420.4,494.6,574.3),
    3500:(140.9,164.2,250.9,291.7,379.0,454.5,529.3,614.6),
}
_M_SP_14 = {
    1250:(44.8,54.2,79.6,96.4,124.4,149.0,176.4,214.0),
    1500:(55.4,66.3,98.6,117.9,154.0,182.6,218.4,262.4),
    1750:(66.0,78.5,117.5,139.6,183.7,216.4,260.6,311.1),
    2000:(76.7,90.7,136.5,161.3,213.4,250.3,302.8,360.0),
    2250:(87.4,102.9,155.6,183.0,243.2,284.3,345.0,408.9),
    2500:(98.1,115.2,174.6,204.8,273.0,318.3,387.3,456.7),
    2750:(108.8,127.4,193.7,226.5,302.8,352.4,428.5,497.5),
    3000:(119.5,139.7,212.7,248.2,331.9,386.4,463.3,537.9),
    3250:(130.2,151.9,231.8,270.0,356.7,420.5,498.1,578.3),
    3500:(140.9,164.2,250.9,291.7,381.6,454.6,532.8,618.7),
}
_M_57 = {
    1000:(60.7,74.6,133.6,163.4,181.6,222.5),
    1250:(79.7,96.8,175.9,213.1,239.0,290.1),
    1500:(98.6,118.3,217.9,261.7,296.1,356.2),
    1750:(117.6,139.9,260.0,310.5,353.4,422.6),
    2000:(136.6,161.5,302.2,353.9,410.7,481.7),
    2250:(155.6,183.1,339.5,393.3,459.6,535.2),
    2500:(174.7,204.8,373.3,432.4,505.2,588.5),
    2750:(193.7,226.5,407.0,471.5,550.8,641.7),
    3000:(212.8,248.2,440.8,510.6,596.3,694.8),
    3250:(231.8,270.0,474.5,549.6,641.8,748.0),
    3500:(250.9,291.8,508.2,588.7,687.3,801.1),
}

_JOINT = {
    "HP": {1:13.5, 2:13.5, 3:11.7, 4:10.1, 5:13.5, 6:11.7, 7:10.1},
    "SP": {1:23.0, 2:23.0, 3:19.8, 4:17.0, 5:23.0, 6:19.8, 7:17.0},
}


@dataclass(frozen=True)
class WtCandidate:
    series: str
    load_range: int
    wall_height_mm: int
    width_mm: int
    concrete: str
    mrd: float
    vrd_vertical: float
    vrd_horizontal: float
    eta_m: float
    eta_v: float
    eta_h: float
    utilization: float
    page: int
    joint_spacing_m: float

    @property
    def designation(self) -> str:
        return f"HIT-{self.series} WT-{self.load_range}-{self.wall_height_mm // 10:03d}-{self.width_mm // 10:02d}"

    @property
    def mode(self) -> str:
        checks = (("M−", self.eta_m), ("Vv+", self.eta_v), ("Vh±", self.eta_h))
        governing = max(checks, key=lambda item: item[1])
        return f"rozhoduje {governing[0]}: η {governing[1]*100:.1f} %"


def _concrete_index(concrete: str) -> int:
    value = str(concrete or "").strip()
    if value == "C20/25":
        return 0
    if value in {"C25/30", "C30/37"}:
        return 1
    raise ValueError(f"Beton {value or '—'} není pro HIT-WT podporován.")


def _moment_capacity(series: str, load_range: int, height_mm: int, concrete_index: int) -> float | None:
    if load_range <= 4:
        table = _M_HP_14 if series == "HP" else _M_SP_14
        values = table.get(height_mm)
        if values is None:
            return None
        offset = (load_range - 1) * 2 + concrete_index
        return float(values[offset])
    values = _M_57.get(height_mm)
    if values is None:
        return None
    offset = (load_range - 5) * 2 + concrete_index
    return float(values[offset])


def validate_geometry(wall_height_mm: int, width_mm: int) -> None:
    if not 150 <= width_mm <= 250 or width_mm % 10:
        raise ValueError("HIT-WT: B musí být 150–250 mm po 10 mm; jiné šířky jsou zákaznické řešení.")
    if wall_height_mm < 1000 or wall_height_mm > 3500 or wall_height_mm % 250:
        raise ValueError(
            "HIT-WT: pro automatický návrh zadejte výšku stěny 1000–3500 mm po 250 mm "
            "podle tabulovaných MRd. Jiné výšky program bez ověřené interpolace neodhaduje."
        )


def design_wt(*, series: str, wall_height_mm: int, width_mm: int, concrete: str,
              med_neg: float, ved_vertical: float, ved_horizontal: float) -> tuple[list[WtCandidate], str]:
    series = str(series or "").strip().upper()
    if series not in SERIES:
        return [], "Řada HIT-WT musí být HP nebo SP."
    try:
        height = int(wall_height_mm)
        width = int(width_mm)
        validate_geometry(height, width)
        ci = _concrete_index(concrete)
        m = abs(float(med_neg or 0.0))
        vv = abs(float(ved_vertical or 0.0))
        vh = abs(float(ved_horizontal or 0.0))
    except (TypeError, ValueError) as exc:
        return [], str(exc)

    if max(m, vv, vh) <= TOL:
        return [], "Zadejte alespoň jeden účinek MEd−, VEd,v+ nebo VEd,h± na jeden WT prvek."

    rows: list[WtCandidate] = []
    for load_range in range(1, 8):
        if load_range <= 4 and height < 1250:
            continue
        mrd = _moment_capacity(series, load_range, height, ci)
        if mrd is None:
            continue
        vrd_v = float(_VV[load_range][ci])
        vrd_h = float(_VH[series][load_range][ci])
        eta_m = m / mrd if m > TOL else 0.0
        eta_v = vv / vrd_v if vv > TOL else 0.0
        eta_h = vh / vrd_h if vh > TOL else 0.0
        eta = max(eta_m, eta_v, eta_h)
        if eta <= 1.0 + TOL:
            page = SOURCE_PAGES[(series + ("14" if load_range <= 4 else "57"))]
            rows.append(WtCandidate(
                series=series, load_range=load_range, wall_height_mm=height, width_mm=width,
                concrete=str(concrete), mrd=mrd, vrd_vertical=vrd_v, vrd_horizontal=vrd_h,
                eta_m=eta_m, eta_v=eta_v, eta_h=eta_h, utilization=eta, page=page,
                joint_spacing_m=_JOINT[series][load_range],
            ))
    rows.sort(key=lambda row: (row.load_range, -row.utilization))
    if rows:
        return rows, ""
    return [], (
        "Pro zadané MEd− / VEd,v+ / VEd,h± nebyl v tabulkách HIT-WT 1–7 nalezen vyhovující prvek. "
        "Program nekombinuje ani neinterpoluje netabulované hodnoty."
    )


def candidate_dict(row: WtCandidate) -> dict[str, Any]:
    return {
        "designation": row.designation, "series": row.series, "load_range": row.load_range,
        "wall_height_mm": row.wall_height_mm, "width_mm": row.width_mm, "concrete": row.concrete,
        "mrd": row.mrd, "vrd_vertical": row.vrd_vertical, "vrd_horizontal": row.vrd_horizontal,
        "eta_m": row.eta_m, "eta_v": row.eta_v, "eta_h": row.eta_h,
        "utilization": row.utilization, "page": row.page, "joint_spacing_m": row.joint_spacing_m,
        "mode": row.mode, "source": SOURCE,
    }
