"""Uživatelské přijetí konkrétní katalogové záměny, nikoli schválení statikem.

Potvrdit lze pouze oznámení, že prvotní odhad nahradil vyhovující HIT.
Ostatní varování ani nevyhovující/neúplný výpočet tento modul nepotlačí.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any

_FALLBACK = re.compile(
    r"odhad MVX-\d{4}(?:-(?:OU|OD)\d+)? nebyl staticky použitelný; "
    r"použita nejbližší vyhovující varianta\Z"
)
_TOL = 1e-9


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _messages(value: Any) -> list[str]:
    return list(dict.fromkeys(str(x).strip() for x in value if str(x).strip())) if isinstance(value, (list, tuple)) else []


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def is_estimate_notice(message: str) -> bool:
    return bool(_FALLBACK.fullmatch(str(message).strip()))


def exact_target(mapping: dict[str, Any]) -> dict[str, Any]:
    """Nikdy nepotvrdí první náhradní záznam při neplatném selected_target_id."""
    selected = str(mapping.get("selected_target_id") or "")
    targets = mapping.get("targets")
    if not selected or not isinstance(targets, list):
        return {}
    found = [t for t in targets if isinstance(t, dict) and str(t.get("id")) == selected]
    return found[0] if len(found) == 1 else {}


def calculation_blockers(mapping: dict[str, Any]) -> list[str]:
    if mapping.get("status") not in {"ok", "review"}:
        return ["Řádek nemá dokončený vyhovující návrh. Spusťte Navrhnout vybrané."]
    target = exact_target(mapping)
    if not target or not str(target.get("designation") or "").strip():
        return ["Chybí jednoznačně vybraná varianta HIT. Spusťte nový návrh."]
    for key in ("utilization", "interaction_utilization"):
        if key not in target and key != "utilization":
            continue
        n = _number(target.get(key))
        if not math.isfinite(n) or n < 0 or n > 1.0 + _TOL:
            return ["Výpočet nevyhovuje nebo nemá platné využití. Potvrzení jej nemůže obejít."]
    checks = target.get("checks")
    if not isinstance(checks, list) or not checks:
        return ["Chybí úplná směrová statická kontrola. Spusťte nový návrh."]
    for check in checks:
        if not isinstance(check, dict):
            return ["Směrová kontrola obsahuje neplatná data."]
        req, cap, eta = (_number(check.get(k)) for k in ("requirement", "capacity", "eta"))
        if (not all(math.isfinite(v) for v in (req, cap, eta))
                or req < 0 or cap <= 0 or eta < 0 or eta > 1 + _TOL
                or req / cap > 1 + _TOL
                or not math.isclose(eta, req / cap, rel_tol=1e-7, abs_tol=1e-9)
                or check.get("result") != "VYHOVUJE"):
            return ["Některá směrová kontrola není platná nebo nevyhovuje; nelze ji potvrdit."]
    source = _dict(target.get("source_element_actions"))
    if not source or not any(_number(v) > 0 for v in source.values()):
        return ["Chybí uložené směrové požadavky původního prvku. Spusťte nový návrh."]
    for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg"):
        value = _number(source.get(key, 0))
        if not math.isfinite(value) or value < 0:
            return ["Zdrojové směrové požadavky obsahují neplatnou hodnotu."]
        if value > _TOL:
            label = key[0].upper() + ("+" if key.endswith("pos") else "-")
            matching = [c for c in checks if str(c.get("label", "")).replace("−", "-") == label]
            if len(matching) != 1 or not math.isclose(_number(matching[0].get("requirement")), value, rel_tol=1e-7, abs_tol=1e-9):
                return ["Směrová kontrola neobsahuje všechny požadavky zdrojového prvku."]
    return []


def acceptance_signature(row: dict[str, Any]) -> str:
    mapping = _dict(row.get("mapping"))
    target = exact_target(mapping)
    if not target:
        return ""
    payload = {
        "schema": 1, "row_id": row.get("id"),
        "selection": row.get("selection"), "snapshot": row.get("snapshot"),
        "source_text": row.get("source_text"), "note": row.get("note"),
        "overrides": _dict(mapping.get("source_overrides")),
        "target": target, "estimated_type": mapping.get("estimated_type"),
        "warnings": sorted(_messages(mapping.get("warnings"))),
    }
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def review_state(row: dict[str, Any], metadata: dict[str, Any], extra_warnings=()) -> dict[str, Any]:
    """Jedna společná pravda pro tabulku, Excel i PDF. Nemění zdrojová data."""
    mapping = _dict(row.get("mapping"))
    status = str(mapping.get("status", "not_run"))
    warnings = _messages([*_messages(mapping.get("warnings")), *_messages(metadata.get("warnings")), *_messages(extra_warnings)])
    errors = _messages([*_messages(mapping.get("errors")), *_messages(metadata.get("errors"))])
    if metadata.get("geometry_target") and not metadata.get("geometry_confirmed"):
        message = "Nejprve potvrďte geometrii OU/OD tlačítkem Potvrdit geometrii."
        if not any("geometr" in x.lower() and "potvr" in x.lower() for x in warnings):
            warnings.append(message)
    numeric_errors = calculation_blockers(mapping)
    acceptance = _dict(mapping.get("substitution_acceptance"))
    signature = acceptance_signature(row)
    accepted_warnings = sorted(w for w in warnings if is_estimate_notice(w))
    valid = (bool(acceptance) and bool(signature) and not errors and not numeric_errors
             and acceptance.get("schema") == 1
             and acceptance.get("signature") == signature
             and acceptance.get("target_id") == str(mapping.get("selected_target_id"))
             and sorted(_messages(acceptance.get("warnings"))) == accepted_warnings
             and bool(str(acceptance.get("confirmed_at") or "")))
    pending = [w for w in warnings if not (valid and is_estimate_notice(w))]
    if acceptance and not valid:
        pending.append("Potvrzení záměny již neplatí pro aktuální data nebo variantu. Návrh znovu přepočítejte a potvrďte.")
    if status in {"ok", "review"}:
        if errors or numeric_errors:
            status = "error"
        elif pending:
            status = "review"
        elif valid or status == "ok":
            status = "ok"
        # Neznámý důvod dřívější KONTROLY nelze zrušit pouhou změnou popisku.
    blockers = [*errors, *numeric_errors, *(w for w in warnings if not is_estimate_notice(w))]
    if mapping.get("status") == "review" and not warnings and not valid:
        blockers.append("Stav KONTROLA nemá popsaný důvod. Spusťte nový návrh.")
    notes: list[str] = []
    if valid:
        chosen = str(exact_target(mapping).get("designation"))
        notes.append(f"Potvrzení záměny uživatelem: {chosen}; {acceptance['confirmed_at']}. Nutno schválit statikem stavby.")
        notes.extend("Potvrzená informace o původním odhadu: " + w for w in accepted_warnings)
    return {"status": status, "warnings": _messages(pending),
            "errors": _messages([*errors, *(numeric_errors if mapping.get('status') in {'ok', 'review'} else [])]),
            "accepted": bool(valid), "audit_notes": notes,
            "blockers": _messages(blockers), "can_accept": not blockers and bool(signature),
            "acceptance_text": "Záměna potvrzena uživatelem" if valid else ""}


def accept_substitution(row: dict[str, Any], metadata: dict[str, Any], extra_warnings=()) -> None:
    """Volat až po novém návrhu a výslovném potvrzení dialogu uživatelem."""
    state = review_state(row, metadata, extra_warnings)
    if not state["can_accept"]:
        raise ValueError("\n".join(state["blockers"]) or "Výsledek nelze potvrdit.")
    mapping = _dict(row.get("mapping"))
    mapping["substitution_acceptance"] = {
        "schema": 1, "signature": acceptance_signature(row),
        "target_id": str(mapping["selected_target_id"]),
        "confirmed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "warnings": sorted(w for w in _messages(mapping.get("warnings")) if is_estimate_notice(w)),
    }
    mapping["status"] = review_state(row, metadata, extra_warnings)["status"]


def revoke_acceptance(row: dict[str, Any], metadata: dict[str, Any], extra_warnings=()) -> None:
    mapping = _dict(row.get("mapping"))
    mapping.pop("substitution_acceptance", None)
    mapping["status"] = review_state(row, metadata, extra_warnings)["status"]
