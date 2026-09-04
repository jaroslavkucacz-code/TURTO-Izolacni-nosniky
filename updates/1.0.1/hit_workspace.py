from __future__ import annotations

import hashlib
import os
import shutil
import webbrowser
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hit_core import CONCRETES, COVERS, CONNECTION_TYPES, DATA_FILENAME, Candidate, DirectionalActions, HitDatabase, build_database_from_pdf, fmt
from ui_utils import place_dialog_on_parent

HIT_MODULE_VERSION = "1.0.1"

# Aktivní návrhové účinky pro jednotlivé typy. False = pole je v UI uzamčené
# a jeho případná dříve zadaná hodnota se při výpočtu ignoruje.
HIT_ACTION_FIELD_MASKS: dict[str, dict[str, bool]] = {
    "MVX":  {"m_pos": False, "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},
    "MVXL": {"m_pos": False, "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},
    "ZVX":  {"m_pos": False, "m_neg": False, "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": False},
    "ZDX":  {"m_pos": False, "m_neg": False, "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},
    "DD":   {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},
    "DVL":  {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": False},
    "DDL":  {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},
    "AT":   {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": True,  "v_pos": True, "v_neg": True},
    "FT":   {"m_pos": True,  "m_neg": True,  "n_pos": True,  "n_neg": True,  "v_pos": True, "v_neg": True},
    "OTX":  {"m_pos": False, "m_neg": False, "n_pos": True,  "n_neg": True,  "v_pos": True, "v_neg": False},
}

HIT_ACTION_META = {
    "m_pos": ("MEd+", "kNm/m"),
    "m_neg": ("MEd−", "kNm/m"),
    "n_pos": ("NEd+", "kN/m"),
    "n_neg": ("NEd−", "kN/m"),
    "v_pos": ("VEd+", "kN/m"),
    "v_neg": ("VEd−", "kN/m"),
}

# Typy, u kterých katalog nepřipouští volbu krytí. Hodnota je přímo kód cnom v mm.
# Annex 3 vede ZVX/ZDX výhradně s cnom = 30 mm.
HIT_FIXED_COVER_TYPES: dict[str, str] = {
    "ZVX": "30",
    "ZDX": "30",
    "AT": "30",
    "FT": "30",
    "OTX": "30",
}


def hit_action_field_mask(connection_type: str) -> dict[str, bool]:
    # Neznámý budoucí typ je bezpečně uzamčený, dokud mu výslovně neurčíme směry.
    return dict(HIT_ACTION_FIELD_MASKS.get(str(connection_type or "").upper(), {key: False for key in HIT_ACTION_META}))


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
        place_dialog_on_parent(self, parent)
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
                f"{row.series.get()} {row.connection_type.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "
                f"{row.action_summary()}"
            ),
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 2))
        economy_hint = (
            row.connection_type.get().strip().upper() == "MVXL"
            and row._family_info.get("mode") == "related"
            and int(row._family_info.get("alternative_count", 0) or 0) > 0
        )
        help_text = (
            "⚠ MVXL vyhovuje, ale vyhovuje i MVX. Bez cenové databáze je MVX označen jako možná úspornější alternativa; porovnejte varianty."
            if economy_hint
            else "První řádek je automaticky doporučená varianta. Dvojklikem nebo tlačítkem Použít variantu vyberete jiný vyhovující prvek."
        )
        ttk.Label(
            outer,
            text=help_text,
            style="HitEconomy.TLabel" if economy_hint else "Muted.TLabel",
        ).grid(row=2, column=0, sticky="ew", pady=(0, 10))

        frame = ttk.Frame(outer, style="Card.TFrame", padding=1)
        frame.grid(row=3, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = ("rank", "type", "designation", "length", "variant", "util", "amax", "nrd", "mode", "m1", "v1", "m2", "v2", "page")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", style="Data.Treeview")
        headings = {
            "rank": ("Poř.", 92, "center"),
            "type": ("Typ", 72, "center"),
            "designation": ("Varianta HIT", 340, "w"),
            "length": ("Délka", 82, "center"),
            "variant": ("Provedení", 84, "center"),
            "util": ("Využití", 82, "center"),
            "amax": ("a max", 82, "center"),
            "nrd": ("NRd", 78, "center"),
            "mode": ("Rozhoduje", 105, "center"),
            "m1": ("M1 / MRd", 88, "center"),
            "v1": ("V1 / VRd", 88, "center"),
            "m2": ("M2", 82, "center"),
            "v2": ("V2", 82, "center"),
            "page": ("Zdroj", 150, "center"),
        }
        for column, (label, width, anchor) in headings.items():
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=50, anchor=anchor, stretch=column == "designation")
        ybar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        economy_bg = "#FFF1C2" if getattr(parent, "theme_name", "light") == "light" else "#4A4126"
        self.tree.tag_configure("economy_alt", background=economy_bg)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")

        selected_iid = None
        selected = row.selected_candidate
        for index, candidate in enumerate(row.candidates, start=1):
            iid = f"v{index - 1}"
            self._candidate_by_iid[iid] = candidate
            suffix = candidate.suffix or "standard"
            preferred_type = row.connection_type.get().strip().upper()
            if candidate.connection_type != preferred_type:
                rank = "1 • náhrada" if index == 1 else ("náhrada" if not row._family_info.get("primary_available") else "alternativa")
            else:
                rank = "1 • preferovaný" if index == 1 else str(index)
            row_tags = ("economy_alt",) if (preferred_type == "MVXL" and candidate.connection_type == "MVX") else ()
            self.tree.insert(
                "", "end", iid=iid, tags=row_tags,
                values=(
                    rank, candidate.connection_type, candidate.designation, f"{candidate.physical_length_mm} mm", suffix,
                    ("—" if candidate.spacing_max > 0 else fmt(candidate.utilization * 100.0) + " %"),
                    (fmt(candidate.spacing_max,3) + " m" if candidate.spacing_max > 0 else "—"),
                    (fmt(candidate.nrd) if candidate.spacing_max > 0 else "—"), candidate.mode,
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
        self.connection_type = tk.StringVar(value=str(defaults.get("connection_type", "MVX")))
        self.height = tk.StringVar(value=str(defaults.get("height", "200")))
        self.cover = tk.StringVar(value=str(defaults.get("cover", "35")))
        self.concrete = tk.StringVar(value=str(defaults.get("concrete", "C25/30")))
        legacy_med = str(defaults.get("med", ""))
        legacy_ved = str(defaults.get("ved", ""))
        self.med_pos = tk.StringVar(value=str(defaults.get("med_pos", "")))
        self.med_neg = tk.StringVar(value=str(defaults.get("med_neg", legacy_med)))
        self.ved_pos = tk.StringVar(value=str(defaults.get("ved_pos", legacy_ved)))
        self.ved_neg = tk.StringVar(value=str(defaults.get("ved_neg", "")))
        self.ned_pos = tk.StringVar(value=str(defaults.get("ned_pos", "")))
        self.ned_neg = tk.StringVar(value=str(defaults.get("ned_neg", "")))
        self.load_x = tk.StringVar(value=str(defaults.get("load_x", "")))
        self.spacing = tk.StringVar(value="—")
        # Dočasné aliasy pro případ návazností vytvořených před v0.8.1.
        self.med = self.med_neg
        self.ved = self.ved_pos
        self.product = tk.StringVar(value="—")
        self.util = tk.StringVar(value="—")
        self.page = tk.StringVar(value="—")
        self.detail = tk.StringVar(value="čeká na MEd / VEd")
        self.candidates: list[Candidate] = []
        self._after_id: str | None = None
        self._manual_product = False
        self._family_info: dict[str, Any] = {}
        self.widgets: list[tk.Widget] = []
        self.action_entries: dict[str, ttk.Entry] = {}
        self._cover_forced = False
        self._last_free_cover = self.cover.get().strip() or "35"
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
        self.type_combo = combo(self.connection_type, CONNECTION_TYPES, 7)
        # Typ potřebuje nejprve změnit dostupnost vstupů a až potom přepočítat.
        self.type_combo.bind("<<ComboboxSelected>>", self._type_changed)
        entry(self.height, 8)
        self.cover_combo = combo(self.cover, tuple(str(value) for value in COVERS), 7)
        self.cover_combo.bind("<<ComboboxSelected>>", self._cover_changed)
        combo(self.concrete, CONCRETES, 9)
        self.med_pos_entry = entry(self.med_pos, 9)
        self.med_neg_entry = entry(self.med_neg, 9)
        self.ned_pos_entry = entry(self.ned_pos, 9)
        self.ned_neg_entry = entry(self.ned_neg, 9)
        self.ved_pos_entry = entry(self.ved_pos, 9)
        self.ved_neg_entry = entry(self.ved_neg, 9)
        self.load_x_entry = entry(self.load_x, 8)
        self.action_entries = {
            "m_pos": self.med_pos_entry,
            "m_neg": self.med_neg_entry,
            "n_pos": self.ned_pos_entry,
            "n_neg": self.ned_neg_entry,
            "v_pos": self.ved_pos_entry,
            "v_neg": self.ved_neg_entry,
        }
        self.product_combo = ttk.Combobox(parent, textvariable=self.product, values=(), state="readonly", width=41)
        self.widgets.append(self.product_combo)
        self.product_combo.bind("<<ComboboxSelected>>", self._product_changed)
        self.variants_button = ttk.Button(parent, text="Varianty…", width=10, command=self.open_variants, state="disabled")
        self.widgets.append(self.variants_button)
        self.util_label = ttk.Label(parent, textvariable=self.util, width=10, anchor="center", style="Card.TLabel")
        self.widgets.append(self.util_label)
        self.spacing_label = ttk.Label(parent, textvariable=self.spacing, width=10, anchor="center", style="Card.TLabel")
        self.widgets.append(self.spacing_label)
        self.page_label = ttk.Label(parent, textvariable=self.page, width=7, anchor="center", style="Card.TLabel")
        self.widgets.append(self.page_label)
        self.detail_label = ttk.Label(parent, textvariable=self.detail, width=45, anchor="w", style="MutedCard.TLabel")
        self.widgets.append(self.detail_label)
        self.remove_button = ttk.Button(parent, text="×", width=3, command=lambda: self.owner.remove_hit_row(self))
        self.widgets.append(self.remove_button)
        self.regrid(self.row_no)
        self._apply_type_constraints()

    def regrid(self, row_no: int) -> None:
        self.row_no = row_no
        for column, widget in enumerate(self.widgets):
            widget.grid(row=row_no, column=column, sticky="ew", padx=2, pady=2)

    def _active_action_mask(self) -> dict[str, bool]:
        return hit_action_field_mask(self.connection_type.get())

    def _apply_action_field_states(self) -> None:
        mask = self._active_action_mask()
        for key, widget in self.action_entries.items():
            active = bool(mask.get(key, False))
            widget.configure(
                state="normal" if active else "disabled",
                style="HitEditable.TEntry" if active else "HitLocked.TEntry",
            )

    def _apply_x_field_state(self) -> None:
        active = self.connection_type.get().strip().upper() == "OTX"
        self.load_x_entry.configure(
            state="normal" if active else "disabled",
            style="HitEditable.TEntry" if active else "HitLocked.TEntry",
        )

    def _apply_cover_field_state(self) -> None:
        typ = self.connection_type.get().strip().upper()
        fixed_cover = HIT_FIXED_COVER_TYPES.get(typ)
        if fixed_cover is not None:
            if not self._cover_forced:
                current = self.cover.get().strip()
                if current:
                    self._last_free_cover = current
            self.cover.set(fixed_cover)
            self.cover_combo.configure(state="disabled", style="HitLocked.TCombobox")
            self._cover_forced = True
            return

        if self._cover_forced:
            restore = self._last_free_cover if self._last_free_cover in {str(value) for value in COVERS} else "35"
            self.cover.set(restore)
        self.cover_combo.configure(state="readonly", style="TCombobox")
        self._cover_forced = False

    def _apply_type_constraints(self) -> None:
        self._apply_action_field_states()
        self._apply_x_field_state()
        self._apply_cover_field_state()

    def _cover_changed(self, _event: Any = None) -> None:
        if not self._cover_forced:
            current = self.cover.get().strip()
            if current:
                self._last_free_cover = current
        self._input_changed_now()

    def effective_action_texts(self) -> dict[str, str]:
        mask = self._active_action_mask()
        raw = {
            "m_pos": self.med_pos.get().strip(),
            "m_neg": self.med_neg.get().strip(),
            "n_pos": self.ned_pos.get().strip(),
            "n_neg": self.ned_neg.get().strip(),
            "v_pos": self.ved_pos.get().strip(),
            "v_neg": self.ved_neg.get().strip(),
        }
        return {key: (value if mask.get(key, False) else "") for key, value in raw.items()}

    def action_summary(self) -> str:
        values = self.effective_action_texts()
        parts = []
        for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg"):
            if not self._active_action_mask().get(key, False):
                continue
            label, unit = HIT_ACTION_META[key]
            parts.append(f"{label} {values[key] or '—'} {unit}")
        return " • ".join(parts) if parts else "bez aktivního směru zatížení"

    def _type_changed(self, _event: Any = None) -> None:
        self._manual_product = False
        if self._after_id:
            try:
                self.owner.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._apply_type_constraints()
        self.recalculate()

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

    def _read_values(self) -> tuple[int, int, DirectionalActions, float] | None:
        effective = self.effective_action_texts()
        texts = [effective[key] for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg")]
        if not any(texts):
            return None
        height = int(float(self.height.get().replace(",", ".")))
        cover = int(self.cover.get())

        def load_value(value: str) -> float:
            return abs(float((value or "0").replace(",", ".")))

        actions = DirectionalActions(
            m_pos=load_value(effective["m_pos"]), m_neg=load_value(effective["m_neg"]),
            v_pos=load_value(effective["v_pos"]), v_neg=load_value(effective["v_neg"]),
            n_pos=load_value(effective["n_pos"]), n_neg=load_value(effective["n_neg"]),
        )
        x_mm = load_value(self.load_x.get().strip()) if self.connection_type.get().strip().upper() == "OTX" else 0.0
        return height, cover, actions, x_mm


    def recalculate(self, preserve_product: str | None = None) -> None:
        self._after_id = None
        database = self.owner.hit_db
        self._family_info = {}
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
            self.variants_button.configure(text="Varianty…", state="disabled")
            self.product.set("—")
            self.util.set("—")
            self.page.set("—")
            self.spacing.set("—")
            self.detail_label.configure(style="MutedCard.TLabel")
            self.detail.set("čeká na MEd / VEd")
            self.owner.update_hit_status()
            return
        height, cover, actions, x_mm = values
        lengths = self.owner.allowed_hit_lengths()
        if not lengths:
            self._set_error("není povolena žádná délka")
            return
        candidates, error, family_info = database.proposal_candidates(
            self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), actions, lengths,
            self.owner.hit_offsets_var.get(), load_distance_x=x_mm,
        )
        self._family_info = family_info
        self.candidates = candidates
        if error:
            self._set_error(error)
            return
        if not candidates:
            self._set_error(f"bez vyhovující varianty {self.connection_type.get()} pro zadané zatížení")
            return
        names = [candidate.designation for candidate in candidates]
        self.product_combo.configure(values=names)
        alt_type = str(self._family_info.get("alternative_type", ""))
        alt_count = int(self._family_info.get("alternative_count", 0) or 0)
        economy_attention = (
            self.connection_type.get().strip().upper() == "MVXL"
            and alt_type == "MVX"
            and alt_count > 0
            and bool(self._family_info.get("primary_available"))
        )
        button_text = "⚠ Varianty… +MVX" if economy_attention else (f"Varianty… +{alt_type}" if alt_count else "Varianty…")
        self.variants_button.configure(text=button_text, width=16 if economy_attention else 14, state="normal" if len(candidates) > 1 else "disabled")
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
        if candidate.spacing_max > 0:
            self.util.set("—")
            self.spacing.set(fmt(candidate.spacing_max, 3) + " m")
        else:
            self.util.set(fmt(candidate.utilization * 100.0) + " %")
            self.spacing.set("—")
        self.page.set(str(candidate.page))
        self.detail_label.configure(style="MutedCard.TLabel")
        text = f"{len(self.candidates)} variant • {candidate.mode}"
        if self._manual_product:
            text += " • ručně zvoleno"
        preferred_type = self.connection_type.get().strip().upper()
        if candidate.connection_type != preferred_type:
            if preferred_type == "MVX" and candidate.connection_type == "MVXL":
                text += " • náhradní typ MVXL (MVX nevyhovuje)"
            elif preferred_type == "MVXL" and candidate.connection_type == "MVX":
                text += " • alternativa MVX místo MVXL"
        elif self._family_info.get("mode") == "related":
            text += " • ⚠ VYHOVUJE I MVX – zvažte jednodušší / možná úspornější variantu"
            self.detail_label.configure(style="HitEconomy.TLabel")
        if candidate.connection_type in {"AT", "FT", "OTX"}:
            text += f" • NRd {fmt(candidate.nrd)} • VRd {fmt(candidate.v1)} • amax {fmt(candidate.spacing_max,3)} m"
            if candidate.connection_type == "OTX":
                text += f" • x {fmt(candidate.load_distance_x,0)} mm"
        elif candidate.connection_type == "MVX":
            text += f" • M1/V1 {fmt(candidate.m1)}/{fmt(candidate.v1)} • M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"
        elif candidate.connection_type == "MVXL":
            text += f" • -MRd {fmt(candidate.m1)} • +VRd {fmt(candidate.v1)} • MVX M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"
        else:
            text += f" • MRd {fmt(candidate.m1)} • VRd {fmt(candidate.v1)}"
        self.detail.set(text)

    def _set_error(self, text: str) -> None:
        self.candidates = []
        self.product_combo.configure(values=())
        self.variants_button.configure(text="Varianty…", state="disabled")
        self.product.set("NELZE NAVRHNOUT")
        self.util.set("—")
        self.page.set("—")
        self.spacing.set("—")
        self.detail_label.configure(style="MutedCard.TLabel")
        self.detail.set(text)
        self.owner.update_hit_status()

    @property
    def selected_candidate(self) -> Candidate | None:
        value = self.product.get()
        return next((candidate for candidate in self.candidates if candidate.designation == value), None)

    def defaults_for_next(self) -> dict[str, str]:
        return {"series": self.series.get(), "connection_type": self.connection_type.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med_pos": "", "med_neg": "", "ned_pos": "", "ned_neg": "", "ved_pos": "", "ved_neg": "", "load_x": ""}

    def future_link_payload(self) -> dict[str, Any] | None:
        candidate = self.selected_candidate
        if candidate is None:
            return None
        effective = self.effective_action_texts()
        return {
            "name": self.name.get().strip(), "series": self.series.get(), "connection_type": candidate.connection_type, "height_mm": candidate.height,
            "cover_mm": candidate.cover, "concrete": candidate.concrete,
            "med_pos": effective["m_pos"], "med_neg": effective["m_neg"],
            "ned_pos": effective["n_pos"], "ned_neg": effective["n_neg"],
            "ved_pos": effective["v_pos"], "ved_neg": effective["v_neg"],
            "load_distance_x_mm": candidate.load_distance_x, "spacing_max_m": candidate.spacing_max, "nrd": candidate.nrd,
            "med": effective["m_neg"], "ved": effective["v_pos"],
            "designation": candidate.designation, "utilization": candidate.utilization,
            "source_page": candidate.page, "length_mm": candidate.physical_length_mm, "variant": candidate.suffix,
            "m1": candidate.m1, "v1": candidate.v1, "m2": candidate.m2, "v2": candidate.v2, "source_note": candidate.source_note,
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
        self.hit_l033_var = tk.BooleanVar(value=33 in lengths)
        self.hit_l025_var = tk.BooleanVar(value=25 in lengths)
        self.hit_offsets_var = tk.BooleanVar(value=bool(state.get("include_offsets", False)))
        self.hit_status_var = tk.StringVar(value="Připraveno k návrhu HIT.")
        self.hit_source_var = tk.StringVar(value="Data HIT nejsou načtena.")

    def _managed_hit_source_directory(self) -> Path:
        directory = Path(self.settings_path).resolve().parent / "sources" / "HIT"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def _hit_file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _is_managed_hit_source(self, path: Path) -> bool:
        try:
            Path(path).resolve().relative_to(self._managed_hit_source_directory().resolve())
            return True
        except Exception:
            return False

    def _store_hit_source_pdf(self, source: Path, expected_sha256: str = "") -> Path:
        source = Path(source).resolve()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Zdrojové DoP nebylo nalezeno: {source}")
        expected = str(expected_sha256 or "").strip().lower()
        source_sha = self._hit_file_sha256(source)
        if expected and source_sha != expected:
            raise RuntimeError("Zdrojové DoP neodpovídá databázi HIT (nesouhlasí SHA-256).")

        target = self._managed_hit_source_directory() / source.name
        if source == target.resolve():
            return target
        if target.exists() and self._hit_file_sha256(target) == source_sha:
            return target

        temp = target.with_name(target.name + ".tmp")
        try:
            shutil.copy2(source, temp)
            if self._hit_file_sha256(temp) != source_sha:
                raise RuntimeError("Kontrola kopie zdrojového DoP selhala.")
            temp.replace(target)
        finally:
            if temp.exists():
                try:
                    temp.unlink()
                except Exception:
                    pass
        return target

    def _discover_managed_hit_source(self, expected_sha256: str = "") -> Path | None:
        expected = str(expected_sha256 or "").strip().lower()
        for candidate in sorted(self._managed_hit_source_directory().glob("*.pdf")):
            try:
                if not expected or self._hit_file_sha256(candidate) == expected:
                    return candidate
            except Exception:
                continue
        return None

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
        # Vstupy, které se pro zvolený typ nepoužívají, musí být na první pohled
        # odlišné od editovatelných polí. Používáme vlastní styl i v tmavém režimu.
        locked_bg = "#DCE3EA" if getattr(self, "theme_name", "light") == "light" else "#35414D"
        editable_bg = self.colors["panel_alt"]
        self.style.configure(
            "HitEditable.TEntry",
            fieldbackground=editable_bg,
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=7,
            font=("Calibri", 10),
        )
        self.style.configure(
            "HitLocked.TEntry",
            fieldbackground=locked_bg,
            foreground=self.colors["muted"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=7,
            font=("Calibri", 10),
        )
        self.style.map(
            "HitLocked.TEntry",
            fieldbackground=[("disabled", locked_bg)],
            foreground=[("disabled", self.colors["muted"])],
        )
        self.style.configure(
            "HitLocked.TCombobox",
            fieldbackground=locked_bg,
            background=locked_bg,
            foreground=self.colors["muted"],
            arrowcolor=self.colors["muted"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=6,
            font=("Calibri", 10),
        )
        self.style.map(
            "HitLocked.TCombobox",
            fieldbackground=[("disabled", locked_bg)],
            background=[("disabled", locked_bg)],
            foreground=[("disabled", self.colors["muted"])],
            selectbackground=[("disabled", locked_bg)],
            selectforeground=[("disabled", self.colors["muted"])],
        )
        economy_bg = "#FFF1C2" if getattr(self, "theme_name", "light") == "light" else "#4A4126"
        economy_fg = "#6B5200" if getattr(self, "theme_name", "light") == "light" else "#FFE7A3"
        self.style.configure(
            "HitEconomy.TLabel",
            background=economy_bg,
            foreground=economy_fg,
            padding=(7, 4),
            font=("Calibri", 10, "bold"),
        )
        self._hit_built = True
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        top = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="Návrh nosníků Leviat HIT", style="ProjectTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text=f"HIT-HP/SP • MVX / MVXL / ZVX / ZDX / DD / DVL / DDL / AT / FT / OTX • modul {HIT_MODULE_VERSION}", style="MutedCard.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
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
        for column, label, variable in ((6, "1000 mm", self.hit_l100_var), (7, "500 mm", self.hit_l050_var), (8, "333 mm", self.hit_l033_var), (9, "250 mm", self.hit_l025_var)):
            ttk.Checkbutton(toolbar, text=label, variable=variable, command=self._hit_options_changed).grid(row=0, column=column, padx=(7, 0))
        ttk.Checkbutton(toolbar, text="MVX: zahrnout OD/OU/WD/WU", variable=self.hit_offsets_var, command=self._hit_options_changed).grid(row=0, column=10, padx=(16, 0))
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
        headers = ("Označení", "Řada", "Typ", "h [mm]", "cnom", "Beton", "MEd+", "MEd−", "NEd+", "NEd−", "VEd+", "VEd−", "x [mm]", "Navržený výrobek ▼", "Varianty", "Využití", "a max", "Zdroj", "Stav / kontrola", "")
        for column, text in enumerate(headers):
            ttk.Label(self.hit_rows_frame, text=text, style="Card.TLabel", font=("Calibri", 10, "bold"), anchor="w" if column in (0, 13, 18) else "center").grid(row=0, column=column, sticky="ew", padx=2, pady=(0, 5))
            self.hit_rows_frame.columnconfigure(column, weight=1 if column in (0, 13, 18) else 0)
        ttk.Label(parent, text=("Vstupy zatížení se automaticky zamykají podle zvoleného typu: MVX/MVXL = M−, V±; ZVX = pouze V+; ZDX = V±; DD = M±, V±; DVL = M±, V+; DDL = M±, V±; AT = M±, N−, V±; FT = M±, N±, V±; OTX = N±, V+ a vzdálenost x. Good/poor bond MVXL se volí automaticky podle h−cnom. Uzamčená pole mají odlišné podbarvení a při výpočtu se ignorují, ale jejich dříve zadaná hodnota se zachová pro případné přepnutí zpět. ZVX/ZDX mají podle Annexu 3 pevné cnom = 30 mm, proto se u nich volba krytí automaticky nastaví na 30 a uzamkne. Po návratu k jinému typu se obnoví poslední volitelné krytí. Výška v označení HIT je v cm: 200 mm → 20. Cenové doporučení zatím není aktivní: program nejprve hlídá statickou použitelnost a cenu budeme později používat až pro pořadí mezi technicky vyhovujícími variantami."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))
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
        if path is not None:
            try:
                probe = HitDatabase(path)
                if probe.schema_version >= 4:
                    self._load_hit_data(path, quiet=True)
                    return
            except Exception:
                pass

        state = self._hit_settings()
        saved_pdf = str(state.get("source_pdf", "")).strip()
        source = Path(saved_pdf) if saved_pdf and Path(saved_pdf).exists() else self._discover_managed_hit_source()
        if source is not None and source.exists():
            target = self._integrated_hit_data_path()
            try:
                self.hit_source_var.set("Aktualizuji databázi HIT pro další typy…")
                self.update_idletasks()
                build_database_from_pdf(source, target)
                state["data_path"] = str(target)
                state["source_pdf"] = str(source)
                self._load_hit_data(target, quiet=True)
                return
            except Exception as exc:
                self.hit_source_var.set(f"Automatická migrace HIT selhala: {exc}")

        self.hit_db = None
        self.hit_data_path = None
        self.hit_source_var.set("Data HIT nejsou načtena. Vyberte originální CONF-DOP HIT-HP/SP-07-23.")

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
        source_pdf = Path(saved_pdf) if saved_pdf and Path(saved_pdf).exists() else None
        self.hit_source_pdf = None
        if source_pdf is not None:
            try:
                self.hit_source_pdf = self._store_hit_source_pdf(source_pdf, database.source_sha256)
            except Exception as exc:
                # Databáze zůstává použitelná; pouze spravovaná kopie zdroje selhala.
                self.hit_source_pdf = source_pdf
                if not quiet:
                    messagebox.showwarning(
                        "Zdrojové DoP se nepodařilo uložit",
                        f"Databáze HIT je načtená, ale zdrojové PDF se nepodařilo zkopírovat do spravované složky TURTO:\n\n{exc}",
                        parent=self,
                    )
        if self.hit_source_pdf is None:
            self.hit_source_pdf = self._discover_managed_hit_source(database.source_sha256)
        if self.hit_source_pdf is not None:
            state["source_pdf"] = str(self.hit_source_pdf)
        if hasattr(self, "hit_open_source_button"):
            self.hit_open_source_button.configure(state="normal" if self.hit_source_pdf else "disabled")
        short_hash = database.source_sha256[:12] if database.source_sha256 else "bez SHA"
        total_records = len(database.records) + len(database.mvxl_records) + len(database.zvx_records) + len(database.dd_moment) + len(database.dvl_moment)
        self.hit_source_var.set(f"Načteno: {database.source_document} • typy {', '.join(database.available_connection_types)} • {total_records} záznamů • SHA {short_hash}…")
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
        if self.hit_source_pdf is not None and self._is_managed_hit_source(self.hit_source_pdf):
            self.hit_status_var.set("Data HIT i zdrojové DoP byly uloženy do spravované složky TURTO.")
        else:
            self.hit_status_var.set("Data HIT byla obnovena z DoP; zdrojové PDF zůstává na původním umístění.")

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
        if self.hit_l033_var.get(): lengths.add(33)
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
        lines = ["Označení\tŘada\tTyp\th [mm]\tcnom [mm]\tBeton\tMEd+ [kNm/m]\tMEd− [kNm/m]\tNEd+ [kN/m]\tNEd− [kN/m]\tVEd+ [kN/m]\tVEd− [kN/m]\tx [mm]\tNavržený výrobek\tVyužití\ta max [m]\tZdroj\tNRd\tMRd,1\tVRd,1\tMRd,2\tVRd,2"]
        count = 0
        for row in self.hit_rows:
            candidate = row.selected_candidate
            if candidate is None: continue
            effective = row.effective_action_texts()
            lines.append("\t".join([row.name.get(), row.series.get(), candidate.connection_type, row.height.get(), row.cover.get(), row.concrete.get(), effective["m_pos"], effective["m_neg"], effective["n_pos"], effective["n_neg"], effective["v_pos"], effective["v_neg"], (fmt(candidate.load_distance_x,0) if candidate.load_distance_x else ""), candidate.designation, ("" if candidate.spacing_max > 0 else fmt(candidate.utilization * 100.0) + " %"), (fmt(candidate.spacing_max,3) if candidate.spacing_max > 0 else ""), str(candidate.page), fmt(candidate.nrd), fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2)]))
            count += 1
        if not count:
            self.hit_status_var.set("Není co kopírovat – nejprve navrhněte alespoň jeden HIT.")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.hit_status_var.set(f"Do schránky zkopírováno {count} navržených HIT.")

    def hit_future_link_payloads(self) -> list[dict[str, Any]]:
        return [payload for row in self.hit_rows if (payload := row.future_link_payload()) is not None]
