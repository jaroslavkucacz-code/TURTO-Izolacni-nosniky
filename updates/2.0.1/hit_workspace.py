from __future__ import annotations

"""TURTO 2.0.1 thermal-break design UI hotfix.

Fixes the 2.0.0 startup regression where the generic supplementary-row button
referenced a non-existent ``add_aux_row`` method. The verified 1.1.27 module
publishes ``add_aux_row_for_type``; this compatibility layer exposes a generic
``add_aux_row`` alias that creates an HT row, whose type can then be changed in
the row selector. No calculation logic is changed.
"""

from typing import Any
from tkinter import ttk

import hit_workspace_200 as _prev
from hit_workspace_200 import *  # noqa: F401,F403

HIT_MODULE_VERSION = "2.0.1"
try:
    _prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION
    _prev._prev.HIT_MODULE_VERSION = HIT_MODULE_VERSION  # type: ignore[attr-defined]
except Exception:
    pass


def _add_aux_row(self):
    """Generic supplementary row used by the 2.0 platform UI."""
    return self.add_aux_row_for_type("HT")


# Publish the compatibility alias on the same shared mixin class used by the
# application. This also makes the existing 2.0.0 post-processing callback
# (command=self.add_aux_row) safe during UI construction.
_prev.HitWorkspaceMixin.add_aux_row = _add_aux_row

HitInputRow = _prev.HitInputRow
HitWorkspaceMixin = _prev.HitWorkspaceMixin
