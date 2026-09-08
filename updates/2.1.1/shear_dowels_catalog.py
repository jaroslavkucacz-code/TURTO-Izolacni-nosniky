from __future__ import annotations

"""TURTO 2.1.1 – historical Schöck Dorn aliases for Decoder only.

The current 2.1.0 calculation/design tables remain authoritative for design and
substitution. This layer only broadens name recognition for old project files.
Historical aliases are explicitly marked and are never converted to current
Stacon capacities automatically.
"""

import re
from typing import Any

import shear_dowels_catalog_210 as _prev
from shear_dowels_catalog_210 import *  # noqa: F401,F403

LEGACY_SLD_SIZES = {"40", "50", "60", "70", "80", "120", "150"}
LEGACY_LD_SIZES = {"16", "20", "22", "25", "30"}

# Older planning documents used e.g. SLD-Q-60 and SLD-60.
_LEGACY_SLD_RE = re.compile(
    r"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?"
    r"SLD\s*(?:[- ]?Q)?\s*[- ]?\s*(40|50|60|70|80|120|150)\b",
    re.IGNORECASE,
)

# Accept compact spelling SLDQ 60 as well.
_LEGACY_SLDQ_RE = re.compile(
    r"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?"
    r"SLDQ\s*[- ]?\s*(40|50|60|70|80|120|150)\b",
    re.IGNORECASE,
)

# Historical LD system designations included sleeve and dowel materials, e.g.
# LD-20-S-A4, LD-20-P-A4, LD-20-P-Zn, LD-Q-20-S-A4, LD-20-F-A4.
_LEGACY_LD_RE = re.compile(
    r"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?"
    r"LD\s*(?P<q>[- ]?Q)?\s*[- ]?\s*(?P<size>16|20|22|25|30)"
    r"\s*[- ]\s*(?P<sleeve>S|P|F)\s*[- ]\s*(?P<material>A4|ZN)\b",
    re.IGNORECASE,
)

# Component notation also appeared in the older technical information.
_LEGACY_LD_PART_RE = re.compile(
    r"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?"
    r"LD\s*(?P<q>[- ]?Q)?\s*[- ]?\s*(?P<size>16|20|22|25|30)"
    r"\s+(?:PART|TEIL)\s+(?P<part>A4|ZN|S|P)\b",
    re.IGNORECASE,
)


def _legacy_info(*, raw: str, family: str, size: str, movement: str,
                 detail: str = "", material: str = "", sleeve: str = "") -> dict[str, Any]:
    return {
        "manufacturer": "Schöck",
        "family": family,
        "base_family": family.replace("-Q", ""),
        "size": size,
        "movement": movement,
        "text": raw,
        "legacy": True,
        "generation": "Schöck Dorn – historické značení",
        "decoder_only": True,
        "legacy_detail": detail,
        "legacy_material": material,
        "legacy_sleeve": sleeve,
    }


def decode_dowel(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    upper = raw.upper().replace("–", "-").replace("—", "-")

    m = _LEGACY_SLDQ_RE.search(upper)
    if m:
        return _legacy_info(
            raw=raw,
            family="SLD-Q",
            size=m.group(1),
            movement="transverse",
            detail="Starší řada Schöck Dorn SLD-Q; únosnostní třída není totožná s dnešní řadou Stacon SLD-Q.",
        )

    m = _LEGACY_SLD_RE.search(upper)
    if m:
        # Determine Q from the actual matched prefix, not from a loose Q elsewhere.
        prefix = m.group(0).upper()
        q = bool(re.search(r"SLD\s*[- ]?Q", prefix))
        return _legacy_info(
            raw=raw,
            family="SLD-Q" if q else "SLD",
            size=m.group(1),
            movement="transverse" if q else "axial",
            detail="Starší řada Schöck Dorn SLD; třídy 40/50/60/70/80/120/150 jsou historické a nemapují se automaticky na dnešní Stacon.",
        )

    m = _LEGACY_LD_RE.search(upper)
    if m:
        q = bool(m.group("q"))
        sleeve = m.group("sleeve").upper()
        material = m.group("material").upper().replace("ZN", "Zn")
        sleeve_text = {"S": "nerezová objímka", "P": "plastová objímka", "F": "jednostranná plastová objímka"}.get(sleeve, sleeve)
        mat_text = "nerez A4" if material == "A4" else "žárově zinkovaný trn Zn"
        return _legacy_info(
            raw=raw,
            family="LD-Q" if q else "LD",
            size=m.group("size"),
            movement="transverse" if q else "axial",
            detail=f"Starší materiálové značení Schöck Dorn LD: {sleeve_text}, {mat_text}.",
            material=material,
            sleeve=sleeve,
        )

    m = _LEGACY_LD_PART_RE.search(upper)
    if m:
        q = bool(m.group("q"))
        part = m.group("part").upper().replace("ZN", "Zn")
        return _legacy_info(
            raw=raw,
            family="LD-Q" if q else "LD",
            size=m.group("size"),
            movement="transverse" if q else "axial",
            detail=f"Starší komponentové značení Schöck Dorn LD – Part {part}.",
            material=part if part in {"A4", "Zn"} else "",
            sleeve=part if part in {"S", "P"} else "",
        )

    return _prev.decode_dowel(raw)


def propose_substitution(*args, **kwargs):
    source = str(kwargs.get("source_designation", "") or "")
    info = decode_dowel(source)
    if info and info.get("legacy"):
        return None, None, (
            "Historické označení Schöck Dorn je v TURTO 2.1.1 určeno pouze pro Dekodér. "
            "Bez odpovídajícího historického katalogu se nesmí automaticky použít pro návrh ani katalogovou záměnu."
        )
    return _prev.propose_substitution(*args, **kwargs)


def catalog_summary() -> str:
    return _prev.catalog_summary() + " • Dekodér navíc: historické Schöck Dorn SLD 40–150 a staré LD materiálové označení"
