from __future__ import annotations

"""Stabilní dekodér historických Schöck Dorn pro TURTO 2.2+.

Funkčně zachovává ověřenou logiku TURTO 2.1.5. Úplné historické typy
SLD/SLD-Q a LD/LD-Q mohou používat archivní VRd; samostatná označení
komponent zůstávají pouze informativní.
"""

import re
from typing import Any

import shear_dowels_catalog as _catalog
import shear_dowels_ui as _ui

_ORIGINAL_DECODE = _catalog.decode_dowel
_ORIGINAL_SUMMARY = _catalog.catalog_summary

_SIZES = "40|50|60|70|80|120|150"
_SLDQ = re.compile(
    rf"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?SLD\s*[- ]?Q\s*[- ]?\s*({_SIZES})\b",
    re.I,
)
_SLD = re.compile(
    rf"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?SLD\s*[- ]?\s*({_SIZES})\b",
    re.I,
)
_LD = re.compile(
    r"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?"
    r"LD\s*(?P<q>[- ]?Q)?\s*[- ]?\s*(?P<size>16|20|22|25|30)"
    r"\s*[- ]\s*(?P<sleeve>S|P|F)\s*[- ]\s*(?P<material>A4|ZN)\b",
    re.I,
)
_PART = re.compile(
    r"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?"
    r"LD\s*(?P<q>[- ]?Q)?\s*[- ]?\s*(?P<size>16|20|22|25|30)"
    r"\s+(?:PART|TEIL)\s+(?P<part>A4|ZN|S|P)\b",
    re.I,
)


def _legacy(
    raw: str,
    family: str,
    size: str,
    movement: str,
    detail: str,
    *,
    archive_supported: bool,
    decoder_only: bool,
) -> dict[str, Any]:
    return {
        "manufacturer": "Schöck",
        "family": family,
        "base_family": family.replace("-Q", ""),
        "size": size,
        "movement": movement,
        "text": raw,
        "legacy": True,
        "archive_supported": archive_supported,
        "decoder_only": decoder_only,
        "generation": "Schöck Dorn – historické značení",
        "legacy_detail": detail,
    }


def decode_dowel(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    upper = raw.upper().replace("–", "-").replace("—", "-")

    match = _SLDQ.search(upper)
    if match:
        return _legacy(
            raw,
            "SLD-Q",
            match.group(1),
            "transverse",
            "Historický Schöck Dorn SLD-Q; archivní VRd je integrováno v TURTO.",
            archive_supported=True,
            decoder_only=False,
        )

    match = _SLD.search(upper)
    if match:
        return _legacy(
            raw,
            "SLD",
            match.group(1),
            "axial",
            "Historický Schöck Dorn SLD; archivní VRd je integrováno v TURTO.",
            archive_supported=True,
            decoder_only=False,
        )

    match = _LD.search(upper)
    if match:
        q = bool(match.group("q"))
        sleeve = match.group("sleeve").upper()
        material = match.group("material").upper().replace("ZN", "Zn")
        sleeve_text = {
            "S": "nerezová objímka",
            "P": "plastová objímka",
            "F": "jednostranná plastová objímka",
        }.get(sleeve, sleeve)
        material_text = "nerez A4" if material == "A4" else "žárově zinkovaný trn Zn"
        return _legacy(
            raw,
            "LD-Q" if q else "LD",
            match.group("size"),
            "transverse" if q else "axial",
            f"Historický Schöck Dorn LD: {sleeve_text}, {material_text}; archivní VRd je integrováno v TURTO.",
            archive_supported=True,
            decoder_only=False,
        )

    match = _PART.search(upper)
    if match:
        q = bool(match.group("q"))
        part = match.group("part").upper().replace("ZN", "Zn")
        return _legacy(
            raw,
            "LD-Q" if q else "LD",
            match.group("size"),
            "transverse" if q else "axial",
            f"Historické komponentové značení Schöck Dorn LD – Part {part}. "
            "Samostatná komponenta neurčuje celý komplet.",
            archive_supported=False,
            decoder_only=True,
        )

    return _ORIGINAL_DECODE(raw)


def catalog_summary() -> str:
    return (
        _ORIGINAL_SUMMARY()
        + " • Archiv Schöck Dorn: SLD/SLD-Q 40–150 a kompletní staré LD/LD-Q s tabulkovým VRd"
    )


def install(app_base: Any) -> None:
    # Starší ověřené moduly řeší dekódování přes tyto modulové globály.
    _catalog.decode_dowel = decode_dowel
    _catalog.catalog_summary = catalog_summary
    _ui.decode_dowel = decode_dowel
    _ui.catalog_summary = catalog_summary
