from __future__ import annotations

"""TURTO ISO 1.1.27 unified PDF presentation for all HIT proposal groups."""

import math
from typing import Any

import hit_pdf_prev as _prev
from hit_pdf_prev import *  # noqa: F401,F403

REPORT_VERSION = "1.1.27"
_prev.REPORT_VERSION = REPORT_VERSION
_base = _prev._base
_TOL = _prev._TOL

_ORIGINAL_ACTIONS = _prev._actions
_ORIGINAL_INPUT = _prev._input_summary
_ORIGINAL_CATALOG_TABLE = _prev._ProposalReport._catalog_table
_ORIGINAL_CARD_FLOWS = _prev._ProposalReport.card_flows


def _actions(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    custom = row.get("custom_actions")
    if isinstance(custom, list):
        out: list[tuple[str, str, str]] = []
        for item in custom:
            if not isinstance(item, dict):
                continue
            raw = item.get("value")
            number = _prev._float(raw)
            if math.isnan(number) or abs(number) <= _TOL:
                continue
            out.append((
                str(item.get("label", "") or "Účinek"),
                _prev._num(number, 1),
                str(item.get("unit", "") or ""),
            ))
        return out
    return _ORIGINAL_ACTIONS(row)


def _input_summary(row: dict[str, Any], *, with_actions: bool = True) -> str:
    if str(row.get("group", "")).strip() == "Stěny WT" or str(row.get("connection_type", "")).upper() == "WT":
        parts = [
            f"{_prev._text(row.get('series'))} WT",
            f"h stěny {_prev._text(row.get('height_mm'))} mm",
            f"B {_prev._text(row.get('required_length_mm'))} mm",
        ]
        concrete = str(row.get("concrete", "") or "").strip()
        if concrete:
            parts.append(concrete)
        if with_actions:
            parts.append(" • ".join(f"{a} {v} {u}" for a, v, u in _actions(row)) or "bez zadaných účinků")
        return " • ".join(parts)
    return _ORIGINAL_INPUT(row, with_actions=with_actions)


def _catalog_table(self, row: dict[str, Any], width: float):
    candidate = _prev._candidate(row)
    if not candidate:
        return self.p("Katalogové hodnoty nejsou k dispozici.", color=_base.WARNING)
    typ = str(candidate.get("connection_type", "") or "").upper()

    if typ == "WT":
        entries = [
            ("MRd", candidate.get("mrd"), "kNm/prvek"),
            ("VRd,v", candidate.get("vrd_vertical"), "kN/prvek"),
            ("VRd,h", candidate.get("vrd_horizontal"), "kN/prvek"),
            ("s_joint max.", candidate.get("joint_spacing_m"), "m"),
        ]
    elif typ in {"AT", "FT", "OTX"}:
        entries = []
        if _prev._float(candidate.get("m1"), 0.0) > _TOL:
            entries.append(("MRd", candidate.get("m1"), "kNm/m"))
        if _prev._float(candidate.get("nrd"), 0.0) > _TOL:
            entries.append(("NRd", candidate.get("nrd"), "kN/m"))
        if _prev._float(candidate.get("v1"), 0.0) > _TOL:
            entries.append(("VRd", candidate.get("v1"), "kN/m"))
        if _prev._float(candidate.get("spacing_max"), 0.0) > _TOL:
            entries.append(("a max", candidate.get("spacing_max"), "m"))
    else:
        return _ORIGINAL_CATALOG_TABLE(self, row, width)

    widths = [160.0, 105.0, width - 265.0]
    data = [[
        self.p("Katalogová hodnota", size=10.5, bold=True, color=_base.NAVY),
        self.p("Hodnota", size=10.5, bold=True, color=_base.NAVY, align=2),
        self.p("Jednotka", size=10.5, bold=True, color=_base.NAVY),
    ]]
    for label, value, unit in entries:
        decimals = 3 if unit == "m" and label == "a max" else 1
        data.append([self.p(label, bold=True), self.p(_prev._num(value, decimals), align=2), self.p(unit)])
    table = self.table(data, widths, grid=True)
    table.setStyle(self.b["TableStyle"]([("BACKGROUND", (0, 0), (-1, 0), self.b["colors"].HexColor(_base.PANEL))]))
    table.repeatRows = 1
    return table


def _card_flows(self, row: dict[str, Any], refs: list[int]):
    candidate = _prev._candidate(row)
    typ = str(candidate.get("connection_type", "") or "").upper()
    if typ != "WT":
        return _ORIGINAL_CARD_FLOWS(self, row, refs)

    width = self.width - 14
    status = _prev._status(row)
    flows = [
        self.p(
            f'<font color="{_base.TEAL}">Zadání: </font>' + _base.escape(_input_summary(row, with_actions=False)),
            markup=True,
        ),
        self._actions_table(row, width),
        self.b["Spacer"](1, 3),
    ]
    flows.append(self.p(
        f'<font color="{_base.GOLD}">Navržený HIT: </font>' + _base.escape(_prev._text(candidate.get("designation"))),
        bold=True,
        markup=True,
    ))
    flows.append(self.p(
        f"B: {_prev._num(candidate.get('physical_length_mm'), 0)} mm  •  "
        f"h stěny: {_prev._num(candidate.get('height'), 0)} mm  •  "
        f"{_prev._text(candidate.get('concrete'))}  •  zdroj HIT20.2 p.{_prev._text(candidate.get('page'))}"
    ))
    flows.append(self._catalog_table(row, width))
    flows.append(self.p(
        f"Výsledek dílčích kontrol: η = {_prev._percent(candidate.get('utilization'))}  •  {status}",
        bold=True,
        color=_prev._status_color(status),
    ))
    mode = str(candidate.get("mode", "") or "").strip()
    if mode:
        flows.append(self.p("Rozhodující dílčí kontrola: " + mode, size=10.5, color=_base.MUTED))
    if status == "KONTROLA":
        flows.append(self.p(
            "Současné působení více složek WT: dílčí tabulované únosnosti vyhovují, ale společná interakce není bez ověřeného katalogového pravidla automaticky prohlášena za vyhovující.",
            size=10.5,
            color=_base.WARNING,
        ))
    if refs:
        flows.append(self.p(
            "Poznámky a omezení: " + ", ".join(f"[{value}]" for value in refs) + " (příloha).",
            size=10.5,
            color=_base.MUTED,
        ))
    return flows


def _card_title(self, card):
    group = str(card.row.get("group", "") or "").strip()
    title = _prev._text(card.row.get("name"))
    if group:
        title = group + " • " + title
    if card.continued:
        title += "  •  pokračování"
    width = self.width - 14
    status = _prev._status(card.row)
    return self.table(
        [[self.p(title, bold=True), self.p(status, bold=True, align=2, color=_prev._status_color(status))]],
        [width - 151, 151],
        background=_base.PANEL,
        padding=2,
    )


_prev._actions = _actions
_prev._input_summary = _input_summary
_prev._ProposalReport._catalog_table = _catalog_table
_prev._ProposalReport.card_flows = _card_flows
_prev._ProposalReport.card_title = _card_title

PdfExportError = _prev.PdfExportError
ensure_hit_pdf_backend = _prev.ensure_hit_pdf_backend
write_hit_proposal_pdf = _prev.write_hit_proposal_pdf
