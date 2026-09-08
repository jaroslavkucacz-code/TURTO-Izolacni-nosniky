from __future__ import annotations

"""Unified Treeview controls for TURTO 2.2.4.

Every data table (except the ISO decoder, which already has the same advanced
behaviour in its historical implementation) gets one consistent model:
- left click on heading = toggle ascending / descending sort,
- right click on heading = sort / move / fit / hide / manage columns,
- persistent order, visibility and widths,
- dynamic dialogs are discovered when they are mapped.
"""

from dataclasses import dataclass
import re
import unicodedata
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

SETTING_KEY = "table_layouts_224"
_EXCLUDED_STYLES = {"Suggest.Treeview"}


def _ascii(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def natural_value(value: Any) -> tuple[Any, ...]:
    text = str(value or "").strip()
    if not text or text in {"—", "-"}:
        return (3, "")
    normalized = text.replace("\u00a0", " ").replace("−", "-").replace(",", ".")
    numeric = re.fullmatch(
        r"\s*([+-]?\d+(?:\.\d+)?)\s*(?:%|mm|m|kN|kNm|kN/m|kNm/m|ks)?\s*",
        normalized,
        flags=re.I,
    )
    if numeric:
        try:
            return (0, float(numeric.group(1)))
        except Exception:
            pass
    parts = re.split(r"(\d+(?:[.,]\d+)?)", _ascii(text).casefold())
    key: list[Any] = [1]
    for part in parts:
        if not part:
            continue
        try:
            key.append((0, float(part.replace(",", "."))))
        except ValueError:
            key.append((1, part))
    return tuple(key)


def _safe_title(widget: tk.Misc) -> str:
    try:
        return str(widget.winfo_toplevel().title() or "")
    except Exception:
        return ""


def _slug(value: str) -> str:
    text = _ascii(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:80] or "table"


def _semantic_key(owner: Any, tree: ttk.Treeview) -> str:
    for name, value in vars(owner).items():
        if value is tree and name.endswith(("tree", "_tree")):
            return name
    columns = "_".join(str(c) for c in tree["columns"])
    return f"{_slug(_safe_title(tree))}:{_slug(columns)}"


@dataclass
class _Defaults:
    order: list[str]
    widths: dict[str, int]
    labels: dict[str, str]
    anchors: dict[str, str]
    stretch: dict[str, bool]


class ColumnLayoutDialog(tk.Toplevel):
    def __init__(self, controller: "TableController") -> None:
        owner = controller.owner
        super().__init__(owner)
        self.controller = controller
        self.title(f"Sloupce – {controller.title}")
        self.geometry("780x650")
        self.minsize(620, 520)
        self.transient(owner)
        self.grab_set()
        self.configure(background=owner.colors["bg"])

        try:
            from ui_utils import place_dialog_on_parent
            place_dialog_on_parent(self, owner)
        except Exception:
            pass

        outer = ttk.Frame(self, style="App.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        ttk.Label(
            outer,
            text=f"Rozložení sloupců – {controller.title}",
            style="DialogTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text="Dvojklik přepíná zobrazení. Pořadí, viditelnost a šířky se ukládají pro příští spuštění.",
            style="Muted.TLabel",
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 10))

        box = ttk.Frame(outer, style="Card.TFrame", padding=1)
        box.grid(row=2, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            box,
            columns=("visible", "name", "width"),
            show="headings",
            selectmode="browse",
            style="Project.Treeview",
        )
        for column, label, anchor, width in (
            ("visible", "Zobrazen", "center", 90),
            ("name", "Sloupec", "w", 470),
            ("width", "Šířka", "center", 100),
        ):
            self.tree.heading(column, text=label, anchor=anchor)
            self.tree.column(column, width=width, minwidth=60, anchor=anchor, stretch=column == "name")
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda _event: self.toggle())
        self.tree.bind("<space>", lambda _event: (self.toggle(), "break")[1])

        controls = ttk.Frame(outer, style="App.TFrame")
        controls.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        controls.columnconfigure(9, weight=1)
        ttk.Button(controls, text="↑ Nahoru", command=lambda: self.move(-1)).grid(row=0, column=0)
        ttk.Button(controls, text="↓ Dolů", command=lambda: self.move(1)).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(controls, text="⇤ Na začátek", command=lambda: self.edge("first")).grid(row=0, column=2, padx=(12, 0))
        ttk.Button(controls, text="⇥ Na konec", command=lambda: self.edge("last")).grid(row=0, column=3, padx=(6, 0))
        ttk.Separator(controls, orient="vertical").grid(row=0, column=4, sticky="ns", padx=10)
        ttk.Button(controls, text="Zobrazit / skrýt", command=self.toggle).grid(row=0, column=5)
        ttk.Button(controls, text="Automatická šířka", command=self.fit).grid(row=0, column=6, padx=(6, 0))
        ttk.Button(controls, text="Zobrazit vše", command=self.show_all).grid(row=0, column=7, padx=(12, 0))
        ttk.Button(controls, text="Výchozí", command=self.reset).grid(row=0, column=8, padx=(6, 0))
        ttk.Button(controls, text="Zavřít", style="Accent.TButton", command=self.destroy).grid(row=0, column=10, sticky="e")

        self.bind("<Escape>", lambda _event: self.destroy())
        self.refresh()

    def selected(self) -> str | None:
        selection = self.tree.selection()
        return str(selection[0]) if selection else None

    def refresh(self, select: str | None = None) -> None:
        previous = select or self.selected()
        self.tree.delete(*self.tree.get_children(""))
        state = self.controller.state
        hidden = set(state.get("hidden", []))
        for column in state["order"]:
            width = int(state.get("widths", {}).get(column, self.controller.defaults.widths[column]))
            self.tree.insert("", "end", iid=column, values=("✓" if column not in hidden else "—", self.controller.defaults.labels.get(column, column), f"{width} px"))
        if previous and self.tree.exists(previous):
            self.tree.selection_set(previous)
            self.tree.focus(previous)
            self.tree.see(previous)

    def move(self, delta: int) -> None:
        column = self.selected()
        if column:
            self.controller.move(column, delta)
            self.refresh(column)

    def edge(self, edge: str) -> None:
        column = self.selected()
        if column:
            self.controller.move(column, edge=edge)
            self.refresh(column)

    def toggle(self) -> None:
        column = self.selected()
        if column:
            self.controller.toggle(column)
            self.refresh(column)

    def fit(self) -> None:
        column = self.selected()
        if column:
            self.controller.fit(column)
            self.refresh(column)

    def show_all(self) -> None:
        self.controller.show_all()
        self.refresh()

    def reset(self) -> None:
        if messagebox.askyesno("Výchozí rozložení", f"Obnovit výchozí pořadí, viditelnost, šířky a řazení tabulky „{self.controller.title}“?", parent=self):
            self.controller.reset()
            self.refresh()


class TableController:
    def __init__(self, owner: Any, tree: ttk.Treeview, key: str, title: str) -> None:
        self.owner = owner
        self.tree = tree
        self.key = key
        self.title = title
        columns = [str(c) for c in tree["columns"]]
        self.defaults = _Defaults(
            order=columns,
            widths={c: int(tree.column(c, "width")) for c in columns},
            labels={c: str(tree.heading(c, "text") or c) for c in columns},
            anchors={c: str(tree.column(c, "anchor") or "center") for c in columns},
            stretch={c: bool(tree.column(c, "stretch")) for c in columns},
        )
        self.state = self._load_state()
        self.apply_layout()
        self._install_headings()
        tree.bind("<Button-3>", self._header_menu, add="+")
        tree.bind("<ButtonRelease-1>", self._capture_widths, add="+")

    def _settings_root(self) -> dict[str, Any]:
        settings = getattr(self.owner, "settings", None)
        if not isinstance(settings, dict):
            settings = {}
            try: self.owner.settings = settings
            except Exception: pass
        root = settings.setdefault(SETTING_KEY, {})
        if not isinstance(root, dict):
            root = {}
            settings[SETTING_KEY] = root
        return root

    def _load_state(self) -> dict[str, Any]:
        raw = self._settings_root().get(self.key, {})
        raw = raw if isinstance(raw, dict) else {}
        valid = set(self.defaults.order)
        order = [str(c) for c in raw.get("order", []) if str(c) in valid]
        order.extend(c for c in self.defaults.order if c not in order)
        hidden = [str(c) for c in raw.get("hidden", []) if str(c) in valid]
        widths = {}
        for c in self.defaults.order:
            try: widths[c] = max(42, min(900, int(raw.get("widths", {}).get(c, self.defaults.widths[c]))))
            except Exception: widths[c] = self.defaults.widths[c]
        sort_column = str(raw.get("sort_column", ""))
        if sort_column not in valid: sort_column = ""
        return {"order": order, "hidden": hidden, "widths": widths, "sort_column": sort_column, "sort_reverse": bool(raw.get("sort_reverse", False))}

    def save(self) -> None:
        self._settings_root()[self.key] = {"order": list(self.state["order"]), "hidden": list(self.state["hidden"]), "widths": dict(self.state["widths"]), "sort_column": str(self.state.get("sort_column", "")), "sort_reverse": bool(self.state.get("sort_reverse", False))}
        save = getattr(self.owner, "_save_settings", None)
        if callable(save):
            try: save()
            except Exception: pass

    def visible_order(self) -> list[str]:
        hidden = set(self.state.get("hidden", []))
        visible = [c for c in self.state["order"] if c not in hidden]
        if not visible and self.state["order"]:
            visible = [self.state["order"][0]]
            self.state["hidden"] = [c for c in self.state["hidden"] if c != visible[0]]
        return visible

    def apply_layout(self) -> None:
        if not self.tree.winfo_exists(): return
        valid = set(str(c) for c in self.tree["columns"])
        self.state["order"] = [c for c in self.state["order"] if c in valid]
        self.state["order"].extend(c for c in self.defaults.order if c in valid and c not in self.state["order"])
        self.state["hidden"] = [c for c in self.state["hidden"] if c in valid]
        self.tree.configure(displaycolumns=tuple(self.visible_order()))
        for c in self.state["order"]:
            try: self.tree.column(c, width=int(self.state["widths"].get(c, self.defaults.widths[c])))
            except Exception: pass
        self._update_heading_labels()

    def _install_headings(self) -> None:
        for column in self.defaults.order:
            try: self.tree.heading(column, command=lambda c=column: self.sort(c))
            except Exception: pass
        self._update_heading_labels()

    def _update_heading_labels(self) -> None:
        sorted_column = str(self.state.get("sort_column", "")); reverse = bool(self.state.get("sort_reverse", False))
        for column, label in self.defaults.labels.items():
            suffix = " ▼" if column == sorted_column and reverse else (" ▲" if column == sorted_column else "")
            try: self.tree.heading(column, text=label + suffix, anchor=self.defaults.anchors[column])
            except Exception: pass

    def _display_column_from_x(self, x: int) -> str | None:
        try:
            token = self.tree.identify_column(x); index = int(str(token).lstrip("#")) - 1; visible = self.visible_order()
            return visible[index] if 0 <= index < len(visible) else None
        except Exception: return None

    def sort(self, column: str, reverse: bool | None = None, *, save: bool = True) -> None:
        if column not in self.defaults.order or not self.tree.winfo_exists(): return
        if reverse is None:
            reverse = (not bool(self.state.get("sort_reverse", False))) if self.state.get("sort_column") == column else False
        self.state["sort_column"] = column; self.state["sort_reverse"] = bool(reverse)
        items = list(self.tree.get_children("")); keyed = [(natural_value(self.tree.set(iid, column)), pos, iid) for pos, iid in enumerate(items)]
        keyed.sort(key=lambda item: (item[0], item[1]), reverse=bool(reverse))
        for pos, (_key, _old, iid) in enumerate(keyed):
            try: self.tree.move(iid, "", pos)
            except Exception: pass
        self._update_heading_labels()
        if save: self.save()

    def reapply(self) -> None:
        if not self.tree.winfo_exists(): return
        self.apply_layout(); column = str(self.state.get("sort_column", ""))
        if column: self.sort(column, bool(self.state.get("sort_reverse", False)), save=False)

    def move(self, column: str, delta: int = 0, *, edge: str | None = None) -> None:
        order = list(self.state["order"])
        if column not in order: return
        old = order.index(column); order.pop(old)
        new = 0 if edge == "first" else (len(order) if edge == "last" else max(0, min(len(order), old + int(delta))))
        order.insert(new, column); self.state["order"] = order; self.apply_layout(); self.save()

    def set_visible(self, column: str, visible: bool) -> None:
        hidden = set(self.state.get("hidden", []))
        if visible: hidden.discard(column)
        else:
            if len(self.visible_order()) <= 1 and column in self.visible_order(): return
            hidden.add(column)
        self.state["hidden"] = [c for c in self.state["order"] if c in hidden]; self.apply_layout(); self.save()

    def toggle(self, column: str) -> None: self.set_visible(column, column in set(self.state.get("hidden", [])))
    def show_all(self) -> None: self.state["hidden"] = []; self.apply_layout(); self.save()

    def fit(self, column: str) -> None:
        label = self.defaults.labels.get(column, column); longest = len(label)
        for count, iid in enumerate(self.tree.get_children("")):
            if count >= 400: break
            try: longest = max(longest, min(90, len(str(self.tree.set(iid, column)))))
            except Exception: pass
        width = max(54, min(720, 24 + longest * 8)); self.state["widths"][column] = width
        try: self.tree.column(column, width=width)
        except Exception: pass
        self.save()

    def _capture_widths(self, event: tk.Event[Any]) -> None:
        try:
            if self.tree.identify_region(event.x, event.y) not in {"heading", "separator"}: return
        except Exception: return
        changed = False
        for column in self.defaults.order:
            try: width = int(self.tree.column(column, "width"))
            except Exception: continue
            if width != int(self.state["widths"].get(column, width)):
                self.state["widths"][column] = width; changed = True
        if changed: self.save()

    def open_manager(self) -> None: ColumnLayoutDialog(self)

    def _header_menu(self, event: tk.Event[Any]) -> str | None:
        try:
            if self.tree.identify_region(event.x, event.y) != "heading": return None
        except Exception: return None
        column = self._display_column_from_x(event.x)
        if not column: return "break"
        label = self.defaults.labels.get(column, column)
        menu = tk.Menu(self.owner, tearoff=False, font=("Calibri", 10), background=self.owner.colors["panel"], foreground=self.owner.colors["text"], activebackground=self.owner.colors["accent"], activeforeground="#FFFFFF")
        menu.add_command(label=f"↑ Seřadit „{label}“ vzestupně", command=lambda: self.sort(column, False)); menu.add_command(label=f"↓ Seřadit „{label}“ sestupně", command=lambda: self.sort(column, True)); menu.add_separator()
        menu.add_command(label="← Posunout o sloupec vlevo", command=lambda: self.move(column, -1)); menu.add_command(label="→ Posunout o sloupec vpravo", command=lambda: self.move(column, 1)); menu.add_command(label="Automatická šířka", command=lambda: self.fit(column)); menu.add_separator()
        menu.add_command(label="Skrýt tento sloupec", command=lambda: self.set_visible(column, False)); menu.add_command(label="Nastavit všechny sloupce…", command=self.open_manager)
        try: menu.tk_popup(event.x_root, event.y_root)
        finally:
            try: menu.grab_release()
            except Exception: pass
        return "break"

    def reset(self) -> None:
        self.state = {"order": list(self.defaults.order), "hidden": [], "widths": dict(self.defaults.widths), "sort_column": "", "sort_reverse": False}; self.apply_layout(); self.save()


def controller_for(owner: Any, tree: ttk.Treeview | None) -> TableController | None:
    if tree is None: return None
    registry = getattr(owner, "_turto_table_controllers", {})
    return registry.get(str(tree)) if isinstance(registry, dict) else None


def open_columns(owner: Any, tree: ttk.Treeview | None) -> None:
    controller = controller_for(owner, tree)
    if controller is not None: controller.open_manager()


def _walk_widgets(root: tk.Misc):
    stack = list(root.winfo_children())
    while stack:
        widget = stack.pop(); yield widget
        try: stack.extend(widget.winfo_children())
        except Exception: pass


def _eligible(owner: Any, tree: ttk.Treeview) -> bool:
    if tree is getattr(owner, "project_tree", None): return False
    try:
        if str(tree.cget("style")) in _EXCLUDED_STYLES: return False
    except Exception: pass
    try:
        if _safe_title(tree).startswith("Sloupce –"): return False
    except Exception: pass
    try: return bool(tree["columns"])
    except Exception: return False


def scan(owner: Any) -> None:
    registry = getattr(owner, "_turto_table_controllers", None)
    if not isinstance(registry, dict): registry = {}; owner._turto_table_controllers = registry
    for widget in _walk_widgets(owner):
        if not isinstance(widget, ttk.Treeview) or not _eligible(owner, widget): continue
        token = str(widget)
        if token in registry: continue
        key = _semantic_key(owner, widget); title = _safe_title(widget) or key
        registry[token] = TableController(owner, widget, key, title)


def reapply(owner: Any) -> None:
    scan(owner); registry = getattr(owner, "_turto_table_controllers", {})
    for token, controller in list(registry.items()):
        try:
            if not controller.tree.winfo_exists(): registry.pop(token, None); continue
            controller.reapply()
        except Exception: pass


def _wrap_refresh(owner: Any, name: str) -> None:
    original = getattr(owner, name, None)
    if not callable(original): return
    marker = f"_turto_table_refresh_wrapped_{name}"
    if getattr(owner, marker, False): return
    def wrapped(*args: Any, **kwargs: Any):
        result = original(*args, **kwargs)
        try: owner.after_idle(lambda: reapply(owner))
        except Exception: pass
        return result
    try: setattr(owner, name, wrapped); setattr(owner, marker, True)
    except Exception: pass


def install(owner: Any) -> None:
    if getattr(owner, "_turto_universal_tables_224_installed", False): reapply(owner); return
    owner._turto_universal_tables_224_installed = True; owner._turto_table_controllers = {}; scan(owner)
    for name in ("refresh_shear_tables", "refresh_substitution_tree", "refresh_project_tree"): _wrap_refresh(owner, name)
    def mapped(_event: Any = None) -> None:
        try: owner.after_idle(lambda: scan(owner))
        except Exception: pass
    owner.bind_all("<Map>", mapped, add="+")


def selftest() -> None:
    values = ["10", "2", "1,5", "—"]; ordered = sorted(values, key=natural_value)
    assert ordered[:3] == ["1,5", "2", "10"] and ordered[-1] == "—"


if __name__ == "__main__": selftest()
