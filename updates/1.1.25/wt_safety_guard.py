from __future__ import annotations

"""Conservative presentation guard for HIT-WT combined actions.

The catalog tables publish MRd, VRd,v and VRd,h individually but the currently
verified source section does not state an M-V interaction rule. The proposal may
therefore select a load range that passes every published component check, while
the UI keeps a combined multi-action case in KONTROLA until such a rule is
verified instead of silently inventing an interaction.
"""

from typing import Any
import hit_wt
import hit_wt_ui


def _active(row: Any) -> int:
    values = []
    for attr in ("med_neg", "ved_vertical", "ved_horizontal"):
        var = getattr(row, attr, None)
        try:
            text = str(var.get() if var is not None else "").strip().replace(",", ".")
            values.append(abs(float(text or "0")))
        except Exception:
            values.append(0.0)
    return sum(value > hit_wt.TOL for value in values)


_ORIGINAL_SHOW = hit_wt_ui.WtRow._show


def _show(self, candidate) -> None:
    _ORIGINAL_SHOW(self, candidate)
    if _active(self) > 1:
        current = str(self.status.get())
        self.status.set(
            "KONTROLA KOMBINACE • " + current
            + " • jednotlivé MRd / VRd vyhovují, ale katalogové M–V pravidlo není zatím ověřeno"
        )
        try:
            self.status_label.configure(style="Warning.TLabel")
        except Exception:
            pass


hit_wt_ui.WtRow._show = _show
