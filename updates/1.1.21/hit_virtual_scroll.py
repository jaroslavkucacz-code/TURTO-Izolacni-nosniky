from __future__ import annotations

"""Viewport-based rendering for the large Tkinter HIT proposal grid."""

from typing import Any
from tkinter import ttk

from hit_row_extension import ROW_HEIGHT, grid_row_widgets

MARGIN_ROWS = 5


def install(base: Any) -> None:
    original_init = base.HitWorkspaceMixin._init_hit_workspace
    original_build = base.HitWorkspaceMixin._build_hit_tab
    original_canvas_configure = base.HitWorkspaceMixin._on_hit_canvas_configure

    def schedule_scrollregion(self) -> None:
        if not hasattr(self, "hit_canvas") or getattr(self, "_hit_scrollregion_job", None):
            return
        self._hit_scrollregion_job = self.after_idle(self._hit_apply_scrollregion)

    def apply_scrollregion(self) -> None:
        self._hit_scrollregion_job = None
        if not hasattr(self, "hit_canvas"):
            return
        try:
            bbox = self.hit_canvas.bbox("all")
            if bbox:
                self.hit_canvas.configure(scrollregion=bbox)
        except Exception:
            pass

    def reconfigure_minsizes(self) -> None:
        count = len(getattr(self, "hit_rows", []))
        maximum = max(count, int(getattr(self, "_hit_grid_rows_max", 0) or 0))
        for index in range(1, maximum + 1):
            try:
                self.hit_rows_frame.grid_rowconfigure(index, minsize=ROW_HEIGHT if index <= count else 0)
            except Exception:
                pass
        self._hit_grid_rows_max = count
        self._hit_schedule_scrollregion()

    def schedule_refresh(self) -> None:
        if not getattr(self, "_hit_virtual_enabled", False) or not hasattr(self, "hit_canvas"):
            return
        if getattr(self, "_hit_virtual_job", None):
            return
        self._hit_virtual_job = self.after_idle(self._hit_refresh_virtual_rows)

    def refresh(self) -> None:
        self._hit_virtual_job = None
        if not getattr(self, "_hit_virtual_enabled", False) or not hasattr(self, "hit_canvas"):
            return
        try:
            y0 = float(self.hit_canvas.canvasy(0))
            height = max(1, int(self.hit_canvas.winfo_height()))
        except Exception:
            y0, height = 0.0, 800
        first = max(1, int(y0 // ROW_HEIGHT) - MARGIN_ROWS)
        last = min(
            max(1, len(self.hit_rows)),
            int((y0 + height) // ROW_HEIGHT) + MARGIN_ROWS + 2,
        )
        self._hit_visible_first = first
        self._hit_visible_last = last
        for index, row in enumerate(self.hit_rows, 1):
            row.row_no = index
            grid_row_widgets(row, first <= index <= last)
        self._hit_schedule_scrollregion()

    def shift_headers(self) -> None:
        if getattr(self, "_hit_quantity_header_added", False):
            return
        row_widgets = {widget for row in self.hit_rows for widget in getattr(row, "widgets", [])}
        headers = []
        for child in self.hit_rows_frame.winfo_children():
            if child in row_widgets:
                continue
            try:
                info = child.grid_info()
                if int(info.get("row", -1)) == 0:
                    headers.append((int(info.get("column", 0)), child))
            except Exception:
                pass
        for column, widget in sorted(headers, reverse=True):
            if column >= 1:
                widget.grid_configure(column=column + 1)
        ttk.Label(
            self.hit_rows_frame,
            text="Ks",
            style="Card.TLabel",
            font=("Calibri", 10, "bold"),
            anchor="center",
        ).grid(row=0, column=1, sticky="ew", padx=2, pady=(0, 5))
        for column in (18, 23):
            self.hit_rows_frame.columnconfigure(column, weight=0)
        for column in (0, 19, 24):
            self.hit_rows_frame.columnconfigure(column, weight=1)
        self.hit_rows_frame.columnconfigure(1, weight=0)
        self._hit_quantity_header_added = True

    def init_workspace(self) -> None:
        original_init(self)
        self._hit_virtual_enabled = False
        self._hit_visible_first = 1
        self._hit_visible_last = 40
        self._hit_scrollregion_job = None
        self._hit_virtual_job = None
        self._hit_grid_rows_max = 0

    def build_tab(self, parent) -> None:
        self._hit_virtual_enabled = True
        self._hit_visible_first = 1
        self._hit_visible_last = 40
        original_build(self, parent)
        self._hit_shift_quantity_headers()
        try:
            self.hit_canvas.configure(yscrollincrement=ROW_HEIGHT)
            for child in self.hit_canvas.master.winfo_children():
                if isinstance(child, ttk.Scrollbar) and str(child.cget("orient")) == "vertical":
                    child.bind("<B1-Motion>", lambda _e: self._hit_schedule_virtual_refresh(), add="+")
                    child.bind("<ButtonRelease-1>", lambda _e: self._hit_schedule_virtual_refresh(), add="+")
        except Exception:
            pass
        self._hit_reconfigure_row_minsizes()
        self._hit_schedule_virtual_refresh()

    def rows_configure(self, _event: Any = None) -> None:
        self._hit_schedule_scrollregion()

    def canvas_configure(self, event: Any) -> None:
        original_canvas_configure(self, event)
        self._hit_schedule_virtual_refresh()

    def mousewheel(self, event: Any) -> str:
        if not hasattr(self, "hit_canvas"):
            return "break"
        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return "break"
        direction = -1 if delta > 0 else 1
        magnitude = max(1, abs(delta) // 120)
        try:
            self.hit_canvas.yview_scroll(direction * magnitude * 2, "units")
        except Exception:
            pass
        self._hit_schedule_virtual_refresh()
        return "break"

    base.HitWorkspaceMixin._hit_schedule_scrollregion = schedule_scrollregion
    base.HitWorkspaceMixin._hit_apply_scrollregion = apply_scrollregion
    base.HitWorkspaceMixin._hit_reconfigure_row_minsizes = reconfigure_minsizes
    base.HitWorkspaceMixin._hit_schedule_virtual_refresh = schedule_refresh
    base.HitWorkspaceMixin._hit_refresh_virtual_rows = refresh
    base.HitWorkspaceMixin._hit_shift_quantity_headers = shift_headers
    base.HitWorkspaceMixin._init_hit_workspace = init_workspace
    base.HitWorkspaceMixin._build_hit_tab = build_tab
    base.HitWorkspaceMixin._on_hit_rows_configure = rows_configure
    base.HitWorkspaceMixin._on_hit_canvas_configure = canvas_configure
    base.HitWorkspaceMixin._on_hit_mousewheel = mousewheel
