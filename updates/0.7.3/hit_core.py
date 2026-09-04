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
APP_VERSION = "0.3.0"
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
        self.source_document = str(self.data.get("source_document", "CONF-DOP HIT-HP/SP-07-23"))
        self.source_sha256 = str(self.data.get("source_sha256", ""))
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
