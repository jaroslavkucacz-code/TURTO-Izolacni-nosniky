from __future__ import annotations

"""Leviat / HALFEN HSD decoder and reviewed catalogue resistance data.

Source supplied by the user:
HSD EC 10-E, HALFEN HSD Shear Dowel System, PDF 03/26.
The technical table pages themselves are marked (c) 2020 and reference
EN 1992-1-1:2008. Values are copied without interpolation.
"""

import re
from typing import Any

SOURCE = (
    "Leviat / HALFEN HSD EC 10-E, PDF 03/26 "
    "(technical tables marked 2020), EN 1992-1-1:2008"
)
TOL = 1e-9

CRET_SIZES = (122, 124, 128, 134, 140, 145, 150, 155)
CRET_DIAMETER = {122: 22, 124: 24, 128: 28, 134: 34, 140: 40, 145: 45, 150: 50, 155: 55}
CRET_HMIN = {122: 180, 124: 200, 128: 240, 134: 300, 140: 350, 145: 420, 150: 600, 155: 650}
CRET_GAPS = (10, 20, 30, 40, 50, 60)

# Published VRd [kN] tables, brochure p.7 and p.8.
# Keyed by type -> concrete table -> component thickness lower-bound -> six joint widths.
CRET_LONG = {
    122: {
        "C20/25": {
            180: (54.9, 54.9, 54.9, 54.9, 53.2, 44.4),
            200: (61.3, 61.3, 61.3, 61.3, 53.2, 44.4),
            220: (67.6, 67.6, 67.6, 66.6, 53.2, 44.4),
            240: (74.0, 74.0, 74.0, 66.6, 53.2, 44.4),
            250: (77.2, 77.2, 77.2, 66.6, 53.2, 44.4),
            260: (80.4, 80.4, 80.4, 66.6, 53.2, 44.4),
            280: (86.8, 86.8, 81.8, 66.6, 53.2, 44.4),
        },
        "C25/30": {
            180: (68.6, 68.6, 68.6, 66.6, 53.2, 44.4),
            200: (76.6, 76.6, 76.6, 66.6, 53.2, 44.4),
            220: (84.5, 84.5, 81.8, 66.6, 53.2, 44.4),
            240: (92.5, 92.5, 81.8, 66.6, 53.2, 44.4),
            250: (96.5, 96.5, 81.8, 66.6, 53.2, 44.4),
            260: (100.5, 98.2, 81.8, 66.6, 53.2, 44.4),
            280: (108.5, 98.2, 81.8, 66.6, 53.2, 44.4),
        },
    },
    124: {
        "C20/25": {
            200: (79.8, 79.8, 79.8, 79.8, 69.1, 57.6),
            220: (87.7, 87.7, 87.7, 86.4, 69.1, 57.6),
            240: (95.7, 95.7, 95.7, 86.4, 69.1, 57.6),
            250: (99.7, 99.7, 99.7, 86.4, 69.1, 57.6),
            260: (103.7, 103.7, 103.7, 86.4, 69.1, 57.6),
            280: (111.7, 111.7, 108.8, 86.4, 69.1, 57.6),
        },
        "C25/30": {
            200: (99.7, 99.7, 99.7, 86.4, 69.1, 57.6),
            220: (109.7, 109.7, 108.8, 86.4, 69.1, 57.6),
            240: (119.6, 119.6, 108.8, 86.4, 69.1, 57.6),
            250: (124.6, 124.6, 108.8, 86.4, 69.1, 57.6),
            260: (129.6, 125.6, 108.8, 86.4, 69.1, 57.6),
            280: (139.6, 125.6, 108.8, 86.4, 69.1, 57.6),
        },
    },
    128: {
        "C20/25": {
            240: (121.0, 121.0, 121.0, 121.0, 109.8, 91.5),
            250: (125.6, 125.6, 125.6, 125.6, 109.8, 91.5),
            260: (130.3, 130.3, 130.3, 130.2, 109.8, 91.5),
            280: (139.6, 139.6, 139.6, 130.2, 109.8, 91.5),
            300: (148.9, 148.9, 147.5, 130.2, 109.8, 91.5),
            320: (158.2, 158.2, 147.5, 130.2, 109.8, 91.5),
        },
        "C25/30": {
            240: (151.2, 151.2, 147.9, 130.2, 109.8, 91.5),
            250: (157.0, 157.0, 147.9, 130.2, 109.8, 91.5),
            260: (162.8, 162.8, 147.9, 130.2, 109.8, 91.5),
            280: (174.5, 169.1, 147.9, 130.2, 109.8, 91.5),
            300: (186.1, 169.1, 147.9, 130.2, 109.8, 91.5),
            320: (188.2, 169.1, 147.9, 130.2, 109.8, 91.5),
        },
    },
    134: {
        "C20/25": {
            300: (202.9, 202.9, 202.9, 197.0, 175.5, 162.7),
            320: (213.8, 213.8, 213.8, 197.0, 175.5, 162.7),
        },
        "C25/30": {
            300: (253.6, 239.7, 219.3, 198.2, 175.7, 162.7),
            320: (259.5, 239.7, 219.3, 198.2, 175.7, 162.7),
        },
    },
    140: {
        "C20/25": {
            350: (290.4, 290.4, 290.4, 290.4, 263.0, 250.2),
            360: (296.8, 296.8, 296.8, 291.9, 263.0, 250.2),
            380: (309.4, 309.4, 309.4, 291.9, 263.0, 250.2),
            400: (322.0, 322.0, 317.9, 291.9, 263.0, 250.2),
        },
        "C25/30": {
            350: (363.0, 347.0, 320.8, 293.2, 263.1, 250.2),
            360: (370.9, 347.0, 320.8, 293.2, 263.1, 250.2),
            380: (372.1, 347.0, 320.8, 293.2, 263.1, 250.2),
            400: (372.1, 347.0, 320.8, 293.2, 263.1, 250.2),
        },
    },
}

CRET_TRANSVERSE = {
    122: {
        "C20/25": {
            180: (54.9, 54.9, 54.9, 54.9, 47.9, 39.9),
            200: (61.3, 61.3, 61.3, 59.9, 47.9, 39.9),
            220: (67.6, 67.6, 67.6, 59.9, 47.9, 39.9),
            240: (74.0, 74.0, 74.0, 59.9, 47.9, 39.9),
            250: (77.2, 77.2, 77.2, 59.9, 47.9, 39.9),
            260: (80.4, 80.4, 79.4, 59.9, 47.9, 39.9),
            280: (86.8, 86.8, 79.4, 59.9, 47.9, 39.9),
        },
        "C25/30": {
            180: (68.6, 68.6, 68.6, 59.9, 47.9, 39.9),
            200: (76.6, 76.6, 76.6, 59.9, 47.9, 39.9),
            220: (84.5, 84.5, 79.4, 59.9, 47.9, 39.9),
            240: (92.5, 92.5, 79.4, 59.9, 47.9, 39.9),
            250: (96.5, 93.1, 79.4, 59.9, 47.9, 39.9),
            260: (100.5, 93.1, 79.4, 59.9, 47.9, 39.9),
            280: (108.5, 93.1, 79.4, 59.9, 47.9, 39.9),
        },
    },
    124: {
        "C20/25": {
            200: (79.8, 79.8, 79.8, 77.8, 62.2, 51.8),
            220: (87.7, 87.7, 87.7, 77.8, 62.2, 51.8),
            240: (95.7, 95.7, 95.7, 77.8, 62.2, 51.8),
            250: (99.7, 99.7, 99.7, 77.8, 62.2, 51.8),
            260: (103.7, 103.7, 101.4, 77.8, 62.2, 51.8),
            280: (111.7, 111.7, 101.4, 77.8, 62.2, 51.8),
        },
        "C25/30": {
            200: (99.7, 99.7, 99.7, 77.8, 62.2, 51.8),
            220: (109.7, 109.7, 101.4, 77.8, 62.2, 51.8),
            240: (119.6, 119.6, 101.4, 77.8, 62.2, 51.8),
            250: (124.6, 119.0, 101.4, 77.8, 62.2, 51.8),
            260: (129.6, 119.0, 101.4, 77.8, 62.2, 51.8),
            280: (139.6, 119.0, 101.4, 77.8, 62.2, 51.8),
        },
    },
    128: {
        "C20/25": {
            240: (121.0, 121.0, 121.0, 121.0, 98.8, 82.3),
            250: (125.6, 125.6, 125.6, 123.4, 98.8, 82.3),
            260: (130.3, 130.3, 130.3, 123.4, 98.8, 82.3),
            280: (139.6, 139.6, 138.4, 123.4, 98.8, 82.3),
            300: (148.9, 148.9, 138.4, 123.4, 98.8, 82.3),
            320: (158.2, 158.2, 138.4, 123.4, 98.8, 82.3),
        },
        "C25/30": {
            240: (151.2, 151.2, 138.5, 123.4, 98.8, 82.3),
            250: (157.0, 157.0, 138.5, 123.4, 98.8, 82.3),
            260: (162.8, 162.2, 138.5, 123.4, 98.8, 82.3),
            280: (174.5, 162.2, 138.5, 123.4, 98.8, 82.3),
            300: (182.6, 162.2, 138.5, 123.4, 98.8, 82.3),
            320: (182.6, 162.2, 138.5, 123.4, 98.8, 82.3),
        },
    },
    134: {
        "C20/25": {
            300: (202.9, 202.9, 202.9, 185.6, 162.7, 147.4),
            320: (213.8, 213.8, 207.6, 185.6, 162.7, 147.4),
        },
        "C25/30": {
            300: (251.8, 231.1, 209.5, 186.5, 162.7, 147.4),
            320: (251.8, 231.1, 209.5, 186.5, 162.7, 147.4),
        },
    },
    140: {
        "C20/25": {
            350: (290.4, 290.4, 290.4, 275.6, 250.2, 240.0),
            360: (296.8, 296.8, 296.8, 275.6, 250.2, 240.0),
            380: (309.4, 309.4, 304.5, 275.6, 250.2, 240.0),
            400: (322.0, 322.0, 304.5, 275.6, 250.2, 240.0),
        },
        "C25/30": {
            350: (361.1, 334.6, 306.6, 276.2, 250.2, 240.0),
            360: (361.1, 334.6, 306.6, 276.2, 250.2, 240.0),
            380: (361.1, 334.6, 306.6, 276.2, 250.2, 240.0),
            400: (361.1, 334.6, 306.6, 276.2, 250.2, 240.0),
        },
    },
}

SINGLE_SIZES = (20, 22, 25, 30)
SINGLE_LENGTH = {20: 300, 22: 300, 25: 300, 30: 350}
SINGLE_GAPS = (10, 20, 30, 40)
SINGLE_STEEL_LONG = {
    20: (14.3, 9.5, 7.1, 5.7),
    22: (18.1, 12.2, 9.3, 7.4),
    25: (24.8, 17.1, 13.1, 10.6),
    30: (38.5, 27.5, 21.4, 17.5),
}
SINGLE_STEEL_TRANSVERSE = {
    20: (12.8, 8.6, 6.4, 5.1),
    22: (16.3, 11.0, 8.3, 6.7),
    25: (22.3, 15.4, 11.8, 9.5),
    30: (34.6, 24.7, 19.2, 15.7),
}
SINGLE_CONCRETE_LONG = {
    20: {160: 14.2, 180: 15.8},
    22: {160: 14.2, 180: 15.8, 200: 17.3, 220: 18.9, 240: 20.4},
    25: {180: 20.5, 200: 22.4, 220: 24.3, 240: 26.2, 260: 28.0},
    30: {220: 29.3, 240: 31.5, 260: 33.7, 280: 35.9, 300: 38.1, 320: 40.2},
}
# Blank entries in the source table remain absent; they are never inferred.
SINGLE_CONCRETE_TRANSVERSE = {
    20: {180: 13.0},
    22: {180: 12.5, 200: 13.9, 220: 15.3, 240: 16.7},
    25: {200: 18.0, 220: 19.8, 240: 21.5, 260: 23.2},
    30: {220: 24.6, 240: 26.7, 260: 28.7, 280: 30.7, 300: 32.7, 320: 34.7},
}

_CRET_RE = re.compile(r"\bHSD\s*-\s*CRET\s*[- ]?\s*(122|124|128|134|140|145|150|155)\s*(V)?\b", re.I)
_SET_RE = re.compile(r"\bHSD\s*-\s*SET\s*[- ]?\s*(20|22|25|30)\s*(V)?\s*(?:[- ]\s*(A4|FV))?\b", re.I)
_D_RE = re.compile(r"\bHSD\s*-\s*D\s*[- ]?\s*(20|22|25|30)\s*(?:[- ]\s*(A4|FV))?\b", re.I)
_SOCKET_RE = re.compile(r"\bHSD\s*-\s*(SV|S|P)\s*[- ]?\s*(20|22|25|30)\b", re.I)
_FIRE_CRET_RE = re.compile(r"\bHSD\s*-\s*F\s*-\s*CRET\s*[- ]?\s*(122|124|128|134|140)\s*(V)?\s*[- ]?\s*(20|30)?\b", re.I)
_FIRE_SINGLE_RE = re.compile(r"\bHSD\s*-\s*F\s*[- ]?\s*(20|22|25|30)\s*(V)?\s*[- ]?\s*(20|30)?\b", re.I)


def _strength(concrete: str) -> int | None:
    match = re.search(r"C\s*(\d+)\s*/", str(concrete or "").upper())
    return int(match.group(1)) if match else None


def _concrete_table(concrete: str) -> str | None:
    strength = _strength(concrete)
    if strength is None or strength < 20:
        return None
    return "C20/25" if strength < 25 else "C25/30"


def _gap_up(actual: float, allowed: tuple[int, ...]) -> int | None:
    value = float(actual)
    if value < -TOL:
        return None
    return next((g for g in allowed if value <= g + TOL), None)


def _height_down(actual: float, values: dict[int, Any]) -> int | None:
    value = float(actual)
    eligible = [h for h in values if h <= value + TOL]
    return max(eligible) if eligible else None


def decode_hsd(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    match = _CRET_RE.search(raw)
    if match:
        size = int(match.group(1))
        transverse = bool(match.group(2))
        published = size <= 140
        return {
            "manufacturer": "Leviat",
            "family": "HSD-CRET V" if transverse else "HSD-CRET",
            "base_family": "HSD-CRET",
            "size": str(size),
            "diameter_mm": CRET_DIAMETER[size],
            "movement": "transverse" if transverse else "axial",
            "decoder_only": not published,
            "legacy_detail": (
                "HSD-CRET 145/150/155 je katalogově rozpoznán, ale jeho tabulková VRd "
                "je v HSD EC 10-E uvedena pouze jako dostupná na vyžádání."
                if not published else ""
            ),
            "text": raw,
        }

    match = _SET_RE.search(raw)
    if match:
        size = int(match.group(1))
        transverse = bool(match.group(2))
        material = (match.group(3) or "A4").upper()
        return {
            "manufacturer": "Leviat",
            "family": "HSD-SET V" if transverse else "HSD-SET",
            "base_family": "HSD-D",
            "size": str(size),
            "diameter_mm": size,
            "movement": "transverse" if transverse else "axial",
            "material": material,
            "socket": "SV" if transverse else ("P" if material == "FV" else "S"),
            "text": raw,
        }

    dowel = _D_RE.search(raw)
    socket = _SOCKET_RE.search(raw)
    if dowel and socket:
        d_size = int(dowel.group(1))
        s_size = int(socket.group(2))
        material = (dowel.group(2) or "A4").upper()
        sleeve = socket.group(1).upper()
        errors = []
        if d_size != s_size:
            errors.append("Průměr trnu a pouzdra se neshoduje.")
        if material == "FV" and sleeve != "P":
            errors.append("Provedení HSD-D FV je v katalogu určeno pouze s plastovým pouzdrem HSD-P.")
        if material == "A4" and sleeve == "P":
            errors.append("Katalog HSD-P uvádí plastové pouzdro pouze pro trn HSD-D v provedení FV.")
        movement = "transverse" if sleeve == "SV" else "axial"
        return {
            "manufacturer": "Leviat",
            "family": f"HSD-D + HSD-{sleeve}",
            "base_family": "HSD-D",
            "size": str(d_size),
            "diameter_mm": d_size,
            "movement": movement,
            "material": material,
            "socket": sleeve,
            "decoder_only": bool(errors),
            "legacy_detail": " ".join(errors),
            "text": raw,
        }

    if dowel:
        size = int(dowel.group(1))
        material = (dowel.group(2) or "A4").upper()
        return {
            "manufacturer": "Leviat",
            "family": "HSD-D",
            "base_family": "HSD-D",
            "size": str(size),
            "diameter_mm": size,
            "movement": "unknown",
            "material": material,
            "decoder_only": True,
            "legacy_detail": "Samostatný HSD-D neurčuje typ pouzdra HSD-S/HSD-SV/HSD-P, a tedy ani směr posunu.",
            "text": raw,
        }

    if socket:
        sleeve = socket.group(1).upper()
        size = int(socket.group(2))
        return {
            "manufacturer": "Leviat",
            "family": f"HSD-{sleeve}",
            "base_family": "HSD-D",
            "size": str(size),
            "diameter_mm": size,
            "movement": "transverse" if sleeve == "SV" else "axial",
            "socket": sleeve,
            "decoder_only": True,
            "legacy_detail": "Jde pouze o pouzdro; pro úplný smykový spoj chybí odpovídající trn HSD-D.",
            "text": raw,
        }

    match = _FIRE_CRET_RE.search(raw)
    if match:
        return {
            "manufacturer": "Leviat",
            "family": "HSD-F",
            "base_family": "HSD-F",
            "size": match.group(1),
            "movement": "transverse" if match.group(2) else "axial",
            "decoder_only": True,
            "legacy_detail": "HSD-F je protipožární vložka, nikoli nosný smykový trn.",
            "text": raw,
        }
    match = _FIRE_SINGLE_RE.search(raw)
    if match:
        return {
            "manufacturer": "Leviat",
            "family": "HSD-F",
            "base_family": "HSD-F",
            "size": match.group(1),
            "movement": "transverse" if match.group(2) else "axial",
            "decoder_only": True,
            "legacy_detail": "HSD-F je protipožární vložka, nikoli nosný smykový trn.",
            "text": raw,
        }
    return None


def _capacity_payload(
    *, designation: str, family: str, size: int, vrd: float, slab_table_mm: int,
    gap_table_mm: int, concrete_table: str, movement: str, page: str, note: str,
    length_mm: int | None = None,
) -> dict[str, Any]:
    return {
        "manufacturer": "Leviat",
        "family": family,
        "size": str(size),
        "designation": designation,
        "vrd": float(vrd),
        "utilization": 0.0,
        "slab_table_mm": int(slab_table_mm),
        "gap_table_mm": int(gap_table_mm),
        "concrete_table": concrete_table,
        "movement": movement,
        "page": page,
        "source": SOURCE,
        "status": "KONTROLA VÝZTUŽE",
        "note": note,
        "length_mm": length_mm,
    }


def hsd_capacity(
    designation: str, *, slab_mm: float, gap_mm: float, concrete: str = "C25/30",
) -> tuple[dict[str, Any] | None, str]:
    info = decode_hsd(designation)
    if not info:
        return None, "Označení není Leviat / HALFEN HSD."
    if info.get("decoder_only"):
        return None, str(info.get("legacy_detail") or "Typ je určen pouze k dekódování.")

    family = str(info.get("base_family", ""))
    size = int(info.get("size") or 0)
    movement = str(info.get("movement", "unknown"))

    if family == "HSD-CRET":
        if size > 140:
            return None, "Pro HSD-CRET 145/150/155 nejsou v dodaném katalogu zveřejněny tabulkové únosnosti."
        concrete_table = _concrete_table(concrete)
        if concrete_table is None:
            return None, "HSD-CRET tabulky vyžadují beton minimálně C20/25."
        table = CRET_TRANSVERSE if movement == "transverse" else CRET_LONG
        rows = table[size][concrete_table]
        ht = _height_down(slab_mm, rows)
        gt = _gap_up(gap_mm, CRET_GAPS)
        if ht is None:
            return None, f"Tloušťka {slab_mm:g} mm je menší než katalogové minimum HSD-CRET {size}: {CRET_HMIN[size]} mm."
        if gt is None:
            return None, "HSD-CRET má v dodaném katalogu tabulky pouze do šířky spáry 60 mm."
        vrd = rows[ht][CRET_GAPS.index(gt)]
        note = (
            "Tabulková VRd bez interpolace. Pro C30/37 a vyšší je použita tabulka C25/30. "
            "Hodnota platí při předepsané závěsné a okrajové výztuži dle HSD EC 10-E; "
            "u varianty V je zohledněn podélný i příčný posun."
        )
        return _capacity_payload(
            designation=designation, family=info["family"], size=size, vrd=vrd,
            slab_table_mm=ht, gap_table_mm=gt, concrete_table=concrete_table,
            movement=movement, page="8" if movement == "transverse" else "7",
            note=note,
        ), ""

    if family == "HSD-D":
        if size not in SINGLE_SIZES:
            return None, "Nepodporovaný průměr HSD-D."
        strength = _strength(concrete)
        if strength is None or strength < 20:
            return None, "Tabulky HSD-D pro železobeton vyžadují beton minimálně C20/25."
        gt = _gap_up(gap_mm, SINGLE_GAPS)
        if gt is None:
            return None, "HSD-D má v dodaném katalogu tabulky pro železobeton pouze do šířky spáry 40 mm."
        concrete_rows = SINGLE_CONCRETE_TRANSVERSE if movement == "transverse" else SINGLE_CONCRETE_LONG
        rows = concrete_rows[size]
        ht = _height_down(slab_mm, rows)
        if ht is None:
            return None, (
                f"Pro HSD-D {size} ({'HSD-SV' if movement == 'transverse' else 'HSD-S/HSD-P'}) "
                f"není při h={slab_mm:g} mm v tabulce železobetonu zveřejněna číselná VRd,c."
            )
        steel_table = SINGLE_STEEL_TRANSVERSE if movement == "transverse" else SINGLE_STEEL_LONG
        vrd_s = steel_table[size][SINGLE_GAPS.index(gt)]
        vrd_c = rows[ht]
        vrd = min(vrd_s, vrd_c)
        note = (
            f"Železobeton, cnom = 30 mm; VRd = min(VRd,s={vrd_s:g}; VRd,c={vrd_c:g}) = {vrd:g} kN. "
            "Bez interpolace. Platí s předepsanou Asx/Asy a roztečemi dle HSD EC 10-E."
        )
        return _capacity_payload(
            designation=designation, family=info["family"], size=size, vrd=vrd,
            slab_table_mm=ht, gap_table_mm=gt, concrete_table=">= C20/25; cnom 30 mm",
            movement=movement, page="19-20", note=note, length_mm=SINGLE_LENGTH[size],
        ), ""

    return None, str(info.get("legacy_detail") or "Tento HSD typ nemá únosnost smykového trnu.")


def selftest() -> None:
    assert decode_hsd("HSD-CRET 124")["movement"] == "axial"
    assert decode_hsd("HSD-CRET-124 V")["movement"] == "transverse"
    assert decode_hsd("HSD-SET 22-A4")["movement"] == "axial"
    assert decode_hsd("HSD-SET 22 V-A4")["movement"] == "transverse"
    assert decode_hsd("HSD-D 22-A4 + HSD-S 22")["movement"] == "axial"
    assert decode_hsd("HSD-D 22-A4 + HSD-SV 22")["movement"] == "transverse"
    assert decode_hsd("HSD-D 22-FV + HSD-P 22")["movement"] == "axial"
    assert decode_hsd("HSD-D 22-A4")["decoder_only"] is True
    assert decode_hsd("HSD-CRET 150 V")["decoder_only"] is True

    c, e = hsd_capacity("HSD-CRET 124", slab_mm=280, gap_mm=30, concrete="C25/30")
    assert not e and c and c["vrd"] == 108.8
    c, e = hsd_capacity("HSD-CRET 124 V", slab_mm=280, gap_mm=30, concrete="C25/30")
    assert not e and c and c["vrd"] == 101.4
    c, e = hsd_capacity("HSD-CRET 122", slab_mm=200, gap_mm=10, concrete="C20/25")
    assert not e and c and c["vrd"] == 61.3
    c, e = hsd_capacity("HSD-CRET 124", slab_mm=280, gap_mm=30, concrete="C30/37")
    assert not e and c and c["vrd"] == 108.8 and c["concrete_table"] == "C25/30"
    c, e = hsd_capacity("HSD-CRET 124", slab_mm=270, gap_mm=15, concrete="C25/30")
    assert not e and c and c["vrd"] == 125.6 and c["slab_table_mm"] == 260 and c["gap_table_mm"] == 20
    c, e = hsd_capacity("HSD-SET 22-A4", slab_mm=240, gap_mm=30, concrete="C25/30")
    assert not e and c and c["vrd"] == 9.3
    c, e = hsd_capacity("HSD-SET 30 V-A4", slab_mm=320, gap_mm=20, concrete="C25/30")
    assert not e and c and c["vrd"] == 24.7
    c, e = hsd_capacity("HSD-SET 20 V-A4", slab_mm=160, gap_mm=10, concrete="C25/30")
    assert c is None and e
    c, e = hsd_capacity("HSD-CRET 150", slab_mm=650, gap_mm=20, concrete="C25/30")
    assert c is None and "145/150/155" in e


if __name__ == "__main__":
    selftest()
