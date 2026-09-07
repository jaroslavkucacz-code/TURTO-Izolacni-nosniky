from __future__ import annotations

"""Specialized UI for HIT supplementary elements (HT / AT / FT / OTX)."""

from typing import Any
import tkinter as tk
from tkinter import ttk

from hit_core import CONCRETES, Candidate, DirectionalActions, fmt
from hit_ht import design_ht_candidates, expected_ht_width_mm

AUX_TYPES = ("HT", "AT", "FT", "OTX")
SPECIAL_TYPES = ("AT", "FT", "OTX")
MASKS = {
    "HT":  {"m_pos": False, "m_neg": False, "n_pos": False, "n_neg": False, "v_pos": False, "v_neg": False, "h_parallel": True,  "h_perp": True},
    "AT":  {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": True,  "v_pos": True,  "v_neg": True,  "h_parallel": False, "h_perp": False},
    "FT":  {"m_pos": True,  "m_neg": True,  "n_pos": True,  "n_neg": True,  "v_pos": True,  "v_neg": True,  "h_parallel": False, "h_perp": False},
    "OTX": {"m_pos": False, "m_neg": False, "n_pos": True,  "n_neg": True,  "v_pos": True,  "v_neg": False, "h_parallel": False, "h_perp": False},
}

HEADERS = (
    ("name", "Pozice", "w"),
    ("quantity", "Ks", "center"),
    ("series", "Řada", "center"),
    ("type", "Typ HIT", "center"),
    ("height", "h [mm]", "center"),
    ("dimension", "B / L [mm]", "center"),
    ("concrete", "Beton", "center"),
    ("m_pos", "MEd+ [kNm/m]", "center"),
    ("m_neg", "MEd− [kNm/m]", "center"),
    ("n_pos", "NEd+ [kN/m]", "center"),
    ("n_neg", "NEd− [kN/m]", "center"),
    ("v_pos", "VEd+ [kN/m]", "center"),
    ("v_neg", "VEd− [kN/m]", "center"),
    ("h_parallel", "HEd∥ [kN/prv.]", "center"),
    ("h_perp", "HEd⊥ [kN/prv.]", "center"),
    ("x", "x [mm]", "center"),
    ("product", "Navržený HIT", "w"),
    ("util", "Využití / a max", "center"),
    ("source", "Zdroj", "center"),
    ("status", "Výsledek / kontrola", "w"),
    ("remove", "", "center"),
)


def _num(text: Any) -> float:
    value = str(text or "").strip().replace("−", "-").replace(",", ".")
    if not value:
        return 0.0
    return abs(float(value))


def _qty(text: Any) -> int:
    value = int(str(text or "1").strip())
    if not 1 <= value <= 1_000_000:
        raise ValueError("Počet kusů musí být celé číslo 1–1 000 000.")
    return value


def _candidate_dict(candidate: Candidate | None) -> dict[str, Any]:
    if candidate is None:
        return {}
    return {
        "designation": candidate.designation,
        "series": candidate.series,
        "connection_type": candidate.connection_type,
        "code": candidate.code,
        "physical_length_mm": candidate.physical_length_mm,
        "height": candidate.height,
        "cover": candidate.cover,
        "concrete": candidate.concrete,
        "utilization": candidate.utilization,
        "spacing_max": candidate.spacing_max,
        "load_distance_x": candidate.load_distance_x,
        "page": candidate.page,
        "nrd": candidate.nrd,
        "m1": candidate.m1,
        "v1": candidate.v1,
        "m2": candidate.m2,
        "v2": candidate.v2,
        "mode": candidate.mode,
        "source_note": candidate.source_note,
    }


class AuxRow:
    def __init__(self, owner: Any, parent: ttk.Frame, row_no: int, defaults: dict[str, Any] | None = None) -> None:
        self.owner = owner
        self.parent = parent
        self.row_no = row_no
        d = dict(defaults or {})
        self.name = tk.StringVar(master=owner, value=str(d.get("name", f"D{row_no:03d}")))
        self.quantity = tk.StringVar(master=owner, value=str(d.get("quantity", "1") or "1"))
        self.series = tk.StringVar(master=owner, value=str(d.get("series", "HP") or "HP"))
        typ = str(d.get("connection_type", d.get("type", "HT")) or "HT").upper()
        self.connection_type = tk.StringVar(master=owner, value=typ if typ in AUX_TYPES else "HT")
        self.height = tk.StringVar(master=owner, value=str(d.get("height", "200") or "200"))
        default_dimension = expected_ht_width_mm(self.series.get()) if self.connection_type.get() == "HT" else 250
        self.dimension = tk.StringVar(master=owner, value=str(d.get("dimension", d.get("required_length", default_dimension)) or default_dimension))
        self.concrete = tk.StringVar(master=owner, value=str(d.get("concrete", "C25/30") or "C25/30"))
        self.med_pos = tk.StringVar(master=owner, value=str(d.get("med_pos", "")))
        self.med_neg = tk.StringVar(master=owner, value=str(d.get("med_neg", "")))
        self.ned_pos = tk.StringVar(master=owner, value=str(d.get("ned_pos", "")))
        self.ned_neg = tk.StringVar(master=owner, value=str(d.get("ned_neg", "")))
        self.ved_pos = tk.StringVar(master=owner, value=str(d.get("ved_pos", "")))
        self.ved_neg = tk.StringVar(master=owner, value=str(d.get("ved_neg", "")))
        self.hed_parallel = tk.StringVar(master=owner, value=str(d.get("hed_parallel", "")))
        self.hed_perp = tk.StringVar(master=owner, value=str(d.get("hed_perp", "")))
        self.load_x = tk.StringVar(master=owner, value=str(d.get("load_x", "")))
        self.product = tk.StringVar(master=owner, value="—")
        self.util = tk.StringVar(master=owner, value="—")
        self.source = tk.StringVar(master=owner, value="—")
        self.status = tk.StringVar(master=owner, value="čeká na zatížení")
        self.saved_designation = str(d.get("selected_designation", "") or "")
        self.manual_product = bool(d.get("manual_product", False))
        self.candidates: list[Candidate] = []
        self.selected_candidate: Candidate | None = None
        self.widgets: list[tk.Widget] = []
        self.entries: dict[str, ttk.Entry] = {}
        self._after: str | None = None
        self._build()
        self._apply_type()
        self.recalculate(preserve=self.saved_designation or None)

    def _entry(self, key: str, variable: tk.StringVar, width: int, justify: str = "center") -> ttk.Entry:
        widget = ttk.Entry(self.parent, textvariable=variable, width=width, justify=justify)
        self.widgets.append(widget)
        self.entries[key] = widget
        widget.bind("<KeyRelease>", self._changed)
        widget.bind("<FocusOut>", self._changed_now)
        widget.bind("<Return>", self._changed_now)
        widget.bind("<MouseWheel>", self.owner._on_aux_mousewheel)
        return widget

    def _combo(self, variable: tk.StringVar, values: tuple[Any, ...], width: int) -> ttk.Combobox:
        widget = ttk.Combobox(self.parent, textvariable=variable, values=values, state="readonly", width=width, justify="center")
        self.widgets.append(widget)
        widget.bind("<<ComboboxSelected>>", self._changed_now)
        widget.bind("<MouseWheel>", self.owner._on_aux_mousewheel)
        return widget

    def _build(self) -> None:
        self._entry("name", self.name, 9, "left")
        self._entry("quantity", self.quantity, 5)
        self.series_combo = self._combo(self.series, ("HP", "SP"), 5)
        self.type_combo = self._combo(self.connection_type, AUX_TYPES, 7)
        self._entry("height", self.height, 8)
        self._entry("dimension", self.dimension, 9)
        self._combo(self.concrete, CONCRETES, 9)
        self._entry("m_pos", self.med_pos, 9)
        self._entry("m_neg", self.med_neg, 9)
        self._entry("n_pos", self.ned_pos, 9)
        self._entry("n_neg", self.ned_neg, 9)
        self._entry("v_pos", self.ved_pos, 9)
        self._entry("v_neg", self.ved_neg, 9)
        self._entry("h_parallel", self.hed_parallel, 9)
        self._entry("h_perp", self.hed_perp, 9)
        self._entry("x", self.load_x, 8)
        self.product_combo = ttk.Combobox(self.parent, textvariable=self.product, values=(), state="readonly", width=38, justify="left")
        self.widgets.append(self.product_combo)
        self.product_combo.bind("<<ComboboxSelected>>", self._product_changed)
        self.product_combo.bind("<MouseWheel>", self.owner._on_aux_mousewheel)
        self.widgets.append(ttk.Label(self.parent, textvariable=self.util, width=14, anchor="center", style="Card.TLabel"))
        self.widgets.append(ttk.Label(self.parent, textvariable=self.source, width=14, anchor="center", style="Card.TLabel"))
        self.status_label = ttk.Label(self.parent, textvariable=self.status, width=42, anchor="w", style="MutedCard.TLabel")
        self.widgets.append(self.status_label)
        self.widgets.append(ttk.Button(self.parent, text="×", width=3, command=lambda: self.owner.remove_aux_row(self)))
        self.type_combo.bind("<<ComboboxSelected>>", self._type_changed)
        self.series_combo.bind("<<ComboboxSelected>>", self._series_changed)
        self.regrid(self.row_no)

    def regrid(self, row_no: int) -> None:
        self.row_no = row_no
        for column, widget in enumerate(self.widgets):
            widget.grid(row=row_no, column=column, sticky="ew", padx=2, pady=2)

    def destroy(self) -> None:
        if self._after:
            try:
                self.owner.after_cancel(self._after)
            except Exception:
                pass
        for widget in self.widgets:
            try:
                widget.destroy()
            except Exception:
                pass

    def _mark_dirty(self) -> None:
        if not getattr(self.owner, "_action_loading", False) and hasattr(self.owner, "mark_project_dirty"):
            self.owner.mark_project_dirty()

    def _series_changed(self, _event: Any = None) -> None:
        if self.connection_type.get() == "HT":
            self.dimension.set(str(expected_ht_width_mm(self.series.get())))
        self._changed_now()

    def _type_changed(self, _event: Any = None) -> None:
        self.manual_product = False
        self._apply_type()
        self._changed_now()

    def _apply_type(self) -> None:
        typ = self.connection_type.get().strip().upper()
        mask = MASKS.get(typ, MASKS["HT"])
        for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg", "h_parallel", "h_perp"):
            widget = self.entries[key]
            widget.configure(state="normal" if mask.get(key) else "disabled",
                             style="HitEditable.TEntry" if mask.get(key) else "HitLocked.TEntry")
        if typ == "HT":
            self.dimension.set(str(expected_ht_width_mm(self.series.get())))
            self.entries["dimension"].configure(state="normal", style="HitEditable.TEntry")
        else:
            self.dimension.set("250")
            self.entries["dimension"].configure(state="disabled", style="HitLocked.TEntry")
        self.entries["x"].configure(
            state="normal" if typ == "OTX" else "disabled",
            style="HitEditable.TEntry" if typ == "OTX" else "HitLocked.TEntry",
        )

    def _changed(self, _event: Any = None) -> None:
        self.manual_product = False
        self.status.set("počítám…")
        self._mark_dirty()
        if self._after:
            try:
                self.owner.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.owner.after(300, self.recalculate)

    def _changed_now(self, _event: Any = None) -> None:
        self.manual_product = False
        self._mark_dirty()
        if self._after:
            try:
                self.owner.after_cancel(self._after)
            except Exception:
                pass
        self._after = None
        self.recalculate()

    def _effective(self) -> dict[str, str]:
        raw = {
            "m_pos": self.med_pos.get().strip(), "m_neg": self.med_neg.get().strip(),
            "n_pos": self.ned_pos.get().strip(), "n_neg": self.ned_neg.get().strip(),
            "v_pos": self.ved_pos.get().strip(), "v_neg": self.ved_neg.get().strip(),
            "h_parallel": self.hed_parallel.get().strip(), "h_perp": self.hed_perp.get().strip(),
        }
        mask = MASKS.get(self.connection_type.get().strip().upper(), {})
        return {key: (value if mask.get(key, False) else "") for key, value in raw.items()}

    def recalculate(self, preserve: str | None = None) -> None:
        self._after = None
        typ = self.connection_type.get().strip().upper()
        try:
            self.quantity.set(str(_qty(self.quantity.get())))
            height = int(self.height.get().strip())
            effective = self._effective()
            values = {key: _num(value) for key, value in effective.items()}
        except Exception as exc:
            self._error(str(exc) or "Neplatný číselný vstup.")
            return

        candidates: list[Candidate] = []
        error = ""
        info: dict[str, Any] = {}
        if typ == "HT":
            if max(values["h_parallel"], values["h_perp"]) <= 1e-9:
                self._waiting("čeká na HEd∥ / HEd⊥ [kN/prvek]")
                return
            candidates, error, info = design_ht_candidates(
                self.series.get(), height, self.concrete.get(),
                values["h_parallel"], values["h_perp"], self.dimension.get(),
            )
        else:
            if max(values["m_pos"], values["m_neg"], values["n_pos"], values["n_neg"], values["v_pos"], values["v_neg"]) <= 1e-9:
                self._waiting("čeká na návrhové účinky")
                return
            database = getattr(self.owner, "hit_db", None)
            if database is None:
                self._error("nejprve načtěte data HIT z DoP")
                return
            actions = DirectionalActions(
                m_pos=values["m_pos"], m_neg=values["m_neg"],
                n_pos=values["n_pos"], n_neg=values["n_neg"],
                v_pos=values["v_pos"], v_neg=values["v_neg"],
            )
            try:
                x = _num(self.load_x.get()) if typ == "OTX" else 0.0
                candidates, error, info = database.proposal_candidates(
                    typ, self.series.get(), height, 30, self.concrete.get(),
                    actions, {25}, False, load_distance_x=x,
                )
            except Exception as exc:
                error = str(exc)

        self.candidates = list(candidates)
        if error:
            self._error(error)
            return
        if not self.candidates:
            self._error(f"bez vyhovující varianty {typ}")
            return
        names = [candidate.designation for candidate in self.candidates]
        self.product_combo.configure(values=names)
        chosen = self.candidates[0]
        if preserve and preserve in names:
            chosen = self.candidates[names.index(preserve)]
        self.product.set(chosen.designation)
        self.manual_product = bool(preserve and preserve == chosen.designation and chosen is not self.candidates[0])
        self._show(chosen)
        self.owner.update_aux_status()

    def _show(self, candidate: Candidate) -> None:
        self.selected_candidate = candidate
        if candidate.spacing_max > 0:
            self.util.set("a max " + fmt(candidate.spacing_max, 3) + " m")
        else:
            self.util.set(fmt(candidate.utilization * 100.0) + " %")
        self.source.set(str(candidate.page))
        text = candidate.mode
        if self.manual_product:
            text += " • ručně zvoleno"
        if candidate.connection_type == "HT":
            text += f" • HRd∥ {fmt(candidate.m1)} / HRd⊥ {fmt(candidate.v1)} kN/prvek"
        else:
            text += " • specializovaný návrh dle tabulek M/N/V"
        self.status.set(text)
        self.status_label.configure(style="Good.TLabel")

    def _product_changed(self, _event: Any = None) -> None:
        value = self.product.get()
        for index, candidate in enumerate(self.candidates):
            if candidate.designation == value:
                self.manual_product = index != 0
                self._mark_dirty()
                self._show(candidate)
                self.owner.update_aux_status()
                return

    def _reset(self, text: str, style: str) -> None:
        self.candidates = []
        self.selected_candidate = None
        self.product_combo.configure(values=())
        self.product.set("—")
        self.util.set("—")
        self.source.set("—")
        self.status.set(text)
        self.status_label.configure(style=style)
        self.owner.update_aux_status()

    def _waiting(self, text: str) -> None:
        self._reset(text, "MutedCard.TLabel")

    def _error(self, text: str) -> None:
        self._reset(text, "Bad.TLabel")

    def payload(self) -> dict[str, Any]:
        effective = self._effective()
        return {
            "name": self.name.get().strip(),
            "quantity": _qty(self.quantity.get()),
            "series": self.series.get().strip(),
            "connection_type": self.connection_type.get().strip(),
            "height": self.height.get().strip(),
            "dimension": self.dimension.get().strip(),
            "required_length": self.dimension.get().strip(),
            "concrete": self.concrete.get().strip(),
            "med_pos": effective["m_pos"], "med_neg": effective["m_neg"],
            "ned_pos": effective["n_pos"], "ned_neg": effective["n_neg"],
            "ved_pos": effective["v_pos"], "ved_neg": effective["v_neg"],
            "hed_parallel": effective["h_parallel"], "hed_perp": effective["h_perp"],
            "load_x": self.load_x.get().strip() if self.connection_type.get() == "OTX" else "",
            "selected_designation": self.selected_candidate.designation if self.selected_candidate else "",
            "manual_product": bool(self.manual_product),
        }

    def report_row(self) -> dict[str, Any]:
        effective = self._effective()
        candidate = self.selected_candidate
        return {
            "group": "Doplňkové prvky",
            "name": self.name.get().strip() or f"D{self.row_no:03d}",
            "quantity": _qty(self.quantity.get()),
            "series": self.series.get().strip(),
            "connection_type": self.connection_type.get().strip(),
            "height_mm": self.height.get().strip(),
            "cover_mm": "" if self.connection_type.get() == "HT" else "30",
            "concrete": self.concrete.get().strip(),
            "required_length_mm": self.dimension.get().strip(),
            "actions": {
                "m_pos": effective["m_pos"], "m_neg": effective["m_neg"],
                "n_pos": effective["n_pos"], "n_neg": effective["n_neg"],
                "v_pos": effective["v_pos"], "v_neg": effective["v_neg"],
                "h_parallel": effective["h_parallel"], "h_perp": effective["h_perp"],
            },
            "candidate": _candidate_dict(candidate),
            "status": "VYHOVUJE" if candidate is not None else ("NELZE" if self.status.get().strip() not in {"", "čeká na návrhové účinky", "čeká na HEd∥ / HEd⊥ [kN/prvek]"} else "NEPOSOUZENO"),
            "detail": self.status.get().strip(),
            "notes": [self.status.get().strip()] if candidate is None and self.status.get().strip() else [],
        }


def install(base: Any) -> None:
    original_init = base.HitWorkspaceMixin._init_hit_workspace

    def init(self) -> None:
        original_init(self)
        self.aux_rows: list[AuxRow] = []
        self.aux_status_var = tk.StringVar(master=self, value="Doplňkové prvky: připraveno.")

    def build_aux(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        head = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Doplňkové prvky HIT", style="ProjectTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            head,
            text="HT používá HEd∥/HEd⊥ [kN/prvek]. AT/FT/OTX používají specializované M/N/V vstupy; OTX navíc vzdálenost x. Tyto prvky jsou záměrně mimo hlavní deskovou tabulku.",
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        bar = ttk.Frame(parent, style="App.TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        ttk.Button(bar, text="+ HT", style="Accent.TButton", command=lambda: self.add_aux_row_for_type("HT")).grid(row=0, column=0)
        ttk.Button(bar, text="+ AT", command=lambda: self.add_aux_row_for_type("AT")).grid(row=0, column=1, padx=(7, 0))
        ttk.Button(bar, text="+ FT", command=lambda: self.add_aux_row_for_type("FT")).grid(row=0, column=2, padx=(7, 0))
        ttk.Button(bar, text="+ OTX", command=lambda: self.add_aux_row_for_type("OTX")).grid(row=0, column=3, padx=(7, 0))
        ttk.Button(bar, text="Přepočítat vše", command=self.recalculate_aux_all).grid(row=0, column=4, padx=(14, 0))
        ttk.Button(bar, text="Vymazat vše", command=self.clear_aux_rows).grid(row=0, column=5, padx=(7, 0))
        ttk.Button(bar, text="Kopírovat tabulku", command=self.copy_aux_table).grid(row=0, column=6, padx=(14, 0))
        bar.columnconfigure(20, weight=1)
        ttk.Label(bar, textvariable=self.aux_status_var, style="Muted.TLabel").grid(row=0, column=20, sticky="e")

        card = ttk.Frame(parent, style="Card.TFrame", padding=(10, 10, 10, 8))
        card.grid(row=2, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        canvas = tk.Canvas(card, highlightthickness=0, background=self.colors["panel"])
        y = ttk.Scrollbar(card, orient="vertical", command=canvas.yview)
        x = ttk.Scrollbar(card, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame = ttk.Frame(canvas, style="Card.TFrame")
        window = canvas.create_window((0, 0), window=frame, anchor="nw")
        self.aux_canvas = canvas
        self.aux_rows_frame = frame
        self.aux_canvas_window = window
        for column, (_key, label, anchor) in enumerate(HEADERS):
            ttk.Label(
                frame, text=label, style="Card.TLabel",
                font=("Calibri", 10, "bold"), anchor=("w" if anchor == "w" else "center"),
            ).grid(row=0, column=column, sticky="ew", padx=2, pady=(0, 5))
            frame.columnconfigure(column, weight=1 if anchor == "w" else 0)
        frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=max(e.width, frame.winfo_reqwidth())))
        canvas.bind("<MouseWheel>", self._on_aux_mousewheel)
        ttk.Label(
            parent,
            text="HT je samostatný přenos vodorovných sil. AT/FT/OTX používají katalogové interakční/tabulkové postupy a pevnou délku 250 mm; OTX vyžaduje x. Export PDF nahoře v kartě Návrh HIT zahrnuje tuto tabulku, desky/balkony i WT.",
            style="Muted.TLabel", wraplength=1500, justify="left",
        ).grid(row=3, column=0, sticky="ew", pady=(8, 0))
        if not self.aux_rows:
            self.add_aux_row_for_type("HT", mark_dirty=False)

    def wheel(self, event: Any) -> str:
        delta = int(getattr(event, "delta", 0) or 0)
        if delta and hasattr(self, "aux_canvas"):
            self.aux_canvas.yview_scroll(-1 if delta > 0 else 1, "units")
        return "break"

    def add(self, typ: str = "HT", defaults: dict[str, Any] | None = None, *, mark_dirty: bool = True):
        values = dict(defaults or {})
        values["connection_type"] = str(values.get("connection_type") or typ).upper()
        if values["connection_type"] not in AUX_TYPES:
            raise ValueError(f"{values['connection_type']} není doplňkový typ HIT.")
        row = AuxRow(self, self.aux_rows_frame, len(self.aux_rows) + 1, values)
        self.aux_rows.append(row)
        if mark_dirty and not getattr(self, "_action_loading", False) and hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.update_aux_status()
        return row

    def remove(self, row: AuxRow) -> None:
        if row not in self.aux_rows:
            return
        row.destroy()
        self.aux_rows.remove(row)
        for index, item in enumerate(self.aux_rows, 1):
            item.regrid(index)
        if not getattr(self, "_action_loading", False) and hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.update_aux_status()

    def clear(self, *, mark_dirty: bool = True) -> None:
        for row in list(self.aux_rows):
            row.destroy()
        self.aux_rows.clear()
        if mark_dirty and not getattr(self, "_action_loading", False) and hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.update_aux_status()

    def recalc(self) -> None:
        for row in list(self.aux_rows):
            row.recalculate(preserve=row.product.get() if row.manual_product else None)
        self.update_aux_status()

    def status(self) -> None:
        if not hasattr(self, "aux_status_var"):
            return
        ok = sum(1 for row in self.aux_rows if row.selected_candidate is not None)
        qty = sum(_qty(row.quantity.get()) for row in self.aux_rows) if self.aux_rows else 0
        self.aux_status_var.set(f"{len(self.aux_rows)} řádků • {qty} ks • {ok} s návrhem")

    def serialize(self) -> dict[str, Any]:
        return {"schema_version": 1, "rows": [row.payload() for row in self.aux_rows]}

    def load(self, payload: dict[str, Any] | None) -> None:
        self.clear_aux_rows(mark_dirty=False)
        raw_rows = payload.get("rows") if isinstance(payload, dict) else []
        if not isinstance(raw_rows, list):
            raw_rows = []
        for raw in raw_rows:
            if isinstance(raw, dict):
                self.add_aux_row_for_type(str(raw.get("connection_type", "HT")), raw, mark_dirty=False)
        if not self.aux_rows and getattr(self, "_hit_built", False):
            self.add_aux_row_for_type("HT", mark_dirty=False)
        self.update_aux_status()

    def import_defaults(self, defaults: list[dict[str, Any]]) -> list[AuxRow]:
        created: list[AuxRow] = []
        blank_only = (
            len(self.aux_rows) == 1
            and self.aux_rows[0].connection_type.get() == "HT"
            and all(
                not getattr(self.aux_rows[0], attr).get().strip()
                for attr in ("hed_parallel", "hed_perp", "med_pos", "med_neg", "ned_pos", "ned_neg", "ved_pos", "ved_neg", "load_x")
            )
        )
        if blank_only:
            self.clear_aux_rows(mark_dirty=False)
        for raw in defaults:
            typ = str(raw.get("connection_type", "")).upper()
            if typ not in AUX_TYPES:
                continue
            values = {
                "name": raw.get("name", ""),
                "quantity": raw.get("quantity", 1),
                "series": raw.get("series", "HP"),
                "connection_type": typ,
                "height": raw.get("height", "200"),
                "dimension": raw.get("required_length", raw.get("dimension", "")),
                "concrete": raw.get("concrete", "C25/30"),
                "med_pos": raw.get("med_pos", ""), "med_neg": raw.get("med_neg", ""),
                "ned_pos": raw.get("ned_pos", ""), "ned_neg": raw.get("ned_neg", ""),
                "ved_pos": raw.get("ved_pos", ""), "ved_neg": raw.get("ved_neg", ""),
                "hed_parallel": raw.get("hed_parallel", ""), "hed_perp": raw.get("hed_perp", ""),
                "load_x": raw.get("load_x", ""),
            }
            created.append(self.add_aux_row_for_type(typ, values, mark_dirty=False))
        if created and hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.update_aux_status()
        return created

    def copy_table(self) -> None:
        lines = ["\t".join(label for _key, label, _anchor in HEADERS[:-1])]
        for row in self.aux_rows:
            values = [
                row.name.get(), row.quantity.get(), row.series.get(), row.connection_type.get(),
                row.height.get(), row.dimension.get(), row.concrete.get(),
                row.med_pos.get(), row.med_neg.get(), row.ned_pos.get(), row.ned_neg.get(),
                row.ved_pos.get(), row.ved_neg.get(), row.hed_parallel.get(), row.hed_perp.get(),
                row.load_x.get(), row.product.get(), row.util.get(), row.source.get(), row.status.get(),
            ]
            lines.append("\t".join(str(value) for value in values))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.update_aux_status()

    base.HitWorkspaceMixin._build_aux_tab = build_aux
    base.HitWorkspaceMixin._on_aux_mousewheel = wheel
    base.HitWorkspaceMixin.add_aux_row_for_type = add
    base.HitWorkspaceMixin.remove_aux_row = remove
    base.HitWorkspaceMixin.clear_aux_rows = clear
    base.HitWorkspaceMixin.recalculate_aux_all = recalc
    base.HitWorkspaceMixin.update_aux_status = status
    base.HitWorkspaceMixin.serialize_aux_design = serialize
    base.HitWorkspaceMixin.load_aux_design = load
    base.HitWorkspaceMixin.import_aux_defaults = import_defaults
    base.HitWorkspaceMixin.copy_aux_table = copy_table
    base.HitWorkspaceMixin._collect_aux_pdf_rows = lambda self: [row.report_row() for row in self.aux_rows]
    base.HitWorkspaceMixin._init_hit_workspace = init
