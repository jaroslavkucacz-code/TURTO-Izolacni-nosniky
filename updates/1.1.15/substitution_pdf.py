from __future__ import annotations

"""Readable, measured A4-portrait vector reports for TURTO ISO.

All engineering values are typeset at 11 points, without page or text scaling.
Pagination is measured from actual content. No result, name or warning is
ellipsized: long notes are indexed in the appendix and long cards continue.
"""

from dataclasses import dataclass
from datetime import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import site
import subprocess
import sys
import tempfile
from typing import Any, Iterable
from xml.sax.saxutils import escape

REPORT_VERSION = "1.1.15"
VALUE_FONT_SIZE = 11.0
BODY_FONT_SIZE = 11.0
LABEL_FONT_SIZE = 10.5
_REPORTLAB_REQUIREMENT = "reportlab>=4.2,<5"
_BACKEND = None

NAVY = "#17324D"
TEAL = "#0E6E8E"
GOLD = "#B88B30"
TEXT = "#1B222C"
MUTED = "#526173"
BORDER = "#CCD6DF"
PANEL = "#F3F6F8"
WHITE = "#FFFFFF"
SUCCESS = "#246E49"
WARNING = "#8B5B10"
DANGER = "#A42C37"


class PdfExportError(RuntimeError):
    pass


def _install_reportlab() -> None:
    if getattr(sys, "frozen", False):
        raise PdfExportError("V instalaci programu chybí ReportLab. Opravte instalaci TURTO ISO.")
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"]
    if getattr(sys, "base_prefix", sys.prefix) == sys.prefix:
        cmd.append("--user")
    cmd.append(_REPORTLAB_REQUIREMENT)
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if completed.returncode:
            raise RuntimeError((completed.stderr or completed.stdout)[-1600:])
        site.addsitedir(site.getusersitepackages())
        importlib.invalidate_caches()
    except Exception as exc:
        raise PdfExportError(
            "ReportLab není dostupný a automatická instalace selhala.\n"
            f'Ruční instalace: "{sys.executable}" -m pip install reportlab\n{exc}'
        ) from exc


def _load_backend():
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    if importlib.util.find_spec("reportlab") is None:
        _install_reportlab()
    try:
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Table, TableStyle, Spacer
    except Exception as exc:
        raise PdfExportError(f"Nelze načíst vektorový PDF modul: {exc}") from exc
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    pairs = [
        (windows / "calibri.ttf", windows / "calibrib.ttf"),
        (windows / "arial.ttf", windows / "arialbd.ttf"),
        (windows / "aptos.ttf", windows / "aptos-bold.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
        (Path("/Library/Fonts/Arial.ttf"), Path("/Library/Fonts/Arial Bold.ttf")),
    ]
    names = None
    for i, (regular, bold) in enumerate(pairs):
        if not (regular.exists() and bold.exists()):
            continue
        try:
            r, b = f"TurtoReport{i}", f"TurtoReportBold{i}"
            for name, path in ((r, regular), (b, bold)):
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, str(path)))
            pdfmetrics.registerFontFamily(r, normal=r, bold=b, italic=r, boldItalic=b)
            names = r, b
            break
        except Exception:
            continue
    if names is None:
        raise PdfExportError("Chybí použitelné písmo pro češtinu. Nainstalujte Calibri, Arial, Aptos nebo DejaVu Sans.")
    _BACKEND = dict(Canvas=Canvas, colors=colors, A4=A4, ParagraphStyle=ParagraphStyle,
                    Paragraph=Paragraph, Table=Table, TableStyle=TableStyle, Spacer=Spacer,
                    regular=names[0], bold=names[1], pdfmetrics=pdfmetrics)
    return _BACKEND


def ensure_vector_pdf_backend() -> None:
    _load_backend()


def _text(value: Any) -> str:
    return str(value).replace("\u00a0", " ").strip() if value not in (None, "") else "—"


def _float(value: Any, default: float = float("nan")) -> float:
    try:
        return float(str(value).replace(",", ".").replace("−", "-"))
    except (ValueError, TypeError):
        return default


def _num(value: Any, decimals: int = 1) -> str:
    n = _float(value)
    if math.isnan(n):
        return "—"
    if math.isinf(n):
        return "∞" if n > 0 else "−∞"
    return f"{n:.{decimals}f}".replace(".", ",")


def _percent(value: Any) -> str:
    return _num(_float(value) * 100) + " %" if not math.isnan(_float(value)) else "—"


def _target(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("target") if isinstance(row.get("target"), dict) else {}


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("source_meta") if isinstance(row.get("source_meta"), dict) else {}


def _checks(row: dict[str, Any]) -> list[dict[str, Any]]:
    target = _target(row)
    checks = target.get("checks")
    if isinstance(checks, list) and any(isinstance(x, dict) for x in checks):
        return [dict(x) for x in checks if isinstance(x, dict)]
    # Missing directional results are not fabricated from aggregate maxima.
    actions = row.get("source_actions") or {}
    out = []
    for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg"):
        v = _float(actions.get(key), 0.0)
        if v > 0:
            out.append(dict(label=key[0].upper() + ("+" if key.endswith("pos") else "−"),
                            requirement=v, capacity=None, eta=None,
                            unit="kNm/prvek" if key[0] == "m" else "kN/prvek", result="NEPOSOUZENO"))
    return out


def _interaction_applies(row: dict[str, Any]) -> bool:
    t = _target(row)
    actions = t.get("actions") or row.get("source_actions") or {}
    return (t.get("connection_type") in {"MVX", "MVXL"}
            and max(_float(actions.get(k), 0) for k in ("m_pos", "m_neg")) > 0
            and max(_float(actions.get(k), 0) for k in ("v_pos", "v_neg")) > 0)


def _governing_check(row: dict[str, Any]) -> tuple[str, float]:
    t = _target(row)
    if not t:
        return "—", float("nan")
    options = [(_text(c.get("label")), _float(c.get("eta"))) for c in _checks(row)]
    options = [(label, n) for label, n in options if not math.isnan(n)]
    if _interaction_applies(row):
        options.append(("M/V", _float(t.get("interaction_utilization"))))
    options = [x for x in options if not math.isnan(x[1])]
    overall = _float(t.get("utilization"))
    if not math.isnan(overall) and (not options or overall > max(x[1] for x in options) + 1e-8):
        options.append(("η max", overall))
    options = [x for x in options if not math.isnan(x[1])]
    return max(options, key=lambda x: x[1]) if options else ("—", float("nan"))


def _status(row: dict[str, Any]) -> str:
    status = _text(row.get("status", "NEPOSOUZENO"))
    if status == "VYHOVUJE" and (not _target(row) or any(math.isnan(_float(c.get("eta"))) for c in _checks(row))):
        return "NEPOSOUZENO"
    if _governing_check(row)[1] > 1.0 + 1e-9:
        return "NEVYHOVUJE"
    return status


def _status_color(status: str) -> str:
    if status == "VYHOVUJE":
        return SUCCESS
    if status in {"NELZE", "CHYBA", "NEVYHOVUJE"}:
        return DANGER
    return WARNING


def _pressure(value: Any) -> str:
    text = _text(value).lower()
    if "bez" in text and ("ložis" in text or "csb" in text):
        return "bez ložisek / tlačené pruty" if "prut" in text else "bez ložisek"
    if "ložis" in text or "csb" in text:
        return "s ložisky"
    return _text(value)


@dataclass
class _Card:
    row: dict[str, Any]
    flows: list[Any]
    continued: bool = False


class _Report:
    def __init__(self, rows: list[dict[str, Any]], project_name: str, creator: str):
        self.b = _load_backend()
        self.rows = rows
        self.project = _text(project_name)
        self.creator = _text(creator)
        self.generated = datetime.now().strftime("%d.%m.%Y %H:%M")
        self.w, self.h = self.b["A4"]
        self.margin = 24.0
        self.width = self.w - 2 * self.margin
        self.bottom = 70.0
        self.logo = self._load_logo()
        self.note_index: dict[str, int] = {}
        self.note_positions: dict[int, list[str]] = {}
        self.row_refs: list[list[int]] = []
        for row in rows:
            refs = []
            for note in row.get("notes") or []:
                text = _text(note)
                if text in {"", "—"}:
                    continue
                number = self.note_index.setdefault(text, len(self.note_index) + 1)
                if number not in refs:
                    refs.append(number)
                positions = self.note_positions.setdefault(number, [])
                if _text(row.get("position")) not in positions:
                    positions.append(_text(row.get("position")))
            self.row_refs.append(refs)
        project_h = self.p(self.project, bold=True).wrap(self.width - 86, 10000)[1]
        self.top = max(88.0, 55.0 + project_h + 8)
        if self.top > 220:
            raise PdfExportError("Název projektu je pro záhlaví příliš dlouhý. Zkraťte jej prosím.")

    def _load_logo(self) -> dict[str, Any]:
        path = Path(__file__).resolve().parent / "assets" / "turto_logo_vector.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not data.get("shapes") or data["width"] <= 0 or data["height"] <= 0:
                raise ValueError("neplatný obsah loga")
            return data
        except Exception as exc:
            raise PdfExportError(f"Chybí vektorové logo TURTO ({path.name}); dokončete aktualizaci programu.\n{exc}") from exc

    def p(self, text: Any, *, size: float = BODY_FONT_SIZE, bold: bool = False,
          color: str = TEXT, align: int = 0, markup: bool = False):
        style = self.b["ParagraphStyle"](
            "report", fontName=self.b["bold"] if bold else self.b["regular"],
            fontSize=size, leading=size + 1.6, textColor=self.b["colors"].HexColor(color),
            spaceAfter=0, spaceBefore=0, alignment=align, splitLongWords=1,
            allowWidows=1, allowOrphans=1,
        )
        safe = str(text) if markup else escape(_text(text)).replace("\n", "<br/>")
        return self.b["Paragraph"](safe, style)

    def table(self, data: list, widths: list[float], *, header: bool = False, background=None,
              padding: float = 3, grid: bool = False):
        t = self.b["Table"](data, colWidths=widths, hAlign="LEFT")
        commands = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), padding), ("RIGHTPADDING", (0, 0), (-1, -1), padding),
                    ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]
        if background:
            commands.append(("BACKGROUND", (0, 0), (-1, -1), self.b["colors"].HexColor(background)))
        if grid:
            commands.append(("LINEBELOW", (0, 0), (-1, -1), .35, self.b["colors"].HexColor(BORDER)))
        t.setStyle(self.b["TableStyle"](commands))
        return t

    def height(self, flow, width: float | None = None) -> float:
        return flow.wrap(self.width if width is None else width, 100000)[1]

    def draw(self, canvas, flow, y: float, x: float | None = None, width: float | None = None) -> float:
        h = self.height(flow, width)
        flow.drawOn(canvas, self.margin if x is None else x, self.h - y - h)
        return y + h

    def logo_draw(self, c):
        data = self.logo
        scale = min(67 / data["width"], 64 / data["height"])
        x, y = self.margin, 15
        for shape in data["shapes"]:
            c.setFillColor(self.b["colors"].HexColor(shape["fill"]))
            for group in shape["groups"]:
                path = c.beginPath()
                for loop in group:
                    if not loop:
                        continue
                    path.moveTo(x + loop[0][0] * scale, self.h - y - loop[0][1] * scale)
                    for xx, yy in loop[1:]:
                        path.lineTo(x + xx * scale, self.h - y - yy * scale)
                    path.close()
                c.drawPath(path, stroke=0, fill=1, fillMode=0)

    def header(self, c, title: str, page: int, total: int):
        self.logo_draw(c)
        x, width = self.margin + 82, self.width - 82
        self.draw(c, self.p(title, size=16, bold=True, color=NAVY), 15, x, width)
        self.draw(c, self.p(f"TURTO ISO  •  {self.generated}", color=MUTED), 37, x, width)
        self.draw(c, self.p(self.project, bold=True), 54, x, width)
        c.setStrokeColor(self.b["colors"].HexColor(GOLD)); c.setLineWidth(1.2)
        c.line(self.margin, self.h - self.top + 5, self.w - self.margin, self.h - self.top + 5)
        footer_y = self.h - 60
        c.setStrokeColor(self.b["colors"].HexColor(BORDER)); c.setLineWidth(.5)
        c.line(self.margin, 64, self.w - self.margin, 64)
        self.draw(c, self.p(self.creator, size=10.5), footer_y, width=self.width - 90)
        self.draw(c, self.p(f"{page} / {total}", align=2), footer_y, self.w - self.margin - 80, 80)
        self.draw(c, self.p("Předběžná katalogová záměna M/N/V a základní geometrie. Nutno schválit statikem stavby.",
                            size=10.5, color=MUTED), footer_y + 16)

    def summary_header(self):
        widths = [43., 30., 182., 198., self.width - 453.]
        labels = ["Poz.", "Ks", "Původní prvek", "Navržený HIT", "Kontrola"]
        return self.table([[self.p(v, size=10.5, bold=True, color=WHITE) for v in labels]], widths, background=NAVY), widths

    def summary_row(self, row, index, widths):
        t = _target(row)
        label, eta = _governing_check(row)
        status = _status(row)
        control = (f"{escape(label)} {_percent(eta)}<br/>" if not math.isnan(eta) else "") + escape(status)
        return self.table([[self.p(row.get("position"), bold=True), self.p(row.get("quantity"), align=1),
                            self.p(row.get("source")), self.p(t.get("designation") if t else "—", bold=True),
                            self.p(control, color=_status_color(status), markup=True)]], widths,
                          background=WHITE if index % 2 == 0 else PANEL, grid=True)

    def summary_pages(self):
        header, widths = self.summary_header()
        quantities = sum(_float(r.get("quantity"), 0) for r in self.rows)
        ok = sum(_status(r) == "VYHOVUJE" for r in self.rows)
        intro = self.p(f"{len(self.rows)} pozic  •  {_num(quantities, 0)} ks  •  vyhovuje {ok}  •  k posouzení {len(self.rows) - ok}", bold=True)
        flows = [intro, self.p("Porovnání katalogových únosností jednoho prvku za jeden HIT.", size=10.5, color=MUTED), self.b["Spacer"](1, 6), header]
        y = self.top + sum(self.height(f) for f in flows)
        pages = []
        for i, row in enumerate(self.rows):
            f = self.summary_row(row, i, widths)
            rh = self.height(f)
            if y + rh > self.h - self.bottom:
                pages.append(("summary", flows))
                flows = [header]; y = self.top + self.height(header)
            if y + rh > self.h - self.bottom:
                # Do not compress a pathological long description. Split its table row.
                f.splitInRow = 1
                pieces = f.split(self.width, self.h - self.bottom - y)
                if len(pieces) < 2:
                    raise PdfExportError(f"Souhrnný řádek {_text(row.get('position'))} je delší než stránka.")
                pending = pieces
                while pending:
                    part = pending.pop(0)
                    ph = self.height(part)
                    if y + ph > self.h - self.bottom:
                        more = part.split(self.width, self.h - self.bottom - y)
                        if not more:
                            raise PdfExportError("Velmi dlouhý souhrnný řádek nelze rozdělit.")
                        pending = more + pending
                        continue
                    flows.append(part); y += ph
                    if pending:
                        pages.append(("summary", flows)); flows = [header]; y = self.top + self.height(header)
                continue
            flows.append(f); y += rh
        pages.append(("summary", flows))
        return pages

    def checks_table(self, row, width):
        widths = [55., 96., 110., 106., width - 367.]
        labels = ["Účinek", "Požadavek", "Únosnost HIT", "Jednotka", "Využití η"]
        values = [[self.p(v, size=10.5, bold=True, color=NAVY) for v in labels]]
        for check in _checks(row):
            eta = _float(check.get("eta"))
            values.append([self.p(check.get("label"), bold=True),
                           self.p(_num(check.get("requirement")), align=2),
                           self.p(_num(check.get("capacity")), align=2),
                           self.p(check.get("unit")),
                           self.p(_percent(eta), bold=True, align=2,
                                  color=MUTED if math.isnan(eta) else (SUCCESS if eta <= 1 + 1e-9 else DANGER))])
        if len(values) == 1:
            return self.p("Směrová statická kontrola není k dispozici.", color=WARNING)
        t = self.table(values, widths, grid=True)
        t.setStyle(self.b["TableStyle"]([("BACKGROUND", (0,0),(-1,0),self.b["colors"].HexColor(PANEL))]))
        t.repeatRows = 1
        return t

    def card_flows(self, row, refs):
        t, m = _target(row), _meta(row)
        width = self.width - 14
        flows = [self.p(f'<font color="{TEAL}">Původní: </font>' + escape(_text(row.get("source"))), markup=True),
                 self.p(f'<font color="{GOLD}">HIT: </font>' + escape(_text(t.get("designation")) if t else "Bez navrženého HIT"), bold=True, markup=True)]
        src = [m.get("source_insulation_mm"), m.get("source_height_mm"), m.get("source_cover_mm")]
        dst = [t.get("target_insulation_mm", src[0]), t.get("height_mm", src[1]), t.get("cover_mm", src[2])]
        vals = [_num(v, 0) if v == d or not t else f"{_num(v,0)}→{_num(d,0)}" for v, d in zip(src,dst)]
        lsrc, ldst = m.get("source_length_mm"), t.get("length_mm")
        length = _num(lsrc,0) if not t or lsrc == ldst else f"{_num(lsrc,0)}→{_num(ldst,0)}"
        concrete = _text(m.get("source_concrete"))
        if t.get("concrete") and concrete != _text(t.get("concrete")):
            concrete += "→" + _text(t["concrete"])
        flows.append(self.p(f"I/h/cnom: {' / '.join(vals)} mm  •  L: {length} mm  •  {concrete}"))
        pressure = _pressure(m.get("source_compression_text"))
        dest_pressure = _pressure(t.get("compression_text")) if t else "—"
        if pressure != dest_pressure:
            pressure += " → " + dest_pressure
        flows.append(self.p(f"Tlakový přenos: {pressure}", size=10.5, color=MUTED))
        if m.get("geometry_display"):
            flows.append(self.p("Geometrie: " + _text(m["geometry_display"]), color=TEAL))
        if row.get("acceptance_text"):
            flows.append(self.p(_text(row["acceptance_text"]), color=SUCCESS))
        if t and lsrc != ldst and t.get("length_relation"):
            flows.append(self.p(_text(t["length_relation"]), size=10.5, color=MUTED))
        flows.append(self.b["Spacer"](1,3))
        flows.append(self.checks_table(row, width))
        if t:
            label, eta = _governing_check(row)
            line = f"Rozhoduje {label}: η = {_percent(eta)}"
            line += " ≤ 100 %" if eta <= 1.0 + 1e-9 else (" > 100 %" if not math.isnan(eta) else "")
            if _interaction_applies(row) and label != "M/V":
                line += f"  •  interakce M/V: {_percent(t.get('interaction_utilization'))}"
            if _float(t.get("spacing_max_m"),0) > 0:
                line += f"  •  a max = {_num(t.get('spacing_max_m'),3)} m"
            flows.append(self.p(line, bold=True, color=_status_color(_status(row))))
        if refs:
            flows.append(self.p("Poznámky a omezení: " + ", ".join(f"[{v}]" for v in refs) + " (příloha).", size=10.5, color=MUTED))
        return flows

    def card_title(self, card):
        title = f"{_text(card.row.get('position'))}  •  {_text(card.row.get('quantity'))} ks"
        if card.continued:
            title += "  •  pokračování"
        w = self.width - 14
        return self.table([[self.p(title, bold=True), self.p(_status(card.row), bold=True, align=2, color=_status_color(_status(card.row)))]],
                          [w-151,151], background=PANEL, padding=2)

    def card_height(self, card):
        w = self.width - 14
        return 9 + self.height(self.card_title(card),w) + sum(self.height(f,w) for f in card.flows)

    def detail_pages(self):
        capacity = self.h - self.bottom - self.top
        cards = []
        for row,refs in zip(self.rows,self.row_refs):
            card = _Card(row, self.card_flows(row,refs))
            if self.card_height(card) <= capacity:
                cards.append(card); continue
            # Unusually long data are continued at the same font size.
            remaining = list(card.flows)
            current = _Card(row,[])
            while remaining:
                f = remaining.pop(0)
                room = capacity - self.card_height(current)
                if self.height(f,self.width-14) <= room:
                    current.flows.append(f); continue
                pieces = f.split(self.width-14,room)
                if pieces:
                    current.flows.append(pieces[0]); remaining = pieces[1:] + remaining
                else:
                    remaining.insert(0,f)
                if not current.flows:
                    raise PdfExportError(f"Pozici {_text(row.get('position'))} nelze zalomit při velikosti písma 11 pt.")
                cards.append(current);current=_Card(row,[],True)
            if current.flows:
                cards.append(current)
        pages=[]; chunk=[]; used=0.
        for card in cards:
            h=self.card_height(card)
            gap=6 if chunk else 0
            if chunk and (len(chunk)>=4 or used+gap+h>capacity):
                pages.append(("detail",chunk));chunk=[];used=0;gap=0
            chunk.append(card); used+=gap+h
        if chunk:pages.append(("detail",chunk))
        return pages

    def notes_pages(self):
        if not self.note_index:
            return []
        pending=[]
        for text,number in self.note_index.items():
            positions=", ".join(self.note_positions[number])
            pending.extend([self.p(f"[{number}]  Pozice: {positions}",bold=True),self.p(text,size=10.5),self.b["Spacer"](1,8)])
        pages=[];flows=[];y=self.top
        while pending:
            f=pending.pop(0);h=self.height(f)
            if y+h<=self.h-self.bottom:
                flows.append(f);y+=h;continue
            pieces=f.split(self.width,self.h-self.bottom-y)
            if pieces:
                flows.append(pieces[0]);pending=pieces[1:]+pending
            else:
                pending.insert(0,f)
            if not flows:
                raise PdfExportError("Poznámku nelze vysázet do PDF.")
            pages.append(("notes",flows));flows=[];y=self.top
        if flows:pages.append(("notes",flows))
        return pages

    def card_draw(self,c,card,y):
        h=self.card_height(card);w=self.width
        c.setStrokeColor(self.b["colors"].HexColor(BORDER)); c.setLineWidth(.5)
        c.rect(self.margin,self.h-y-h,w,h,stroke=1,fill=0)
        c.setStrokeColor(self.b["colors"].HexColor(_status_color(_status(card.row))));c.setLineWidth(2)
        c.line(self.margin,self.h-y,self.margin,self.h-y-h)
        yy=self.draw(c,self.card_title(card),y+3,self.margin+7,w-14)
        for f in card.flows:
            yy=self.draw(c,f,yy,self.margin+7,w-14)
        if yy > y+h+0.1:
            raise PdfExportError("Vnitřní chyba stránkování: obsah přesahuje výšku karty.")
        return y+h

    def write(self,path:Path):
        plan=self.summary_pages()+self.detail_pages()+self.notes_pages()
        c=self.b["Canvas"](str(path),pagesize=self.b["A4"],pageCompression=1)
        c.setTitle(f"TURTO ISO – Tabulka záměn – {self.project}")
        c.setAuthor(self.creator);c.setCreator("TURTO ISO " + REPORT_VERSION)
        c.setSubject("Předběžná katalogová záměna izolačních nosníků za HIT")
        detail_i=summary_i=notes_i=0
        for index,(kind,items) in enumerate(plan,1):
            title={"summary":"Tabulka záměn za HIT","detail":"Statická kontrola záměn","notes":"Poznámky a omezení"}[kind]
            self.header(c,title,index,len(plan));y=self.top
            c.bookmarkPage(f"page{index}")
            if kind=="detail":
                detail_i+=1
                label="Pozice " + ", ".join(_text(card.row.get("position")) for card in items)
                c.addOutlineEntry(label,f"page{index}",0)
                for card in items:y=self.card_draw(c,card,y)+6
            else:
                if kind=="summary":summary_i+=1;label=f"Souhrn záměn – {summary_i}"
                else:notes_i+=1;label=f"Poznámky – {notes_i}"
                c.addOutlineEntry(label,f"page{index}",0)
                for flow in items:y=self.draw(c,flow,y)
            if y > self.h-self.bottom+6.2:
                raise PdfExportError("Obsah PDF přesahuje vyhrazenou tiskovou oblast.")
            c.showPage()
        c.save()
        return {"pages":len(plan),"summary_pages":summary_i,"detail_pages":detail_i,"notes_pages":notes_i,
                "detail_positions_per_page":[len(items) for kind,items in plan if kind=="detail"],
                "numeric_font_pt":VALUE_FONT_SIZE,"body_font_pt":BODY_FONT_SIZE}


def write_substitution_pdf(path: Path | str, *, project_name: str, rows: Iterable[dict[str, Any]],
                           creator: str = "Vytvořil Ing. Jaroslav Kučera") -> Path:
    """Export with stable API. Atomic save keeps an existing PDF safe on failure."""
    data=list(rows)
    if not data:
        raise PdfExportError("Není co exportovat do PDF.")
    if not all(isinstance(row,dict) for row in data):
        raise PdfExportError("Neplatný formát řádků pro export.")
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    report=_Report(data,project_name,creator)
    fd,name=tempfile.mkstemp(prefix=".turto_pdf_",suffix=".pdf",dir=str(target.parent))
    os.close(fd);temporary=Path(name)
    try:
        report.write(temporary)
        if temporary.stat().st_size < 1000:
            raise PdfExportError("PDF se nepodařilo vytvořit.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
