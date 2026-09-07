from __future__ import annotations

"""TURTO ISO 1.1.27 central AKCE payload: separate supplementary HIT rows."""

from copy import deepcopy
from typing import Any

import action_payload_125 as _prev
from action_payload_125 import *  # noqa: F401,F403

AUX_TYPES = {"HT", "AT", "FT", "OTX"}
_ORIGINAL_SERIALIZE = _prev.serialize_action
_ORIGINAL_LOAD = _prev.load_action_record
_ORIGINAL_NEW = _prev.new_action
_ORIGINAL_SAVE = _prev.save_action


def _split_legacy_hit(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    work = deepcopy(payload)
    hit = work.get("hit_design") if isinstance(work.get("hit_design"), dict) else {}
    rows = hit.get("rows") if isinstance(hit.get("rows"), list) else []
    standard: list[dict[str, Any]] = []
    aux: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        typ = str(raw.get("connection_type", "") or "").strip().upper()
        (aux if typ in AUX_TYPES else standard).append(raw)
    hit["rows"] = standard
    work["hit_design"] = hit

    existing_aux = work.get("aux_design") if isinstance(work.get("aux_design"), dict) else None
    if existing_aux is None:
        work["aux_design"] = {"schema_version": 1, "rows": aux}
    else:
        current = existing_aux.get("rows") if isinstance(existing_aux.get("rows"), list) else []
        if aux:
            existing_aux["rows"] = [*current, *aux]
        work["aux_design"] = existing_aux
    return work, work["aux_design"]


def serialize_action(owner: Any) -> dict[str, Any]:
    payload = _ORIGINAL_SERIALIZE(owner)
    payload["schema_version"] = max(3, int(payload.get("schema_version", 1) or 1))
    if hasattr(owner, "serialize_aux_design"):
        payload["aux_design"] = owner.serialize_aux_design()
    else:
        payload["aux_design"] = {"schema_version": 1, "rows": []}
    cleaned, aux = _split_legacy_hit(payload)
    cleaned["aux_design"] = payload["aux_design"] if isinstance(payload.get("aux_design"), dict) else aux
    return cleaned


_prev.serialize_action = serialize_action
try:
    _prev._prev.serialize_action = serialize_action  # type: ignore[attr-defined]
except Exception:
    pass


def load_action_record(owner: Any, record: dict[str, Any]) -> None:
    raw_payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    clean_payload, aux_payload = _split_legacy_hit(raw_payload)
    work = dict(record)
    work["payload"] = clean_payload
    _ORIGINAL_LOAD(owner, work)

    if hasattr(owner, "load_aux_design"):
        owner._action_loading = True
        try:
            owner.load_aux_design(aux_payload)
            owner.project_dirty = False
            owner._update_project_title()
            owner._update_action_info()
        finally:
            owner._action_loading = False

    owner.set_status(
        f"Načtena AKCE {owner.project.name} • {len(owner.project.rows)} Dekodér ISO • "
        f"{len(getattr(owner, 'hit_rows', []))} desky/balkony • "
        f"{len(getattr(owner, 'aux_rows', []))} doplňkové HIT • "
        f"{len(getattr(owner, 'wt_rows', []))} WT."
    )


def save_action(owner: Any, *, as_new: bool = False, forced_name: str | None = None) -> bool:
    ok = _ORIGINAL_SAVE(owner, as_new=as_new, forced_name=forced_name)
    if ok:
        owner.set_status(
            f"AKCE „{owner.project.name}“ uložena • "
            f"{len(owner.project.rows)} Dekodér ISO • "
            f"{len(getattr(owner, 'hit_rows', []))} desky/balkony • "
            f"{len(getattr(owner, 'aux_rows', []))} doplňkové HIT • "
            f"{len(getattr(owner, 'wt_rows', []))} WT."
        )
    return bool(ok)


def new_action(owner: Any) -> None:
    _ORIGINAL_NEW(owner)
    if hasattr(owner, "load_aux_design"):
        owner._action_loading = True
        try:
            owner.load_aux_design({"schema_version": 1, "rows": []})
            owner.project_dirty = False
            owner._update_project_title()
            owner._update_action_info()
        finally:
            owner._action_loading = False


_prev.load_action_record = load_action_record
_prev.save_action = save_action
_prev.new_action = new_action
try:
    _prev._prev.load_action_record = load_action_record  # type: ignore[attr-defined]
    _prev._prev.save_action = save_action  # type: ignore[attr-defined]
    _prev._prev.new_action = new_action  # type: ignore[attr-defined]
except Exception:
    pass

save_action_as_new = _prev.save_action_as_new
confirm_action_close = _prev.confirm_action_close
action_store = _prev.action_store
