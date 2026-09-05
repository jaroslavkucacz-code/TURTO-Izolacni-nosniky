from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import replace
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from hit_core import Candidate, DirectionalActions, HitDatabase, fmt
from xlsx_export import write_xlsx
from substitution_pdf import write_substitution_pdf
from ui_utils import place_dialog_on_parent


SUBSTITUTION_MODULE_VERSION = "1.1.10"
_KEYS = ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg")
_LABELS = {
    "m_pos": "M+", "m_neg": "M−", "n_pos": "N+", "n_neg": "N−", "v_pos": "V+", "v_neg": "V−",
}
_FIXED_COVER = {"ZVX", "ZDX", "AT", "FT", "OTX"}
_TOL = 1e-9

# Tabulka záměn musí sama prověřit všechny standardní délky HIT.
# Zaškrtávače v kartě Návrh HIT jsou pouze filtrem ručního návrhu a nesmí
# blokovat automatickou záměnu, zejména potřebný přechod 300 → 333 mm.
SUBSTITUTION_LENGTH_CODES = frozenset({100, 50, 33, 25})


def _num(value: Any) -> float | None:
    if value in (None, "", "—", "-", "–"):
        return None
    try:
        return float(str(value).strip().replace("−", "-").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _unit(value: Any) -> str:
    return str(value or "").upper().replace(" ", "").replace("·", "").replace("−", "-")


def _per_m(kind: str, unit: Any) -> bool:
    value = _unit(unit)
    return value in ({"KNM/M", "KNM/M1"} if kind == "moment" else {"KN/M", "KN/M1"})


def _per_element(kind: str, unit: Any) -> bool:
    value = _unit(unit)
    return value in ({"KNM/ELEMENT", "KNM/ELEM", "KNM/PRVEK"} if kind == "moment" else {"KN/ELEMENT", "KN/ELEM", "KN/PRVEK"})


_STANDARD_LENGTHS: tuple[tuple[int, int], ...] = ((100, 1000), (50, 500), (33, 333), (25, 250))
_LENGTH_KEYS_MM = (
    "element_length_mm", "unit_length_mm", "physical_length_mm", "length_mm", "element_width_mm", "width_mm",
)
_LENGTH_KEYS_M = (
    "element_length_m", "unit_length_m", "physical_length_m", "length_m", "element_width_m", "width_m",
)


def _ascii_upper(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).upper().replace("−", "-").replace("–", "-")


def _parse_length_mm(value: Any, default_unit: str = "mm") -> int | None:
    if value in (None, "", "—", "-"):
        return None
    text = str(value).strip().replace("\u00a0", " ")
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    number = float(match.group(0).replace(",", "."))
    upper = _ascii_upper(text)
    if re.search(r"\bMM\b", upper):
        factor = 1.0
    elif re.search(r"\bCM\b", upper):
        factor = 10.0
    elif re.search(r"\bM\b", upper):
        factor = 1000.0
    else:
        factor = 1000.0 if default_unit == "m" else 1.0
    result = int(round(number * factor))
    return result if result > 0 else None


_VM_K_LENGTHS = {
    "VM": {24: 200, 43: 250, 65: 250, 86: 300, 108: 400, 130: 400, 151: 500, 200: 500},
    "VXL": {18: 200, 32: 250, 48: 300, 65: 300, 75: 400, 97: 400, 113: 500, 152: 510},
}
_VM_K_BIDIRECTIONAL_LENGTHS = {
    "VM": {24: 200, 43: 250, 65: 250, 86: 310, 108: 400, 130: 400, 151: 500, 200: 520},
    "VXL": {18: 200, 32: 250, 48: 300, 65: 310, 75: 400, 97: 400, 113: 500, 152: 530},
}


def _maxfrank_catalog_length_mm(selection: dict[str, Any], source_text: str) -> int | None:
    """Délka jednoho aktuálního prvku Egcobox podle katalogové řady.

    Používá přesné délkové řady z katalogů Egcobox M a XL. Složené rohové
    prvky CO se záměrně neodhadují, protože jejich dílčí prvky mají rozdílné
    délky a jeden společný převod by byl zavádějící.
    """
    manufacturer = _ascii_upper(selection.get("manufacturer", ""))
    model = _ascii_upper(selection.get("model", ""))
    type_name = _ascii_upper(selection.get("type_name", ""))
    moment_class = _ascii_upper(selection.get("moment_class", ""))
    shear_class = _ascii_upper(selection.get("shear_class", ""))
    source = _ascii_upper(source_text)
    joined = " ".join((model, type_name, moment_class, shear_class, source))
    if "MAX FRANK" not in manufacturer and "EGCOBOX" not in source:
        return None
    if re.search(r"(?:MM|MXL)\s*-?\s*CO\b", joined) or "-CO-" in joined:
        return None

    # Momentové prvky MM/MXL: běžné typy mají 1000 mm; všechny katalogové
    # K-prvky (např. MXL10-K, MXL80-K, MXL110-K) mají 500 mm.
    moment = re.search(r"\b(MXL|MM)\s*(\d{1,3})(?:\s*[±+/-]+)?(?:\s*-\s*K)?\b", joined)
    if moment:
        token_start, token_end = moment.span()
        nearby = joined[token_start : min(len(joined), token_end + 6)]
        number = int(moment.group(2))
        has_k = bool(re.search(r"-\s*K\b", nearby))
        if has_k or number == 10:
            return 500
        if 20 <= number <= 80:
            return 1000

    # Smykové řady VM/VXL bez K mají vždy délku 1000 mm. Krátké K-prvky
    # používají samostatné délkové tabulky; obousměrné ± mají u několika
    # stupňů odlišnou fyzickou délku, proto se rozlišují zvlášť.
    shear = re.search(r"\b(VXL|VM)\s*(?:Z\s*)?(\d{2,3})(?:\s*-\s*K)?\s*(?:±|\+/-|\+-)?", joined)
    if shear:
        family = shear.group(1)
        number = int(shear.group(2))
        token_start, token_end = shear.span()
        nearby = joined[max(0, token_start - 8) : min(len(joined), token_end + 8)]
        has_k = bool(re.search(r"-\s*K\b", nearby))
        if not has_k:
            return 1000
        bidirectional = "±" in nearby or "+/-" in nearby or "+-" in nearby or "±" in type_name
        table = _VM_K_BIDIRECTIONAL_LENGTHS if bidirectional else _VM_K_LENGTHS
        return table.get(family, {}).get(number)
    return None


def _source_element_length_info(row: dict[str, Any]) -> tuple[int | None, str, list[str]]:
    selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
    overrides = mapping.get("source_overrides") if isinstance(mapping.get("source_overrides"), dict) else {}

    override = _parse_length_mm(overrides.get("source_length_mm"), "mm")
    if override:
        return override, "ručně zadaná délka", []

    source_text = str(row.get("source_text") or snapshot.get("designation", ""))
    note = str(row.get("note", ""))
    combined = _ascii_upper(f"{source_text} | {note}")
    patterns = (
        r"(?:DELKA PRVKU|UNIT LENGTH|ELEMENT LENGTH|ELEMENTLAENGE)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(MM|CM|M)\b",
        r"(?:^|\s)-\s*(\d+(?:[.,]\d+)?)\s*(M)\s*(?=$|\|)",
    )
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            length = _parse_length_mm(match.group(1) + " " + match.group(2), match.group(2).lower())
            if length:
                return length, "délka z označení / poznámky", []
    l_code = re.search(r"(?:^|[-\s])L\s*(\d{3,4})(?=[-\s]|$)", _ascii_upper(source_text))
    if l_code:
        length = int(l_code.group(1))
        if length > 0:
            return length, "délka L z označení", []

    for container_name, container in (("katalogový záznam", snapshot), ("výběrová data", selection)):
        for key in _LENGTH_KEYS_MM:
            length = _parse_length_mm(container.get(key), "mm")
            if length:
                return length, f"{container_name}: {key}", []
        for key in _LENGTH_KEYS_M:
            length = _parse_length_mm(container.get(key), "m")
            if length:
                return length, f"{container_name}: {key}", []

    catalog_length = _maxfrank_catalog_length_mm(selection, source_text)
    if catalog_length:
        return catalog_length, "délka z katalogové řady Egcobox", []
    return None, "", []


def _length_is_allowed(source_length_mm: int, target_length_mm: int) -> bool:
    """Délková kompatibilita jednoho zdrojového prvku a jednoho HIT.

    Standardně nesmí být HIT delší než původní prvek. Výslovně povolenou
    výjimkou je zdrojový prvek délky 300 mm, který lze nahradit standardním
    HIT délky 333 mm. Únosnost se i v tomto případě kontroluje na celý prvek.
    """
    source = int(source_length_mm)
    target = int(target_length_mm)
    return target <= source or (source == 300 and target == 333)


def _length_relation_text(source_length_mm: int, target_length_mm: int) -> str:
    source = int(source_length_mm)
    target = int(target_length_mm)
    if source == target:
        return "shodná délka"
    if source == 300 and target == 333:
        return "povolená výjimka 300→333 mm"
    if target < source:
        return "nejbližší kratší vyhovující délka"
    return "nepřípustná delší délka"


def _target_length_options(source_length_mm: int, allowed_codes: set[int] | None = None) -> list[tuple[int, int]]:
    allowed = set(allowed_codes or {code for code, _length in _STANDARD_LENGTHS})
    return [
        (code, length)
        for code, length in _STANDARD_LENGTHS
        if code in allowed and _length_is_allowed(int(source_length_mm), length)
    ]


def _hint(record: dict[str, Any]) -> str:
    text = " ".join(str(record.get(k, "")) for k in ("label", "key", "note", "text")).upper().replace("−", "-")
    if "±" in text or "+/-" in text or "+-" in text:
        return "both"
    if any(x in text for x in ("NEGATIVE", "ZÁPORN", "ZAPORN", "M-", "V-", "N-")):
        return "neg"
    if any(x in text for x in ("POSITIVE", "KLADN", "M+", "V+", "N+")):
        return "pos"
    return ""


def _read_result(values: dict[str, float], prefix: str, record: dict[str, Any], factor: float = 1.0) -> None:
    positive = _num(record.get("positive"))
    negative = _num(record.get("negative"))
    if positive is not None or negative is not None:
        if positive is not None:
            values[prefix + "_pos"] = max(values[prefix + "_pos"], abs(positive) * factor)
        if negative is not None:
            values[prefix + "_neg"] = max(values[prefix + "_neg"], abs(negative) * factor)
        return
    value = _num(record.get("value"))
    if value is None:
        return
    value *= factor
    hint = _hint(record)
    if hint == "both":
        values[prefix + "_pos"] = max(values[prefix + "_pos"], abs(value))
        values[prefix + "_neg"] = max(values[prefix + "_neg"], abs(value))
    elif hint == "neg" or value < 0:
        values[prefix + "_neg"] = max(values[prefix + "_neg"], abs(value))
    elif value > 0:
        values[prefix + "_pos"] = max(values[prefix + "_pos"], abs(value))


def _collect_source_actions(
    row: dict[str, Any],
    *,
    per_m_factor: float,
    per_element_factor: float,
) -> tuple[DirectionalActions, list[str]]:
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    results = snapshot.get("results") if isinstance(snapshot.get("results"), list) else []
    values = {key: 0.0 for key in _KEYS}
    warnings: list[str] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        kind = str(result.get("kind", "")).lower()
        if kind not in {"moment", "shear", "normal"}:
            continue
        label = str(result.get("label") or result.get("key") or kind or "hodnota")
        if _per_m(kind, result.get("unit")):
            factor = per_m_factor
        elif _per_element(kind, result.get("unit")):
            factor = per_element_factor
        else:
            warnings.append(f"nelze převést: {label} [{result.get('unit') or 'bez jednotky'}]")
            continue
        _read_result(values, {"moment": "m", "shear": "v", "normal": "n"}[kind], result, factor)
    actions = DirectionalActions(**values)
    if not actions.has_any():
        warnings.append("nebyly nalezeny použitelné únosnosti M/N/V")
    return actions, list(dict.fromkeys(warnings))


def source_element_actions(row: dict[str, Any]) -> tuple[DirectionalActions, list[str]]:
    """Celkové katalogové únosnosti jednoho původního prvku."""
    length_mm, _origin, length_warnings = _source_element_length_info(row)
    if not length_mm:
        return DirectionalActions(), [*length_warnings, "chybí délka původního prvku"]
    actions, warnings = _collect_source_actions(
        row,
        per_m_factor=length_mm / 1000.0,
        per_element_factor=1.0,
    )
    return actions, list(dict.fromkeys([*length_warnings, *warnings]))


def source_actions(
    row: dict[str, Any],
    target_length_mm: int | None = None,
) -> tuple[DirectionalActions, list[str]]:
    """Požadované účinky na metr cílového HIT konkrétní délky.

    Hodnota zdroje uvedená na metr se nejprve převede na celkovou únosnost
    původního prvku. Hodnota uvedená na prvek je již celková. Obě se poté
    vydělí skutečnou délkou cílového HIT.
    """
    source_length_mm, _origin, length_warnings = _source_element_length_info(row)
    if not source_length_mm:
        return DirectionalActions(), [*length_warnings, "chybí délka původního prvku"]
    target_mm = int(target_length_mm or source_length_mm)
    if target_mm <= 0:
        return DirectionalActions(), ["cílová délka HIT musí být kladná"]
    actions, warnings = _collect_source_actions(
        row,
        per_m_factor=source_length_mm / target_mm,
        per_element_factor=1000.0 / target_mm,
    )
    return actions, list(dict.fromkeys([*length_warnings, *warnings]))


def action_values(actions: DirectionalActions) -> dict[str, float]:
    value = actions.normalized()
    return {key: float(getattr(value, key)) for key in _KEYS}


def action_text(actions: DirectionalActions) -> str:
    units = {"m": "kNm/m", "n": "kN/m", "v": "kN/m"}
    return " • ".join(
        f"{_LABELS[key]} {fmt(value)} {units[key[0]]}"
        for key, value in action_values(actions).items() if value > _TOL
    ) or "—"


def hit_concrete(value: str) -> str | None:
    match = re.search(r"C\s*(\d{2})\s*/\s*(\d{2})", str(value or "").upper())
    if not match or int(match.group(1)) < 20:
        return None
    strength = int(match.group(1))
    return "C20/25" if strength < 25 else ("C25/30" if strength < 30 else "C30/37")


def _source_cover(selection: dict[str, Any], source_text: str) -> int | None:
    raw = str(selection.get("cover", "")).upper().strip()
    match = re.fullmatch(r"(?:CNOM|CV|C)?\s*(\d{2,3})(?:\s*MM)?", raw)
    if match:
        return int(match.group(1))
    match = re.search(r"(?:^|[-\s])(?:CNOM|CV|C)\s*(\d{2,3})(?:[-\s/]|$)", source_text.upper())
    return int(match.group(1)) if match else None


def _source_height(selection: dict[str, Any], source_text: str) -> int | None:
    raw = str(selection.get("height_mm", "")).strip()
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    match = re.search(r"(?:^|[-\s])H\s*(\d{3})(?:[-\s]|$)", source_text.upper())
    return int(match.group(1)) if match else None


def _source_insulation(snapshot: dict[str, Any], source_text: str) -> int | None:
    value = _num(snapshot.get("insulation_thickness_mm"))
    if value and value > 0:
        return int(round(value))
    match = re.search(r"(?:IZOLANT|INSULATION|I)\s*[:=]?\s*(80|120)\s*MM", source_text.upper())
    return int(match.group(1)) if match else None


def _source_geometry(row: dict[str, Any], source_text: str) -> tuple[str, int | None, str, list[str]]:
    note = str(row.get("note", ""))
    combined = f"{source_text} | {note}"
    match = re.search(r"GEOMETRIE\s+([A-Z]{2,4})\s*:\s*(\d{2,4})\s*MM", combined, flags=re.I)
    if not match:
        # ISOPRO 120 zapisuje např. ``WU WD 220``; pro HIT jde o OU s bx = WD.
        match = re.search(r"(?:^|[-\s])(WU)\s+(?:WD\s*)?(\d{2,4})(?=[-\s]|$)", combined, flags=re.I)
    if not match:
        match = re.search(r"(?:^|[-\s])(WU|OU|OD|WD|WO|HVS|WOS|BHS|WUS|BH)\s*(\d{2,4})(?=[-\s]|$)", combined, flags=re.I)
    if not match:
        return "", None, "", []
    source_variant = match.group(1).upper()
    dimension = int(match.group(2))
    target_map = {"WU": "OU", "OU": "OU", "OD": "OD"}
    target_variant = target_map.get(source_variant, "")
    warnings: list[str] = []
    if not target_variant:
        warnings.append(f"geometrie {source_variant}{dimension} zatím nemá ověřené automatické přiřazení k HIT")
    display = f"{source_variant}{dimension}" + (f" → {target_variant}{dimension}" if target_variant else "")
    return target_variant, dimension, display, warnings


def _compression_category(value: Any) -> str:
    text = _ascii_upper(value)
    if not text or text in {"-", "—"} or "NEUVEDENO" in text or "DLE TYPU" in text:
        return "unknown"
    # Smíšený rohový nebo sestavný prvek může obsahovat současně ložiska i
    # tlačené pruty. Takový celek nelze bezpečně převést jednou binární volbou.
    bearing_hint = "COMPRESSION BEARING" in text or "PRESSURE BEARING" in text or ("TLAKOV" in text and "LOZISK" in text)
    bar_hint = any(pattern in text for pattern in ("TLACENE OCEL", "TLACENE PRUTY", "COMPRESSION BARS", "TENSION/COMPRESSION BARS"))
    if bearing_hint and bar_hint:
        return "unknown"
    without_patterns = (
        "BEZ TLAKOV", "BEZ CSB", "WITHOUT CSB", "NO CSB", "WITHOUT COMPRESSION BEARING",
        "NO COMPRESSION BEARING", "WITHOUT PRESSURE BEARING", "TLACENE OCEL", "TLACENE PRUTY",
        "COMPRESSION BARS", "TENSION/COMPRESSION BARS",
    )
    if any(pattern in text for pattern in without_patterns):
        return "without"
    if "CSB" in text or "COMPRESSION BEARING" in text or "PRESSURE BEARING" in text or ("TLAKOV" in text and "LOZISK" in text):
        return "bearing"
    if "LOZISK" in text and "BEZ" not in text:
        return "bearing"
    return "unknown"


def _compression_label(category: str, detail: str = "") -> str:
    if detail and _compression_category(detail) != "unknown":
        return detail
    return {
        "bearing": "s tlakovými ložisky",
        "without": "bez tlakových ložisek",
        "unknown": "neuvedeno",
    }.get(str(category), "neuvedeno")


def _manual_compression_category(value: Any) -> str | None:
    text = _ascii_upper(value).strip()
    if text in {"", "AUTO", "AUTOMATICKY"}:
        return ""
    if text in {"LOZISKA", "LOZISKO", "S LOZISKY", "S TLAKOVYMI LOZISKY", "BEARING", "CSB"}:
        return "bearing"
    if text in {"BEZ", "BEZ LOZISEK", "BEZ TLAKOVYCH LOZISEK", "WITHOUT", "NO CSB", "PRUTY", "TLACENE PRUTY"}:
        return "without"
    category = _compression_category(value)
    return category if category != "unknown" else None


def _source_compression(row: dict[str, Any], source_text: str) -> tuple[str, str, list[str]]:
    selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
    overrides = mapping.get("source_overrides") if isinstance(mapping.get("source_overrides"), dict) else {}
    override = str(overrides.get("compression_category", "")).strip()
    if override in {"bearing", "without"}:
        return override, _compression_label(override), []

    detail = str(snapshot.get("compression_transfer", "")).strip()
    category = _compression_category(detail)
    if category != "unknown":
        return category, _compression_label(category, detail), []

    typ = _ascii_upper(selection.get("type_name", ""))
    source = _ascii_upper(source_text)
    without_tokens = ("QP-Z", "IPZQ", "IPQZ", "A-IPZQ", "A-IPQZ")
    if any(token in typ or token in source for token in without_tokens):
        return "without", "bez tlakových ložisek – odhad z typu", ["tlakový přenos byl odhadnut z označení typu"]
    if any(token in typ for token in ("A-IPT", "A-IPTD", "A-IPTS", "A-IPTW", "DD", "DDL", "DVL")):
        return "without", "bez tlakových ložisek – tlačené pruty", ["tlakový přenos byl odhadnut z označení typu"]
    if typ in {"QL", "QP", "SKP", "SQP"}:
        return "bearing", "s tlakovými ložisky – odhad z typu", ["tlakový přenos byl odhadnut z označení typu"]
    if ("MAX FRANK" in _ascii_upper(selection.get("manufacturer", "")) or "EGCOBOX" in source) and re.search(r"\b(?:MM|MXL|VM|VXL)\d", source):
        return "bearing", "s tlakovými ložisky – odhad z typu Egcobox", ["tlakový přenos byl odhadnut z označení Egcobox"]
    return "unknown", "neuvedeno", []


def _candidate_compression_category(candidate: Candidate) -> str:
    typ = str(candidate.connection_type).upper()
    if typ in {"MVX", "MVXL"}:
        return "bearing"
    if typ in {"ZVX", "ZDX"}:
        _xx, csb = _code_parts(candidate)
        return "bearing" if csb > 0 else "without"
    if typ in {"DD", "DVL", "DDL", "AT", "FT", "OTX"}:
        return "without"
    return "unknown"


def _candidate_compression_text(candidate: Candidate) -> str:
    typ = str(candidate.connection_type).upper()
    category = _candidate_compression_category(candidate)
    if typ in {"MVX", "MVXL"}:
        return "s tlakovými ložisky (CSB)"
    if typ in {"ZVX", "ZDX"}:
        _xx, csb = _code_parts(candidate)
        return f"s tlakovými ložisky ({csb} CSB)" if csb > 0 else "bez tlakových ložisek (0 CSB)"
    if category == "without":
        return "bez tlakových ložisek – tlačené pruty"
    return "neuvedeno"


def _compression_compatible(source_category: str, candidate: Candidate) -> bool:
    target = _candidate_compression_category(candidate)
    if source_category == "unknown" or target == "unknown":
        return False
    return source_category == target


def _source_capacity_basis(row: dict[str, Any]) -> str:
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    results = snapshot.get("results") if isinstance(snapshot.get("results"), list) else []
    per_m = per_element = False
    for result in results:
        if not isinstance(result, dict):
            continue
        kind = str(result.get("kind", "")).lower()
        if kind not in {"moment", "shear", "normal"}:
            continue
        per_m = per_m or _per_m(kind, result.get("unit"))
        per_element = per_element or _per_element(kind, result.get("unit"))
    if per_m and per_element:
        return "smíšené hodnoty /m a /prvek; převedeno na jeden zdrojový prvek"
    if per_element:
        return "zdrojové únosnosti /prvek; porovnání jednoho prvku za jeden"
    if per_m:
        return "zdrojové únosnosti /m; převedeno přes skutečnou délku prvku"
    return ""


def source_metadata(row: dict[str, Any]) -> dict[str, Any]:
    selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    canonical = str(snapshot.get("designation", ""))
    source_text = str(row.get("source_text") or canonical).strip()
    insulation = _source_insulation(snapshot, source_text)
    series = "HP" if insulation == 80 else ("SP" if insulation == 120 else "")
    cover = _source_cover(selection, source_text)
    height = _source_height(selection, source_text)
    concrete = hit_concrete(str(selection.get("concrete_min", "")))
    geometry_target, geometry_bx, geometry_display, geometry_warnings = _source_geometry(row, source_text)
    length_mm, length_origin, length_warnings = _source_element_length_info(row)
    compression_category, compression_text, compression_warnings = _source_compression(row, source_text)
    policy = str(snapshot.get("substitution_policy", "automatic") or "automatic").strip().lower()
    policy_note = str(snapshot.get("substitution_note", "") or "").strip()
    warnings = list(dict.fromkeys([*geometry_warnings, *length_warnings, *compression_warnings]))
    errors: list[str] = []
    if policy in {"manual", "none", "disabled"}:
        errors.append(policy_note or "tento katalogový typ vyžaduje ruční technickou záměnu")
    elif policy == "review" and policy_note:
        warnings.append(policy_note)
    warnings = list(dict.fromkeys(warnings))
    if not series:
        errors.append("tloušťka izolantu musí být jednoznačně 80 mm (HIT-HP) nebo 120 mm (HIT-SP)")
    if cover not in {30, 35, 50}:
        errors.append("krytí musí být jednoznačně 30, 35 nebo 50 mm")
    if not height or height <= 0 or height % 10:
        errors.append("výška prvku musí být kladná a zadaná po 10 mm")
    if concrete is None:
        errors.append("zdrojový beton nelze přiřadit k C20/25, C25/30 nebo C30/37")
    if not length_mm:
        errors.append("délka původního prvku není jednoznačná; potvrďte ji přes Upravit zdroj / délku / tlak")
    elif not _target_length_options(length_mm):
        errors.append(f"pro délku zdroje {length_mm} mm neexistuje přípustná standardní délka HIT; u zdroje 300 mm je povolen také HIT 333 mm")
    if compression_category == "unknown":
        errors.append("není jednoznačné, zda je původní prvek s tlakovými ložisky, nebo bez nich")
    if geometry_target and geometry_bx is not None and series:
        maximum = 290 if series == "SP" else 330
        if not 175 <= geometry_bx <= maximum:
            errors.append(f"{geometry_target}{geometry_bx}: bx je mimo standardní rozsah 175–{maximum} mm pro HIT-{series}")
    return {
        "source_text": source_text,
        "canonical_designation": canonical,
        "manufacturer": str(selection.get("manufacturer", "")),
        "source_cover_mm": cover,
        "target_cover_mm": cover,
        "source_height_mm": height,
        "target_height_mm": height,
        "source_insulation_mm": insulation,
        "target_insulation_mm": insulation,
        "target_series": series,
        "source_concrete": str(selection.get("concrete_min", "")),
        "target_concrete": concrete,
        "source_length_mm": length_mm,
        "source_length_origin": length_origin,
        "target_length_options": [length for _code, length in _target_length_options(length_mm or 0)],
        "source_compression_category": compression_category,
        "source_compression_text": compression_text,
        "geometry_target": geometry_target,
        "geometry_bx_mm": geometry_bx,
        "geometry_display": geometry_display,
        "unit_basis": _source_capacity_basis(row),
        "substitution_policy": policy,
        "substitution_note": policy_note,
        "warnings": warnings,
        "errors": errors,
    }


def hit_type_order(actions: DirectionalActions, cover: int, geometry_target: str = "") -> tuple[str, ...]:
    a = actions.normalized()
    if geometry_target:
        return ("MVX",)
    if a.n_pos > _TOL or a.n_neg > _TOL:
        return ("AT", "FT") if a.n_pos <= _TOL else ("FT",)
    if a.m_pos > _TOL and a.m_neg > _TOL:
        return ("DDL", "DD") if a.v_neg > _TOL else ("DD", "DDL", "DVL")
    if a.m_pos > _TOL:
        return ("DDL", "DD") if a.v_neg > _TOL else ("DVL", "DD", "DDL")
    if a.m_neg > _TOL:
        return ("MVX", "DDL", "DD") if a.v_neg > _TOL else ("MVX", "DVL", "DD", "DDL")
    if a.v_neg > _TOL:
        return ("ZDX", "DDL", "DD") if cover == 30 else ("DDL", "DD")
    if a.v_pos > _TOL:
        return ("ZVX", "DVL", "DD", "DDL") if cover == 30 else ("DVL", "DD", "DDL")
    return ()


_EGCOBOX_MOMENT_CODE = {"20": "04", "25": "05", "35": "07", "50": "08"}


def _egcobox_estimated_type(metadata: dict[str, Any]) -> str:
    source = str(metadata.get("source_text") or metadata.get("canonical_designation") or "").upper()
    manufacturer = str(metadata.get("manufacturer", "")).upper()
    if "EGCOBOX" not in source and "MAX FRANK" not in manufacturer:
        return ""
    moment = re.search(r"\bMXL\s*(20|25|35|50)(?:-K)?(?:-|\b)", source)
    if not moment:
        return ""
    xx = _EGCOBOX_MOMENT_CODE.get(moment.group(1), "")
    cover = int(metadata.get("target_cover_mm") or 0)
    yy = ""
    if re.search(r"-V6(?:±|\+/-|\+-)?(?:-|\b)", source) or re.search(r"-VS(?:-|\b)", source):
        yy = "04"
    elif re.search(r"-V1(?:-|\b)", source):
        yy = "06" if cover == 30 else ("05" if cover == 50 else "")
    elif re.search(r"-V2(?:-|\b)", source):
        yy = "07" if cover == 50 else ""
    if not xx or not yy:
        return ""
    estimate = f"MVX-{xx}{yy}"
    geometry = str(metadata.get("geometry_target", ""))
    bx = int(metadata.get("geometry_bx_mm") or 0)
    if geometry and bx:
        estimate += f"-{geometry}{bx}"
    return estimate


def estimated_hit_type(metadata: dict[str, Any], actions: DirectionalActions) -> str:
    specific = _egcobox_estimated_type(metadata)
    if specific:
        return specific
    order = hit_type_order(
        actions,
        int(metadata.get("target_cover_mm") or 0),
        str(metadata.get("geometry_target", "")),
    )
    return order[0] if order else ""


def _designation_matches_estimate(designation: str, estimate: str) -> bool:
    match = re.search(r"MVX-(\d{4})", str(estimate).upper())
    if not match:
        return False
    if f"MVX-{match.group(1)}-" not in str(designation).upper():
        return False
    geometry = re.search(r"-(OU|OD)(\d+)$", str(estimate).upper())
    return not geometry or str(designation).upper().endswith(f"-{geometry.group(1)}{geometry.group(2)}")


def _capacity_values(candidate: Candidate) -> tuple[float, float, float]:
    return (
        max(abs(float(candidate.m1)), abs(float(candidate.m2))),
        max(abs(float(candidate.v1)), abs(float(candidate.v2))),
        abs(float(candidate.nrd)),
    )


def _candidate_capacity_element(candidate: Candidate) -> tuple[float, float, float]:
    m_cap, v_cap, n_cap = _capacity_values(candidate)
    factor = 1.0 if candidate.spacing_max > 0 else candidate.physical_length_mm / 1000.0
    return m_cap * factor, v_cap * factor, n_cap * factor


def _component_ratios(candidate: Candidate, actions: DirectionalActions) -> dict[str, float]:
    """Poměry v jednotkách na metr cílového HIT – pomocná kontrola jádra."""
    a = actions.normalized()
    m_req = max(a.m_pos, a.m_neg)
    v_req = max(a.v_pos, a.v_neg)
    n_req = max(a.n_pos, a.n_neg)
    m_cap, v_cap, n_cap = _capacity_values(candidate)

    def ratio(requirement: float, capacity: float) -> float:
        if requirement <= _TOL:
            return 0.0
        return requirement / capacity if capacity > _TOL else float("inf")

    return {"m": ratio(m_req, m_cap), "v": ratio(v_req, v_cap), "n": ratio(n_req, n_cap)}


def _element_ratios(candidate: Candidate, source_totals: DirectionalActions) -> dict[str, float]:
    """Kontrola jeden původní prvek za jeden konkrétní HIT."""
    a = source_totals.normalized()
    m_req = max(a.m_pos, a.m_neg)
    v_req = max(a.v_pos, a.v_neg)
    n_req = max(a.n_pos, a.n_neg)
    m_cap, v_cap, n_cap = _candidate_capacity_element(candidate)

    def ratio(requirement: float, capacity: float) -> float:
        if requirement <= _TOL:
            return 0.0
        return requirement / capacity if capacity > _TOL else float("inf")

    return {"m": ratio(m_req, m_cap), "v": ratio(v_req, v_cap), "n": ratio(n_req, n_cap)}


def _component_ok(candidate: Candidate, target_actions: DirectionalActions, source_totals: DirectionalActions) -> bool:
    per_m = _component_ratios(candidate, target_actions)
    per_element = _element_ratios(candidate, source_totals)
    if max([*per_m.values(), *per_element.values()]) > 1.0 + _TOL:
        return False
    return candidate.spacing_max <= 0 or candidate.spacing_max + _TOL >= 0.25


def _code_parts(candidate: Candidate) -> tuple[int, int]:
    match = re.match(r"^(\d{2})(\d{2})", str(candidate.code))
    return (int(match.group(1)), int(match.group(2))) if match else (999, 999)


def _overall_utilization(candidate: Candidate, target_actions: DirectionalActions, source_totals: DirectionalActions) -> float:
    values = [value for value in _element_ratios(candidate, source_totals).values() if value != float("inf")]
    values.extend(value for value in _component_ratios(candidate, target_actions).values() if value != float("inf"))
    values.append(max(0.0, float(candidate.utilization)))
    return max(values, default=0.0)


def _candidate_rank(
    candidate: Candidate,
    target_actions: DirectionalActions,
    source_totals: DirectionalActions,
    type_order: tuple[str, ...],
    source_length_mm: int,
    estimated_type: str = "",
) -> tuple[Any, ...]:
    try:
        type_index: float = float(type_order.index(candidate.connection_type))
    except ValueError:
        type_index = float(type_order.index("MVX")) + 0.5 if candidate.connection_type == "MVXL" and "MVX" in type_order else 99.0
    length_gap = abs(int(source_length_mm) - int(candidate.physical_length_mm))
    estimate_rank = 0 if _designation_matches_estimate(candidate.designation, estimated_type) else 1
    xx, yy = _code_parts(candidate)
    reinforcement = (xx + yy, yy, xx) if xx < 999 else (1998, yy, xx)
    return (
        length_gap,
        estimate_rank,
        type_index,
        *reinforcement,
        -_overall_utilization(candidate, target_actions, source_totals),
        candidate.designation,
    )


def _geometry_candidates(
    database: HitDatabase,
    actions: DirectionalActions,
    *,
    series: str,
    height: int,
    cover: int,
    concrete: str,
    target_variant: str,
    bx: int,
    length_code: int,
) -> tuple[list[Candidate], str]:
    rows, error = database.directional_candidates(
        "MVX", series, height, cover, concrete, actions, {length_code}, True, load_distance_x=0.0
    )
    selected: list[Candidate] = []
    for candidate in rows:
        if str(candidate.suffix).upper() != target_variant:
            continue
        selected.append(replace(
            candidate,
            suffix=f"{target_variant}{bx}",
            mode=f"{candidate.mode} • geometrie {target_variant}{bx}",
        ))
    return selected, error


def design_targets(
    database: HitDatabase,
    *,
    row: dict[str, Any],
    metadata: dict[str, Any],
    allowed_length_codes: set[int] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    series = str(metadata.get("target_series", ""))
    height = int(metadata.get("target_height_mm") or 0)
    cover = int(metadata.get("target_cover_mm") or 0)
    concrete = str(metadata.get("target_concrete", ""))
    source_length = int(metadata.get("source_length_mm") or 0)
    source_compression = str(metadata.get("source_compression_category", "unknown"))
    geometry_target = str(metadata.get("geometry_target", ""))
    geometry_bx = int(metadata.get("geometry_bx_mm") or 0)
    source_totals, total_warnings = source_element_actions(row)
    base_actions, base_warnings = source_actions(row)
    order = hit_type_order(base_actions, cover, geometry_target)
    estimate = estimated_hit_type(metadata, base_actions)
    errors: list[str] = [*total_warnings, *base_warnings]
    rows: list[tuple[Candidate, DirectionalActions, dict[str, Any]]] = []
    seen: set[str] = set()
    compression_rejected = 0

    length_options = _target_length_options(source_length, allowed_length_codes)
    if not length_options:
        allowed_text = ", ".join(str(length) for _code, length in _STANDARD_LENGTHS if not allowed_length_codes or _code in allowed_length_codes)
        return [], [f"není dostupná přípustná délka HIT pro zdroj {source_length} mm (standardně shodná/kratší; u zdroje 300 mm také 333 mm; povoleno: {allowed_text or 'nic'})"]

    for length_code, target_length in length_options:
        target_actions, target_warnings = source_actions(row, target_length_mm=target_length)
        errors.extend(target_warnings)
        if not target_actions.has_any():
            continue
        for connection_type in order:
            if connection_type in _FIXED_COVER and cover != 30:
                errors.append(f"{connection_type}: používá pevné cnom 30 mm, zdroj má {cover} mm")
                continue
            if geometry_target and connection_type != "MVX":
                continue
            if geometry_target:
                candidates, error = _geometry_candidates(
                    database,
                    target_actions,
                    series=series,
                    height=height,
                    cover=cover,
                    concrete=concrete,
                    target_variant=geometry_target,
                    bx=geometry_bx,
                    length_code=length_code,
                )
            else:
                target_cover = 30 if connection_type in _FIXED_COVER else cover
                candidates, error, _info = database.proposal_candidates(
                    connection_type,
                    series,
                    height,
                    target_cover,
                    concrete,
                    target_actions,
                    {length_code},
                    False,
                    load_distance_x=0.0,
                )
            if error and not candidates:
                errors.append(f"{connection_type} {target_length} mm: {error}")
                continue
            for candidate in candidates:
                if not _length_is_allowed(source_length, candidate.physical_length_mm):
                    continue
                if not _compression_compatible(source_compression, candidate):
                    compression_rejected += 1
                    continue
                if candidate.designation in seen or not _component_ok(candidate, target_actions, source_totals):
                    continue
                seen.add(candidate.designation)
                target = target_dict(candidate, target_actions, source_totals, metadata)
                rows.append((candidate, target_actions, target))

    if not rows and compression_rejected:
        errors.append("staticky vyhovující kandidáti neodpovídají vazbě s tlakovými ložisky / bez tlakových ložisek")
    rows.sort(
        key=lambda item: _candidate_rank(
            item[0], item[1], source_totals, order, source_length, estimate
        )
    )
    ordered_targets = [target for _candidate, _actions, target in rows]
    preferred_diameters = _diameter_representatives(ordered_targets, show_all=False)
    limited_targets: list[dict[str, Any]] = []
    seen_target_ids: set[str] = set()
    for target in [*preferred_diameters, *ordered_targets]:
        target_id = str(target.get("id"))
        if target_id in seen_target_ids:
            continue
        seen_target_ids.add(target_id)
        limited_targets.append(target)
        if len(limited_targets) >= 80:
            break
    return limited_targets, list(dict.fromkeys(errors))


def _direction_requirement(actions: DirectionalActions, prefix: str) -> tuple[str, float]:
    a = actions.normalized()
    pos = float(getattr(a, prefix + "_pos"))
    neg = float(getattr(a, prefix + "_neg"))
    symbol = prefix.upper()
    if pos > _TOL and neg > _TOL:
        label = symbol + ("±" if abs(pos - neg) <= _TOL else "+/−")
        return label, max(pos, neg)
    if pos > _TOL:
        return symbol + "+", pos
    if neg > _TOL:
        return symbol + "−", neg
    return symbol, 0.0


def _calculation_checks(candidate: Candidate, source_totals: DirectionalActions) -> list[dict[str, Any]]:
    m_cap, v_cap, n_cap = _candidate_capacity_element(candidate)
    capacities = {"m": m_cap, "n": n_cap, "v": v_cap}
    units = {"m": "kNm/prvek", "n": "kN/prvek", "v": "kN/prvek"}
    labels = {
        "m_pos": "M+", "m_neg": "M−", "n_pos": "N+", "n_neg": "N−", "v_pos": "V+", "v_neg": "V−",
    }
    actions = action_values(source_totals)
    checks: list[dict[str, Any]] = []
    for key in _KEYS:
        requirement = float(actions.get(key, 0.0) or 0.0)
        if requirement <= _TOL:
            continue
        capacity = float(capacities[key[0]])
        eta = requirement / capacity if capacity > _TOL else float("inf")
        checks.append({
            "label": labels[key],
            "requirement": requirement,
            "capacity": capacity,
            "unit": units[key[0]],
            "eta": eta,
            "result": "VYHOVUJE" if eta <= 1.0 + _TOL else "NEVYHOVUJE",
        })
    return checks


def calculation(
    candidate: Candidate,
    target_actions: DirectionalActions,
    source_totals: DirectionalActions,
    metadata: dict[str, Any],
) -> str:
    checks = _calculation_checks(candidate, source_totals)
    parts = [
        f"{check['label']}: {fmt(check['requirement'])}/{fmt(check['capacity'])} {check['unit']} = η {fmt(check['eta'] * 100.0)} % {check['result']}"
        for check in checks
    ]
    target_a = target_actions.normalized()
    if (
        candidate.connection_type in {"MVX", "MVXL"}
        and max(target_a.m_pos, target_a.m_neg) > _TOL
        and max(target_a.v_pos, target_a.v_neg) > _TOL
    ):
        parts.append(f"interakce M–V: η {fmt(candidate.utilization * 100.0)} %")
    source_length = int(metadata.get("source_length_mm") or 0)
    parts.append(f"L {source_length}→{candidate.physical_length_mm} mm ({_length_relation_text(source_length, candidate.physical_length_mm)})")
    source_pressure = _compression_label(
        str(metadata.get("source_compression_category", "unknown")),
        str(metadata.get("source_compression_text", "")),
    )
    parts.append(f"tlakový přenos: {source_pressure} → {_candidate_compression_text(candidate)}")
    parts.append(
        f"I {metadata.get('source_insulation_mm')}→{80 if candidate.series == 'HP' else 120} mm; "
        f"cnom {metadata.get('source_cover_mm')}→{candidate.cover} mm; h {metadata.get('source_height_mm')}→{candidate.height} mm"
    )
    return " | ".join(parts)


def target_dict(
    candidate: Candidate,
    target_actions: DirectionalActions,
    source_totals: DirectionalActions,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    per_m_ratios = _component_ratios(candidate, target_actions)
    element_ratios = _element_ratios(candidate, source_totals)
    m_cap, v_cap, n_cap = _capacity_values(candidate)
    m_element, v_element, n_element = _candidate_capacity_element(candidate)
    overall = _overall_utilization(candidate, target_actions, source_totals)
    return {
        "id": candidate.designation,
        "designation": candidate.designation,
        "connection_type": candidate.connection_type,
        "series": candidate.series,
        "target_insulation_mm": 80 if candidate.series == "HP" else 120,
        "cover_mm": candidate.cover,
        "height_mm": candidate.height,
        "concrete": candidate.concrete,
        "length_mm": candidate.physical_length_mm,
        "source_length_mm": int(metadata.get("source_length_mm") or 0),
        "length_relation": _length_relation_text(int(metadata.get("source_length_mm") or 0), candidate.physical_length_mm),
        "wire_diameter_mm": _candidate_wire_diameter(candidate),
        "compression_category": _candidate_compression_category(candidate),
        "compression_text": _candidate_compression_text(candidate),
        "utilization": overall,
        "interaction_utilization": float(candidate.utilization),
        "eta_m": float(element_ratios["m"]), "eta_v": float(element_ratios["v"]), "eta_n": float(element_ratios["n"]),
        "eta_m_per_m": float(per_m_ratios["m"]), "eta_v_per_m": float(per_m_ratios["v"]), "eta_n_per_m": float(per_m_ratios["n"]),
        "m_capacity": m_cap, "v_capacity": v_cap, "n_capacity": n_cap,
        "m_capacity_element": m_element, "v_capacity_element": v_element, "n_capacity_element": n_element,
        "spacing_max_m": float(candidate.spacing_max),
        "mode": candidate.mode,
        "page": candidate.page,
        "m1": float(candidate.m1), "v1": float(candidate.v1),
        "m2": float(candidate.m2), "v2": float(candidate.v2),
        "actions": action_values(target_actions),
        "source_element_actions": action_values(source_totals),
        "checks": _calculation_checks(candidate, source_totals),
        "calculation": calculation(candidate, target_actions, source_totals, metadata),
    }


def selected_target(mapping: dict[str, Any]) -> dict[str, Any] | None:
    targets = mapping.get("targets") if isinstance(mapping, dict) else []
    if not isinstance(targets, list):
        return None
    selected = str(mapping.get("selected_target_id") or "")
    if selected:
        for target in targets:
            if isinstance(target, dict) and str(target.get("id")) == selected:
                return target
    return next((target for target in targets if isinstance(target, dict)), None)



_WIRE_DIAMETERS = (6, 8, 10, 12)
_DIAMETER_TYPES = {"ZVX", "ZDX", "DD", "DVL", "DDL"}


def _wire_diameter_from_designation(designation: Any) -> int | None:
    matches = re.findall(r"(?:^|-)(06|08|10|12)(?=$|-)", str(designation or "").upper())
    return int(matches[-1]) if matches else None


def _candidate_wire_diameter(candidate: Candidate) -> int | None:
    suffix = str(candidate.suffix or "").strip()
    if suffix.isdigit() and int(suffix) in _WIRE_DIAMETERS:
        return int(suffix)
    return _wire_diameter_from_designation(candidate.designation)


def _target_wire_diameter(target: dict[str, Any] | None) -> int | None:
    if not isinstance(target, dict):
        return None
    try:
        value = int(target.get("wire_diameter_mm") or 0)
    except (TypeError, ValueError):
        value = 0
    return value if value in _WIRE_DIAMETERS else _wire_diameter_from_designation(target.get("designation"))


def _wire_diameter_text(target: dict[str, Any] | None) -> str:
    value = _target_wire_diameter(target)
    return f"Ø {value:02d}" if value else "—"


def _variant_overview(
    targets: list[dict[str, Any]],
    availability: dict[str, Any] | None = None,
) -> str:
    availability = availability if isinstance(availability, dict) else {}
    if availability:
        markers = []
        for diameter in _WIRE_DIAMETERS:
            status = availability.get(str(diameter), {})
            available = bool(status.get("available")) if isinstance(status, dict) else False
            markers.append(f"Ø{diameter:02d}{'✓' if available else '×'}")
        return f"{len(targets)} • " + " ".join(markers)
    diameters = sorted({value for value in (_target_wire_diameter(target) for target in targets) if value})
    suffix = "/".join(f"Ø{value:02d}" for value in diameters)
    return f"{len(targets)} ({suffix})" if suffix else str(len(targets))


def _diameter_representatives(
    targets: list[dict[str, Any]],
    *,
    current_id: str = "",
    show_all: bool = False,
) -> list[dict[str, Any]]:
    clean = [target for target in targets if isinstance(target, dict)]
    if show_all:
        return clean
    groups: dict[int, list[dict[str, Any]]] = {}
    for target in clean:
        diameter = _target_wire_diameter(target) or 999
        groups.setdefault(diameter, []).append(target)
    selected: list[dict[str, Any]] = []
    for diameter in sorted(groups, key=lambda value: (value == 999, value)):
        selected.append(groups[diameter][0])
    current = next((target for target in clean if str(target.get("id")) == str(current_id)), None)
    if current is not None and all(str(target.get("id")) != str(current.get("id")) for target in selected):
        selected.append(current)
    order = {str(target.get("id")): index for index, target in enumerate(clean)}
    selected.sort(key=lambda target: order.get(str(target.get("id")), 10**9))
    return selected


def _raw_zvx_compression_category(record: dict[str, Any]) -> str:
    code = str(record.get("code", "")).strip()
    match = re.match(r"^(\d{2})(\d{2})", code)
    if not match:
        return "unknown"
    return "bearing" if int(match.group(2)) > 0 else "without"


def _zvx_unavailable_diameter_reason(
    database: HitDatabase,
    diameter: int,
    metadata: dict[str, Any],
    source_totals: DirectionalActions,
    allowed_length_codes: set[int] | None,
) -> str:
    records = getattr(database, "zvx_records", None)
    if not isinstance(records, list) or not records:
        return "v načtených datech HIT není pro tento průměr ověřená katalogová varianta"

    series = str(metadata.get("target_series", ""))
    concrete = "C20/25" if str(metadata.get("target_concrete", "")) == "C20/25" else "C25/30"
    height = int(metadata.get("target_height_mm") or 0)
    source_length = int(metadata.get("source_length_mm") or 0)
    source_compression = str(metadata.get("source_compression_category", "unknown"))
    length_options = _target_length_options(source_length, allowed_length_codes)
    length_by_code = {code: length for code, length in length_options}
    length_text = "/".join(str(length) for _code, length in length_options) or "žádná"

    diameter_rows: list[tuple[dict[str, Any], int]] = []
    for record in records:
        try:
            length_code = int(record.get("length_code", 0))
            record_diameter = int(record.get("diameter", 0))
        except (TypeError, ValueError):
            continue
        if (
            str(record.get("series", "")) == series
            and str(record.get("concrete", "")) == concrete
            and length_code in length_by_code
            and record_diameter == int(diameter)
        ):
            diameter_rows.append((record, length_by_code[length_code]))

    if not diameter_rows:
        return f"v přípustných délkách {length_text} mm není katalogová varianta Ø{diameter:02d}"

    compression_rows = [
        (record, length)
        for record, length in diameter_rows
        if _raw_zvx_compression_category(record) == source_compression
    ]
    if not compression_rows:
        return "v přípustné délce existuje pouze provedení s jiným tlakovým přenosem"

    height_rows = [
        (record, length)
        for record, length in compression_rows
        if int(record.get("h_min", 0)) <= height <= int(record.get("h_max", 0))
    ]
    if not height_rows:
        minimum = min(int(record.get("h_min", 0)) for record, _length in compression_rows)
        maximum = max(int(record.get("h_max", 0)) for record, _length in compression_rows)
        if height < minimum:
            return f"katalogový rozsah pro přípustnou délku začíná na h = {minimum} mm; zdroj má h = {height} mm"
        if height > maximum:
            return f"katalogový rozsah pro přípustnou délku končí na h = {maximum} mm; zdroj má h = {height} mm"
        ranges = sorted({f"{int(record.get('h_min', 0))}–{int(record.get('h_max', 0))}" for record, _length in compression_rows})
        return f"výška h = {height} mm neleží v katalogových intervalech {', '.join(ranges)} mm"

    requirement = max(
        float(source_totals.normalized().v_pos),
        float(source_totals.normalized().v_neg),
    )
    best_record, best_length = max(
        height_rows,
        key=lambda item: abs(float(item[0].get("vrd", 0.0))) * item[1] / 1000.0,
    )
    capacity = abs(float(best_record.get("vrd", 0.0))) * best_length / 1000.0
    if capacity + _TOL < requirement:
        return (
            f"max. {fmt(capacity)} kN/prvek při L = {best_length} mm "
            f"je méně než požadovaných {fmt(requirement)} kN/prvek"
        )
    return "katalogový prvek splní dílčí smyk, ale byl vyloučen jinou technickou podmínkou"


def _diameter_availability(
    database: HitDatabase,
    targets: list[dict[str, Any]],
    metadata: dict[str, Any],
    source_totals: DirectionalActions,
    allowed_length_codes: set[int] | None,
) -> dict[str, dict[str, Any]]:
    clean = [target for target in targets if isinstance(target, dict)]
    target_types = {str(target.get("connection_type", "")).upper() for target in clean}
    if not (target_types & _DIAMETER_TYPES):
        return {}

    normalized = source_totals.normalized()
    pure_shear = (
        max(normalized.v_pos, normalized.v_neg) > _TOL
        and max(normalized.m_pos, normalized.m_neg, normalized.n_pos, normalized.n_neg) <= _TOL
    )
    result: dict[str, dict[str, Any]] = {}
    for diameter in _WIRE_DIAMETERS:
        candidates = [target for target in clean if _target_wire_diameter(target) == diameter]
        if candidates:
            result[str(diameter)] = {
                "available": True,
                "count": len(candidates),
                "best_id": str(candidates[0].get("id", "")),
                "reason": f"{len(candidates)} staticky a geometricky vyhovující varianta" + ("y" if len(candidates) != 1 else ""),
            }
            continue
        if pure_shear and ("ZVX" in target_types or "ZDX" in target_types):
            reason = _zvx_unavailable_diameter_reason(
                database, diameter, metadata, source_totals, allowed_length_codes
            )
        else:
            reason = "pro zadané M/N/V, délku, výšku a tlakový přenos není vyhovující varianta"
        result[str(diameter)] = {
            "available": False,
            "count": 0,
            "best_id": "",
            "reason": reason,
        }
    return result


def _diameter_availability_summary(availability: dict[str, Any] | None) -> str:
    availability = availability if isinstance(availability, dict) else {}
    if not availability:
        return ""
    parts = []
    for diameter in _WIRE_DIAMETERS:
        status = availability.get(str(diameter), {})
        if not isinstance(status, dict):
            continue
        if status.get("available"):
            parts.append(f"Ø{diameter:02d}: vyhovuje ({int(status.get('count', 0) or 0)} variant)")
        else:
            parts.append(f"Ø{diameter:02d}: ne – {status.get('reason', 'není vyhovující varianta')}")
    return "Dostupnost průměrů: " + " | ".join(parts) if parts else ""


class SubstitutionVariantsDialog(tk.Toplevel):
    """Výběr konkrétní vyhovující záměny, standardně po jednom kandidátu pro každý průměr drátu."""

    def __init__(self, parent: "SubstitutionWorkspaceMixin", targets: list[dict[str, Any]], current_id: str, diameter_availability: dict[str, Any] | None = None) -> None:
        super().__init__(parent)
        self.result: dict[str, Any] | None = None
        self._targets = [target for target in targets if isinstance(target, dict)]
        self._current_id = str(current_id or "")
        self._diameter_availability = diameter_availability if isinstance(diameter_availability, dict) else {}
        self._target_by_iid: dict[str, dict[str, Any]] = {}
        self.show_all_var = tk.BooleanVar(value=False)
        self.title("Vyhovující varianty záměny HIT")
        self.geometry("1480x650")
        self.minsize(1040, 500)
        self.transient(parent)
        place_dialog_on_parent(self, parent)
        self.grab_set()
        self.configure(background=parent.colors["bg"])
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)
        ttk.Label(outer, text="Vyhovující varianty záměny", style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=(
                "Základní pohled uvádí všechny průměry 06 / 08 / 10 / 12. Vyhovující varianty lze vybrat; šedé řádky vysvětlují, proč jiný průměr pro zadanou výšku, délku, únosnost nebo tlakový přenos dostupný není. "
                "Volbou Zobrazit všechny lze rozbalit všechny skutečně vyhovující délky, výztužné třídy a konstrukční typy."
            ),
            style="Muted.TLabel", wraplength=1400, justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Checkbutton(
            outer, text="Zobrazit všechny vyhovující varianty", variable=self.show_all_var, command=self._populate,
        ).grid(row=2, column=0, sticky="w", pady=(0, 8))

        frame = ttk.Frame(outer, style="Card.TFrame", padding=1)
        frame.grid(row=3, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = ("role", "diameter", "type", "designation", "length", "compression", "m", "v", "n", "util", "mode")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", style="Project.Treeview")
        headings = {
            "role": ("Volba", 130, "center"),
            "diameter": ("Ø drátu", 72, "center"),
            "type": ("Typ", 70, "center"),
            "designation": ("Vyhovující HIT", 360, "w"),
            "length": ("Délka", 75, "center"),
            "compression": ("Tlakový přenos", 200, "w"),
            "m": ("MRd / prvek", 100, "center"),
            "v": ("VRd / prvek", 100, "center"),
            "n": ("NRd / prvek", 100, "center"),
            "util": ("Využití", 82, "center"),
            "mode": ("Rozhodující kontrola", 285, "w"),
        }
        for column, (label, width, anchor) in headings.items():
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=52, anchor=anchor, stretch=column in {"designation", "mode"})
        ybar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        current_bg = parent.colors.get("select", "#DCEEF4")
        recommended_bg = "#FFF4D2" if getattr(parent, "theme_name", "light") == "light" else "#473D24"
        self.tree.tag_configure("current", background=current_bg)
        self.tree.tag_configure("diameter_best", background=recommended_bg)
        self.tree.tag_configure("unavailable", background=parent.colors.get("panel_alt", "#F3F6F9"), foreground=parent.colors.get("muted", "#6B7280"))
        self.tree.bind("<Double-1>", self._use_selected)
        self.tree.bind("<Return>", self._use_selected)

        actions = ttk.Frame(outer, style="App.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Zrušit", command=self.destroy).grid(row=0, column=1)
        ttk.Button(actions, text="Použít vybranou variantu", style="Accent.TButton", command=self._use_selected).grid(row=0, column=2, padx=(8, 0))
        self.bind("<Escape>", lambda _event: self.destroy())
        self._populate()

    @staticmethod
    def _capacity(target: dict[str, Any], key: str) -> str:
        value = float(target.get(key, 0.0) or 0.0)
        return fmt(value) if value > _TOL else "—"

    def _populate(self) -> None:
        previous = self.tree.selection()
        previous_id = ""
        if previous:
            old = self._target_by_iid.get(previous[0])
            previous_id = str(old.get("id")) if old else ""
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        self._target_by_iid.clear()

        displayed = _diameter_representatives(
            self._targets,
            current_id=self._current_id,
            show_all=bool(self.show_all_var.get()),
        )
        groups: dict[int, list[dict[str, Any]]] = {diameter: [] for diameter in _WIRE_DIAMETERS}
        without_diameter: list[dict[str, Any]] = []
        for target in displayed:
            diameter = _target_wire_diameter(target)
            if diameter in groups:
                groups[diameter].append(target)
            else:
                without_diameter.append(target)

        first_by_diameter: set[int] = set()
        selected_iid = ""
        row_index = 0
        for diameter in _WIRE_DIAMETERS:
            group = groups[diameter]
            if not group:
                status = self._diameter_availability.get(str(diameter), {})
                if self._diameter_availability:
                    iid = f"unavailable_{diameter}"
                    reason = str(status.get("reason") or "pro zadané podmínky není vyhovující varianta") if isinstance(status, dict) else "pro zadané podmínky není vyhovující varianta"
                    self.tree.insert(
                        "", "end", iid=iid, tags=("unavailable",),
                        values=(
                            "není vyhovující",
                            f"Ø {diameter:02d}",
                            "—", "—", "—", "—", "—", "—", "—", "—",
                            reason,
                        ),
                    )
                continue

            for target in group:
                iid = f"variant_{row_index}"
                row_index += 1
                self._target_by_iid[iid] = target
                target_id = str(target.get("id"))
                is_current = target_id == self._current_id
                is_best = diameter not in first_by_diameter
                first_by_diameter.add(diameter)
                role = "aktuálně vybraná" if is_current else ("doporučená pro Ø" if is_best else "další vyhovující")
                spacing = float(target.get("spacing_max_m", 0.0) or 0.0)
                utilization = f"a max {fmt(spacing, 3)} m" if spacing > 0 else f"{fmt(float(target.get('utilization', 0.0) or 0.0) * 100.0)} %"
                tags = ("current",) if is_current else (("diameter_best",) if is_best else ())
                self.tree.insert(
                    "", "end", iid=iid, tags=tags,
                    values=(
                        role,
                        _wire_diameter_text(target),
                        str(target.get("connection_type", "")),
                        str(target.get("designation", "")),
                        f"{target.get('length_mm', '—')} mm",
                        str(target.get("compression_text", "")),
                        self._capacity(target, "m_capacity_element"),
                        self._capacity(target, "v_capacity_element"),
                        self._capacity(target, "n_capacity_element"),
                        utilization,
                        str(target.get("mode", "")),
                    ),
                )
                if target_id == (previous_id or self._current_id):
                    selected_iid = iid

        for target in without_diameter:
            iid = f"variant_{row_index}"
            row_index += 1
            self._target_by_iid[iid] = target
            target_id = str(target.get("id"))
            is_current = target_id == self._current_id
            spacing = float(target.get("spacing_max_m", 0.0) or 0.0)
            utilization = f"a max {fmt(spacing, 3)} m" if spacing > 0 else f"{fmt(float(target.get('utilization', 0.0) or 0.0) * 100.0)} %"
            self.tree.insert(
                "", "end", iid=iid, tags=(("current",) if is_current else ()),
                values=(
                    "aktuálně vybraná" if is_current else "další vyhovující",
                    "—",
                    str(target.get("connection_type", "")),
                    str(target.get("designation", "")),
                    f"{target.get('length_mm', '—')} mm",
                    str(target.get("compression_text", "")),
                    self._capacity(target, "m_capacity_element"),
                    self._capacity(target, "v_capacity_element"),
                    self._capacity(target, "n_capacity_element"),
                    utilization,
                    str(target.get("mode", "")),
                ),
            )
            if target_id == (previous_id or self._current_id):
                selected_iid = iid

        children = self.tree.get_children("")
        if not selected_iid:
            selected_iid = next((iid for iid in children if iid in self._target_by_iid), "")
        if selected_iid:
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
            self.tree.see(selected_iid)

    def _use_selected(self, _event: Any = None) -> str | None:
        selected = self.tree.selection()
        if not selected:
            return "break"
        target = self._target_by_iid.get(selected[0])
        if target is None:
            reason = str(self.tree.set(selected[0], "mode") or "Pro zadané podmínky není tento průměr dostupný.")
            messagebox.showinfo("Průměr není vyhovující", reason, parent=self)
            return "break"
        self.result = target
        self.destroy()
        return "break"


class SubstitutionWorkspaceMixin:
    COLUMNS = (
        ("position", "Pozice", 78, "w", False),
        ("quantity", "Ks", 48, "center", False),
        ("manufacturer", "Původní výrobce", 120, "w", False),
        ("source", "Původní typ", 320, "w", True),
        ("source_insulation", "Izolant zdroje", 92, "center", False),
        ("target_series", "Řada HIT", 72, "center", False),
        ("source_cover", "cnom zdroj", 82, "center", False),
        ("target_cover", "cnom HIT", 78, "center", False),
        ("source_height", "h zdroj", 72, "center", False),
        ("target_height", "h HIT", 68, "center", False),
        ("source_length", "Délka zdroje", 92, "center", False),
        ("target_length", "Délka HIT", 82, "center", False),
        ("source_compression", "Tlakový přenos zdroj", 190, "w", False),
        ("target_compression", "Tlakový přenos HIT", 190, "w", False),
        ("source_concrete", "Beton", 86, "center", False),
        ("geometry", "Geometrie", 120, "center", False),
        ("m_pos", "M+ / prvek", 88, "center", False), ("m_neg", "M− / prvek", 88, "center", False),
        ("n_pos", "N+ / prvek", 88, "center", False), ("n_neg", "N− / prvek", 88, "center", False),
        ("v_pos", "V+ / prvek", 88, "center", False), ("v_neg", "V− / prvek", 88, "center", False),
        ("estimated_type", "Odhad typu", 86, "center", False),
        ("target_type", "HIT typ", 72, "center", False),
        ("wire_diameter", "Ø drátu", 72, "center", False),
        ("target", "Navržený HIT", 330, "w", True),
        ("target_m", "MRd / prvek", 92, "center", False),
        ("target_v", "VRd / prvek", 92, "center", False),
        ("target_n", "NRd / prvek", 92, "center", False),
        ("utilization", "Využití", 82, "center", False),
        ("alternatives", "Varianty / průměry", 220, "center", False),
        ("calculation", "Stručná statická kontrola", 580, "w", True),
        ("status", "Stav", 112, "center", False),
        ("note", "Poznámka / omezení", 320, "w", True),
    )

    def _init_substitution_workspace(self) -> None:
        self.sub_status_var = tk.StringVar(value="Připraveno k vytvoření tabulky záměn.")

    def _build_substitution_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        head = ttk.Frame(parent, style="Card.TFrame", padding=(16, 13))
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Tabulka záměn jiných výrobců za Leviat HIT", style="ProjectTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            head,
            text=(
                "Krytí, výška, beton, izolant, skutečná délka a vazba tlakových ložisek se přebírají z původního prvku. "
                "Standardně se navrhuje nejbližší shodná nebo kratší délka HIT; u zdroje 300 mm je přípustný také HIT 333 mm, pokud staticky vyhoví. "
                "Záměny automaticky prověřují všechny standardní délky HIT bez ohledu na zaškrtávače v kartě Návrh HIT. "
                "Délky aktuálních řad Egcobox MM/MXL a VM/VXL se určují přímo z katalogové třídy; neznámá délka návrh zastaví."
            ),
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        bar = ttk.Frame(parent, style="App.TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bar, text="Aktualizovat z projektu", command=self.refresh_substitution_tree).grid(row=0, column=0)
        ttk.Button(bar, text="Navrhnout vybrané", style="Accent.TButton", command=lambda: self.design_substitutions(True)).grid(row=0, column=1, padx=(7, 0))
        ttk.Button(bar, text="Navrhnout vše", command=lambda: self.design_substitutions(False)).grid(row=0, column=2, padx=(7, 0))
        ttk.Button(bar, text="Upravit zdroj / délku / tlak", command=self.edit_substitution_source).grid(row=0, column=3, padx=(7, 0))
        ttk.Button(bar, text="Vybrat variantu…", command=self.choose_substitution_variant).grid(row=0, column=4, padx=(7, 0))
        ttk.Button(bar, text="Kopírovat tabulku", command=self.copy_substitution_table).grid(row=0, column=5, padx=(7, 0))
        ttk.Button(bar, text="Export Excel", command=self.export_substitution_xlsx).grid(row=0, column=6, padx=(7, 0))
        ttk.Button(bar, text="Export PDF", style="Accent.TButton", command=self.export_substitution_pdf).grid(row=0, column=7, padx=(7, 0))
        bar.columnconfigure(20, weight=1)
        ttk.Label(bar, textvariable=self.sub_status_var, style="Muted.TLabel").grid(row=0, column=20, sticky="e")

        warning = ttk.Frame(parent, style="Warning.TFrame", padding=(12, 9))
        warning.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            warning,
            text=(
                "Převádí se katalogová momentová, smyková a normálová únosnost jednoho prvku, cnom, výška, izolant a délka. "
                "HIT standardně nesmí být delší než zdroj; výjimkou je zdroj 300 mm, který lze nahradit HIT 333 mm. Jinak se upřednostní nejbližší shodná nebo kratší vyhovující délka. "
                "Pro automatickou záměnu se vždy prověří délky 1000, 500, 333 a 250 mm; volby délek v ručním návrhu HIT se zde nepoužívají. "
                "Prvek s tlakovými ložisky se nahradí pouze HIT s tlakovými ložisky, prvek bez nich pouze provedením bez nich. "
                "Nejednoznačná délka ani smíšený tlakový přenos se neodhadují a návrh se zastaví. Požární odolnost REI se zatím neposuzuje."
            ),
            style="Warning.TLabel", wraplength=1500, justify="left",
        ).pack(anchor="w")

        card = ttk.Frame(parent, style="Card.TFrame", padding=(10, 10, 10, 8))
        card.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        frame = ttk.Frame(card, style="Card.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = tuple(item[0] for item in self.COLUMNS)
        self.sub_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended", style="Project.Treeview")
        for column, label, width, anchor, stretch in self.COLUMNS:
            self.sub_tree.heading(column, text=label)
            self.sub_tree.column(column, width=width, minwidth=42, anchor=anchor, stretch=stretch)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.sub_tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=self.sub_tree.xview)
        self.sub_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.sub_tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        self.sub_tree.tag_configure("odd", background=self.colors["panel_alt"])
        self.sub_tree.tag_configure("ok", foreground=self.colors["success"])
        self.sub_tree.tag_configure("review", foreground=self.colors["warning_text"])
        self.sub_tree.tag_configure("error", foreground=self.colors["danger"])
        self.sub_tree.bind("<Control-c>", lambda _event: self.copy_substitution_table())
        self.sub_tree.bind("<Double-1>", lambda _event: self.edit_substitution_source())
        self.sub_tree.bind("<Return>", lambda _event: self.choose_substitution_variant())
        self.refresh_substitution_tree()

    def _on_substitution_tab_selected(self, _event: Any = None) -> None:
        try:
            if str(self.main_notebook.select()) == str(self.substitution_tab):
                self.refresh_substitution_tree()
        except Exception:
            pass

    def _payload(self, row: dict[str, Any]) -> tuple[dict[str, Any], str]:
        selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
        mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
        actions, action_warnings = source_element_actions(row)
        values = action_values(actions)
        meta = source_metadata(row)
        stored_meta = mapping.get("source_meta") if isinstance(mapping.get("source_meta"), dict) else {}
        if stored_meta:
            meta = {**meta, **stored_meta}
        target = selected_target(mapping)
        status = str(mapping.get("status", "not_run"))
        status_text = {"not_run": "NEPOSOUZENO", "ok": "VYHOVUJE", "review": "KONTROLA", "error": "NELZE", "already_hit": "JIŽ HIT"}.get(status, status.upper())
        targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []
        diameter_availability = mapping.get("diameter_availability") if isinstance(mapping.get("diameter_availability"), dict) else {}
        utilization = ""
        calculation_text = ""
        if target:
            spacing = float(target.get("spacing_max_m", 0.0) or 0.0)
            utilization = ("a max " + fmt(spacing, 3) + " m") if spacing > 0 else fmt(100.0 * float(target.get("utilization", 0.0))) + " %"
            calculation_text = str(target.get("calculation", ""))
        warnings = list(action_warnings)
        warnings.extend(str(value) for value in meta.get("warnings", []) if str(value))
        warnings.extend(str(value) for value in mapping.get("warnings", []) if str(value))
        errors = [str(value) for value in mapping.get("errors", []) if str(value)]
        if status == "error" and mapping.get("selected_target_id"):
            errors.append(str(mapping.get("selected_target_id")))
        notes = list(dict.fromkeys([*errors, *warnings]))
        if meta.get("unit_basis"):
            notes.append(str(meta["unit_basis"]))
        return {
            "position": str(row.get("position", "")), "quantity": int(row.get("quantity", 1)),
            "manufacturer": str(selection.get("manufacturer", "")), "source": str(meta.get("source_text", "")),
            "source_insulation": (f"{meta.get('source_insulation_mm')} mm" if meta.get("source_insulation_mm") else ""),
            "target_series": (f"HIT-{meta.get('target_series')}" if meta.get("target_series") else ""),
            "source_cover": (f"{meta.get('source_cover_mm')} mm" if meta.get("source_cover_mm") else ""),
            "target_cover": (f"{target.get('cover_mm')} mm" if target else (f"{meta.get('target_cover_mm')} mm" if meta.get("target_cover_mm") else "")),
            "source_height": (f"{meta.get('source_height_mm')} mm" if meta.get("source_height_mm") else ""),
            "target_height": (f"{target.get('height_mm')} mm" if target else (f"{meta.get('target_height_mm')} mm" if meta.get("target_height_mm") else "")),
            "source_length": (f"{meta.get('source_length_mm')} mm" if meta.get("source_length_mm") else ""),
            "target_length": (f"{target.get('length_mm')} mm" if target and target.get("length_mm") else ""),
            "source_compression": str(meta.get("source_compression_text", "")),
            "target_compression": str(target.get("compression_text", "")) if target else "",
            "source_concrete": str(meta.get("source_concrete", "")),
            "geometry": str(meta.get("geometry_display", "")),
            **{key: (fmt(values[key]) if values[key] > _TOL else "") for key in _KEYS},
            "estimated_type": str(mapping.get("estimated_type", "")),
            "target_type": str(target.get("connection_type", "")) if target else "",
            "wire_diameter": _wire_diameter_text(target),
            "target": str(target.get("designation", "")) if target else "",
            "target_m": (fmt(float(target.get("m_capacity_element", target.get("m_capacity", 0.0)))) if target and float(target.get("m_capacity_element", target.get("m_capacity", 0.0)) or 0.0) > _TOL else ""),
            "target_v": (fmt(float(target.get("v_capacity_element", target.get("v_capacity", 0.0)))) if target and float(target.get("v_capacity_element", target.get("v_capacity", 0.0)) or 0.0) > _TOL else ""),
            "target_n": (fmt(float(target.get("n_capacity_element", target.get("n_capacity", 0.0)))) if target and float(target.get("n_capacity_element", target.get("n_capacity", 0.0)) or 0.0) > _TOL else ""),
            "utilization": utilization, "alternatives": _variant_overview(targets, diameter_availability), "calculation": calculation_text,
            "status": status_text, "note": " • ".join(dict.fromkeys(notes)),
        }, status

    def refresh_substitution_tree(self) -> None:
        if not hasattr(self, "sub_tree"):
            return
        selected = set(self.sub_tree.selection())
        for item in self.sub_tree.get_children(""):
            self.sub_tree.delete(item)
        mapped = 0
        for index, row in enumerate(self.project.rows):
            payload, status = self._payload(row)
            tags = ["odd"] if index % 2 else []
            if status in {"ok", "review", "error"}:
                tags.append(status)
            row_id = str(row.get("id"))
            self.sub_tree.insert("", "end", iid=row_id, values=tuple(payload[c] for c, *_ in self.COLUMNS), tags=tuple(tags))
            if status in {"ok", "review"}:
                mapped += 1
        valid = [row_id for row_id in selected if self.sub_tree.exists(row_id)]
        if valid:
            self.sub_tree.selection_set(valid)
        self.sub_status_var.set(f"{len(self.project.rows)} řádků projektu • {mapped} s návrhem HIT")

    def _settings(self) -> HitDatabase | None:
        database = getattr(self, "hit_db", None)
        if database is None and hasattr(self, "_try_load_hit_data"):
            try:
                self._try_load_hit_data()
            except Exception:
                pass
            database = getattr(self, "hit_db", None)
        if database is None:
            messagebox.showwarning("Data HIT", "Nejprve načtěte data v kartě Návrh HIT.", parent=self)
            return None
        return database

    @staticmethod
    def _already_hit(row: dict[str, Any]) -> bool:
        snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
        text = str(snapshot.get("designation", "")).upper()
        return "HIT-HP" in text or "HIT-SP" in text

    def edit_substitution_source(self) -> None:
        selected = list(self.sub_tree.selection()) if hasattr(self, "sub_tree") else []
        if len(selected) != 1:
            messagebox.showinfo("Zdrojový typ", "Vyberte právě jeden řádek.", parent=self)
            return
        row = self.project.row_by_id(selected[0])
        if row is None:
            return
        snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
        mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
        overrides = dict(mapping.get("source_overrides", {})) if isinstance(mapping.get("source_overrides"), dict) else {}
        initial = str(row.get("source_text") or snapshot.get("designation", ""))
        value = simpledialog.askstring(
            "Zdrojový typ / geometrie",
            "Původní označení použité pro převod (např. včetně WU280 a délky 0,93 m):",
            initialvalue=initial,
            parent=self,
        )
        if value is None:
            return
        preview = dict(row)
        preview["source_text"] = value.strip() or initial
        preview_mapping = dict(mapping)
        preview_mapping["source_overrides"] = overrides
        preview["mapping"] = preview_mapping
        preview_meta = source_metadata(preview)
        initial_length = int(overrides.get("source_length_mm") or preview_meta.get("source_length_mm") or 1000)
        length = simpledialog.askinteger(
            "Délka zdrojového prvku",
            "Skutečná délka jednoho původního prvku [mm]:",
            initialvalue=initial_length,
            minvalue=1,
            maxvalue=10000,
            parent=self,
        )
        if length is None:
            return
        current_category = str(overrides.get("compression_category") or preview_meta.get("source_compression_category") or "unknown")
        initial_compression = {"bearing": "ložiska", "without": "bez", "unknown": "auto"}.get(current_category, "auto")
        compression = simpledialog.askstring(
            "Tlakový přenos",
            "Zadejte: ložiska / bez / auto\n(bez zahrnuje i provedení s tlačenými pruty bez tlakových ložisek)",
            initialvalue=initial_compression,
            parent=self,
        )
        if compression is None:
            return
        category = _manual_compression_category(compression)
        if category is None:
            messagebox.showwarning("Tlakový přenos", "Použijte hodnotu ložiska, bez nebo auto.", parent=self)
            return
        overrides["source_length_mm"] = int(length)
        if category:
            overrides["compression_category"] = category
        else:
            overrides.pop("compression_category", None)
        row["source_text"] = value.strip() or initial
        row["mapping"] = {
            "status": "not_run", "targets": [], "selected_target_id": None,
            "source_meta": {}, "warnings": [], "errors": [], "estimated_type": "",
            "source_overrides": overrides,
        }
        self.project.touch()
        if hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.refresh_substitution_tree()
        if hasattr(self, "refresh_project_tree"):
            self.refresh_project_tree(select_ids=[str(row.get("id"))])
        self.sub_status_var.set("Zdroj, délka a tlakový přenos byly upraveny – spusťte Navrhnout vybrané.")


    def choose_substitution_variant(self) -> None:
        selected = list(self.sub_tree.selection()) if hasattr(self, "sub_tree") else []
        if len(selected) != 1:
            messagebox.showinfo("Varianta záměny", "Vyberte právě jeden řádek.", parent=self)
            return
        row = self.project.row_by_id(selected[0])
        if row is None:
            return
        mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
        targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []
        if not targets:
            messagebox.showinfo("Varianta záměny", "Řádek zatím nemá vyhovující návrh. Nejdříve spusťte Navrhnout vybrané.", parent=self)
            return
        dialog = SubstitutionVariantsDialog(
            self, targets, str(mapping.get("selected_target_id") or ""),
            mapping.get("diameter_availability") if isinstance(mapping.get("diameter_availability"), dict) else {},
        )
        self.wait_window(dialog)
        target = dialog.result
        if not target:
            return
        mapping["selected_target_id"] = str(target.get("id"))
        row["mapping"] = mapping
        self.project.touch()
        if hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.refresh_substitution_tree()
        if hasattr(self, "refresh_project_tree"):
            self.refresh_project_tree(select_ids=[str(row.get("id"))])
        diameter = _wire_diameter_text(target)
        self.sub_status_var.set(f"Použita varianta {diameter}: {target.get('designation', '')}")


    def next_substitution_variant(self) -> None:
        selected = list(self.sub_tree.selection()) if hasattr(self, "sub_tree") else []
        if len(selected) != 1:
            messagebox.showinfo("Varianta záměny", "Vyberte právě jeden řádek.", parent=self)
            return
        row = self.project.row_by_id(selected[0])
        if row is None:
            return
        mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
        targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []
        if len(targets) < 2:
            messagebox.showinfo("Varianta záměny", "Řádek nemá další vyhovující variantu.", parent=self)
            return
        current = str(mapping.get("selected_target_id") or "")
        index = next((i for i, target in enumerate(targets) if str(target.get("id")) == current), -1)
        target = targets[(index + 1) % len(targets)]
        mapping["selected_target_id"] = str(target.get("id"))
        row["mapping"] = mapping
        self.project.touch()
        if hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.refresh_substitution_tree()
        if hasattr(self, "refresh_project_tree"):
            self.refresh_project_tree(select_ids=[str(row.get("id"))])
        self.sub_status_var.set(f"Použita varianta: {target.get('designation', '')}")

    def design_substitutions(self, selected_only: bool) -> None:
        database = self._settings()
        if database is None:
            return
        selected = set(self.sub_tree.selection())
        if selected_only and not selected:
            messagebox.showinfo("Záměny za HIT", "Vyberte alespoň jeden řádek.", parent=self)
            return
        rows = [row for row in self.project.rows if not selected_only or str(row.get("id")) in selected]
        allowed_lengths = set(SUBSTITUTION_LENGTH_CODES)
        ok = review = failed = skipped = 0
        for row in rows:
            previous_mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
            overrides = dict(previous_mapping.get("source_overrides", {})) if isinstance(previous_mapping.get("source_overrides"), dict) else {}
            if self._already_hit(row):
                row["mapping"] = {
                    "status": "already_hit", "targets": [], "selected_target_id": None,
                    "source_overrides": overrides,
                }
                skipped += 1
                continue
            actions, action_warnings = source_actions(row)
            meta = source_metadata(row)
            fatal = list(meta.get("errors", []))
            if not actions.has_any():
                fatal.append("chybí použitelné momentové, smykové nebo normálové únosnosti")
            estimate = estimated_hit_type(meta, actions) if not fatal else ""
            order = hit_type_order(actions, int(meta.get("target_cover_mm") or 0), str(meta.get("geometry_target", ""))) if not fatal else ()
            if not order and not fatal:
                fatal.append("z účinků nelze odhadnout vhodnou rodinu HIT")
            if fatal:
                row["mapping"] = {
                    "status": "error", "targets": [], "selected_target_id": " | ".join(dict.fromkeys(fatal)),
                    "source_meta": meta, "warnings": action_warnings, "errors": fatal,
                    "estimated_type": estimate, "source_overrides": overrides,
                }
                failed += 1
                continue
            targets, errors = design_targets(
                database,
                row=row,
                metadata=meta,
                allowed_length_codes=allowed_lengths,
            )
            if not targets:
                message = " | ".join(errors[:8]) or "Bez vyhovujícího HIT při zachování délky, izolantu, cnom, výšky a tlakového přenosu."
                row["mapping"] = {
                    "status": "error", "targets": [], "selected_target_id": message,
                    "source_meta": meta, "warnings": action_warnings, "errors": errors,
                    "estimated_type": estimate or (order[0] if order else ""), "source_overrides": overrides,
                }
                failed += 1
                continue
            source_totals, _total_warnings = source_element_actions(row)
            diameter_availability = _diameter_availability(
                database, targets, meta, source_totals, allowed_lengths
            )
            warnings = list(dict.fromkeys([*action_warnings, *meta.get("warnings", [])]))
            if estimate.startswith("MVX-") and not _designation_matches_estimate(str(targets[0].get("designation", "")), estimate):
                warnings.append(f"odhad {estimate} nebyl staticky použitelný; použita nejbližší vyhovující varianta")
            row["mapping"] = {
                "status": "review" if warnings else "ok",
                "targets": targets,
                "selected_target_id": str(targets[0]["id"]),
                "source_meta": meta,
                "warnings": warnings,
                "errors": [],
                "estimated_type": estimate or order[0],
                "diameter_availability": diameter_availability,
                "source_overrides": overrides,
            }
            if warnings:
                review += 1
            else:
                ok += 1
        self.project.touch()
        if hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.refresh_substitution_tree()
        if hasattr(self, "refresh_project_tree"):
            self.refresh_project_tree()
        self.sub_status_var.set(f"Navrženo {ok} • ke kontrole {review} • nelze {failed} • již HIT {skipped}")


    def _pdf_report_rows(self) -> list[dict[str, Any]]:
        selected = set(self.sub_tree.selection()) if hasattr(self, "sub_tree") else set()
        report: list[dict[str, Any]] = []
        for row in self.project.rows:
            if selected and str(row.get("id")) not in selected:
                continue
            payload, _status_code = self._payload(row)
            mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
            meta = source_metadata(row)
            stored_meta = mapping.get("source_meta") if isinstance(mapping.get("source_meta"), dict) else {}
            if stored_meta:
                meta = {**meta, **stored_meta}
            source_actions_value, action_warnings = source_element_actions(row)
            target = selected_target(mapping)
            target_copy = dict(target) if isinstance(target, dict) else {}
            if target_copy:
                target_copy.setdefault("wire_diameter_mm", _target_wire_diameter(target_copy))
                target_copy.setdefault(
                    "length_relation",
                    _length_relation_text(int(meta.get("source_length_mm") or 0), int(target_copy.get("length_mm") or 0)),
                )
            notes: list[str] = []
            notes.extend(str(value) for value in mapping.get("errors", []) if str(value))
            notes.extend(str(value) for value in mapping.get("warnings", []) if str(value))
            notes.extend(str(value) for value in meta.get("warnings", []) if str(value))
            notes.extend(str(value) for value in action_warnings if str(value))
            diameter_summary = _diameter_availability_summary(
                mapping.get("diameter_availability") if isinstance(mapping.get("diameter_availability"), dict) else {}
            )
            if diameter_summary:
                notes.append(diameter_summary)
            if payload.get("note"):
                notes.extend(part.strip() for part in str(payload["note"]).split(" • ") if part.strip())
            report.append({
                "position": str(row.get("position", "")),
                "quantity": int(row.get("quantity", 1)),
                "manufacturer": str(payload.get("manufacturer", "")),
                "source": str(payload.get("source", "")),
                "source_meta": meta,
                "source_actions": action_values(source_actions_value),
                "estimated_type": str(mapping.get("estimated_type", "")),
                "target": target_copy,
                "status": str(payload.get("status", "NEPOSOUZENO")),
                "notes": list(dict.fromkeys(notes)),
            })
        return report

    def export_substitution_pdf(self) -> None:
        rows = self._pdf_report_rows()
        if not rows:
            messagebox.showinfo("Export PDF", "Není co exportovat.", parent=self)
            return
        name = re.sub(r'[\\/:*?"<>|]+', "_", str(self.project.name or "projekt")).strip() or "projekt"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Uložit profesionální výpočet záměn",
            defaultextension=".pdf",
            initialfile=f"Staticky_vypocet_zamen_HIT_{name}.pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        try:
            target = write_substitution_pdf(
                Path(path),
                project_name=str(self.project.name or "Projekt"),
                rows=rows,
                creator="Vytvořil Ing. Jaroslav Kučera",
            )
        except Exception as exc:
            messagebox.showerror("Export PDF se nezdařil", str(exc), parent=self)
            return
        self.sub_status_var.set(f"PDF výpočet exportován: {target.name}")
        try:
            if sys.platform == "win32":
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception:
            pass


    def _output_rows(self) -> list[dict[str, Any]]:
        selected = set(self.sub_tree.selection())
        rows = []
        for row in self.project.rows:
            if selected and str(row.get("id")) not in selected:
                continue
            rows.append(self._payload(row)[0])
        return rows

    def copy_substitution_table(self) -> str:
        rows = self._output_rows()
        if not rows:
            return "break"
        headers = [label for _, label, *_ in self.COLUMNS]
        ids = [column for column, *_ in self.COLUMNS]
        lines = ["\t".join(headers)]
        lines.extend("\t".join(str(row.get(column, "")).replace("\n", " ") for column in ids) for row in rows)
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.sub_status_var.set(f"Zkopírováno {len(rows)} řádků.")
        return "break"

    def export_substitution_xlsx(self) -> None:
        rows = self._output_rows()
        if not rows:
            messagebox.showinfo("Export", "Není co exportovat.", parent=self)
            return
        name = re.sub(r'[\\/:*?"<>|]+', "_", str(self.project.name or "projekt")).strip() or "projekt"
        path = filedialog.asksaveasfilename(
            parent=self, title="Uložit tabulku záměn", defaultextension=".xlsx",
            initialfile=f"Tabulka_zamen_HIT_{name}.xlsx", filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        headers = [label for _, label, *_ in self.COLUMNS]
        ids = [column for column, *_ in self.COLUMNS]
        target = write_xlsx(
            Path(path), headers=headers, rows=[[row.get(column, "") for column in ids] for row in rows],
            sheet_name="Tabulka záměn za HIT", creator="TURTO ISO – Vytvořil Ing. Jaroslav Kučera",
        )
        self.sub_status_var.set(f"Exportováno {len(rows)} řádků: {target.name}")
        try:
            if sys.platform == "win32":
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception:
            pass
