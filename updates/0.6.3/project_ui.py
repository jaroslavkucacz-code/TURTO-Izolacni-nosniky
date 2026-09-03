from __future__ import annotations

import copy
import csv
import re
from pathlib import Path
from typing import Any, Iterable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from catalog_engine import QueryResult, concrete_label, natural_key
from autocomplete import DesignationAutocomplete
from project_model import (
    PROJECT_FILE_EXTENSION,
    ProjectDocument,
    create_project_row,
    query_from_selection,
    row_status,
    safe_quantity,
)


class RowMetaDialog(tk.Toplevel):
    """Malý modální dialog pro údaje řádku, které nejsou součástí katalogového typu."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        position: str,
        quantity: int,
        note: str,
        designation: str,
        colors: dict[str, str],
    ) -> None:
        super().__init__(parent)
        self.result: dict[str, Any] | None = None
        self.colors = colors
        self.title(title)
        self.geometry("620x330")
        self.minsize(520, 300)
        self.transient(parent)
        self.grab_set()
        self.configure(background=colors["bg"])
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.position_var = tk.StringVar(value=position)
        self.quantity_var = tk.StringVar(value=str(quantity))
        self.note_var = tk.StringVar(value=note)

        outer = ttk.Frame(self, style="App.TFrame", padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        ttk.Label(outer, text=title, style="DialogTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )
        ttk.Label(
            outer,
            text=designation,
            style="Muted.TLabel",
            wraplength=560,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        ttk.Label(outer, text="Pozice / označení v projektu").grid(row=2, column=0, sticky="w", padx=(0, 14), pady=5)
        position_entry = ttk.Entry(outer, textvariable=self.position_var)
        position_entry.grid(row=2, column=1, sticky="ew", pady=5)

        ttk.Label(outer, text="Počet kusů").grid(row=3, column=0, sticky="w", padx=(0, 14), pady=5)
        quantity_entry = ttk.Entry(outer, textvariable=self.quantity_var, width=12)
        quantity_entry.grid(row=3, column=1, sticky="w", pady=5)

        ttk.Label(outer, text="Poznámka").grid(row=4, column=0, sticky="nw", padx=(0, 14), pady=5)
        note_entry = ttk.Entry(outer, textvariable=self.note_var)
        note_entry.grid(row=4, column=1, sticky="ew", pady=5)

        buttons = ttk.Frame(outer, style="App.TFrame")
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(22, 0))
        ttk.Button(buttons, text="Zrušit", command=self._cancel).pack(side="right")
        ttk.Button(buttons, text="Uložit řádek", style="Accent.TButton", command=self._submit).pack(
            side="right", padx=(0, 8)
        )

        self.bind("<Escape>", lambda _event: self._cancel())
        self.bind("<Return>", lambda _event: self._submit())
        position_entry.focus_set()
        position_entry.selection_range(0, "end")

    def _submit(self) -> None:
        position = self.position_var.get().strip()
        if not position:
            messagebox.showwarning("Chybí pozice", "Doplňte pozici řádku.", parent=self)
            return
        try:
            quantity = safe_quantity(self.quantity_var.get())
        except ValueError as exc:
            messagebox.showwarning("Neplatný počet kusů", str(exc), parent=self)
            return
        self.result = {
            "position": position,
            "quantity": quantity,
            "note": self.note_var.get().strip(),
        }
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class BulkPasteDialog(tk.Toplevel):
    """Dialog pro vložení desítek řádků z Excelu nebo prostého textu."""

    def __init__(self, parent: tk.Misc, colors: dict[str, str]) -> None:
        super().__init__(parent)
        self.result: str | None = None
        self.colors = colors
        self.title("Hromadné vložení nosníků")
        self.geometry("930x630")
        self.minsize(720, 480)
        self.transient(parent)
        self.grab_set()
        self.configure(background=colors["bg"])
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        outer = ttk.Frame(self, style="App.TFrame", padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, text="Hromadné vložení řádků", style="DialogTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text=(
                "Každý nosník vložte na samostatný řádek. Lze vložit pouze úplné označení, nebo tabulku "
                "zkopírovanou z Excelu. Platné formáty jsou uvedeny níže."
            ),
            style="Muted.TLabel",
            wraplength=860,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 10))

        examples = (
            "1)  XT typ KL-M8-V2-CV1-H220-6.2\n"
            "2)  P001    [TAB]    XT typ KL-M8-V2-CV1-H220-6.2\n"
            "3)  P001    [TAB]    4    [TAB]    XT typ KL-M8-V2-CV1-H220-6.2    [TAB]    poznámka"
        )
        ttk.Label(outer, text=examples, style="CardAlt.TLabel", padding=10, justify="left").grid(
            row=2, column=0, sticky="ew", pady=(0, 10)
        )

        text_frame = ttk.Frame(outer, style="Card.TFrame", padding=1)
        text_frame.grid(row=3, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.text = tk.Text(
            text_frame,
            wrap="none",
            undo=True,
            font=("Calibri", 10),
            background=colors["panel"],
            foreground=colors["text"],
            insertbackground=colors["text"],
            selectbackground=colors["accent"],
            selectforeground="#FFFFFF",
            relief="flat",
            padx=10,
            pady=10,
        )
        yscroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        xscroll = ttk.Scrollbar(text_frame, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        buttons = ttk.Frame(outer, style="App.TFrame")
        buttons.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        buttons.columnconfigure(0, weight=1)
        ttk.Label(
            buttons,
            text="Chybné řádky se vypíší samostatně; správné řádky se přesto načtou.",
            style="Muted.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(buttons, text="Zrušit", command=self._cancel).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(buttons, text="Načíst řádky", style="Accent.TButton", command=self._submit).grid(
            row=0, column=2, padx=(8, 0)
        )

        self.bind("<Escape>", lambda _event: self._cancel())
        self.text.bind("<Control-a>", self._select_all)
        self.text.focus_set()

    def _select_all(self, _event: tk.Event[Any]) -> str:
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _submit(self) -> None:
        value = self.text.get("1.0", "end-1c")
        if not value.strip():
            messagebox.showwarning("Prázdné vložení", "Vložte alespoň jeden řádek.", parent=self)
            return
        self.result = value
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class ProjectWorkspaceMixin:
    """Projektová tabulka pro práci s desítkami až stovkami prvků.

    Mixin očekává, že hostitelská aplikace poskytuje atributy ``database``,
    ``colors``, ``style``, ``settings``, ``current_result`` a stávající kaskádové
    metody detailního výběru.
    """

    PROJECT_COLUMNS: tuple[tuple[str, str, int, str, bool], ...] = (
        ("order", "Poř.", 52, "center", False),
        ("position", "Pozice", 86, "w", False),
        ("quantity", "Ks", 54, "center", False),
        ("manufacturer", "Výrobce", 100, "w", False),
        ("model", "Řada", 90, "center", False),
        ("type_name", "Typ", 72, "center", False),
        ("generation", "Gen.", 58, "center", False),
        ("moment_class", "Třída 1", 78, "center", False),
        ("shear_class", "Třída 2", 88, "center", False),
        ("concrete", "Beton", 88, "center", False),
        ("cover", "Varianta", 120, "center", False),
        ("height", "Rozměr", 88, "center", False),
        ("insulation", "Izolant", 76, "center", False),
        ("compression", "Tlakový přenos", 170, "w", False),
        ("moment", "Moment", 128, "center", False),
        ("shear", "Smyk / síla", 150, "center", False),
        ("extra", "Další statika", 210, "w", False),
        ("designation", "Úplné označení", 360, "w", True),
        ("catalog", "Katalog", 178, "w", False),
        ("pages", "Str.", 58, "center", False),
        ("mapping", "Převod", 105, "center", False),
        ("note", "Poznámka", 240, "w", True),
        ("status", "Stav dat", 116, "center", False),
    )

    def _init_project_workspace(self) -> None:
        self.project = ProjectDocument()
        self.project_dirty = False
        self.project_edit_row_id: str | None = None
        self.project_sort_column: str | None = None
        self.project_sort_reverse = False
        self.project_result_cache: dict[str, QueryResult | None] = {}
        self._project_var_guard = False
        self._project_filter_trace: str | None = None
        self._project_name_trace: str | None = None
        self.base_window_title = getattr(self, "base_window_title", "TURTO – Databáze izolačních nosníků")

    def _configure_project_styles(self) -> None:
        c = self.colors
        self.style.configure("Workspace.TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        self.style.configure(
            "Workspace.TNotebook.Tab",
            font=("Calibri", 11, "bold"),
            padding=(18, 9),
            background=c["panel_alt"],
            foreground=c["muted"],
            bordercolor=c["border"],
        )
        self.style.map(
            "Workspace.TNotebook.Tab",
            background=[("selected", c["panel"]), ("active", c["select"])],
            foreground=[("selected", c["text"]), ("active", c["text"])],
        )
        self.style.configure("ProjectTitle.TLabel", background=c["panel"], foreground=c["text"], font=("Calibri", 14, "bold"))
        self.style.configure("ProjectCount.TLabel", background=c["panel"], foreground=c["muted"], font=("Calibri", 10, "bold"))
        self.style.configure("ProjectPath.TLabel", background=c["panel"], foreground=c["muted"], font=("Calibri", 9))
        self.style.configure(
            "Danger.TButton",
            font=("Calibri", 10),
            padding=(10, 7),
            background=c["panel_alt"],
            foreground=c["danger"],
            bordercolor=c["border"],
        )
        self.style.map("Danger.TButton", background=[("active", c["select"])])
        self.style.configure(
            "Project.Treeview",
            font=("Calibri", 10),
            rowheight=29,
            background=c["panel"],
            fieldbackground=c["panel"],
            foreground=c["text"],
            bordercolor=c["border"],
        )
        self.style.map("Project.Treeview", background=[("selected", c["accent"])], foreground=[("selected", "#FFFFFF")])
        self.style.configure(
            "Project.Treeview.Heading",
            font=("Calibri", 10, "bold"),
            background=c["panel_alt"],
            foreground=c["text"],
            relief="flat",
            padding=(6, 7),
        )
        self.style.map("Project.Treeview.Heading", background=[("active", c["select"])])

    def _create_project_variables(self) -> None:
        self.project_name_var = tk.StringVar(value=self.project.name)
        self.project_path_var = tk.StringVar(value="Dosud neuložený projekt")
        self.project_count_var = tk.StringVar(value="0 řádků")
        self.project_filter_var = tk.StringVar()
        self.project_quick_position_var = tk.StringVar(value=self.project.next_position())
        self.project_quick_quantity_var = tk.StringVar(value="1")
        self.project_quick_designation_var = tk.StringVar()
        self.project_quick_note_var = tk.StringVar()
        self.project_detail_action_var = tk.StringVar(value="Přidat do projektu")
        self.project_edit_info_var = tk.StringVar(value="")
        self.project_concrete_var = tk.StringVar(value=getattr(self.project, "concrete_class", "C25/30") or "C25/30")

    def _available_project_concretes(self) -> list[str]:
        values: set[str] = set()
        for family in self.database.families:
            rows = family.get("moment_rows", []) if family.get("backend") == "matrix" else family.get("records", [])
            for row in rows:
                value = str(row.get("concrete_min", "")).strip()
                if value:
                    values.add(value)
        ordered = sorted(values, key=natural_key)
        if "C25/30" in ordered:
            ordered.remove("C25/30")
            ordered.insert(0, "C25/30")
        return ordered

    # ---------- sestavení projektové karty ----------

    def _build_project_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        project_card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 13))
        project_card.grid(row=0, column=0, sticky="ew")
        project_card.columnconfigure(1, weight=1)

        ttk.Label(project_card, text="Soupis izolačních nosníků objektu", style="ProjectTitle.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 16)
        )
        name_entry = ttk.Entry(project_card, textvariable=self.project_name_var)
        name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        self.project_name_entry = name_entry
        ttk.Label(project_card, textvariable=self.project_count_var, style="ProjectCount.TLabel").grid(
            row=0, column=2, sticky="e"
        )
        ttk.Label(project_card, textvariable=self.project_path_var, style="ProjectPath.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(5, 0)
        )
        concrete_bar = ttk.Frame(project_card, style="Card.TFrame")
        concrete_bar.grid(row=1, column=2, sticky="e", pady=(5, 0))
        ttk.Label(concrete_bar, text="Beton projektu", style="Card.TLabel").pack(side="left", padx=(0, 6))
        concrete_values = self._available_project_concretes()
        if self.project_concrete_var.get() not in concrete_values:
            self.project_concrete_var.set("C25/30" if "C25/30" in concrete_values else (concrete_values[0] if concrete_values else "C25/30"))
        self.project_concrete_combo = ttk.Combobox(concrete_bar, textvariable=self.project_concrete_var, values=concrete_values, state="readonly", width=10)
        self.project_concrete_combo.pack(side="left")
        self.project_concrete_combo.bind("<<ComboboxSelected>>", self._on_project_concrete_changed)
        ttk.Button(concrete_bar, text="Použít na řádky", command=self.apply_project_concrete_to_rows).pack(side="left", padx=(7, 0))

        filebar = ttk.Frame(parent, style="App.TFrame")
        filebar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        filebar.columnconfigure(9, weight=1)
        ttk.Button(filebar, text="Nový objekt", command=self.new_project).grid(row=0, column=0)
        ttk.Button(filebar, text="Otevřít projekt", command=self.open_project).grid(row=0, column=1, padx=(7, 0))
        ttk.Button(filebar, text="Uložit", style="Accent.TButton", command=self.save_project).grid(row=0, column=2, padx=(7, 0))
        ttk.Button(filebar, text="Uložit jako…", command=self.save_project_as).grid(row=0, column=3, padx=(7, 0))
        ttk.Separator(filebar, orient="vertical").grid(row=0, column=4, sticky="ns", padx=10)
        ttk.Button(filebar, text="Hromadné vložení", command=self.bulk_paste_project_rows).grid(row=0, column=5)
        ttk.Button(filebar, text="Kopírovat pro Excel", command=self.copy_project_table).grid(row=0, column=6, padx=(7, 0))
        ttk.Button(filebar, text="Export CSV", command=self.export_project_csv).grid(row=0, column=7, padx=(7, 0))
        ttk.Label(
            filebar,
            text="Projektový soubor uchovává i vydání katalogu a snímek hodnot.",
            style="Muted.TLabel",
        ).grid(row=0, column=9, sticky="e")

        quick_card = ttk.Frame(parent, style="Card.TFrame", padding=(14, 11))
        quick_card.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        quick_card.columnconfigure(5, weight=3)
        quick_card.columnconfigure(7, weight=2)
        ttk.Label(quick_card, text="Rychlé přidání řádku", style="Section.TLabel").grid(
            row=0, column=0, columnspan=9, sticky="w", pady=(0, 8)
        )
        ttk.Label(quick_card, text="Pozice", style="Card.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Entry(quick_card, textvariable=self.project_quick_position_var, width=10).grid(
            row=1, column=1, sticky="ew", padx=(6, 12)
        )
        ttk.Label(quick_card, text="Ks", style="Card.TLabel").grid(row=1, column=2, sticky="w")
        ttk.Entry(quick_card, textvariable=self.project_quick_quantity_var, width=6).grid(
            row=1, column=3, sticky="ew", padx=(6, 12)
        )
        ttk.Label(quick_card, text="Označení / část názvu", style="Card.TLabel").grid(row=1, column=4, sticky="w")
        designation_entry = ttk.Entry(quick_card, textvariable=self.project_quick_designation_var)
        designation_entry.grid(row=1, column=5, sticky="ew", padx=(6, 12))
        self.project_quick_entry = designation_entry
        ttk.Label(quick_card, text="Poznámka", style="Card.TLabel").grid(row=1, column=6, sticky="w")
        ttk.Entry(quick_card, textvariable=self.project_quick_note_var).grid(row=1, column=7, sticky="ew", padx=(6, 12))
        ttk.Button(quick_card, text="Přidat řádek", style="Accent.TButton", command=self.quick_add_project_row).grid(
            row=1, column=8
        )
        ttk.Label(
            quick_card,
            text="Stačí i část názvu nebo zápis s překlepem. Šipka ↓ otevře návrhy, Enter vybraný návrh doplní.",
            style="MutedCard.TLabel",
        ).grid(row=2, column=4, columnspan=5, sticky="w", pady=(6, 0))
        designation_entry.bind("<Control-a>", lambda _e: (designation_entry.selection_range(0, "end"), "break")[-1])
        self.project_autocomplete = DesignationAutocomplete(
            entry=designation_entry,
            variable=self.project_quick_designation_var,
            database=self.database,
            colors=self.colors,
            submit_callback=self.quick_add_project_row,
            on_choose=lambda result: self.set_status(f"Doplněno z našeptávače: {result.designation}"),
            preferred_catalog_getter=None,
            preferred_concrete_getter=lambda: self.project_concrete_var.get(),
            limit=12,
        )

        table_card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 12, 12, 10))
        table_card.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(2, weight=1)

        actionbar = ttk.Frame(table_card, style="Card.TFrame")
        actionbar.grid(row=0, column=0, sticky="ew")
        actionbar.columnconfigure(10, weight=1)
        ttk.Button(
            actionbar,
            textvariable=self.project_detail_action_var,
            style="Accent.TButton",
            command=self.add_or_update_project_from_lookup,
        ).grid(row=0, column=0)
        ttk.Button(actionbar, text="Načíst do editoru", command=self.load_selected_project_row).grid(
            row=0, column=1, padx=(7, 0)
        )
        ttk.Button(actionbar, text="Upravit pozici / ks", command=self.edit_selected_project_metadata).grid(
            row=0, column=2, padx=(7, 0)
        )
        ttk.Button(actionbar, text="Duplikovat", command=self.duplicate_selected_project_rows).grid(
            row=0, column=3, padx=(7, 0)
        )
        ttk.Button(actionbar, text="Nahoru", command=lambda: self.move_selected_project_rows(-1)).grid(
            row=0, column=4, padx=(7, 0)
        )
        ttk.Button(actionbar, text="Dolů", command=lambda: self.move_selected_project_rows(1)).grid(
            row=0, column=5, padx=(7, 0)
        )
        ttk.Button(actionbar, text="Smazat", style="Danger.TButton", command=self.delete_selected_project_rows).grid(
            row=0, column=6, padx=(7, 0)
        )
        ttk.Label(actionbar, text="Filtr", style="Card.TLabel").grid(row=0, column=8, padx=(18, 6))
        filter_entry = ttk.Entry(actionbar, textvariable=self.project_filter_var, width=27)
        filter_entry.grid(row=0, column=9, sticky="e")
        ttk.Button(actionbar, text="×", width=3, command=lambda: self.project_filter_var.set("")).grid(
            row=0, column=10, sticky="w", padx=(5, 0)
        )

        ttk.Label(
            table_card,
            text=(
                "Dvojklik načte řádek do detailního editoru. Více řádků lze označit pomocí Ctrl/Shift; "
                "kopírování bez výběru použije všechny právě zobrazené řádky."
            ),
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(8, 7))

        tree_frame = ttk.Frame(table_card, style="Card.TFrame")
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        column_ids = tuple(item[0] for item in self.PROJECT_COLUMNS)
        self.project_tree = ttk.Treeview(
            tree_frame,
            columns=column_ids,
            show="headings",
            selectmode="extended",
            style="Project.Treeview",
        )
        self._project_heading_labels = {column: label for column, label, *_rest in self.PROJECT_COLUMNS}
        for column, label, width, anchor, stretch in self.PROJECT_COLUMNS:
            self.project_tree.heading(column, text=label, command=lambda col=column: self.sort_project_table(col))
            self.project_tree.column(column, width=width, minwidth=42, anchor=anchor, stretch=stretch)
        vscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.project_tree.yview)
        hscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.project_tree.xview)
        self.project_tree.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        self.project_tree.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")

        self.project_tree.tag_configure("odd", background=self.colors["panel_alt"])
        self.project_tree.tag_configure("changed", foreground=self.colors["warning_text"])
        self.project_tree.tag_configure("missing", foreground=self.colors["danger"])
        self.project_tree.bind("<Double-1>", self.load_selected_project_row)
        self.project_tree.bind("<Delete>", self.delete_selected_project_rows)
        self.project_tree.bind("<Control-c>", self.copy_project_table)
        self.project_tree.bind("<<TreeviewSelect>>", self._on_project_tree_selection)

        self._build_project_context_menu()
        self.project_tree.bind("<Button-3>", self._show_project_context_menu)

        if self._project_filter_trace is None:
            self._project_filter_trace = self.project_filter_var.trace_add("write", self._on_project_filter_changed)
        if self._project_name_trace is None:
            self._project_name_trace = self.project_name_var.trace_add("write", self._on_project_name_changed)

        self.refresh_project_tree()

    def _on_project_concrete_changed(self, _event: tk.Event[Any] | None = None) -> None:
        target = self.project_concrete_var.get().strip() or "C25/30"
        self.project.concrete_class = target
        self.project.touch()
        self.mark_project_dirty()
        try:
            if hasattr(self, "refresh_project_concrete_filter"):
                self.refresh_project_concrete_filter()
        except Exception:
            pass
        self.set_status(f"Beton projektu nastaven na {target}. Databáze i našeptávač zobrazují pouze tento beton.")

    def apply_project_concrete_to_rows(self) -> None:
        target = self.project_concrete_var.get().strip() or "C25/30"
        self.project.concrete_class = target
        if not self.project.rows:
            self.mark_project_dirty()
            self.set_status(f"Beton projektu nastaven na {target}.")
            return
        if not messagebox.askyesno(
            "Použít beton na projekt",
            f"Přepočítat všechny řádky projektu na beton {target}, pokud je pro daný typ v katalogu dostupný?",
            parent=self,
        ):
            return
        updated = 0
        skipped: list[str] = []
        for row in list(self.project.rows):
            selection = dict(row.get("selection", {}))
            if str(selection.get("concrete_min", "")) == target:
                continue
            selection["concrete_min"] = target
            try:
                result = query_from_selection(self.database, selection)
            except Exception:
                skipped.append(str(row.get("position", "")) or str(row.get("id", ""))[:8])
                continue
            replacement = create_project_row(
                result,
                row_id=str(row["id"]),
                position=str(row.get("position", "")),
                quantity=int(row.get("quantity", 1)),
                note=str(row.get("note", "")),
            )
            self.project.replace(str(row["id"]), replacement)
            updated += 1
        self.mark_project_dirty()
        self.refresh_project_tree()
        message = f"Beton projektu: {target}. Přepočítáno {updated} řádků."
        if skipped:
            message += f" Beze změny zůstalo {len(skipped)} řádků, kde tato třída není dostupná."
        self.set_status(message)
        if skipped:
            messagebox.showwarning(
                "Beton projektu",
                message + "\n\nŘádky beze změny: " + ", ".join(skipped[:20]),
                parent=self,
            )

    def _build_project_context_menu(self) -> None:
        menu = tk.Menu(
            self,
            tearoff=False,
            font=("Calibri", 10),
            background=self.colors["panel"],
            foreground=self.colors["text"],
            activebackground=self.colors["accent"],
            activeforeground="#FFFFFF",
        )
        menu.add_command(label="Načíst do editoru", command=self.load_selected_project_row)
        menu.add_command(label="Upravit pozici / ks / poznámku", command=self.edit_selected_project_metadata)
        menu.add_command(label="Duplikovat", command=self.duplicate_selected_project_rows)
        menu.add_separator()
        menu.add_command(label="Kopírovat pro Excel", command=self.copy_project_table)
        menu.add_separator()
        menu.add_command(label="Smazat", command=self.delete_selected_project_rows)
        self.project_context_menu = menu

    def _show_project_context_menu(self, event: tk.Event[Any]) -> None:
        row_id = self.project_tree.identify_row(event.y)
        if row_id:
            if row_id not in self.project_tree.selection():
                self.project_tree.selection_set(row_id)
            self.project_tree.focus(row_id)
            try:
                self.project_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.project_context_menu.grab_release()

    # ---------- zobrazení a filtrování ----------

    def _on_project_filter_changed(self, *_args: Any) -> None:
        if hasattr(self, "project_tree"):
            self.refresh_project_tree()

    def _on_project_name_changed(self, *_args: Any) -> None:
        if self._project_var_guard:
            return
        self.project.name = self.project_name_var.get().strip() or "Nový objekt"
        self.mark_project_dirty()

    def _on_project_tree_selection(self, _event: tk.Event[Any] | None = None) -> None:
        selected = len(self.project_tree.selection()) if hasattr(self, "project_tree") else 0
        if selected:
            self.set_status(f"Vybráno {selected} řádků projektu.")

    def _mapping_text(self, row: dict[str, Any]) -> str:
        mapping = row.get("mapping", {})
        if not isinstance(mapping, dict):
            return "—"
        targets = mapping.get("targets", [])
        selected_id = mapping.get("selected_target_id")
        if selected_id and isinstance(targets, list):
            for target in targets:
                if isinstance(target, dict) and str(target.get("id")) == str(selected_id):
                    return str(target.get("designation") or target.get("label") or "Vybráno")
        if isinstance(targets, list) and targets:
            return f"{len(targets)} návrhů"
        status = str(mapping.get("status", "not_run"))
        return "—" if status == "not_run" else status

    def _row_payload(self, row: dict[str, Any], order: int) -> tuple[dict[str, Any], str]:
        status_code, result, _description = row_status(self.database, row)
        self.project_result_cache[str(row["id"])] = result
        selection = row.get("selection", {})
        snapshot = row.get("snapshot", {})
        status_text = {"ok": "OK", "changed": "Data změněna", "missing": "Nenalezeno"}.get(status_code, status_code)
        pages = ", ".join(str(value) for value in snapshot.get("source_pages", []))
        catalog_edition = str(snapshot.get("catalog_edition", ""))
        publication = str(snapshot.get("publication_label", ""))
        catalog_text = " • ".join(part for part in (catalog_edition, publication) if part)
        payload = {
            "order": order,
            "position": str(row.get("position", "")),
            "quantity": int(row.get("quantity", 1)),
            "manufacturer": str(selection.get("manufacturer", "")),
            "model": str(selection.get("model", "")),
            "type_name": str(selection.get("type_name", "")),
            "generation": str(selection.get("generation", "")),
            "moment_class": str(selection.get("moment_class", "")),
            "shear_class": str(selection.get("shear_class", "")),
            "concrete": concrete_label(str(selection.get("concrete_min", ""))) if selection.get("concrete_min") else "",
            "cover": str(selection.get("cover", "")),
            "height": str(selection.get("height_mm", "")) if selection.get("height_mm") is not None else "",
            "insulation": str(snapshot.get("insulation_text") or (result.insulation_text if result else "—")),
            "compression": str(snapshot.get("compression_transfer") or (result.compression_transfer if result else "neuvedeno / dle typu")),
            "moment": str(snapshot.get("moment_text", "—")),
            "shear": str(snapshot.get("shear_text", "—")),
            "extra": str(snapshot.get("other_text", "—")).replace("\n", "; "),
            "designation": str(snapshot.get("designation", "")),
            "catalog": catalog_text,
            "pages": pages,
            "mapping": self._mapping_text(row),
            "note": str(row.get("note", "")),
            "status": status_text,
        }
        return payload, status_code

    def _project_rows_for_view(self) -> list[tuple[dict[str, Any], int]]:
        filter_text = self.project_filter_var.get().strip().casefold() if hasattr(self, "project_filter_var") else ""
        rows: list[tuple[dict[str, Any], int]] = []
        for order, row in enumerate(self.project.rows, start=1):
            if filter_text:
                selection = row.get("selection", {})
                snapshot = row.get("snapshot", {})
                haystack = " ".join(
                    [
                        str(row.get("position", "")),
                        str(row.get("quantity", "")),
                        str(row.get("note", "")),
                        str(snapshot.get("designation", "")),
                        str(selection.get("manufacturer", "")),
                        str(selection.get("model", "")),
                        str(selection.get("type_name", "")),
                        str(selection.get("moment_class", "")),
                        str(selection.get("shear_class", "")),
                        str(selection.get("cover", "")),
                        str(selection.get("height_mm", "")),
                    ]
                ).casefold()
                if filter_text not in haystack:
                    continue
            rows.append((row, order))

        if self.project_sort_column:
            column = self.project_sort_column

            def key(item: tuple[dict[str, Any], int]) -> Any:
                payload, _status = self._row_payload(item[0], item[1])
                value = payload.get(column, "")
                if column in {"order", "quantity"}:
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return -1.0
                if column in {"moment", "shear"}:
                    match = re.search(r"[-−+]?\d+(?:[.,]\d+)?", str(value))
                    if match:
                        try:
                            return float(match.group(0).replace("−", "-").replace(",", "."))
                        except ValueError:
                            pass
                return natural_key(str(value))

            rows.sort(key=key, reverse=self.project_sort_reverse)
        return rows

    def refresh_project_tree(self, select_ids: Iterable[str] | None = None) -> None:
        if not hasattr(self, "project_tree"):
            return
        previous = set(select_ids or self.project_tree.selection())
        for item in self.project_tree.get_children(""):
            self.project_tree.delete(item)
        self.project_result_cache.clear()

        view_rows = self._project_rows_for_view()
        for visible_index, (row, original_order) in enumerate(view_rows):
            payload, status_code = self._row_payload(row, original_order)
            values = tuple(payload[column] for column, *_rest in self.PROJECT_COLUMNS)
            tags: list[str] = []
            if visible_index % 2:
                tags.append("odd")
            if status_code in {"changed", "missing"}:
                tags.append(status_code)
            self.project_tree.insert("", "end", iid=str(row["id"]), values=values, tags=tuple(tags))

        valid_previous = [row_id for row_id in previous if self.project_tree.exists(row_id)]
        if valid_previous:
            self.project_tree.selection_set(valid_previous)
            self.project_tree.focus(valid_previous[0])
            self.project_tree.see(valid_previous[0])

        total_rows = len(self.project.rows)
        displayed = len(view_rows)
        total_pieces = sum(int(row.get("quantity", 1)) for row in self.project.rows)
        if displayed == total_rows:
            count_text = f"{total_rows} řádků • {total_pieces} ks"
        else:
            count_text = f"Zobrazeno {displayed} z {total_rows} řádků • celkem {total_pieces} ks"
        self.project_count_var.set(count_text)
        self.project_path_var.set(str(self.project.path) if self.project.path else "Dosud neuložený projekt")
        self.project_quick_position_var.set(self.project.next_position())
        self._update_project_title()

    def sort_project_table(self, column: str) -> None:
        if self.project_sort_column == column:
            self.project_sort_reverse = not self.project_sort_reverse
        else:
            self.project_sort_column = column
            self.project_sort_reverse = False
        for col, label in self._project_heading_labels.items():
            arrow = ""
            if col == self.project_sort_column:
                arrow = " ▼" if self.project_sort_reverse else " ▲"
            self.project_tree.heading(col, text=label + arrow)
        self.refresh_project_tree()

    # ---------- rychlé a hromadné přidávání ----------

    def quick_add_project_row(self, _event: tk.Event[Any] | None = None) -> str | None:
        designation = self.project_quick_designation_var.get().strip()
        if not designation:
            self.set_status("Doplňte úplné označení nosníku.")
            return "break"
        try:
            quantity = safe_quantity(self.project_quick_quantity_var.get())
            result = self.database.resolve_designation(designation, preferred_concrete=self.project_concrete_var.get())
            position = self.project_quick_position_var.get().strip() or self.project.next_position()
            row = create_project_row(
                result,
                position=position,
                quantity=quantity,
                note=self.project_quick_note_var.get(),
            )
            self.project.add(row)
        except Exception as exc:
            messagebox.showerror("Řádek se nepodařilo přidat", str(exc), parent=self)
            self.set_status("Řádek nebyl přidán.")
            return "break"

        self.mark_project_dirty()
        self.project_quick_designation_var.set("")
        self.project_quick_note_var.set("")
        self.project_quick_quantity_var.set("1")
        self.refresh_project_tree(select_ids=[str(row["id"])])
        self.project_quick_entry.focus_set()
        self.set_status(f"Přidán řádek {position}: {result.designation}")
        return "break"

    @staticmethod
    def _split_bulk_line(line: str) -> list[str]:
        if "\t" in line:
            return [part.strip() for part in line.split("\t")]
        if line.count(";") >= 1:
            return [part.strip() for part in line.split(";")]
        return [line.strip()]

    @staticmethod
    def _looks_like_bulk_header(parts: list[str]) -> bool:
        normalized = " ".join(parts).casefold()
        return "označení" in normalized and ("pozice" in normalized or "typ" in normalized)

    def _interpret_bulk_parts(self, parts: list[str]) -> tuple[str, int, str, str]:
        while parts and not parts[-1]:
            parts.pop()
        if not parts:
            raise ValueError("Prázdný řádek.")
        if len(parts) == 1:
            return self.project.next_position(), 1, parts[0], ""
        if len(parts) == 2:
            return parts[0] or self.project.next_position(), 1, parts[1], ""
        if len(parts) == 3:
            try:
                quantity = safe_quantity(parts[1])
                return parts[0] or self.project.next_position(), quantity, parts[2], ""
            except ValueError:
                return parts[0] or self.project.next_position(), 1, parts[1], parts[2]
        quantity = safe_quantity(parts[1] or 1)
        return parts[0] or self.project.next_position(), quantity, parts[2], " | ".join(parts[3:]).strip()

    def bulk_paste_project_rows(self) -> None:
        dialog = BulkPasteDialog(self, self.colors)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        added_ids: list[str] = []
        errors: list[str] = []
        skipped_headers = 0
        for line_number, raw_line in enumerate(dialog.result.splitlines(), start=1):
            if not raw_line.strip():
                continue
            parts = self._split_bulk_line(raw_line)
            if self._looks_like_bulk_header(parts):
                skipped_headers += 1
                continue
            try:
                position, quantity, designation, note = self._interpret_bulk_parts(parts)
                if not designation.strip():
                    raise ValueError("Chybí označení nosníku.")
                result = self.database.resolve_designation(designation, preferred_concrete=self.project_concrete_var.get())
                row = create_project_row(result, position=position, quantity=quantity, note=note)
                self.project.add(row)
                added_ids.append(str(row["id"]))
            except Exception as exc:
                preview = raw_line.strip()
                if len(preview) > 95:
                    preview = preview[:92] + "…"
                errors.append(f"Řádek {line_number}: {preview} — {exc}")

        if added_ids:
            self.mark_project_dirty()
            self.refresh_project_tree(select_ids=added_ids[-1:])

        summary = f"Přidáno {len(added_ids)} řádků."
        if skipped_headers:
            summary += f" Přeskočeno záhlaví: {skipped_headers}."
        if errors:
            detail = "\n".join(errors[:18])
            if len(errors) > 18:
                detail += f"\n… a dalších {len(errors) - 18} chyb."
            messagebox.showwarning(
                "Hromadné vložení dokončeno s chybami",
                f"{summary}\nNepodařilo se načíst {len(errors)} řádků:\n\n{detail}",
                parent=self,
            )
            self.set_status(f"{summary} Chybných řádků: {len(errors)}.")
        else:
            messagebox.showinfo("Hromadné vložení dokončeno", summary, parent=self)
            self.set_status(summary)

    # ---------- přenos mezi tabulkou a detailním editorem ----------

    def _selected_project_ids(self) -> list[str]:
        if not hasattr(self, "project_tree"):
            return []
        return [str(value) for value in self.project_tree.selection()]

    def _single_selected_project_row(self, *, warn: bool = True) -> dict[str, Any] | None:
        selected = self._selected_project_ids()
        if len(selected) != 1:
            if warn:
                messagebox.showinfo("Vyberte jeden řádek", "Pro tuto akci vyberte právě jeden řádek.", parent=self)
            return None
        row = self.project.row_by_id(selected[0])
        if row is None and warn:
            messagebox.showerror("Řádek nebyl nalezen", "Vybraný řádek již v projektu neexistuje.", parent=self)
        return row

    def add_or_update_project_from_lookup(self) -> None:
        result: QueryResult | None = getattr(self, "current_result", None)
        if result is None:
            messagebox.showinfo("Výběr není úplný", "Nejprve v detailním editoru zvolte platný typ nosníku.", parent=self)
            return

        existing = self.project.row_by_id(self.project_edit_row_id) if self.project_edit_row_id else None
        position = str(existing.get("position")) if existing else self.project.next_position()
        quantity = int(existing.get("quantity", 1)) if existing else 1
        note = str(existing.get("note", "")) if existing else ""
        dialog = RowMetaDialog(
            self,
            title="Uložit změny projektového řádku" if existing else "Přidat nosník do projektu",
            position=position,
            quantity=quantity,
            note=note,
            designation=result.designation,
            colors=self.colors,
        )
        self.wait_window(dialog)
        if dialog.result is None:
            return

        if existing:
            row_id = str(existing["id"])
            replacement = create_project_row(result, row_id=row_id, **dialog.result)
            self.project.replace(row_id, replacement)
            action = "Aktualizován"
        else:
            replacement = create_project_row(result, **dialog.result)
            self.project.add(replacement)
            row_id = str(replacement["id"])
            action = "Přidán"

        self.mark_project_dirty()
        self.cancel_project_row_edit()
        self.refresh_project_tree(select_ids=[row_id])
        if hasattr(self, "main_notebook") and hasattr(self, "project_tab"):
            self.main_notebook.select(self.project_tab)
        self.set_status(f"{action} projektový řádek {dialog.result['position']}.")

    def _apply_project_selection_to_lookup(self, selection: dict[str, Any]) -> None:
        target = self.project_concrete_var.get().strip() or "C25/30"
        row_concrete = str(selection.get("concrete_min", ""))
        if row_concrete and row_concrete != target:
            raise ValueError(f"Řádek používá beton {row_concrete}, ale projekt je nastaven na {target}. Nejprve změňte beton projektu nebo použijte „Použít na řádky“.")
        self._updating = True
        try:
            manufacturer = str(selection["manufacturer"])
            manufacturers = tuple(self.combos["manufacturer"].cget("values"))
            if manufacturer not in manufacturers:
                raise ValueError(f"Výrobce {manufacturer} není v databázi.")
            self.manufacturer_var.set(manufacturer)
            self._cascade_from_manufacturer(str(selection["catalog_id"]))

            model = str(selection["model"])
            if model not in tuple(self.combos["model"].cget("values")):
                raise ValueError(f"Řada {model} není ve vybraném katalogu.")
            self.model_var.set(model)
            self._cascade_from_model(str(selection["type_name"]))

            type_name = str(selection["type_name"])
            if type_name not in tuple(self.combos["type"].cget("values")):
                raise ValueError(f"Typ {type_name} není ve vybraném katalogu.")
            self.type_var.set(type_name)
            self._cascade_from_type(str(selection["generation"]))

            generation = str(selection["generation"])
            if generation not in tuple(self.combos["generation"].cget("values")):
                raise ValueError(f"Generace {generation} není ve vybraném katalogu.")
            self.generation_var.set(generation)
            self._cascade_from_generation(str(selection["moment_class"]))

            moment = str(selection["moment_class"])
            if moment not in tuple(self.combos["moment"].cget("values")):
                raise ValueError(f"Momentová třída {moment} není dostupná.")
            self.moment_var.set(moment)
            self._cascade_from_moment(str(selection["concrete_min"]), str(selection["shear_class"]))

            concrete = str(selection["concrete_min"])
            if concrete not in tuple(self.combos["concrete"].cget("values")):
                raise ValueError(f"Beton {concrete} není dostupný.")
            self.concrete_var.set(concrete)
            self._cascade_from_concrete(
                preferred_shear=str(selection["shear_class"]),
                preferred_cover=str(selection["cover"]),
            )

            shear = str(selection["shear_class"])
            if shear not in tuple(self.combos["shear"].cget("values")):
                raise ValueError(f"Smyková třída {shear} není dostupná.")
            self.shear_var.set(shear)
            cover = str(selection["cover"])
            if cover not in tuple(self.combos["cover"].cget("values")):
                raise ValueError(f"Krytí {cover} není dostupné.")
            self.cover_var.set(cover)
            self._cascade_from_cover(selection["height_mm"])

            height = str(selection["height_mm"])
            if height not in tuple(self.combos["height"].cget("values")):
                raise ValueError(f"Výška H{height} není dostupná.")
            self.height_var.set(height)
        finally:
            self._updating = False
        self.refresh_result()

    def load_selected_project_row(self, _event: tk.Event[Any] | None = None) -> str | None:
        row = self._single_selected_project_row()
        if row is None:
            return "break"
        try:
            self._apply_project_selection_to_lookup(row["selection"])
        except Exception as exc:
            messagebox.showerror(
                "Řádek nelze načíst do editoru",
                f"Původní kombinace není v aktuální databázi dostupná:\n\n{exc}",
                parent=self,
            )
            return "break"

        self.project_edit_row_id = str(row["id"])
        self.project_detail_action_var.set("Uložit změny řádku")
        self.project_edit_info_var.set(f"Upravujete řádek {row.get('position', '')}")
        if hasattr(self, "cancel_project_edit_button"):
            self.cancel_project_edit_button.configure(state="normal")
        if hasattr(self, "main_notebook") and hasattr(self, "lookup_tab"):
            self.main_notebook.select(self.lookup_tab)
        self.quick_var.set(str(row.get("snapshot", {}).get("designation", "")))
        self.set_status(
            f"Řádek {row.get('position', '')} byl načten do editoru. Změňte parametry a použijte „Uložit změny řádku“."
        )
        return "break"

    def cancel_project_row_edit(self) -> None:
        self.project_edit_row_id = None
        self.project_detail_action_var.set("Přidat do projektu")
        self.project_edit_info_var.set("")
        if hasattr(self, "cancel_project_edit_button"):
            self.cancel_project_edit_button.configure(state="disabled")

    # ---------- operace s řádky ----------

    def edit_selected_project_metadata(self) -> None:
        row = self._single_selected_project_row()
        if row is None:
            return
        designation = str(row.get("snapshot", {}).get("designation", ""))
        dialog = RowMetaDialog(
            self,
            title="Upravit údaje projektového řádku",
            position=str(row.get("position", "")),
            quantity=int(row.get("quantity", 1)),
            note=str(row.get("note", "")),
            designation=designation,
            colors=self.colors,
        )
        self.wait_window(dialog)
        if dialog.result is None:
            return
        row.update(dialog.result)
        self.project.touch()
        self.mark_project_dirty()
        self.refresh_project_tree(select_ids=[str(row["id"])])
        self.set_status(f"Údaje řádku {dialog.result['position']} byly upraveny.")

    def duplicate_selected_project_rows(self) -> None:
        selected = self._selected_project_ids()
        if not selected:
            messagebox.showinfo("Není vybrán řádek", "Vyberte alespoň jeden řádek k duplikování.", parent=self)
            return
        new_ids: list[str] = []
        for row_id in selected:
            row = self.project.row_by_id(row_id)
            if row is None:
                continue
            duplicate = copy.deepcopy(row)
            duplicate["id"] = ""  # normalize_project_row vytvoří nové ID
            duplicate["position"] = self.project.next_position()
            self.project.add(duplicate)
            new_ids.append(str(self.project.rows[-1]["id"]))
        if new_ids:
            self.mark_project_dirty()
            self.refresh_project_tree(select_ids=new_ids)
            self.set_status(f"Duplikováno {len(new_ids)} řádků.")

    def delete_selected_project_rows(self, _event: tk.Event[Any] | None = None) -> str | None:
        selected = self._selected_project_ids()
        if not selected:
            return "break"
        count = len(selected)
        if not messagebox.askyesno(
            "Smazat řádky",
            f"Opravdu chcete z projektu odstranit {count} vybraných řádků?",
            parent=self,
        ):
            return "break"
        removed = self.project.remove_ids(selected)
        if self.project_edit_row_id in selected:
            self.cancel_project_row_edit()
        if removed:
            self.mark_project_dirty()
            self.refresh_project_tree()
            self.set_status(f"Odstraněno {removed} řádků.")
        return "break"

    def move_selected_project_rows(self, direction: int) -> None:
        selected = set(self._selected_project_ids())
        if not selected or direction not in {-1, 1}:
            return
        rows = self.project.rows
        if direction < 0:
            for index in range(1, len(rows)):
                if str(rows[index].get("id")) in selected and str(rows[index - 1].get("id")) not in selected:
                    rows[index - 1], rows[index] = rows[index], rows[index - 1]
        else:
            for index in range(len(rows) - 2, -1, -1):
                if str(rows[index].get("id")) in selected and str(rows[index + 1].get("id")) not in selected:
                    rows[index + 1], rows[index] = rows[index], rows[index + 1]
        self.project_sort_column = None
        self.project_sort_reverse = False
        self.mark_project_dirty()
        self.refresh_project_tree(select_ids=selected)
        self.set_status("Pořadí vybraných řádků bylo změněno.")

    # ---------- projektové soubory ----------

    def mark_project_dirty(self) -> None:
        self.project_dirty = True
        self._update_project_title()

    def _update_project_title(self) -> None:
        project_name = self.project.name.strip() or "Nový objekt"
        marker = " *" if self.project_dirty else ""
        self.title(f"{self.base_window_title} — {project_name}{marker}")

    def _set_project_document(self, document: ProjectDocument) -> None:
        self.project = document
        self.project_dirty = False
        self.project_edit_row_id = None
        self.project_sort_column = None
        self.project_sort_reverse = False
        self._project_var_guard = True
        try:
            self.project_name_var.set(document.name)
            self.project_concrete_var.set(getattr(document, "concrete_class", "C25/30") or "C25/30")
            self.project_filter_var.set("")
        finally:
            self._project_var_guard = False
        self.cancel_project_row_edit()
        self.refresh_project_tree()
        if hasattr(self, "refresh_project_concrete_filter"):
            self.refresh_project_concrete_filter()
        self._update_project_title()

    def _default_project_directory(self) -> Path:
        raw = self.settings.get("last_project_directory")
        if raw:
            path = Path(str(raw))
            if path.exists():
                return path
        documents = Path.home() / "Documents"
        return documents if documents.exists() else Path.home()

    @staticmethod
    def _safe_filename(value: str, fallback: str = "nosniky") -> str:
        cleaned = re.sub(r"[<>:\"/\\|?*]+", "_", value).strip(" ._")
        return cleaned or fallback

    def _confirm_project_save_if_needed(self) -> bool:
        if not self.project_dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Neuložené změny",
            f"Projekt „{self.project.name}“ obsahuje neuložené změny. Chcete je uložit?",
            parent=self,
        )
        if answer is None:
            return False
        if answer:
            return self.save_project()
        return True

    def new_project(self) -> None:
        if not self._confirm_project_save_if_needed():
            return
        self._set_project_document(ProjectDocument())
        self.project_quick_entry.focus_set()
        self.set_status("Byl založen nový prázdný projekt.")

    def open_project(self) -> None:
        if not self._confirm_project_save_if_needed():
            return
        path = filedialog.askopenfilename(
            parent=self,
            title="Otevřít projekt izolačních nosníků",
            initialdir=str(self._default_project_directory()),
            filetypes=[("Projekt TURTO – izolační nosníky", f"*{PROJECT_FILE_EXTENSION}"), ("Všechny soubory", "*.*")],
        )
        if not path:
            return
        try:
            document = ProjectDocument.load(path)
        except Exception as exc:
            messagebox.showerror("Projekt se nepodařilo otevřít", str(exc), parent=self)
            return
        self.settings["last_project_directory"] = str(Path(path).resolve().parent)
        self._set_project_document(document)
        self.set_status(f"Otevřen projekt {document.name} ({len(document.rows)} řádků).")

    def save_project(self) -> bool:
        if self.project.path is None:
            return self.save_project_as()
        return self._save_project_to(self.project.path)

    def save_project_as(self) -> bool:
        self.project.name = self.project_name_var.get().strip() or "Nový objekt"
        suggested = self._safe_filename(self.project.name, "projekt_nosniku") + PROJECT_FILE_EXTENSION
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Uložit projekt izolačních nosníků",
            initialdir=str(self._default_project_directory()),
            initialfile=suggested,
            defaultextension=PROJECT_FILE_EXTENSION,
            filetypes=[("Projekt TURTO – izolační nosníky", f"*{PROJECT_FILE_EXTENSION}"), ("Všechny soubory", "*.*")],
        )
        if not path:
            return False
        return self._save_project_to(Path(path))

    def _save_project_to(self, path: Path | str) -> bool:
        try:
            self.project.name = self.project_name_var.get().strip() or "Nový objekt"
            saved = self.project.save(path)
        except Exception as exc:
            messagebox.showerror("Projekt se nepodařilo uložit", str(exc), parent=self)
            return False
        self.project_dirty = False
        self.settings["last_project_directory"] = str(saved.parent)
        self.project_path_var.set(str(saved))
        self._update_project_title()
        self.set_status(f"Projekt byl uložen: {saved.name}")
        return True

    def confirm_project_close(self) -> bool:
        return self._confirm_project_save_if_needed()

    # ---------- kopírování a export ----------

    def _rows_for_copy(self) -> list[dict[str, Any]]:
        selected = self._selected_project_ids()
        ids = selected if selected else [str(value) for value in self.project_tree.get_children("")]
        rows: list[dict[str, Any]] = []
        for row_id in ids:
            row = self.project.row_by_id(row_id)
            if row is not None:
                rows.append(row)
        return rows

    def _payloads_for_rows(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        order_map = {str(row.get("id")): index for index, row in enumerate(self.project.rows, start=1)}
        result: list[dict[str, Any]] = []
        for row in rows:
            payload, _status = self._row_payload(row, order_map.get(str(row.get("id")), 0))
            result.append(payload)
        return result

    def copy_project_table(self, _event: tk.Event[Any] | None = None) -> str | None:
        rows = self._rows_for_copy()
        if not rows:
            self.set_status("Projekt neobsahuje řádky ke kopírování.")
            return "break"
        columns = [column for column, *_rest in self.PROJECT_COLUMNS]
        labels = [label for _column, label, *_rest in self.PROJECT_COLUMNS]
        lines = ["\t".join(labels)]
        for payload in self._payloads_for_rows(rows):
            values = [str(payload.get(column, "")).replace("\t", " ").replace("\r", " ").replace("\n", " ") for column in columns]
            lines.append("\t".join(values))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.set_status(f"Do schránky bylo zkopírováno {len(rows)} řádků pro vložení do Excelu.")
        return "break"

    def export_project_csv(self) -> None:
        if not self.project.rows:
            messagebox.showinfo("Projekt je prázdný", "Nejprve přidejte alespoň jeden řádek.", parent=self)
            return
        suggested = self._safe_filename(self.project.name, "projekt") + "_izolacni_nosniky.csv"
        initial_dir = self.settings.get("last_export_directory") or self._default_project_directory()
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Exportovat soupis pro Excel",
            initialdir=str(initial_dir),
            initialfile=suggested,
            defaultextension=".csv",
            filetypes=[("CSV pro Excel", "*.csv"), ("Všechny soubory", "*.*")],
        )
        if not path:
            return
        columns = [column for column, *_rest in self.PROJECT_COLUMNS]
        labels = [label for _column, label, *_rest in self.PROJECT_COLUMNS]
        try:
            with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
                writer.writerow(labels)
                for payload in self._payloads_for_rows(self.project.rows):
                    writer.writerow([payload.get(column, "") for column in columns])
        except Exception as exc:
            messagebox.showerror("Export se nepodařil", str(exc), parent=self)
            return
        self.settings["last_export_directory"] = str(Path(path).resolve().parent)
        self.set_status(f"Exportováno {len(self.project.rows)} řádků do {Path(path).name}.")
        messagebox.showinfo("Export dokončen", f"Soubor byl uložen:\n{Path(path).resolve()}", parent=self)

    # ---------- inicializace a klávesové zkratky ----------

    def finalize_project_workspace(self) -> None:
        self.project_quick_position_var.set(self.project.next_position())
        self.refresh_project_tree()
        self._update_project_title()
        self.bind_all("<Control-s>", lambda _event: self.save_project())
        self.bind_all("<Control-Shift-S>", lambda _event: self.save_project_as())
        self.bind_all("<Control-o>", lambda _event: self.open_project())
        self.bind_all("<Control-n>", lambda _event: self.new_project())
