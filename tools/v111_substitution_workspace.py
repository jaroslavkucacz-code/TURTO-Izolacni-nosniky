from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from hit_core import Candidate, DirectionalActions, HitDatabase, fmt
from xlsx_export import write_xlsx


SUBSTITUTION_MODULE_VERSION = "1.1.1"
_KEYS = ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg")
_LABELS = {
    "m_pos": "M+", "m_neg": "M−", "n_pos": "N+", "n_neg": "N−", "v_pos": "V+", "v_neg": "V−",
}
_FIXED_COVER = {"ZVX", "ZDX", "AT", "FT", "OTX"}
_TOL = 1e-9


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


def _source_element_width_m(row: dict[str, Any]) -> float | None:
    """Šířka katalogového prvku pro přepočet hodnot /element na /m.

    Maticové katalogy MAX FRANK M/XL v této databázi reprezentují standardní
    jedno-metrový prvek. Případný projektový dovětek 0,93 m nebo 1 m je výrobní
    poznámka a nemění katalogovou hodnotu, kterou uživatel požaduje převést.
    """
    selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    for container in (snapshot, selection):
        for key in ("element_width_mm", "physical_length_mm", "width_mm"):
            value = _num(container.get(key))
            if value and value > 0:
                return value / 1000.0
    manufacturer = str(selection.get("manufacturer", "")).upper()
    model = str(selection.get("model", "")).upper()
    type_name = str(selection.get("type_name", "")).upper()
    if "MAX FRANK" in manufacturer and (model in {"M", "XL"} or type_name.startswith(("MM", "MXL"))):
        return 1.0
    return None


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


def source_actions(row: dict[str, Any]) -> tuple[DirectionalActions, list[str]]:
    """Převede katalogové únosnosti zdroje na požadavky pro srovnání s HIT.

    Přijímáme hodnoty na metr i hodnoty na prvek, pokud je šířka prvku známá.
    Pro MAX FRANK M/XL je v databázi znám standardní modul 1,0 m, takže čísla
    /element jsou číselně totožná s požadavkem /m.
    """
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    results = snapshot.get("results") if isinstance(snapshot.get("results"), list) else []
    values = {key: 0.0 for key in _KEYS}
    warnings: list[str] = []
    width_m = _source_element_width_m(row)
    for result in results:
        if not isinstance(result, dict):
            continue
        kind = str(result.get("kind", "")).lower()
        if kind not in {"moment", "shear", "normal"}:
            # Požár, teplo, tuhost a ostatní veličiny se v této fázi záměny
            # vědomě neposuzují a nesmí blokovat návrh.
            continue
        label = str(result.get("label") or result.get("key") or kind or "hodnota")
        factor: float | None
        if _per_m(kind, result.get("unit")):
            factor = 1.0
        elif _per_element(kind, result.get("unit")):
            factor = (1.0 / width_m) if width_m and width_m > 0 else None
        else:
            factor = None
        if factor is None:
            warnings.append(f"nelze převést: {label} [{result.get('unit') or 'bez jednotky'}] – chybí šířka prvku")
            continue
        _read_result(values, {"moment": "m", "shear": "v", "normal": "n"}[kind], result, factor)
    actions = DirectionalActions(**values)
    if not actions.has_any():
        warnings.append("nebyly nalezeny použitelné únosnosti M/N/V")
    return actions, list(dict.fromkeys(warnings))


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
    match = re.fullmatch(r"(?:CNOM|CV|C)?\s*(30|35|50)(?:\s*MM)?", raw)
    if match:
        return int(match.group(1))
    match = re.search(r"(?:^|[-\s])C(30|35|50)(?:[-\s]|$)", source_text.upper())
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
    warnings = list(geometry_warnings)
    errors: list[str] = []
    if not series:
        errors.append("tloušťka izolantu musí být jednoznačně 80 mm (HIT-HP) nebo 120 mm (HIT-SP)")
    if cover not in {30, 35, 50}:
        errors.append("krytí musí být jednoznačně 30, 35 nebo 50 mm")
    if not height or height <= 0 or height % 10:
        errors.append("výška prvku musí být kladná a zadaná po 10 mm")
    if concrete is None:
        errors.append("zdrojový beton nelze přiřadit k C20/25, C25/30 nebo C30/37")
    if geometry_target and geometry_bx is not None and series:
        maximum = 290 if series == "SP" else 330
        if not 175 <= geometry_bx <= maximum:
            errors.append(f"{geometry_target}{geometry_bx}: bx je mimo standardní rozsah 175–{maximum} mm pro HIT-{series}")
    width_m = _source_element_width_m(row)
    uses_element = any(
        isinstance(result, dict) and _per_element(str(result.get("kind", "")).lower(), result.get("unit"))
        for result in (snapshot.get("results") if isinstance(snapshot.get("results"), list) else [])
    )
    basis = ""
    if uses_element:
        basis = f"/element přepočteno přes šířku {fmt(width_m, 3)} m" if width_m else "/element – šířka neznámá"
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
        "geometry_target": geometry_target,
        "geometry_bx_mm": geometry_bx,
        "geometry_display": geometry_display,
        "unit_basis": basis,
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


def _capacity_values(candidate: Candidate) -> tuple[float, float, float]:
    return (
        max(abs(float(candidate.m1)), abs(float(candidate.m2))),
        max(abs(float(candidate.v1)), abs(float(candidate.v2))),
        abs(float(candidate.nrd)),
    )


def _component_ratios(candidate: Candidate, actions: DirectionalActions) -> dict[str, float]:
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


def _component_ok(candidate: Candidate, actions: DirectionalActions) -> bool:
    if candidate.spacing_max > 0:
        return candidate.spacing_max + _TOL >= 0.25
    return max(_component_ratios(candidate, actions).values()) <= 1.0 + _TOL


def _code_parts(candidate: Candidate) -> tuple[int, int]:
    match = re.match(r"^(\d{2})(\d{2})", str(candidate.code))
    return (int(match.group(1)), int(match.group(2))) if match else (999, 999)


def _overall_utilization(candidate: Candidate, actions: DirectionalActions) -> float:
    ratios = _component_ratios(candidate, actions)
    values = [value for value in ratios.values() if value != float("inf")]
    values.append(max(0.0, float(candidate.utilization)))
    return max(values, default=0.0)


def _candidate_rank(candidate: Candidate, actions: DirectionalActions, type_order: tuple[str, ...]) -> tuple[Any, ...]:
    try:
        type_index: float = float(type_order.index(candidate.connection_type))
    except ValueError:
        # MVXL je bezpečný fallback rodiny MVX.
        type_index = float(type_order.index("MVX")) + 0.5 if candidate.connection_type == "MVXL" and "MVX" in type_order else 99.0
    xx, yy = _code_parts(candidate)
    if xx < 999:
        reinforcement = (xx + yy, yy, xx)
    else:
        reinforcement = (1998, yy, xx)
    return (type_index, *reinforcement, -_overall_utilization(candidate, actions), candidate.designation)


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
) -> tuple[list[Candidate], str]:
    rows, error = database.directional_candidates(
        "MVX", series, height, cover, concrete, actions, {100}, True, load_distance_x=0.0
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
    actions: DirectionalActions,
    *,
    metadata: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    series = str(metadata.get("target_series", ""))
    height = int(metadata.get("target_height_mm") or 0)
    cover = int(metadata.get("target_cover_mm") or 0)
    concrete = str(metadata.get("target_concrete", ""))
    geometry_target = str(metadata.get("geometry_target", ""))
    geometry_bx = int(metadata.get("geometry_bx_mm") or 0)
    order = hit_type_order(actions, cover, geometry_target)
    errors: list[str] = []
    rows: list[tuple[Candidate, dict[str, Any]]] = []
    seen: set[str] = set()

    for connection_type in order:
        if connection_type in _FIXED_COVER and cover != 30:
            errors.append(f"{connection_type}: používá pevné cnom 30 mm, zdroj má {cover} mm")
            continue
        if geometry_target and connection_type != "MVX":
            continue
        if geometry_target:
            candidates, error = _geometry_candidates(
                database, actions, series=series, height=height, cover=cover, concrete=concrete,
                target_variant=geometry_target, bx=geometry_bx,
            )
        else:
            target_cover = 30 if connection_type in _FIXED_COVER else cover
            candidates, error, _info = database.proposal_candidates(
                connection_type, series, height, target_cover, concrete, actions, {100}, False, load_distance_x=0.0
            )
        if error and not candidates:
            errors.append(f"{connection_type}: {error}")
            continue
        for candidate in candidates:
            if candidate.designation in seen or not _component_ok(candidate, actions):
                continue
            seen.add(candidate.designation)
            rows.append((candidate, target_dict(candidate, actions, metadata)))

    rows.sort(key=lambda item: _candidate_rank(item[0], actions, order))
    return [target for _candidate, target in rows[:50]], errors


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


def calculation(candidate: Candidate, actions: DirectionalActions, metadata: dict[str, Any]) -> str:
    if candidate.spacing_max > 0:
        return (
            f"{action_text(actions)} → amax {fmt(candidate.spacing_max, 3)} m; "
            f"izolant {metadata.get('source_insulation_mm')}→HIT-{candidate.series}, "
            f"cnom {candidate.cover} mm, h {candidate.height} mm"
        )
    m_cap, v_cap, n_cap = _capacity_values(candidate)
    checks: list[str] = []
    for prefix, capacity, unit in (("m", m_cap, "kNm/m"), ("v", v_cap, "kN/m"), ("n", n_cap, "kN/m")):
        label, requirement = _direction_requirement(actions, prefix)
        if requirement <= _TOL:
            continue
        ratio = requirement / capacity if capacity > _TOL else float("inf")
        checks.append(f"{label} {fmt(requirement)}/{fmt(capacity)} = {fmt(ratio * 100.0)} %")
    if candidate.connection_type in {"MVX", "MVXL"} and max(actions.normalized().m_pos, actions.normalized().m_neg) > _TOL and max(actions.normalized().v_pos, actions.normalized().v_neg) > _TOL:
        checks.append(f"interakce M–V {fmt(candidate.utilization * 100.0)} %")
    checks.append(
        f"izolant {metadata.get('source_insulation_mm')} mm = HIT-{candidate.series}; "
        f"cnom {metadata.get('source_cover_mm')}→{candidate.cover} mm; h {metadata.get('source_height_mm')}→{candidate.height} mm"
    )
    return "; ".join(checks)


def target_dict(candidate: Candidate, actions: DirectionalActions, metadata: dict[str, Any]) -> dict[str, Any]:
    ratios = _component_ratios(candidate, actions)
    m_cap, v_cap, n_cap = _capacity_values(candidate)
    overall = _overall_utilization(candidate, actions)
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
        "utilization": overall,
        "interaction_utilization": float(candidate.utilization),
        "eta_m": float(ratios["m"]), "eta_v": float(ratios["v"]), "eta_n": float(ratios["n"]),
        "m_capacity": m_cap, "v_capacity": v_cap, "n_capacity": n_cap,
        "spacing_max_m": float(candidate.spacing_max),
        "mode": candidate.mode,
        "page": candidate.page,
        "m1": float(candidate.m1), "v1": float(candidate.v1),
        "m2": float(candidate.m2), "v2": float(candidate.v2),
        "actions": action_values(actions),
        "calculation": calculation(candidate, actions, metadata),
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
        ("source_concrete", "Beton", 86, "center", False),
        ("geometry", "Geometrie", 120, "center", False),
        ("m_pos", "M+", 70, "center", False), ("m_neg", "M−", 70, "center", False),
        ("n_pos", "N+", 70, "center", False), ("n_neg", "N−", 70, "center", False),
        ("v_pos", "V+", 70, "center", False), ("v_neg", "V−", 70, "center", False),
        ("estimated_type", "Odhad typu", 86, "center", False),
        ("target_type", "HIT typ", 72, "center", False),
        ("target", "Navržený HIT", 330, "w", True),
        ("target_m", "MRd,max", 82, "center", False),
        ("target_v", "VRd,max", 82, "center", False),
        ("target_n", "NRd", 76, "center", False),
        ("utilization", "Využití", 82, "center", False),
        ("alternatives", "Varianty", 70, "center", False),
        ("calculation", "Drobný statický výpočet", 520, "w", True),
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
                "Krytí, výška, beton a tloušťka izolantu se přebírají z původního prvku. "
                "HIT-HP odpovídá izolantu 80 mm, HIT-SP izolantu 120 mm."
            ),
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        bar = ttk.Frame(parent, style="App.TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bar, text="Aktualizovat z projektu", command=self.refresh_substitution_tree).grid(row=0, column=0)
        ttk.Button(bar, text="Navrhnout vybrané", style="Accent.TButton", command=lambda: self.design_substitutions(True)).grid(row=0, column=1, padx=(7, 0))
        ttk.Button(bar, text="Navrhnout vše", command=lambda: self.design_substitutions(False)).grid(row=0, column=2, padx=(7, 0))
        ttk.Button(bar, text="Upravit zdroj / geometrii", command=self.edit_substitution_source).grid(row=0, column=3, padx=(7, 0))
        ttk.Button(bar, text="Další varianta", command=self.next_substitution_variant).grid(row=0, column=4, padx=(7, 0))
        ttk.Button(bar, text="Kopírovat tabulku", command=self.copy_substitution_table).grid(row=0, column=5, padx=(7, 0))
        ttk.Button(bar, text="Export Excel", command=self.export_substitution_xlsx).grid(row=0, column=6, padx=(7, 0))
        bar.columnconfigure(20, weight=1)
        ttk.Label(bar, textvariable=self.sub_status_var, style="Muted.TLabel").grid(row=0, column=20, sticky="e")

        warning = ttk.Frame(parent, style="Warning.TFrame", padding=(12, 9))
        warning.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            warning,
            text=(
                "Převádí se katalogová momentová, smyková a normálová únosnost, cnom, výška a izolant. "
                "Požární odolnost REI se v této fázi vědomě neposuzuje a návrh neblokuje. "
                "Únosnosti se porovnávají samostatně; u MVX/MVXL se navíc informativně kontroluje společný bod M–V."
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
        actions, action_warnings = source_actions(row)
        values = action_values(actions)
        meta = source_metadata(row)
        stored_meta = mapping.get("source_meta") if isinstance(mapping.get("source_meta"), dict) else {}
        if stored_meta:
            meta = {**meta, **stored_meta}
        target = selected_target(mapping)
        status = str(mapping.get("status", "not_run"))
        status_text = {"not_run": "NEPOSOUZENO", "ok": "VYHOVUJE", "review": "KONTROLA", "error": "NELZE", "already_hit": "JIŽ HIT"}.get(status, status.upper())
        targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []
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
            "source_concrete": str(meta.get("source_concrete", "")),
            "geometry": str(meta.get("geometry_display", "")),
            **{key: (fmt(values[key]) if values[key] > _TOL else "") for key in _KEYS},
            "estimated_type": str(mapping.get("estimated_type", "")),
            "target_type": str(target.get("connection_type", "")) if target else "",
            "target": str(target.get("designation", "")) if target else "",
            "target_m": (fmt(float(target.get("m_capacity", 0.0))) if target and float(target.get("m_capacity", 0.0)) > _TOL else ""),
            "target_v": (fmt(float(target.get("v_capacity", 0.0))) if target and float(target.get("v_capacity", 0.0)) > _TOL else ""),
            "target_n": (fmt(float(target.get("n_capacity", 0.0))) if target and float(target.get("n_capacity", 0.0)) > _TOL else ""),
            "utilization": utilization, "alternatives": len(targets), "calculation": calculation_text,
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
        initial = str(row.get("source_text") or snapshot.get("designation", ""))
        value = simpledialog.askstring(
            "Zdrojový typ / geometrie",
            "Původní označení použité pro převod (např. včetně WU280):",
            initialvalue=initial,
            parent=self,
        )
        if value is None:
            return
        row["source_text"] = value.strip() or initial
        row["mapping"] = {"status": "not_run", "targets": [], "selected_target_id": None}
        self.project.touch()
        if hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.refresh_substitution_tree()
        if hasattr(self, "refresh_project_tree"):
            self.refresh_project_tree(select_ids=[str(row.get("id"))])
        self.sub_status_var.set("Zdrojový text byl upraven – spusťte Navrhnout vybrané.")

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
        ok = review = failed = skipped = 0
        for row in rows:
            if self._already_hit(row):
                row["mapping"] = {"status": "already_hit", "targets": [], "selected_target_id": None}
                skipped += 1
                continue
            actions, action_warnings = source_actions(row)
            meta = source_metadata(row)
            fatal = list(meta.get("errors", []))
            if not actions.has_any():
                fatal.append("chybí použitelné momentové, smykové nebo normálové únosnosti")
            order = hit_type_order(actions, int(meta.get("target_cover_mm") or 0), str(meta.get("geometry_target", ""))) if not fatal else ()
            if not order and not fatal:
                fatal.append("z účinků nelze odhadnout vhodnou rodinu HIT")
            if fatal:
                row["mapping"] = {
                    "status": "error", "targets": [], "selected_target_id": " | ".join(fatal),
                    "source_meta": meta, "warnings": action_warnings, "errors": fatal, "estimated_type": "",
                }
                failed += 1
                continue
            targets, errors = design_targets(database, actions, metadata=meta)
            if not targets:
                message = " | ".join(errors[:6]) or "Bez vyhovujícího HIT při zachování izolantu, cnom a výšky."
                row["mapping"] = {
                    "status": "error", "targets": [], "selected_target_id": message,
                    "source_meta": meta, "warnings": action_warnings, "errors": errors, "estimated_type": order[0],
                }
                failed += 1
                continue
            warnings = list(dict.fromkeys([*action_warnings, *meta.get("warnings", [])]))
            row["mapping"] = {
                "status": "review" if warnings else "ok",
                "targets": targets,
                "selected_target_id": str(targets[0]["id"]),
                "source_meta": meta,
                "warnings": warnings,
                "errors": errors,
                "estimated_type": order[0],
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
