from __future__ import annotations

"""TURTO 2.0 workspace composition.

AKCE is the persistent root. Product domains sit below it; each domain exposes
Decoder / Design / Substitution. Manufacturer selection belongs to design and
substitution, not to the decoder. This makes the same UI reusable for dowels,
stair acoustics and future product families.
"""

from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

from action_workspace import build_action_bar
from action_report import export_action_pdf
from platform_registry import domain, domains, manufacturer, manufacturer_id_from_label, manufacturer_labels
from platform_state import ensure_platform_variables
from unified_schedule import open_unified_schedule
from supplier_export import export_supplier_excel


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _manufacturer_changed(owner: Any, mode: str) -> None:
    ensure_platform_variables(owner)
    variable = owner.design_manufacturer_var if mode == "design" else owner.substitution_manufacturer_var
    manufacturer_id = manufacturer_id_from_label("thermal_breaks", variable.get())
    if not manufacturer_id:
        variable.set("Leviat")
        return
    spec = manufacturer("thermal_breaks", manufacturer_id)
    adapter = spec.design_adapter if mode == "design" else spec.substitution_adapter
    if adapter != "leviat_hit":
        messagebox.showwarning(
            "Výrobce zatím není aktivní",
            f"Pro výrobce {spec.label} zatím není nainstalován návrhový / záměnový adaptér.",
            parent=owner,
        )
        variable.set("Leviat")
        return
    try:
        if mode == "design" and hasattr(owner, "design_catalog_var"):
            owner.design_catalog_var.set(spec.catalog_label)
        if mode == "substitution" and hasattr(owner, "substitution_catalog_var"):
            owner.substitution_catalog_var.set(spec.catalog_label)
        if not getattr(owner, "_action_loading", False) and hasattr(owner, "mark_project_dirty"):
            owner.mark_project_dirty()
    except Exception:
        pass


def _build_design_manufacturer_bar(owner: Any, parent: ttk.Frame) -> None:
    ensure_platform_variables(owner)
    spec = manufacturer("thermal_breaks", "leviat")
    owner.design_catalog_var = tk.StringVar(master=owner, value=spec.catalog_label)
    bar = ttk.Frame(parent, style="Card.TFrame", padding=(12, 8))
    bar.grid(row=0, column=0, sticky="ew")
    bar.columnconfigure(6, weight=1)
    ttk.Label(bar, text="Výrobce návrhu:", style="Card.TLabel", font=("Calibri", 10, "bold")).grid(row=0, column=0, sticky="w")
    combo = ttk.Combobox(bar, textvariable=owner.design_manufacturer_var, values=manufacturer_labels("thermal_breaks", enabled_only=True), state="readonly", width=18)
    combo.grid(row=0, column=1, sticky="w", padx=(7, 12))
    combo.bind("<<ComboboxSelected>>", lambda _e: _manufacturer_changed(owner, "design"))
    ttk.Label(bar, text="Katalog:", style="MutedCard.TLabel").grid(row=0, column=2, sticky="e")
    ttk.Label(bar, textvariable=owner.design_catalog_var, style="MutedCard.TLabel").grid(row=0, column=3, sticky="w", padx=(5, 12))
    ttk.Button(bar, text="Vložit výkaz…", style="Accent.TButton", command=lambda: open_unified_schedule(owner)).grid(row=0, column=7, padx=(8, 0))
    ttk.Button(bar, text="Export Excel – poptávka", command=lambda: export_supplier_excel(owner)).grid(row=0, column=8, padx=(7, 0))
    ttk.Button(bar, text="Aktualizovat katalog", command=owner.rebuild_hit_data).grid(row=0, column=9, padx=(7, 0))
    ttk.Button(bar, text="Otevřít zdroj", command=owner.open_hit_source).grid(row=0, column=10, padx=(7, 0))
    ttk.Label(parent, textvariable=getattr(owner, "hit_source_var", tk.StringVar(master=owner, value="")), style="Muted.TLabel").grid(row=1, column=0, sticky="ew", pady=(4, 0))


def _build_substitution_manufacturer_bar(owner: Any, parent: ttk.Frame) -> None:
    ensure_platform_variables(owner)
    spec = manufacturer("thermal_breaks", "leviat")
    owner.substitution_catalog_var = tk.StringVar(master=owner, value=spec.catalog_label)
    bar = ttk.Frame(parent, style="Card.TFrame", padding=(12, 8))
    bar.grid(row=0, column=0, sticky="ew")
    bar.columnconfigure(5, weight=1)
    ttk.Label(bar, text="Cílový výrobce záměny:", style="Card.TLabel", font=("Calibri", 10, "bold")).grid(row=0, column=0, sticky="w")
    combo = ttk.Combobox(bar, textvariable=owner.substitution_manufacturer_var, values=manufacturer_labels("thermal_breaks", enabled_only=True), state="readonly", width=18)
    combo.grid(row=0, column=1, sticky="w", padx=(7, 12))
    combo.bind("<<ComboboxSelected>>", lambda _e: _manufacturer_changed(owner, "substitution"))
    ttk.Label(bar, text="Aktivní převodní modul:", style="MutedCard.TLabel").grid(row=0, column=2, sticky="e")
    ttk.Label(bar, text="Leviat HIT", style="MutedCard.TLabel").grid(row=0, column=3, sticky="w", padx=(5, 12))
    ttk.Label(bar, text="Výběr výrobce je uložen v AKCI; další katalogové adaptéry se sem doplní bez změny pracovního postupu.", style="MutedCard.TLabel").grid(row=0, column=5, sticky="e")


def _future_domain(owner: Any, parent: ttk.Frame, domain_id: str) -> None:
    spec = domain(domain_id)
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)
    head = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
    head.grid(row=0, column=0, sticky="ew")
    ttk.Label(head, text=spec.label, style="ProjectTitle.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(head, text=spec.description, style="MutedCard.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
    notebook = ttk.Notebook(parent, style="Workspace.TNotebook")
    notebook.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
    for title in ("Dekodér", "Návrh", "Záměny"):
        tab = ttk.Frame(notebook, style="App.TFrame", padding=18)
        notebook.add(tab, text=title)
        card = ttk.Frame(tab, style="Card.TFrame", padding=22)
        card.pack(fill="x")
        ttk.Label(card, text=f"{title} – modul připraven", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="TURTO 2.0 už má pro tuto produktovou oblast samostatný prostor a jednotný model AKCE. Funkce se aktivují přidáním katalogu a výrobního adaptéru; není potřeba měnit strukturu programu.", style="MutedCard.TLabel", wraplength=1000, justify="left").pack(anchor="w", pady=(6, 0))


def install(app_base: Any) -> None:
    cls = app_base.ThermalConnectorApp
    original_header = cls._build_header

    def header(self) -> None:
        original_header(self)
        for widget in _walk(self):
            try:
                if isinstance(widget, ttk.Label):
                    text = str(widget.cget("text"))
                    if text in {"TURTO ISO | Databáze izolačních nosníků", "TURTO ISO | Izolační nosníky"}:
                        widget.configure(text="TURTO 2.0 | Technické prvky")
                    elif text.startswith("Jedna AKCE • Dekodér ISO") or text.startswith("Projektový soupis"):
                        widget.configure(text="Jedna AKCE • více produktových oblastí • více výrobců • Dekodér / Návrh / Záměny")
            except Exception:
                pass

    def body(self) -> None:
        ensure_platform_variables(self)
        body = ttk.Frame(self, style="App.TFrame", padding=(18, 12, 18, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        action_bar = build_action_bar(self, body)
        action_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        report = ttk.Frame(body, style="Card.TFrame", padding=(12, 8))
        report.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        report.columnconfigure(2, weight=1)
        ttk.Label(report, text="Výstup celé AKCE", style="Card.TLabel", font=("Calibri", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(report, text="PDF je nadřazené produktovým oblastem. Dnes obsahuje izolační nosníky; další oblasti se přidají přes report provider.", style="MutedCard.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Button(report, text="Export PDF AKCE", style="Accent.TButton", command=lambda: export_action_pdf(self)).grid(row=0, column=3, sticky="e")

        domains_nb = ttk.Notebook(body, style="Workspace.TNotebook")
        domains_nb.grid(row=2, column=0, sticky="nsew")
        self.product_domain_notebook = domains_nb
        self.product_domain_tab_by_id = {}

        thermal = ttk.Frame(domains_nb, style="App.TFrame", padding=(0, 8, 0, 0))
        shear = ttk.Frame(domains_nb, style="App.TFrame", padding=(0, 8, 0, 0))
        acoustics = ttk.Frame(domains_nb, style="App.TFrame", padding=(0, 8, 0, 0))
        for spec, frame in zip(domains(), (thermal, shear, acoustics)):
            domains_nb.add(frame, text=spec.short_label)
            self.product_domain_tab_by_id[spec.id] = frame

        thermal.columnconfigure(0, weight=1)
        thermal.rowconfigure(1, weight=1)
        domain_head = ttk.Frame(thermal, style="Card.TFrame", padding=(12, 8))
        domain_head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(domain_head, text="Izolační nosníky", style="ProjectTitle.TLabel").pack(side="left")
        ttk.Label(domain_head, text="Dekodér pracuje se všemi katalogy; výrobce se volí až pro Návrh a Záměny.", style="MutedCard.TLabel").pack(side="left", padx=(14, 0))

        operations = ttk.Notebook(thermal, style="Workspace.TNotebook")
        operations.grid(row=1, column=0, sticky="nsew")
        self.main_notebook = operations

        decoder = ttk.Frame(operations, style="App.TFrame", padding=(0, 8, 0, 0))
        design = ttk.Frame(operations, style="App.TFrame", padding=(0, 8, 0, 0))
        substitution = ttk.Frame(operations, style="App.TFrame", padding=(0, 8, 0, 0))
        operations.add(decoder, text="Dekodér")
        operations.add(design, text="Návrh")
        operations.add(substitution, text="Záměny")
        self.project_tab = decoder
        self.hit_tab = design
        self.substitution_tab = substitution

        decoder.columnconfigure(0, weight=1); decoder.rowconfigure(0, weight=1)
        self._build_project_tab(decoder)

        design.columnconfigure(0, weight=1); design.rowconfigure(2, weight=1)
        design_content = ttk.Frame(design, style="App.TFrame")
        design_content.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        design_content.columnconfigure(0, weight=1); design_content.rowconfigure(0, weight=1)
        self._build_hit_tab(design_content)
        _build_design_manufacturer_bar(self, design)

        substitution.columnconfigure(0, weight=1); substitution.rowconfigure(1, weight=1)
        _build_substitution_manufacturer_bar(self, substitution)
        substitution_content = ttk.Frame(substitution, style="App.TFrame")
        substitution_content.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        substitution_content.columnconfigure(0, weight=1); substitution_content.rowconfigure(0, weight=1)
        self._build_substitution_tab(substitution_content)
        for widget in _walk(substitution_content):
            try:
                if isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Aktualizovat z projektu":
                    widget.configure(text="Aktualizovat z Dekodéru")
                elif isinstance(widget, ttk.Label):
                    text = str(widget.cget("text"))
                    if text == "Záměny za HIT":
                        widget.configure(text="Záměny izolačních nosníků")
                    elif text.startswith("Návrh záměny za Leviat HIT"):
                        widget.configure(text="Cílový výrobce je určen nahoře; aktivní adaptér této verze je Leviat HIT.")
            except Exception:
                pass

        operations.bind("<<NotebookTabChanged>>", self._on_substitution_tab_selected, add="+")
        operations.select(decoder)

        _future_domain(self, shear, "shear_dowels")
        _future_domain(self, acoustics, "stair_acoustics")

        self._action_loading = False
        if str(self.project_name_var.get()).strip() in {"", "Nový objekt"}:
            self._project_var_guard = True
            try:
                self.project.name = "Nová akce"
                self.project_name_var.set("Nová akce")
            finally:
                self._project_var_guard = False
        self.project_dirty = False
        self.project.path = None
        self.base_window_title = "TURTO 2.0 – Technické prvky"
        self._update_action_info()
        self._update_project_title()

    cls._build_header = header
    cls._build_body = body
