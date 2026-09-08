from __future__ import annotations

"""Safety guard for TURTO 2.1.4 shear-dowel schedule import.

A shear dowel is designed from force per dowel/element. A value explicitly
labelled kN/m must never be silently interpreted as kN/dowel.
"""

import re
from typing import Any

import shear_dowels_schedule as _schedule

_ORIGINAL_EXTRACT_VED = _schedule._extract_ved
_NUM = _schedule._NUM


def _extract_ved(content: str, raw: str) -> float | None:
    text = str(raw or "")
    if re.search(
        rf"\bV\s*[_ ]?\s*Ed(?:\s*[+\-])?\s*(?:=|:)?\s*{_NUM}\s*kN\s*/\s*m\b",
        text,
        re.IGNORECASE,
    ):
        return None
    return _ORIGINAL_EXTRACT_VED(content, raw)


_schedule._extract_ved = _extract_ved

ShearScheduleDialog = _schedule.ShearScheduleDialog
ScheduleItem = _schedule.ScheduleItem
parse_decoder_schedule = _schedule.parse_decoder_schedule
parse_design_schedule = _schedule.parse_design_schedule
