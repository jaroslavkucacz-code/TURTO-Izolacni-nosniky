from __future__ import annotations

"""Viewport-based rendering for the large Tkinter HIT proposal grid."""

from typing import Any
import math
from tkinter import ttk

from hit_row_extension import ROW_HEIGHT, grid_row_widgets as _grid_row_widgets, row_widgets_in_order

MARGIN_ROWS = 8


def grid_row_widgets(row, visible):
    _grid_row_widgets(row, visible)
    height = getattr(row.owner, '_hit_row_height_311', ROW_HEIGHT)
    if height != ROW_HEIGHT:
        row.owner.hit_rows_frame.grid_rowconfigure(row.row_no, minsize=height)


def _lock_columns(owner):
    """Keep natural column widths when a wider row leaves the viewport."""
    frame = owner.hit_rows_frame
    widths = getattr(owner, '_hit_column_widths_311', {})
    measured = dict(widths)
    for widget in frame.grid_slaves():
        info = widget.grid_info()
        if int(info.get('columnspan', 1)) != 1:
            continue
        col = int(info['column'])
        measured[col] = max(measured.get(col, 0), widget.winfo_reqwidth() + 4)
    for col, width in measured.items():
        if width != widths.get(col):
            frame.columnconfigure(col, minsize=width)
    owner._hit_column_widths_311 = measured


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
            if bbox and bbox != getattr(self, '_hit_scrollregion_311', None):
                self.hit_canvas.configure(scrollregion=bbox)
                self._hit_scrollregion_311 = bbox
        except Exception:
            pass

    def reconfigure_minsizes(self) -> None:
        count = len(getattr(self, "hit_rows", []))
        previous = int(getattr(self, '_hit_grid_rows_max', 0) or 0)
        height = getattr(self, '_hit_row_height_311', ROW_HEIGHT)
        same_height = height == getattr(self, '_hit_grid_height_311', ROW_HEIGHT)
        start = min(count, previous) + 1 if same_height else 1
        for index in range(start, max(count, previous) + 1):
            try:
                self.hit_rows_frame.grid_rowconfigure(index, minsize=height if index <= count else 0)
            except Exception:
                pass
        self._hit_grid_rows_max = count
        self._hit_grid_height_311 = height
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
        if not self.hit_canvas.winfo_ismapped():
            return  # A hidden tab's transient size must not collapse its rows.
        try:
            y0 = float(self.hit_canvas.canvasy(0))
            height = max(1, int(self.hit_canvas.winfo_height()))
        except Exception:
            y0, height = 0.0, 800
        rows = self.hit_rows
        row_height = max([ROW_HEIGHT] + [w.winfo_reqheight() + 4
                         for row in rows[:1] for w in row_widgets_in_order(row)])
        if row_height != getattr(self, '_hit_row_height_311', ROW_HEIGHT):
            self._hit_row_height_311 = row_height
            self._hit_reconfigure_row_minsizes()
        header = self.hit_rows_frame.grid_bbox(0, 0, 0, 0)[3]
        top = max(1, int((y0 - header) // row_height) + 1)
        bottom = min(len(rows), math.ceil((y0 + height - header) / row_height) + 1)
        signature = (tuple(id(r) for r in rows), row_height)
        old_first = getattr(self, '_hit_visible_first', 1)
        old_last = getattr(self, '_hit_visible_last', 0)
        # Reuse the buffered viewport for small moves; map only near its edges.
        if (signature == getattr(self, '_hit_mounted_311', None)
                and (old_first == 1 or top >= old_first + 2)
                and (old_last == len(rows) or bottom <= old_last - 2)):
            return
        first = max(1, top - MARGIN_ROWS)
        last = min(len(rows), bottom + MARGIN_ROWS)
        self._hit_visible_first = first
        self._hit_visible_last = last
        focus = self.focus_get()
        for index, row in enumerate(rows, 1):
            row.row_no = index
            # Retain the focused editor even when scrolled out of view.
            grid_row_widgets(row, first <= index <= last or focus in row.widgets)
        self._hit_mounted_311 = signature
        _lock_columns(self)
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
            self.hit_canvas.bind('<Map>', lambda _e: self._hit_schedule_virtual_refresh(), add='+')
            for child in self.hit_canvas.master.winfo_children():
                if isinstance(child, ttk.Scrollbar) and str(child.cget("orient")) == "vertical":
                    def position(first, last, bar=child):
                        bar.set(first, last)
                        self._hit_schedule_virtual_refresh()
                    # Covers thumb, arrow, track, wheel and programmatic moves.
                    self.hit_canvas.configure(yscrollcommand=position)
        except Exception:
            pass
        self._hit_reconfigure_row_minsizes()
        self._hit_schedule_virtual_refresh()

    def rows_configure(self, _event: Any = None) -> None:
        self._hit_schedule_scrollregion()

    def canvas_configure(self, event: Any) -> None:
        width = max(event.width, self.hit_rows_frame.winfo_reqwidth())
        if int(float(self.hit_canvas.itemcget(self.hit_canvas_window, 'width'))) != width:
            self.hit_canvas.itemconfigure(self.hit_canvas_window, width=width)
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
