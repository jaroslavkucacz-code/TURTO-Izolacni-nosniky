from __future__ import annotations
"""Leviat / Aschwanden CRET Series 100, Switzerland, PDF 05/2026.

Exact FRd and aD,min tables transcribed from the user-supplied official technical
documentation. No resistance interpolation is performed. This is a separate
product source from HALFEN HSD EC 10-E (03/2026); bare CRET markings must not be
silently converted to HSD-CRET.
"""
from dataclasses import dataclass
import base64
import json
import math
import re
import zlib
from typing import Any

CATALOG_ID = "CRET Serie 100"
CATALOG_EDITION = "CHD | CHF PDF 05/26"
CATALOG_SOURCE = "Leviat / Aschwanden CRET Serie 100, Schweiz/Suisse, PDF 05/2026"
SOURCE_MONTH = "2026-05"
GAPS = (10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)
from cret_series_100_239_data1 import PART as _P1
from cret_series_100_239_data2 import PART as _P2
from cret_series_100_239_data3 import PART as _P3
from cret_series_100_239_data4 import PART as _P4
_raw_table = json.loads(zlib.decompress(base64.b64decode(_P1 + _P2 + _P3 + _P4)).decode("utf-8"))
del _P1, _P2, _P3, _P4
TABLE = {
    size: {int(h): {int(g): cell for g, cell in gaps.items()} for h, gaps in heights.items()}
    for size, heights in _raw_table.items()
}
del _raw_table
META = {'122': {'hmin': 180, 'corrosion': 'IV', 'base_constructive': 180, 'default_v': '25', 'variants': {'25': {'lateral': 12.5, 'constructive': 205, 'special': False}, '50': {'lateral': 25.0, 'constructive': 250, 'special': True}, '75': {'lateral': 37.5, 'constructive': 304, 'special': True}}, 'suspension': {'base': 'C25/30: 2×Ø14 (h≤200) / 4×Ø12 (h>200); C30/37: 4×Ø12', 'V25': '4×Ø14', 'V50': '4×Ø14', 'V75': '4×Ø14'}, 'pages': '6-10'}, '124': {'hmin': 200, 'corrosion': 'IV', 'base_constructive': 186, 'default_v': '28', 'variants': {'28': {'lateral': 14.0, 'constructive': 213, 'special': False}, '50': {'lateral': 25.0, 'constructive': 267, 'special': True}, '75': {'lateral': 37.5, 'constructive': 307, 'special': True}}, 'suspension': {'base': 'C25/30: 4×Ø12 (h=200), 4×Ø14 (h=201-400), 4×Ø12 (h>400); C30/37: 4×Ø14 (h≤350), 4×Ø12 (h>350)', 'V28': '4×Ø14', 'V50': '4×Ø16', 'V75': '4×Ø16'}, 'pages': '11-15'}, '128': {'hmin': 240, 'corrosion': 'IV', 'base_constructive': 188, 'default_v': '29', 'variants': {'29': {'lateral': 14.5, 'constructive': 216, 'special': False}, '50': {'lateral': 25.0, 'constructive': 271, 'special': True}, '75': {'lateral': 37.5, 'constructive': 311, 'special': True}}, 'suspension': {'base': 'C25/30: 4×Ø14 (h≤260), 4×Ø16 (h=261-340), 4×Ø14 (h>340); C30/37: 4×Ø16 (h≤280), 4×Ø14 (h>280)', 'V29': '4×Ø16', 'V50': '4×Ø16', 'V75': '4×Ø16'}, 'pages': '16-20'}, '134': {'hmin': 300, 'corrosion': 'IV', 'base_constructive': 316, 'default_v': '33', 'variants': {'33': {'lateral': 16.5, 'constructive': 348, 'special': False}, '50': {'lateral': 25.0, 'constructive': None, 'special': True}, '75': {'lateral': 37.5, 'constructive': None, 'special': True}}, 'suspension': {'base': 'C25/30: 6×Ø16 (h=300), 6×Ø14 (h=301-340), 4×Ø16 (h>340); C30/37: 4×Ø16', 'V33': '6×Ø16'}, 'pages': '21-24'}, '140': {'hmin': 350, 'corrosion': 'IV', 'base_constructive': 334, 'default_v': '32', 'variants': {'32': {'lateral': 16.0, 'constructive': 370, 'special': False}, '50': {'lateral': 25.0, 'constructive': None, 'special': True}, '75': {'lateral': 37.5, 'constructive': None, 'special': True}}, 'suspension': {'base': '6×Ø16', 'V32': '8×Ø16'}, 'pages': '25-28'}, '145': {'hmin': 420, 'corrosion': 'II', 'base_constructive': 434, 'default_v': '42', 'variants': {'42': {'lateral': 21.0, 'constructive': 474, 'special': False}}, 'suspension': {'base': 'C25/30: 8×Ø16 (h≤580), 6×Ø16 (h>580); C30/37: 8×Ø16 (h≤480), 6×Ø16 (h>480)', 'V42': 'C25/30: 10×Ø16; C30/37: 8×Ø16'}, 'pages': '29-32'}, '150': {'hmin': 600, 'corrosion': 'II', 'base_constructive': 470, 'default_v': '42', 'variants': {'42': {'lateral': 21.0, 'constructive': 510, 'special': False}}, 'suspension': {'base': '8×Ø16', 'V42': '10×Ø16'}, 'pages': '33-36'}, '155': {'hmin': 650, 'corrosion': 'II', 'base_constructive': 610, 'default_v': '42', 'variants': {'42': {'lateral': 21.0, 'constructive': 650, 'special': False}}, 'suspension': {'base': '10×Ø16', 'V42': '12×Ø16'}, 'pages': '37-41'}}
SERIES500 = {'504': {'joint_range': '10/20/30/40', 'h_ref': 300, 'e_ref': 20, 'vrd_ref': 76.7, 'variants': ('', 'A', 'B'), 'v': (20, 40), 'corrosion': 'III', 'special': False}, '508': {'joint_range': '50/60/70/80', 'h_ref': 280, 'e_ref': 50, 'vrd_ref': 49.0, 'variants': ('', 'A', 'B'), 'v': (20, 40), 'corrosion': 'III', 'special': False}, '512': {'joint_range': '90/100/110/120', 'h_ref': 160, 'e_ref': 90, 'vrd_ref': 28.0, 'variants': ('', 'A', 'B'), 'v': (20, 40), 'corrosion': 'III', 'special': True}, '515': {'joint_range': '130/140/150', 'h_ref': 160, 'e_ref': 130, 'vrd_ref': 15.0, 'variants': ('', 'A', 'B'), 'v': (20, 40), 'corrosion': 'III', 'special': True}}
SIZE_ORDER = ("122","124","128","134","140","145","150","155")

@dataclass(frozen=True)
class CretCandidate:
    manufacturer: str
    family: str
    size: str
    designation: str
    vrd: float
    utilization: float
    slab_table_mm: int
    gap_table_mm: int
    concrete_table: str
    movement: str
    page: str
    source: str
    status: str = "VYHOVUJE"
    note: str = ""
    length_mm: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer, "family": self.family,
            "size": self.size, "designation": self.designation,
            "vrd": self.vrd, "utilization": self.utilization,
            "slab_table_mm": self.slab_table_mm, "gap_table_mm": self.gap_table_mm,
            "concrete_table": self.concrete_table, "movement": self.movement,
            "page": self.page, "source": self.source, "status": self.status,
            "note": self.note, "length_mm": self.length_mm,
        }

def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").upper().replace("–","-").replace("—","-")).strip()

def _series100(raw: str):
    if "HSD" in raw:
        return None
    m = re.search(r"\bCRET\s*[- ]?\s*(122|124|128|134|140|145|150|155)\b", raw)
    if not m:
        return None
    size = m.group(1)
    tail = raw[m.end():]
    vm = re.match(r"\s*[- ]?\s*V(?:\s*[- ]?\s*(25|28|29|32|33|42|50|75))?\b", tail)
    has_v = vm is not None
    variant = vm.group(1) if vm is not None else None
    if variant and variant not in META[size]["variants"]:
        return None
    return size, has_v, variant

def decode_designation(text: Any) -> dict[str, Any] | None:
    raw = _norm(text)
    parsed = _series100(raw)
    if parsed:
        size, has_v, variant = parsed
        item = META[size]
        detail = item["variants"].get(variant) if variant else None
        designation = f"CRET-{size}" + (f" V{variant}" if variant else (" V" if has_v else ""))
        return {
            "manufacturer": "Leviat / Aschwanden",
            "family": "CRET Série 100 V" if has_v else "CRET Série 100",
            "size": size, "movement": "transverse" if has_v else "axial",
            "designation": designation, "series": "100", "cret_2026": True,
            "catalog": CATALOG_ID, "catalog_edition": CATALOG_EDITION,
            "source": CATALOG_SOURCE, "hmin_mm": item["hmin"],
            "max_joint_mm": 60, "corrosion_class": item["corrosion"],
            "v_variant": variant or "", "v_variant_unspecified": bool(has_v and not variant),
            "lateral_movement_mm": (detail or {}).get("lateral"),
            "constructive_min_mm": (detail or {}).get("constructive") if has_v else item["base_constructive"],
            "special": bool((detail or {}).get("special", False)),
            "decoder_only": False,
        }
    if "HSD" not in raw:
        m = re.search(r"\bCRET\s*[- ]?\s*(504|508|512|515)\s*([AB])?\s*(?:[- ]?\s*V\s*[- ]?\s*(20|40))?\b", raw)
        if m:
            size, model, v = m.group(1), (m.group(2) or ""), (m.group(3) or "")
            spec = SERIES500[size]
            designation = f"CRET-{size}{model}" + (f" V{v}" if v else "")
            return {
                "manufacturer":"Leviat / Aschwanden","family":"CRET Série 500",
                "size":f"{size}{model}","movement":"transverse" if v else "axial",
                "designation":designation,"series":"500","cret_2026":True,
                "catalog":CATALOG_ID,"catalog_edition":CATALOG_EDITION,"source":CATALOG_SOURCE,
                "corrosion_class":spec["corrosion"],"decoder_only":True,
                "overview_vrd":spec["vrd_ref"],"overview_h_mm":spec["h_ref"],"overview_gap_mm":spec["e_ref"],
                "joint_range":spec["joint_range"],"lateral_movement_mm":(float(v)/2.0 if v else None),
                "special":bool(spec["special"]),
            }
        m = re.search(r"\bCRET\s+SEISMIC\s*[- ]?\s*(122|124|128)\b", raw)
        if m:
            return {"manufacturer":"Leviat / Aschwanden","family":"CRET Seismic","size":m.group(1),
                     "movement":"seismic","designation":f"CRET Seismic-{m.group(1)}","cret_2026":True,
                     "catalog":CATALOG_ID,"catalog_edition":CATALOG_EDITION,"source":CATALOG_SOURCE,
                     "decoder_only":True,"special":True}
        m = re.search(r"\bCRET\s+MAGNET\s*[- ]?\s*(122|124)\b", raw)
        if m:
            return {"manufacturer":"Leviat / Aschwanden","family":"CRET Magnet","size":m.group(1),
                     "movement":"axial","designation":f"CRET Magnet-{m.group(1)}","cret_2026":True,
                     "catalog":CATALOG_ID,"catalog_edition":CATALOG_EDITION,"source":CATALOG_SOURCE,
                     "decoder_only":True,"special":True}
    return None

def _concrete(value: Any) -> tuple[str | None, str]:
    raw = _norm(value).replace(" ","")
    if raw in ("C25/30","C30/37"):
        return raw, ""
    m = re.fullmatch(r"C(\d+)/(\d+)", raw)
    if not m:
        return None, "Beton musí být C25/30 nebo C30/37 podle tabulek CRET 05/2026."
    return None, f"CRET 05/2026 tabuluje FRd pouze pro C25/30 a C30/37; {value} se automaticky nenahrazuje jinou třídou."

def _gap(value: float) -> int | None:
    if not math.isfinite(value) or value < 0:
        return None
    return next((g for g in GAPS if value <= g + 1e-9), None)

def _height(size: str, value: float) -> int | None:
    if not math.isfinite(value):
        return None
    rows = sorted(int(h) for h in TABLE[size])
    usable = [h for h in rows if h <= value + 1e-9]
    return max(usable) if usable else None

def capacity_for(info_or_text: dict[str, Any] | str, slab_mm: float, gap_mm: float,
                 concrete: str = "C25/30") -> tuple[dict[str, Any] | None, str]:
    info = decode_designation(info_or_text) if isinstance(info_or_text, str) else dict(info_or_text)
    if not info or not info.get("cret_2026"):
        return None, "Označení není CRET z dokumentace Leviat / Aschwanden 05/2026."
    if info.get("decoder_only") or info.get("series") != "100":
        return None, "Tento CRET je v dodaném dokumentu pouze v produktovém přehledu; bez detailní tabulky se automatická VRd nepřiřazuje."
    try:
        h, gap = float(slab_mm), float(gap_mm)
    except (TypeError, ValueError):
        return None, "Pro VRd doplňte tloušťku h a návrhovou spáru."
    if not math.isfinite(h) or not math.isfinite(gap) or h <= 0 or gap < 0:
        return None, "Pro VRd doplňte platnou kladnou tloušťku a nezápornou spáru."
    size = str(info["size"])
    ht = _height(size, h)
    if ht is None:
        return None, f"Tloušťka {h:g} mm je menší než hmin={META[size]['hmin']} mm pro CRET-{size}."
    gt = _gap(gap)
    if gt is None:
        return None, "Tabulky CRET Série 100 končí návrhovou spárou 60 mm."
    conc, cnote = _concrete(concrete)
    if conc is None:
        return None, cnote
    cell = TABLE[size][ht][gt][conc]
    vrd = float(cell["FRd"])
    variant = str(info.get("v_variant","") or "")
    meta = META[size]
    constructive = info.get("constructive_min_mm")
    suspension_key = ("V" + variant) if variant else "base"
    suspension = meta.get("suspension",{}).get(suspension_key, "")
    note_parts = [
        "Bez interpolace: h je volena dolů na nejbližší tabulkovou hodnotu a spára nahoru.",
        "FRd je převzata z tabulky typu CRET Série 100 pro C25/30 nebo C30/37.",
        "Platí při předepsané závěsné výztuži a dodržení minimálních vzdáleností.",
    ]
    if info.get("v_variant_unspecified"):
        note_parts.append("V-varianta není v označení upřesněna; před realizací doplňte konkrétní Vxx kvůli příčnému posunu a konstrukčnímu odstupu.")
    if info.get("special"):
        note_parts.append("Jde o speciální výrobek vyráběný na objednávku.")
    return {
        "vrd": vrd, "VRd": vrd, "movement": info.get("movement","axial"),
        "slab_table_mm": ht, "gap_table_mm": gt, "concrete_table": conc,
        "source": CATALOG_SOURCE, "catalog": CATALOG_ID, "catalog_edition": CATALOG_EDITION,
        "aD_min_rho_02_mm": int(cell["aD_02"]), "aD_min_rho_05_mm": int(cell["aD_05"]),
        "aD_min_rho_10_mm": int(cell["aD_10"]), "constructive_min_mm": constructive,
        "suspension_reinforcement": suspension, "corrosion_class": meta["corrosion"],
        "lateral_movement_mm": info.get("lateral_movement_mm"),
        "note": " ".join(note_parts), "conditional": True,
    }, ""

def _default_info(size: str, movement: str) -> dict[str, Any]:
    if movement == "transverse":
        return decode_designation(f"CRET-{size} V{META[size]['default_v']}")
    return decode_designation(f"CRET-{size}")

def design_cret(*, ved: float, slab_mm: float, gap_mm: float, concrete: str = "C25/30",
                movement: str = "axial", application: str = "new",
                low_sleeve: str = "stainless", **_kwargs):
    try:
        demand = abs(float(ved))
    except (TypeError, ValueError):
        return [], "VEd musí být číslo v kN na jeden trn."
    if not math.isfinite(demand) or demand <= 0:
        return [], "VEd musí být > 0 kN na jeden trn."
    if application not in ("new", "", None):
        return [], "CRET Série 100 je zde navrhován pro novou konstrukci; detail pro dodatečné kotvení tento katalog neobsahuje."
    movement = "transverse" if str(movement) == "transverse" else "axial"
    candidates = []
    errors = []
    for size in SIZE_ORDER:
        info = _default_info(size, movement)
        cap, error = capacity_for(info, slab_mm, gap_mm, concrete)
        if not cap:
            errors.append(error)
            continue
        if float(cap["vrd"]) + 1e-9 < demand:
            continue
        constructive = cap.get("constructive_min_mm")
        spacing = f"konstr. aD,min {constructive} mm" if constructive else "konstr. aD,min ověřit"
        note = (
            f"{cap['note']} {spacing}; tabulkové aD,min pro ρ=0,2/0,5/1,0 %: "
            f"{cap['aD_min_rho_02_mm']}/{cap['aD_min_rho_05_mm']}/{cap['aD_min_rho_10_mm']} mm."
        )
        candidates.append(CretCandidate(
            "Leviat / Aschwanden", str(info["family"]), size, str(info["designation"]),
            float(cap["vrd"]), demand / float(cap["vrd"]), int(cap["slab_table_mm"]),
            int(cap["gap_table_mm"]), str(cap["concrete_table"]), movement,
            str(META[size]["pages"]), CATALOG_SOURCE, "VYHOVUJE", note, None
        ))
    candidates.sort(key=lambda c: (c.vrd, SIZE_ORDER.index(c.size)))
    if candidates:
        return candidates, ""
    return [], (errors[0] if errors else "Pro zadané VEd a geometrii nebyl v tabulkách CRET Série 100 nalezen vyhovující typ.")

def suggestions() -> list[tuple[str,str,tuple[str,...]]]:
    rows = []
    for size in SIZE_ORDER:
        rows.append((f"CRET-{size}", "Leviat / Aschwanden • CRET Série 100 • podélný", (f"CRET {size}",f"ASCHWANDEN CRET {size}")))
        for variant, detail in META[size]["variants"].items():
            suffix = " • speciální" if detail.get("special") else ""
            rows.append((f"CRET-{size} V{variant}", f"Leviat / Aschwanden • příčný ±{detail['lateral']:g} mm{suffix}",
                         (f"CRET {size} V{variant}", f"CRET-{size}V{variant}")))
        rows.append((f"CRET-{size} V", "Leviat / Aschwanden • V-varianta bez upřesnění", (f"CRET {size} V",)))
    for size, spec in SERIES500.items():
        for model in spec["variants"]:
            rows.append((f"CRET-{size}{model}","Leviat / Aschwanden • CRET Série 500 • pouze dekodér",()))
            for v in spec["v"]:
                rows.append((f"CRET-{size}{model} V{v}","Leviat / Aschwanden • CRET Série 500 V • pouze dekodér",()))
    for size in ("122","124","128"):
        rows.append((f"CRET Seismic-{size}","Leviat / Aschwanden • speciální • pouze dekodér",()))
    for size in ("122","124"):
        rows.append((f"CRET Magnet-{size}","Leviat / Aschwanden • speciální • pouze dekodér",()))
    return rows

def selftest() -> None:
    a = decode_designation("CRET 122")
    assert a and a["manufacturer"] == "Leviat / Aschwanden" and not a["decoder_only"]
    v, e = capacity_for(a, 220, 20, "C30/37")
    assert not e and v and abs(v["vrd"] - 96.3) < 1e-9
    v, e = capacity_for("CRET-145 V42", 420, 20, "C30/37")
    assert not e and v and abs(v["vrd"] - 449.7) < 1e-9 and v["constructive_min_mm"] == 474
    v, e = capacity_for("CRET-155", 780, 10, "C25/30")
    assert not e and v and abs(v["vrd"] - 758.2) < 1e-9
    v, e = capacity_for("CRET-122", 220, 20, "C35/45")
    assert v is None and "pouze pro C25/30 a C30/37" in e
    assert decode_designation("HSD-CRET 122") is None
    assert decode_designation("CRET-504A V20")["decoder_only"] is True
    cands, err = design_cret(ved=440, slab_mm=420, gap_mm=20, concrete="C30/37", movement="axial")
    assert not err and cands and cands[0].designation == "CRET-145"
    cands, err = design_cret(ved=90, slab_mm=220, gap_mm=20, concrete="C30/37", movement="transverse")
    assert not err and cands and cands[0].designation == "CRET-122 V25"

if __name__ == "__main__":
    selftest()
