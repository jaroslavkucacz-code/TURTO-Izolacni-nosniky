from __future__ import annotations

import base64
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "TURTO – Návrh nosníků HIT"
APP_VERSION = "0.2.0"
CREATOR = "Vytvořil Ing. Jaroslav Kučera"
REPO_RAW = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main"
MANIFEST_URL = REPO_RAW + "/hit/update_manifest.json"
DATA_FILENAME = "hit_mvx_2023.json.gz.b64"
CONCRETES = ("C20/25", "C25/30", "C30/37")
COVERS = (30, 35, 50)


def root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def fmt(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def version_tuple(v: str):
    return tuple(int("".join(c for c in p if c.isdigit()) or 0) for p in str(v).split("."))


@dataclass(frozen=True)
class Candidate:
    series: str
    code: str
    length_code: int
    suffix: str
    h_table: int
    concrete: str
    m1: float
    v1: float
    m2: float
    v2: float
    page: int
    cover: int
    height: int
    utilization: float
    mode: str

    @property
    def designation(self) -> str:
        tail = f"-{self.suffix}" if self.suffix else ""
        return f"HIT-{self.series} MVX-{self.code}-{self.height}-{self.length_code:03d}-{self.cover}{tail}"

    @property
    def physical_length_mm(self) -> int:
        return {100: 1000, 50: 500, 25: 250}.get(self.length_code, self.length_code)


@dataclass
class DesignInput:
    name: str
    series: str
    height: int
    cover: int
    concrete: str
    med: float
    ved: float
    lengths: set[int]
    include_offsets: bool = False


@dataclass
class DesignRow:
    inp: DesignInput
    candidates: list[Candidate]
    selected_index: int | None
    error: str = ""

    @property
    def selected(self) -> Candidate | None:
        if self.selected_index is None:
            return None
        if not (0 <= self.selected_index < len(self.candidates)):
            return None
        return self.candidates[self.selected_index]


def _group_lines(words, tol: float = 1.5):
    groups = []
    for w in sorted(words, key=lambda z: (z["top"], z["x0"])):
        hit = None
        for g in groups[-3:]:
            if abs(g["top"] - w["top"]) <= tol:
                hit = g
                break
        if hit is None:
            hit = {"top": w["top"], "words": []}
            groups.append(hit)
        hit["words"].append(w)
    for g in groups:
        g["text"] = " ".join(x["text"] for x in sorted(g["words"], key=lambda z: z["x0"]))
    return groups


def _parse_side(page, x0: float, x1: float):
    words = [w for w in page.extract_words(x_tolerance=1, y_tolerance=2) if x0 <= w["x0"] < x1]
    lines = _group_lines(words)
    concrete_lines = [i for i, g in enumerate(lines) if g["text"].startswith("C20/25")]
    sections = []
    for ci in concrete_lines:
        ctop = lines[ci]["top"]
        heads = []
        for j in range(ci - 1, -1, -1):
            if ctop - lines[j]["top"] > 35:
                break
            if "HIT-" in lines[j]["text"]:
                heads.extend(re.findall(r"HIT-(?:HP|SP) MVX-[^\s]+", lines[j]["text"]))
        heads = heads[::-1]
        if not heads:
            continue
        end = page.height - 40
        for g in lines[ci + 1 :]:
            if "HIT-" in g["text"] and g["top"] > ctop + 20:
                end = g["top"] - 2
                break
        rows = []
        for g in lines[ci + 1 :]:
            if g["top"] >= end:
                break
            toks = g["text"].split()
            if not toks or not toks[0].isdigit():
                continue
            try:
                h = int(toks[0])
                vals = [float(t.replace(",", ".")) for t in toks[1:13]]
            except Exception:
                continue
            if 100 <= h <= 500 and len(vals) == 12:
                rows.append([h, *vals])
        if rows:
            sections.append([heads, rows])
    return sections


def build_database_from_pdf(pdf_path: Path, out_path: Path):
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "Chybí knihovna pdfplumber. Nainstalujte ji příkazem: py -m pip install pdfplumber"
        ) from exc

    sections = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        if len(pdf.pages) < 54:
            raise RuntimeError("Vybraný dokument nemá očekávaný rozsah DoP HIT-HP/SP-07-23.")
        for pi in range(3, 54):
            page = pdf.pages[pi]
            for x0, x1 in ((35, page.width / 2), (page.width / 2, page.width - 25)):
                for heads, rows in _parse_side(page, x0, x1):
                    sections.append([heads, rows, pi + 1])

    if len(sections) < 190:
        raise RuntimeError(
            f"Z DoP se podařilo načíst jen {len(sections)} tabulek; očekáváno přibližně 200."
        )

    payload = {
        "schema_version": 1,
        "catalog_id": "leviat_hit_hp_sp_07_23",
        "source_document": "CONF-DOP_HIT-HP/SP-07-23",
        "source_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "covers_mm": [30, 35, 50],
        "concretes": ["C20/25", "C25/30", "C30/37"],
        "ratio_min_m": 0.15,
        "sections": sections,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    out_path.write_text(base64.b64encode(gzip.compress(raw, 9)).decode("ascii"), encoding="ascii")
    return payload


class HitDatabase:
    def __init__(self, path: Path):
        text = path.read_text(encoding="ascii").strip()
        raw = gzip.decompress(base64.b64decode(text))
        self.data = json.loads(raw.decode("utf-8"))
        self.records = []
        concretes = self.data.get("concretes", list(CONCRETES))

        for heads, rows, page in self.data["sections"]:
            for head in heads:
                m = re.match(
                    r"HIT-(HP|SP) MVX-(\d{4})-hh-(100|050|025)-cc(?:-(OD|OU|WD|WU))?$",
                    head,
                )
                if not m:
                    continue
                series, code, length, suffix = m.groups()
                for row in rows:
                    h = int(row[0])
                    vals = row[1:]
                    for ci, conc in enumerate(concretes):
                        m1, v1, m2, v2 = vals[ci * 4 : (ci + 1) * 4]
                        self.records.append(
                            [
                                series,
                                code,
                                int(length),
                                suffix or "",
                                h,
                                conc,
                                m1,
                                v1,
                                m2,
                                v2,
                                page,
                            ]
                        )

    def candidates(
        self,
        series: str,
        height: int,
        cover: int,
        concrete: str,
        med: float,
        ved: float,
        lengths: set[int],
        include_offsets: bool = False,
    ):
        htab = height - cover
        if htab < 0:
            return [], f"Výška h − krytí = {htab} mm není platná."

        q = math.inf if abs(ved) < 1e-12 else abs(med) / abs(ved)
        if abs(ved) > 1e-12 and q < float(self.data.get("ratio_min_m", 0.15)) - 1e-12:
            return [], f"Poměr |MEd| / |VEd| = {fmt(q, 3)} m je menší než požadovaných 0,150 m."

        out = []
        for r in self.records:
            s, code, L, suffix, h, conc, m1, v1, m2, v2, page = r
            if (
                s != series
                or int(h) != htab
                or conc != concrete
                or int(L) not in lengths
            ):
                continue
            if suffix and not include_offsets:
                continue

            u, mode = utilization(
                abs(med),
                abs(ved),
                abs(float(m1)),
                abs(float(v1)),
                abs(float(m2)),
                abs(float(v2)),
            )
            if u <= 1.0 + 1e-9:
                out.append(
                    Candidate(
                        s,
                        code,
                        int(L),
                        suffix,
                        int(h),
                        conc,
                        float(m1),
                        float(v1),
                        float(m2),
                        float(v2),
                        int(page),
                        cover,
                        height,
                        u,
                        mode,
                    )
                )

        # První je nejbližší vyhovující shoda:
        # nejvyšší využití <= 100 %, při shodě standardní varianta a delší prvek.
        out.sort(
            key=lambda x: (
                -x.utilization,
                0 if not x.suffix else 1,
                -x.length_code,
                x.code,
            )
        )
        return out, ""


def utilization(M: float, V: float, M1: float, V1: float, M2: float, V2: float):
    if M < 1e-12 and V < 1e-12:
        return 0.0, "nulové zatížení"

    lambdas = []
    if V > 1e-12:
        lam = V1 / V
        if lam * M <= M1 + 1e-9:
            lambdas.append((lam, "V1"))

    if M > 1e-12:
        lam = M2 / M
        if lam * V <= V2 + 1e-9:
            lambdas.append((lam, "M2"))

    dx = M2 - M1
    dy = V2 - V1
    den = M * dy - V * dx
    if abs(den) > 1e-12:
        lam = (M1 * dy - V1 * dx) / den
        if lam >= 0:
            if abs(dx) >= abs(dy):
                t = (lam * M - M1) / dx if abs(dx) > 1e-12 else 0
            else:
                t = (lam * V - V1) / dy if abs(dy) > 1e-12 else 0
            if -1e-9 <= t <= 1 + 1e-9:
                lambdas.append((lam, "interpolace M–V"))

    valid = [x for x in lambdas if x[0] >= 0]
    if not valid:
        return math.inf, "mimo obálku"

    lam = max(valid, key=lambda x: x[0])
    if lam[0] <= 1e-12:
        return math.inf, lam[1]

    return 1.0 / lam[0], lam[1]


class CandidateDialog(tk.Toplevel):
    def __init__(self, master, row: DesignRow, on_choose):
        super().__init__(master)
        self.row = row
        self.on_choose = on_choose
        self.title(f"Výběr typu – {row.inp.name}")
        self.geometry("1060x580")
        self.minsize(900, 480)
        self.transient(master)
        self.grab_set()

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=f"Vyber jiný vyhovující typ pro {row.inp.name}",
            font=("Calibri", 15, "bold"),
        ).pack(anchor="w")

        inp = row.inp
        ttk.Label(
            outer,
            text=(
                f"{inp.series} • h {inp.height} mm • cnom {inp.cover} mm • {inp.concrete} "
                f"• MEd {fmt(inp.med)} kNm/m • VEd {fmt(inp.ved)} kN/m"
            ),
        ).pack(anchor="w", pady=(2, 3))

        ttk.Label(
            outer,
            text=(
                "První řádek je automaticky doporučená nejbližší vyhovující shoda. "
                "Můžeš zvolit libovolnou jinou vyhovující variantu."
            ),
        ).pack(anchor="w", pady=(0, 10))

        frame = ttk.Frame(outer)
        frame.pack(fill="both", expand=True)

        cols = ("product", "util", "m1", "v1", "m2", "v2", "page", "mode")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        heads = {
            "product": "Výrobek",
            "util": "Využití",
            "m1": "MRd,1",
            "v1": "VRd,1",
            "m2": "MRd,2",
            "v2": "VRd,2",
            "page": "DoP str.",
            "mode": "Rozhodující větev",
        }
        widths = {
            "product": 320,
            "util": 85,
            "m1": 80,
            "v1": 75,
            "m2": 80,
            "v2": 75,
            "page": 65,
            "mode": 130,
        }
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w" if c == "product" else "center")

        ybar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        for i, cand in enumerate(row.candidates):
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    cand.designation,
                    fmt(cand.utilization * 100) + " %",
                    fmt(cand.m1),
                    fmt(cand.v1),
                    fmt(cand.m2),
                    fmt(cand.v2),
                    cand.page,
                    cand.mode,
                ),
            )

        if row.selected_index is not None and str(row.selected_index) in self.tree.get_children():
            chosen = str(row.selected_index)
        elif self.tree.get_children():
            chosen = self.tree.get_children()[0]
        else:
            chosen = None

        if chosen:
            self.tree.selection_set(chosen)
            self.tree.focus(chosen)
            self.tree.see(chosen)

        self.tree.bind("<Double-1>", lambda _e: self.apply())

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Zrušit", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="POUŽÍT VYBRANÝ TYP", command=self.apply).pack(
            side="right", padx=(0, 8)
        )

    def apply(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.on_choose(idx)
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1460x840")
        self.minsize(1120, 680)
        self.option_add("*Font", ("Calibri", 10))

        self.data_path = root_dir() / DATA_FILENAME
        if not self.data_path.exists():
            self.withdraw()
            pdf = filedialog.askopenfilename(
                title="Vyberte CONF-DOP HIT-HP/SP-07-23",
                filetypes=[("PDF", "*.pdf")],
            )
            if not pdf:
                messagebox.showerror(
                    "TURTO HIT", "Pro první spuštění je nutné vybrat zdrojové DoP."
                )
                self.destroy()
                return
            try:
                build_database_from_pdf(Path(pdf), self.data_path)
            except Exception as exc:
                messagebox.showerror(
                    "TURTO HIT", f"Databázi se nepodařilo vytvořit:\n{exc}"
                )
                self.destroy()
                return
            self.deiconify()

        self.db = HitDatabase(self.data_path)
        self.rows: list[DesignRow] = []

        self.name_var = tk.StringVar(value="N1")
        self.series = tk.StringVar(value="HP")
        self.height = tk.StringVar(value="200")
        self.cover = tk.StringVar(value="35")
        self.concrete = tk.StringVar(value="C25/30")
        self.med = tk.StringVar(value="-40")
        self.ved = tk.StringVar(value="30")
        self.l100 = tk.BooleanVar(value=True)
        self.l050 = tk.BooleanVar(value=True)
        self.l025 = tk.BooleanVar(value=False)
        self.offsets = tk.BooleanVar(value=False)
        self.status = tk.StringVar(
            value="Přidej jeden nebo více nosníků. Každému se automaticky přiřadí nejbližší vyhovující typ."
        )

        self._build()

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Calibri", 18, "bold"))
        style.configure("Sub.TLabel", font=("Calibri", 10))
        style.configure("Good.TLabel", font=("Calibri", 11, "bold"))
        style.configure("Treeview", rowheight=27)

        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        hdr = ttk.Frame(outer)
        hdr.pack(fill="x")
        ttk.Label(
            hdr, text="TURTO | Návrh nosníků Leviat HIT", style="Title.TLabel"
        ).pack(side="left")
        ttk.Button(hdr, text="Aktualizace", command=self.check_updates).pack(side="right")
        ttk.Button(hdr, text="Obnovit data z DoP", command=self.rebuild_data).pack(
            side="right", padx=(0, 8)
        )

        ttk.Label(
            outer,
            text="Hromadný návrh HIT-HP/SP MVX podle MEd a VEd • " + CREATOR,
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        entry = ttk.LabelFrame(outer, text="Přidat nosník", padding=12)
        entry.pack(fill="x")

        field_defs = [
            ("Označení", self.name_var, None, 13),
            ("Řada", self.series, ("HP", "SP"), 9),
            ("Výška h [mm]", self.height, None, 12),
            ("Krytí [mm]", self.cover, tuple(map(str, COVERS)), 10),
            ("Beton", self.concrete, CONCRETES, 12),
            ("MEd [kNm/m]", self.med, None, 13),
            ("VEd [kN/m]", self.ved, None, 13),
        ]

        for i, (label, var, values, width) in enumerate(field_defs):
            ttk.Label(entry, text=label).grid(row=0, column=i, sticky="w", padx=(0, 8))
            if values:
                widget = ttk.Combobox(
                    entry, textvariable=var, values=values, state="readonly", width=width
                )
            else:
                widget = ttk.Entry(entry, textvariable=var, width=width)
            widget.grid(row=1, column=i, sticky="ew", padx=(0, 8), pady=(2, 8))
            entry.columnconfigure(i, weight=1 if i in (0, 2, 5, 6) else 0)

        opts = ttk.Frame(entry)
        opts.grid(row=2, column=0, columnspan=7, sticky="ew")

        ttk.Label(opts, text="Povolené délky:").pack(side="left")
        ttk.Checkbutton(opts, text="1000 mm", variable=self.l100).pack(
            side="left", padx=(8, 0)
        )
        ttk.Checkbutton(opts, text="500 mm", variable=self.l050).pack(
            side="left", padx=(8, 0)
        )
        ttk.Checkbutton(opts, text="250 mm", variable=self.l025).pack(
            side="left", padx=(8, 0)
        )
        ttk.Checkbutton(
            opts, text="zahrnout OD/OU/WD/WU", variable=self.offsets
        ).pack(side="left", padx=(18, 0))

        ttk.Button(opts, text="PŘIDAT NOSNÍK", command=self.add_row).pack(side="right")
        ttk.Button(opts, text="PŘEPSAT VYBRANÝ", command=self.replace_selected).pack(
            side="right", padx=(0, 8)
        )
        ttk.Button(opts, text="NAČÍST VYBRANÝ", command=self.load_selected_to_form).pack(
            side="right", padx=(0, 8)
        )

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(12, 6))
        ttk.Label(bar, textvariable=self.status, style="Good.TLabel").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(bar, text="Vymazat vše", command=self.clear_all).pack(side="right")
        ttk.Button(bar, text="Odstranit", command=self.remove_selected).pack(
            side="right", padx=(0, 8)
        )
        ttk.Button(bar, text="ZMĚNIT TYP", command=self.choose_alternative).pack(
            side="right", padx=(0, 8)
        )
        ttk.Button(bar, text="PŘEPOČÍTAT VŠE", command=self.recalculate_all).pack(
            side="right", padx=(0, 8)
        )

        table_frame = ttk.Frame(outer)
        table_frame.pack(fill="both", expand=True)

        cols = (
            "name",
            "series",
            "h",
            "cover",
            "concrete",
            "med",
            "ved",
            "product",
            "util",
            "alts",
            "page",
            "mode",
        )
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", selectmode="browse", height=16
        )

        heads = {
            "name": "Označení",
            "series": "Řada",
            "h": "h [mm]",
            "cover": "cnom",
            "concrete": "Beton",
            "med": "MEd",
            "ved": "VEd",
            "product": "Navržený výrobek ▼",
            "util": "Využití",
            "alts": "Variant",
            "page": "DoP",
            "mode": "Rozhodující větev",
        }
        widths = {
            "name": 95,
            "series": 55,
            "h": 65,
            "cover": 60,
            "concrete": 75,
            "med": 85,
            "ved": 80,
            "product": 330,
            "util": 80,
            "alts": 65,
            "page": 55,
            "mode": 130,
        }

        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w" if c in ("name", "product") else "center")

        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree.tag_configure("error", background="#f5dddd")
        self.tree.bind("<Double-1>", self._double_click)

        ttk.Label(
            outer,
            text=(
                "Automaticky se vybere vyhovující varianta s nejvyšším využitím – tedy nejbližší možná shoda. "
                "Dvojklikem na řádek nebo tlačítkem ZMĚNIT TYP otevřeš všechny další vyhovující varianty. "
                "Výpočet používá zjednodušenou lineární interakční obálku z DoP; platí |MEd|/|VEd| ≥ 0,15 m."
            ),
            wraplength=1370,
            justify="left",
        ).pack(fill="x", pady=(9, 0))

    def _get_form_input(self) -> DesignInput:
        name = self.name_var.get().strip() or self._next_name()
        try:
            h = int(float(self.height.get().replace(",", ".")))
            c = int(self.cover.get())
            m = float(self.med.get().replace(",", "."))
            v = float(self.ved.get().replace(",", "."))
        except ValueError:
            raise ValueError("Výška, krytí, MEd a VEd musí být číselné.")

        lengths = {
            L
            for L, var in ((100, self.l100), (50, self.l050), (25, self.l025))
            if var.get()
        }
        if not lengths:
            raise ValueError("Vyber alespoň jednu délku prvku.")

        return DesignInput(
            name=name,
            series=self.series.get(),
            height=h,
            cover=c,
            concrete=self.concrete.get(),
            med=m,
            ved=v,
            lengths=lengths,
            include_offsets=self.offsets.get(),
        )

    def _design_input(self, inp: DesignInput, preserve_designation: str | None = None) -> DesignRow:
        candidates, err = self.db.candidates(
            inp.series,
            inp.height,
            inp.cover,
            inp.concrete,
            inp.med,
            inp.ved,
            inp.lengths,
            inp.include_offsets,
        )

        if err:
            return DesignRow(inp, [], None, err)

        if not candidates:
            return DesignRow(
                inp,
                [],
                None,
                f"Nenalezen vyhovující prvek pro h−cnom = {inp.height - inp.cover} mm.",
            )

        selected = 0
        if preserve_designation:
            for i, c in enumerate(candidates):
                if c.designation == preserve_designation:
                    selected = i
                    break

        return DesignRow(inp, candidates, selected, "")

    def add_row(self):
        try:
            inp = self._get_form_input()
        except ValueError as exc:
            messagebox.showerror("Vstup", str(exc))
            return

        row = self._design_input(inp)
        self.rows.append(row)
        self._refresh_tree(select_index=len(self.rows) - 1)
        self.name_var.set(self._next_name())
        self._update_status()

    def replace_selected(self):
        idx = self._selected_row_index()
        if idx is None:
            messagebox.showinfo("TURTO HIT", "Nejprve vyber řádek, který chceš přepsat.")
            return

        try:
            inp = self._get_form_input()
        except ValueError as exc:
            messagebox.showerror("Vstup", str(exc))
            return

        self.rows[idx] = self._design_input(inp)
        self._refresh_tree(select_index=idx)
        self._update_status()

    def load_selected_to_form(self):
        idx = self._selected_row_index()
        if idx is None:
            messagebox.showinfo("TURTO HIT", "Nejprve vyber nosník v tabulce.")
            return

        inp = self.rows[idx].inp
        self.name_var.set(inp.name)
        self.series.set(inp.series)
        self.height.set(str(inp.height))
        self.cover.set(str(inp.cover))
        self.concrete.set(inp.concrete)
        self.med.set(fmt(inp.med))
        self.ved.set(fmt(inp.ved))
        self.l100.set(100 in inp.lengths)
        self.l050.set(50 in inp.lengths)
        self.l025.set(25 in inp.lengths)
        self.offsets.set(inp.include_offsets)

    def remove_selected(self):
        idx = self._selected_row_index()
        if idx is None:
            return
        del self.rows[idx]
        self._refresh_tree(select_index=min(idx, len(self.rows) - 1))
        self._update_status()

    def clear_all(self):
        if not self.rows:
            return
        if not messagebox.askyesno("TURTO HIT", "Vymazat všechny zadané nosníky?"):
            return
        self.rows.clear()
        self._refresh_tree()
        self.name_var.set("N1")
        self._update_status()

    def recalculate_all(self):
        if not self.rows:
            return
        new_rows = []
        for row in self.rows:
            selected_designation = row.selected.designation if row.selected else None
            new_rows.append(self._design_input(row.inp, selected_designation))
        self.rows = new_rows
        self._refresh_tree()
        self._update_status("Všechny nosníky byly přepočítány.")

    def choose_alternative(self):
        idx = self._selected_row_index()
        if idx is None:
            messagebox.showinfo("TURTO HIT", "Nejprve vyber nosník v tabulce.")
            return

        row = self.rows[idx]
        if not row.candidates:
            messagebox.showinfo(
                "TURTO HIT",
                "Pro tento řádek nejsou k dispozici žádné vyhovující varianty.",
            )
            return

        def apply_choice(candidate_index):
            row.selected_index = candidate_index
            self._refresh_tree(select_index=idx)
            self._update_status(
                f"{row.inp.name}: ručně zvolen typ {row.selected.designation}."
            )

        CandidateDialog(self, row, apply_choice)

    def _double_click(self, _event=None):
        self.choose_alternative()

    def _selected_row_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _refresh_tree(self, select_index: int | None = None):
        self.tree.delete(*self.tree.get_children())

        for i, row in enumerate(self.rows):
            inp = row.inp
            cand = row.selected
            if cand:
                values = (
                    inp.name,
                    inp.series,
                    inp.height,
                    inp.cover,
                    inp.concrete,
                    fmt(inp.med),
                    fmt(inp.ved),
                    cand.designation + "  ▼",
                    fmt(cand.utilization * 100) + " %",
                    len(row.candidates),
                    cand.page,
                    cand.mode,
                )
                tags = ()
            else:
                values = (
                    inp.name,
                    inp.series,
                    inp.height,
                    inp.cover,
                    inp.concrete,
                    fmt(inp.med),
                    fmt(inp.ved),
                    row.error or "NELZE NAVRHNOUT",
                    "—",
                    0,
                    "—",
                    "—",
                )
                tags = ("error",)

            self.tree.insert("", "end", iid=str(i), values=values, tags=tags)

        if select_index is not None and 0 <= select_index < len(self.rows):
            iid = str(select_index)
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)

    def _update_status(self, prefix: str = ""):
        total = len(self.rows)
        ok = sum(1 for r in self.rows if r.selected is not None)
        bad = total - ok

        if total == 0:
            text = (
                "Přidej jeden nebo více nosníků. Každému se automaticky přiřadí nejbližší vyhovující typ."
            )
        else:
            text = f"Nosníků: {total} • navrženo: {ok}"
            if bad:
                text += f" • bez vyhovující varianty: {bad}"
            text += " • dvojklikem na řádek lze změnit typ."

        if prefix:
            text = prefix + "  " + text
        self.status.set(text)

    def _next_name(self):
        used = {r.inp.name for r in self.rows}
        n = 1
        while f"N{n}" in used:
            n += 1
        return f"N{n}"

    def rebuild_data(self):
        pdf = filedialog.askopenfilename(
            title="Vyberte CONF-DOP HIT-HP/SP-07-23",
            filetypes=[("PDF", "*.pdf")],
        )
        if not pdf:
            return

        try:
            build_database_from_pdf(Path(pdf), self.data_path)
            self.db = HitDatabase(self.data_path)
            if self.rows:
                self.recalculate_all()
            self.status.set("Databáze HIT byla znovu vytvořena ze zvoleného DoP.")
            messagebox.showinfo("TURTO HIT", "Databáze byla úspěšně obnovena.")
        except Exception as exc:
            messagebox.showerror(
                "TURTO HIT", f"Databázi se nepodařilo vytvořit:\n{exc}"
            )

    def check_updates(self):
        try:
            req = urllib.request.Request(
                MANIFEST_URL, headers={"User-Agent": "TURTO-HIT-Updater"}
            )
            with urllib.request.urlopen(req, timeout=20) as f:
                manifest = json.loads(f.read().decode("utf-8"))

            latest = str(manifest.get("version", "0"))
            if version_tuple(latest) <= version_tuple(APP_VERSION):
                messagebox.showinfo(
                    "Aktualizace", f"Používáte aktuální HIT verzi {APP_VERSION}."
                )
                return

            if not messagebox.askyesno(
                "Aktualizace",
                f"Je dostupná HIT verze {latest}.\n\n"
                f"{manifest.get('notes', '')}\n\nNainstalovat?",
            ):
                return

            temp = Path(tempfile.mkdtemp(prefix="turto_hit_"))
            files = manifest.get("files", [])
            for item in files:
                req = urllib.request.Request(
                    item["url"], headers={"User-Agent": "TURTO-HIT-Updater"}
                )
                with urllib.request.urlopen(req, timeout=30) as f:
                    b = f.read()

                if (
                    hashlib.sha256(b).hexdigest().lower()
                    != item["sha256"].lower()
                ):
                    raise RuntimeError("Nesouhlasí SHA-256: " + item["path"])

                p = temp / item["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b)

            script = temp / "apply.py"
            paths = [x["path"] for x in files]
            script.write_text(
                "import os,shutil,sys,time\n"
                "from pathlib import Path\n"
                "time.sleep(1.2)\n"
                "s=Path(__file__).parent; d=Path(sys.argv[1])\n"
                + f"paths={paths!r}\n"
                + "[( (d/p).parent.mkdir(parents=True,exist_ok=True), shutil.copy2(s/p,d/p)) for p in paths]\n"
                + "try: os.startfile(str(d/'hit_design.pyw'))\n"
                + "except Exception: pass\n",
                encoding="utf-8",
            )

            subprocess.Popen(
                [sys.executable, str(script), str(root_dir())],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.after(200, self.destroy)

        except Exception as exc:
            messagebox.showerror(
                "Aktualizace", f"Aktualizaci se nepodařilo provést:\n{exc}"
            )


if __name__ == "__main__":
    App().mainloop()
