from __future__ import annotations

"""Quantity and row lifecycle extensions for direct HIT proposals."""

from typing import Any
import tkinter as tk
from tkinter import ttk

ROW_HEIGHT = 34


def quantity_int(row: Any) -> int:
    variable = getattr(row, "quantity", None)
    raw = str(variable.get() if variable is not None else "1").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{row.name.get()}: počet kusů musí být celé číslo.") from exc
    if value < 1:
        raise ValueError(f"{row.name.get()}: počet kusů musí být alespoň 1.")
    if value > 1_000_000:
        raise ValueError(f"{row.name.get()}: počet kusů je neobvykle vysoký.")
    return value


def _quantity_finished(row: Any, _event: Any = None) -> None:
    try:
        value = quantity_int(row)
    except ValueError:
        row.quantity.set("1")
        try:
            row.owner.hit_status_var.set(f"{row.name.get()}: neplatné množství bylo vráceno na 1 ks.")
        except Exception:
            pass
        return
    row.quantity.set(str(value))
    try:
        row.owner.update_hit_status()
    except Exception:
        pass


def row_widgets_in_order(row: Any) -> list[Any]:
    base = list(getattr(row, "_hit_base_widgets", []))
    qty = getattr(row, "quantity_entry", None)
    if not base or qty is None:
        return list(getattr(row, "widgets", []))
    return [base[0], qty, *base[1:]]


def grid_row_widgets(row: Any, visible: bool, *, force: bool = False) -> None:
    previous_visible = getattr(row, "_hit_grid_visible", None)
    previous_row = getattr(row, "_hit_grid_row", None)
    if not force and previous_visible is visible and (not visible or previous_row == row.row_no):
        return
    owner = row.owner
    try:
        owner.hit_rows_frame.grid_rowconfigure(row.row_no, minsize=ROW_HEIGHT)
    except Exception:
        pass
    ordered = row_widgets_in_order(row)
    if visible:
        for column, widget in enumerate(ordered):
            try:
                widget.grid(row=row.row_no, column=column, sticky="ew", padx=2, pady=2)
            except Exception:
                pass
    else:
        for widget in ordered:
            try:
                widget.grid_remove()
            except Exception:
                pass
    row._hit_grid_visible = bool(visible)
    row._hit_grid_row = row.row_no


def install(base: Any) -> None:
    original_row_init = base.HitInputRow.__init__
    original_row_regrid = base.HitInputRow.regrid
    original_row_defaults = base.HitInputRow.defaults_for_next
    original_add = base.HitWorkspaceMixin.add_hit_row
    original_remove = base.HitWorkspaceMixin.remove_hit_row

    def row_init(self, owner, row_no: int, defaults: dict[str, Any] | None = None) -> None:
        values = dict(defaults or {})
        self.quantity = tk.StringVar(master=owner, value=str(values.get("quantity", "1") or "1"))
        self._saved_manual_product = bool(values.get("manual_product", False))
        self._saved_designation = (
            str(values.get("selected_designation", "") or "") if self._saved_manual_product else ""
        )
        self._hit_defer_initial_grid = True
        original_row_init(self, owner, row_no, values)
        self._hit_defer_initial_grid = False
        self._hit_base_widgets = list(self.widgets)
        self.quantity_entry = ttk.Entry(owner.hit_rows_frame, textvariable=self.quantity, width=6, justify="center")
        self.quantity_entry.bind("<FocusOut>", lambda event: _quantity_finished(self, event))
        self.quantity_entry.bind("<Return>", lambda event: _quantity_finished(self, event))
        self.quantity_entry.bind("<MouseWheel>", owner._on_hit_mousewheel)
        self.widgets.append(self.quantity_entry)
        for widget in self._hit_base_widgets:
            try:
                widget.bind("<MouseWheel>", owner._on_hit_mousewheel, add="+")
            except Exception:
                pass
        self.regrid(row_no)

    def row_regrid(self, row_no: int) -> None:
        self.row_no = row_no
        if getattr(self, "_hit_defer_initial_grid", False) and getattr(getattr(self, "owner", None), "_hit_virtual_enabled", False):
            try:
                self.owner.hit_rows_frame.grid_rowconfigure(row_no, minsize=ROW_HEIGHT)
            except Exception:
                pass
            return
        if not hasattr(self, "quantity_entry"):
            original_row_regrid(self, row_no)
            return
        owner = self.owner
        if not getattr(owner, "_hit_virtual_enabled", False):
            grid_row_widgets(self, True, force=True)
            return
        first = int(getattr(owner, "_hit_visible_first", 1) or 1)
        last = int(getattr(owner, "_hit_visible_last", 40) or 40)
        grid_row_widgets(self, first <= row_no <= last, force=True)

    def row_defaults(self) -> dict[str, str]:
        result = dict(original_row_defaults(self))
        result["quantity"] = "1"
        return result

    def add_row(self) -> None:
        original_add(self)
        if hasattr(self, "_hit_reconfigure_row_minsizes"):
            self._hit_reconfigure_row_minsizes()
        if hasattr(self, "_hit_schedule_virtual_refresh"):
            self._hit_schedule_virtual_refresh()

    def remove_row(self, row: Any) -> None:
        original_remove(self, row)
        if hasattr(self, "_hit_reconfigure_row_minsizes"):
            self._hit_reconfigure_row_minsizes()
        if hasattr(self, "_hit_schedule_virtual_refresh"):
            self._hit_schedule_virtual_refresh()

    def recalculate_all(self) -> None:
        if not getattr(self, "_hit_built", False):
            return
        for row in list(self.hit_rows):
            preserve = row.product.get() if getattr(row, "_manual_product", False) else None
            if not preserve:
                preserve = str(getattr(row, "_saved_designation", "") or "") or None
            saved_restore = bool(getattr(row, "_saved_designation", ""))
            saved_manual = bool(getattr(row, "_saved_manual_product", False))
            row.recalculate(preserve_product=preserve)
            if preserve and row.selected_candidate is not None and row.selected_candidate.designation == preserve and saved_manual:
                row._manual_product = True
            if saved_restore:
                row._saved_designation = ""
                row._saved_manual_product = False
        self.update_hit_status()
        if hasattr(self, "_hit_schedule_virtual_refresh"):
            self._hit_schedule_virtual_refresh()

    base.HitInputRow.__init__ = row_init
    base.HitInputRow.regrid = row_regrid
    base.HitInputRow.defaults_for_next = row_defaults
    base.HitWorkspaceMixin.add_hit_row = add_row
    base.HitWorkspaceMixin.remove_hit_row = remove_row
    base.HitWorkspaceMixin.recalculate_hit_all = recalculate_all
