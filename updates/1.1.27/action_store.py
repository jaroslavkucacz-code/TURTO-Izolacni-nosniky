from __future__ import annotations

"""TURTO ISO 1.1.27 store counts standard + supplementary + WT HIT rows."""

from typing import Any

import action_store_125 as _prev
from action_store_125 import *  # noqa: F401,F403


class ActionStore(_prev.ActionStore):
    @staticmethod
    def _counts(payload: dict[str, Any]) -> tuple[int, int]:
        project = payload.get("project") if isinstance(payload, dict) else {}
        decoder_rows = project.get("rows") if isinstance(project, dict) else []
        hit = payload.get("hit_design") if isinstance(payload, dict) else {}
        hit_rows = hit.get("rows") if isinstance(hit, dict) else []
        aux = payload.get("aux_design") if isinstance(payload, dict) else {}
        aux_rows = aux.get("rows") if isinstance(aux, dict) else []
        wt = payload.get("wt_design") if isinstance(payload, dict) else {}
        wt_rows = wt.get("rows") if isinstance(wt, dict) else []
        decoder_count = len(decoder_rows) if isinstance(decoder_rows, list) else 0
        hit_count = (
            (len(hit_rows) if isinstance(hit_rows, list) else 0)
            + (len(aux_rows) if isinstance(aux_rows, list) else 0)
            + (len(wt_rows) if isinstance(wt_rows, list) else 0)
        )
        return decoder_count, hit_count
