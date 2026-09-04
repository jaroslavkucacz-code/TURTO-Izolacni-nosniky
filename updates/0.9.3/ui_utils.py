from __future__ import annotations

from typing import Any


def place_dialog_on_parent(dialog: Any, parent: Any) -> None:
    """Umístí dialog nad rodičovské okno, tedy na stejný monitor.

    Zachová velikost nastavenou pomocí geometry()/minsize(). Souřadnice mohou být
    záporné, což je důležité pro monitory vlevo nebo nad primárním monitorem.
    Volání je odloženo přes after_idle, aby už Tk znal skutečnou velikost oken.
    """
    def _place() -> None:
        try:
            parent.update_idletasks()
            dialog.update_idletasks()

            width = int(dialog.winfo_width())
            height = int(dialog.winfo_height())
            if width <= 1:
                width = max(1, int(dialog.winfo_reqwidth()))
            if height <= 1:
                height = max(1, int(dialog.winfo_reqheight()))

            parent_x = int(parent.winfo_rootx())
            parent_y = int(parent.winfo_rooty())
            parent_w = max(1, int(parent.winfo_width()))
            parent_h = max(1, int(parent.winfo_height()))

            x = parent_x + (parent_w - width) // 2
            y = parent_y + (parent_h - height) // 2
            dialog.geometry(f"{width}x{height}{x:+d}{y:+d}")
            dialog.lift(parent)
        except Exception:
            # Umístění dialogu nesmí nikdy zablokovat jeho otevření.
            pass

    try:
        dialog.after_idle(_place)
    except Exception:
        pass


def maximize_window_on_pointer_monitor(window: Any, pointer: tuple[int, int] | None = None) -> None:
    """Přesune hlavní okno na monitor pod kurzorem při startu a maximalizuje ho."""
    def _maximize() -> None:
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                class POINT(ctypes.Structure):
                    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", wintypes.LONG), ("top", wintypes.LONG),
                        ("right", wintypes.LONG), ("bottom", wintypes.LONG),
                    ]

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("rcMonitor", RECT),
                        ("rcWork", RECT),
                        ("dwFlags", wintypes.DWORD),
                    ]

                user32 = ctypes.windll.user32
                if pointer is None:
                    point = POINT()
                    if not user32.GetCursorPos(ctypes.byref(point)):
                        raise OSError("GetCursorPos selhalo")
                else:
                    point = POINT(int(pointer[0]), int(pointer[1]))

                monitor = user32.MonitorFromPoint(point, 2)
                if not monitor:
                    raise OSError("MonitorFromPoint selhalo")
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    raise OSError("GetMonitorInfoW selhalo")

                left, top = int(info.rcWork.left), int(info.rcWork.top)
                area_w = max(800, int(info.rcWork.right - info.rcWork.left))
                area_h = max(600, int(info.rcWork.bottom - info.rcWork.top))

                window.update_idletasks()
                width = int(window.winfo_width())
                height = int(window.winfo_height())
                if width <= 1:
                    width = int(window.winfo_reqwidth())
                if height <= 1:
                    height = int(window.winfo_reqheight())
                width = max(900, min(width, max(900, area_w - 80)))
                height = max(650, min(height, max(650, area_h - 80)))
                x = left + (area_w - width) // 2
                y = top + (area_h - height) // 2

                window.state("normal")
                window.geometry(f"{width}x{height}{x:+d}{y:+d}")
                window.update_idletasks()
                window.state("zoomed")
                window.lift()
                return

            try:
                window.state("zoomed")
            except Exception:
                window.attributes("-zoomed", True)
        except Exception:
            try:
                window.state("zoomed")
            except Exception:
                pass

    try:
        window.after_idle(_maximize)
    except Exception:
        pass

