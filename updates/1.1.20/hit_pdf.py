from __future__ import annotations

"""Vector PDF report for direct Leviat HIT proposals.

The visual language intentionally follows the existing TURTO ISO substitution
report, but the semantics are proposal-specific: there is no "original product"
column. The report presents design inputs, the selected HIT, catalogue values,
utilization and any warnings/source notes.
"""

from datetime import datetime
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

import substitution_pdf_base as _base

PdfExportError = _base.PdfExportError
REPORT_VERSION = "1.1.20"
_TOL = 1e-9

_ACTION_META = {
    "m_pos": ("MEd+", "kNm/m"),
    "m_neg": ("MEd−", "kNm/m"),
    "n_pos": ("NEd+", "kN/m"),
    "n_neg": ("NEd−", "kN/m"),
    "v_pos": ("VEd+", "kN/m"),
    "v_neg": ("VEd−", "kN/m"),
    "h_parallel": ("HEd∥", "kN/prvek"),
    "h_perp": ("HEd⊥", "kN/prvek"),
}


def _text(value: Any) -> str:
    return str(value).replace("\u00a0", " ").strip() if value not in (None, "") else "—"


def _float(value: Any, default: float = float("nan")) -> float:
    try:
        return float(str(value).strip().replace(",", ".").replace("−", "-"))
    except (TypeError, ValueError):
        return default


def _num(value: Any, decimals: int = 1) -> str:
    number = _float(value)
    if math.isnan(number):
        return "—"
    if math.isinf(number):
        return "∞" if number > 0 else "−∞"
    return f"{number:.{decimals}f}".replace(".", ",")


def _percent(value: Any) -> str:
    n = _float(value)
    return "—" if math.isnan(n) else _num(100.0 * n, 1) + " %"


def _status(row: dict[str, Any]) -> str:
    return str(row.get("status", "NEPOSOUZENO") or "NEPOSOUZENO").strip().upper()


def _status_color(status: str) -> str:
    if status == "VYHOVUJE":
        return _base.SUCCESS
    if status in {"NELZE", "CHYBA", "NEVYHOVUJE"}:
        return _base.DANGER
    return _base.WARNING


def _candidate(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("candidate")
    return value if isinstance(value, dict) else {}


def _actions(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    data = row.get("actions") if isinstance(row.get("actions"), dict) else {}
    out: list[tuple[str, str, str]] = []
    for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg", "h_parallel", "h_perp"):
        raw = str(data.get(key, "") or "").strip()
        if not raw:
            continue
        label, unit = _ACTION_META[key]
        number = _float(raw)
        out.append((label, _num(number, 1) if math.isfinite(number) else raw, unit))
    return out


def _action_summary(row: dict[str, Any]) -> str:
    parts = [f"{label} {value} {unit}" for label, value, unit in _actions(row)]
    return " • ".join(parts) if parts else "bez zadaných účinků"


def _geometry_text(row: dict[str, Any]) -> str:
    variant = str(row.get("mvx_variant", "") or "").strip().upper()
    bx = str(row.get("bx_mm", "") or "").strip()
    if variant in {"OU", "OD"} and bx:
        return f"{variant}{bx}"
    return ""


def _input_summary(row: dict[str, Any], *, with_actions: bool = True) -> str:
    parts = [
        f"{_text(row.get('series'))} {_text(row.get('connection_type'))}",
        f"h {_text(row.get('height_mm'))} mm",
    ]
    cover = str(row.get("cover_mm", "") or "").strip()
    if cover and cover not in {"0", "—"}:
        parts.append(f"cnom {cover} mm")
    concrete = str(row.get("concrete", "") or "").strip()
    if concrete:
        parts.append(concrete)
    required = str(row.get("required_length_mm", "") or "").strip()
    if required:
        prefix = "B pož." if str(row.get("connection_type", "")).upper() == "HT" else "L pož."
        parts.append(f"{prefix} {required} mm")
    geometry = _geometry_text(row)
    if geometry:
        parts.append(geometry)
    if with_actions:
        parts.append(_action_summary(row))
    return " • ".join(parts)


class _ProposalReport(_base._Report):
    def __init__(self, rows: list[dict[str, Any]], project_name: str, creator: str):
        super().__init__(rows, project_name, creator)
        self.generated = datetime.now().strftime("%d.%m.%Y")

    def header(self, c, title: str, page: int, total: int):
        self.logo_draw(c)
        x, width = self.margin + 82, self.width - 82
        self.draw(c, self.p(title, size=16, bold=True, color=_base.NAVY), 15, x, width)
        self.draw(c, self.p(f"TURTO ISO  •  {self.generated}", color=_base.MUTED), 37, x, width)
        self.draw(c, self.p(self.project, bold=True), 54, x, width)
        c.setStrokeColor(self.b["colors"].HexColor(_base.GOLD)); c.setLineWidth(1.2)
        c.line(self.margin, self.h - self.top + 5, self.w - self.margin, self.h - self.top + 5)
        footer_y = self.h - 60
        c.setStrokeColor(self.b["colors"].HexColor(_base.BORDER)); c.setLineWidth(.5)
        c.line(self.margin, 64, self.w - self.margin, 64)
        self.draw(c, self.p(self.creator, size=10.5), footer_y, width=self.width - 90)
        self.draw(c, self.p(f"{page} / {total}", align=2), footer_y, self.w - self.margin - 80, 80)
        self.draw(
            c,
            self.p(
                "Předběžný katalogový návrh nosníků HIT. Nutno schválit statikem stavby.",
                size=10.5,
                color=_base.MUTED,
            ),
            footer_y + 16,
        )

    def summary_header(self):
        widths = [43., 166., 205., 70., self.width - 484.]
        labels = ["Poz.", "Zadání", "Navržený HIT", "Využití", "Výsledek"]
        return self.table(
            [[self.p(v, size=10.5, bold=True, color=_base.WHITE) for v in labels]],
            widths,
            background=_base.NAVY,
        ), widths

    def summary_row(self, row: dict[str, Any], index: int, widths: list[float]):
        candidate = _candidate(row)
        status = _status(row)
        if candidate:
            utilization = (
                "a max " + _num(candidate.get("spacing_max"), 3) + " m"
                if _float(candidate.get("spacing_max"), 0.0) > _TOL
                else _percent(candidate.get("utilization"))
            )
            designation = _text(candidate.get("designation"))
        else:
            utilization, designation = "—", "—"
        return self.table(
            [[
                self.p(row.get("name"), bold=True),
                self.p(_input_summary(row, with_actions=True), size=10.5),
                self.p(designation, bold=True),
                self.p(utilization, align=2, bold=True, color=_status_color(status)),
                self.p(status, align=2, bold=True, color=_status_color(status)),
            ]],
            widths,
            background=_base.WHITE if index % 2 == 0 else _base.PANEL,
            grid=True,
        )

    def summary_pages(self):
        header, widths = self.summary_header()
        ok = sum(_status(row) == "VYHOVUJE" for row in self.rows)
        failed = sum(_status(row) in {"NELZE", "NEVYHOVUJE", "CHYBA"} for row in self.rows)
        intro = self.p(
            f"{len(self.rows)} pozic  •  vyhovuje {ok}  •  nevyhovuje / nelze {failed}  •  k doplnění {len(self.rows) - ok - failed}",
            bold=True,
        )
        flows = [
            intro,
            self.p("Přímý návrh HIT z návrhových účinků a geometrických parametrů.", size=10.5, color=_base.MUTED),
            self.b["Spacer"](1, 6),
            header,
        ]
        y = self.top + sum(self.height(flow) for flow in flows)
        pages = []
        for index, row in enumerate(self.rows):
            flow = self.summary_row(row, index, widths)
            h = self.height(flow)
            if y + h > self.h - self.bottom:
                pages.append(("summary", flows))
                flows = [header]
                y = self.top + self.height(header)
            if y + h > self.h - self.bottom:
                flow.splitInRow = 1
                pieces = flow.split(self.width, self.h - self.bottom - y)
                if len(pieces) < 2:
                    raise PdfExportError(f"Souhrnný řádek {_text(row.get('name'))} je delší než stránka.")
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
            flows.append(flow); y += h
        pages.append(("summary", flows))
        return pages

    def _actions_table(self, row: dict[str, Any], width: float):
        values = _actions(row)
        if not values:
            return self.p("Návrhové účinky nejsou zadané.", color=_base.WARNING)
        widths = [95., 105., width - 200.]
        data = [[
            self.p("Účinek", size=10.5, bold=True, color=_base.NAVY),
            self.p("Hodnota", size=10.5, bold=True, color=_base.NAVY, align=2),
            self.p("Jednotka", size=10.5, bold=True, color=_base.NAVY),
        ]]
        for label, value, unit in values:
            data.append([self.p(label, bold=True), self.p(value, align=2), self.p(unit)])
        table = self.table(data, widths, grid=True)
        table.setStyle(self.b["TableStyle"]([("BACKGROUND", (0, 0), (-1, 0), self.b["colors"].HexColor(_base.PANEL))]))
        table.repeatRows = 1
        return table

    def _catalog_table(self, row: dict[str, Any], width: float):
        c = _candidate(row)
        if not c:
            return self.p("Katalogové hodnoty nejsou k dispozici.", color=_base.WARNING)
        typ = str(c.get("connection_type", "") or "").upper()
        if typ == "HT":
            entries = [
                ("HRd∥", c.get("m1"), "kN/prvek"),
                ("HRd⊥", c.get("v1"), "kN/prvek"),
            ]
        else:
            entries = [
                ("MRd / HRd∥,1", c.get("m1"), "kNm/m"),
                ("VRd / HRd⊥,1", c.get("v1"), "kN/m"),
                ("MRd,2", c.get("m2"), "kNm/m"),
                ("VRd,2", c.get("v2"), "kN/m"),
            ]
            if _float(c.get("nrd"), 0.0) > _TOL:
                entries.append(("NRd", c.get("nrd"), "kN/m"))
        widths = [160., 105., width - 265.]
        data = [[
            self.p("Katalogová hodnota", size=10.5, bold=True, color=_base.NAVY),
            self.p("Hodnota", size=10.5, bold=True, color=_base.NAVY, align=2),
            self.p("Jednotka", size=10.5, bold=True, color=_base.NAVY),
        ]]
        for label, value, unit in entries:
            data.append([self.p(label, bold=True), self.p(_num(value), align=2), self.p(unit)])
        table = self.table(data, widths, grid=True)
        table.setStyle(self.b["TableStyle"]([("BACKGROUND", (0, 0), (-1, 0), self.b["colors"].HexColor(_base.PANEL))]))
        table.repeatRows = 1
        return table

    def card_flows(self, row: dict[str, Any], refs: list[int]):
        width = self.width - 14
        status = _status(row)
        candidate = _candidate(row)
        flows = [
            self.p(f'<font color="{_base.TEAL}">Zadání: </font>' + _base.escape(_input_summary(row, with_actions=False)), markup=True),
            self._actions_table(row, width),
            self.b["Spacer"](1, 3),
        ]
        if candidate:
            flows.append(self.p(
                f'<font color="{_base.GOLD}">Navržený HIT: </font>' + _base.escape(_text(candidate.get("designation"))),
                bold=True,
                markup=True,
            ))
            length_label = "B" if str(candidate.get("connection_type", "")).upper() == "HT" else "L"
            geometry = (
                f"{length_label}: {_num(candidate.get('physical_length_mm'), 0)} mm  •  "
                f"h: {_num(candidate.get('height'), 0)} mm"
            )
            cover = _float(candidate.get("cover"), 0.0)
            if cover > 0:
                geometry += f"  •  cnom: {_num(cover, 0)} mm"
            geometry += f"  •  {_text(candidate.get('concrete'))}  •  zdroj {_text(candidate.get('page'))}"
            flows.append(self.p(geometry))
            variant = _geometry_text(row)
            if variant:
                flows.append(self.p(f"Geometrie MVX: {variant}", color=_base.TEAL))
            flows.append(self._catalog_table(row, width))
            spacing = _float(candidate.get("spacing_max"), 0.0)
            if spacing > _TOL:
                result_line = f"Výsledek: a max = {_num(spacing, 3)} m"
            else:
                result_line = f"Výsledek: η = {_percent(candidate.get('utilization'))}"
            flows.append(self.p(result_line + f"  •  {status}", bold=True, color=_status_color(status)))
            mode = str(candidate.get("mode", "") or "").strip()
            if mode:
                flows.append(self.p("Rozhodující kontrola: " + mode, size=10.5, color=_base.MUTED))
            source_note = str(candidate.get("source_note", "") or "").strip()
            if source_note:
                flows.append(self.p("Katalogový podklad: " + source_note, size=10.5, color=_base.MUTED))
        else:
            flows.append(self.p("Navržený HIT: —", bold=True, color=_base.WARNING))
            detail = str(row.get("detail", "") or "").strip()
            if detail:
                flows.append(self.p(detail, bold=True, color=_status_color(status)))

        source_text = str(row.get("import_source_text", "") or "").strip()
        if source_text:
            flows.append(self.p("Původní řádek výkazu: " + source_text, size=10.5, color=_base.MUTED))
        if refs:
            flows.append(self.p("Poznámky a omezení: " + ", ".join(f"[{v}]" for v in refs) + " (příloha).", size=10.5, color=_base.MUTED))
        return flows

    def card_title(self, card):
        title = _text(card.row.get("name"))
        if card.continued:
            title += "  •  pokračování"
        width = self.width - 14
        status = _status(card.row)
        return self.table(
            [[self.p(title, bold=True), self.p(status, bold=True, align=2, color=_status_color(status))]],
            [width - 151, 151],
            background=_base.PANEL,
            padding=2,
        )

    def write(self, path: Path):
        plan = self.summary_pages() + self.detail_pages() + self.notes_pages()
        c = self.b["Canvas"](str(path), pagesize=self.b["A4"], pageCompression=1)
        c.setTitle(f"TURTO ISO – Návrh HIT – {self.project}")
        c.setAuthor(self.creator)
        c.setCreator("TURTO ISO " + REPORT_VERSION)
        c.setSubject("Předběžný katalogový návrh nosníků Leviat HIT")
        detail_i = summary_i = notes_i = 0
        for index, (kind, items) in enumerate(plan, 1):
            title = {"summary": "Návrh nosníků HIT", "detail": "Statická kontrola návrhu HIT", "notes": "Poznámky a omezení"}[kind]
            self.header(c, title, index, len(plan)); y = self.top
            c.bookmarkPage(f"page{index}")
            if kind == "detail":
                detail_i += 1
                label = "Pozice " + ", ".join(_text(card.row.get("name")) for card in items)
                c.addOutlineEntry(label, f"page{index}", 0)
                for card in items:
                    y = self.card_draw(c, card, y) + 6
            else:
                if kind == "summary":
                    summary_i += 1; label = f"Souhrn návrhu – {summary_i}"
                else:
                    notes_i += 1; label = f"Poznámky – {notes_i}"
                c.addOutlineEntry(label, f"page{index}", 0)
                for flow in items:
                    y = self.draw(c, flow, y)
            if y > self.h - self.bottom + 6.2:
                raise PdfExportError("Obsah PDF přesahuje vyhrazenou tiskovou oblast.")
            c.showPage()
        c.save()
        return {"pages": len(plan), "summary_pages": summary_i, "detail_pages": detail_i, "notes_pages": notes_i}


def ensure_hit_pdf_backend() -> None:
    _base.ensure_vector_pdf_backend()


def write_hit_proposal_pdf(
    path: Path | str,
    *,
    project_name: str,
    rows: Iterable[dict[str, Any]],
    creator: str = "Vytvořil Ing. Jaroslav Kučera",
) -> Path:
    data = [dict(row) for row in rows]
    if not data:
        raise PdfExportError("Není co exportovat do PDF.")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    report = _ProposalReport(data, project_name, creator)
    fd, name = tempfile.mkstemp(prefix=".turto_hit_pdf_", suffix=".pdf", dir=str(target.parent))
    os.close(fd)
    temporary = Path(name)
    try:
        report.write(temporary)
        if temporary.stat().st_size < 1000:
            raise PdfExportError("PDF se nepodařilo vytvořit.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
