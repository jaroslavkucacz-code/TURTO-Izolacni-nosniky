from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.10"
OUT = ROOT / "updates" / "0.6.11"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(fn(text), encoding="utf-8")


def patch_app(text: str) -> str:
    text = replace_once(text, 'APP_VERSION = "0.6.10"', 'APP_VERSION = "0.6.11"', "app version")
    old = '''    def on_close(self) -> None:\n        if not self.confirm_project_close():\n            return\n        selections: dict[str, Any] = {\n'''
    new = '''    def on_close(self) -> None:\n        if not self.confirm_project_close():\n            return\n        try:\n            if hasattr(self, "capture_project_table_layout"):\n                self.capture_project_table_layout(save=False)\n        except Exception:\n            pass\n        selections: dict[str, Any] = {\n'''
    return replace_once(text, old, new, "capture project layout on close")


def project_helpers() -> str:
    return r'''
    # ---------- trvalé rozložení sloupců ----------

    def _project_layout_state(self) -> dict[str, Any]:
        layouts = self.settings.setdefault("table_layouts", {})
        if not isinstance(layouts, dict):
            layouts = {}
            self.settings["table_layouts"] = layouts
        state = layouts.setdefault("project", {})
        if not isinstance(state, dict):
            state = {}
            layouts["project"] = state

        ids = [item[0] for item in self.PROJECT_COLUMNS]
        order = [str(x) for x in state.get("order", []) if str(x) in ids]
        order.extend(column for column in ids if column not in order)
        hidden = [str(x) for x in state.get("hidden", []) if str(x) in ids]
        if len(hidden) >= len(ids):
            hidden = hidden[:-1]
        raw_widths = state.get("widths", {}) if isinstance(state.get("widths", {}), dict) else {}
        widths: dict[str, int] = {}
        for column, _label, default_width, _anchor, _stretch in self.PROJECT_COLUMNS:
            try:
                widths[column] = max(42, min(1600, int(raw_widths.get(column, default_width))))
            except (TypeError, ValueError):
                widths[column] = default_width
        state["order"] = order
        state["hidden"] = hidden
        state["widths"] = widths
        sort = state.get("sort") if isinstance(state.get("sort"), dict) else {}
        sort_column = str(sort.get("column", ""))
        if sort_column not in ids:
            sort_column = ""
        state["sort"] = {"column": sort_column, "reverse": bool(sort.get("reverse", False))}
        return state

    def _project_visible_columns(self) -> list[str]:
        state = self._project_layout_state()
        hidden = set(state.get("hidden", []))
        visible = [column for column in state["order"] if column not in hidden]
        if not visible:
            visible = [state["order"][0]]
            state["hidden"] = [column for column in state["order"] if column != visible[0]]
        return visible

    def _apply_project_column_layout(self) -> None:
        if not hasattr(self, "project_tree"):
            return
        state = self._project_layout_state()
        self.project_tree.configure(displaycolumns=tuple(self._project_visible_columns()))
        for column, _label, default_width, _anchor, _stretch in self.PROJECT_COLUMNS:
            width = int(state.get("widths", {}).get(column, default_width))
            self.project_tree.column(column, width=width)
        self._update_project_heading_labels()

    def _update_project_heading_labels(self) -> None:
        if not hasattr(self, "project_tree"):
            return
        for column, label in self._project_heading_labels.items():
            arrow = ""
            if column == self.project_sort_column:
                arrow = " ▼" if self.project_sort_reverse else " ▲"
            self.project_tree.heading(column, text=label + arrow)

    def capture_project_table_layout(self, *, save: bool = True) -> None:
        if not hasattr(self, "project_tree"):
            return
        state = self._project_layout_state()
        widths = state.setdefault("widths", {})
        for column, _label, _default, _anchor, _stretch in self.PROJECT_COLUMNS:
            try:
                widths[column] = int(self.project_tree.column(column, "width"))
            except Exception:
                pass
        state["sort"] = {"column": self.project_sort_column or "", "reverse": bool(self.project_sort_reverse)}
        if save and hasattr(self, "_save_settings"):
            self._save_settings()

    def _set_project_column_visible(self, column: str, visible: bool) -> None:
        state = self._project_layout_state()
        hidden = list(state.get("hidden", []))
        if visible:
            hidden = [value for value in hidden if value != column]
        elif column not in hidden:
            if len(self._project_visible_columns()) <= 1:
                messagebox.showinfo("Sloupce", "Alespoň jeden sloupec musí zůstat zobrazený.", parent=self)
                return
            hidden.append(column)
        state["hidden"] = hidden
        self._apply_project_column_layout()
        self.capture_project_table_layout()

    def _move_project_column(self, column: str, delta: int | None = None, *, edge: str | None = None) -> None:
        state = self._project_layout_state()
        order = list(state["order"])
        if column not in order:
            return
        old = order.index(column)
        if edge == "first":
            new = 0
        elif edge == "last":
            new = len(order) - 1
        else:
            new = max(0, min(len(order) - 1, old + int(delta or 0)))
        if new == old:
            return
        order.pop(old)
        order.insert(new, column)
        state["order"] = order
        self._apply_project_column_layout()
        self.capture_project_table_layout()

    def _show_all_project_columns(self) -> None:
        state = self._project_layout_state()
        state["hidden"] = []
        self._apply_project_column_layout()
        self.capture_project_table_layout()

    def _reset_project_column_layout(self) -> None:
        layouts = self.settings.setdefault("table_layouts", {})
        if isinstance(layouts, dict):
            layouts.pop("project", None)
        self.project_sort_column = None
        self.project_sort_reverse = False
        self._apply_project_column_layout()
        self.capture_project_table_layout()
        self.set_status("Rozložení projektové tabulky bylo obnoveno na výchozí stav.")

    def _project_column_from_x(self, x: int) -> str | None:
        if not hasattr(self, "project_tree"):
            return None
        marker = str(self.project_tree.identify_column(x))
        if not marker.startswith("#"):
            return None
        try:
            index = int(marker[1:]) - 1
        except ValueError:
            return None
        visible = self._project_visible_columns()
        return visible[index] if 0 <= index < len(visible) else None

    def _make_project_columns_menu(self, parent_menu: tk.Menu) -> tk.Menu:
        menu = tk.Menu(
            parent_menu,
            tearoff=False,
            font=("Calibri", 10),
            background=self.colors["panel"],
            foreground=self.colors["text"],
            activebackground=self.colors["accent"],
            activeforeground="#FFFFFF",
        )
        state = self._project_layout_state()
        hidden = set(state.get("hidden", []))
        variables: list[tk.BooleanVar] = []
        for column in state["order"]:
            label = self._project_heading_labels.get(column, column)
            variable = tk.BooleanVar(value=column not in hidden)
            variables.append(variable)
            menu.add_checkbutton(
                label=label,
                variable=variable,
                command=lambda col=column, var=variable: self._set_project_column_visible(col, bool(var.get())),
            )
        menu._turto_vars = variables  # type: ignore[attr-defined]
        menu.add_separator()
        menu.add_command(label="Zobrazit všechny", command=self._show_all_project_columns)
        menu.add_command(label="Výchozí rozložení", command=self._reset_project_column_layout)
        return menu

    def _show_project_columns_button_menu(self) -> None:
        button = getattr(self, "project_columns_button", None)
        if button is None:
            return
        menu = self._make_project_columns_menu(button)
        try:
            menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())
        finally:
            menu.grab_release()

    def _show_project_header_menu(self, event: tk.Event[Any]) -> str | None:
        if self.project_tree.identify_region(event.x, event.y) != "heading":
            return None
        column = self._project_column_from_x(event.x)
        if not column:
            return "break"
        menu = tk.Menu(
            self,
            tearoff=False,
            font=("Calibri", 10),
            background=self.colors["panel"],
            foreground=self.colors["text"],
            activebackground=self.colors["accent"],
            activeforeground="#FFFFFF",
        )
        label = self._project_heading_labels.get(column, column)
        menu.add_command(label=f"Seřadit {label} vzestupně", command=lambda: self.sort_project_table(column, reverse=False))
        menu.add_command(label=f"Seřadit {label} sestupně", command=lambda: self.sort_project_table(column, reverse=True))
        menu.add_separator()
        menu.add_command(label="Přesunout vlevo", command=lambda: self._move_project_column(column, -1))
        menu.add_command(label="Přesunout vpravo", command=lambda: self._move_project_column(column, 1))
        menu.add_command(label="Přesunout na začátek", command=lambda: self._move_project_column(column, edge="first"))
        menu.add_command(label="Přesunout na konec", command=lambda: self._move_project_column(column, edge="last"))
        menu.add_separator()
        menu.add_command(label="Skrýt tento sloupec", command=lambda: self._set_project_column_visible(column, False))
        columns_menu = self._make_project_columns_menu(menu)
        menu.add_cascade(label="Zobrazit / skrýt sloupce", menu=columns_menu)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _on_project_tree_release(self, event: tk.Event[Any]) -> None:
        if self.project_tree.identify_region(event.x, event.y) == "separator":
            self.after_idle(lambda: self.capture_project_table_layout())
'''


def patch_project_ui(text: str) -> str:
    init_old = '''        self.project_sort_column: str | None = None\n        self.project_sort_reverse = False\n        self.project_result_cache: dict[str, QueryResult | None] = {}\n'''
    init_new = '''        layout = self._project_layout_state()\n        sort = layout.get("sort", {}) if isinstance(layout.get("sort", {}), dict) else {}\n        self.project_sort_column: str | None = str(sort.get("column", "")) or None\n        self.project_sort_reverse = bool(sort.get("reverse", False))\n        self.project_result_cache: dict[str, QueryResult | None] = {}\n'''
    text = replace_once(text, init_old, init_new, "project layout init")

    marker = '''    def _configure_project_styles(self) -> None:\n'''
    text = replace_once(text, marker, project_helpers() + "\n" + marker, "project layout helpers")

    old_action = '''        ttk.Button(actionbar, text="Smazat", style="Danger.TButton", command=self.delete_selected_project_rows).grid(\n            row=0, column=6, padx=(7, 0)\n        )\n        ttk.Label(actionbar, text="Filtr", style="Card.TLabel").grid(row=0, column=8, padx=(18, 6))\n'''
    new_action = '''        ttk.Button(actionbar, text="Smazat", style="Danger.TButton", command=self.delete_selected_project_rows).grid(\n            row=0, column=6, padx=(7, 0)\n        )\n        self.project_columns_button = ttk.Button(actionbar, text="Sloupce…", command=self._show_project_columns_button_menu)\n        self.project_columns_button.grid(row=0, column=7, padx=(7, 0))\n        ttk.Label(actionbar, text="Filtr", style="Card.TLabel").grid(row=0, column=8, padx=(18, 6))\n'''
    text = replace_once(text, old_action, new_action, "project columns button")

    old_hint = '''                "Dvojklik načte řádek do detailního editoru. Více řádků lze označit pomocí Ctrl/Shift; "\n                "kopírování bez výběru použije všechny právě zobrazené řádky."\n'''
    new_hint = '''                "Dvojklik načte řádek do detailního editoru. Více řádků lze označit pomocí Ctrl/Shift. "\n                "Tlačítko Sloupce… nebo pravý klik na záhlaví umožní sloupce skrýt, přesunout a řadit; rozložení se ukládá automaticky."\n'''
    text = replace_once(text, old_hint, new_hint, "project columns hint")

    loop_old = '''        self._project_heading_labels = {column: label for column, label, *_rest in self.PROJECT_COLUMNS}\n        for column, label, width, anchor, stretch in self.PROJECT_COLUMNS:\n            self.project_tree.heading(column, text=label, command=lambda col=column: self.sort_project_table(col))\n            self.project_tree.column(column, width=width, minwidth=42, anchor=anchor, stretch=stretch)\n'''
    loop_new = '''        self._project_heading_labels = {column: label for column, label, *_rest in self.PROJECT_COLUMNS}\n        layout = self._project_layout_state()\n        for column, label, width, anchor, stretch in self.PROJECT_COLUMNS:\n            saved_width = int(layout.get("widths", {}).get(column, width))\n            self.project_tree.heading(column, text=label, command=lambda col=column: self.sort_project_table(col))\n            self.project_tree.column(column, width=saved_width, minwidth=42, anchor=anchor, stretch=stretch)\n        self._apply_project_column_layout()\n'''
    text = replace_once(text, loop_old, loop_new, "project apply saved layout")

    bind_old = '''        self.project_tree.bind("<<TreeviewSelect>>", self._on_project_tree_selection)\n\n        self._build_project_context_menu()\n        self.project_tree.bind("<Button-3>", self._show_project_context_menu)\n'''
    bind_new = '''        self.project_tree.bind("<<TreeviewSelect>>", self._on_project_tree_selection)\n        self.project_tree.bind("<ButtonRelease-1>", self._on_project_tree_release, add="+")\n\n        self._build_project_context_menu()\n        self.project_tree.bind("<Button-3>", self._show_project_context_menu)\n'''
    text = replace_once(text, bind_old, bind_new, "project width persistence binding")

    context_old = '''    def _show_project_context_menu(self, event: tk.Event[Any]) -> None:\n        row_id = self.project_tree.identify_row(event.y)\n        if row_id:\n            if row_id not in self.project_tree.selection():\n                self.project_tree.selection_set(row_id)\n            self.project_tree.focus(row_id)\n            try:\n                self.project_context_menu.tk_popup(event.x_root, event.y_root)\n            finally:\n                self.project_context_menu.grab_release()\n'''
    context_new = '''    def _show_project_context_menu(self, event: tk.Event[Any]) -> str | None:\n        if self.project_tree.identify_region(event.x, event.y) == "heading":\n            return self._show_project_header_menu(event)\n        row_id = self.project_tree.identify_row(event.y)\n        if row_id:\n            if row_id not in self.project_tree.selection():\n                self.project_tree.selection_set(row_id)\n            self.project_tree.focus(row_id)\n            try:\n                self.project_context_menu.tk_popup(event.x_root, event.y_root)\n            finally:\n                self.project_context_menu.grab_release()\n        return None\n'''
    text = replace_once(text, context_old, context_new, "project header context menu")

    sort_old = '''    def sort_project_table(self, column: str) -> None:\n        if self.project_sort_column == column:\n            self.project_sort_reverse = not self.project_sort_reverse\n        else:\n            self.project_sort_column = column\n            self.project_sort_reverse = False\n        for col, label in self._project_heading_labels.items():\n            arrow = ""\n            if col == self.project_sort_column:\n                arrow = " ▼" if self.project_sort_reverse else " ▲"\n            self.project_tree.heading(col, text=label + arrow)\n        self.refresh_project_tree()\n'''
    sort_new = '''    def sort_project_table(self, column: str, reverse: bool | None = None) -> None:\n        if reverse is not None:\n            self.project_sort_column = column\n            self.project_sort_reverse = bool(reverse)\n        elif self.project_sort_column == column:\n            self.project_sort_reverse = not self.project_sort_reverse\n        else:\n            self.project_sort_column = column\n            self.project_sort_reverse = False\n        self._update_project_heading_labels()\n        self.capture_project_table_layout()\n        self.refresh_project_tree()\n'''
    text = replace_once(text, sort_old, sort_new, "project persistent sort")

    dialog_old = '''        dialog = BulkImportDialog(\n            self,\n            database=self.database,\n            colors=self.colors,\n            preferred_concrete=self.project_concrete_var.get(),\n            existing_positions=[str(row.get("position", "")) for row in self.project.rows],\n            start_position=self.project.next_position(),\n        )\n'''
    dialog_new = '''        dialog = BulkImportDialog(\n            self,\n            database=self.database,\n            colors=self.colors,\n            preferred_concrete=self.project_concrete_var.get(),\n            existing_positions=[str(row.get("position", "")) for row in self.project.rows],\n            start_position=self.project.next_position(),\n            settings=self.settings,\n            save_settings=getattr(self, "_save_settings", None),\n        )\n'''
    text = replace_once(text, dialog_old, dialog_new, "pass settings to bulk dialog")
    return text


def bulk_helpers() -> str:
    return r'''
    # ---------- trvalé rozložení kontrolní tabulky ----------

    def _review_layout_state(self) -> dict[str, Any]:
        layouts = self.settings.setdefault("table_layouts", {})
        if not isinstance(layouts, dict):
            layouts = {}
            self.settings["table_layouts"] = layouts
        state = layouts.setdefault("bulk_review", {})
        if not isinstance(state, dict):
            state = {}
            layouts["bulk_review"] = state
        ids = list(self._review_heading_labels)
        order = [str(x) for x in state.get("order", []) if str(x) in ids]
        order.extend(column for column in ids if column not in order)
        hidden = [str(x) for x in state.get("hidden", []) if str(x) in ids]
        if len(hidden) >= len(ids):
            hidden = hidden[:-1]
        defaults = self._review_column_defaults
        raw_widths = state.get("widths", {}) if isinstance(state.get("widths", {}), dict) else {}
        widths = {}
        for column in ids:
            try:
                widths[column] = max(40, min(1400, int(raw_widths.get(column, defaults[column][0]))))
            except (TypeError, ValueError):
                widths[column] = defaults[column][0]
        sort = state.get("sort") if isinstance(state.get("sort"), dict) else {}
        sort_column = str(sort.get("column", ""))
        if sort_column not in ids:
            sort_column = ""
        state.update({"order": order, "hidden": hidden, "widths": widths, "sort": {"column": sort_column, "reverse": bool(sort.get("reverse", False))}})
        return state

    def _review_visible_columns(self) -> list[str]:
        state = self._review_layout_state()
        hidden = set(state["hidden"])
        visible = [column for column in state["order"] if column not in hidden]
        return visible or [state["order"][0]]

    def _apply_review_layout(self) -> None:
        state = self._review_layout_state()
        self.review_tree.configure(displaycolumns=tuple(self._review_visible_columns()))
        for column, (default_width, _anchor) in self._review_column_defaults.items():
            self.review_tree.column(column, width=int(state["widths"].get(column, default_width)))
        self._update_review_headings()

    def _save_review_layout(self, *, capture_widths: bool = True) -> None:
        state = self._review_layout_state()
        if capture_widths:
            for column in self._review_heading_labels:
                try:
                    state["widths"][column] = int(self.review_tree.column(column, "width"))
                except Exception:
                    pass
        state["sort"] = {"column": self.review_sort_column or "", "reverse": bool(self.review_sort_reverse)}
        if self.save_settings is not None:
            self.save_settings()

    def _update_review_headings(self) -> None:
        for column, label in self._review_heading_labels.items():
            arrow = ""
            if column == self.review_sort_column:
                arrow = " ▼" if self.review_sort_reverse else " ▲"
            self.review_tree.heading(column, text=label + arrow)

    def _sort_review_table(self, column: str, reverse: bool | None = None, *, save: bool = True) -> None:
        if reverse is not None:
            self.review_sort_column = column
            self.review_sort_reverse = bool(reverse)
        elif self.review_sort_column == column:
            self.review_sort_reverse = not self.review_sort_reverse
        else:
            self.review_sort_column = column
            self.review_sort_reverse = False

        def key(iid: str):
            value = self.review_tree.set(iid, column)
            if column in {"line", "qty"}:
                try:
                    return (0, float(str(value).replace(",", ".")))
                except ValueError:
                    return (1, str(value).casefold())
            return (1, str(value).casefold())

        rows = list(self.review_tree.get_children(""))
        rows.sort(key=key, reverse=self.review_sort_reverse)
        for index, iid in enumerate(rows):
            self.review_tree.move(iid, "", index)
        self._update_review_headings()
        if save:
            self._save_review_layout()

    def _set_review_column_visible(self, column: str, visible: bool) -> None:
        state = self._review_layout_state()
        hidden = list(state["hidden"])
        if visible:
            hidden = [value for value in hidden if value != column]
        elif column not in hidden:
            if len(self._review_visible_columns()) <= 1:
                messagebox.showinfo("Sloupce", "Alespoň jeden sloupec musí zůstat zobrazený.", parent=self)
                return
            hidden.append(column)
        state["hidden"] = hidden
        self._apply_review_layout()
        self._save_review_layout()

    def _move_review_column(self, column: str, delta: int) -> None:
        state = self._review_layout_state()
        order = list(state["order"])
        if column not in order:
            return
        old = order.index(column)
        new = max(0, min(len(order) - 1, old + delta))
        if old == new:
            return
        order.pop(old)
        order.insert(new, column)
        state["order"] = order
        self._apply_review_layout()
        self._save_review_layout()

    def _review_column_from_x(self, x: int) -> str | None:
        marker = str(self.review_tree.identify_column(x))
        try:
            index = int(marker[1:]) - 1
        except Exception:
            return None
        visible = self._review_visible_columns()
        return visible[index] if 0 <= index < len(visible) else None

    def _show_review_header_menu(self, event: tk.Event[Any]) -> str | None:
        if self.review_tree.identify_region(event.x, event.y) != "heading":
            return None
        column = self._review_column_from_x(event.x)
        if not column:
            return "break"
        menu = tk.Menu(self, tearoff=False, font=("Calibri", 10), background=self.colors["panel"], foreground=self.colors["text"], activebackground=self.colors["accent"], activeforeground="#FFFFFF")
        label = self._review_heading_labels[column]
        menu.add_command(label=f"Seřadit {label} vzestupně", command=lambda: self._sort_review_table(column, False))
        menu.add_command(label=f"Seřadit {label} sestupně", command=lambda: self._sort_review_table(column, True))
        menu.add_separator()
        menu.add_command(label="Přesunout vlevo", command=lambda: self._move_review_column(column, -1))
        menu.add_command(label="Přesunout vpravo", command=lambda: self._move_review_column(column, 1))
        menu.add_command(label="Skrýt tento sloupec", command=lambda: self._set_review_column_visible(column, False))
        columns = tk.Menu(menu, tearoff=False, font=("Calibri", 10), background=self.colors["panel"], foreground=self.colors["text"], activebackground=self.colors["accent"], activeforeground="#FFFFFF")
        variables = []
        hidden = set(self._review_layout_state()["hidden"])
        for col in self._review_layout_state()["order"]:
            variable = tk.BooleanVar(value=col not in hidden)
            variables.append(variable)
            columns.add_checkbutton(label=self._review_heading_labels[col], variable=variable, command=lambda c=col, v=variable: self._set_review_column_visible(c, bool(v.get())))
        columns._turto_vars = variables  # type: ignore[attr-defined]
        menu.add_cascade(label="Zobrazit / skrýt sloupce", menu=columns)
        menu.add_separator()
        menu.add_command(label="Výchozí rozložení", command=self._reset_review_layout)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _reset_review_layout(self) -> None:
        layouts = self.settings.setdefault("table_layouts", {})
        if isinstance(layouts, dict):
            layouts.pop("bulk_review", None)
        self.review_sort_column = None
        self.review_sort_reverse = False
        self._apply_review_layout()
        self._save_review_layout()
        self._refresh_review_tree(preserve_selection=True)

    def _on_review_tree_release(self, event: tk.Event[Any]) -> None:
        if self.review_tree.identify_region(event.x, event.y) == "separator":
            self.after_idle(self._save_review_layout)
'''


def patch_bulk_ui(text: str) -> str:
    text = replace_once(text, "from typing import Any, Iterable\n", "from typing import Any, Callable, Iterable\n", "bulk Callable import")
    sig_old = '''        existing_positions: Iterable[str],\n        start_position: str,\n    ) -> None:\n'''
    sig_new = '''        existing_positions: Iterable[str],\n        start_position: str,\n        settings: dict[str, Any] | None = None,\n        save_settings: Callable[[], None] | None = None,\n    ) -> None:\n'''
    text = replace_once(text, sig_old, sig_new, "bulk settings signature")

    init_old = '''        self.start_position = str(start_position or "P001")\n        self.result: list[dict[str, Any]] | None = None\n'''
    init_new = '''        self.start_position = str(start_position or "P001")\n        self.settings = settings if isinstance(settings, dict) else {}\n        self.save_settings = save_settings\n        self.result: list[dict[str, Any]] | None = None\n'''
    text = replace_once(text, init_old, init_new, "bulk settings init")

    headings_old = '''        headings = {\n            "line": ("Ř.", 44, "center"),\n            "status": ("Stav", 92, "center"),\n            "position": ("Pozice", 76, "center"),\n            "qty": ("Ks", 48, "center"),\n            "input": ("Původní označení", 250, "w"),\n            "resolved": ("Rozpoznaný typ", 310, "w"),\n            "issue": ("Kontrola / co doplnit", 280, "w"),\n        }\n        for column, (label, width, anchor) in headings.items():\n            self.review_tree.heading(column, text=label)\n            self.review_tree.column(column, width=width, minwidth=40, anchor=anchor, stretch=column in {"input", "resolved", "issue"})\n'''
    headings_new = '''        headings = {\n            "line": ("Ř.", 44, "center"),\n            "status": ("Stav", 92, "center"),\n            "position": ("Pozice", 76, "center"),\n            "qty": ("Ks", 48, "center"),\n            "input": ("Původní označení", 250, "w"),\n            "resolved": ("Rozpoznaný typ", 310, "w"),\n            "issue": ("Kontrola / co doplnit", 280, "w"),\n        }\n        self._review_heading_labels = {column: value[0] for column, value in headings.items()}\n        self._review_column_defaults = {column: (value[1], value[2]) for column, value in headings.items()}\n        initial_layout = self._review_layout_state()\n        initial_sort = initial_layout.get("sort", {})\n        self.review_sort_column = str(initial_sort.get("column", "")) or None\n        self.review_sort_reverse = bool(initial_sort.get("reverse", False))\n        for column, (label, width, anchor) in headings.items():\n            saved_width = int(initial_layout.get("widths", {}).get(column, width))\n            self.review_tree.heading(column, text=label, command=lambda col=column: self._sort_review_table(col))\n            self.review_tree.column(column, width=saved_width, minwidth=40, anchor=anchor, stretch=column in {"input", "resolved", "issue"})\n        self._apply_review_layout()\n'''
    text = replace_once(text, headings_old, headings_new, "bulk review persistent columns")

    bind_old = '''        self.review_tree.bind("<<TreeviewSelect>>", self._on_review_selected)\n'''
    bind_new = '''        self.review_tree.bind("<<TreeviewSelect>>", self._on_review_selected)\n        self.review_tree.bind("<Button-3>", self._show_review_header_menu)\n        self.review_tree.bind("<ButtonRelease-1>", self._on_review_tree_release, add="+")\n'''
    text = replace_once(text, bind_old, bind_new, "bulk review header menu binding")

    marker = '''    def _select_all(self, _event: tk.Event[Any]) -> str:\n'''
    text = replace_once(text, marker, bulk_helpers() + "\n" + marker, "bulk layout helpers")

    refresh_marker = '''        valid = [iid for iid in selected if self.review_tree.exists(iid)]\n'''
    refresh_new = '''        if self.review_sort_column:\n            self._sort_review_table(self.review_sort_column, self.review_sort_reverse, save=False)\n\n        valid = [iid for iid in selected if self.review_tree.exists(iid)]\n'''
    text = replace_once(text, refresh_marker, refresh_new, "bulk reapply persistent sort")
    return text


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)
    patch_file(OUT / "project_ui.py", patch_project_ui)
    patch_file(OUT / "bulk_import.py", patch_bulk_ui)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.11\n"
        "- Projektová tabulka: tlačítko Sloupce… a pravý klik na záhlaví umožňují zobrazit/skrýt a přesouvat sloupce.\n"
        "- Řazení vzestupně/sestupně je dostupné z hlavičky i kontextové nabídky a pamatuje se po restartu.\n"
        "- Ukládá se pořadí sloupců, skryté sloupce, šířky a řazení do uživatelského settings.json.\n"
        "- Stejné trvalé rozložení a řazení je dostupné v kontrolní tabulce hromadného importu.\n"
        "- Nastavení je uživatelské, nikoli součást projektu .tinp.\n",
        encoding="utf-8",
    )

    for name in ("app.pyw", "project_ui.py", "bulk_import.py", "bulk_import_engine.py", "catalog_engine.py", "project_model.py", "autocomplete.py", "updater.py"):
        py_compile.compile(str(OUT / name), doraise=True)

    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    project_text = (OUT / "project_ui.py").read_text(encoding="utf-8")
    bulk_text = (OUT / "bulk_import.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.6.11"' in app_text
    assert 'text="Sloupce…"' in project_text
    assert 'def _project_layout_state' in project_text
    assert 'displaycolumns=' in project_text
    assert 'table_layouts' in project_text and '"project"' in project_text
    assert 'def _show_project_header_menu' in project_text
    assert 'settings=self.settings' in project_text
    assert 'def _review_layout_state' in bulk_text
    assert '"bulk_review"' in bulk_text
    assert 'def _sort_review_table' in bulk_text
    assert 'save_settings: Callable[[], None] | None = None' in bulk_text

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "schoeck_archive_sources.json",
        "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.11/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.11",
        "notes": (
            "Trvalé uživatelské rozložení tabulek: sloupce lze zobrazit/skrýt, přesouvat a řadit; program si po restartu pamatuje "
            "pořadí, viditelnost, šířky i řazení hlavní projektové tabulky a kontrolní tabulky hromadného importu."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.6.11 OK; persistent project and bulk-review column layouts enabled")


if __name__ == "__main__":
    main()
