from __future__ import annotations

"""Verified HIT-ST beam and HIT-WT wall-connector design values from HALFEN HIT 20.2-EN (2023).

WT is intentionally kept outside the slab-oriented HitInputRow calculation path.
The catalogue gives capacities per element and a wall-height-dependent MRd table.
No undocumented combined interaction is invented here: MEd-, VEd,v and VEd,h
are checked separately against their published design values and the governing
utilization is reported.
"""

from dataclasses import dataclass
import math
from typing import Any

TOL = 1e-9
SOURCE = "HALFEN HIT Insulated Connection ©2023, HIT 20.2-EN"
SOURCE_PAGES = {"overview": 161, "HP14": 162, "HP57": 163, "SP14": 164, "SP57": 165}
SERIES = ("HP", "SP")
CONCRETES = ("C20/25", "C25/30", "C30/37")
SOURCE_URL = "https://www.halfen.com/cdn/Medien%20I%20Media/Druckschriften%20-%20Printed%20materials/Technische%20Produktinformationen/HALFEN_HIT_20_v2026-03-EN.pdf"

# Printed pp. 154–155, 157–158 in the current official PDF (tables ©2023).
# Geometry is a range; MRd is conservatively taken at the next lower TABLE
# height. This is our conservative lookup, not a manufacturer interpolation rule.
_ST_M = {
    400: (25.7,29.6,33.1,39.2,44.8,51.8,61.3,71.4),
    500: (34.6,39.9,44.6,52.8,60.5,70.2,83.1,96.7),
    600: (43.4,50.1,56.1,66.5,76.2,88.4,104.8,122.0),
    700: (52.3,60.3,67.6,80.1,91.9,106.6,126.6,147.3),
    800: (61.2,70.6,79.2,93.8,107.6,124.8,148.3,172.6),
    900: (70.1,80.8,90.7,107.4,123.3,143.1,170.1,197.9),
    1000: (79.0,91.1,102.2,121.1,139.0,161.3,191.8,223.2),
}
_ST_V = {1:(26.7,30.9), 2:(44.0,48.3), 3:(60.0,69.5), 4:(82.2,94.7)}
_ST_JOINT = {"HP":{1:11.7,2:10.1,3:9.2,4:8.0}, "SP":{1:19.8,2:17.0,3:15.5,4:13.5}}

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
    vrd_horizontal: float | None
    eta_m: float
    eta_v: float
    eta_h: float
    utilization: float
    page: int
    joint_spacing_m: float
    connection_type: str = "WT"
    table_height_mm: int = 0

    @property
    def designation(self) -> str:
        # Keep the ACTUAL geometry, including a non-table height. Never truncate
        # millimetres to an integer centimetre in the ordering designation.
        return f"HIT-{self.series} {self.connection_type}-{self.load_range}-{self.wall_height_mm / 10:g}-{self.width_mm / 10:g}"

    @property
    def height_note(self) -> str:
        h = self.table_height_mm or self.wall_height_mm
        return (f"h = {self.wall_height_mm} mm; únosnost pro h tab. = {h} mm"
                + (" (nižší tabulková výška, bez interpolace)" if h != self.wall_height_mm else ""))

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
    raise ValueError(f"Beton {value or '—'} není pro HIT-ST / WT podporován.")


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


def validate_geometry(wall_height_mm: int, width_mm: int, connection_type="WT") -> None:
    low, high, b_low, b_high = (400,1000,220,340) if connection_type == "ST" else (1000,3500,150,250)
    if not b_low <= width_mm <= b_high or width_mm % 10:
        raise ValueError(f"HIT-{connection_type}: B musí být {b_low}–{b_high} mm po 10 mm; jiné šířky jsou zákaznické řešení.")
    if not low <= wall_height_mm <= high:
        raise ValueError(f"HIT-{connection_type}: h musí být {low}–{high} mm. Mimo katalogový rozsah je nutné zákaznické řešení.")


def _dimension(value):
    number = float(value)
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError("Rozměry zadejte v celých mm.")
    return int(number)


def design_wt(*, series: str, wall_height_mm: int, width_mm: int, concrete: str,
              med_neg: float, ved_vertical: float, ved_horizontal: float) -> tuple[list[WtCandidate], str]:
    return design_connector(connection_type="WT", series=series, wall_height_mm=wall_height_mm,
                            width_mm=width_mm, concrete=concrete, med_neg=med_neg,
                            ved_vertical=ved_vertical, ved_horizontal=ved_horizontal)


def design_connector(*, connection_type: str, series: str, wall_height_mm: int, width_mm: int,
                     concrete: str, med_neg: float, ved_vertical: float, ved_horizontal: float = 0):
    typ = str(connection_type).strip().upper()
    if typ not in {"ST", "WT"}:
        return [], "Vyberte typ ST nebo WT."
    series = str(series or "").strip().upper()
    if series not in SERIES:
        return [], f"Řada HIT-{typ} musí být HP nebo SP."
    try:
        height = _dimension(wall_height_mm)
        width = _dimension(width_mm)
        validate_geometry(height, width, typ)
        ci = _concrete_index(concrete)
        m = abs(float(med_neg or 0.0))
        vv = abs(float(ved_vertical or 0.0))
        vh = abs(float(ved_horizontal or 0.0))
        if not all(math.isfinite(v) for v in (m, vv, vh)):
            raise ValueError("Účinky musí být konečná čísla.")
        if typ == "ST" and vh > TOL:
            raise ValueError("HIT-ST nemá tabulovanou únosnost VEd,h. Vodorovnou sílu nelze tímto návrhem posoudit.")
    except (TypeError, ValueError) as exc:
        return [], str(exc)

    if max(m, vv, vh) <= TOL:
        return [], f"Zadejte alespoň jeden účinek na jeden prvek HIT-{typ}."

    rows: list[WtCandidate] = []
    table_height = height // (100 if typ == "ST" else 250) * (100 if typ == "ST" else 250)
    for load_range in range(1, 5 if typ == "ST" else 8):
        if typ == "WT" and load_range <= 4 and height < 1250:
            continue
        mrd = (_ST_M[table_height][(load_range - 1) * 2 + ci] if typ == "ST"
               else _moment_capacity(series, load_range, table_height, ci))
        if mrd is None:
            continue
        vrd_v = float((_ST_V if typ == "ST" else _VV)[load_range][ci])
        vrd_h = None if typ == "ST" else float(_VH[series][load_range][ci])
        eta_m = m / mrd if m > TOL else 0.0
        eta_v = vv / vrd_v if vv > TOL else 0.0
        eta_h = vh / vrd_h if vh > TOL else 0.0
        eta = max(eta_m, eta_v, eta_h)
        if eta <= 1.0 + TOL:
            page = 155 if typ == "ST" else SOURCE_PAGES[(series + ("14" if load_range <= 4 else "57"))]
            rows.append(WtCandidate(
                series=series, load_range=load_range, wall_height_mm=height, width_mm=width,
                concrete=str(concrete), mrd=mrd, vrd_vertical=vrd_v, vrd_horizontal=vrd_h,
                eta_m=eta_m, eta_v=eta_v, eta_h=eta_h, utilization=eta, page=page,
                joint_spacing_m=(_ST_JOINT if typ == "ST" else _JOINT)[series][load_range],
                connection_type=typ, table_height_mm=table_height,
            ))
    rows.sort(key=lambda row: (row.load_range, -row.utilization))
    if rows:
        return rows, ""
    return [], (
        f"Pro zadané účinky nebyl v tabulkách HIT-{typ} nalezen vyhovující prvek. "
        "Program nekombinuje ani neinterpoluje netabulované hodnoty."
    )


def candidate_dict(row: WtCandidate) -> dict[str, Any]:
    return {
        "designation": row.designation, "series": row.series, "load_range": row.load_range,
        "wall_height_mm": row.wall_height_mm, "width_mm": row.width_mm, "concrete": row.concrete,
        "mrd": row.mrd, "vrd_vertical": row.vrd_vertical, "vrd_horizontal": row.vrd_horizontal,
        "eta_m": row.eta_m, "eta_v": row.eta_v, "eta_h": row.eta_h,
        "utilization": row.utilization, "page": row.page, "joint_spacing_m": row.joint_spacing_m,
        "mode": row.mode, "source": SOURCE, "source_url": SOURCE_URL,
        "connection_type": row.connection_type, "table_height_mm": row.table_height_mm,
        "height_note": row.height_note,
    }
