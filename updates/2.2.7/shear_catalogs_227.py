from __future__ import annotations

"""TURTO 2.2.7 – current PohlCon and MAX FRANK shear-dowel catalog adapters.

The adapter intentionally keeps the original Ancon/Schöck engine untouched.
For products where the current manufacturer document publishes a product/steel
resistance separately from the concrete member resistance, the candidate is
returned as KONTROLA DESKY instead of pretending that the whole connection has
been verified.
"""

import re
from typing import Any, Iterable

import shear_dowels_catalog as _base

DowelCandidate = _base.DowelCandidate
TOL = _base.TOL

POHLCON_HED_SOURCE = "PohlCon / H-BAU Technik – Shear dowel HED, Technical information, current EN"
POHLCON_JDSD_SOURCE = "PohlCon – Double Shear Dowel JDSD/JDSDQ, Technical information, current EN"
MAXFRANK_EGCODORN_SOURCE = "MAX FRANK – Egcodorn® & Egcodubel, Shear force dowel for expansion joints, current INT/GB"
TARGET_MANUFACTURERS = ("Ancon", "Schöck", "PohlCon", "MAX FRANK")

_ORIGINAL_DECODE = _base.decode_dowel
_ORIGINAL_SUMMARY = _base.catalog_summary


def _strength(concrete: str) -> int | None:
    match = re.search(r"C\s*(\d+)\s*/", str(concrete or "").upper())
    return int(match.group(1)) if match else None


def _gap_up(actual: float, gaps: Iterable[int]) -> int | None:
    value = float(actual)
    return next((int(g) for g in sorted({int(x) for x in gaps}) if value <= int(g) + TOL), None)


def _height_down(actual: float, heights: Iterable[int]) -> int | None:
    value = float(actual)
    eligible = [int(h) for h in heights if int(h) <= value + TOL]
    return max(eligible) if eligible else None


def _candidate(
    manufacturer: str,
    family: str,
    size: str,
    designation: str,
    vrd: float,
    required: float,
    slab_table: int,
    gap_table: int,
    concrete_table: str,
    movement: str,
    page: str,
    source: str,
    *,
    status: str = "VYHOVUJE",
    note: str = "",
    length_mm: int | None = None,
) -> DowelCandidate:
    v = float(vrd)
    return DowelCandidate(
        manufacturer, family, str(size), designation, v,
        (abs(float(required)) / v if v > TOL else float("inf")),
        int(slab_table), int(gap_table), concrete_table, movement, page, source,
        status=status, note=note, length_mm=length_mm,
    )


# ---------------------------------------------------------------------------
# PohlCon HED – current Technical Information
# ---------------------------------------------------------------------------

HED_STEEL = {
    20: {10: 14.3, 20: 9.5, 30: 7.1, 40: 5.7},
    22: {10: 18.1, 20: 12.2, 30: 9.3, 40: 7.4},
    25: {10: 24.8, 20: 17.1, 30: 13.1, 40: 10.6},
    30: {10: 38.5, 20: 27.5, 30: 21.4, 40: 17.5},
}
HED_CONCRETE_C20 = {
    20: {160: 13.7, 180: 14.3},
    22: {160: 14.2, 180: 15.8, 200: 17.2, 220: 18.0, 240: 18.1},
    25: {180: 20.5, 200: 22.4, 220: 23.6, 240: 24.6, 260: 24.8},
    30: {220: 29.2, 240: 31.5, 260: 33.7, 280: 35.8, 300: 38.0, 320: 38.5},
}
HED_HMIN = {20: 160, 22: 160, 25: 180, 30: 220}
HED_LENGTH = {20: 300, 22: 300, 25: 300, 30: 350}
HED_GS_LENGTH = {20: 160, 22: 160, 25: 160, 30: 185}
HED_GSQ_LENGTH = {20: 180, 22: 180, 25: 180, 30: 205}


def _hed_rows(required_vrd: float, slab_mm: float, gap_mm: float, concrete: str, movement: str, low_sleeve: str) -> list[DowelCandidate]:
    strength = _strength(concrete)
    if strength is None or strength < 20:
        return []
    gt = _gap_up(gap_mm, (10, 20, 30, 40))
    if gt is None:
        return []
    transverse = str(movement) == "transverse"
    out: list[DowelCandidate] = []
    for size in (20, 22, 25, 30):
        if float(slab_mm) + TOL < HED_HMIN[size]:
            continue
        ht = _height_down(slab_mm, HED_CONCRETE_C20[size])
        if ht is None:
            continue
        steel = HED_STEEL[size][gt]
        concrete_cap = HED_CONCRETE_C20[size][ht]
        vrd = min(steel, concrete_cap)
        if vrd + TOL < abs(float(required_vrd)):
            continue
        if transverse:
            sleeve = f"GSQ {size}/{HED_GSQ_LENGTH[size]}"
            designation = f"PohlCon HED-S {size}/{HED_LENGTH[size]} + {sleeve}"
        elif str(low_sleeve) == "plastic":
            sleeve = f"GK {size}/{HED_GS_LENGTH[size]}"
            designation = f"PohlCon HED-S {size}/{HED_LENGTH[size]} + {sleeve}"
        else:
            sleeve = f"GS {size}/{HED_GS_LENGTH[size]}"
            designation = f"PohlCon HED-S {size}/{HED_LENGTH[size]} + {sleeve}"
        out.append(_candidate(
            "PohlCon", "HED-S", str(size), designation, vrd, required_vrd,
            ht, gt, "C20/25 – tabulka HED", "transverse" if transverse else "axial",
            "8–9", POHLCON_HED_SOURCE,
            note=(
                f"VRd = min(VRd,S={steel:g}; VRd,C={concrete_cap:g}) kN. "
                "Platí s předepsanou místní výztuží a minimálními vzdálenostmi dle aktuální TI HED."
            ),
            length_mm=HED_LENGTH[size],
        ))
    return out


# ---------------------------------------------------------------------------
# PohlCon JDSD/JDSDQ – product resistance from current Technical Information.
# Concrete/member verification remains explicitly open.
# ---------------------------------------------------------------------------

JDSD_SIZES = ("20 HF", "25 HF", "30 HF", "45 HF", "60 HF", "90 HF", "120 HF", "130", "150", "400", "450")
JDSD_Q_SIZES = ("25 HF", "30 HF", "45 HF", "60 HF", "90 HF", "120 HF", "130", "150", "400", "450")
JDSD_HMIN = {
    "20 HF": 160, "25 HF": 160, "30 HF": 180, "45 HF": 200, "60 HF": 240,
    "90 HF": 240, "120 HF": 280, "130": 350, "150": 450, "400": 600, "450": 650,
}
JDSDQ_HMIN = {**JDSD_HMIN, "25 HF": 170}
JDSD_VRD_S = {
    "20 HF": [51.6, 34.4, 25.8, 20.7, 17.2],
    "25 HF": [75.4, 51.4, 38.5, 30.8, 25.7],
    "30 HF": [103.2, 73.2, 54.9, 43.9, 36.6],
    "45 HF": [135.1, 100.4, 75.3, 60.2, 50.2],
    "60 HF": [171.2, 132.9, 100.2, 80.2, 66.8],
    "90 HF": [211.3, 169.5, 130.1, 104.1, 86.7],
    "120 HF": [356.3, 304.1, 251.8, 203.2, 169.4],
    "130": [260.0, 228.6, 197.3, 165.9, 138.4],
    "150": [389.4, 351.8, 314.2, 276.5, 238.9],
    "400": [619.1, 572.5, 525.9, 479.4, 432.8],
    "450": [996.5, 938.2, 880.0, 821.8, 763.5],
}
JDSDQ_VRD_S = {
    "25 HF": [67.8, 46.2, 34.7, 27.7, 23.1],
    "30 HF": [92.9, 65.8, 49.4, 39.5, 32.9],
    "45 HF": [121.6, 90.3, 67.7, 54.2, 45.2],
    "60 HF": [154.1, 119.6, 90.2, 72.1, 60.1],
    "90 HF": [190.2, 152.6, 117.1, 93.7, 78.0],
    "120 HF": [320.7, 273.7, 226.7, 182.9, 152.4],
    "130": [234.0, 205.8, 177.5, 149.3, 124.5],
    "150": [350.5, 316.6, 282.7, 248.9, 215.0],
    "400": [557.2, 515.3, 473.3, 431.4, 389.5],
    "450": [896.8, 844.4, 792.0, 739.6, 687.2],
}
_JDSD_GAPS = (20, 30, 40, 50, 60)


def _jdsd_rows(required_vrd: float, slab_mm: float, gap_mm: float, concrete: str, movement: str) -> list[DowelCandidate]:
    strength = _strength(concrete)
    if strength is None or strength < 20:
        return []
    transverse = str(movement) == "transverse"
    gt = _gap_up(gap_mm, _JDSD_GAPS)
    if gt is None:
        return []
    index = _JDSD_GAPS.index(gt)
    sizes = JDSD_Q_SIZES if transverse else JDSD_SIZES
    table = JDSDQ_VRD_S if transverse else JDSD_VRD_S
    hmin = JDSDQ_HMIN if transverse else JDSD_HMIN
    family = "JDSDQ" if transverse else "JDSD"
    out: list[DowelCandidate] = []
    for size in sizes:
        if float(slab_mm) + TOL < hmin[size]:
            continue
        vrd = float(table[size][index])
        if vrd + TOL < abs(float(required_vrd)):
            continue
        out.append(_candidate(
            "PohlCon", family, size, f"PohlCon {family} {size}", vrd, required_vrd,
            hmin[size], gt, "C20/25+; beton zvlášť", "transverse" if transverse else "axial",
            "9–11", POHLCON_JDSD_SOURCE,
            status="KONTROLA DESKY",
            note=(
                "Tabulovaná hodnota je VRd,S výrobku. Před konečným VYHOVUJE je nutné "
                "ověřit únosnost připojeného betonu, předepsanou výztuž, rozteče a okraje dle aktuální TI/zulassung JDSD."
            ),
        ))
    return out


def design_pohlcon(
    *, ved: float, slab_mm: float, gap_mm: float, concrete: str,
    movement: str = "axial", application: str = "new", low_sleeve: str = "stainless",
) -> tuple[list[DowelCandidate], str]:
    try:
        req = abs(float(ved))
    except Exception:
        return [], "Neplatná hodnota VEd."
    if req <= TOL:
        return [], "Zadejte VEd > 0 kN na jeden trn."
    movement = "transverse" if str(movement).lower() in {"transverse", "q", "příčný", "pricny"} else "axial"
    low_sleeve = "plastic" if str(low_sleeve).lower().startswith("plast") else "stainless"
    out = [
        *_hed_rows(req, slab_mm, gap_mm, concrete, movement, low_sleeve),
        *_jdsd_rows(req, slab_mm, gap_mm, concrete, movement),
    ]
    rank = {"HED-S": 0, "JDSD": 1, "JDSDQ": 1}
    out.sort(key=lambda c: (rank.get(c.family, 9), c.vrd, int(re.sub(r"\D", "", c.size) or 9999)))
    return out, "" if out else "V aktuálních tabulkách PohlCon HED/JDSD nebyl pro zadané VEd, h, spáru a pohyb nalezen použitelný typ."


# ---------------------------------------------------------------------------
# MAX FRANK Egcodorn WN/WQ and modular N/Q.
# ---------------------------------------------------------------------------

MF_EGCODORN_SIZES = (40, 50, 70, 95, 100, 120, 150, 210, 300, 350, 400)
MF_EGCODORN_HMIN = {40: 140, 50: 160, 70: 180, 95: 200, 100: 210, 120: 230, 150: 250, 210: 280, 300: 300, 350: 350, 400: 350}
_MF_GAPS = (10, 20, 30, 40, 50, 60)
MF_WN = {
    40:[62.0,58.9,54.5,40.9,32.7,27.3], 50:[89.4,85.3,72.2,54.5,43.6,36.3],
    70:[122.3,117.4,102.9,79.9,63.9,53.3], 95:[154.7,149.1,138.7,112.2,89.8,74.8],
    100:[155.8,150.6,145.7,136.9,110.5,92.0], 120:[241.5,224.4,194.1,163.8,134.1,111.7],
    150:[243.8,236.8,230.3,208.4,175.3,146.2], 210:[380.3,369.5,331.6,293.8,255.9,218.2],
    300:[382.1,373.0,364.4,331.9,292.1,252.4], 350:[388.0,380.2,372.7,365.6,358.7,352.0],
    400:[486.7,476.9,467.6,458.6,449.9,411.7],
}
MF_WQ = {
    40:[62.0,58.9,49.1,36.8,29.5,24.5], 50:[89.4,83.7,65.0,49.0,39.2,32.7],
    70:[122.3,113.9,92.6,71.9,57.5,47.9], 95:[154.7,148.6,124.8,100.9,80.8,67.4],
    100:[155.8,150.6,145.7,123.2,99.4,82.8], 120:[229.2,201.9,174.7,147.4,120.6,100.5],
    150:[243.8,236.8,217.3,187.5,157.7,131.5], 210:[366.6,332.6,298.5,264.4,230.3,196.4],
    300:[382.1,370.2,334.4,298.7,262.9,227.1], 350:[388.0,380.2,372.7,365.6,358.7,352.0],
    400:[486.7,476.9,467.6,455.7,413.2,370.6],
}


# Egcodubel – stainless EDM, high-strength core, current brochure.
MF_EGCDUBEL_SIZES = (20, 22, 27, 30, 37)
MF_EGCDUBEL_HMIN = {20:160, 22:180, 27:200, 30:220, 37:260}
MF_EGCDUBEL_LENGTH = {20:315, 22:340, 27:405, 30:445, 37:535}
MF_EGCDUBEL_HF_LONG = {
    20:[39.8,29.8,23.9,19.9,17.0,14.9],
    22:[51.1,39.0,31.5,26.4,22.7,20.0],
    27:[86.4,68.0,56.1,47.7,41.5,36.7],
    30:[112.2,89.8,74.8,64.1,56.1,49.9],
    37:[185.2,153.9,130.9,113.9,100.8,90.4],
}
MF_EGCDUBEL_HF_Q = {
    20:[35.8,26.8,21.5,17.9,15.3,13.4],
    22:[46.0,35.1,28.3,23.8,20.5,18.0],
    27:[77.7,61.2,50.5,42.9,37.4,33.1],
    30:[100.9,80.8,67.4,57.7,50.5,44.9],
    37:[166.7,138.5,117.8,102.5,90.7,81.4],
}


def _egcodubel_rows(required_vrd: float, slab_mm: float, gap_mm: float, concrete: str, movement: str) -> list[DowelCandidate]:
    strength = _strength(concrete)
    if strength is None or strength < 20:
        return []
    gt = _gap_up(gap_mm, _MF_GAPS)
    if gt is None:
        return []
    transverse = str(movement) == "transverse"
    table = MF_EGCDUBEL_HF_Q if transverse else MF_EGCDUBEL_HF_LONG
    idx = _MF_GAPS.index(gt)
    sleeve = "HQI" if transverse else "HI"
    out = []
    for size in MF_EGCDUBEL_SIZES:
        if float(slab_mm) + TOL < MF_EGCDUBEL_HMIN[size]:
            continue
        vrd = float(table[size][idx])
        if vrd + TOL < abs(float(required_vrd)):
            continue
        out.append(_candidate(
            "MAX FRANK", "Egcodubel", str(size),
            f"MAX FRANK Egcodubel EDM {size} HF {sleeve}",
            vrd, required_vrd, MF_EGCDUBEL_HMIN[size], gt,
            "C20/25+; beton zvlášť", "transverse" if transverse else "axial",
            "40–43", MAXFRANK_EGCODORN_SOURCE,
            status="KONTROLA DESKY",
            note=(
                "Použita tabulovaná produktová únosnost VRd,s pro EDM HF. "
                "Systémová VRd = min(VRd,s, VRd,C); beton, výztuž a kritické vzdálenosti je nutné ověřit dle aktuálního katalogu."
            ),
            length_mm=MF_EGCDUBEL_LENGTH[size],
        ))
    return out


def _egcodorn_rows(required_vrd: float, slab_mm: float, gap_mm: float, concrete: str, movement: str) -> list[DowelCandidate]:
    strength = _strength(concrete)
    if strength is None or strength < 20:
        return []
    gt = _gap_up(gap_mm, _MF_GAPS)
    if gt is None:
        return []
    transverse = str(movement) == "transverse"
    table = MF_WQ if transverse else MF_WN
    idx = _MF_GAPS.index(gt)
    out = []
    for size in MF_EGCODORN_SIZES:
        hmin = MF_EGCODORN_HMIN[size]
        if float(slab_mm) + TOL < hmin:
            continue
        vrd = float(table[size][idx])
        if vrd + TOL < abs(float(required_vrd)):
            continue
        if size == 400:
            family = "Q" if transverse else "N"
        else:
            family = "WQ" if transverse else "WN"
        designation = f"MAX FRANK Egcodorn® {family}{size}"
        out.append(_candidate(
            "MAX FRANK", family, str(size), designation, vrd, required_vrd,
            hmin, gt, "C20/25–C50/60; beton zvlášť",
            "transverse" if transverse else "axial",
            "11–18", MAXFRANK_EGCODORN_SOURCE,
            status="KONTROLA DESKY",
            note=(
                "Použita produktová únosnost VRd,s dle Z-15.7-301. "
                "Systémová VRd = min(VRd,s, VRd,rc); únosnost desky, místní výztuž, rozteče a okraje je nutné ověřit. "
                "Automatický návrh používá pouze standardní spáru z ≤ 60 mm."
            ),
        ))
    return out


def design_maxfrank(
    *, ved: float, slab_mm: float, gap_mm: float, concrete: str,
    movement: str = "axial", application: str = "new", low_sleeve: str = "stainless",
) -> tuple[list[DowelCandidate], str]:
    try:
        req = abs(float(ved))
    except Exception:
        return [], "Neplatná hodnota VEd."
    if req <= TOL:
        return [], "Zadejte VEd > 0 kN na jeden trn."
    movement = "transverse" if str(movement).lower() in {"transverse", "q", "příčný", "pricny"} else "axial"
    if str(application).lower() in {"existing_wall", "existing", "stávající"}:
        return [], (
            "MAX FRANK Egcodorn SWN/SWQ pro stěnové napojení vyžaduje samostatnou kontrolu tloušťky stěny a "
            "stěnové výztuže. Současný formulář má pouze h desky; automatický návrh proto z bezpečnostních důvodů není aktivní."
        )
    out = [
        *_egcodubel_rows(req, slab_mm, gap_mm, concrete, movement),
        *_egcodorn_rows(req, slab_mm, gap_mm, concrete, movement),
    ]
    rank = {"Egcodubel": 0, "WN": 1, "WQ": 1, "N": 1, "Q": 1}
    out.sort(key=lambda c: (rank.get(c.family, 9), c.vrd, int(re.sub(r"\D", "", c.size) or 9999)))
    return out, "" if out else "V aktuálním katalogu MAX FRANK Egcodubel/Egcodorn nebyl pro zadané VEd, h, spáru a pohyb nalezen standardní typ."


# ---------------------------------------------------------------------------
# Decoder and generic dispatch
# ---------------------------------------------------------------------------

_POHLCON_JDSD_RE = re.compile(r"(?:POHLCON\s+)?(JDSDQ|JDSD)\s*[- ]?\s*(20|25|30|45|60|90|120|130|150|400|450)(?:\s*HF)?", re.I)
_POHLCON_HED_RE = re.compile(r"(?:POHLCON\s+)?(HED-S|HED-P)\s*[- ]?\s*(20|22|25|30)(?:\s*/\s*(300|350|500))?(.*)", re.I)
_MF_EGCODORN_RE = re.compile(r"(?:(?:MAX\s*FRANK|EGCODORN(?:®)?)\s*)?(SWQ|SWN|WQ|WN)\s*[- ]?\s*(40|50|70|95|100|120|150|210|300|350|400)\b", re.I)
_MF_MODULAR_RE = re.compile(r"(?:MAX\s*FRANK|EGCODORN(?:®)?)\s*(Q|N)\s*[- ]?\s*(400)\b", re.I)
_MF_DND_RE = re.compile(r"(?:MAX\s*FRANK\s+)?(?:EGCODORN(?:®)?\s+)?DND\s*[- ]?\s*([A-Z0-9.-]+)?", re.I)
_MF_EGCDUBEL_RE = re.compile(r"(?:MAX\s*FRANK\s+)?(?:EGCODUBEL\s+)?(EDM|EDV)\s*[- ]?\s*(20|22|25|27|30|37)(?:\s+(HF|S355|S235))?(?:\s+(HQI|HI|H))?", re.I)


def decode_dowel(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    match = _POHLCON_JDSD_RE.search(raw)
    if match:
        family = match.group(1).upper()
        numeric = match.group(2)
        hf = numeric in {"20", "25", "30", "45", "60", "90", "120"}
        size = numeric + (" HF" if hf else "")
        return {
            "manufacturer": "PohlCon", "family": family, "base_family": "JDSD",
            "size": size, "movement": "transverse" if family == "JDSDQ" else "axial",
            "text": raw,
        }
    match = _POHLCON_HED_RE.search(raw)
    if match:
        family = match.group(1).upper()
        tail = str(match.group(4) or "").upper()
        if "GSQ" in tail:
            movement = "transverse"
        elif family == "HED-P" or any(token in tail for token in (" GS", "+GS", " GK", "+GK")):
            movement = "axial"
        else:
            movement = "unknown"
        return {
            "manufacturer": "PohlCon", "family": family, "base_family": "HED",
            "size": match.group(2), "suffix": match.group(3) or "",
            "movement": movement, "decoder_only": movement == "unknown",
            "legacy_detail": (
                "U HED-S určuje jednosměrné/obousměrné provedení použitá objímka GS/GK nebo GSQ."
                if movement == "unknown" else ""
            ),
            "text": raw,
        }

    match = _MF_EGCODORN_RE.search(raw)
    if match:
        family = match.group(1).upper()
        size = match.group(2)
        movement = "transverse" if family.endswith("Q") else "axial"
        decoder_only = family.startswith("SW")
        return {
            "manufacturer": "MAX FRANK", "family": family, "base_family": family,
            "size": size, "movement": movement, "decoder_only": decoder_only,
            "legacy_detail": (
                "SWN/SWQ je stěnová aplikace; pro automatickou statickou záměnu je nutná tloušťka stěny a její výztuž."
                if decoder_only else ""
            ),
            "text": raw,
        }
    match = _MF_MODULAR_RE.search(raw)
    if match:
        family = match.group(1).upper()
        return {
            "manufacturer": "MAX FRANK", "family": family, "base_family": family,
            "size": match.group(2), "movement": "transverse" if family == "Q" else "axial",
            "text": raw,
        }
    match = _MF_EGCDUBEL_RE.search(raw)
    if match:
        family = match.group(1).upper()
        material = (match.group(3) or "HF").upper()
        sleeve = (match.group(4) or "").upper()
        movement = "transverse" if sleeve == "HQI" else "axial"
        decoder_only = not sleeve
        return {
            "manufacturer": "MAX FRANK", "family": "Egcodubel", "base_family": family,
            "size": match.group(2), "material": material, "sleeve": sleeve,
            "movement": movement, "decoder_only": decoder_only,
            "legacy_detail": "U Egcodubel je pro záměnu nutné znát provedení objímky HI/HQI." if decoder_only else "",
            "text": raw,
        }
    if _MF_DND_RE.search(raw):
        return {
            "manufacturer": "MAX FRANK", "family": "DND", "base_family": "DND",
            "size": (_MF_DND_RE.search(raw).group(1) or "").strip(),
            "movement": "axial", "decoder_only": True,
            "legacy_detail": "Egcodorn DND je určen pro dynamické zatížení; automatická statická záměna není povolena.",
            "text": raw,
        }

    return _ORIGINAL_DECODE(raw)


def _pohlcon_capacity(designation: str, slab_mm: float, gap_mm: float, concrete: str) -> tuple[DowelCandidate | None, str]:
    info = decode_dowel(designation)
    if not info or info.get("manufacturer") != "PohlCon":
        return None, "Označení není PohlCon."
    movement = str(info.get("movement", "unknown"))
    if movement == "unknown":
        return None, "U HED-S není z označení určena objímka GS/GK/GSQ, a tedy ani směr posunu."
    family = str(info.get("family", ""))
    size = str(info.get("size", ""))
    if family.startswith("HED"):
        rows = _hed_rows(0.0, slab_mm, gap_mm, concrete, movement, "stainless")
        numeric = re.sub(r"\D", "", size)
        found = next((c for c in rows if c.size == numeric), None)
    else:
        rows = _jdsd_rows(0.0, slab_mm, gap_mm, concrete, movement)
        found = next((c for c in rows if c.size == size), None)
    if found is None:
        return None, "Pro zdrojový PohlCon trn nelze z dané geometrie určit katalogovou únosnost."
    return DowelCandidate(
        found.manufacturer, found.family, found.size, designation, found.vrd, 0.0,
        found.slab_table_mm, found.gap_table_mm, found.concrete_table, found.movement,
        found.page, found.source, status=found.status, note=found.note, length_mm=found.length_mm,
    ), ""


def _maxfrank_capacity(designation: str, slab_mm: float, gap_mm: float, concrete: str) -> tuple[DowelCandidate | None, str]:
    info = decode_dowel(designation)
    if not info or info.get("manufacturer") != "MAX FRANK":
        return None, "Označení není MAX FRANK."
    if info.get("decoder_only"):
        return None, str(info.get("legacy_detail") or "Tento typ vyžaduje doplňující technické údaje.")
    family = str(info.get("family", ""))
    movement = str(info.get("movement", "axial"))
    size = int(re.sub(r"\D", "", str(info.get("size", ""))) or 0)
    if family == "Egcodubel":
        rows = _egcodubel_rows(0.0, slab_mm, gap_mm, concrete, movement)
    else:
        rows = _egcodorn_rows(0.0, slab_mm, gap_mm, concrete, movement)
    found = next((c for c in rows if int(re.sub(r"\D", "", c.size) or 0) == size), None)
    if found is None:
        return None, "Pro zdrojový MAX FRANK trn nelze z dané geometrie určit katalogovou produktovou únosnost."
    return DowelCandidate(
        found.manufacturer, found.family, found.size, designation, found.vrd, 0.0,
        found.slab_table_mm, found.gap_table_mm, found.concrete_table, found.movement,
        found.page, found.source, status=found.status, note=found.note, length_mm=found.length_mm,
    ), ""


def capacity_from_designation(
    designation: str, *, slab_mm: float, gap_mm: float, concrete: str = "C25/30", cover_mm: int = 30,
) -> tuple[DowelCandidate | None, str]:
    info = decode_dowel(designation)
    if not info:
        return None, "Zdrojové označení smykového trnu nebylo rozpoznáno."
    manufacturer = str(info.get("manufacturer", ""))
    if manufacturer == "Ancon":
        value = _base.ancon_capacity_from_designation(designation, slab_mm, gap_mm, concrete)
        return value, "" if value else "Pro zdrojový Ancon nelze z dané geometrie určit katalogovou VRd."
    if manufacturer == "Schöck":
        value = _base.schock_capacity_from_designation(designation, slab_mm, gap_mm, cover_mm)
        return value, "" if value else "Pro zdrojový Schöck nelze z dané geometrie určit katalogovou VRd."
    if manufacturer == "PohlCon":
        return _pohlcon_capacity(designation, slab_mm, gap_mm, concrete)
    if manufacturer == "MAX FRANK":
        return _maxfrank_capacity(designation, slab_mm, gap_mm, concrete)
    return None, f"Výrobce {manufacturer or '—'} zatím nemá adaptér únosnosti."


def design_for_manufacturer(
    manufacturer: str, *, ved: float, slab_mm: float, gap_mm: float, concrete: str,
    movement: str = "axial", application: str = "new", low_sleeve: str = "stainless", cover_mm: int = 30,
) -> tuple[list[DowelCandidate], str]:
    label = str(manufacturer or "").strip().lower()
    if "sch" in label:
        return _base.design_schock(
            required_vrd=abs(float(ved)), slab_mm=slab_mm, gap_mm=gap_mm,
            movement=movement, cover_mm=cover_mm,
        )
    if "pohl" in label:
        return design_pohlcon(
            ved=ved, slab_mm=slab_mm, gap_mm=gap_mm, concrete=concrete,
            movement=movement, application=application, low_sleeve=low_sleeve,
        )
    if "max" in label or "frank" in label:
        return design_maxfrank(
            ved=ved, slab_mm=slab_mm, gap_mm=gap_mm, concrete=concrete,
            movement=movement, application=application, low_sleeve=low_sleeve,
        )
    return _base.design_ancon(
        ved=ved, slab_mm=slab_mm, gap_mm=gap_mm, concrete=concrete,
        movement=movement, application=application, low_sleeve=low_sleeve,
    )


def propose_substitution(
    *, source_designation: str, target_manufacturer: str, slab_mm: float, gap_mm: float,
    concrete: str = "C25/30", cover_mm: int = 30, low_sleeve: str = "stainless",
) -> tuple[DowelCandidate | None, DowelCandidate | None, str]:
    info = decode_dowel(source_designation)
    if not info:
        return None, None, "Zdrojové označení smykového trnu nebylo rozpoznáno."
    if info.get("decoder_only"):
        return None, None, str(info.get("legacy_detail") or "Zdrojový typ nemá dost údajů pro automatickou záměnu.")
    source, source_error = capacity_from_designation(
        source_designation, slab_mm=slab_mm, gap_mm=gap_mm,
        concrete=concrete, cover_mm=cover_mm,
    )
    if source is None:
        return None, None, source_error
    candidates, error = design_for_manufacturer(
        target_manufacturer,
        ved=source.vrd, slab_mm=slab_mm, gap_mm=gap_mm, concrete=concrete,
        movement=str(info.get("movement", source.movement)),
        application="new", low_sleeve=low_sleeve, cover_mm=cover_mm,
    )
    return (source, candidates[0], "") if candidates else (source, None, error)


def catalog_summary() -> str:
    return (
        "Ancon/Leviat: ED/ESD/HLD/DSD/DSDS/E-HLD • Schöck Stacon: LD/SLD • "
        "PohlCon: HED, JDSD/JDSDQ • MAX FRANK: Egcodubel, Egcodorn WN/WQ/N/Q; SWN/SWQ a DND v Dekodéru"
    )


def install_catalog_hooks() -> None:
    _base.decode_dowel = decode_dowel
    _base.catalog_summary = catalog_summary
    _base.propose_substitution = propose_substitution

    try:
        import shear_dowels_ui as ui0
        ui0.decode_dowel = decode_dowel
        ui0.catalog_summary = catalog_summary
        ui0.propose_substitution = propose_substitution
    except Exception:
        pass


def selftest() -> None:
    assert decode_dowel("PohlCon JDSDQ 60 HF")["movement"] == "transverse"
    assert decode_dowel("HED-S 25/300 + GSQ 25/180")["movement"] == "transverse"
    assert decode_dowel("HED-S 25/300 + GS 25/160")["movement"] == "axial"
    assert decode_dowel("MAX FRANK Egcodorn WQ120")["movement"] == "transverse"
    assert decode_dowel("Egcodorn WN 70")["manufacturer"] == "MAX FRANK"
    assert decode_dowel("MAX FRANK Egcodubel EDM 27 HF HQI")["movement"] == "transverse"
    assert decode_dowel("MAX FRANK Egcodorn DND 100")["decoder_only"] is True

    hed, err = design_pohlcon(ved=12.0, slab_mm=200, gap_mm=10, concrete="C25/30", movement="axial")
    assert not err and hed and hed[0].manufacturer == "PohlCon"
    assert hed[0].vrd >= 12.0

    mf, err = design_maxfrank(ved=30.0, slab_mm=200, gap_mm=20, concrete="C25/30", movement="axial")
    assert not err and mf and mf[0].manufacturer == "MAX FRANK"
    assert mf[0].vrd >= 30.0

    src, dst, err = propose_substitution(
        source_designation="PohlCon JDSD 60 HF", target_manufacturer="MAX FRANK",
        slab_mm=240, gap_mm=20, concrete="C25/30",
    )
    assert not err and src and dst and dst.manufacturer == "MAX FRANK"
    assert dst.vrd + TOL >= src.vrd


if __name__ == "__main__":
    selftest()
