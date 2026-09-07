from __future__ import annotations

"""Unified schedule import for the thermal-break design domain in TURTO 2.0.

One pasted schedule is classified into slab/balcony, supplementary and WT rows.
The implementation intentionally reuses the verified 1.1.22/1.1.27 parser for
ordinary M/V and HT rows; only WT and explicitly named AT/FT/OTX rows need a
small specialized parser because their inputs are different.
"""

from dataclasses import dataclass, field
import math
import re
import unicodedata
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

import hit_schedule_127 as _legacy
from hit_aux_ui import AUX_TYPES

_QTY_RE = re.compile(r"^\s*(\d+)\s*(?:ks|kus(?:y|ů)?)?\s*$", re.I)
_NUM = r"[+-]?\s*(?:\d{1,3}(?:[ ]\d{3})+|\d+)(?:[.,]\d+)?"


@dataclass
class RoutedRecord:
    line: int
    source: str
    target: str
    type_name: str
    quantity: int = 1
    payload: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).replace("−", "-").replace("–", "-")
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return value.lower()


def _number(text: Any) -> float:
    value = float(str(text).replace(" ", "").replace(",", "."))
    if not math.isfinite(value) or abs(value) > 1e9:
        raise ValueError("Číslo je mimo podporovaný rozsah.")
    return abs(value)


def _text_number(value: float) -> str:
    return format(float(value), ".12g").replace(".", ",")


def _split_quantity(raw: str) -> tuple[str, int] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if "|" in text:
        cells = [cell.strip() for cell in text.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"[\s:=-]+", cells[0] or ""):
            return None
        if len(cells) >= 2:
            match = _QTY_RE.fullmatch(cells[-1])
            if match:
                return " | ".join(cells[:-1]).strip(), int(match.group(1))
    if "\t" in text:
        cells = [cell.strip() for cell in text.split("\t")]
        if len(cells) >= 2:
            match = _QTY_RE.fullmatch(cells[-1])
            if match:
                return "\t".join(cells[:-1]).strip(), int(match.group(1))
    return text.strip("|").strip(), 1


def _explicit_series(source: str, fallback: str) -> str:
    upper = source.upper()
    if re.search(r"\bSP\b|HIT-SP", upper):
        return "SP"
    if re.search(r"\bHP\b|HIT-HP", upper):
        return "HP"
    return fallback


def _extract_dimension(source: str, labels: tuple[str, ...], default: int) -> int:
    text = _norm(source)
    label = "(?:" + "|".join(labels) + ")"
    match = re.search(rf"\b{label}\s*(?:=|:)?\s*({_NUM})\s*mm\b", text, re.I)
    if not match:
        return int(default)
    return int(round(_number(match.group(1))))


def _find_action(source: str, pattern: str, expected_unit: str) -> tuple[str, str | None]:
    text = _norm(source)
    match = re.search(pattern + rf"\s*(?:=|:)\s*({_NUM})\s*([^,;|]*)", text, re.I)
    if not match:
        return "", None
    value = _text_number(_number(match.group(1)))
    tail = str(match.group(2) or "").strip().replace("·", "").replace(" ", "")
    expected = expected_unit.lower().replace(" ", "")
    if expected not in tail:
        return value, f"Očekávána jednotka {expected_unit}."
    return value, None


def _parse_wt(source: str, quantity: int, common: dict[str, str], name: str, line: int) -> RoutedRecord:
    record = RoutedRecord(line, source, "wt", "WT", quantity)
    try:
        wall_h = _extract_dimension(source, (r"h(?:\s*steny)?", r"vyska(?:\s*steny)?"), int(common["wt_height"]))
        width = _extract_dimension(source, ("b", "sirka"), int(common["wt_width"]))
        series = _explicit_series(source, common["series"])
        med, err_m = _find_action(source, r"\bm\s*_?\s*ed\s*-", "kNm/prvek")
        vv, err_vv = _find_action(source, r"\bv\s*_?\s*ed\s*[,._-]?\s*v\s*\+?", "kN/prvek")
        vh, err_vh = _find_action(source, r"\bv\s*_?\s*ed\s*[,._-]?\s*h\s*(?:±|\+/-|\+-)?", "kN/prvek")
        for err in (err_m, err_vv, err_vh):
            if err:
                record.errors.append(err)
        if not any((med, vv, vh)):
            record.errors.append("WT: zadejte alespoň MEd−, VEd,v+ nebo VEd,h± v jednotkách na prvek.")
        record.payload = {
            "name": name,
            "quantity": str(quantity),
            "series": series,
            "wall_height": str(wall_h),
            "width": str(width),
            "concrete": common["concrete"],
            "med_neg": med,
            "ved_vertical": vv,
            "ved_horizontal": vh,
            "selected_designation": "",
            "manual_product": False,
            "import_source_text": source,
        }
    except Exception as exc:
        record.errors.append(str(exc))
    return record


def _parse_special(source: str, quantity: int, common: dict[str, str], name: str, line: int, typ: str) -> RoutedRecord:
    record = RoutedRecord(line, source, "aux", typ, quantity)
    try:
        height = _extract_dimension(source, ("h", "vyska"), int(common["height"]))
        series = _explicit_series(source, common["series"])
        patterns = {
            "med_pos": (r"\bm\s*_?\s*ed\s*\+", "kNm/m"),
            "med_neg": (r"\bm\s*_?\s*ed\s*-", "kNm/m"),
            "ned_pos": (r"\bn\s*_?\s*ed\s*\+", "kN/m"),
            "ned_neg": (r"\bn\s*_?\s*ed\s*-", "kN/m"),
            "ved_pos": (r"\bv\s*_?\s*ed\s*\+", "kN/m"),
            "ved_neg": (r"\bv\s*_?\s*ed\s*-", "kN/m"),
        }
        actions: dict[str, str] = {}
        for key, (pattern, unit) in patterns.items():
            value, error = _find_action(source, pattern, unit)
            actions[key] = value
            if error:
                record.errors.append(f"{key}: {error}")
        x = ""
        if typ == "OTX":
            match = re.search(rf"\bx\s*(?:=|:)\s*({_NUM})\s*mm\b", _norm(source), re.I)
            if match:
                x = _text_number(_number(match.group(1)))
        if not any(actions.values()):
            record.errors.append(f"{typ}: chybí návrhové účinky MEd / NEd / VEd.")
        record.payload = {
            "name": name,
            "quantity": str(quantity),
            "series": series,
            "connection_type": typ,
            "height": str(height),
            "dimension": "250",
            "required_length": "250",
            "concrete": common["concrete"],
            "load_x": x,
            "selected_designation": "",
            "manual_product": False,
            **actions,
        }
    except Exception as exc:
        record.errors.append(str(exc))
    return record


def _parse_legacy(source_with_quantity: str, common: dict[str, str], name: str, line: int) -> list[RoutedRecord]:
    out: list[RoutedRecord] = []
    try:
        records = _legacy.parse_schedule(source_with_quantity)
    except Exception as exc:
        return [RoutedRecord(line, source_with_quantity, "standard", "?", 1, errors=[str(exc)])]
    if not records:
        return [RoutedRecord(line, source_with_quantity, "standard", "?", 1, errors=["Řádek nebyl rozpoznán."])]
    options = {
        "height": common["height"],
        "cover": common["cover"],
        "concrete": common["concrete"],
        "series": common["series"],
        "bending": common["bending"],
        "shear": common["shear"],
        "moment": common["moment"],
    }
    for parsed in records:
        quantity = int(getattr(parsed, "quantity", 1) or 1)
        item = RoutedRecord(line, str(getattr(parsed, "source", source_with_quantity)), "standard", "?", quantity)
        try:
            payload = _legacy.row_defaults(parsed, options, name)
            typ = str(payload.get("connection_type", "") or "").upper()
            item.type_name = typ
            item.target = "aux" if typ in AUX_TYPES else "standard"
            item.payload = payload
        except Exception as exc:
            item.errors.append(str(exc))
        out.append(item)
    return out


def route_schedule(text: str, common: dict[str, str], existing_names: set[str]) -> list[RoutedRecord]:
    result: list[RoutedRecord] = []
    counters = {"standard": 1, "aux": 1, "wt": 1}

    def next_name(target: str) -> str:
        prefix = {"standard": "N", "aux": "D", "wt": "W"}[target]
        value = counters[target]
        while f"{prefix}{value:03d}" in existing_names:
            value += 1
        counters[target] = value + 1
        name = f"{prefix}{value:03d}"
        existing_names.add(name)
        return name

    for lineno, raw in enumerate(str(text).splitlines(), 1):
        split = _split_quantity(raw)
        if split is None:
            continue
        source, quantity = split
        normalized = _norm(source)
        if re.search(r"\bwt(?:\b|-)|stenov", normalized):
            result.append(_parse_wt(source, quantity, common, next_name("wt"), lineno))
            continue
        explicit = ""
        for typ in ("OTX", "AT", "FT"):
            if re.search(rf"\b{typ}\b", source.upper()):
                explicit = typ
                break
        if explicit:
            result.append(_parse_special(source, quantity, common, next_name("aux"), lineno, explicit))
            continue
        encoded = source + "\t" + str(quantity)
        temporary_name = next_name("standard")
        routed = _parse_legacy(encoded, common, temporary_name, lineno)
        for item in routed:
            if item.target == "aux":
                old_name = item.payload.get("name") if isinstance(item.payload, dict) else None
                new_name = next_name("aux")
                if isinstance(item.payload, dict):
                    item.payload["name"] = new_name
                if old_name:
                    existing_names.discard(str(old_name))
            result.append(item)
    return result


class UnifiedScheduleDialog(tk.Toplevel):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.title("Výkaz → návrh izolačních nosníků")
        self.geometry("1260x780")
        self.minsize(980, 650)
        self.transient(owner)
        self.grab_set()
        self.configure(background=owner.colors["bg"])
        self.records: list[RoutedRecord] = []
        self.included: set[int] = set()
        self.ack = tk.BooleanVar(master=self, value=False)
        self.replace = tk.BooleanVar(master=self, value=False)
        self.vars = {
            "height": tk.StringVar(master=self, value="200"),
            "cover": tk.StringVar(master=self, value="35"),
            "concrete": tk.StringVar(master=self, value="C25/30"),
            "series": tk.StringVar(master=self, value="HP"),
            "bending": tk.StringVar(master=self, value="MVX"),
            "shear": tk.StringVar(master=self, value="ZVX"),
            "moment": tk.StringVar(master=self, value="MEd− (konzola)"),
            "wt_height": tk.StringVar(master=self, value="1500"),
            "wt_width": tk.StringVar(master=self, value="150"),
        }
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self, style="App.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)
        ttk.Label(outer, text="Jeden výkaz → automatické rozřazení", style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text="Řádky se rozdělí do Desky / balkony, Doplňkové prvky a Stěny WT. Výrobce návrhu: Leviat (aktivní adaptér HIT).",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 8))
        source = ttk.Frame(outer, style="App.TFrame")
        source.grid(row=2, column=0, sticky="ew")
        source.columnconfigure(0, weight=1)
        self.text = tk.Text(source, height=6, wrap="none", undo=True, font=("Calibri", 11), background=self.owner.colors["panel"], foreground=self.owner.colors["text"], insertbackground=self.owner.colors["text"])
        self.text.grid(row=0, column=0, sticky="ew")
        y = ttk.Scrollbar(source, orient="vertical", command=self.text.yview)
        y.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=y.set)
        actions = ttk.Frame(outer, style="App.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(6, 8))
        ttk.Button(actions, text="Vložit ze schránky", command=self.paste).pack(side="left")
        ttk.Button(actions, text="Načíst / obnovit náhled", command=self.analyze).pack(side="left", padx=(6, 0))
        params = ttk.LabelFrame(outer, text="Výchozí parametry pro řádky, které je nemají uvedené", padding=8)
        params.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        specs = (
            ("height", "h desky [mm]", tuple(str(v) for v in range(160, 401, 10))),
            ("cover", "cnom [mm]", ("30", "35", "50")),
            ("concrete", "Beton", ("C20/25", "C25/30", "C30/37")),
            ("series", "Řada", ("HP", "SP")),
            ("bending", "Ohybové →", ("MVX", "MVXL", "DD", "DVL", "DDL")),
            ("shear", "Smykové →", ("ZVX", "ZDX")),
            ("wt_height", "WT h stěny [mm]", tuple(str(v) for v in range(1000, 3501, 250))),
            ("wt_width", "WT B [mm]", tuple(str(v) for v in range(150, 251, 10))),
        )
        for index, (key, label, values) in enumerate(specs):
            row, col = divmod(index, 4)
            ttk.Label(params, text=label).grid(row=row * 2, column=col, sticky="w", padx=5, pady=(2, 0))
            ttk.Combobox(params, textvariable=self.vars[key], values=values, state="readonly", width=18).grid(row=row * 2 + 1, column=col, sticky="ew", padx=5, pady=(2, 5))
            params.columnconfigure(col, weight=1)
        box = ttk.Frame(outer, style="Card.TFrame")
        box.grid(row=5, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        columns = ("use", "line", "target", "position", "qty", "type", "source", "check")
        self.tree = ttk.Treeview(box, columns=columns, show="headings", selectmode="extended", style="Data.Treeview")
        headings = {
            "use": ("✓", 34, "center"), "line": ("Ř.", 44, "center"),
            "target": ("Cíl", 145, "w"), "position": ("Pozice", 70, "center"),
            "qty": ("Ks", 52, "center"), "type": ("Typ", 76, "center"),
            "source": ("Původní řádek", 430, "w"), "check": ("Kontrola", 300, "w"),
        }
        for key, (label, width, anchor) in headings.items():
            self.tree.heading(key, text=label, anchor=anchor)
            self.tree.column(key, width=width, minwidth=34, anchor=anchor, stretch=key in {"source", "check"})
        self.tree.grid(row=0, column=0, sticky="nsew")
        sy = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        sx = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.tag_configure("error", foreground=self.owner.colors.get("danger", "#a02020"))
        row_actions = ttk.Frame(outer, style="App.TFrame")
        row_actions.grid(row=6, column=0, sticky="ew", pady=(8, 4))
        ttk.Button(row_actions, text="Zahrnout označené", command=lambda: self.include(True)).pack(side="left")
        ttk.Button(row_actions, text="Vynechat označené", command=lambda: self.include(False)).pack(side="left", padx=(6, 0))
        self.summary = tk.StringVar(master=self, value="Vložte výkaz a načtěte náhled.")
        ttk.Label(row_actions, textvariable=self.summary, style="Muted.TLabel").pack(side="right")
        ttk.Checkbutton(outer, text="Potvrzuji rozřazení, směry účinků a jednotky podle skutečného zadání.", variable=self.ack).grid(row=7, column=0, sticky="w", pady=(3, 0))
        ttk.Checkbutton(outer, text="Nahradit dosavadní návrh ve všech třech skupinách (jinak připojit)", variable=self.replace).grid(row=8, column=0, sticky="w")
        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bottom, text="Zrušit", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Přidat do návrhu", style="Accent.TButton", command=self.commit).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda _e: self.destroy())
        try:
            from ui_utils import place_dialog_on_parent
            self.update_idletasks()
            place_dialog_on_parent(self, self.owner)
        except Exception:
            pass

    def paste(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Schránka", "Schránka neobsahuje text.", parent=self)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.analyze()

    def analyze(self) -> None:
        common = {key: var.get() for key, var in self.vars.items()}
        common["moment"] = "MEd− (konzola)"
        existing = {str(row.name.get()).strip() for collection in (getattr(self.owner, "hit_rows", []), getattr(self.owner, "aux_rows", []), getattr(self.owner, "wt_rows", [])) for row in collection if hasattr(row, "name")}
        self.records = route_schedule(self.text.get("1.0", "end-1c"), common, existing)
        self.included = set(range(len(self.records)))
        self.ack.set(False)
        self.render()

    def render(self) -> None:
        self.tree.delete(*self.tree.get_children(""))
        errors = 0
        target_label = {"standard": "Desky / balkony", "aux": "Doplňkové prvky", "wt": "Stěny WT"}
        quantities = 0
        for index, record in enumerate(self.records):
            if index in self.included:
                quantities += record.quantity
                if record.errors:
                    errors += 1
            payload = record.payload or {}
            position = str(payload.get("name", "") or "")
            check = "Připraveno" if not record.errors else " • ".join(record.errors)
            self.tree.insert("", "end", iid=str(index), tags=("error",) if record.errors else (), values=("✓" if index in self.included else "—", record.line, target_label.get(record.target, record.target), position, record.quantity, record.type_name, record.source, check))
        self.summary.set(f"{len(self.included)} z {len(self.records)} řádků • {quantities} ks • {errors} chyb v zahrnutých řádcích")

    def include(self, include: bool) -> None:
        selected = {int(iid) for iid in self.tree.selection() if str(iid).isdigit()}
        if include:
            self.included.update(selected)
        else:
            self.included.difference_update(selected)
        self.render()

    def commit(self) -> None:
        if not self.records:
            messagebox.showinfo("Není co vložit", "Nejprve načtěte náhled výkazu.", parent=self)
            return
        if not self.included:
            messagebox.showinfo("Není co vložit", "Zahrňte alespoň jeden řádek.", parent=self)
            return
        bad = [index for index in sorted(self.included) if self.records[index].errors or not self.records[index].payload]
        if bad:
            iid = str(bad[0])
            try:
                self.tree.selection_set(iid); self.tree.focus(iid); self.tree.see(iid)
            except Exception:
                pass
            messagebox.showwarning("Výkaz obsahuje chybu", f"{len(bad)} zahrnutých řádků není připraveno. První problematický řádek je označen.", parent=self)
            return
        if not self.ack.get():
            messagebox.showwarning("Potvrďte výkaz", "Zaškrtněte potvrzení rozřazení, směrů a jednotek.", parent=self)
            return
        replace = bool(self.replace.get())
        if replace and any((getattr(self.owner, "hit_rows", []), getattr(self.owner, "aux_rows", []), getattr(self.owner, "wt_rows", []))):
            if not messagebox.askyesno("Nahradit celý návrh", "Nahradit dosavadní řádky Desky / balkony, Doplňkové prvky i Stěny WT?", parent=self):
                return
        standard = [dict(self.records[i].payload) for i in sorted(self.included) if self.records[i].target == "standard" and isinstance(self.records[i].payload, dict)]
        aux = [dict(self.records[i].payload) for i in sorted(self.included) if self.records[i].target == "aux" and isinstance(self.records[i].payload, dict)]
        wt = [dict(self.records[i].payload) for i in sorted(self.included) if self.records[i].target == "wt" and isinstance(self.records[i].payload, dict)]
        try:
            if replace:
                if hasattr(self.owner, "clear_aux_rows"):
                    self.owner.clear_aux_rows(mark_dirty=False)
                if hasattr(self.owner, "clear_wt_rows"):
                    self.owner.clear_wt_rows(mark_dirty=False)
                if not standard and hasattr(self.owner, "clear_hit_rows"):
                    self.owner.clear_hit_rows()
            created_standard = []
            if standard:
                installer = _legacy._prev._prev.install_rows
                created_standard = installer(self.owner, standard, replace)
            created_aux = self.owner.import_aux_defaults(aux) if aux else []
            created_wt = [self.owner.add_wt_row(payload) for payload in wt]
            for name in ("_hit_reconfigure_row_minsizes", "_hit_schedule_virtual_refresh", "_hit_schedule_scrollregion"):
                method = getattr(self.owner, name, None)
                if callable(method):
                    method()
            if hasattr(self.owner, "mark_project_dirty"):
                self.owner.mark_project_dirty()
            self.owner.update_idletasks()
        except Exception as exc:
            messagebox.showerror("Import návrhu", f"Import se nezdařil.\n\n{exc}", parent=self)
            return
        counts = (len(created_standard), len(created_aux), len(created_wt))
        total = sum(counts)
        quantity = sum(self.records[i].quantity for i in self.included)
        try:
            self.owner.set_status(f"Výkaz rozřazen: {total} řádků / {quantity} ks • desky {counts[0]} • doplňky {counts[1]} • WT {counts[2]}. Uložte AKCI.")
            notebook = getattr(self.owner, "hit_design_notebook", None)
            if notebook is not None:
                if counts[0] and hasattr(self.owner, "hit_standard_tab"):
                    notebook.select(self.owner.hit_standard_tab)
                elif counts[1] and hasattr(self.owner, "hit_aux_tab"):
                    notebook.select(self.owner.hit_aux_tab)
                elif counts[2] and hasattr(self.owner, "hit_wt_tab"):
                    notebook.select(self.owner.hit_wt_tab)
        except Exception:
            pass
        self.destroy()


def open_unified_schedule(owner: Any) -> None:
    dialog = UnifiedScheduleDialog(owner)
    owner.wait_window(dialog)
