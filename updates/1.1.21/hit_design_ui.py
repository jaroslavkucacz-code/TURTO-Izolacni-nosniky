from __future__ import annotations

"""UI and serialization for the local database of direct HIT proposals."""

from datetime import datetime
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from hit_design_store import HitDesignStore
from hit_row_extension import quantity_int


def design_store(owner: Any) -> HitDesignStore:
    path = Path(owner.settings_path).resolve().parent / "hit_designs.sqlite3"
    return HitDesignStore(path)


def current_action_name(owner: Any) -> str:
    loaded = str(getattr(owner, "hit_design_action", "") or "").strip()
    if loaded:
        return loaded
    project = getattr(owner, "project", None)
    return str(getattr(project, "name", "") or "").strip() or "Bez názvu akce"


def serialize_hit_design(owner: Any) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in owner.hit_rows:
        candidate = row.selected_candidate
        rows.append({
            "name": row.name.get().strip(),
            "quantity": quantity_int(row),
            "series": row.series.get().strip(),
            "connection_type": row.connection_type.get().strip(),
            "mvx_variant": row.mvx_variant.get().strip(),
            "mvx_bx": row.mvx_bx.get().strip(),
            "height": row.height.get().strip(),
            "required_length": row.required_length.get().strip(),
            "cover": row.cover.get().strip(),
            "concrete": row.concrete.get().strip(),
            "med_pos": row.med_pos.get().strip(),
            "med_neg": row.med_neg.get().strip(),
            "ned_pos": row.ned_pos.get().strip(),
            "ned_neg": row.ned_neg.get().strip(),
            "ved_pos": row.ved_pos.get().strip(),
            "ved_neg": row.ved_neg.get().strip(),
            "hed_parallel": row.hed_parallel.get().strip(),
            "hed_perp": row.hed_perp.get().strip(),
            "load_x": row.load_x.get().strip(),
            "import_source_text": str(getattr(row, "import_source_text", "") or ""),
            "import_source_line": str(getattr(row, "import_source_line", "") or ""),
            "selected_designation": candidate.designation if candidate is not None else "",
            "manual_product": bool(getattr(row, "_manual_product", False)),
        })
    return {
        "schema_version": 1,
        "module_version": "1.1.21",
        "lengths": sorted(owner.allowed_hit_lengths(), reverse=True),
        "rows": rows,
    }


def _ask_design_metadata(owner: Any, *, action_default: str, name_default: str) -> tuple[str, str] | None:
    action = simpledialog.askstring(
        "Uložit návrh HIT", "AKCE:", initialvalue=action_default, parent=owner,
    )
    if action is None:
        return None
    action = action.strip()
    if not action:
        messagebox.showerror("Uložit návrh HIT", "AKCE nesmí být prázdná.", parent=owner)
        return None
    name = simpledialog.askstring(
        "Uložit návrh HIT", "Název návrhu:", initialvalue=name_default or "Návrh HIT", parent=owner,
    )
    if name is None:
        return None
    name = name.strip()
    if not name:
        messagebox.showerror("Uložit návrh HIT", "Název návrhu nesmí být prázdný.", parent=owner)
        return None
    return action, name


def save_hit_design(owner: Any, *, as_new: bool = False) -> str | None:
    try:
        payload = serialize_hit_design(owner)
    except ValueError as exc:
        messagebox.showerror("Uložit návrh HIT", str(exc), parent=owner)
        return None
    design_id = None if as_new else getattr(owner, "hit_design_id", None)
    action = str(getattr(owner, "hit_design_action", "") or "").strip()
    name = str(getattr(owner, "hit_design_name", "") or "").strip()
    if not design_id or as_new:
        metadata = _ask_design_metadata(
            owner,
            action_default=action or current_action_name(owner),
            name_default=(name + " – kopie") if as_new and name else (name or "Návrh HIT"),
        )
        if metadata is None:
            return None
        action, name = metadata
    try:
        key = design_store(owner).save(
            action_name=action, design_name=name, payload=payload, design_id=design_id,
        )
    except Exception as exc:
        messagebox.showerror("Uložit návrh HIT", str(exc), parent=owner)
        return None
    owner.hit_design_id = key
    owner.hit_design_action = action
    owner.hit_design_name = name
    owner.hit_status_var.set(f"Uloženo: {action} • {name} • {len(payload['rows'])} řádků")
    return key


def _load_design_record(owner: Any, base: Any, record: dict[str, Any]) -> None:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    raw_rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(raw_rows, list):
        raise ValueError("Uložený návrh nemá platné řádky.")
    if len(raw_rows) > 2000:
        raise ValueError("Uložený návrh obsahuje příliš mnoho řádků.")

    for row in list(owner.hit_rows):
        row.destroy()
    owner.hit_rows.clear()

    lengths = {int(value) for value in payload.get("lengths", []) if str(value).isdigit()}
    if not lengths:
        lengths = {100, 50}
    owner.hit_l100_var.set(100 in lengths)
    owner.hit_l050_var.set(50 in lengths)
    owner.hit_l033_var.set(33 in lengths)
    owner.hit_l025_var.set(25 in lengths)
    owner._save_hit_options()

    for index, raw in enumerate(raw_rows, 1):
        if not isinstance(raw, dict):
            continue
        defaults = dict(raw)
        defaults.setdefault("name", f"N{index:03d}")
        defaults.setdefault("quantity", 1)
        row = base.HitInputRow(owner, index, defaults)
        owner.hit_rows.append(row)
    if not owner.hit_rows:
        owner.add_hit_row()

    owner.hit_design_id = str(record.get("id") or "") or None
    owner.hit_design_action = str(record.get("action_name") or "")
    owner.hit_design_name = str(record.get("design_name") or "")
    if hasattr(owner, "_hit_reconfigure_row_minsizes"):
        owner._hit_reconfigure_row_minsizes()
    owner.recalculate_hit_all()
    try:
        owner.hit_canvas.yview_moveto(0.0)
    except Exception:
        pass
    if hasattr(owner, "_hit_schedule_virtual_refresh"):
        owner._hit_schedule_virtual_refresh()
    owner.hit_status_var.set(
        f"Načteno: {owner.hit_design_action} • {owner.hit_design_name} • {len(owner.hit_rows)} řádků"
    )


def load_hit_design(owner: Any, base: Any, design_id: str) -> None:
    if owner.hit_rows and not messagebox.askyesno(
        "Načíst uložený návrh",
        "Načtením se nahradí aktuální řádky Návrhu HIT. Pokračovat?",
        parent=owner,
    ):
        return
    try:
        record = design_store(owner).load(design_id)
        _load_design_record(owner, base, record)
    except Exception as exc:
        messagebox.showerror("Načíst návrh HIT", str(exc), parent=owner)


def _format_modified(value: str) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(value)


class HitDesignBrowser(tk.Toplevel):
    def __init__(self, owner: Any, base: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.base = base
        self.store = design_store(owner)
        self.title("Databáze návrhů HIT")
        self.geometry("980x620")
        self.minsize(760, 450)
        self.configure(background=owner.colors["bg"])
        self.transient(owner)
        self.grab_set()

        outer = ttk.Frame(self, style="App.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        ttk.Label(outer, text="Uložené návrhy HIT", style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        searchbar = ttk.Frame(outer, style="App.TFrame")
        searchbar.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        ttk.Label(searchbar, text="Hledat AKCI / název:").pack(side="left")
        self.search = tk.StringVar()
        entry = ttk.Entry(searchbar, textvariable=self.search, width=38)
        entry.pack(side="left", padx=(7, 0))
        self.search.trace_add("write", lambda *_: self.refresh())

        box = ttk.Frame(outer, style="Card.TFrame")
        box.grid(row=2, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        columns = ("action", "name", "modified", "rows")
        self.tree = ttk.Treeview(box, columns=columns, show="headings", selectmode="browse", style="Data.Treeview")
        specs = {
            "action": ("AKCE", 290, "w"),
            "name": ("Název návrhu", 280, "w"),
            "modified": ("Poslední úprava", 160, "center"),
            "rows": ("Řádků", 80, "center"),
        }
        for col, (label, width, anchor) in specs.items():
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, minwidth=60, anchor=anchor, stretch=col in {"action", "name"})
        ybar = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ybar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda _e: self.load_selected())
        self.tree.bind("<Return>", lambda _e: self.load_selected())

        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bottom, text="Uložit aktuální jako nový…", command=self.save_new).pack(side="left")
        ttk.Button(bottom, text="Smazat", command=self.delete_selected).pack(side="left", padx=(7, 0))
        ttk.Button(bottom, text="Zavřít", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Načíst", style="Accent.TButton", command=self.load_selected).pack(side="right", padx=(0, 7))
        self.refresh()
        try:
            from ui_utils import place_dialog_on_parent
            place_dialog_on_parent(self, owner)
        except Exception:
            pass
        entry.focus_set()

    def refresh(self) -> None:
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        try:
            records = self.store.list(self.search.get())
        except Exception as exc:
            messagebox.showerror("Databáze návrhů HIT", str(exc), parent=self)
            return
        for record in records:
            key = str(record["id"])
            self.tree.insert(
                "", "end", iid=key,
                values=(record["action_name"], record["design_name"], _format_modified(record["updated_at"]), record["row_count"]),
            )
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])

    def _selected_id(self) -> str | None:
        selected = self.tree.selection()
        return selected[0] if selected else None

    def load_selected(self) -> None:
        key = self._selected_id()
        if not key:
            return
        load_hit_design(self.owner, self.base, key)
        self.destroy()

    def save_new(self) -> None:
        if save_hit_design(self.owner, as_new=True):
            self.refresh()

    def delete_selected(self) -> None:
        key = self._selected_id()
        if not key:
            return
        values = self.tree.item(key, "values")
        label = " • ".join(str(v) for v in values[:2])
        if not messagebox.askyesno("Smazat návrh", f"Opravdu smazat uložený návrh?\n\n{label}", parent=self):
            return
        try:
            self.store.delete(key)
        except Exception as exc:
            messagebox.showerror("Smazat návrh", str(exc), parent=self)
            return
        if str(getattr(self.owner, "hit_design_id", "")) == key:
            self.owner.hit_design_id = None
            self.owner.hit_design_action = ""
            self.owner.hit_design_name = ""
        self.refresh()


def install(base: Any) -> None:
    original_init = base.HitWorkspaceMixin._init_hit_workspace

    def init_workspace(self) -> None:
        original_init(self)
        self.hit_design_id: str | None = None
        self.hit_design_action = ""
        self.hit_design_name = ""

    def save(self, as_new: bool = False) -> str | None:
        return save_hit_design(self, as_new=as_new)

    def load(self, design_id: str) -> None:
        load_hit_design(self, base, design_id)

    def browser(self) -> None:
        HitDesignBrowser(self, base)

    base.HitWorkspaceMixin._init_hit_workspace = init_workspace
    base.HitWorkspaceMixin._hit_design_store = design_store
    base.HitWorkspaceMixin._current_action_name = current_action_name
    base.HitWorkspaceMixin._serialize_hit_design = serialize_hit_design
    base.HitWorkspaceMixin.save_hit_design = save
    base.HitWorkspaceMixin.load_hit_design = load
    base.HitWorkspaceMixin.open_hit_design_browser = browser
