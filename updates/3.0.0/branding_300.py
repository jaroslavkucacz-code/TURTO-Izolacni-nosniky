from __future__ import annotations

"""TURTO 3.0.0 branding using the user-selected thermal-break/shear-dowel mark."""

from pathlib import Path
import tkinter as tk
from tkinter import ttk

VERSION = "3.0.0"
LOGO_FILE = Path(__file__).resolve().with_name("turto_logo_300.png")


def _walk(root):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def install(base_module) -> None:
    app_cls = base_module.ThermalConnectorApp
    if getattr(app_cls, "_turto_branding_300", False):
        return

    original_header = app_cls._build_header

    def _brand_window(self) -> None:
        if getattr(self, "_turto_logo_master", None) is not None:
            return
        if not LOGO_FILE.is_file():
            return
        logo = tk.PhotoImage(master=self, file=str(LOGO_FILE))
        self._turto_logo_master = logo
        try:
            self.iconphoto(True, logo)
        except Exception:
            pass
        try:
            self.title("TURTO 3.0")
        except Exception:
            pass

    def _branded_header(self) -> None:
        original_header(self)
        try:
            _brand_window(self)
            logo = getattr(self, "_turto_logo_master", None)
            if logo is None:
                return
            header_logo = logo.subsample(2, 2)
            self._turto_logo_header = header_logo
            for widget in _walk(self):
                if not isinstance(widget, ttk.Label):
                    continue
                try:
                    text = str(widget.cget("text") or "")
                except Exception:
                    continue
                if text.startswith("TURTO ISO") or text.startswith("TURTO 3.0"):
                    widget.configure(
                        text="TURTO 3.0 | Izolační nosníky a smykové trny",
                        image=header_logo,
                        compound="left",
                    )
                    break
        except Exception:
            # Branding must never block startup.
            pass

    app_cls._build_header = _branded_header
    app_cls._turto_branding_300 = True
    app_cls._turto_brand_window = _brand_window


def selftest() -> None:
    assert VERSION == "3.0.0"
    assert LOGO_FILE.name == "turto_logo_300.png"


if __name__ == "__main__":
    selftest()
