from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
import math
import os
import re


PAGE_W = 1754
PAGE_H = 1240
DPI = 150
MARGIN = 58
HEADER_H = 92
FOOTER_H = 34

NAVY = (23, 50, 77)
TEAL = (14, 110, 142)
GOLD = (184, 139, 48)
TEXT = (27, 34, 44)
MUTED = (91, 104, 120)
BORDER = (208, 218, 228)
PANEL = (247, 249, 251)
WHITE = (255, 255, 255)
SUCCESS = (44, 122, 84)
WARNING = (158, 109, 22)
DANGER = (166, 61, 64)
LIGHT_TEAL = (231, 243, 247)
LIGHT_GOLD = (252, 246, 229)
SHADOW = (226, 232, 238)


class PdfExportError(RuntimeError):
    pass


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise PdfExportError(
            "Pro export PDF je potřeba knihovna Pillow. Nainstalujte ji příkazem: py -m pip install Pillow"
        ) from exc
    return Image, ImageDraw, ImageFont


def _font_candidates(bold: bool) -> list[str]:
    windows = Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Fonts"
    candidates = [
        windows / ("calibrib.ttf" if bold else "calibri.ttf"),
        windows / ("arialbd.ttf" if bold else "arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    return [str(path) for path in candidates]


def _font(size: int, bold: bool = False):
    _Image, _ImageDraw, ImageFont = _pil()
    for candidate in _font_candidates(bold):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _text(value: Any) -> str:
    if value in (None, ""):
        return "-"
    return str(value).replace("\u00a0", " ").strip() or "-"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _number(value: Any, decimals: int = 1) -> str:
    number = _safe_float(value, float("nan"))
    if not math.isfinite(number):
        return "-"
    return f"{number:.{decimals}f}".replace(".", ",")


def _integer(value: Any) -> str:
    number = _safe_float(value, float("nan"))
    if not math.isfinite(number):
        return "-"
    return str(int(round(number)))


def _percent(value: Any) -> str:
    number = _safe_float(value, float("nan")) * 100.0
    if not math.isfinite(number):
        return "-"
    return f"{number:.1f} %".replace(".", ",")


def _wire_diameter(target: dict[str, Any]) -> str:
    value = target.get("wire_diameter_mm")
    try:
        diameter = int(value)
    except (TypeError, ValueError):
        diameter = 0
    if diameter in {6, 8, 10, 12}:
        return f"Ø {diameter:02d}"
    match = re.search(r"-(06|08|10|12)(?:$|[-\s])", _text(target.get("designation")))
    return f"Ø {match.group(1)}" if match else "-"


def _status_style(status: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    value = status.upper()
    if value == "VYHOVUJE":
        return SUCCESS, (234, 246, 239)
    if value == "KONTROLA":
        return WARNING, (255, 247, 229)
    if value in {"NELZE", "CHYBA", "NEVYHOVUJE"}:
        return DANGER, (253, 237, 238)
    return MUTED, PANEL


def _measure(draw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text or " ", font=font)
    return max(0, box[2] - box[0]), max(0, box[3] - box[1])


def _wrap(draw, text: str, font, max_width: int, max_lines: int | None = None) -> list[str]:
    raw_lines = _text(text).splitlines() or ["-"]
    out: list[str] = []
    for raw in raw_lines:
        words = raw.split()
        if not words:
            out.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = current + " " + word
            if _measure(draw, trial, font)[0] <= max_width:
                current = trial
            else:
                out.append(current)
                current = word
        out.append(current)
    if max_lines is not None and len(out) > max_lines:
        out = out[:max_lines]
        tail = out[-1]
        while tail and _measure(draw, tail + "...", font)[0] > max_width:
            tail = tail[:-1]
        out[-1] = tail.rstrip() + "..."
    return out


def _draw_wrapped(
    draw,
    xy: tuple[int, int],
    text: str,
    font,
    fill,
    max_width: int,
    line_gap: int = 4,
    max_lines: int | None = None,
) -> int:
    x, y = xy
    lines = _wrap(draw, text, font, max_width, max_lines=max_lines)
    line_h = max(1, _measure(draw, "Ag", font)[1])
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h + line_gap
    return y


def _new_page():
    Image, ImageDraw, _ImageFont = _pil()
    image = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
    return image, ImageDraw.Draw(image)


def _header(draw, project_name: str, subtitle: str, generated: str) -> None:
    draw.rectangle((0, 0, PAGE_W, HEADER_H), fill=NAVY)
    draw.rectangle((0, HEADER_H - 7, PAGE_W, HEADER_H), fill=GOLD)
    draw.text((MARGIN, 19), "TURTO ISO", font=_font(30, True), fill=WHITE)
    draw.text((MARGIN + 230, 24), subtitle, font=_font(23, True), fill=(225, 237, 245))
    right = PAGE_W - MARGIN
    project = f"Projekt: {_text(project_name)}"
    project_w = _measure(draw, project, _font(15, True))[0]
    draw.text((right - project_w, 17), project, font=_font(15, True), fill=WHITE)
    stamp = f"Vygenerováno: {generated}"
    stamp_w = _measure(draw, stamp, _font(13))[0]
    draw.text((right - stamp_w, 48), stamp, font=_font(13), fill=(215, 226, 235))


def _footer(draw, page_no: int, total_pages: int, creator: str) -> None:
    y = PAGE_H - FOOTER_H
    draw.line((MARGIN, y, PAGE_W - MARGIN, y), fill=BORDER, width=2)
    draw.text((MARGIN, y + 8), creator, font=_font(12, True), fill=MUTED)
    note = "Předběžná katalogová záměna M/N/V a základní geometrie; požární odolnost se neposuzuje. Ověřit projektantem."
    note_w = _measure(draw, note, _font(11))[0]
    draw.text(((PAGE_W - note_w) // 2, y + 9), note, font=_font(11), fill=MUTED)
    page = f"Strana {page_no}/{total_pages}"
    page_w = _measure(draw, page, _font(12))[0]
    draw.text((PAGE_W - MARGIN - page_w, y + 8), page, font=_font(12), fill=MUTED)


def _check_rows(item: dict[str, Any]) -> list[dict[str, Any]]:
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    checks = target.get("checks") if isinstance(target.get("checks"), list) else []
    result: list[dict[str, Any]] = []
    for check in checks:
        if isinstance(check, dict):
            result.append(check)
    if result:
        return result

    actions = item.get("source_actions") if isinstance(item.get("source_actions"), dict) else {}
    capacities = {
        "m": _safe_float(target.get("m_capacity_element")),
        "n": _safe_float(target.get("n_capacity_element")),
        "v": _safe_float(target.get("v_capacity_element")),
    }
    units = {"m": "kNm/prvek", "n": "kN/prvek", "v": "kN/prvek"}
    labels = {"m_pos": "M+", "m_neg": "M-", "n_pos": "N+", "n_neg": "N-", "v_pos": "V+", "v_neg": "V-"}
    for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg"):
        requirement = _safe_float(actions.get(key))
        if requirement <= 1e-9:
            continue
        capacity = capacities[key[0]]
        eta = requirement / capacity if capacity > 1e-9 else float("inf")
        result.append(
            {
                "label": labels[key],
                "requirement": requirement,
                "capacity": capacity,
                "unit": units[key[0]],
                "eta": eta,
                "result": "VYHOVUJE" if eta <= 1.0 + 1e-9 else "NEVYHOVUJE",
            }
        )
    return result


def _governing_check(item: dict[str, Any]) -> tuple[str, float]:
    checks = _check_rows(item)
    if checks:
        check = max(checks, key=lambda value: _safe_float(value.get("eta"), -1.0))
        return _text(check.get("label")), max(0.0, _safe_float(check.get("eta")))
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    utilization = max(0.0, _safe_float(target.get("utilization")))
    return ("η max" if target else "-"), utilization


def _geometry_summary(item: dict[str, Any], target: dict[str, Any]) -> str:
    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}
    insulation = target.get("insulation_mm", meta.get("source_insulation_mm"))
    height = target.get("height_mm", meta.get("source_height_mm"))
    cover = target.get("cover_mm", meta.get("source_cover_mm"))
    values: list[str] = []
    if _integer(insulation) != "-":
        values.append(f"I {_integer(insulation)}")
    if _integer(height) != "-":
        values.append(f"h {_integer(height)}")
    if _integer(cover) != "-":
        values.append(f"c {_integer(cover)}")
    return " • ".join(values) or "-"


def _length_summary(item: dict[str, Any], target: dict[str, Any]) -> str:
    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}
    source = _integer(meta.get("source_length_mm"))
    destination = _integer(target.get("length_mm")) if target else "-"
    if source == "-" and destination == "-":
        return "-"
    if destination == "-":
        return f"{source} mm"
    return f"{source} → {destination} mm"


def _draw_kpi_card(draw, box: tuple[int, int, int, int], label: str, value: str, accent, note: str = "") -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0 + 3, y0 + 4, x1 + 3, y1 + 4), radius=12, fill=SHADOW)
    draw.rounded_rectangle(box, radius=12, fill=WHITE, outline=BORDER, width=1)
    draw.rectangle((x0, y0 + 6, x0 + 8, y1 - 6), fill=accent)
    draw.text((x0 + 22, y0 + 12), label.upper(), font=_font(10, True), fill=MUTED)
    draw.text((x0 + 22, y0 + 31), value, font=_font(23, True), fill=accent)
    if note:
        tw = _measure(draw, note, _font(9))[0]
        draw.text((x1 - tw - 14, y1 - 20), note, font=_font(9), fill=MUTED)


def _draw_utilization_bar(draw, box: tuple[int, int, int, int], utilization: float) -> None:
    x0, y0, x1, y1 = box
    value = max(0.0, _safe_float(utilization))
    draw.rounded_rectangle(box, radius=7, fill=(232, 237, 242))
    usable = max(1, x1 - x0)
    fill_ratio = min(value / 1.20, 1.0)
    fill_x = x0 + int(usable * fill_ratio)
    color = SUCCESS if value <= 0.90 else (WARNING if value <= 1.0 else DANGER)
    if fill_x > x0:
        if fill_x - x0 >= 14:
            draw.rounded_rectangle((x0, y0, fill_x, y1), radius=7, fill=color)
        else:
            draw.rectangle((x0, y0, fill_x, y1), fill=color)
    limit_x = x0 + int(usable * (1.0 / 1.20))
    draw.line((limit_x, y0 - 2, limit_x, y1 + 2), fill=DANGER, width=2)
    draw.text((limit_x - 12, y0 - 16), "100 %", font=_font(8, True), fill=DANGER)


def _summary_pages(project_name: str, rows: list[dict[str, Any]], generated: str) -> list[Any]:
    pages: list[Any] = []
    columns = [
        ("position", "Poz.", 68),
        ("quantity", "Ks", 44),
        ("source", "Původní prvek", 365),
        ("target", "Navržený HIT", 385),
        ("length", "Délka", 120),
        ("geometry", "I / h / cnom", 132),
        ("wire", "Ø", 58),
        ("governing", "Rozhoduje", 155),
        ("status", "Stav", 106),
    ]
    table_w = sum(width for _key, _label, width in columns)
    x0 = (PAGE_W - table_w) // 2
    header_font = _font(11, True)
    body_font = _font(10)
    row_h = 60

    total_positions = len(rows)
    total_pieces = sum(int(round(_safe_float(row.get("quantity"), 0.0))) for row in rows)
    passed = sum(1 for row in rows if _text(row.get("status")).upper() == "VYHOVUJE")
    attention = total_positions - passed
    max_eta = max((_governing_check(row)[1] for row in rows), default=0.0)

    first_capacity = 11
    continuation_capacity = 15
    chunks: list[list[dict[str, Any]]] = []
    remaining = list(rows)
    chunks.append(remaining[:first_capacity])
    remaining = remaining[first_capacity:]
    while remaining:
        chunks.append(remaining[:continuation_capacity])
        remaining = remaining[continuation_capacity:]
    if not chunks:
        chunks = [[]]

    for page_index, chunk in enumerate(chunks):
        image, draw = _new_page()
        subtitle = "Tabulka záměn - souhrn" if page_index == 0 else "Tabulka záměn - pokračování"
        _header(draw, project_name, subtitle, generated)
        y = HEADER_H + 22

        if page_index == 0:
            draw.text((MARGIN, y), "Přehled navržených záměn", font=_font(25, True), fill=NAVY)
            draw.text(
                (MARGIN, y + 34),
                "Rychlá kontrola původního prvku, navrženého HIT, základní geometrie a rozhodujícího využití.",
                font=_font(12),
                fill=MUTED,
            )
            y += 70

            gap = 12
            card_w = (PAGE_W - 2 * MARGIN - 4 * gap) // 5
            card_h = 72
            kpis = [
                ("Pozice", str(total_positions), NAVY, "řádků"),
                ("Množství", str(total_pieces), TEAL, "kusů"),
                ("Vyhovuje", str(passed), SUCCESS, "pozic"),
                ("K posouzení", str(attention), WARNING if attention else SUCCESS, "pozic"),
                (
                    "Max. využití",
                    _percent(max_eta),
                    DANGER if max_eta > 1.0 else (WARNING if max_eta > 0.90 else TEAL),
                    "η max",
                ),
            ]
            for index, (label, value, accent, note) in enumerate(kpis):
                cx = MARGIN + index * (card_w + gap)
                _draw_kpi_card(draw, (cx, y, cx + card_w, y + card_h), label, value, accent, note)
            y += card_h + 24
        else:
            draw.text((MARGIN, y), f"Souhrn navržených záměn - strana {page_index + 1}", font=_font(20, True), fill=NAVY)
            y += 38

        draw.rounded_rectangle((x0 - 2, y - 2, x0 + table_w + 2, y + 38), radius=7, fill=NAVY)
        x = x0
        for _key, label, width in columns:
            label_w = _measure(draw, label, header_font)[0]
            draw.text((x + max(4, (width - label_w) // 2), y + 11), label, font=header_font, fill=WHITE)
            x += width
        y += 40

        for row_index, item in enumerate(chunk):
            fill = WHITE if row_index % 2 == 0 else PANEL
            target = item.get("target") if isinstance(item.get("target"), dict) else {}
            status = _text(item.get("status"))
            governing_label, governing_eta = _governing_check(item)
            governing = f"{governing_label} • {_percent(governing_eta)}" if target else "-"
            values = {
                "position": _text(item.get("position")),
                "quantity": _text(item.get("quantity")),
                "source": _text(item.get("source")),
                "target": _text(target.get("designation")) if target else "-",
                "length": _length_summary(item, target),
                "geometry": _geometry_summary(item, target),
                "wire": _wire_diameter(target) if target else "-",
                "governing": governing,
                "status": status,
            }

            draw.rectangle((x0, y, x0 + table_w, y + row_h), fill=fill, outline=BORDER, width=1)
            x = x0
            for key, _label, width in columns:
                value = values[key]
                font = body_font
                color = TEXT
                if key == "status":
                    color, status_fill = _status_style(status)
                    draw.rounded_rectangle(
                        (x + 7, y + 15, x + width - 7, y + row_h - 15),
                        radius=8,
                        fill=status_fill,
                        outline=color,
                        width=1,
                    )
                    font = _font(10, True)
                elif key == "governing":
                    color = SUCCESS if governing_eta <= 0.90 else (WARNING if governing_eta <= 1.0 else DANGER)
                    font = _font(10, True)

                if key in {"source", "target"}:
                    _draw_wrapped(draw, (x + 7, y + 7), value, font, color, width - 14, line_gap=2, max_lines=3)
                else:
                    tw, th = _measure(draw, value, font)
                    draw.text(
                        (x + max(4, (width - tw) // 2), y + max(5, (row_h - th) // 2)),
                        value,
                        font=font,
                        fill=color,
                    )
                x += width
            y += row_h

        legend_y = min(PAGE_H - FOOTER_H - 42, y + 16)
        draw.rounded_rectangle(
            (MARGIN, legend_y, PAGE_W - MARGIN, legend_y + 30),
            radius=7,
            fill=LIGHT_TEAL,
            outline=(190, 216, 225),
            width=1,
        )
        draw.text(
            (MARGIN + 13, legend_y + 9),
            "Rozhoduje = nejvyšší poměr požadavek / únosnost. Tlakový přenos a úplná směrová kontrola jsou uvedeny v detailních listech.",
            font=_font(10),
            fill=NAVY,
        )
        pages.append(image)
    return pages


def _detail_card(draw, box: tuple[int, int, int, int], item: dict[str, Any]) -> None:
    x0, y0, x1, y1 = box
    width = x1 - x0
    status = _text(item.get("status"))
    status_color, status_fill = _status_style(status)
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}

    draw.rounded_rectangle((x0 + 5, y0 + 6, x1 + 5, y1 + 6), radius=15, fill=SHADOW)
    draw.rounded_rectangle(box, radius=15, fill=WHITE, outline=BORDER, width=2)
    draw.rectangle((x0, y0 + 10, x0 + 9, y1 - 10), fill=status_color)

    top_h = 48
    draw.rounded_rectangle((x0 + 9, y0, x1, y0 + top_h), radius=14, fill=NAVY)
    draw.rectangle((x0 + 9, y0 + 28, x1, y0 + top_h), fill=NAVY)
    title = f"POZICE {_text(item.get('position'))}   •   {_text(item.get('quantity'))} ks"
    draw.text((x0 + 28, y0 + 16), title, font=_font(15, True), fill=WHITE)
    badge_w = 126
    draw.rounded_rectangle(
        (x1 - badge_w - 20, y0 + 11, x1 - 20, y0 + 38),
        radius=9,
        fill=status_fill,
        outline=status_color,
        width=1,
    )
    sw = _measure(draw, status, _font(11, True))[0]
    draw.text(
        (x1 - badge_w - 20 + max(6, (badge_w - sw) // 2), y0 + 18),
        status,
        font=_font(11, True),
        fill=status_color,
    )

    content_x = x0 + 26
    content_w = width - 52
    gap = 18
    col_w = (content_w - gap) // 2
    left_x = content_x
    right_x = left_x + col_w + gap
    y = y0 + 62

    for px, label, accent in ((left_x, "PŮVODNÍ PRVEK", TEAL), (right_x, "NAVRŽENÝ HIT", GOLD)):
        draw.rounded_rectangle((px, y, px + col_w, y + 82), radius=9, fill=PANEL, outline=BORDER, width=1)
        draw.rectangle((px, y + 8, px + 6, y + 74), fill=accent)
        draw.text((px + 16, y + 10), label, font=_font(10, True), fill=accent)

    source_name = _text(item.get("source"))
    target_name = _text(target.get("designation")) if target else "Bez navrženého HIT"
    _draw_wrapped(draw, (left_x + 16, y + 30), source_name, _font(13, True), TEXT, col_w - 28, line_gap=2, max_lines=2)
    _draw_wrapped(draw, (right_x + 16, y + 30), target_name, _font(13, True), TEXT, col_w - 28, line_gap=2, max_lines=2)

    source_params = (
        f"I {_integer(meta.get('source_insulation_mm'))} mm   •   h {_integer(meta.get('source_height_mm'))} mm   •   "
        f"cnom {_integer(meta.get('source_cover_mm'))} mm   •   L {_integer(meta.get('source_length_mm'))} mm   •   "
        f"{_text(meta.get('source_concrete'))}"
    )
    target_params = (
        f"HIT-{_text(target.get('series'))}   •   h {_integer(target.get('height_mm'))} mm   •   "
        f"cnom {_integer(target.get('cover_mm'))} mm   •   L {_integer(target.get('length_mm'))} mm   •   "
        f"{_wire_diameter(target)}"
    ) if target else "-"
    param_y = y + 92
    draw.rounded_rectangle((content_x, param_y, content_x + content_w, param_y + 42), radius=8, fill=LIGHT_TEAL, outline=(190, 216, 225), width=1)
    _draw_wrapped(draw, (content_x + 12, param_y + 7), source_params, _font(10), TEXT, col_w - 18, line_gap=1, max_lines=2)
    _draw_wrapped(draw, (right_x + 10, param_y + 7), target_params, _font(10), TEXT, col_w - 18, line_gap=1, max_lines=2)

    governing_label, governing_eta = _governing_check(item)
    util_y = param_y + 53
    draw.text((content_x, util_y), "ROZHODUJÍCÍ KONTROLA", font=_font(10, True), fill=MUTED)
    governing_color = SUCCESS if governing_eta <= 0.90 else (WARNING if governing_eta <= 1.0 else DANGER)
    draw.text(
        (content_x, util_y + 20),
        f"{governing_label}   η = {_percent(governing_eta)}",
        font=_font(18, True),
        fill=governing_color,
    )
    bar_x0 = content_x + 290
    bar_x1 = x1 - 30
    _draw_utilization_bar(draw, (bar_x0, util_y + 23, bar_x1, util_y + 39), governing_eta)

    table_y = util_y + 57
    draw.text((content_x, table_y), "STATICKÁ KONTROLA JEDNOHO PRVKU", font=_font(11, True), fill=NAVY)
    table_y += 20
    table_w = int(content_w * 0.68)
    widths = [70, 145, 145, 92, 104]
    scale = table_w / sum(widths)
    widths = [int(value * scale) for value in widths]
    widths[-1] += table_w - sum(widths)
    headers = ["Účinek", "Požadavek", "Únosnost HIT", "Využití", "Výsledek"]
    x = content_x
    for label, cell_w in zip(headers, widths):
        draw.rectangle((x, table_y, x + cell_w, table_y + 27), fill=NAVY, outline=WHITE, width=1)
        tw = _measure(draw, label, _font(9, True))[0]
        draw.text((x + max(4, (cell_w - tw) // 2), table_y + 8), label, font=_font(9, True), fill=WHITE)
        x += cell_w

    checks = _check_rows(item)
    row_y = table_y + 27
    max_check_rows = 6
    for row_index, check in enumerate(checks[:max_check_rows]):
        x = content_x
        eta = max(0.0, _safe_float(check.get("eta")))
        check_result = _text(check.get("result"))
        values = [
            _text(check.get("label")),
            f"{_number(check.get('requirement'))} {_text(check.get('unit'))}",
            f"{_number(check.get('capacity'))} {_text(check.get('unit'))}",
            _percent(eta),
            check_result,
        ]
        row_fill = WHITE if row_index % 2 == 0 else PANEL
        for index, (value, cell_w) in enumerate(zip(values, widths)):
            draw.rectangle((x, row_y, x + cell_w, row_y + 25), fill=row_fill, outline=BORDER, width=1)
            font = _font(9, index in {0, 3, 4})
            color = TEXT
            if index == 3:
                color = SUCCESS if eta <= 0.90 else (WARNING if eta <= 1.0 else DANGER)
            if index == 4:
                color = SUCCESS if eta <= 1.0 + 1e-9 else DANGER
            tw = _measure(draw, value, font)[0]
            draw.text((x + max(3, (cell_w - tw) // 2), row_y + 7), value, font=font, fill=color)
            x += cell_w
        row_y += 25

    if not checks:
        draw.rectangle((content_x, row_y, content_x + table_w, row_y + 32), fill=PANEL, outline=BORDER, width=1)
        draw.text((content_x + 10, row_y + 10), "Pro tento řádek nejsou dostupné směrové kontroly.", font=_font(9), fill=MUTED)
        row_y += 32
    elif len(checks) > max_check_rows:
        draw.text(
            (content_x, row_y + 4),
            f"+ {len(checks) - max_check_rows} další kontroly jsou uložené v datovém výstupu",
            font=_font(9),
            fill=MUTED,
        )

    info_x = content_x + table_w + 20
    info_w = x1 - 28 - info_x
    info_bottom = max(row_y, table_y + 27 + 4 * 25)
    draw.rounded_rectangle((info_x, table_y, x1 - 28, info_bottom), radius=9, fill=LIGHT_GOLD, outline=(226, 207, 157), width=1)
    draw.text((info_x + 12, table_y + 10), "TECHNICKÁ SHODA", font=_font(10, True), fill=GOLD)
    interaction = _safe_float(target.get("interaction_utilization")) if target else 0.0
    info_lines = [
        f"Celkové využití: {_percent(target.get('utilization')) if target else '-'}",
        f"Interakce M-V: {_percent(interaction)}" if interaction > 0 else "Interakce M-V: neaplikuje se",
        f"Délka: {_text(target.get('length_relation')) if target else '-'}",
        f"Tlakový přenos: {_text(meta.get('source_compression_text'))} → {_text(target.get('compression_text')) if target else '-'}",
        f"Odhad typu: {_text(item.get('estimated_type'))}",
    ]
    iy = table_y + 31
    for index, line in enumerate(info_lines):
        _draw_wrapped(
            draw,
            (info_x + 12, iy),
            line,
            _font(9, index == 0),
            TEXT if index < 3 else MUTED,
            info_w - 24,
            line_gap=1,
            max_lines=2 if index == 3 else 1,
        )
        iy += 25 if index == 3 else 20

    notes = item.get("notes") if isinstance(item.get("notes"), list) else []
    note_text = " • ".join(_text(value) for value in notes if _text(value) != "-")
    if not note_text:
        note_text = "Základní geometrie a statická únosnost odpovídají zvolenému převodu; ostatní projektové podmínky ověřuje projektant."
    note_y = y1 - 48
    draw.line((content_x, note_y - 7, x1 - 28, note_y - 7), fill=BORDER, width=1)
    draw.text((content_x, note_y), "POZNÁMKA", font=_font(9, True), fill=MUTED)
    _draw_wrapped(draw, (content_x + 78, note_y), note_text, _font(9), MUTED, content_w - 82, line_gap=1, max_lines=2)


def _detail_pages(project_name: str, rows: list[dict[str, Any]], generated: str) -> list[Any]:
    pages: list[Any] = []
    cards_per_page = 2
    card_gap = 18
    content_top = HEADER_H + 18
    content_bottom = PAGE_H - FOOTER_H - 14
    card_h = (content_bottom - content_top - card_gap) // cards_per_page
    for start in range(0, len(rows), cards_per_page):
        image, draw = _new_page()
        _header(draw, project_name, "Stručný statický výpočet", generated)
        chunk = rows[start:start + cards_per_page]
        y = content_top
        for item in chunk:
            _detail_card(draw, (MARGIN, y, PAGE_W - MARGIN, y + card_h), item)
            y += card_h + card_gap
        pages.append(image)
    return pages


def write_substitution_pdf(
    path: Path | str,
    *,
    project_name: str,
    rows: Iterable[dict[str, Any]],
    creator: str = "Vytvořil Ing. Jaroslav Kučera",
) -> Path:
    """Vytvoří profesionální vícestránkový PDF výstup tabulky záměn."""
    Image, _ImageDraw, _ImageFont = _pil()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = list(rows)
    if not data:
        raise PdfExportError("Není co exportovat do PDF.")
    generated = datetime.now().strftime("%d.%m.%Y %H:%M")
    pages = _summary_pages(project_name, data, generated)
    pages.extend(_detail_pages(project_name, data, generated))
    total = len(pages)
    for index, page in enumerate(pages, start=1):
        draw = _pil()[1].Draw(page)
        _footer(draw, index, total, creator)
    first, rest = pages[0], pages[1:]
    first.save(
        target,
        format="PDF",
        resolution=float(DPI),
        save_all=True,
        append_images=rest,
        quality=95,
        subsampling=0,
        title=f"TURTO ISO - Tabulka záměn - {_text(project_name)}",
        author=creator,
        subject="Předběžná katalogová záměna izolačních nosníků za Leviat HIT",
        creator="TURTO ISO",
    )
    for page in pages:
        try:
            page.close()
        except Exception:
            pass
    if not target.exists() or target.stat().st_size < 1000:
        raise PdfExportError("PDF se nepodařilo korektně vytvořit.")
    return target
