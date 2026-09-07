from __future__ import annotations

"""TURTO 2.0 central AKCE payload extension.

The established 1.1.27 data fields remain intact for backwards compatibility.
A new platform_state section stores product-area and manufacturer choices so
future design/substitution engines can be added without changing old AKCE data.
"""

from typing import Any

import action_payload_127 as _prev
from action_payload_127 import *  # noqa: F401,F403
from platform_registry import default_platform_state
from platform_state import apply_platform_state, capture_platform_state, reset_platform_state

_ORIGINAL_SERIALIZE = _prev.serialize_action
_ORIGINAL_LOAD = _prev.load_action_record
_ORIGINAL_NEW = _prev.new_action
_ORIGINAL_SAVE = _prev.save_action


def serialize_action(owner: Any) -> dict[str, Any]:
    payload = _ORIGINAL_SERIALIZE(owner)
    payload["schema_version"] = max(4, int(payload.get("schema_version", 1) or 1))
    payload["platform_state"] = capture_platform_state(owner)
    payload["product_domains"] = {
        "thermal_breaks": {
            "decoder_storage": "project",
            "design_storage": ("hit_design", "aux_design", "wt_design"),
            "substitution_storage": "project.rows[*].substitution",
        },
        "shear_dowels": {"status": "framework_ready"},
        "stair_acoustics": {"status": "framework_ready"},
    }
    return payload


_prev.serialize_action = serialize_action
for obj in (getattr(_prev, "_prev", None), getattr(getattr(_prev, "_prev", None), "_prev", None)):
    if obj is not None:
        try:
            obj.serialize_action = serialize_action
        except Exception:
            pass


def load_action_record(owner: Any, record: dict[str, Any]) -> None:
    _ORIGINAL_LOAD(owner, record)
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    apply_platform_state(owner, payload.get("platform_state", default_platform_state()))
    try:
        owner.project_dirty = False
        owner._update_project_title()
        owner._update_action_info()
        owner.set_status(
            f"Načtena AKCE {owner.project.name} • Izolační nosníky: "
            f"{len(owner.project.rows)} dekódovaných • "
            f"{len(getattr(owner, 'hit_rows', [])) + len(getattr(owner, 'aux_rows', [])) + len(getattr(owner, 'wt_rows', []))} návrhových řádků."
        )
    except Exception:
        pass


def save_action(owner: Any, *, as_new: bool = False, forced_name: str | None = None) -> bool:
    capture_platform_state(owner)
    ok = bool(_ORIGINAL_SAVE(owner, as_new=as_new, forced_name=forced_name))
    if ok:
        try:
            owner.set_status(
                f"AKCE „{owner.project.name}“ uložena • Izolační nosníky: "
                f"{len(owner.project.rows)} dekódovaných • "
                f"{len(getattr(owner, 'hit_rows', [])) + len(getattr(owner, 'aux_rows', [])) + len(getattr(owner, 'wt_rows', []))} návrhových řádků."
            )
        except Exception:
            pass
    return ok


def new_action(owner: Any) -> None:
    _ORIGINAL_NEW(owner)
    try:
        owner._action_loading = True
        reset_platform_state(owner)
        owner.project_dirty = False
        owner._update_project_title()
        owner._update_action_info()
    finally:
        owner._action_loading = False


_prev.load_action_record = load_action_record
_prev.save_action = save_action
_prev.new_action = new_action
for obj in (getattr(_prev, "_prev", None), getattr(getattr(_prev, "_prev", None), "_prev", None)):
    if obj is not None:
        try:
            obj.load_action_record = load_action_record
            obj.save_action = save_action
            obj.new_action = new_action
        except Exception:
            pass

save_action_as_new = _prev.save_action_as_new
confirm_action_close = _prev.confirm_action_close
action_store = _prev.action_store
