from __future__ import annotations

"""Central AKCE browser and global toolbar."""

from datetime import datetime
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from project_model import ProjectDocument, PROJECT_FILE_EXTENSION
from action_payload import action_store, confirm_action_close, load_action_record


def _fmt_date(value: str) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(value or "")


class ActionBrowser(tk.Toplevel):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.store = action_store(owner)
        self.title("Centrální databáze AKCÍ")
        self.geometry("1050x650")
        self.minsize(800, 480)
        self.transient(owner)
        self.grab_set()
        self.configure(background=owner.colors["bg"])
        outer = ttk.Frame(self, style="App.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        ttk.Label(outer, text="Uložené AKCE TURTO ISO", style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        searchbar = ttk.Frame(outer, style="App.TFrame")
        searchbar.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        ttk.Label(searchbar, text="Hledat AKCI:").pack(side="left")
        self.search = tk.StringVar()
        entry = ttk.Entry(searchbar, textvariable=self.search, width=42)
        entry.pack(side="left", padx=(7, 0))
        self.search.trace_add("write", lambda *_: self.refresh())
        frame = ttk.Frame(outer, style="Card.TFrame")
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1); frame.rowconfigure(0, weight=1)
        columns = ("name", "updated", "decoder", "hit")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", style="Data.Treeview")
        for col, spec in {
            "name": ("AKCE", 470, "w"), "updated": ("Poslední úprava", 180, "center"),
            "decoder": ("Dekodér ISO", 110, "center"), "hit": ("Návrh HIT", 110, "center"),
        }.items():
            label, width, anchor = spec
            self.tree.heading(col, text=label); self.tree.column(col, width=width, minwidth=70, anchor=anchor, stretch=col == "name")
        bar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); bar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda _e: self.load_selected())
        self.tree.bind("<Return>", lambda _e: self.load_selected())
        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bottom, text="Importovat starý .tinp…", command=self.import_legacy).pack(side="left")
        ttk.Button(bottom, text="Smazat AKCI", command=self.delete_selected).pack(side="left", padx=(7, 0))
        ttk.Button(bottom, text="Zavřít", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Otevřít AKCI", style="Accent.TButton", command=self.load_selected).pack(side="right", padx=(0, 7))
        self.refresh()
        try:
            from ui_utils import place_dialog_on_parent
            place_dialog_on_parent(self, owner)
        except Exception:
            pass
        entry.focus_set()

    def refresh(self) -> None:
        previous = self.tree.selection()
        self.tree.delete(*self.tree.get_children(""))
        try:
            records = self.store.list(self.search.get())
        except Exception as exc:
            messagebox.showerror("Databáze AKCÍ", str(exc), parent=self); return
        for record in records:
            key = str(record["id"])
            self.tree.insert("", "end", iid=key, values=(
                record["action_name"], _fmt_date(record["updated_at"]),
                record["decoder_count"], record["hit_count"],
            ))
        if previous and self.tree.exists(previous[0]): self.tree.selection_set(previous[0])

    def selected_id(self) -> str | None:
        selected = self.tree.selection()
        return str(selected[0]) if selected else None

    def load_selected(self) -> None:
        key = self.selected_id()
        if not key or not confirm_action_close(self.owner): return
        try:
            load_action_record(self.owner, self.store.load(key))
        except Exception as exc:
            messagebox.showerror("AKCI se nepodařilo otevřít", str(exc), parent=self); return
        self.destroy()

    def delete_selected(self) -> None:
        key = self.selected_id()
        if not key: return
        name = str(self.tree.set(key, "name") or "AKCE")
        if not messagebox.askyesno("Smazat AKCI", f"Opravdu trvale smazat AKCI „{name}“ z centrální databáze?", parent=self): return
        try: self.store.delete(key)
        except Exception as exc:
            messagebox.showerror("Smazat AKCI", str(exc), parent=self); return
        if str(getattr(self.owner, "action_id", "")) == key:
            self.owner.action_id = None; self.owner.project_dirty = True; self.owner._update_action_info()
        self.refresh()

    def import_legacy(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Importovat starý projekt TURTO ISO",
            filetypes=[("Starý projekt TURTO ISO", f"*{PROJECT_FILE_EXTENSION}"), ("Všechny soubory", "*.*")],
        )
        if not path: return
        try:
            doc = ProjectDocument.load(path); doc.path = None
            payload = {
                "schema_version": 1, "application": "TURTO ISO", "action_name": doc.name,
                "project": doc.to_dict(),
                "hit_design": {"schema_version": 1, "module_version": "legacy", "lengths": [100, 50], "rows": []},
            }
            saved = self.store.save(action_name=doc.name, payload=payload)
        except Exception as exc:
            messagebox.showerror("Import se nepodařil", str(exc), parent=self); return
        self.refresh()
        if self.tree.exists(saved["id"]):
            self.tree.selection_set(saved["id"]); self.tree.focus(saved["id"])
        messagebox.showinfo("Import dokončen", f"Starý projekt byl uložen do centrální databáze jako AKCE „{doc.name}“.", parent=self)


def build_action_bar(owner: Any, parent: ttk.Frame) -> ttk.Frame:
    bar = ttk.Frame(parent, style="Card.TFrame", padding=(14, 9)); bar.columnconfigure(1, weight=1)
    ttk.Label(bar, text="AKCE", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
    entry = ttk.Entry(bar, textvariable=owner.project_name_var); entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))
    owner.action_name_entry = entry
    ttk.Button(bar, text="Nová akce", command=owner.new_action).grid(row=0, column=2)
    ttk.Button(bar, text="Otevřít akci…", command=owner.open_action_browser).grid(row=0, column=3, padx=(7, 0))
    ttk.Button(bar, text="Uložit", style="Accent.TButton", command=owner.save_action).grid(row=0, column=4, padx=(7, 0))
    ttk.Button(bar, text="Uložit jako…", command=owner.save_action_as_new).grid(row=0, column=5, padx=(7, 0))
    owner.action_info_var = tk.StringVar(value="Nová AKCE • dosud neuloženo")
    ttk.Label(bar, textvariable=owner.action_info_var, style="MutedCard.TLabel").grid(row=1, column=0, columnspan=6, sticky="w", pady=(5, 0))
    return bar
