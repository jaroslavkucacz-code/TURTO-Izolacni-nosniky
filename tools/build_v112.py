from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.1.1"
OUT = ROOT / "updates" / "1.1.2"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        raise RuntimeError(f"{label}: start marker not found: {start!r}")
    j = text.find(end, i + len(start))
    if j < 0:
        raise RuntimeError(f"{label}: end marker not found: {end!r}")
    return text[:i] + replacement + text[j:]


def compile_sources(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.suffix not in {".py", ".pyw"}:
            continue
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


LENGTH_HELPERS = r'''_STANDARD_LENGTHS: tuple[tuple[int, int], ...] = ((100, 1000), (50, 500), (33, 333), (25, 250))
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

    manufacturer = _ascii_upper(selection.get("manufacturer", ""))
    model = _ascii_upper(selection.get("model", ""))
    type_name = _ascii_upper(selection.get("type_name", ""))
    source = _ascii_upper(source_text)
    if (
        "MAX FRANK" in manufacturer
        and (model in {"M", "XL", "MM", "MXL"} or type_name.startswith(("MM", "MXL")))
    ) or ("EGCOBOX" in source and re.search(r"\b(?:MM|MXL)\d", source)):
        warning = (
            "délka zdrojového prvku nebyla v datech jednoznačná; použit předpoklad 1000 mm pro katalogovou matici "
            "Egcobox. Délku lze potvrdit přes Upravit zdroj / délku / tlak"
        )
        return 1000, "odhad 1000 mm", [warning]
    return None, "", []


def _target_length_options(source_length_mm: int, allowed_codes: set[int] | None = None) -> list[tuple[int, int]]:
    allowed = set(allowed_codes or {code for code, _length in _STANDARD_LENGTHS})
    return [(code, length) for code, length in _STANDARD_LENGTHS if code in allowed and length <= int(source_length_mm)]


'''


SOURCE_ACTIONS = r'''def _collect_source_actions(
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


'''


SOURCE_METADATA = r'''def _compression_category(value: Any) -> str:
    text = _ascii_upper(value)
    if not text or text in {"-", "—"} or "NEUVEDENO" in text or "DLE TYPU" in text:
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
    warnings = list(dict.fromkeys([*geometry_warnings, *length_warnings, *compression_warnings]))
    errors: list[str] = []
    if not series:
        errors.append("tloušťka izolantu musí být jednoznačně 80 mm (HIT-HP) nebo 120 mm (HIT-SP)")
    if cover not in {30, 35, 50}:
        errors.append("krytí musí být jednoznačně 30, 35 nebo 50 mm")
    if not height or height <= 0 or height % 10:
        errors.append("výška prvku musí být kladná a zadaná po 10 mm")
    if concrete is None:
        errors.append("zdrojový beton nelze přiřadit k C20/25, C25/30 nebo C30/37")
    if not length_mm:
        errors.append("délka původního prvku není jednoznačná")
    elif not _target_length_options(length_mm):
        errors.append(f"pro délku zdroje {length_mm} mm neexistuje shodná ani kratší standardní délka HIT")
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
        "warnings": warnings,
        "errors": errors,
    }


'''


CAPACITY_AND_DESIGN = r'''def _capacity_values(candidate: Candidate) -> tuple[float, float, float]:
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
    length_gap = max(0, int(source_length_mm) - int(candidate.physical_length_mm))
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
        return [], [f"není dostupná povolená délka HIT shodná nebo kratší než {source_length} mm (povoleno: {allowed_text or 'nic'})"]

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
                if candidate.physical_length_mm > source_length:
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
    return [target for _candidate, _actions, target in rows[:50]], list(dict.fromkeys(errors))


def calculation(
    candidate: Candidate,
    target_actions: DirectionalActions,
    source_totals: DirectionalActions,
    metadata: dict[str, Any],
) -> str:
    m_cap, v_cap, n_cap = _candidate_capacity_element(candidate)
    checks: list[str] = []
    for prefix, capacity, unit in (("m", m_cap, "kNm/prvek"), ("v", v_cap, "kN/prvek"), ("n", n_cap, "kN/prvek")):
        label, requirement = _direction_requirement(source_totals, prefix)
        if requirement <= _TOL:
            continue
        ratio = requirement / capacity if capacity > _TOL else float("inf")
        checks.append(f"{label} {fmt(requirement)}/{fmt(capacity)} {unit} = {fmt(ratio * 100.0)} %")
    if candidate.connection_type in {"MVX", "MVXL"} and max(target_actions.normalized().m_pos, target_actions.normalized().m_neg) > _TOL and max(target_actions.normalized().v_pos, target_actions.normalized().v_neg) > _TOL:
        checks.append(f"interakce M–V {fmt(candidate.utilization * 100.0)} %")
    source_length = int(metadata.get("source_length_mm") or 0)
    relation = "shodná délka" if source_length == candidate.physical_length_mm else "nejbližší kratší vyhovující délka"
    checks.append(f"L {source_length}→{candidate.physical_length_mm} mm ({relation})")
    checks.append(
        f"tlakový přenos: {_compression_label(str(metadata.get('source_compression_category', 'unknown')), str(metadata.get('source_compression_text', '')))} "
        f"→ {_candidate_compression_text(candidate)}"
    )
    checks.append(
        f"izolant {metadata.get('source_insulation_mm')} mm = HIT-{candidate.series}; "
        f"cnom {metadata.get('source_cover_mm')}→{candidate.cover} mm; h {metadata.get('source_height_mm')}→{candidate.height} mm"
    )
    return "; ".join(checks)


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
        "calculation": calculation(candidate, target_actions, source_totals, metadata),
    }


'''


EDIT_METHOD = r'''    def edit_substitution_source(self) -> None:
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


'''


DESIGN_METHOD = r'''    def design_substitutions(self, selected_only: bool) -> None:
        database = self._settings()
        if database is None:
            return
        selected = set(self.sub_tree.selection())
        if selected_only and not selected:
            messagebox.showinfo("Záměny za HIT", "Vyberte alespoň jeden řádek.", parent=self)
            return
        rows = [row for row in self.project.rows if not selected_only or str(row.get("id")) in selected]
        allowed_lengths = set(self.allowed_hit_lengths()) if hasattr(self, "allowed_hit_lengths") else {100, 50, 33, 25}
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
            if not allowed_lengths:
                fatal.append("v kartě Návrh HIT není povolena žádná délka")
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


'''


def patch_substitution(text: str) -> str:
    text = replace_once(text, 'import sys\nfrom dataclasses import replace', 'import sys\nimport unicodedata\nfrom dataclasses import replace', "unicodedata import")
    text = replace_once(text, 'SUBSTITUTION_MODULE_VERSION = "1.1.1"', 'SUBSTITUTION_MODULE_VERSION = "1.1.2"', "substitution version")
    text = replace_between(text, "def _source_element_width_m", "def _hint", LENGTH_HELPERS, "length helpers")
    text = replace_between(text, "def source_actions", "def action_values", SOURCE_ACTIONS, "source action conversion")
    text = replace_between(text, "def source_metadata", "def hit_type_order", SOURCE_METADATA, "source metadata and compression")
    text = replace_between(text, "def _capacity_values", "def selected_target", CAPACITY_AND_DESIGN, "length-aware candidate design")

    old_columns = '''        ("source_height", "h zdroj", 72, "center", False),
        ("target_height", "h HIT", 68, "center", False),
        ("source_concrete", "Beton", 86, "center", False),
        ("geometry", "Geometrie", 120, "center", False),
        ("m_pos", "M+", 70, "center", False), ("m_neg", "M−", 70, "center", False),
        ("n_pos", "N+", 70, "center", False), ("n_neg", "N−", 70, "center", False),
        ("v_pos", "V+", 70, "center", False), ("v_neg", "V−", 70, "center", False),
'''
    new_columns = '''        ("source_height", "h zdroj", 72, "center", False),
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
'''
    text = replace_once(text, old_columns, new_columns, "substitution columns")
    text = replace_once(text, '("target_m", "MRd,max", 82, "center", False),', '("target_m", "MRd / prvek", 92, "center", False),', "target moment header")
    text = replace_once(text, '("target_v", "VRd,max", 82, "center", False),', '("target_v", "VRd / prvek", 92, "center", False),', "target shear header")
    text = replace_once(text, '("target_n", "NRd", 76, "center", False),', '("target_n", "NRd / prvek", 92, "center", False),', "target normal header")

    text = replace_once(
        text,
        '                "Krytí, výška, beton a tloušťka izolantu se přebírají z původního prvku. "\n                "HIT-HP odpovídá izolantu 80 mm, HIT-SP izolantu 120 mm."',
        '                "Krytí, výška, beton, izolant, skutečná délka a vazba tlakových ložisek se přebírají z původního prvku. "\n                "Navrhuje se nejbližší shodná nebo kratší standardní délka HIT, která jako jeden prvek přenese stejnou únosnost."',
        "substitution subtitle",
    )
    text = replace_once(text, 'text="Upravit zdroj / geometrii"', 'text="Upravit zdroj / délku / tlak"', "edit button")
    text = replace_once(
        text,
        '                "Převádí se katalogová momentová, smyková a normálová únosnost, cnom, výška a izolant. "\n                "Požární odolnost REI se v této fázi vědomě neposuzuje a návrh neblokuje. "\n                "Únosnosti se porovnávají samostatně; u MVX/MVXL se navíc informativně kontroluje společný bod M–V."',
        '                "Převádí se katalogová momentová, smyková a normálová únosnost jednoho prvku, cnom, výška, izolant a délka. "\n                "HIT nesmí být delší než zdroj; z povolených délek se upřednostní nejbližší kratší vyhovující prvek. "\n                "Prvek s tlakovými ložisky se nahradí pouze HIT s tlakovými ložisky, prvek bez nich pouze provedením bez nich. "\n                "Požární odolnost REI se zatím neposuzuje."',
        "warning text",
    )

    text = replace_once(text, '        actions, action_warnings = source_actions(row)\n        values = action_values(actions)\n', '        actions, action_warnings = source_element_actions(row)\n        values = action_values(actions)\n', "payload source totals")
    old_payload_dimensions = '''            "source_height": (f"{meta.get('source_height_mm')} mm" if meta.get("source_height_mm") else ""),
            "target_height": (f"{target.get('height_mm')} mm" if target else (f"{meta.get('target_height_mm')} mm" if meta.get("target_height_mm") else "")),
            "source_concrete": str(meta.get("source_concrete", "")),
'''
    new_payload_dimensions = '''            "source_height": (f"{meta.get('source_height_mm')} mm" if meta.get("source_height_mm") else ""),
            "target_height": (f"{target.get('height_mm')} mm" if target else (f"{meta.get('target_height_mm')} mm" if meta.get("target_height_mm") else "")),
            "source_length": (f"{meta.get('source_length_mm')} mm" if meta.get("source_length_mm") else ""),
            "target_length": (f"{target.get('length_mm')} mm" if target and target.get("length_mm") else ""),
            "source_compression": str(meta.get("source_compression_text", "")),
            "target_compression": str(target.get("compression_text", "")) if target else "",
            "source_concrete": str(meta.get("source_concrete", "")),
'''
    text = replace_once(text, old_payload_dimensions, new_payload_dimensions, "payload length compression")
    old_caps = '''            "target_m": (fmt(float(target.get("m_capacity", 0.0))) if target and float(target.get("m_capacity", 0.0)) > _TOL else ""),
            "target_v": (fmt(float(target.get("v_capacity", 0.0))) if target and float(target.get("v_capacity", 0.0)) > _TOL else ""),
            "target_n": (fmt(float(target.get("n_capacity", 0.0))) if target and float(target.get("n_capacity", 0.0)) > _TOL else ""),
'''
    new_caps = '''            "target_m": (fmt(float(target.get("m_capacity_element", target.get("m_capacity", 0.0)))) if target and float(target.get("m_capacity_element", target.get("m_capacity", 0.0)) or 0.0) > _TOL else ""),
            "target_v": (fmt(float(target.get("v_capacity_element", target.get("v_capacity", 0.0)))) if target and float(target.get("v_capacity_element", target.get("v_capacity", 0.0)) or 0.0) > _TOL else ""),
            "target_n": (fmt(float(target.get("n_capacity_element", target.get("n_capacity", 0.0)))) if target and float(target.get("n_capacity_element", target.get("n_capacity", 0.0)) or 0.0) > _TOL else ""),
'''
    text = replace_once(text, old_caps, new_caps, "payload per-element capacities")

    text = replace_between(text, "    def edit_substitution_source", "    def next_substitution_variant", EDIT_METHOD, "edit source method")
    text = replace_between(text, "    def design_substitutions", "    def _output_rows", DESIGN_METHOD, "design method")
    return text


def patch_project_model(text: str) -> str:
    helper = r'''def _catalog_element_length_mm(result: QueryResult) -> int | None:
    containers = (result.record, result.family)
    keys_mm = ("element_length_mm", "unit_length_mm", "physical_length_mm", "length_mm", "element_width_mm", "width_mm")
    keys_m = ("element_length_m", "unit_length_m", "physical_length_m", "length_m", "element_width_m", "width_m")
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in keys_mm:
            value = container.get(key)
            if value in (None, "", "—"):
                continue
            match = re.search(r"\d+(?:[.,]\d+)?", str(value))
            if match:
                length = int(round(float(match.group(0).replace(",", "."))))
                if length > 0:
                    return length
        for key in keys_m:
            value = container.get(key)
            if value in (None, "", "—"):
                continue
            match = re.search(r"\d+(?:[.,]\d+)?", str(value))
            if match:
                length = int(round(float(match.group(0).replace(",", ".")) * 1000.0))
                if length > 0:
                    return length
    return None


'''
    text = replace_once(text, "def snapshot_from_result(result: QueryResult) -> dict[str, Any]:\n", helper + "def snapshot_from_result(result: QueryResult) -> dict[str, Any]:\n", "catalog length helper")
    text = replace_once(
        text,
        '        "compression_transfer":result.compression_transfer,\n',
        '        "compression_transfer":result.compression_transfer,\n        "element_length_mm":_catalog_element_length_mm(result),\n',
        "snapshot element length",
    )
    text = replace_once(
        text,
        '            "mapping":{"status":"not_run","targets":[],"selected_target_id":None,"source_meta":{},"warnings":[],"errors":[],"estimated_type":""}}\n',
        '            "mapping":{"status":"not_run","targets":[],"selected_target_id":None,"source_meta":{},"warnings":[],"errors":[],"estimated_type":"","source_overrides":{}}}\n',
        "new row source overrides",
    )
    text = replace_once(
        text,
        '    snap.setdefault("compression_transfer", "neuvedeno / dle typu")\n',
        '    snap.setdefault("compression_transfer", "neuvedeno / dle typu")\n    snap.setdefault("element_length_mm", None)\n',
        "legacy snapshot length",
    )
    text = replace_once(
        text,
        '        "estimated_type":str(raw_mapping.get("estimated_type","")),\n    }\n',
        '        "estimated_type":str(raw_mapping.get("estimated_type","")),\n        "source_overrides":dict(raw_mapping.get("source_overrides",{})) if isinstance(raw_mapping.get("source_overrides",{}),dict) else {},\n    }\n',
        "normalize source overrides",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise RuntimeError(f"Base update not found: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    substitution = OUT / "substitution_workspace.py"
    substitution.write_text(patch_substitution(substitution.read_text(encoding="utf-8")), encoding="utf-8")

    model = OUT / "project_model.py"
    model.write_text(patch_project_model(model.read_text(encoding="utf-8")), encoding="utf-8")

    app = OUT / "app.pyw"
    app.write_text(
        replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "1.1.1"', 'APP_VERSION = "1.1.2"', "app version"),
        encoding="utf-8",
    )

    compile_sources(OUT)

    sys.path.insert(0, str(OUT))
    import project_model as pm
    import substitution_workspace as sw
    from hit_core import Candidate

    source_row = {
        "source_text": "EGCOBOX MXL20-VS-C50-h200-REI120-SW - 0,93m",
        "note": "Délka prvku: 0,93 m",
        "selection": {
            "manufacturer": "MAX FRANK", "model": "XL", "type_name": "MXL",
            "cover": "C50", "height_mm": "200", "concrete_min": "C25/30",
        },
        "snapshot": {
            "designation": "Egcobox MXL20-VS-C50-h200",
            "insulation_thickness_mm": 120,
            "compression_transfer": "betonová tlaková ložiska",
            "results": [
                {"kind": "moment", "value": -21.4, "unit": "kNm/element"},
                {"kind": "shear", "value": 36.5, "unit": "kN/element"},
            ],
        },
        "mapping": {"source_overrides": {}},
    }
    meta = sw.source_metadata(source_row)
    assert meta["source_length_mm"] == 930 and not meta["errors"]
    assert meta["source_compression_category"] == "bearing"
    total, warnings = sw.source_element_actions(source_row)
    assert not [w for w in warnings if "nelze převést" in w]
    assert abs(total.m_neg - 21.4) < 1e-9 and abs(total.v_pos - 36.5) < 1e-9
    demand500, _ = sw.source_actions(source_row, 500)
    assert abs(demand500.m_neg - 42.8) < 1e-9 and abs(demand500.v_pos - 73.0) < 1e-9
    assert sw._target_length_options(930, {100, 50, 33, 25}) == [(50, 500), (33, 333), (25, 250)]

    with_bearing = Candidate("SP", "ZVX", "0402", 50, "06", 200, "C25/30", 0.0, 80.0, 0.0, 80.0, 1, 30, 200, 0.9, "test")
    without_bearing = Candidate("SP", "ZVX", "0400", 50, "06", 200, "C25/30", 0.0, 80.0, 0.0, 80.0, 1, 30, 200, 0.9, "test")
    assert sw._candidate_compression_category(with_bearing) == "bearing"
    assert sw._candidate_compression_category(without_bearing) == "without"
    assert sw._compression_compatible("bearing", with_bearing) and not sw._compression_compatible("bearing", without_bearing)
    assert sw._compression_compatible("without", without_bearing) and not sw._compression_compatible("without", with_bearing)
    assert sw._candidate_compression_category(Candidate("SP", "MVX", "0404", 100, "", 150, "C25/30", 20, 40, 25, 0, 1, 50, 200, 0.5, "test")) == "bearing"
    assert sw._candidate_compression_category(Candidate("SP", "DD", "0404", 100, "06", 200, "C25/30", 20, 40, 20, 40, 1, 50, 200, 0.5, "test")) == "without"

    class FakeDatabase:
        def __init__(self):
            self.calls: list[tuple[str, int, float]] = []

        def proposal_candidates(self, connection_type, series, height, cover, concrete, actions, lengths, include_offsets=False, load_distance_x=0.0):
            code = next(iter(lengths))
            self.calls.append((connection_type, code, float(actions.v_pos)))
            if connection_type != "MVX" or code != 50:
                return [], "bez záznamu", {"preferred_type": connection_type}
            utilization = max(actions.m_neg / 50.0, actions.v_pos / 80.0)
            candidate = Candidate("SP", "MVX", "0404", 50, "", 150, "C25/30", 50.0, 80.0, 55.0, 0.0, 1, 50, 200, utilization, "test")
            return ([candidate] if utilization <= 1.0 else []), "", {"preferred_type": connection_type}

    fake = FakeDatabase()
    targets, errors = sw.design_targets(fake, row=source_row, metadata=meta, allowed_length_codes={100, 50, 33, 25})
    assert targets, errors
    assert targets[0]["length_mm"] == 500
    assert abs(targets[0]["v_capacity_element"] - 40.0) < 1e-9
    assert abs(targets[0]["m_capacity_element"] - 27.5) < 1e-9
    assert "L 930→500 mm" in targets[0]["calculation"]
    assert all(code != 100 for _typ, code, _v in fake.calls)
    assert any(code == 50 and abs(v - 73.0) < 1e-9 for _typ, code, v in fake.calls)

    short_row = dict(source_row)
    short_row["mapping"] = {"source_overrides": {"source_length_mm": 200, "compression_category": "bearing"}}
    short_meta = sw.source_metadata(short_row)
    assert any("neexistuje" in error for error in short_meta["errors"])

    class Dummy:
        catalog = {"id": "c", "edition": "e", "publication_label": "p", "publication_date": "", "source_filename": ""}
        family = {"manufacturer": "MAX FRANK", "model": "XL", "type": "MXL", "generation": "g", "unit_length_mm": 500}
        record = {"moment_class": "MXL20", "concrete_min": "C25/30", "shear_class": "VS", "cover": "C50", "height_mm": "200"}
        designation = "Egcobox MXL20-VS-C50-h200"
        results = source_row["snapshot"]["results"]
        all_results_text = ""
        moment_text = ""
        shear_text = ""
        other_text = ""
        insulation_thickness_mm = 120
        insulation_text = "120 mm"
        compression_transfer = "betonová tlaková ložiska"
        source_pages = []

    snapshot = pm.snapshot_from_result(Dummy())
    assert snapshot["element_length_mm"] == 500
    project_row = pm.create_project_row(Dummy(), position="P001")
    project_row["mapping"]["source_overrides"] = {"source_length_mm": 930, "compression_category": "bearing"}
    normalized = pm.normalize_project_row(project_row)
    assert normalized["mapping"]["source_overrides"]["source_length_mm"] == 930

    generated = substitution.read_text(encoding="utf-8")
    assert 'SUBSTITUTION_MODULE_VERSION = "1.1.2"' in generated
    assert "Délka zdroje" in generated and "Tlakový přenos zdroj" in generated
    assert "candidate.physical_length_mm > source_length" in generated
    assert 'APP_VERSION = "1.1.2"' in app.read_text(encoding="utf-8")
    assert not any(OUT.rglob("*.pyc"))
    assert not any(p.name == "__pycache__" for p in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.1.2\n"
        "- Záměny za HIT nově pracují se skutečnou délkou původního prvku. Hodnoty /m se převádějí na celý zdrojový prvek a hodnoty /prvek zůstávají celkové.\n"
        "- Cílový HIT nikdy nesmí být delší než původní prvek. Z povolených standardních délek se jako první navrhne nejbližší shodná nebo kratší délka, která jako jeden prvek přenese požadovanou únosnost.\n"
        "- Pro kratší HIT se požadavek správně přepočítá na jeho vlastní délku; kontrola a tabulka zobrazují kapacity v kNm/prvek a kN/prvek.\n"
        "- Délka se čte ze strukturovaných katalogových dat, z označení L..., z dovětku 0,93 m / 1 m nebo z ručního upřesnění. Nejednoznačný předpoklad je označen ke kontrole.\n"
        "- Zachovává se vazba tlakových ložisek: zdroj s tlakovými ložisky smí nahradit jen HIT s CSB; zdroj bez tlakových ložisek jen HIT bez CSB / s tlačenými pruty.\n"
        "- U ZVX/ZDX se přítomnost tlakových ložisek určuje z počtu CSB v kódu prvku; MVX/MVXL jsou vedeny s CSB, DD/DVL/DDL/AT/FT/OTX bez tlakových ložisek.\n"
        "- Tabulka záměn a Excel export nově obsahují délku zdroje i HIT a tlakový přenos na obou stranách.\n"
        "- Dialog Upravit zdroj / délku / tlak umožňuje ručně potvrdit skutečnou délku a vazbu tlakových ložisek.\n",
        encoding="utf-8",
    )

    previous_manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    paths = [str(item["path"]) for item in previous_manifest.get("files", [])]
    manifest_files = []
    for rel in paths:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.1.2/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.1.2",
        "notes": "TURTO ISO: délkově správná záměna jeden prvek za jeden a zachování vazby tlakových ložisek.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.1.2")


if __name__ == "__main__":
    main()
