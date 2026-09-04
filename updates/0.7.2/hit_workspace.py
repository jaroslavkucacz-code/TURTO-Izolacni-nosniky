from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hit_core import CONCRETES, COVERS, DATA_FILENAME, Candidate, HitDatabase, build_database_from_pdf, fmt

HIT_MODULE_VERSION = "0.3.0"


class HitVariantsDialog(tk.Toplevel):
    """Přehled všech vyhovujících variant pro jeden řádek návrhu HIT."""

    def __init__(self, parent: "HitWorkspaceMixin", row: "HitInputRow") -> None:
        super().__init__(parent)
        self.row = row
        self.result: Candidate | None = None
        self._candidate_by_iid: dict[str, Candidate] = {}
        self.title(f"Vyhovující varianty HIT – {row.name.get().strip() or 'řádek'}")
        self.geometry("1280x620")
        self.minsize(940, 460)
        self.transient(parent)
        self.grab_set()
        self.configure(background=parent.colors["bg"])
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, text="Vyhovující varianty Leviat HIT", style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=(
                f"{row.series.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "
                f"MEd {row.med.get()} kNm/m • VEd {row.ved.get()} kN/m"
            ),
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 2))
        ttk.Label(
            outer,
            text="První řádek je automaticky doporučená varianta. Dvojklikem nebo tlačítkem Použít variantu vyberete jiný vyhovující prvek.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(0, 10))

        frame = ttk.Frame(outer, style="Card.TFrame", padding=1)
        frame.grid(row=3, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = ("rank", "designation", "length", "variant", "util", "mode", "m1", "v1", "m2", "v2", "page")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", style="Data.Treeview")
        headings = {
            "rank": ("Poř.", 58, "center"),
            "designation": ("Varianta HIT", 340, "w"),
            "length": ("Délka", 82, "center"),
            "variant": ("Provedení", 84, "center"),
            "util": ("Využití", 82, "center"),
            "mode": ("Rozhoduje", 105, "center"),
            "m1": ("M1", 82, "center"),
            "v1": ("V1", 82, "center"),
            "m2": ("M2", 82, "center"),
            "v2": ("V2", 82, "center"),
            "page": ("DoP", 62, "center"),
        }
        for column, (label, width, anchor) in headings.items():
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=50, anchor=anchor, stretch=column == "designation")
        ybar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")

        selected_iid = None
        selected = row.selected_candidate
        for index, candidate in enumerate(row.candidates, start=1):
            iid = f"v{index - 1}"
            self._candidate_by_iid[iid] = candidate
            suffix = candidate.suffix or "standard"
            rank = "1 • doporučeno" if index == 1 else str(index)
            self.tree.insert(
                "", "end", iid=iid,
                values=(
                    rank, candidate.designation, f"{candidate.physical_length_mm} mm", suffix,
                    fmt(candidate.utilization * 100.0) + " %", candidate.mode,
                    fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2), str(candidate.page),
                ),
            )
            if candidate == selected:
                selected_iid = iid
        children = self.tree.get_children("")
        if selected_iid is None and children:
            selected_iid = children[0]
        if selected_iid:
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
            self.tree.see(selected_iid)

        self.tree.bind("<Double-1>", self._use_selected)
        self.tree.bind("<Return>", self._use_selected)
        actions = ttk.Frame(outer, style="App.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Zavřít", command=self.destroy).grid(row=0, column=1)
        ttk.Button(actions, text="Použít variantu", style="Accent.TButton", command=self._use_selected).grid(row=0, column=2, padx=(8, 0))
        self.bind("<Escape>", lambda _e: self.destroy())

    def _use_selected(self, _event: Any = None) -> str | None:
        selected = self.tree.selection()
        if not selected:
            return "break"
        candidate = self._candidate_by_iid.get(selected[0])
        if candidate is None:
            return "break"
        self.result = candidate
        self.destroy()
        return "break"


class HitInputRow:
    def __init__(self, owner: "HitWorkspaceMixin", row_no: int, defaults: dict[str, Any] | None = None):
        self.owner = owner
        self.row_no = row_no
        defaults = defaults or {}
        self.name = tk.StringVar(value=str(defaults.get("name", f"N{row_no}")))
        self.series = tk.StringVar(value=str(defaults.get("series", "HP")))
        self.height = tk.StringVar(value=str(defaults.get("height", "200")))
        self.cover = tk.StringVar(value=str(defaults.get("cover", "35")))
        self.concrete = tk.StringVar(value=str(defaults.get("concrete", "C25/30")))
        self.med = tk.StringVar(value=str(defaults.get("med", "")))
        self.ved = tk.StringVar(value=str(defaults.get("ved", "")))
        self.product = tk.StringVar(value="—")
        self.util = tk.StringVar(value="—")
        self.page = tk.StringVar(value="—")
        self.detail = tk.StringVar(value="čeká na MEd / VEd")
        self.candidates: list[Candidate] = []
        self._after_id: str | None = None
        self._manual_product = False
        self.widgets: list[tk.Widget] = []
        self._build()

    def _build(self) -> None:
        parent = self.owner.hit_rows_frame

        def entry(variable: tk.StringVar, width: int) -> ttk.Entry:
            widget = ttk.Entry(parent, textvariable=variable, width=width)
            self.widgets.append(widget)
            widget.bind("<KeyRelease>", self._input_changed)
            widget.bind("<FocusOut>", self._input_changed_now)
            widget.bind("<Return>", self._input_changed_now)
            return widget

        def combo(variable: tk.StringVar, values: tuple[Any, ...], width: int) -> ttk.Combobox:
            widget = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=width)
            self.widgets.append(widget)
            widget.bind("<<ComboboxSelected>>", self._input_changed_now)
            return widget

        entry(self.name, 9)
        combo(self.series, ("HP", "SP"), 6)
        entry(self.height, 8)
        combo(self.cover, tuple(str(value) for value in COVERS), 7)
        combo(self.concrete, CONCRETES, 9)
        entry(self.med, 11)
        entry(self.ved, 11)
        self.product_combo = ttk.Combobox(parent, textvariable=self.product, values=(), state="readonly", width=41)
        self.widgets.append(self.product_combo)
        self.product_combo.bind("<<ComboboxSelected>>", self._product_changed)
        self.variants_button = ttk.Button(parent, text="Varianty…", width=10, command=self.open_variants, state="disabled")
        self.widgets.append(self.variants_button)
        self.util_label = ttk.Label(parent, textvariable=self.util, width=10, anchor="center", style="Card.TLabel")
        self.widgets.append(self.util_label)
        self.page_label = ttk.Label(parent, textvariable=self.page, width=7, anchor="center", style="Card.TLabel")
        self.widgets.append(self.page_label)
        self.detail_label = ttk.Label(parent, textvariable=self.detail, width=45, anchor="w", style="MutedCard.TLabel")
        self.widgets.append(self.detail_label)
        self.remove_button = ttk.Button(parent, text="×", width=3, command=lambda: self.owner.remove_hit_row(self))
        self.widgets.append(self.remove_button)
        self.regrid(self.row_no)

    def regrid(self, row_no: int) -> None:
        self.row_no = row_no
        for column, widget in enumerate(self.widgets):
            widget.grid(row=row_no, column=column, sticky="ew", padx=2, pady=2)

    def _input_changed(self, _event: Any = None) -> None:
        self._manual_product = False
        self.detail.set("počítám…")
        if self._after_id:
            try:
                self.owner.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.owner.after(350, self.recalculate)

    def _input_changed_now(self, _event: Any = None) -> None:
        self._manual_product = False
        if self._after_id:
            try:
                self.owner.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.recalculate()

    def _read_values(self) -> tuple[int, int, float, float] | None:
        if not self.med.get().strip() or not self.ved.get().strip():
            return None
        height = int(float(self.height.get().replace(",", ".")))
        cover = int(self.cover.get())
        med = float(self.med.get().replace(",", "."))
        ved = float(self.ved.get().replace(",", "."))
        return height, cover, med, ved

    def recalculate(self, preserve_product: str | None = None) -> None:
        self._after_id = None
        database = self.owner.hit_db
        if database is None:
            self._set_error("nejprve načtěte data HIT z DoP")
            return
        try:
            values = self._read_values()
        except ValueError:
            self._set_error("neplatný číselný vstup")
            return
        if values is None:
            self.candidates = []
            self.product_combo.configure(values=())
            self.variants_button.configure(state="disabled")
            self.product.set("—")
            self.util.set("—")
            self.page.set("—")
            self.detail.set("čeká na MEd / VEd")
            self.owner.update_hit_status()
            return
        height, cover, med, ved = values
        lengths = self.owner.allowed_hit_lengths()
        if not lengths:
            self._set_error("není povolena žádná délka")
            return
        candidates, error = database.candidates(
            self.series.get(), height, cover, self.concrete.get(), med, ved, lengths, self.owner.hit_offsets_var.get()
        )
        self.candidates = candidates
        if error:
            self._set_error(error)
            return
        if not candidates:
            self._set_error(f"bez vyhovující varianty (tabulková výška h−cnom = {height-cover} mm)")
            return
        names = [candidate.designation for candidate in candidates]
        self.product_combo.configure(values=names)
        self.variants_button.configure(state="normal" if len(candidates) > 1 else "disabled")
        chosen = candidates[0]
        if preserve_product and preserve_product in names:
            chosen = candidates[names.index(preserve_product)]
        self.product.set(chosen.designation)
        self._manual_product = chosen is not candidates[0]
        self._show_candidate(chosen)
        self.owner.update_hit_status()

    def open_variants(self) -> None:
        if len(self.candidates) <= 1:
            return
        dialog = HitVariantsDialog(self.owner, self)
        self.owner.wait_window(dialog)
        candidate = dialog.result
        if candidate is None:
            return
        try:
            index = self.candidates.index(candidate)
        except ValueError:
            return
        self.product.set(candidate.designation)
        self._manual_product = index != 0
        self._show_candidate(candidate)
        self.owner.update_hit_status()

    def _product_changed(self, _event: Any = None) -> None:
        value = self.product.get()
        for index, candidate in enumerate(self.candidates):
            if candidate.designation == value:
                self._manual_product = index != 0
                self._show_candidate(candidate)
                self.owner.update_hit_status()
                break

    def _show_candidate(self, candidate: Candidate) -> None:
        self.util.set(fmt(candidate.utilization * 100.0) + " %")
        self.page.set(str(candidate.page))
        text = f"{len(self.candidates)} variant • {candidate.mode}"
        if self._manual_product:
            text += " • ručně zvoleno"
        text += f" • M1/V1 {fmt(candidate.m1)}/{fmt(candidate.v1)} • M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"
        self.detail.set(text)

    def _set_error(self, text: str) -> None:
        self.candidates = []
        self.product_combo.configure(values=())
        self.variants_button.configure(state="disabled")
        self.product.set("NELZE NAVRHNOUT")
        self.util.set("—")
        self.page.set("—")
        self.detail.set(text)
        self.owner.update_hit_status()

    @property
    def selected_candidate(self) -> Candidate | None:
        value = self.product.get()
        return next((candidate for candidate in self.candidates if candidate.designation == value), None)

    def defaults_for_next(self) -> dict[str, str]:
        return {"series": self.series.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med": "", "ved": ""}

    def future_link_payload(self) -> dict[str, Any] | None:
        candidate = self.selected_candidate
        if candidate is None:
            return None
        return {
            "name": self.name.get().strip(), "series": self.series.get(), "height_mm": candidate.height,
            "cover_mm": candidate.cover, "concrete": candidate.concrete, "med": self.med.get().strip(),
            "ved": self.ved.get().strip(), "designation": candidate.designation, "utilization": candidate.utilization,
            "source_page": candidate.page, "length_mm": candidate.physical_length_mm, "variant": candidate.suffix,
            "m1": candidate.m1, "v1": candidate.v1, "m2": candidate.m2, "v2": candidate.v2,
        }

    def destroy(self) -> None:
        if self._after_id:
            try:
                self.owner.after_cancel(self._after_id)
            except Exception:
                pass
        for widget in self.widgets:
            try:
                widget.destroy()
            except Exception:
                pass


class HitWorkspaceMixin:
    def _init_hit_workspace(self) -> None:
        self.hit_db: HitDatabase | None = None
        self.hit_rows: list[HitInputRow] = []
        self.hit_data_path: Path | None = None
        self.hit_source_pdf: Path | None = None
        self._hit_built = False

    def _hit_settings(self) -> dict[str, Any]:
        state = self.settings.setdefault("hit_module", {})
        if not isinstance(state, dict):
            state = {}
            self.settings["hit_module"] = state
        return state

    def _ensure_hit_variables(self) -> None:
        if hasattr(self, "hit_l100_var"):
            return
        state = self._hit_settings()
        lengths = {int(value) for value in state.get("lengths", [100, 50]) if str(value).isdigit()}
        self.hit_l100_var = tk.BooleanVar(value=100 in lengths)
        self.hit_l050_var = tk.BooleanVar(value=50 in lengths)
        self.hit_l025_var = tk.BooleanVar(value=25 in lengths)
        self.hit_offsets_var = tk.BooleanVar(value=bool(state.get("include_offsets", False)))
        self.hit_status_var = tk.StringVar(value="Připraveno k návrhu HIT.")
        self.hit_source_var = tk.StringVar(value="Data HIT nejsou načtena.")

    def _integrated_hit_data_path(self) -> Path:
        return Path(self.settings_path).resolve().parent / DATA_FILENAME

    def _discover_hit_data_path(self) -> Path | None:
        state = self._hit_settings()
        candidates: list[Path] = []
        saved = str(state.get("data_path", "")).strip()
        if saved:
            candidates.append(Path(saved))
        candidates.append(self._integrated_hit_data_path())
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            candidates.append(Path(localappdata) / "TURTO" / "HIT" / DATA_FILENAME)
        if hasattr(self, "root_dir"):
            candidates.append(Path(self.root_dir) / DATA_FILENAME)
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _build_hit_tab(self, parent: ttk.Frame) -> None:
        self._ensure_hit_variables()
        self._hit_built = True
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        top = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="Návrh nosníků Leviat HIT", style="ProjectTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text=f"HIT-HP/SP MVX • integrovaný modul {HIT_MODULE_VERSION}", style="MutedCard.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Label(top, textvariable=self.hit_source_var, style="MutedCard.TLabel").grid(row=2, column=0, sticky="w", pady=(3, 0))
        ttk.Button(top, text="Načíst / obnovit data z DoP", command=self.rebuild_hit_data).grid(row=0, column=1, rowspan=2, padx=(10, 0))
        self.hit_open_source_button = ttk.Button(top, text="Otevřít zdrojové DoP", command=self.open_hit_source, state="disabled")
        self.hit_open_source_button.grid(row=0, column=2, rowspan=2, padx=(7, 0))
        toolbar = ttk.Frame(parent, style="App.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        toolbar.columnconfigure(20, weight=1)
        ttk.Button(toolbar, text="+ Přidat řádek", style="Accent.TButton", command=self.add_hit_row).grid(row=0, column=0)
        ttk.Button(toolbar, text="Přepočítat vše", command=self.recalculate_hit_all).grid(row=0, column=1, padx=(7, 0))
        ttk.Button(toolbar, text="Vymazat vše", command=self.clear_hit_rows).grid(row=0, column=2, padx=(7, 0))
        ttk.Button(toolbar, text="Kopírovat výsledky", command=self.copy_hit_results).grid(row=0, column=3, padx=(7, 0))
        ttk.Separator(toolbar, orient="vertical").grid(row=0, column=4, sticky="ns", padx=12)
        ttk.Label(toolbar, text="Povolené délky").grid(row=0, column=5, sticky="w")
        for column, label, variable in ((6, "1000 mm", self.hit_l100_var), (7, "500 mm", self.hit_l050_var), (8, "250 mm", self.hit_l025_var)):
            ttk.Checkbutton(toolbar, text=label, variable=variable, command=self._hit_options_changed).grid(row=0, column=column, padx=(7, 0))
        ttk.Checkbutton(toolbar, text="zahrnout OD/OU/WD/WU", variable=self.hit_offsets_var, command=self._hit_options_changed).grid(row=0, column=9, padx=(16, 0))
        ttk.Label(toolbar, textvariable=self.hit_status_var, style="Muted.TLabel").grid(row=0, column=20, sticky="e")
        table_card = ttk.Frame(parent, style="Card.TFrame", padding=(10, 10, 10, 8))
        table_card.grid(row=2, column=0, sticky="nsew")
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(0, weight=1)
        canvas = tk.Canvas(table_card, highlightthickness=0, background=self.colors["panel"])
        ybar = ttk.Scrollbar(table_card, orient="vertical", command=canvas.yview)
        xbar = ttk.Scrollbar(table_card, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        self.hit_canvas = canvas
        self.hit_rows_frame = ttk.Frame(canvas, style="Card.TFrame")
        self.hit_canvas_window = canvas.create_window((0, 0), window=self.hit_rows_frame, anchor="nw")
        self.hit_rows_frame.bind("<Configure>", self._on_hit_rows_configure)
        canvas.bind("<Configure>", self._on_hit_canvas_configure)
        canvas.bind("<MouseWheel>", self._on_hit_mousewheel)
        headers = ("Označení", "Řada", "h [mm]", "cnom", "Beton", "MEd [kNm/m]", "VEd [kN/m]", "Navržený výrobek ▼", "Varianty", "Využití", "DoP", "Stav / interakce", "")
        for column, text in enumerate(headers):
            ttk.Label(self.hit_rows_frame, text=text, style="Card.TLabel", font=("Calibri", 10, "bold"), anchor="w" if column in (0, 7, 11) else "center").grid(row=0, column=column, sticky="ew", padx=2, pady=(0, 5))
            self.hit_rows_frame.columnconfigure(column, weight=1 if column in (0, 7, 11) else 0)
        ttk.Label(parent, text=("Výpočet používá přímo data z CONF-DOP HIT-HP/SP-07-23. Tabulková výška je h − cnom; skutečné označení se sestaví zpět s plnou výškou a krytím. Kontroluje se |MEd|/|VEd| ≥ 0,15 m a lineární interakční obálka M1/V1–M2/V2. Tento modul je zatím záměrně oddělený od projektového soupisu; provazby doplníme následně."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self._try_load_hit_data()
        if not self.hit_rows:
            self.add_hit_row()

    def _on_hit_rows_configure(self, _event: Any = None) -> None:
        if hasattr(self, "hit_canvas"):
            self.hit_canvas.configure(scrollregion=self.hit_canvas.bbox("all"))

    def _on_hit_canvas_configure(self, event: Any) -> None:
        if hasattr(self, "hit_canvas"):
            self.hit_canvas.itemconfigure(self.hit_canvas_window, width=max(event.width, self.hit_rows_frame.winfo_reqwidth()))

    def _on_hit_mousewheel(self, event: Any) -> str:
        if hasattr(self, "hit_canvas"):
            self.hit_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _try_load_hit_data(self) -> None:
        path = self._discover_hit_data_path()
        if path is None:
            self.hit_db = None
            self.hit_data_path = None
            self.hit_source_var.set("Data HIT nejsou načtena. Vyberte originální CONF-DOP HIT-HP/SP-07-23.")
            return
        self._load_hit_data(path, quiet=True)

    def _load_hit_data(self, path: Path, *, quiet: bool = False) -> bool:
        try:
            database = HitDatabase(path)
        except Exception as exc:
            self.hit_db = None
            if not quiet:
                messagebox.showerror("Data HIT se nepodařilo načíst", str(exc), parent=self)
            self.hit_source_var.set(f"Chyba databáze HIT: {exc}")
            return False
        self.hit_db = database
        self.hit_data_path = Path(path)
        state = self._hit_settings()
        state["data_path"] = str(self.hit_data_path)
        saved_pdf = str(state.get("source_pdf", "")).strip()
        self.hit_source_pdf = Path(saved_pdf) if saved_pdf and Path(saved_pdf).exists() else None
        if hasattr(self, "hit_open_source_button"):
            self.hit_open_source_button.configure(state="normal" if self.hit_source_pdf else "disabled")
        short_hash = database.source_sha256[:12] if database.source_sha256 else "bez SHA"
        self.hit_source_var.set(f"Načteno: {database.source_document} • {len(database.records)} záznamů • SHA {short_hash}…")
        if hasattr(self, "_save_settings"):
            self._save_settings()
        self.recalculate_hit_all()
        return True

    def rebuild_hit_data(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Vyberte CONF-DOP HIT-HP/SP-07-23", filetypes=[("PDF", "*.pdf"), ("Všechny soubory", "*.*")])
        if not path:
            return
        pdf = Path(path)
        target = self._integrated_hit_data_path()
        self.hit_status_var.set("Načítám tabulky z DoP…")
        self.update_idletasks()
        try:
            build_database_from_pdf(pdf, target)
        except Exception as exc:
            messagebox.showerror("Databázi HIT se nepodařilo vytvořit", str(exc), parent=self)
            self.hit_status_var.set("Data HIT nebyla změněna.")
            return
        state = self._hit_settings()
        state["source_pdf"] = str(pdf)
        state["data_path"] = str(target)
        self.hit_source_pdf = pdf
        self._load_hit_data(target)
        self.hit_status_var.set("Data HIT byla obnovena z DoP.")

    def open_hit_source(self) -> None:
        source = self.hit_source_pdf
        if source is None or not source.exists():
            messagebox.showinfo("Zdrojové DoP není dostupné", "Databáze může být převzata ze starší instalace HIT, ale cesta k původnímu PDF není známá. Použijte „Načíst / obnovit data z DoP“.", parent=self)
            return
        try:
            opened = webbrowser.open(source.resolve().as_uri(), new=2)
            if not opened and hasattr(os, "startfile"):
                os.startfile(str(source.resolve()))
        except Exception as exc:
            messagebox.showerror("DoP se nepodařilo otevřít", str(exc), parent=self)

    def allowed_hit_lengths(self) -> set[int]:
        lengths: set[int] = set()
        if self.hit_l100_var.get(): lengths.add(100)
        if self.hit_l050_var.get(): lengths.add(50)
        if self.hit_l025_var.get(): lengths.add(25)
        return lengths

    def _save_hit_options(self) -> None:
        state = self._hit_settings()
        state["lengths"] = sorted(self.allowed_hit_lengths(), reverse=True)
        state["include_offsets"] = bool(self.hit_offsets_var.get())
        if hasattr(self, "_save_settings"):
            self._save_settings()

    def _hit_options_changed(self) -> None:
        self._save_hit_options()
        self.recalculate_hit_all()

    def add_hit_row(self) -> None:
        defaults = self.hit_rows[-1].defaults_for_next() if self.hit_rows else None
        row = HitInputRow(self, len(self.hit_rows) + 1, defaults)
        self.hit_rows.append(row)
        self._on_hit_rows_configure()
        self.update_hit_status()

    def remove_hit_row(self, row: HitInputRow) -> None:
        if row not in self.hit_rows: return
        row.destroy()
        self.hit_rows.remove(row)
        for index, item in enumerate(self.hit_rows, start=1): item.regrid(index)
        self._on_hit_rows_configure()
        self.update_hit_status()

    def recalculate_hit_all(self) -> None:
        if not getattr(self, "_hit_built", False): return
        for row in list(self.hit_rows):
            preserve = row.product.get() if row._manual_product else None
            row.recalculate(preserve_product=preserve)
        self.update_hit_status()

    def clear_hit_rows(self) -> None:
        for row in list(self.hit_rows): row.destroy()
        self.hit_rows.clear()
        self.add_hit_row()
        self.hit_status_var.set("Zadání HIT bylo vymazáno.")

    def update_hit_status(self) -> None:
        if not hasattr(self, "hit_status_var"): return
        complete = sum(1 for row in self.hit_rows if row.selected_candidate is not None)
        errors = sum(1 for row in self.hit_rows if row.product.get() == "NELZE NAVRHNOUT")
        waiting = len(self.hit_rows) - complete - errors
        parts = [f"{len(self.hit_rows)} řádků", f"{complete} navrženo"]
        if errors: parts.append(f"{errors} nevyhovuje")
        if waiting: parts.append(f"{waiting} čeká")
        self.hit_status_var.set(" • ".join(parts))

    def copy_hit_results(self) -> None:
        lines = ["Označení\tŘada\th [mm]\tcnom [mm]\tBeton\tMEd [kNm/m]\tVEd [kN/m]\tNavržený výrobek\tVyužití\tDoP str.\tMRd,1\tVRd,1\tMRd,2\tVRd,2"]
        count = 0
        for row in self.hit_rows:
            candidate = row.selected_candidate
            if candidate is None: continue
            lines.append("\t".join([row.name.get(), row.series.get(), row.height.get(), row.cover.get(), row.concrete.get(), row.med.get(), row.ved.get(), candidate.designation, fmt(candidate.utilization * 100.0) + " %", str(candidate.page), fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2)]))
            count += 1
        if not count:
            self.hit_status_var.set("Není co kopírovat – nejprve navrhněte alespoň jeden HIT.")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.hit_status_var.set(f"Do schránky zkopírováno {count} navržených HIT.")

    def hit_future_link_payloads(self) -> list[dict[str, Any]]:
        return [payload for row in self.hit_rows if (payload := row.future_link_payload()) is not None]
