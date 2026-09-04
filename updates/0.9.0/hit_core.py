from __future__ import annotations

import base64
import gzip
import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

DATA_FILENAME = "hit_all_2023_v3.json.gz.b64"
CONCRETES = ("C20/25", "C25/30", "C30/37")
COVERS = (30, 35, 50)
CONNECTION_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL")
RATIO_MIN_M = 0.15
TOL = 1e-9

HIT_CATALOG_SOURCE = "HALFEN HIT Insulated Connection ©2023, HIT 20.2-EN"
HIT_CATALOG_URL = "https://www.leviat.com/en-us/mwdownloads/download/link/id/898.pdf"


def fmt(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def height_code(height_mm: int) -> str:
    """HIT designation uses element height in centimetres, e.g. 200 mm -> 20."""
    value = int(height_mm)
    if value % 10:
        raise ValueError("Výška HIT musí být zadána po 10 mm (např. 180, 200, 250 mm).")
    return f"{value // 10:02d}"


def _width_code(length_code: int) -> str:
    return {100: "100", 50: "050", 33: "033", 25: "025"}.get(int(length_code), f"{int(length_code):03d}")


@dataclass(frozen=True)
class DirectionalActions:
    """Obálkové návrhové účinky rozdělené podle znaménka.

    Hodnoty jsou velikosti; směr určuje příslušné pole. Uživatel tedy může
    současně zadat např. V+ i V-. To je důležité i pro budoucí výrobce,
    jejichž únosnost nemusí být v obou směrech shodná.
    """
    m_pos: float = 0.0
    m_neg: float = 0.0
    v_pos: float = 0.0
    v_neg: float = 0.0

    def normalized(self) -> "DirectionalActions":
        return DirectionalActions(
            abs(float(self.m_pos)), abs(float(self.m_neg)),
            abs(float(self.v_pos)), abs(float(self.v_neg)),
        )

    def has_any(self) -> bool:
        a = self.normalized()
        return max(a.m_pos, a.m_neg, a.v_pos, a.v_neg) > TOL


@dataclass(frozen=True)
class Candidate:
    series: str
    connection_type: str
    code: str
    length_code: int
    suffix: str
    h_table: int
    concrete: str
    m1: float
    v1: float
    m2: float
    v2: float
    page: Any
    cover: int
    height: int
    utilization: float
    mode: str
    source_note: str = ""

    @property
    def designation(self) -> str:
        hcode = height_code(self.height)
        width = _width_code(self.length_code)
        typ = self.connection_type.upper()
        if typ == "MVX":
            tail = f"-{self.suffix}" if self.suffix else ""
            return f"HIT-{self.series} MVX-{self.code}-{hcode}-{width}-{self.cover:02d}{tail}"
        if typ == "MVXL":
            tail = f"-{self.suffix}" if self.suffix else ""
            return f"HIT-{self.series} MVXL-{self.code}-{hcode}-{width}-{self.cover:02d}{tail}"
        if typ in {"ZVX", "ZDX"}:
            dia = self.suffix or "06"
            return f"HIT-{self.series} {typ}-{self.code}-{hcode}-{width}-{self.cover:02d}-{dia}"
        if typ in {"DD", "DVL", "DDL"}:
            dia = self.suffix or "06"
            return f"HIT-{self.series} {typ}-{self.code}-{hcode}-{width}-{self.cover:02d}-{dia}"
        return f"HIT-{self.series} {typ}-{self.code}-{hcode}-{width}-{self.cover:02d}"

    @property
    def physical_length_mm(self) -> int:
        return {100: 1000, 50: 500, 33: 333, 25: 250}.get(self.length_code, self.length_code)


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


def _parse_mvx_side(page, x0: float, x1: float):
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


_ZVX_RE = re.compile(
    r"HIT-(HP|SP)\s+ZVX\s+(\d{4})-hh[^-]*-(100|050|033|025)-30-(06|08|10|12)"
)


def _parse_zvx_pages(pdf) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    width_mm = {"100": 1000, "050": 500, "033": 333, "025": 250}
    width_code = {"100": 100, "050": 50, "033": 33, "025": 25}

    for page_index in range(94, 100):
        text = pdf.pages[page_index].extract_text(x_tolerance=1, y_tolerance=2) or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        i = 0
        while i < len(lines):
            if not _ZVX_RE.search(lines[i]):
                i += 1
                continue
            header_lines: list[str] = []
            while i < len(lines) and not lines[i].startswith("C20/25"):
                if "HIT-" in lines[i]:
                    header_lines.append(lines[i])
                i += 1
            products = []
            for line in header_lines:
                for match in _ZVX_RE.finditer(line):
                    series, code, width, dia = match.groups()
                    wmm = width_mm[width]
                    xx = int(code[:2])
                    yy = int(code[2:])
                    density_key = (round(xx * 1000 / wmm), round(yy * 1000 / wmm), dia)
                    products.append({
                        "series": series,
                        "code": code,
                        "length_code": width_code[width],
                        "dia": dia,
                        "density_key": density_key,
                    })
            if not products:
                continue
            keys = list(dict.fromkeys(p["density_key"] for p in products))
            while i < len(lines) and not re.match(r"^\d{3}(?:-\d{3})?\s", lines[i]):
                if _ZVX_RE.search(lines[i]):
                    break
                i += 1
            while i < len(lines):
                line = lines[i]
                if _ZVX_RE.search(line):
                    break
                m = re.match(r"^(\d{3})(?:-(\d{3}))?\s+(.+)$", line)
                if not m:
                    i += 1
                    continue
                hmin = int(m.group(1))
                hmax = int(m.group(2) or m.group(1))
                nums = []
                for tok in m.group(3).split():
                    try:
                        nums.append(float(tok.replace(",", ".")))
                    except Exception:
                        pass
                if len(nums) != len(keys) * 2:
                    i += 1
                    continue
                for product in products:
                    ki = keys.index(product["density_key"])
                    for ci, concrete in enumerate(("C20/25", "C25/30")):
                        records.append({
                            "series": product["series"],
                            "code": product["code"],
                            "length_code": product["length_code"],
                            "diameter": product["dia"],
                            "h_min": hmin,
                            "h_max": hmax,
                            "concrete": concrete,
                            "vrd": nums[2 * ki + ci],
                            "page": page_index + 1,
                        })
                i += 1
    return records



_MVXL_RE = re.compile(
    r"HIT-(HP|SP)\s+MVXL-(\d{4})-hh-(100|050)-cc-(\d{4})"
)
_MVXL_BLOCKS = ((75.0, 220.0), (223.0, 370.0), (372.0, 520.0))


def _parse_number_token(token: str) -> float | None:
    value = str(token).strip().replace("−", "-").replace(",", ".")
    if value in {"", "-", "–", "—"}:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _parse_mvxl_pages(pdf) -> list[dict[str, Any]]:
    """Parse Annex 5 MVXL tables (DoP pages 104-121).

    Each visual block contains one 1000 mm product and, where available, its
    equivalent 500 mm product. The +VRd ranges and -MRd rows are common to both
    because the tables are given per metre. Bond conditions are not a user
    choice: Annex 5 switches from good to poor bond after h-cnom = 300 mm.
    """
    records: list[dict[str, Any]] = []
    width_code = {"100": 100, "050": 50}
    concretes = ("C20/25", "C25/30", "C30/37")

    # PDF indices 103..120 correspond to printed DoP pages 104..121.
    for page_index in range(103, 121):
        page = pdf.pages[page_index]
        all_words = page.extract_words(x_tolerance=1, y_tolerance=1) or []
        for x0, x1 in _MVXL_BLOCKS:
            header_text = page.crop((x0, 0, x1, 105)).extract_text(x_tolerance=1, y_tolerance=2) or ""
            products: list[dict[str, Any]] = []
            seen_product: set[tuple[str, str, int, str]] = set()
            for match in _MVXL_RE.finditer(header_text):
                series, code, width, tail = match.groups()
                key = (series, code, width_code[width], tail)
                if key in seen_product:
                    continue
                seen_product.add(key)
                products.append({
                    "series": series,
                    "code": code,
                    "length_code": width_code[width],
                    "tail": tail,
                })
            if not products:
                continue

            # +VRd range table is located in the upper part of each block.
            top_text = page.crop((x0, 95, x1, 195)).extract_text(x_tolerance=1, y_tolerance=2) or ""
            v_ranges: list[dict[str, Any]] = []
            for raw_line in top_text.splitlines():
                line = " ".join(raw_line.split())
                m = re.match(r"^(\d{3})\s*-\s*(\d{3})\s+(.+)$", line)
                if m:
                    h_min, h_max = int(m.group(1)), int(m.group(2))
                    nums = [_parse_number_token(tok) for tok in m.group(3).split()]
                else:
                    m = re.match(r"^>\s*(\d{3})\s+(.+)$", line)
                    if not m:
                        continue
                    h_min, h_max = int(m.group(1)) + 1, 10000
                    nums = [_parse_number_token(tok) for tok in m.group(2).split()]
                nums = [v for v in nums if v is not None]
                if len(nums) < 3:
                    continue
                v_ranges.append({
                    "h_min": h_min,
                    "h_max": h_max,
                    "values": {concretes[i]: float(nums[i]) for i in range(3)},
                })

            # -MRd rows: group words by their vertical coordinate so extraction
            # is stable even where the PDF inserts the 'Verbundbereich' labels.
            block_words = [
                w for w in all_words
                if x0 <= float(w.get("x0", 0)) < x1 and float(w.get("top", 0)) >= 190
            ]
            groups: list[dict[str, Any]] = []
            for word in sorted(block_words, key=lambda z: (float(z["top"]), float(z["x0"]))):
                target = None
                for group in groups[-4:]:
                    if abs(float(group["top"]) - float(word["top"])) <= 0.9:
                        target = group
                        break
                if target is None:
                    target = {"top": float(word["top"]), "words": []}
                    groups.append(target)
                target["words"].append(word)

            m_rows: list[dict[str, Any]] = []
            for group in groups:
                toks = [str(w["text"]).strip() for w in sorted(group["words"], key=lambda z: float(z["x0"]))]
                if not toks or not re.fullmatch(r"\d{3}", toks[0]):
                    continue
                h_eff = int(toks[0])
                if not 120 <= h_eff <= 500:
                    continue
                values: list[float | None] = []
                for tok in toks[1:]:
                    parsed = _parse_number_token(tok)
                    if parsed is not None or tok in {"-", "–", "—"}:
                        values.append(parsed)
                    if len(values) == 3:
                        break
                if len(values) != 3 or not any(v is not None for v in values):
                    continue
                m_rows.append({
                    "h_eff": h_eff,
                    "bond": "good" if h_eff <= 300 else "poor",
                    "values": {concretes[i]: values[i] for i in range(3)},
                })

            if not v_ranges or not m_rows:
                continue
            for product in products:
                records.append({
                    **product,
                    "page": page_index + 1,
                    "vrd_pos_ranges": v_ranges,
                    "mrd_rows": m_rows,
                })

    # Deduplicate defensively; each designation template must map to one table.
    unique: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for row in records:
        unique[(row["series"], row["code"], int(row["length_code"]), row["tail"])] = row
    return list(unique.values())


def _parse_moment_page(page, xxs: tuple[str, ...], value_count: int) -> list[dict[str, Any]]:
    text = page.extract_text(x_tolerance=1, y_tolerance=2) or ""
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        m = re.match(r"^\s*(\d{3})\s+(.+)$", line.strip())
        if not m:
            continue
        try:
            h_eff = int(m.group(1))
            vals = [float(tok.replace(",", ".")) for tok in m.group(2).split()]
        except Exception:
            continue
        if len(vals) != value_count:
            continue
        for xi, xx in enumerate(xxs):
            rows.append({"h_eff": h_eff, "xx": xx, "concrete": "C20/25", "mrd": vals[2 * xi]})
            rows.append({"h_eff": h_eff, "xx": xx, "concrete": "C25/30", "mrd": vals[2 * xi + 1]})
    return rows


def build_database_from_pdf(pdf_path: Path, out_path: Path):
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("Chybí knihovna pdfplumber. Nainstalujte ji příkazem: py -m pip install pdfplumber") from exc

    mvx_sections = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        if len(pdf.pages) < 123:
            raise RuntimeError("Vybraný dokument nemá očekávaný rozsah DoP HIT-HP/SP-07-23.")
        for pi in range(3, 54):
            page = pdf.pages[pi]
            for x0, x1 in ((35, page.width / 2), (page.width / 2, page.width - 25)):
                for heads, rows in _parse_mvx_side(page, x0, x1):
                    mvx_sections.append([heads, rows, pi + 1])
        if len(mvx_sections) < 190:
            raise RuntimeError(f"Z Annexu 1 se podařilo načíst jen {len(mvx_sections)} tabulek MVX; očekáváno přibližně 200.")

        zvx_records = _parse_zvx_pages(pdf)
        if len(zvx_records) < 300:
            raise RuntimeError(f"Z Annexu 3 se podařilo načíst jen {len(zvx_records)} záznamů ZVX/ZDX; databáze by nebyla úplná.")

        dd_moment = _parse_moment_page(pdf.pages[100], ("04", "05", "06", "07", "08", "10", "12", "14"), 16)
        if len(dd_moment) < 500:
            raise RuntimeError("Nepodařilo se bezpečně načíst momentové tabulky DD z Annexu 4.")

        dvl_moment = _parse_moment_page(pdf.pages[122], ("11", "12", "13", "14", "16"), 10)
        if len(dvl_moment) < 300:
            raise RuntimeError("Nepodařilo se bezpečně načíst momentové tabulky DVL/DDL z Annexu 6.")

        mvxl_records = _parse_mvxl_pages(pdf)
        if len(mvxl_records) < 90:
            raise RuntimeError(f"Z Annexu 5 se podařilo načíst jen {len(mvxl_records)} tabulek MVXL; očekáváno přibližně 96.")

    payload = {
        "schema_version": 3,
        "catalog_id": "leviat_hit_hp_sp_07_23_all_v3",
        "source_document": "CONF-DOP_HIT-HP/SP-07-23",
        "source_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "catalog_source": HIT_CATALOG_SOURCE,
        "catalog_url": HIT_CATALOG_URL,
        "covers_mm": [30, 35, 50],
        "concretes": list(CONCRETES),
        "ratio_min_m": RATIO_MIN_M,
        "sections": mvx_sections,
        "zvx_records": zvx_records,
        "dd_moment": dd_moment,
        "dvl_moment": dvl_moment,
        "mvxl_records": mvxl_records,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(base64.b64encode(gzip.compress(raw, 9)).decode("ascii"), encoding="ascii")
    return payload


def _conc2(concrete: str) -> str:
    return "C20/25" if concrete == "C20/25" else "C25/30"


def _in_range(height: int, span: tuple[int, int] | None) -> bool:
    return span is not None and int(span[0]) <= int(height) <= int(span[1])


# HALFEN HIT 20.2-EN 2023, p. 106 / 108: DD shear capacities.
_DD_LOW = {
    "HP": {
        6: [
            (((160,190),(160,190),(180,210)), {6:(47.4,47.4), 7:(55.3,55.3)}),
            (((200,230),(200,230),(220,250)), {6:(52.2,52.2), 7:(60.9,60.9)}),
            (((240,350),(240,350),(260,350)), {6:(60.5,60.5), 7:(70.5,70.5)}),
        ],
        8: [
            (((160,190),(160,190),(180,210)), {6:(79.9,79.9), 7:(83.6,93.2)}),
            (((200,230),(200,230),(220,250)), {6:(92.8,92.8), 7:(108.2,108.2)}),
            (((240,350),(240,350),(260,350)), {6:(107.5,107.5), 7:(125.4,125.4)}),
        ],
    },
    "SP": {
        6: [
            (((160,190),(160,190),(180,210)), {6:(39.1,39.1), 7:(45.6,45.6)}),
            (((200,210),(200,210),(220,230)), {6:(44.9,44.9), 7:(52.4,52.4)}),
            (((220,230),(220,230),(240,250)), {6:(44.9,44.9), 7:(52.4,52.4)}),
            (((240,350),(240,350),(260,350)), {6:(52.2,52.2), 7:(60.9,60.9)}),
        ],
        8: [
            (((160,190),(160,190),(180,210)), {6:(65.5,65.5), 7:(76.5,76.5)}),
            (((200,210),(200,210),(220,230)), {6:(65.5,65.5), 7:(76.5,76.5)}),
            (((220,230),(220,230),(240,250)), {6:(79.9,79.9), 7:(93.2,93.2)}),
            (((240,350),(240,350),(260,350)), {6:(92.8,92.8), 7:(108.2,108.2)}),
        ],
    },
}

_DD_HIGH = {
    "HP": [
        (((170,170),(170,170),(190,190)), {10:{6:(124.8,124.8),7:(145.6,145.6)}}),
        (((180,200),(180,200),(200,220)), {10:{6:(124.8,124.8),7:(145.6,145.6)}, 12:{6:(179.7,179.7),7:(209.6,209.6)}}),
        (((210,210),(210,210),(230,230)), {10:{6:(144.9,144.9),7:(169.1,169.1)}, 12:{6:(179.7,179.7),7:(209.6,209.6)}}),
        (((220,240),(220,240),(240,260)), {10:{6:(144.9,144.9),7:(169.1,169.1)}, 12:{6:(208.7,208.7),7:(243.5,243.5)}}),
        (((250,350),(250,350),(270,350)), {10:{6:(167.9,167.9),7:(195.9,195.9)}, 12:{6:(208.7,208.7),7:(243.5,243.5)}}),
    ],
    "SP": [
        (((170,170),(170,170),(190,190)), {10:{6:(102.5,102.5),7:(119.6,119.6)}}),
        (((180,210),(180,210),(200,230)), {10:{6:(102.5,102.5),7:(119.6,119.6)}, 12:{6:(147.6,147.6),7:(172.2,172.2)}}),
        (((220,240),(220,240),(240,260)), {10:{6:(124.8,124.8),7:(145.6,145.6)}, 12:{6:(179.7,179.7),7:(209.6,209.6)}}),
        (((250,350),(250,350),(270,350)), {10:{6:(144.9,144.9),7:(169.1,169.1)}, 12:{6:(179.7,179.7),7:(209.6,209.6)}}),
    ],
}


def _dd_shear_options(series: str, height: int, cover: int, concrete: str) -> list[dict[str, Any]]:
    if cover not in COVERS:
        return []
    cover_index = COVERS.index(cover)
    ci = 0 if concrete == "C20/25" else 1
    out = []
    for dia, rows in _DD_LOW.get(series, {}).items():
        for spans, caps in rows:
            if not _in_range(height, spans[cover_index]):
                continue
            for yy, pair in caps.items():
                out.append({"yy": yy, "dia": dia, "vrd": pair[ci], "source_page": 106 if series == "HP" else 108})
    for spans, dia_map in _DD_HIGH.get(series, []):
        if not _in_range(height, spans[cover_index]):
            continue
        for dia, yy_map in dia_map.items():
            for yy, pair in yy_map.items():
                out.append({"yy": yy, "dia": dia, "vrd": pair[ci], "source_page": 106 if series == "HP" else 108})
    best = {}
    for row in out:
        key = (row["yy"], row["dia"])
        if key not in best or row["vrd"] > best[key]["vrd"]:
            best[key] = row
    return list(best.values())


# HALFEN HIT 20.2-EN 2023, p. 114: DVL/DDL shear capacities.
_DVL_SHEAR = {
    8: [
        (((160,190),(160,190),(180,210)), {6:79.8,7:93.1,8:106.4,9:119.7}),
        (((200,230),(200,230),(220,250)), {6:92.7,7:108.2,8:123.6,9:139.1}),
        (((240,250),(240,250),None), {6:107.4,7:125.3,8:143.2,9:161.1}),
    ],
    12: [
        (((180,210),(180,210),(200,230)), {5:149.7,6:179.6,7:209.5,8:239.5,9:269.4}),
        (((220,250),(220,250),(240,250)), {5:173.9,6:208.6,7:243.4,8:278.2,9:312.9}),
    ],
}


def _dvl_shear_options(height: int, cover: int) -> list[dict[str, Any]]:
    if cover not in COVERS:
        return []
    idx = COVERS.index(cover)
    out = []
    for dia, rows in _DVL_SHEAR.items():
        for spans, caps in rows:
            if not _in_range(height, spans[idx]):
                continue
            for yy, vrd in caps.items():
                out.append({"yy": yy, "dia": dia, "vrd": vrd, "source_page": 114})
    best = {}
    for row in out:
        key = (row["yy"], row["dia"])
        if key not in best or row["vrd"] > best[key]["vrd"]:
            best[key] = row
    return list(best.values())


class HitDatabase:
    def __init__(self, path: Path):
        text = path.read_text(encoding="ascii").strip()
        raw = gzip.decompress(base64.b64decode(text))
        self.data = json.loads(raw.decode("utf-8"))
        self.schema_version = int(self.data.get("schema_version", 1))
        self.source_document = str(self.data.get("source_document", "CONF-DOP HIT-HP/SP-07-23"))
        self.source_sha256 = str(self.data.get("source_sha256", ""))
        self.catalog_source = str(self.data.get("catalog_source", HIT_CATALOG_SOURCE))
        self.records = []
        concretes = self.data.get("concretes", list(CONCRETES))

        for heads, rows, page in self.data.get("sections", []):
            for head in heads:
                m = re.match(r"HIT-(HP|SP) MVX-(\d{4})-hh-(100|050|025)-cc(?:-(OD|OU|WD|WU))?$", head)
                if not m:
                    continue
                series, code, length, suffix = m.groups()
                for row in rows:
                    h = int(row[0])
                    vals = row[1:]
                    for ci, conc in enumerate(concretes):
                        m1, v1, m2, v2 = vals[ci * 4 : (ci + 1) * 4]
                        self.records.append([series, code, int(length), suffix or "", h, conc, m1, v1, m2, v2, page])

        self.zvx_records = list(self.data.get("zvx_records", []))
        self.dd_moment = list(self.data.get("dd_moment", []))
        self.dvl_moment = list(self.data.get("dvl_moment", []))
        self.mvxl_records = list(self.data.get("mvxl_records", []))

    @property
    def available_connection_types(self) -> tuple[str, ...]:
        if self.schema_version < 2:
            return ("MVX",)
        values = ["MVX"]
        if self.schema_version >= 3 and self.mvxl_records:
            values.append("MVXL")
        if self.zvx_records:
            values.extend(["ZVX", "ZDX"])
        if self.dd_moment:
            values.append("DD")
        if self.dvl_moment:
            values.extend(["DVL", "DDL"])
        return tuple(values)

    @staticmethod
    def _governing_direction(pos: float, neg: float, symbol: str) -> str:
        pos = abs(float(pos)); neg = abs(float(neg))
        if pos <= TOL and neg <= TOL:
            return symbol + "0"
        if pos > TOL and neg > TOL and abs(pos - neg) <= TOL:
            return symbol + "±"
        return symbol + ("+" if pos >= neg else "−")

    @staticmethod
    def _decorate_directional(rows: list[Candidate], prefix: str) -> list[Candidate]:
        return [replace(row, mode=f"{prefix} • {row.mode}") for row in rows]

    def directional_candidates(
        self, connection_type: str, series: str, height: int, cover: int, concrete: str,
        actions: DirectionalActions, lengths: set[int], include_offsets: bool = False,
    ):
        """Návrh z obálky M+/M-/V+/V-.

        Pro současné HIT se směrovost aplikuje přesně podle charakteru typu:
        MVX: pouze záporný moment, smyk ±; ZVX/DVL: jednosměrný smyk;
        ZDX/DD/DDL: oba směry. API je záměrně směrové, aby pozdější katalogy
        mohly mít rozdílné kladné a záporné únosnosti bez ztráty informace.
        """
        a = actions.normalized()
        typ = str(connection_type or "MVX").upper()
        series = str(series).upper()

        # Výslovně zadané samé nuly zachovají historické chování a nabídnou varianty s 0% využitím.
        if not a.has_any():
            return self.candidates(typ, series, height, cover, concrete, 0.0, 0.0, lengths, include_offsets)

        if typ == "MVX":
            if a.m_pos > TOL:
                return [], "MVX je v tomto DoP určen pro záporný moment; MEd+ musí být 0. Pro obousměrný moment zvolte odpovídající jiný typ."
            load_cases: list[tuple[str, float, float]] = []
            if a.v_pos > TOL:
                load_cases.append(("M−/V+", a.m_neg, a.v_pos))
            if a.v_neg > TOL:
                load_cases.append(("M−/V−", a.m_neg, a.v_neg))
            if not load_cases:
                load_cases.append(("M−", a.m_neg, 0.0))

            case_maps: list[tuple[str, dict[str, Candidate]]] = []
            for label, med, ved in load_cases:
                rows, error = self._mvx_candidates(series, height, cover, concrete, med, ved, lengths, include_offsets)
                if error:
                    return [], f"{label}: {error}"
                case_maps.append((label, {row.designation: row for row in rows}))

            common = set(case_maps[0][1])
            for _label, mapping in case_maps[1:]:
                common &= set(mapping)
            out: list[Candidate] = []
            for designation in common:
                checked = [(label, mapping[designation]) for label, mapping in case_maps]
                governing_label, governing = max(checked, key=lambda item: item[1].utilization)
                summary = ", ".join(f"{label} {fmt(row.utilization * 100.0)} %" for label, row in checked)
                out.append(replace(
                    governing,
                    utilization=max(row.utilization for _label, row in checked),
                    mode=f"obálka směrů • {summary} • rozhoduje {governing_label}: {governing.mode}",
                ))
            out.sort(key=lambda x: (-x.utilization, 0 if not x.suffix else 1, -x.length_code, x.code))
            return out, ""

        if typ == "MVXL":
            if a.m_pos > TOL:
                return [], "MVXL je v Annexu 5 navržen pro záporný moment; MEd+ musí být 0."
            return self._mvxl_candidates(series, height, cover, concrete, a.m_neg, a.v_pos, a.v_neg, lengths)

        if typ in {"ZVX", "ZDX"}:
            if a.m_pos > TOL or a.m_neg > TOL:
                return [], f"{typ} je smykový prvek; MEd+ i MEd− musí být 0."
            if typ == "ZVX" and a.v_pos > TOL and a.v_neg > TOL:
                return [], "ZVX přenáší smyk jedním směrem. Pro současné VEd+ i VEd− použijte ZDX nebo dva samostatně orientované prvky."
            ved = max(a.v_pos, a.v_neg)
            rows, error = self._zvx_candidates(typ, series, height, cover, concrete, 0.0, ved, lengths)
            if error:
                return rows, error
            vdir = self._governing_direction(a.v_pos, a.v_neg, "V")
            prefix = f"směrová kontrola • {'orientace ' if typ == 'ZVX' else 'rozhoduje '}{vdir}"
            return self._decorate_directional(rows, prefix), ""

        if typ == "DD":
            med = max(a.m_pos, a.m_neg)
            ved = max(a.v_pos, a.v_neg)
            rows, error = self._dd_candidates(series, height, cover, concrete, med, ved, lengths)
            if error:
                return rows, error
            mdir = self._governing_direction(a.m_pos, a.m_neg, "M")
            vdir = self._governing_direction(a.v_pos, a.v_neg, "V")
            return self._decorate_directional(rows, f"obálka ± • maxima {mdir}/{vdir}"), ""

        if typ in {"DVL", "DDL"}:
            if typ == "DVL" and a.v_pos > TOL and a.v_neg > TOL:
                return [], "DVL přenáší smyk jedním směrem. Pro současné VEd+ i VEd− použijte DDL."
            med = max(a.m_pos, a.m_neg)
            ved = max(a.v_pos, a.v_neg)
            rows, error = self._dvl_candidates(typ, series, height, cover, concrete, med, ved, lengths)
            if error:
                return rows, error
            mdir = self._governing_direction(a.m_pos, a.m_neg, "M")
            vdir = self._governing_direction(a.v_pos, a.v_neg, "V")
            orientation = "orientace" if typ == "DVL" else "maxima"
            return self._decorate_directional(rows, f"obálka směrů • {mdir} • {orientation} {vdir}"), ""

        return [], f"Typ HIT {typ} zatím není implementován."

    def candidates(self, connection_type: str, series: str, height: int, cover: int, concrete: str, med: float, ved: float, lengths: set[int], include_offsets: bool = False):
        typ = str(connection_type or "MVX").upper()
        series = str(series).upper()
        height = int(height)
        cover = int(cover)
        try:
            height_code(height)
        except ValueError as exc:
            return [], str(exc)
        if typ == "MVX":
            return self._mvx_candidates(series, height, cover, concrete, med, ved, lengths, include_offsets)
        if typ == "MVXL":
            return self._mvxl_candidates(series, height, cover, concrete, med, ved, 0.0, lengths)
        if self.schema_version < 2:
            return [], "Databáze HIT je ze starší verze. Obnovte ji ze spravovaného DoP."
        if typ in {"ZVX", "ZDX"}:
            return self._zvx_candidates(typ, series, height, cover, concrete, med, ved, lengths)
        if typ == "DD":
            return self._dd_candidates(series, height, cover, concrete, med, ved, lengths)
        if typ in {"DVL", "DDL"}:
            return self._dvl_candidates(typ, series, height, cover, concrete, med, ved, lengths)
        return [], f"Typ HIT {typ} zatím není implementován."

    def _mvx_candidates(self, series, height, cover, concrete, med, ved, lengths, include_offsets):
        htab = height - cover
        if htab < 0:
            return [], f"Výška h − krytí = {htab} mm není platná."
        q = math.inf if abs(ved) < 1e-12 else abs(med) / abs(ved)
        if abs(ved) > 1e-12 and q < float(self.data.get("ratio_min_m", RATIO_MIN_M)) - 1e-12:
            return [], f"Poměr |MEd| / |VEd| = {fmt(q, 3)} m je menší než požadovaných 0,150 m."
        out = []
        for r in self.records:
            s, code, L, suffix, h, conc, m1, v1, m2, v2, page = r
            if s != series or int(h) != htab or conc != concrete or int(L) not in lengths:
                continue
            if suffix and not include_offsets:
                continue
            u, mode = utilization(abs(med), abs(ved), abs(float(m1)), abs(float(v1)), abs(float(m2)), abs(float(v2)))
            if u <= 1.0 + 1e-9:
                out.append(Candidate(s, "MVX", code, int(L), suffix, int(h), conc, float(m1), float(v1), float(m2), float(v2), int(page), cover, height, u, mode, "CONF-DOP HIT-HP/SP-07-23, Annex 1/2"))
        out.sort(key=lambda x: (-x.utilization, 0 if not x.suffix else 1, -x.length_code, x.code))
        return out, ""


    def _equivalent_mvx_record(self, series: str, code: str, length_code: int, h_eff: int, concrete: str):
        for row in self.records:
            s, rcode, length, suffix, h, conc, m1, v1, m2, v2, page = row
            if (
                s == series and str(rcode) == str(code) and int(length) == int(length_code)
                and not suffix and int(h) == int(h_eff) and conc == concrete
            ):
                return row
        return None

    @staticmethod
    def _mvxl_value_for_height(record: dict[str, Any], h_eff: int, concrete: str):
        mrd = None
        bond = ""
        for row in record.get("mrd_rows", []):
            if int(row.get("h_eff", -1)) == int(h_eff):
                value = (row.get("values") or {}).get(concrete)
                if value is not None:
                    mrd = abs(float(value))
                    bond = str(row.get("bond") or ("good" if h_eff <= 300 else "poor"))
                break
        vrd_pos = None
        for span in record.get("vrd_pos_ranges", []):
            if int(span.get("h_min", -1)) <= int(h_eff) <= int(span.get("h_max", -1)):
                value = (span.get("values") or {}).get(concrete)
                if value is not None:
                    vrd_pos = abs(float(value))
                break
        return mrd, vrd_pos, bond

    def _mvxl_candidates(
        self, series: str, height: int, cover: int, concrete: str,
        m_neg: float, v_pos: float, v_neg: float, lengths: set[int],
    ):
        if self.schema_version < 3 or not self.mvxl_records:
            return [], "Databáze HIT neobsahuje Annex 5 MVXL. Obnovte ji ze spravovaného DoP."
        if not ({100, 50} & set(lengths)):
            return [], "MVXL je v Annexu 5 veden v délkách 1000 a 500 mm; povolte alespoň jednu z nich."
        h_eff = int(height) - int(cover)
        if h_eff < 0:
            return [], f"Výška h − krytí = {h_eff} mm není platná."

        m_neg = abs(float(m_neg)); v_pos = abs(float(v_pos)); v_neg = abs(float(v_neg))
        out: list[Candidate] = []
        missing_negative_source = False
        for record in self.mvxl_records:
            if record.get("series") != series or int(record.get("length_code", 0)) not in lengths:
                continue
            mrd, vrd_pos, bond = self._mvxl_value_for_height(record, h_eff, concrete)
            if not mrd or not vrd_pos:
                continue
            mu = 0.0 if m_neg <= TOL else m_neg / mrd
            up = max(mu, 0.0 if v_pos <= TOL else v_pos / vrd_pos)
            if up > 1.0 + 1e-9:
                continue

            mvx = self._equivalent_mvx_record(
                series, str(record["code"]), int(record["length_code"]), h_eff, concrete
            )
            m2_eff = 0.0
            v2_eff = 0.0
            un = mu
            neg_mode = ""
            mvx_page = None
            if v_neg > TOL:
                if mvx is None:
                    missing_negative_source = True
                    continue
                _s, _code, _L, _suffix, _h, _conc, mm1, vv1, mm2, vv2, mvx_page = mvx
                mm1 = abs(float(mm1)); vv1 = abs(float(vv1)); mm2 = abs(float(mm2)); vv2 = abs(float(vv2))
                m2_eff, v2_eff = mm2, vv2
                ratio = 0.0 if v_neg <= TOL else m_neg / v_neg
                if ratio <= RATIO_MIN_M + 1e-12:
                    if vv2 <= TOL:
                        continue
                    un = max(mu, v_neg / vv2)
                    neg_mode = f"V− přímá větev MVX V2 ({fmt(vv2)} kN/m; M/V={fmt(ratio,3)} m)"
                else:
                    un, mv_mode = utilization(m_neg, v_neg, mm1, vv1, mm2, vv2)
                    neg_mode = f"V− interakce MVX M1/V1–M2/V2 ({mv_mode})"
                if un > 1.0 + 1e-9:
                    continue
            elif mvx is not None:
                _s, _code, _L, _suffix, _h, _conc, _mm1, _vv1, mm2, vv2, mvx_page = mvx
                m2_eff, v2_eff = abs(float(mm2)), abs(float(vv2))

            u = max(up, un)
            parts = [
                f"MVXL Annex 5 • bond {bond} automaticky",
                f"M− {fmt(mu*100)} %",
            ]
            if v_pos > TOL:
                parts.append(f"V+ {fmt((v_pos/vrd_pos)*100)} %")
            if neg_mode:
                parts.append(neg_mode + f" = {fmt(un*100)} %")
            mode = " • ".join(parts)
            page = f"DoP {record['page']}" + (f" / MVX {mvx_page}" if mvx_page else "")
            note = (
                "MVXL: -MRd a +VRd z Annexu 5; good/poor bond se volí automaticky podle h-cnom. "
                "Zvedající V− se kontroluje proti odpovídajícímu MVX se stejným počtem tahových prutů a CSB."
            )
            out.append(Candidate(
                series, "MVXL", str(record["code"]), int(record["length_code"]), str(record["tail"]),
                h_eff, concrete, mrd, vrd_pos, m2_eff, v2_eff, page, cover, height, u, mode, note,
            ))

        if not out and v_neg > TOL and missing_negative_source:
            return [], "Pro zadané MVXL se nepodařilo dohledat odpovídající MVX pro kontrolu zvedajícího smyku."
        out = list({candidate.designation: candidate for candidate in out}.values())
        out.sort(key=lambda x: (-x.utilization, x.length_code != 100, x.code, x.suffix))
        return out, ""

    def _zvx_candidates(self, typ, series, height, cover, concrete, med, ved, lengths):
        if cover != 30:
            return [], f"{typ} je v ověřených tabulkách DoP veden s dolním krytím 30 mm."
        if abs(med) > 1e-9:
            return [], f"{typ} je smykový prvek; pro automatický návrh musí být MEd = 0."
        conc = _conc2(concrete)
        out = []
        for r in self.zvx_records:
            if r["series"] != series or r["concrete"] != conc or int(r["length_code"]) not in lengths:
                continue
            if not int(r["h_min"]) <= height <= int(r["h_max"]):
                continue
            vrd = abs(float(r["vrd"]))
            u = 0.0 if abs(ved) < 1e-12 else abs(ved) / vrd
            if u > 1.0 + 1e-9:
                continue
            mode = "smyk V • jednosměrný" if typ == "ZVX" else "smyk V • ± směr"
            out.append(Candidate(series, typ, str(r["code"]), int(r["length_code"]), str(r["diameter"]), height, concrete, 0.0, vrd, 0.0, vrd, int(r["page"]), cover, height, u, mode, "CONF-DOP HIT-HP/SP-07-23, Annex 3"))
        out.sort(key=lambda x: (-x.utilization, -x.length_code, int(x.suffix), x.code))
        return out, ""

    def _dd_candidates(self, series, height, cover, concrete, med, ved, lengths):
        if 100 not in lengths:
            return [], "Pro DD je v této verzi automaticky ověřena úplná 1000mm varianta; povolte délku 1000 mm."
        h_eff = height - cover
        conc = _conc2(concrete)
        allowed_xx = {"05", "07", "10", "12", "14"}
        moment_rows = [r for r in self.dd_moment if int(r["h_eff"]) == h_eff and r["concrete"] == conc and str(r["xx"]) in allowed_xx]
        if not moment_rows:
            return [], f"Pro DD není v DoP nalezena kombinace h−cnom = {h_eff} mm."
        shear_rows = _dd_shear_options(series, height, cover, conc)
        if not shear_rows:
            return [], f"Pro DD {series}, h={height} mm a cnom={cover} mm není v ověřené tabulce dostupná smyková varianta."
        out = []
        for mr in moment_rows:
            mrd = abs(float(mr["mrd"]))
            mu = 0.0 if abs(med) < 1e-12 else abs(med) / mrd
            if mu > 1.0 + 1e-9:
                continue
            for sr in shear_rows:
                vrd = abs(float(sr["vrd"]))
                vu = 0.0 if abs(ved) < 1e-12 else abs(ved) / vrd
                u = max(mu, vu)
                if u > 1.0 + 1e-9:
                    continue
                code = f"{int(mr['xx']):02d}{int(sr['yy']):02d}"
                mode = "M" if mu >= vu else "V"
                out.append(Candidate(series, "DD", code, 100, f"{int(sr['dia']):02d}", h_eff, concrete, mrd, vrd, mrd, vrd, f"DoP 101 / HIT20.2 {sr['source_page']}", cover, height, u, f"oddělená kontrola M/V • rozhoduje {mode}", "Moment: CONF-DOP Annex 4; smyk: HALFEN HIT 20.2-EN 2023"))
        out = list({c.designation: c for c in out}.values())
        out.sort(key=lambda x: (-x.utilization, int(x.suffix), x.code))
        return out, ""

    def _dvl_candidates(self, typ, series, height, cover, concrete, med, ved, lengths):
        if series != "HP":
            return [], f"{typ} je v Annexu 6 tohoto DoP uveden pouze jako HIT-HP."
        if 100 not in lengths:
            return [], f"Pro {typ} je v ověřených tabulkách použita 1000mm varianta; povolte délku 1000 mm."
        h_eff = height - cover
        conc = _conc2(concrete)
        allowed_xx = {"11", "13", "16"}
        moment_rows = [r for r in self.dvl_moment if int(r["h_eff"]) == h_eff and r["concrete"] == conc and str(r["xx"]) in allowed_xx]
        if not moment_rows:
            return [], f"Pro {typ} není v DoP nalezena kombinace h−cnom = {h_eff} mm."
        shear_rows = _dvl_shear_options(height, cover)
        if not shear_rows:
            return [], f"Pro {typ}, h={height} mm a cnom={cover} mm není v ověřené tabulce dostupná smyková varianta."
        out = []
        for mr in moment_rows:
            mrd = abs(float(mr["mrd"]))
            mu = 0.0 if abs(med) < 1e-12 else abs(med) / mrd
            if mu > 1.0 + 1e-9:
                continue
            for sr in shear_rows:
                vrd = abs(float(sr["vrd"]))
                vu = 0.0 if abs(ved) < 1e-12 else abs(ved) / vrd
                u = max(mu, vu)
                if u > 1.0 + 1e-9:
                    continue
                code = f"{int(mr['xx']):02d}{int(sr['yy']):02d}"
                direction = "jednosměrný smyk" if typ == "DVL" else "± smyk"
                mode = "M" if mu >= vu else "V"
                out.append(Candidate(series, typ, code, 100, f"{int(sr['dia']):02d}", h_eff, concrete, mrd, vrd, mrd, vrd, "DoP 123 / HIT20.2 114", cover, height, u, f"oddělená kontrola M/V • {direction} • rozhoduje {mode}", "Moment: CONF-DOP Annex 6; smyk: HALFEN HIT 20.2-EN 2023"))
        out = list({c.designation: c for c in out}.values())
        out.sort(key=lambda x: (-x.utilization, int(x.suffix), x.code))
        return out, ""


def _effective_balance_points(M1: float, V1: float, M2: float, V2: float, *, tol: float = 1e-9) -> tuple[float, float, float, float, str]:
    m1 = abs(float(M1)); v1 = abs(float(V1)); m2 = abs(float(M2)); v2 = abs(float(V2)); note = ""
    if m2 + tol < m1:
        if abs(v2 - v1) <= 1e-6 and (m1 - m2) <= 0.11 + tol:
            conservative_m = min(m1, m2); m1 = conservative_m; m2 = conservative_m
            note = "konzervativní normalizace zaokrouhlení DoP"
        else:
            raise ValueError(f"Neplatné pořadí bilančních bodů: M2={m2:g} < M1={m1:g}.")
    if v2 > v1 + tol:
        raise ValueError(f"Neplatné pořadí bilančních bodů: V2={v2:g} > V1={v1:g}.")
    return m1, v1, m2, v2, note


def utilization(M: float, V: float, M1: float, V1: float, M2: float, V2: float):
    """MVX utilization from the polygonal balance-point envelope on DoP page 3."""
    m = abs(float(M)); v = abs(float(V))
    if m < 1e-12 and v < 1e-12:
        return 0.0, "nulové zatížení"
    try:
        m1, v1, m2, v2, note = _effective_balance_points(M1, V1, M2, V2)
    except ValueError as exc:
        return math.inf, f"neplatné bilanční body • {exc}"
    checks = []
    if v1 > 1e-12: checks.append((v / v1, "V1"))
    elif v > 1e-12: return math.inf, "V1 = 0"
    if m2 > 1e-12: checks.append((m / m2, "M2"))
    elif m > 1e-12: return math.inf, "M2 = 0"
    dm = m2 - m1; dv = v1 - v2
    if dm > 1e-12 or dv > 1e-12:
        denominator = dv * m1 + dm * v1
        if denominator > 1e-12:
            checks.append(((dv * m + dm * v) / denominator, "interpolace M–V"))
    if not checks:
        return math.inf, "mimo obálku"
    eta, mode = max(checks, key=lambda item: item[0])
    if note: mode += " • " + note
    return eta, mode
