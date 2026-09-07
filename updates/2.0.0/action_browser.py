from __future__ import annotations

"""TURTO 2.0 terminology wrapper for the central AKCE browser."""

import action_browser_123 as _prev
from action_browser_123 import *  # noqa: F401,F403

_ORIGINAL_INIT = _prev.ActionBrowser.__init__


def _init(self, owner):
    _ORIGINAL_INIT(self, owner)
    try:
        self.tree.heading("decoder", text="Dekodér")
        self.tree.heading("hit", text="Návrhy")
    except Exception:
        pass


_prev.ActionBrowser.__init__ = _init
ActionBrowser = _prev.ActionBrowser
