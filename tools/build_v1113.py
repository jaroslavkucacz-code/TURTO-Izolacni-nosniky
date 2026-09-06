from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.1.12"
OUT = ROOT / "updates" / "1.1.13"
VERSION = "1.1.13"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"

PATCHES = {'_layout': 'def _layout(backend: _Backend) -> _Layout:\n    global _LAYOUT\n    if _LAYOUT is None:\n        # Technický výstup je záměrně na A4 na výšku. Pro souhrn i detail\n        # tak vzniká přirozený dokument vhodný k tisku a založení.\n        page_w, page_h = backend.pagesizes.A4\n        _LAYOUT = _Layout(float(page_w), float(page_h))\n    return _LAYOUT', '_header': 'def _header(c, backend: _Backend, layout: _Layout, project_name: str, subtitle: str, generated: str) -> None:\n    _rect(c, backend, layout, 0, 0, layout.page_w, layout.header_h, fill=NAVY)\n    _rect(c, backend, layout, 0, layout.header_h - 2.8, layout.page_w, 2.8, fill=GOLD)\n\n    logo_w = 116.0\n    _draw_turto_logo(c, backend, layout, layout.margin, 5.0, logo_w, 36.0)\n\n    right_w = 156.0\n    subtitle_x = layout.margin + logo_w + 10.0\n    subtitle_w = layout.page_w - layout.margin - right_w - 10.0 - subtitle_x\n    _draw_text(\n        c,\n        backend,\n        layout,\n        subtitle,\n        subtitle_x,\n        8.0,\n        size=8.7,\n        color="#E1EDF5",\n        bold=True,\n        max_width=max(80.0, subtitle_w),\n        max_lines=2,\n        leading=10.2,\n    )\n    _draw_text(\n        c,\n        backend,\n        layout,\n        f"Projekt: {_text(project_name)}",\n        layout.page_w - layout.margin - right_w,\n        6.0,\n        size=6.4,\n        color=WHITE,\n        bold=True,\n        max_width=right_w,\n        max_lines=1,\n        align="right",\n    )\n    _draw_text(\n        c,\n        backend,\n        layout,\n        f"Vygenerováno: {generated}",\n        layout.page_w - layout.margin - right_w,\n        20.0,\n        size=5.5,\n        color="#D7E3ED",\n        max_width=right_w,\n        max_lines=1,\n        align="right",\n    )', '_draw_kpi_card': 'def _draw_kpi_card(c, backend: _Backend, layout: _Layout, x: float, y: float, w: float, h: float,\n                   label: str, value: str, accent: str, note: str = "") -> None:\n    _rect(c, backend, layout, x + 1.2, y + 1.5, w, h, fill=SHADOW, radius=3.8)\n    _rect(c, backend, layout, x, y, w, h, fill=WHITE, stroke=BORDER, width=0.35, radius=3.8)\n    _rect(c, backend, layout, x, y + 2.5, 3.1, h - 5.0, fill=accent, radius=1.1)\n    _draw_text(c, backend, layout, label.upper(), x + 8.0, y + 4.2, size=4.15, color=MUTED, bold=True)\n    _draw_text(c, backend, layout, value, x + 8.0, y + 12.2, size=9.4, color=accent, bold=True)\n    if note:\n        _draw_text(\n            c,\n            backend,\n            layout,\n            note,\n            x + 8.0,\n            y + h - 7.4,\n            size=3.65,\n            color=MUTED,\n            max_width=w - 13.0,\n            max_lines=1,\n            align="right",\n        )', '_summary_capacities': 'def _summary_capacities(layout: _Layout) -> tuple[int, int]:\n    row_h = 27.0\n    first_table_top = 111.0\n    other_table_top = 69.0\n    table_header_h = 16.0\n    bottom = layout.page_h - layout.footer_h - 5.0\n    reserve_for_note = 20.0\n    first = max(1, int((bottom - first_table_top - table_header_h - reserve_for_note) // row_h))\n    other = max(1, int((bottom - other_table_top - table_header_h - reserve_for_note) // row_h))\n    return first, other', '_draw_summary_table': 'def _draw_summary_table(c, backend: _Backend, layout: _Layout, rows: list[dict[str, Any]], y: float) -> float:\n    content_w = layout.page_w - 2 * layout.margin\n    fixed = [\n        ("position", "Poz.", 28.0, "center"),\n        ("quantity", "Ks", 20.0, "center"),\n        ("source", "Původní prvek", 132.0, "left"),\n        ("target", "Navržený HIT", 147.0, "left"),\n        ("length", "L [mm]", 48.0, "center"),\n        ("geometry", "I/h/c", 45.0, "center"),\n        ("wire", "Ø", 22.0, "center"),\n        ("governing", "Rozhoduje", 58.0, "center"),\n    ]\n    used = sum(width for _key, _label, width, _align in fixed)\n    columns = [*fixed, ("status", "Stav", max(48.0, content_w - used), "center")]\n\n    header_h = 16.0\n    row_h = 27.0\n    x = layout.margin\n    for _key, label, width, _align in columns:\n        _rect(c, backend, layout, x, y, width, header_h, fill=NAVY, stroke=WHITE, width=0.3)\n        _draw_centered(c, backend, layout, label, x, y, width, header_h, size=4.8, color=WHITE, bold=True)\n        x += width\n    y += header_h\n\n    for index, item in enumerate(rows):\n        values = _summary_row_values(item)\n        fill = WHITE if index % 2 == 0 else PANEL\n        x = layout.margin\n        governing_eta = _governing_check(item)[1]\n        status_color, status_fill = _status_palette(values["status"])\n        for key, _label, width, _align in columns:\n            _rect(c, backend, layout, x, y, width, row_h, fill=fill, stroke=BORDER, width=0.28)\n            value = values[key]\n            if key in {"source", "target"}:\n                _draw_text(\n                    c,\n                    backend,\n                    layout,\n                    value,\n                    x + 4.0,\n                    y + 3.4,\n                    size=4.75,\n                    color=TEXT,\n                    bold=(key == "target" and value != "-"),\n                    max_width=width - 8.0,\n                    max_lines=3,\n                    leading=5.55,\n                )\n            elif key == "status":\n                pill_w = max(39.0, width - 7.0)\n                _rect(\n                    c,\n                    backend,\n                    layout,\n                    x + (width - pill_w) / 2,\n                    y + 7.0,\n                    pill_w,\n                    13.0,\n                    fill=status_fill,\n                    stroke=status_color,\n                    width=0.35,\n                    radius=4.5,\n                )\n                _draw_centered(\n                    c,\n                    backend,\n                    layout,\n                    value,\n                    x + (width - pill_w) / 2,\n                    y + 7.0,\n                    pill_w,\n                    13.0,\n                    size=4.35,\n                    color=status_color,\n                    bold=True,\n                )\n            elif key == "governing":\n                color = (\n                    status_color\n                    if not math.isfinite(governing_eta)\n                    else (SUCCESS if governing_eta <= 0.90 else (WARNING if governing_eta <= 1.0 else DANGER))\n                )\n                _draw_centered(\n                    c,\n                    backend,\n                    layout,\n                    value,\n                    x + 1.5,\n                    y + 1.5,\n                    width - 3.0,\n                    row_h - 3.0,\n                    size=4.55,\n                    color=color,\n                    bold=True,\n                    max_lines=2,\n                )\n            else:\n                _draw_centered(\n                    c,\n                    backend,\n                    layout,\n                    value,\n                    x + 1.5,\n                    y + 1.5,\n                    width - 3.0,\n                    row_h - 3.0,\n                    size=4.45,\n                    color=TEXT,\n                    max_lines=2,\n                )\n            x += width\n        y += row_h\n    return y', '_draw_summary_page': 'def _draw_summary_page(c, backend: _Backend, layout: _Layout, project_name: str, rows: list[dict[str, Any]],\n                       generated: str, page_index: int, total_summary_pages: int,\n                       all_rows: list[dict[str, Any]]) -> None:\n    subtitle = "Tabulka záměn - souhrn" if page_index == 0 else "Tabulka záměn - pokračování"\n    _header(c, backend, layout, project_name, subtitle, generated)\n    y = layout.header_h + 6.0\n\n    if page_index == 0:\n        _draw_text(c, backend, layout, "Přehled navržených záměn", layout.margin, y, size=9.6, color=NAVY, bold=True)\n        _draw_text(\n            c,\n            backend,\n            layout,\n            "Kompaktní souhrn původního prvku, navrženého HIT, základních rozměrů a rozhodujícího využití.",\n            layout.margin,\n            y + 12.5,\n            size=4.75,\n            color=MUTED,\n            max_width=layout.page_w - 2 * layout.margin,\n            max_lines=1,\n        )\n        stats = _summary_stats(all_rows)\n        card_y = y + 24.0\n        gap = 5.0\n        card_w = (layout.page_w - 2 * layout.margin - 4 * gap) / 5.0\n        cards = [\n            ("Pozice", str(stats["positions"]), NAVY, "řádků"),\n            ("Množství", str(stats["quantity"]), TEAL, "kusů"),\n            ("Vyhovuje", str(stats["ok"]), SUCCESS, "pozic"),\n            ("K posouzení", str(stats["review"]), WARNING, "pozic"),\n            ("Max. využití", _percent(stats["max_utilization"]), GOLD, "eta max"),\n        ]\n        x = layout.margin\n        for label, value, accent, note in cards:\n            _draw_kpi_card(c, backend, layout, x, card_y, card_w, 24.0, label, value, accent, note)\n            x += card_w + gap\n        table_y = card_y + 29.0\n    else:\n        _draw_text(\n            c,\n            backend,\n            layout,\n            f"Přehled navržených záměn - část {page_index + 1}/{total_summary_pages}",\n            layout.margin,\n            y,\n            size=8.9,\n            color=NAVY,\n            bold=True,\n        )\n        _draw_text(\n            c,\n            backend,\n            layout,\n            "Pokračování kompaktní souhrnné tabulky.",\n            layout.margin,\n            y + 11.5,\n            size=4.7,\n            color=MUTED,\n        )\n        table_y = y + 18.0\n\n    end_y = _draw_summary_table(c, backend, layout, rows, table_y)\n    note_y = min(layout.page_h - layout.footer_h - 15.0, end_y + 4.0)\n    _rect(\n        c,\n        backend,\n        layout,\n        layout.margin,\n        note_y,\n        layout.page_w - 2 * layout.margin,\n        10.5,\n        fill=LIGHT_TEAL,\n        stroke="#BDD7E2",\n        width=0.3,\n        radius=2.5,\n    )\n    _draw_text(\n        c,\n        backend,\n        layout,\n        "Rozhoduje = nejvyšší poměr požadavek / únosnost. Úplná směrová kontrola a tlakový přenos jsou v detailních listech.",\n        layout.margin + 5.0,\n        note_y + 2.9,\n        size=4.35,\n        color=NAVY,\n        max_width=layout.page_w - 2 * layout.margin - 10.0,\n        max_lines=1,\n    )', '_draw_source_target_box': 'def _draw_source_target_box(c, backend: _Backend, layout: _Layout, x: float, y: float, w: float, h: float,\n                            label: str, value: str, accent: str) -> None:\n    compact = h <= 29.0\n    _rect(c, backend, layout, x, y, w, h, fill=PANEL, stroke=BORDER, width=0.35, radius=3.5)\n    _rect(c, backend, layout, x, y + 2.5, 2.8, h - 5.0, fill=accent, radius=1.0)\n    _draw_text(c, backend, layout, label.upper(), x + 6.5, y + 3.6, size=3.9 if compact else 4.3, color=accent, bold=True)\n    _draw_text(\n        c,\n        backend,\n        layout,\n        value,\n        x + 6.5,\n        y + (11.5 if compact else 13.0),\n        size=5.0 if compact else 5.7,\n        color=TEXT,\n        bold=True,\n        max_width=w - 12.0,\n        max_lines=2,\n        leading=5.9 if compact else 6.9,\n    )', '_draw_checks_table': 'def _draw_checks_table(c, backend: _Backend, layout: _Layout, item: dict[str, Any], x: float, y: float,\n                       w: float, max_rows: int = 6, compact: bool = False) -> float:\n    headers = ["Účinek", "Požadavek", "Únosnost HIT", "Využití", "Výsledek"]\n    proportions = (0.12, 0.235, 0.235, 0.155, 0.255)\n    widths = [w * value for value in proportions]\n    widths[-1] += w - sum(widths)\n    header_h = 9.5 if compact else 11.0\n    row_h = 8.9 if compact else 10.2\n    header_size = 3.55 if compact else 3.9\n    body_size = 3.65 if compact else 4.05\n\n    xx = x\n    for label, cell_w in zip(headers, widths):\n        _rect(c, backend, layout, xx, y, cell_w, header_h, fill=NAVY, stroke=WHITE, width=0.25)\n        _draw_centered(c, backend, layout, label, xx, y, cell_w, header_h, size=header_size, color=WHITE, bold=True)\n        xx += cell_w\n    y += header_h\n\n    checks = _check_rows(item)\n    for index, check in enumerate(checks[:max_rows]):\n        xx = x\n        eta = _safe_float(check.get("eta"), float("inf"))\n        values = [\n            _text(check.get("label")),\n            f"{_number(check.get(\'requirement\'))} {_text(check.get(\'unit\'))}",\n            f"{_number(check.get(\'capacity\'))} {_text(check.get(\'unit\'))}",\n            _percent(eta),\n            _text(check.get("result")),\n        ]\n        fill = WHITE if index % 2 == 0 else PANEL\n        for col_index, (value, cell_w) in enumerate(zip(values, widths)):\n            _rect(c, backend, layout, xx, y, cell_w, row_h, fill=fill, stroke=BORDER, width=0.25)\n            color = TEXT\n            bold = col_index in {0, 3, 4}\n            if col_index == 4:\n                color = SUCCESS if eta <= 1.0 + 1e-9 else DANGER\n            _draw_centered(\n                c,\n                backend,\n                layout,\n                value,\n                xx + 1.0,\n                y + 0.3,\n                cell_w - 2.0,\n                row_h - 0.6,\n                size=body_size,\n                color=color,\n                bold=bold,\n                max_lines=1,\n            )\n            xx += cell_w\n        y += row_h\n\n    if not checks:\n        _rect(c, backend, layout, x, y, w, row_h, fill=PANEL, stroke=BORDER, width=0.25)\n        _draw_centered(\n            c,\n            backend,\n            layout,\n            "Není k dispozici směrová statická kontrola.",\n            x,\n            y,\n            w,\n            row_h,\n            size=body_size,\n            color=MUTED,\n        )\n        y += row_h\n    elif len(checks) > max_rows:\n        _draw_text(\n            c,\n            backend,\n            layout,\n            f"+ {len(checks) - max_rows} další kontroly",\n            x,\n            y + 1.2,\n            size=3.7 if compact else 4.0,\n            color=MUTED,\n        )\n        y += 7.0 if compact else 8.0\n    return y', '_draw_technical_match': 'def _draw_technical_match(c, backend: _Backend, layout: _Layout, item: dict[str, Any], x: float, y: float,\n                          w: float, h: float, compact: bool = False) -> None:\n    target = item.get("target") if isinstance(item.get("target"), dict) else {}\n    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}\n    _rect(c, backend, layout, x, y, w, h, fill=LIGHT_GOLD, stroke="#E2CF9D", width=0.35, radius=3.2)\n\n    title_size = 3.8 if compact else 4.25\n    body_size = 3.65 if compact else 4.05\n    _draw_text(c, backend, layout, "TECHNICKÁ SHODA", x + 5.0, y + 3.5, size=title_size, color=GOLD, bold=True)\n\n    overall = _safe_float(target.get("utilization")) if target else float("nan")\n    interaction = _safe_float(target.get("interaction_utilization")) if target else 0.0\n    geometry = _text(meta.get("geometry_display")) if meta.get("geometry_display") else _text(item.get("estimated_type"))\n\n    def pressure_short(value: Any) -> str:\n        text = _text(value).lower()\n        if "bez" in text and "lož" in text:\n            return "bez ložisek"\n        if "lož" in text or "csb" in text:\n            return "s ložisky"\n        if "prut" in text:\n            return "tlačené pruty"\n        return _text(value)\n\n    source_pressure = pressure_short(meta.get("source_compression_text"))\n    target_pressure = pressure_short(target.get("compression_text")) if target else "-"\n\n    if compact:\n        lines = [\n            ("η celkem", _percent(overall), True),\n            ("L / geometrie", f"{_text(target.get(\'length_relation\')) if target else \'-\'} • {geometry}", False),\n            ("Tlak", f"{source_pressure} -> {target_pressure}", False),\n        ]\n        yy = y + 12.0\n        step = 8.1\n    else:\n        lines = [\n            ("Celkové využití", _percent(overall), True),\n            ("Interakce M-V", _percent(interaction) if interaction > 0 else "neaplikuje se", False),\n            ("Délka", _text(target.get("length_relation")) if target else "-", False),\n            ("Tlakový přenos", f"{source_pressure} -> {target_pressure}", False),\n            ("Geometrie", geometry, False),\n        ]\n        yy = y + 14.0\n        step = 9.2\n\n    for label, value, important in lines:\n        _draw_text(c, backend, layout, f"{label}:", x + 5.0, yy, size=body_size, color=TEXT, bold=True)\n        label_w = _text_width(backend, f"{label}:", backend.bold_font, body_size)\n        _draw_text(\n            c,\n            backend,\n            layout,\n            value,\n            x + 7.5 + label_w,\n            yy,\n            size=body_size,\n            color=TEXT,\n            bold=important,\n            max_width=max(10.0, w - 12.5 - label_w),\n            max_lines=1,\n        )\n        yy += step', '_draw_detail_card': 'def _draw_detail_card(c, backend: _Backend, layout: _Layout, box: tuple[float, float, float, float],\n                      item: dict[str, Any]) -> None:\n    x0, y0, x1, y1 = box\n    w = x1 - x0\n    h = y1 - y0\n    compact = h < 210.0\n    status = _text(item.get("status"))\n    status_color, status_fill = _status_palette(status)\n    target = item.get("target") if isinstance(item.get("target"), dict) else {}\n    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}\n\n    shadow = 1.4 if compact else 2.0\n    radius = 4.5 if compact else 5.5\n    _rect(c, backend, layout, x0 + shadow, y0 + shadow, w, h, fill=SHADOW, radius=radius)\n    _rect(c, backend, layout, x0, y0, w, h, fill=WHITE, stroke=BORDER, width=0.5, radius=radius)\n    _rect(c, backend, layout, x0, y0, 3.2, h, fill=status_color, radius=1.6)\n\n    header_h = 18.0 if compact else 21.0\n    _rect(c, backend, layout, x0 + 3.2, y0, w - 3.2, header_h, fill=NAVY, radius=radius)\n    _draw_text(\n        c,\n        backend,\n        layout,\n        f"POZICE {_text(item.get(\'position\'))}   •   {_text(item.get(\'quantity\'))} ks",\n        x0 + 9.0,\n        y0 + (5.0 if compact else 6.0),\n        size=5.35 if compact else 6.0,\n        color=WHITE,\n        bold=True,\n    )\n    badge_w = 48.0 if compact else 54.0\n    badge_h = 10.5 if compact else 12.0\n    _rect(\n        c,\n        backend,\n        layout,\n        x1 - badge_w - 7.0,\n        y0 + (3.8 if compact else 4.5),\n        badge_w,\n        badge_h,\n        fill=status_fill,\n        stroke=status_color,\n        width=0.35,\n        radius=4.0,\n    )\n    _draw_centered(\n        c,\n        backend,\n        layout,\n        status,\n        x1 - badge_w - 7.0,\n        y0 + (3.8 if compact else 4.5),\n        badge_w,\n        badge_h,\n        size=3.85 if compact else 4.25,\n        color=status_color,\n        bold=True,\n    )\n\n    inner_x = x0 + 8.0\n    inner_w = w - 16.0\n    gap = 6.0\n    col_w = (inner_w - gap) / 2.0\n    boxes_y = y0 + header_h + 3.0\n    box_h = 27.0 if compact else 31.0\n    _draw_source_target_box(\n        c, backend, layout, inner_x, boxes_y, col_w, box_h,\n        "Původní prvek", _text(item.get("source")), TEAL,\n    )\n    _draw_source_target_box(\n        c, backend, layout, inner_x + col_w + gap, boxes_y, col_w, box_h,\n        "Navržený HIT", _text(target.get("designation")) if target else "Bez navrženého HIT", GOLD,\n    )\n\n    strip_y = boxes_y + box_h + 3.0\n    strip_h = 12.0 if compact else 14.0\n    _rect(c, backend, layout, inner_x, strip_y, inner_w, strip_h, fill=LIGHT_TEAL, stroke="#C1DBE5", width=0.3, radius=2.5)\n    source_params = (\n        f"I {_integer(meta.get(\'source_insulation_mm\'))} • h {_integer(meta.get(\'source_height_mm\'))} • "\n        f"c {_integer(meta.get(\'source_cover_mm\'))} • L {_integer(meta.get(\'source_length_mm\'))} mm • "\n        f"{_text(meta.get(\'source_concrete\'))}"\n    )\n    target_params = (\n        f"HIT-{_text(target.get(\'series\'))} • h {_integer(target.get(\'height_mm\'))} • "\n        f"c {_integer(target.get(\'cover_mm\'))} • L {_integer(target.get(\'length_mm\'))} mm • {_wire_diameter(target)}"\n        if target else "-"\n    )\n    strip_size = 3.75 if compact else 4.05\n    _draw_text(c, backend, layout, source_params, inner_x + 4.0, strip_y + 3.4, size=strip_size, color=NAVY,\n               max_width=col_w - 7.0, max_lines=1)\n    _draw_text(c, backend, layout, target_params, inner_x + col_w + gap + 3.0, strip_y + 3.4, size=strip_size, color=NAVY,\n               max_width=col_w - 7.0, max_lines=1)\n\n    governing_label, governing_eta = _governing_check(item)\n    gov_y = strip_y + strip_h + 3.0\n    gov_color = (\n        status_color\n        if not math.isfinite(governing_eta)\n        else (SUCCESS if governing_eta <= 0.90 else (WARNING if governing_eta <= 1.0 else DANGER))\n    )\n    _draw_text(c, backend, layout, "ROZHODUJÍCÍ KONTROLA", inner_x, gov_y, size=3.8 if compact else 4.2, color=MUTED, bold=True)\n    _draw_text(\n        c,\n        backend,\n        layout,\n        f"{governing_label}  |  eta = {_percent(governing_eta)}",\n        inner_x,\n        gov_y + (7.0 if compact else 8.0),\n        size=6.5 if compact else 7.2,\n        color=gov_color,\n        bold=True,\n    )\n    bar_x = inner_x + (104.0 if compact else 116.0)\n    _draw_utilization_bar(\n        c,\n        backend,\n        layout,\n        bar_x,\n        gov_y + (10.0 if compact else 11.5),\n        max(40.0, inner_w - (104.0 if compact else 116.0)),\n        4.2 if compact else 5.0,\n        governing_eta,\n    )\n\n    section_y = gov_y + (19.0 if compact else 22.0)\n    table_w = inner_w * 0.66\n    info_gap = 6.0\n    info_w = inner_w - table_w - info_gap\n    _draw_text(\n        c,\n        backend,\n        layout,\n        "STATICKÁ KONTROLA JEDNOHO PRVKU",\n        inner_x,\n        section_y,\n        size=3.9 if compact else 4.3,\n        color=NAVY,\n        bold=True,\n    )\n    max_rows = 3 if compact else 6\n    table_top = section_y + (7.0 if compact else 8.0)\n    table_end = _draw_checks_table(\n        c, backend, layout, item, inner_x, table_top, table_w, max_rows=max_rows, compact=compact\n    )\n    panel_h = max(36.0 if compact else 58.0, table_end - table_top)\n    _draw_technical_match(\n        c,\n        backend,\n        layout,\n        item,\n        inner_x + table_w + info_gap,\n        table_top,\n        info_w,\n        panel_h,\n        compact=compact,\n    )\n\n    note_h = 14.0 if compact else 19.0\n    note_y = y1 - note_h - 3.0\n    _line(c, backend, layout, inner_x, note_y - 2.0, x1 - 7.0, note_y - 2.0, BORDER, 0.3)\n    notes = item.get("notes") if isinstance(item.get("notes"), list) else []\n    note_text = " • ".join(_text(value) for value in notes if _text(value) != "-")\n    if not note_text:\n        note_text = "Základní geometrie a statická únosnost odpovídají; ostatní projektové podmínky ověřte projektantem."\n    _draw_text(c, backend, layout, "POZNÁMKA:", inner_x, note_y + 1.0, size=3.65 if compact else 4.0, color=MUTED, bold=True)\n    _draw_text(\n        c,\n        backend,\n        layout,\n        note_text,\n        inner_x + (34.0 if compact else 38.0),\n        note_y + 1.0,\n        size=3.65 if compact else 4.0,\n        color=MUTED,\n        max_width=inner_w - (34.0 if compact else 38.0),\n        max_lines=1 if compact else 2,\n        leading=4.6 if compact else 5.0,\n    )', '_detail_chunks': 'def _detail_chunks(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:\n    # Čtyři běžné nebo tři obsahově náročnější pozice na jednu A4.\n    chunks: list[list[dict[str, Any]]] = []\n    current: list[dict[str, Any]] = []\n    used = 0.0\n\n    for item in rows:\n        checks = len(_check_rows(item))\n        notes = item.get("notes") if isinstance(item.get("notes"), list) else []\n        note_length = sum(len(_text(value)) for value in notes)\n        status = _text(item.get("status")).upper()\n        complex_item = checks > 3 or note_length > 220 or status not in {"VYHOVUJE", "JIŽ HIT"}\n        weight = 1.32 if complex_item else 1.0\n\n        if current and (len(current) >= 4 or used + weight > 4.01):\n            chunks.append(current)\n            current = []\n            used = 0.0\n        current.append(item)\n        used += weight\n\n    if current:\n        chunks.append(current)\n    return chunks', '_draw_detail_page': 'def _draw_detail_page(c, backend: _Backend, layout: _Layout, project_name: str, rows: list[dict[str, Any]],\n                      generated: str) -> None:\n    _header(c, backend, layout, project_name, "Stručný statický výpočet", generated)\n    content_top = layout.header_h + 5.0\n    content_bottom = layout.page_h - layout.footer_h - 6.0\n    count = max(1, len(rows))\n    gap = 5.5\n    available = content_bottom - content_top - gap * (count - 1)\n    computed_h = available / count\n    # Na poslední neúplné stránce jediný blok zbytečně neroztahujeme.\n    target_h = 188.0 if count >= 4 else 239.0\n    card_h = min(computed_h, target_h)\n\n    y = content_top\n    for item in rows:\n        _draw_detail_card(\n            c,\n            backend,\n            layout,\n            (layout.margin, y, layout.page_w - layout.margin, y + card_h),\n            item,\n        )\n        y += card_h + gap'}
LOGO_HELPER = 'def _draw_turto_logo(\n    c,\n    backend: _Backend,\n    layout: _Layout,\n    x: float,\n    y: float,\n    w: float = 116.0,\n    h: float = 36.0,\n) -> None:\n    # Kompaktní vektorová varianta firemního loga TURTO pro záhlaví PDF.\n    # Logo je sestaveno výhradně z PDF čar a textu.\n    _rect(c, backend, layout, x, y, w, h, fill=WHITE, stroke="#C8D2DC", width=0.45, radius=4.2)\n\n    sx = x + 6.0\n    sy = y + 5.0\n    _set_stroke(c, backend, "#111820")\n    c.setLineCap(1)\n    c.setLineJoin(1)\n    c.setLineWidth(1.25)\n    segments = (\n        (0, 25, 0, 11), (0, 11, 10, 5), (10, 5, 10, 25),\n        (7, 25, 7, 16), (7, 16, 18, 9), (18, 9, 27, 15), (27, 15, 27, 25),\n        (13, 25, 13, 19), (13, 19, 20, 15), (20, 15, 35, 23), (35, 23, 35, 25),\n    )\n    for x1, y1, x2, y2 in segments:\n        _line(c, backend, layout, sx + x1, sy + y1, sx + x2, sy + y2, "#111820", 1.25)\n\n    brand_red = "#B81720"\n    text_x = x + 44.0\n    _draw_text(c, backend, layout, "TURTO", text_x, y + 4.4, size=12.8, color=brand_red, bold=True)\n    _draw_text(c, backend, layout, "ISO", x + w - 22.0, y + 5.5, size=6.3, color=GOLD, bold=True)\n    _draw_text(\n        c,\n        backend,\n        layout,\n        "PRVKY DO MONOLITU",\n        text_x,\n        y + 22.4,\n        size=3.55,\n        color="#111820",\n        bold=True,\n        max_width=w - 49.0,\n        max_lines=1,\n    )'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def replace_function(text: str, name: str, source: str) -> str:
    pattern = re.compile(rf"(?ms)^def {re.escape(name)}\b.*?(?=^def [A-Za-z_]\w*\b|\Z)")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"{name}: expected 1 top-level function, got {len(matches)}")
    replacement = source.strip() + "\n\n"
    return text[:matches[0].start()] + replacement + text[matches[0].end():]


def patch_pdf(text: str) -> str:
    text = replace_once(
        text,
        "    margin: float = 28.0\n    header_h: float = 44.0\n    footer_h: float = 18.0",
        "    margin: float = 18.0\n    header_h: float = 47.0\n    footer_h: float = 15.0",
        "portrait layout constants",
    )
    text = text.replace(
        "Všechny texty, tabulky, rámečky a grafy využití se kreslí přímo do PDF\n"
        "pomocí ReportLabu. Dokument proto neobsahuje rastrové snímky stránek,\n"
        "text je vyhledávatelný a lze jej označit a kopírovat.",
        "Všechny texty, tabulky, rámečky, grafy využití i firemní logo TURTO se kreslí přímo do PDF\n"
        "pomocí ReportLabu. Dokument je na A4 na výšku, neobsahuje rastrové snímky stránek,\n"
        "text je vyhledávatelný a lze jej označit a kopírovat.",
        1,
    )
    text = replace_function(text, "_layout", PATCHES["_layout"])
    if "def _draw_turto_logo(" not in text:
        marker = "\ndef _header("
        if marker not in text:
            raise RuntimeError("header insertion point missing")
        text = text.replace(marker, "\n\n" + LOGO_HELPER.strip() + "\n\n\ndef _header(", 1)
    for name in (
        "_header",
        "_draw_kpi_card",
        "_summary_capacities",
        "_draw_summary_table",
        "_draw_summary_page",
        "_draw_source_target_box",
        "_draw_checks_table",
        "_draw_technical_match",
        "_draw_detail_card",
        "_detail_chunks",
        "_draw_detail_page",
    ):
        text = replace_function(text, name, PATCHES[name])
    return text


def patch_versions() -> None:
    app = OUT / "app.pyw"
    text = app.read_text(encoding="utf-8")
    text = replace_once(text, 'APP_VERSION = "1.1.12"', f'APP_VERSION = "{VERSION}"', "app version")
    app.write_text(text, encoding="utf-8")

    workspace = OUT / "substitution_workspace.py"
    text = workspace.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'SUBSTITUTION_MODULE_VERSION = "1.1.12"',
        f'SUBSTITUTION_MODULE_VERSION = "{VERSION}"',
        "substitution module version",
    )
    workspace.write_text(text, encoding="utf-8")

    (OUT / "version.txt").write_text(VERSION, encoding="utf-8")


def compile_sources(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.suffix not in {".py", ".pyw"}:
            continue
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def diagnostic_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(1, 21):
        utilization = 0.48 + (index % 9) * 0.05
        requirement_m = 18.0 + index * 0.55
        capacity_m = requirement_m / max(utilization, 0.01)
        requirement_v = 30.0 + index * 0.7
        capacity_v = requirement_v / max(utilization - 0.06, 0.25)
        source = f"EGCOBOX MXL{20 + (index % 4) * 5}-VS-C30-h200-REI120-SW"
        target_name = f"HIT-SP MVX-{4 + index % 5:02d}04-20-100-30"
        geometry_display = "WU280 → OU280 • potvrzeno uživatelem" if index % 5 == 0 else ""
        target = {
            "designation": target_name,
            "series": "SP",
            "target_insulation_mm": 120,
            "height_mm": 200,
            "cover_mm": 30,
            "length_mm": 1000,
            "wire_diameter_mm": 8,
            "utilization": utilization,
            "interaction_utilization": max(0.0, utilization - 0.08),
            "length_relation": "shodná délka",
            "compression_text": "s tlakovými ložisky (CSB)",
            "checks": [
                {
                    "label": "M-",
                    "requirement": requirement_m,
                    "capacity": capacity_m,
                    "unit": "kNm/prvek",
                    "eta": utilization,
                    "result": "VYHOVUJE",
                },
                {
                    "label": "V+",
                    "requirement": requirement_v,
                    "capacity": capacity_v,
                    "unit": "kN/prvek",
                    "eta": max(0.0, utilization - 0.06),
                    "result": "VYHOVUJE",
                },
            ],
        }
        rows.append(
            {
                "position": f"P{index:03d}",
                "quantity": 2 + index % 7,
                "manufacturer": "MAX FRANK",
                "source": source,
                "source_meta": {
                    "source_insulation_mm": 120,
                    "source_height_mm": 200,
                    "source_cover_mm": 30,
                    "source_length_mm": 1000,
                    "source_concrete": "C25/30",
                    "source_compression_text": "s tlakovými ložisky",
                    "geometry_display": geometry_display,
                },
                "source_actions": {
                    "m_pos": 0.0,
                    "m_neg": requirement_m,
                    "n_pos": 0.0,
                    "n_neg": 0.0,
                    "v_pos": requirement_v,
                    "v_neg": 0.0,
                },
                "estimated_type": "MVX",
                "target": target,
                "status": "VYHOVUJE",
                "notes": ["Geometrie a statická únosnost potvrzeny."] if geometry_display else [],
            }
        )
    return rows


def count_image_xobjects(reader: Any) -> int:
    seen: set[int] = set()

    def walk_resources(resources: Any) -> int:
        if resources is None:
            return 0
        try:
            resources = resources.get_object()
        except Exception:
            pass
        xobjects = resources.get("/XObject") if hasattr(resources, "get") else None
        if not xobjects:
            return 0
        try:
            xobjects = xobjects.get_object()
        except Exception:
            pass
        total = 0
        for value in xobjects.values():
            try:
                obj = value.get_object()
            except Exception:
                obj = value
            marker = id(obj)
            if marker in seen:
                continue
            seen.add(marker)
            subtype = str(obj.get("/Subtype", "")) if hasattr(obj, "get") else ""
            if subtype == "/Image":
                total += 1
            elif subtype == "/Form" and hasattr(obj, "get"):
                total += walk_resources(obj.get("/Resources"))
        return total

    return sum(walk_resources(page.get("/Resources")) for page in reader.pages)


def verify_pdf() -> None:
    try:
        from pypdf import PdfReader
        import pypdfium2 as pdfium
    except Exception as exc:
        raise RuntimeError("Diagnostic dependencies pypdf and pypdfium2 are required") from exc

    module_path = OUT / "substitution_pdf.py"
    spec = importlib.util.spec_from_file_location("turto_pdf_v1113", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load generated substitution_pdf.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    pdf_path = ROOT / "_diag_v1113_portrait.pdf"
    module.write_substitution_pdf(
        pdf_path,
        project_name="Diagnostika A4 portrait",
        rows=diagnostic_rows(),
        creator="Vytvořil Ing. Jaroslav Kučera",
    )

    reader = PdfReader(str(pdf_path))
    if not reader.pages:
        raise RuntimeError("Diagnostic PDF has no pages")
    first = reader.pages[0]
    width = float(first.mediabox.width)
    height = float(first.mediabox.height)
    if not height > width:
        raise RuntimeError(f"PDF is not portrait: {width} x {height}")

    first_text = first.extract_text() or ""
    missing = [f"P{index:03d}" for index in range(1, 21) if f"P{index:03d}" not in first_text]
    if missing:
        raise RuntimeError(f"Compact first-page summary missing positions: {missing}")

    if len(reader.pages) < 2:
        raise RuntimeError("Diagnostic PDF should contain detail pages")
    detail_text = reader.pages[1].extract_text() or ""
    detail_count = detail_text.count("POZICE")
    if detail_count != 4:
        raise RuntimeError(f"Expected 4 compact detail cards on first detail page, got {detail_count}")

    image_count = count_image_xobjects(reader)
    if image_count != 0:
        raise RuntimeError(f"Vector PDF unexpectedly contains {image_count} image XObjects")

    if "TURTO" not in first_text or "PRVKY DO MONOLITU" not in first_text:
        raise RuntimeError("Vector TURTO logo text is missing from the PDF")

    pdf = pdfium.PdfDocument(str(pdf_path))
    for page_index in (0, 1):
        page = pdf[page_index]
        bitmap = page.render(scale=1.6)
        bitmap.to_pil().save(ROOT / f"_diag_v1113_page{page_index + 1}.png")
        page.close()
    pdf.close()

    report = {
        "version": VERSION,
        "page_size_pt": [round(width, 2), round(height, 2)],
        "portrait": True,
        "summary_positions_on_first_page": 20,
        "detail_cards_on_first_detail_page": detail_count,
        "image_xobjects": image_count,
        "searchable_text": True,
        "vector_turto_logo": True,
        "pages": len(reader.pages),
        "result": "PASS",
    }
    (ROOT / "_diag_v1113_verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_manifest() -> None:
    files: list[dict[str, str]] = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(OUT).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append(
            {
                "path": relative,
                "url": f"https://raw.githubusercontent.com/{REPOSITORY}/main/updates/{VERSION}/{relative}",
                "sha256": digest,
            }
        )

    manifest = {
        "version": VERSION,
        "notes": (
            "TURTO ISO: přepracovaný vektorový PDF výstup na A4 na výšku, "
            "vektorové logo TURTO, výrazně kompaktnější souhrn a 3–4 detailní záměny na stránku."
        ),
        "files": files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if not BASE.exists():
        raise RuntimeError(f"Base update is missing: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    pdf_path = OUT / "substitution_pdf.py"
    pdf_text = pdf_path.read_text(encoding="utf-8")
    pdf_path.write_text(patch_pdf(pdf_text), encoding="utf-8")

    patch_versions()

    release_notes = """TURTO ISO v1.1.13
- Vektorový PDF výstup je nově standardně na A4 na výšku.
- Do záhlaví každé stránky je vložena kompaktní vektorová podoba firemního loga TURTO; PDF zůstává bez rastrových obrazových objektů.
- Celkový přehled je výrazně kompaktnější: užší sloupce, nižší řádky a stručnější typografie umožní zobrazit přibližně 20–25 běžných pozic už na první stránce.
- Souhrn dál obsahuje jen rozhodující údaje; tlakový přenos zůstává v detailní technické kontrole.
- Detailní záměny se skládají adaptivně: běžné pozice po 4 na stránku, obsahově náročnější pozice po 3.
- Všechny texty, čáry, tabulky, grafy využití i logo jsou vektorové, vyhledávatelné a kopírovatelné.
- Zachována je kontrola M/N/V, délek, izolantu, krytí, výšky, tlakového přenosu a potvrzené geometrie OU/OD.
"""
    (OUT / "RELEASE_NOTES.txt").write_text(release_notes, encoding="utf-8")

    compile_sources(OUT)
    verify_pdf()
    build_manifest()

    print(f"Built and verified TURTO ISO {VERSION}")
    print(f"Output: {OUT}")
    print("PASS: A4 portrait, compact summary, four compact details, vector logo, no image XObjects")


if __name__ == "__main__":
    main()
