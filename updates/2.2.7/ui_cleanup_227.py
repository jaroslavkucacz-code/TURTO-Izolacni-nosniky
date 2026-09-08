from __future__ import annotations

"""TURTO 2.2.7 – remove the last clipped legacy line from Decoder ISO."""

from typing import Any
from tkinter import ttk


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _hide(widget: Any) -> None:
    try:
        manager = widget.winfo_manager()
        if manager == "grid":
            widget.grid_remove()
        elif manager == "pack":
            widget.pack_forget()
        elif manager == "place":
            widget.place_forget()
    except Exception:
        pass


def apply(owner: Any) -> None:
    tab = getattr(owner, "project_tab", None)
    path_var = getattr(owner, "project_path_var", None)
    if tab is None or path_var is None:
        return

    variable_name = str(path_var)
    hidden = 0
    for widget in _walk(tab):
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("textvariable")) == variable_name:
                _hide(widget)
                hidden += 1
        except Exception:
            pass

    try:
        tab.grid_rowconfigure(0, minsize=0)
    except Exception:
        pass

    owner._turto_hidden_legacy_project_path_227 = hidden


def selftest() -> None:
    assert callable(apply)


if __name__ == "__main__":
    selftest()
