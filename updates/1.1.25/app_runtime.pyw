from __future__ import annotations

"""TURTO ISO 1.1.25 runtime.

Builds on the central-AKCE 1.1.23 composition, adds table/UI polish and a
specialized HIT-WT wall design workspace.
"""

from tkinter import ttk

import app_central_prev as _prev
import hit_workspace
import substitution_workspace
from table_polish import install_substitution

APP_VERSION = "1.1.25"
_prev.APP_VERSION = APP_VERSION
_prev._base.APP_VERSION = APP_VERSION

try:
    hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    hit_workspace._prev.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
    hit_workspace._prev._base.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

# Záměny use a Treeview; align each heading to the same anchor as its cells and
# improve a few ambiguous labels.
install_substitution(substitution_workspace.SubstitutionWorkspaceMixin)


def _walk(root):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try: stack.extend(widget.winfo_children())
        except Exception: pass


_ORIGINAL_HEADER = _prev._base.ThermalConnectorApp._build_header


def _header(self) -> None:
    _ORIGINAL_HEADER(self)
    for widget in _walk(self):
        if not isinstance(widget, ttk.Label):
            continue
        try:
            text = str(widget.cget("text"))
            if text.startswith("Jedna AKCE • Dekodér ISO"):
                widget.configure(
                    text="Jedna AKCE • Dekodér ISO • Návrh HIT pro desky i WT stěny • Záměny za HIT • společné centrální uložení"
                )
        except Exception:
            pass


_prev._base.ThermalConnectorApp._build_header = _header


if __name__ == "__main__":
    raise SystemExit(_prev._base.main())
