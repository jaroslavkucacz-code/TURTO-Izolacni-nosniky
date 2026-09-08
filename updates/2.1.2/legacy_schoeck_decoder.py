from __future__ import annotations

"""Decoder-only historical Schöck Dorn aliases for TURTO 2.1.2.

This module deliberately patches only the shear-dowel decoder presentation.
The verified 2.1.0 Ancon/Schöck design and substitution engines stay untouched.
"""

import re
from typing import Any
from tkinter import messagebox

import shear_dowels_catalog as _catalog
import shear_dowels_ui as _ui

_ORIGINAL_DECODE = _catalog.decode_dowel
_ORIGINAL_SUMMARY = _catalog.catalog_summary
_ORIGINAL_REFRESH = _ui.refresh
_ORIGINAL_DECODER_TO_SUBSTITUTION = _ui.decoder_to_substitution

_LEGACY_SLD_SIZES = "40|50|60|70|80|120|150"

_LEGACY_SLDQ_RE = re.compile(
    rf"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?SLDQ\s*[- ]?\s*({_LEGACY_SLD_SIZES})\b",
    re.IGNORECASE,
)
_LEGACY_SLD_RE = re.compile(
    rf"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?SLD\s*(?:[- ]?Q)?\s*[- ]?\s*({_LEGACY_SLD_SIZES})\b",
    re.IGNORECASE,
)
_LEGACY_LD_RE = re.compile(
    r"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?"
    r"LD\s*(?P<q>[- ]?Q)?\s*[- ]?\s*(?P<size>16|20|22|25|30)"
    r"\s*[- ]\s*(?P<sleeve>S|P|F)\s*[- ]\s*(?P<material>A4|ZN)\b",
    re.IGNORECASE,
)
_LEGACY_LD_PART_RE = re.compile(
    r"(?:SCH[ÖO]CK\s+)?(?:DORN\s+)?(?:TYP\s+)?"
    r"LD\s*(?P<q>[- ]?Q)?\s*[- ]?\s*(?P<size>16|20|22|25|30)"
    r"\s+(?:PART|TEIL)\s+(?P<part>A4|ZN|S|P)\b",
    re.IGNORECASE,
)


def _legacy(raw: str, family: str, size: str, movement: str, detail: str) -> dict[str, Any]:
    return {
        "manufacturer": "Schöck",
        "family": family,
        "base_family": family.replace("-Q", ""),
        "size": size,
        "movement": movement,
        "text": raw,
        "legacy": True,
        "decoder_only": True,
        "generation": "Schöck Dorn – historické značení",
        "legacy_detail": detail,
    }


def decode_dowel(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    upper = raw.upper().replace("–", "-").replace("—", "-")

    m = _LEGACY_SLDQ_RE.search(upper)
    if m:
        return _legacy(
            raw,
            "SLD-Q",
            m.group(1),
            "transverse",
            "Starší řada Schöck Dorn SLD-Q; historická třída se nepřevádí na dnešní Stacon.",
        )

    m = _LEGACY_SLD_RE.search(upper)
    if m:
        q = bool(re.search(r"SLD\s*[- ]?Q", m.group(0), re.IGNORECASE))
        return _legacy(
            raw,
            "SLD-Q" if q else "SLD",
            m.group(1),
            "transverse" if q else "axial",
            "Starší řada Schöck Dorn SLD 40/50/60/70/80/120/150; pouze pro čtení starších projektů.",
        )

    m = _LEGACY_LD_RE.search(upper)
    if m:
        q = bool(m.group("q"))
        sleeve = m.group("sleeve").upper()
        material = m.group("material").upper().replace("ZN", "Zn")
        sleeve_text = {
            "S": "nerezová objímka",
            "P": "plastová objímka",
            "F": "jednostranná plastová objímka",
        }.get(sleeve, sleeve)
        material_text = "nerez A4" if material == "A4" else "žárově zinkovaný trn Zn"
        return _legacy(
            raw,
            "LD-Q" if q else "LD",
            m.group("size"),
            "transverse" if q else "axial",
            f"Starší materiálové značení Schöck Dorn LD: {sleeve_text}, {material_text}.",
        )

    m = _LEGACY_LD_PART_RE.search(upper)
    if m:
        q = bool(m.group("q"))
        part = m.group("part").upper().replace("ZN", "Zn")
        return _legacy(
            raw,
            "LD-Q" if q else "LD",
            m.group("size"),
            "transverse" if q else "axial",
            f"Starší komponentové značení Schöck Dorn LD – Part {part}.",
        )

    return _ORIGINAL_DECODE(raw)


def catalog_summary() -> str:
    return _ORIGINAL_SUMMARY() + " • Dekodér: historické Schöck Dorn SLD 40–150 a staré LD značení"


def _legacy_row_info(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    info = decode_dowel(str(row.get("designation", "") or ""))
    return info if isinstance(info, dict) and info.get("legacy") else None


def install(app_base: Any) -> None:
    # Old 2.1.0 UI resolves these module globals at runtime. Patching them here
    # broadens Decoder recognition without replacing design/substitution code.
    _catalog.decode_dowel = decode_dowel
    _catalog.catalog_summary = catalog_summary
    _ui.decode_dowel = decode_dowel
    _ui.catalog_summary = catalog_summary

    cls = app_base.ThermalConnectorApp

    def refresh(self: Any) -> None:
        _ORIGINAL_REFRESH(self)
        tree = getattr(self, "shear_decoder_tree", None)
        if tree is None:
            return
        for index, row in enumerate(getattr(self, "shear_decoder_rows", [])):
            info = _legacy_row_info(row)
            if not info:
                continue
            iid = str(index)
            if not tree.exists(iid):
                continue
            movement = "axiální + příčný" if info.get("movement") == "transverse" else "axiální"
            designation = str(row.get("designation", ""))
            detail = str(info.get("legacy_detail", "") or "")
            if detail:
                designation += "  •  " + detail
            tree.item(
                iid,
                values=(
                    row.get("name", ""),
                    row.get("quantity", 1),
                    "Schöck – historické",
                    str(info.get("family", "")) + " (starší)",
                    info.get("size", ""),
                    movement,
                    designation,
                    _ui._fmt(row.get("slab_mm"), 0),
                    _ui._fmt(row.get("gap_mm"), 0),
                    row.get("concrete", ""),
                ),
            )

    def decoder_to_substitution(self: Any) -> None:
        tree = getattr(self, "shear_decoder_tree", None)
        selected = tree.selection() if tree is not None else ()
        if selected:
            try:
                row = self.shear_decoder_rows[int(selected[0])]
            except Exception:
                row = None
            if _legacy_row_info(row):
                messagebox.showinfo(
                    "Historické značení Schöck Dorn",
                    "Historický Schöck Dorn je v TURTO určen pouze pro Dekodér. "
                    "Bez odpovídajícího historického katalogu jej program záměrně nepřenáší do Návrhu ani Záměn.",
                    parent=self,
                )
                return
        _ORIGINAL_DECODER_TO_SUBSTITUTION(self)

    cls.refresh_shear_tables = refresh
    cls.shear_decoder_to_substitution = decoder_to_substitution
