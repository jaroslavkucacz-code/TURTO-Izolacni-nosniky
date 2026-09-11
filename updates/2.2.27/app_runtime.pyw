from __future__ import annotations

"""TURTO 2.2.27 runtime – keep restored main windows on an active monitor."""

import os
import runpy
from pathlib import Path

APP_VERSION = "2.2.27"
BASE_RUNTIME = Path(__file__).with_name("app_runtime_221.pyw")

if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_app_runtime_221")
_base = _namespace.get("_base")
_hit_workspace = _namespace.get("hit_workspace")

if _base is None:
    raise RuntimeError("Runtime 2.2.21 neposkytl app_base.")

_required_shear_methods = (
    "open_shear_decoder_schedule",
    "open_shear_design_schedule",
    "add_shear_decoder_row",
    "add_shear_design_row",
    "shear_decoder_to_substitution",
    "sync_shear_substitutions_from_decoder",
    "recalculate_shear_substitutions",
    "recalculate_shear_design_all",
    "refresh_shear_tables",
)
_missing_shear_methods = [
    name for name in _required_shear_methods
    if not callable(getattr(_base.ThermalConnectorApp, name, None))
]
if _missing_shear_methods:
    raise RuntimeError(
        "Neúplný runtime smykových trnů; chybí metody: "
        + ", ".join(_missing_shear_methods)
    )


def clamp_rect_to_work_area(
    rect: tuple[int, int, int, int],
    work: tuple[int, int, int, int],
    *,
    margin: int = 8,
) -> tuple[int, int, int, int]:
    """Return x, y, width, height fully inside a monitor work area."""
    x, y, width, height = (int(value) for value in rect)
    left, top, right, bottom = (int(value) for value in work)

    work_width = max(1, right - left)
    work_height = max(1, bottom - top)
    margin = max(0, int(margin))
    if work_width <= 2 * margin or work_height <= 2 * margin:
        margin = 0

    max_width = max(1, work_width - 2 * margin)
    max_height = max(1, work_height - 2 * margin)
    width = max(1, min(width, max_width))
    height = max(1, min(height, max_height))

    min_x = left + margin
    min_y = top + margin
    max_x = right - margin - width
    max_y = bottom - margin - height
    x = min(max(x, min_x), max_x)
    y = min(max(y, min_y), max_y)
    return x, y, width, height


def _windows_window_and_work_area(widget):
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = (
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            )

        class MONITORINFO(ctypes.Structure):
            _fields_ = (
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            )

        user32 = ctypes.windll.user32
        hwnd = wintypes.HWND(int(widget.winfo_id()))
        root_hwnd = user32.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT
        rect = RECT()
        if not user32.GetWindowRect(root_hwnd, ctypes.byref(rect)):
            return None
        monitor = user32.MonitorFromWindow(root_hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        return (
            int(root_hwnd),
            (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top),
            (info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom),
        )
    except Exception:
        return None


def _ensure_main_window_visible(widget) -> None:
    try:
        if str(widget.state()).lower() != "normal":
            return
    except Exception:
        return

    win32 = _windows_window_and_work_area(widget)
    if win32 is not None:
        hwnd, rect, work = win32
        fixed = clamp_rect_to_work_area(rect, work)
        if fixed != rect:
            try:
                import ctypes

                x, y, width, height = fixed
                flags = 0x0004 | 0x0010  # SWP_NOZORDER | SWP_NOACTIVATE
                ctypes.windll.user32.SetWindowPos(
                    hwnd, 0, x, y, width, height, flags
                )
            except Exception:
                pass
        return

    try:
        widget.update_idletasks()
        rect = (
            int(widget.winfo_x()),
            int(widget.winfo_y()),
            int(widget.winfo_width()),
            int(widget.winfo_height()),
        )
        work = (
            0,
            0,
            int(widget.winfo_screenwidth()),
            int(widget.winfo_screenheight()),
        )
        fixed = clamp_rect_to_work_area(rect, work)
        if fixed != rect:
            x, y, width, height = fixed
            widget.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


def _poll_main_window_state(widget) -> None:
    try:
        if not bool(widget.winfo_exists()):
            return
        state = str(widget.state()).lower()
    except Exception:
        return

    previous = getattr(widget, "_turto_window_state_227", None)
    if state != previous:
        widget._turto_window_state_227 = state
        if state == "normal":
            # Windows first announces the state transition and then finishes
            # applying the restore rectangle. Check both moments.
            try:
                widget.after(40, lambda: _ensure_main_window_visible(widget))
                widget.after(220, lambda: _ensure_main_window_visible(widget))
            except Exception:
                pass

    try:
        widget.after(120, lambda: _poll_main_window_state(widget))
    except Exception:
        pass


_ORIGINAL_APP_INIT_227 = _base.ThermalConnectorApp.__init__


def _guarded_app_init_227(self, *args, **kwargs) -> None:
    _ORIGINAL_APP_INIT_227(self, *args, **kwargs)
    self._turto_window_state_227 = None
    try:
        self.after(80, lambda: _poll_main_window_state(self))
    except Exception:
        pass


_base.ThermalConnectorApp.__init__ = _guarded_app_init_227

try:
    _base.APP_VERSION = APP_VERSION
    _base.APP_NAME = "TURTO"
except Exception:
    pass

try:
    if _hit_workspace is not None:
        _hit_workspace.HIT_MODULE_VERSION = APP_VERSION
        if hasattr(_hit_workspace, "_base"):
            _hit_workspace._base.HIT_MODULE_VERSION = APP_VERSION
except Exception:
    pass

try:
    import platform_workspace as _platform_workspace
    _platform_workspace.WORKSPACE_VERSION = APP_VERSION
except Exception:
    pass


def selftest() -> None:
    assert APP_VERSION == "2.2.27"
    assert BASE_RUNTIME.name == "app_runtime_221.pyw"
    assert _base is not None
    assert not _missing_shear_methods
    assert clamp_rect_to_work_area((2500, 100, 1200, 800), (0, 0, 1920, 1040)) == (
        712, 100, 1200, 800
    )
    assert clamp_rect_to_work_area((100, 100, 1200, 800), (0, 0, 1920, 1040)) == (
        100, 100, 1200, 800
    )


if __name__ == "__main__":
    raise SystemExit(_base.main())
