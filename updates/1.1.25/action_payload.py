from __future__ import annotations

"""1.1.25 central AKCE payload extension for specialized HIT-WT rows."""

from typing import Any
import action_payload_prev as _prev
from action_payload_prev import *  # noqa: F401,F403


_ORIGINAL_SERIALIZE = _prev.serialize_action
_ORIGINAL_LOAD = _prev.load_action_record
_ORIGINAL_NEW = _prev.new_action
_ORIGINAL_SAVE = _prev.save_action


def serialize_action(owner: Any) -> dict[str, Any]:
    payload = _ORIGINAL_SERIALIZE(owner)
    payload["schema_version"] = max(2, int(payload.get("schema_version", 1) or 1))
    if hasattr(owner, "serialize_wt_design"):
        payload["wt_design"] = owner.serialize_wt_design()
    else:
        payload["wt_design"] = {"schema_version": 1, "rows": []}
    return payload


# The legacy save function resolves serialize_action in its own module globals.
# Redirect that global so Ctrl+S and every old save path also persist WT.
_prev.serialize_action = serialize_action


def load_action_record(owner: Any, record: dict[str, Any]) -> None:
    _ORIGINAL_LOAD(owner, record)
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    wt_payload = payload.get("wt_design") if isinstance(payload, dict) else None
    if hasattr(owner, "load_wt_design"):
        owner._action_loading = True
        try:
            owner.load_wt_design(wt_payload if isinstance(wt_payload, dict) else {"schema_version": 1, "rows": []})
            owner.project_dirty = False
            owner._update_project_title()
            owner._update_action_info()
        finally:
            owner._action_loading = False
        owner.set_status(
            f"Načtena AKCE {owner.project.name} • {len(owner.project.rows)} řádků Dekodéru ISO • "
            f"{len(getattr(owner, 'hit_rows', []))} standardních HIT • {len(getattr(owner, 'wt_rows', []))} WT."
        )


def save_action(owner: Any, *, as_new: bool = False, forced_name: str | None = None) -> bool:
    ok = _ORIGINAL_SAVE(owner, as_new=as_new, forced_name=forced_name)
    if ok and hasattr(owner, "wt_rows"):
        owner.set_status(
            f"AKCE „{owner.project.name}“ uložena • {len(owner.project.rows)} Dekodér ISO • "
            f"{len(getattr(owner, 'hit_rows', []))} standardních HIT • {len(owner.wt_rows)} WT."
        )
    return bool(ok)


def new_action(owner: Any) -> None:
    _ORIGINAL_NEW(owner)
    if hasattr(owner, "load_wt_design"):
        owner._action_loading = True
        try:
            owner.load_wt_design({"schema_version": 1, "rows": []})
            owner.project_dirty = False
            owner._update_project_title()
            owner._update_action_info()
        finally:
            owner._action_loading = False


# Make old module-internal references use the WT-aware functions as well.
_prev.load_action_record = load_action_record
_prev.save_action = save_action
_prev.new_action = new_action

# save_action_as_new and confirm_action_close from the previous layer call
# _prev.save_action dynamically, therefore they automatically use the wrapper.
save_action_as_new = _prev.save_action_as_new
confirm_action_close = _prev.confirm_action_close
action_store = _prev.action_store
