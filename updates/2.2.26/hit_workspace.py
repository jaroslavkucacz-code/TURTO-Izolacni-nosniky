from __future__ import annotations

"""TURTO 2.2.26 – responsive HIT workspace wrapper.

The verified 2.2.19 HIT logic remains unchanged. Only dense toolbars are
reflowed after construction so right-side export/save actions cannot disappear
when Windows display scaling reduces the logical window width.
"""

from typing import Any
from tkinter import ttk

import hit_workspace_219 as _base
from hit_workspace_219 import *  # noqa: F401,F403 - preserve public API

HIT_MODULE_VERSION = "2.2.26"
_prev = getattr(_base, "_prev", _base)

_ORIGINAL_BUILD = _base.HitWorkspaceMixin._build_hit_tab


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _find_button(root: Any, *texts: str):
    wanted = set(texts)
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) in wanted:
                return widget
        except Exception:
            pass
    return None


def _reflow_standard_toolbar(owner: Any, parent: Any) -> None:
    anchor = _find_button(parent, "Kopírovat výsledky")
    if anchor is None:
        return
    toolbar = anchor.master
    second_row_names = {
        "Export Excel",
        "Export Excel – desky",
        "Uložit návrh",
        "Návrhy…",
    }
    second = []
    for child in toolbar.winfo_children():
        try:
            if isinstance(child, ttk.Button) and str(child.cget("text")) in second_row_names:
                second.append(child)
        except Exception:
            pass
    for column, child in enumerate(second):
        try:
            child.grid_configure(
                row=1,
                column=column,
                sticky="w",
                padx=(0 if column == 0 else 7, 0),
                pady=(7, 0),
            )
        except Exception:
            pass
    try:
        toolbar.columnconfigure(9, weight=1)
    except Exception:
        pass
    owner._turto_hit_toolbar_second_row_226 = tuple(second)


def _wrap_global_summary(parent: Any) -> None:
    button = _find_button(parent, "Export PDF – všechny prvky")
    if button is None:
        return
    bar = button.master
    try:
        bar.columnconfigure(1, weight=1)
    except Exception:
        pass
    for child in bar.winfo_children():
        try:
            if isinstance(child, ttk.Label):
                text = str(child.cget("text"))
                if "PDF zahrnuje" in text:
                    child.configure(wraplength=760, justify="left")
                    child.grid_configure(sticky="ew")
        except Exception:
            pass
    try:
        button.grid_configure(sticky="e", padx=(12, 0))
    except Exception:
        pass


def _responsive_build(self: Any, parent: ttk.Frame) -> None:
    _ORIGINAL_BUILD(self, parent)
    _wrap_global_summary(parent)
    _reflow_standard_toolbar(self, parent)
    self._turto_hit_responsive_226 = True


_base.HIT_MODULE_VERSION = HIT_MODULE_VERSION
_base.HitWorkspaceMixin._build_hit_tab = _responsive_build
HitWorkspaceMixin = _base.HitWorkspaceMixin


def selftest() -> None:
    assert HIT_MODULE_VERSION == "2.2.26"
    assert callable(_responsive_build)
    assert callable(_reflow_standard_toolbar)


if __name__ == "__main__":
    selftest()
