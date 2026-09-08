from __future__ import annotations
from typing import Any
import action_store_127 as _prev
from action_store_127 import *  # noqa
class ActionStore(_prev.ActionStore):
    @staticmethod
    def _counts(payload:dict[str,Any])->tuple[int,int]:
        decoder,hit=_prev.ActionStore._counts(payload);shear=payload.get("shear_dowels") if isinstance(payload,dict) else {};design=shear.get("design") if isinstance(shear,dict) else [];sub=shear.get("substitution") if isinstance(shear,dict) else [];extra=(len(design) if isinstance(design,list) else 0)+(len(sub) if isinstance(sub,list) else 0);return decoder,hit+extra
