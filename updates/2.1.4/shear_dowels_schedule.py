from __future__ import annotations

"""Hromadné vložení smykových trnů z textového výkazu.

Dialog záměrně používá stejný model jako hromadné vložení izolačních nosníků:
text ze schránky -> kontrolní náhled -> vložení pouze rozpoznaných řádků.
"""

from dataclasses import dataclass
import re
from typing import Any, Callable

import tkinter as tk
from tkinter import messagebox, ttk

from ui_utils import place_dialog_on_parent


_NUM = r"[+-]?\s*(?:\d+(?:[.,]\d+)?)"
_QTY_RE = re.compile(r"^\s*(\d+)\s*(?:ks|kus(?:y|ů)?)?\s*$", re.I)
_MARKDOWN_RE = re.compile(r"^[\s|:\-]+$")
_CONCRETE_RE = re.compile(r"\bC\s*(25\s*/\s*30|30\s*/\s*37|35\s*/\s*45|40\s*/\s*50)\b", re.I)


@dataclass
class ScheduleItem:
    line: int
    source: str
    name: str
    quantity: int
    values: dict[str, Any]
    result: str = ""
    error: str = ""


def _num(text: Any) -> float:
    return float(str(text).strip().replace(" ", "").replace(",", ".").replace("−", "-"))


def _cells(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text or _MARKDOWN_RE.fullmatch(text):
        return []
    if "|" in text:
        return [x.strip() for x in text.strip().strip("|").split("|") if x.strip()]
    if "\t" in text:
        return [x.strip() for x in text.split("\t") if x.strip()]
    if ";" in text:
        return [x.strip() for x in text.split(";") if x.strip()]
    return [text]


def _looks_position(text: str) -> bool:
    value = str(text or "").strip()
    if not value or len(value) > 18:
        return False
    if re.fullmatch(r"\d+(?:[.,]\d+)?", value):
        return False
    return bool(re.fullmatch(r"[A-Za-zÁ-ž][A-Za-zÁ-ž0-9_.\-/]*", value))


def _position_qty_content(raw: str, default_name: str) -> tuple[str, int, str]:
    cells = _cells(raw)
    if not cells:
        return default_name, 1, ""

    name = default_name
    qty = 1
    content_cells = list(cells)

    if len(content_cells) >= 3 and _looks_position(content_cells[0]) and _QTY_RE.fullmatch(content_cells[1]):
        name = content_cells.pop(0)
        qty = int(_QTY_RE.fullmatch(content_cells.pop(0)).group(1))
    elif len(content_cells) >= 2 and _looks_position(content_cells[0]):
        name = content_cells.pop(0)

    if len(content_cells) >= 2:
        last_qty = _QTY_RE.fullmatch(content_cells[-1])
        if last_qty:
            qty = int(last_qty.group(1))
            content_cells.pop()

    content = " | ".join(content_cells).strip()
    inline = re.match(r"^\s*(\d+)\s*[x×]\s+(.+)$", content, re.I)
    if inline:
        qty = int(inline.group(1))
        content = inline.group(2).strip()
    return name, qty, content


def _inline_geometry(raw: str, defaults: dict[str, str]) -> dict[str, str]:
    text = str(raw or "")
    out = dict(defaults)

    mh = re.search(rf"\bh\s*(?:=|:)?\s*({_NUM})\s*mm\b", text, re.I)
    if mh:
        out["slab"] = str(int(round(abs(_num(mh.group(1))))))

    mg = re.search(rf"\b(?:sp[aá]ra|gap|joint)\s*(?:=|:)?\s*({_NUM})\s*mm\b", text, re.I)
    if mg:
        out["gap"] = str(int(round(abs(_num(mg.group(1))))))

    mc = _CONCRETE_RE.search(text)
    if mc:
        out["concrete"] = "C" + mc.group(1).replace(" ", "")

    mcover = re.search(rf"\bcnom\s*(?:=|:)?\s*({_NUM})\s*mm\b", text, re.I)
    if mcover:
        value = int(round(abs(_num(mcover.group(1)))))
        out["cover"] = "20" if value <= 20 else "30"

    lowered = text.lower()
    if any(token in lowered for token in ("příčný", "pricny", "transverse", "boční", "bocni")):
        out["movement"] = "Podélný + příčný posun"
    if any(token in lowered for token in ("stávající", "stavajici", "existing")):
        out["application"] = "Stávající betonová stěna"
    if "plast" in lowered:
        out["sleeve"] = "Plastová objímka"
    return out


def _best_designation(content: str, raw: str, decoder: Callable[[str], Any]) -> tuple[str, Any]:
    candidates: list[str] = []
    for value in (content, raw):
        value = str(value or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    for cell in reversed(_cells(raw)):
        if cell not in candidates:
            candidates.append(cell)

    for candidate in candidates:
        try:
            info = decoder(candidate)
        except Exception:
            info = None
        if info:
            return candidate, info
    return content.strip(), None


def _extract_ved(content: str, raw: str) -> float | None:
    text = str(raw or "")
    match = re.search(
        rf"\bV\s*[_ ]?\s*Ed(?:\s*[+\-])?\s*(?:=|:)?\s*({_NUM})\s*(?:kN(?:\s*/\s*(?:trn|prvek|ks))?)?",
        text,
        re.I,
    )
    if match:
        return abs(_num(match.group(1)))

    content_text = str(content or "").strip()
    if re.fullmatch(_NUM, content_text):
        return abs(_num(content_text))

    cells = _cells(content)
    for cell in cells:
        if re.fullmatch(_NUM, cell):
            try:
                return abs(_num(cell))
            except Exception:
                continue
    return None


def parse_decoder_schedule(
    text: str,
    *,
    decoder: Callable[[str], Any],
    defaults: dict[str, str],
    existing_names: set[str],
) -> list[ScheduleItem]:
    rows: list[ScheduleItem] = []
    next_index = 1

    def next_name() -> str:
        nonlocal next_index
        while f"S{next_index:03d}" in existing_names:
            next_index += 1
        name = f"S{next_index:03d}"
        existing_names.add(name)
        next_index += 1
        return name

    for lineno, raw in enumerate(str(text or "").splitlines(), 1):
        if not _cells(raw):
            continue
        name, qty, content = _position_qty_content(raw, next_name())
        geometry = _inline_geometry(raw, defaults)
        designation, info = _best_designation(content, raw, decoder)
        item = ScheduleItem(
            lineno,
            raw,
            name,
            qty,
            {
                "designation": designation,
                "slab_mm": float(geometry["slab"]),
                "gap_mm": float(geometry["gap"]),
                "concrete": geometry["concrete"],
                "cover_mm": int(geometry["cover"]),
            },
        )
        if not info:
            item.error = "Označení nebylo rozpoznáno."
        else:
            item.values.update(
                {
                    "manufacturer": info.get("manufacturer", ""),
                    "family": info.get("family", ""),
                    "size": info.get("size", ""),
                    "movement": info.get("movement", "axial"),
                }
            )
            item.result = f"{info.get('manufacturer','')} • {info.get('family','')} {info.get('size','')}".strip()
        rows.append(item)
    return rows


def parse_design_schedule(
    text: str,
    *,
    design: Callable[..., Any],
    defaults: dict[str, str],
    existing_names: set[str],
) -> list[ScheduleItem]:
    rows: list[ScheduleItem] = []
    next_index = 1

    def next_name() -> str:
        nonlocal next_index
        while f"N{next_index:03d}" in existing_names:
            next_index += 1
        name = f"N{next_index:03d}"
        existing_names.add(name)
        next_index += 1
        return name

    for lineno, raw in enumerate(str(text or "").splitlines(), 1):
        if not _cells(raw):
            continue
        name, qty, content = _position_qty_content(raw, next_name())
        geometry = _inline_geometry(raw, defaults)
        ved = _extract_ved(content, raw)
        values = {
            "ved": ved,
            "slab_mm": float(geometry["slab"]),
            "gap_mm": float(geometry["gap"]),
            "concrete": geometry["concrete"],
            "movement": "transverse" if "příčný" in geometry["movement"].lower() else "axial",
            "application": "existing_wall" if "stávající" in geometry["application"].lower() else "new",
            "low_sleeve": "plastic" if "plast" in geometry["sleeve"].lower() else "stainless",
        }
        item = ScheduleItem(lineno, raw, name, qty, values)
        if ved is None:
            item.error = "Chybí VEd. Použijte např. „VEd = 90 kN/trn“."
            rows.append(item)
            continue
        try:
            candidates, error = design(
                ved=ved,
                slab_mm=values["slab_mm"],
                gap_mm=values["gap_mm"],
                concrete=values["concrete"],
                movement=values["movement"],
                application=values["application"],
                low_sleeve=values["low_sleeve"],
            )
        except Exception as exc:
            candidates, error = [], str(exc)
        if not candidates:
            item.error = error or "Nenalezen vyhovující trn."
        else:
            candidate = candidates[0]
            item.values["candidate"] = candidate.as_dict()
            item.result = (
                f"{candidate.designation} • VRd {candidate.vrd:.1f} kN • "
                f"η {candidate.utilization * 100:.1f} %"
            )
        rows.append(item)
    return rows


class ShearScheduleDialog(tk.Toplevel):
    def __init__(
        self,
        owner: Any,
        *,
        mode: str,
        decoder: Callable[[str], Any] | None = None,
        design: Callable[..., Any] | None = None,
        defaults: dict[str, str],
        existing_names: set[str],
    ) -> None:
        super().__init__(owner)
        self.owner = owner
        self.mode = str(mode)
        self.decoder = decoder
        self.design = design
        self.existing_names = set(existing_names)
        self.items: list[ScheduleItem] = []
        self.result: list[dict[str, Any]] | None = None
        self.replace_existing = tk.BooleanVar(master=self, value=False)
        self.vars = {
            "slab": tk.StringVar(master=self, value=str(defaults.get("slab", "200"))),
            "gap": tk.StringVar(master=self, value=str(defaults.get("gap", "20"))),
            "concrete": tk.StringVar(master=self, value=str(defaults.get("concrete", "C25/30"))),
            "cover": tk.StringVar(master=self, value=str(defaults.get("cover", "30"))),
            "movement": tk.StringVar(master=self, value=str(defaults.get("movement", "Podélný posun"))),
            "application": tk.StringVar(master=self, value=str(defaults.get("application", "Nová konstrukce"))),
            "sleeve": tk.StringVar(master=self, value=str(defaults.get("sleeve", "Nerezová objímka"))),
        }

        title = "Výkaz → Dekodér smykových trnů" if self.mode == "decoder" else "Výkaz → Návrh smykových trnů"
        self.title(title)
        self.geometry("1260x780")
        self.minsize(980, 640)
        self.transient(owner)
        place_dialog_on_parent(self, owner)
        self.grab_set()
        self.configure(background=owner.colors["bg"])
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.summary_var = tk.StringVar(master=self, value="Vložte výkaz a spusťte kontrolu.")
        self._build(title)

    def _build(self, title: str) -> None:
        outer = ttk.Frame(self, style="App.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)

        ttk.Label(outer, text=title, style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text="Stejný princip jako u izolačních nosníků: vložit ze schránky, zkontrolovat náhled a teprve potom řádky převzít.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 8))

        source = ttk.Frame(outer, style="Card.TFrame", padding=10)
        source.grid(row=2, column=0, sticky="ew")
        source.columnconfigure(0, weight=1)
        self.text = tk.Text(
            source,
            height=7,
            wrap="none",
            undo=True,
            font=("Calibri", 11),
            background=self.owner.colors["panel"],
            foreground=self.owner.colors["text"],
            insertbackground=self.owner.colors["text"],
        )
        self.text.grid(row=0, column=0, sticky="ew")
        ybar = ttk.Scrollbar(source, orient="vertical", command=self.text.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=ybar.set)

        buttons = ttk.Frame(source, style="Card.TFrame")
        buttons.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        ttk.Button(buttons, text="Vložit ze schránky", command=self._paste).pack(side="left")
        ttk.Button(buttons, text="Načíst / obnovit náhled", style="Accent.TButton", command=self._analyze).pack(side="left", padx=(7, 0))
        ttk.Label(
            buttons,
            text="Podporuje tabulky z Excelu, oddělovač | / TAB a běžný text.",
            style="MutedCard.TLabel",
        ).pack(side="left", padx=(12, 0))

        params = ttk.LabelFrame(outer, text="Výchozí parametry")
        params.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        column = 0
        for label, key, values, width in (
            ("h [mm]", "slab", None, 8),
            ("Spára [mm]", "gap", None, 8),
            ("Beton", "concrete", ("C25/30", "C30/37", "C35/45", "C40/50"), 9),
        ):
            ttk.Label(params, text=label).grid(row=0, column=column, padx=(8 if column else 10, 4), pady=8)
            column += 1
            if values:
                ttk.Combobox(params, textvariable=self.vars[key], values=values, state="readonly", width=width).grid(row=0, column=column, pady=8)
            else:
                ttk.Entry(params, textvariable=self.vars[key], width=width).grid(row=0, column=column, pady=8)
            column += 1

        if self.mode == "decoder":
            ttk.Label(params, text="cnom Schöck").grid(row=0, column=column, padx=(12, 4), pady=8)
            column += 1
            ttk.Combobox(params, textvariable=self.vars["cover"], values=("20", "30"), state="readonly", width=6).grid(row=0, column=column, pady=8)
        else:
            for label, key, values, width in (
                ("Pohyb", "movement", ("Podélný posun", "Podélný + příčný posun"), 21),
                ("Použití", "application", ("Nová konstrukce", "Stávající betonová stěna"), 23),
                ("Objímka", "sleeve", ("Nerezová objímka", "Plastová objímka"), 18),
            ):
                ttk.Label(params, text=label).grid(row=0, column=column, padx=(12, 4), pady=8)
                column += 1
                ttk.Combobox(params, textvariable=self.vars[key], values=values, state="readonly", width=width).grid(row=0, column=column, pady=8)
                column += 1

        summary = ttk.Frame(outer, style="App.TFrame")
        summary.grid(row=4, column=0, sticky="ew", pady=(10, 6))
        summary.columnconfigure(0, weight=1)
        ttk.Label(summary, textvariable=self.summary_var, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(summary, text="Nahradit stávající řádky", variable=self.replace_existing).grid(row=0, column=1, sticky="e")

        preview = ttk.Frame(outer, style="Card.TFrame", padding=8)
        preview.grid(row=5, column=0, sticky="nsew")
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(0, weight=1)
        columns = ("line", "status", "position", "qty", "source", "result", "issue")
        self.tree = ttk.Treeview(preview, columns=columns, show="headings", style="Data.Treeview")
        specs = {
            "line": ("Ř.", 45, "center"),
            "status": ("Stav", 90, "center"),
            "position": ("Pozice", 80, "center"),
            "qty": ("Ks", 50, "center"),
            "source": ("Vstup", 330, "w"),
            "result": ("Rozpoznáno / návrh", 380, "w"),
            "issue": ("Kontrola", 300, "w"),
        }
        for key, (label, width, anchor) in specs.items():
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=anchor, stretch=key in {"source", "result", "issue"})
        y = ttk.Scrollbar(preview, orient="vertical", command=self.tree.yview)
        x = ttk.Scrollbar(preview, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        self.tree.tag_configure("ok", foreground=self.owner.colors["success"])
        self.tree.tag_configure("error", foreground=self.owner.colors["danger"])

        actions = ttk.Frame(outer, style="App.TFrame")
        actions.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Zrušit", command=self._cancel).grid(row=0, column=1)
        self.insert_button = ttk.Button(actions, text="Vložit připravené", style="Accent.TButton", command=self._accept, state="disabled")
        self.insert_button.grid(row=0, column=2, padx=(8, 0))

        self.bind("<Escape>", lambda _e: self._cancel())

    def _defaults(self) -> dict[str, str]:
        return {key: variable.get() for key, variable in self.vars.items()}

    def _paste(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self._analyze()

    def _analyze(self) -> None:
        raw = self.text.get("1.0", "end-1c")
        if not raw.strip():
            self.items = []
            self._refresh()
            return
        try:
            if self.mode == "decoder":
                if self.decoder is None:
                    raise RuntimeError("Chybí dekodér smykových trnů.")
                self.items = parse_decoder_schedule(
                    raw,
                    decoder=self.decoder,
                    defaults=self._defaults(),
                    existing_names=set(self.existing_names),
                )
            else:
                if self.design is None:
                    raise RuntimeError("Chybí návrhový modul smykových trnů.")
                self.items = parse_design_schedule(
                    raw,
                    design=self.design,
                    defaults=self._defaults(),
                    existing_names=set(self.existing_names),
                )
        except Exception as exc:
            messagebox.showerror("Výkaz smykových trnů", str(exc), parent=self)
            return
        self._refresh()

    def _refresh(self) -> None:
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        ready = 0
        for index, item in enumerate(self.items):
            ok = not item.error
            if ok:
                ready += 1
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                tags=("ok" if ok else "error",),
                values=(
                    item.line,
                    "PŘIPRAVENO" if ok else "KONTROLA",
                    item.name,
                    item.quantity,
                    item.source,
                    item.result or "—",
                    item.error or "",
                ),
            )
        total = len(self.items)
        self.summary_var.set(f"{total} řádků • {ready} připraveno • {total - ready} k doplnění")
        self.insert_button.configure(state="normal" if ready else "disabled")

    def _accept(self) -> None:
        ready: list[dict[str, Any]] = []
        for item in self.items:
            if item.error:
                continue
            payload = dict(item.values)
            payload["name"] = item.name
            payload["quantity"] = item.quantity
            payload["import_source_text"] = item.source
            ready.append(payload)
        if not ready:
            return
        self.result = ready
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
