from __future__ import annotations

"""TURTO 2.2.9 – small workspace cleanup after catalog-browser addition."""

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


def apply(owner: Any) -> None:
    for widget in _walk(owner):
        try:
            if isinstance(widget, ttk.Button):
                text = str(widget.cget("text") or "")
                if text == "Otevřít zdroj":
                    widget.configure(text="Otevřít katalog")
        except Exception:
            pass


def selftest() -> None:
    assert callable(apply)


if __name__ == "__main__":
    selftest()
