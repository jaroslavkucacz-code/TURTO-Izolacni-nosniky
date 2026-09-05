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


def _number(value: Any, decimals: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(number):
        return "-"
    return f"{number:.{decimals}f}".replace(".", ",")


def _percent(value: Any) -> str:
    try:
        number = float(value) * 100.0
    except (TypeError, ValueError):
        return "-"
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
    if value in {"NELZE", "CHYBA"}:
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


def _draw_wrapped(draw, xy: tuple[int, int], text: str, font, fill, max_width: int, line_gap: int = 4,
                  max_lines: int | None = None) -> int:
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
    note = "Předběžná katalogová záměna M/N/V; požární odolnost se neposuzuje. Ověřit projektantem."
    note_w = _measure(draw, note, _font(11))[0]
    draw.text(((PAGE_W - note_w) // 2, y + 9), note, font=_font(11), fill=MUTED)
    page = f"Strana {page_no}/{total_pages}"
    page_w = _measure(draw, page, _font(12))[0]
    draw.text((PAGE_W - MARGIN - page_w, y + 8), page, font=_font(12), fill=MUTED)


def _summary_pages(project_name: str, rows: list[dict[str, Any]], generated: str) -> list[Any]:
    pages: list[Any] = []
    columns = [
        ("position", "Poz.", 80),
        ("quantity", "Ks", 45),
        ("source", "Původní prvek", 405),
        ("source_length", "L zdroj", 85),
        ("source_compression", "Tlakový přenos", 185),
        ("target", "Navržený HIT", 390),
        ("target_length", "L HIT", 78),
        ("wire", "Ø", 54),
        ("util", "Využití", 85),
        ("status", "Stav", 105),
    ]
    table_w = sum(width for _key, _label, width in columns)
    x0 = (PAGE_W - table_w) // 2
    header_font = _font(12, True)
    body_font = _font(11)
    row_h = 58
    available_y = PAGE_H - FOOTER_H - 42
    rows_per_page = max(1, (available_y - HEADER_H - 95) // row_h)
    chunks = [rows[i:i + rows_per_page] for i in range(0, len(rows), rows_per_page)] or [[]]
    for page_index, chunk in enumerate(chunks):
        image, draw = _new_page()
        _header(draw, project_name, "Tabulka záměn - souhrn", generated)
        y = HEADER_H + 22
        draw.text((MARGIN, y), "Souhrn navržených záměn", font=_font(22, True), fill=NAVY)
        y += 36
        draw.text(
            (MARGIN, y),
            "Výběr je veden jeden původní prvek za jeden HIT; shoda délky, krytí, výšky, izolantu a tlakového přenosu je součástí kontroly.",
            font=_font(12), fill=MUTED,
        )
        y += 35
        x = x0
        for _key, label, width in columns:
            draw.rectangle((x, y, x + width, y + 34), fill=NAVY, outline=WHITE, width=1)
            label_w = _measure(draw, label, header_font)[0]
            draw.text((x + max(5, (width - label_w) // 2), y + 9), label, font=header_font, fill=WHITE)
            x += width
        y += 34
        for idx, item in enumerate(chunk):
            fill = WHITE if idx % 2 == 0 else PANEL
            x = x0
            target = item.get("target") if isinstance(item.get("target"), dict) else {}
            status = _text(item.get("status"))
            values = {
                "position": _text(item.get("position")),
                "quantity": _text(item.get("quantity")),
                "source": _text(item.get("source")),
                "source_length": f"{_text(item.get('source_meta', {}).get('source_length_mm'))} mm",
                "source_compression": _text(item.get("source_meta", {}).get("source_compression_text")),
                "target": _text(target.get("designation")) if target else "-",
                "target_length": f"{_text(target.get('length_mm'))} mm" if target else "-",
                "wire": _wire_diameter(target) if target else "-",
                "util": _percent(target.get("utilization")) if target else "-",
                "status": status,
            }
            for key, _label, width in columns:
                draw.rectangle((x, y, x + width, y + row_h), fill=fill, outline=BORDER, width=1)
                value = values[key]
                font = body_font
                color = TEXT
                if key == "status":
                    color, status_fill = _status_style(status)
                    draw.rectangle((x + 5, y + 11, x + width - 5, y + row_h - 11), fill=status_fill, outline=color, width=1)
                    font = _font(11, True)
                if key in {"source", "source_compression", "target"}:
                    _draw_wrapped(draw, (x + 6, y + 6), value, font, color, width - 12, line_gap=2, max_lines=3)
                else:
                    tw, th = _measure(draw, value, font)
                    draw.text((x + max(4, (width - tw) // 2), y + max(5, (row_h - th) // 2)), value, font=font, fill=color)
                x += width
            y += row_h
        pages.append(image)
    return pages


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
        "m": float(target.get("m_capacity_element", 0.0) or 0.0),
        "n": float(target.get("n_capacity_element", 0.0) or 0.0),
        "v": float(target.get("v_capacity_element", 0.0) or 0.0),
    }
    units = {"m": "kNm/prvek", "n": "kN/prvek", "v": "kN/prvek"}
    labels = {"m_pos": "M+", "m_neg": "M-", "n_pos": "N+", "n_neg": "N-", "v_pos": "V+", "v_neg": "V-"}
    for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg"):
        requirement = float(actions.get(key, 0.0) or 0.0)
        if requirement <= 1e-9:
            continue
        capacity = capacities[key[0]]
        eta = requirement / capacity if capacity > 1e-9 else float("inf")
        result.append({
            "label": labels[key], "requirement": requirement, "capacity": capacity,
            "unit": units[key[0]], "eta": eta, "result": "VYHOVUJE" if eta <= 1.0 + 1e-9 else "NEVYHOVUJE",
        })
    return result


def _detail_card(draw, box: tuple[int, int, int, int], item: dict[str, Any]) -> None:
    x0, y0, x1, y1 = box
    width = x1 - x0
    draw.rounded_rectangle(box, radius=12, fill=WHITE, outline=BORDER, width=2)
    status = _text(item.get("status"))
    status_color, status_fill = _status_style(status)
    draw.rounded_rectangle((x0 + 10, y0 + 9, x1 - 10, y0 + 45), radius=8, fill=NAVY)
    title = f"Pozice {_text(item.get('position'))}  |  {_text(item.get('quantity'))} ks"
    draw.text((x0 + 24, y0 + 17), title, font=_font(15, True), fill=WHITE)
    badge_w = 112
    draw.rounded_rectangle((x1 - badge_w - 20, y0 + 14, x1 - 20, y0 + 40), radius=8, fill=status_fill, outline=status_color, width=1)
    sw = _measure(draw, status, _font(11, True))[0]
    draw.text((x1 - badge_w - 20 + max(5, (badge_w - sw) // 2), y0 + 20), status, font=_font(11, True), fill=status_color)

    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}
    source = _text(item.get("source"))
    target_name = _text(target.get("designation")) if target else "Bez navrženého HIT"
    col_gap = 20
    col_w = (width - 48 - col_gap) // 2
    left_x = x0 + 24
    right_x = left_x + col_w + col_gap
    y = y0 + 57
    draw.text((left_x, y), "PŮVODNÍ PRVEK", font=_font(11, True), fill=TEAL)
    draw.text((right_x, y), "NAVRŽENÝ HIT", font=_font(11, True), fill=GOLD)
    _draw_wrapped(draw, (left_x, y + 18), source, _font(13, True), TEXT, col_w, line_gap=2, max_lines=2)
    _draw_wrapped(draw, (right_x, y + 18), target_name, _font(13, True), TEXT, col_w, line_gap=2, max_lines=2)

    y = y0 + 112
    param_y2 = y + 51
    draw.rounded_rectangle((x0 + 16, y, x1 - 16, param_y2), radius=7, fill=PANEL, outline=BORDER, width=1)
    source_params = (
        f"I {_text(meta.get('source_insulation_mm'))} mm | cnom {_text(meta.get('source_cover_mm'))} mm | "
        f"h {_text(meta.get('source_height_mm'))} mm | L {_text(meta.get('source_length_mm'))} mm | {_text(meta.get('source_concrete'))}"
    )
    target_params = (
        f"HIT-{_text(target.get('series'))} | cnom {_text(target.get('cover_mm'))} mm | h {_text(target.get('height_mm'))} mm | "
        f"L {_text(target.get('length_mm'))} mm | {_wire_diameter(target)}"
    ) if target else "-"
    _draw_wrapped(draw, (left_x, y + 7), source_params, _font(11), TEXT, col_w, line_gap=1, max_lines=2)
    _draw_wrapped(draw, (right_x, y + 7), target_params, _font(11), TEXT, col_w, line_gap=1, max_lines=2)
    pressure = f"Tlakový přenos: {_text(meta.get('source_compression_text'))} -> {_text(target.get('compression_text')) if target else '-'}"
    _draw_wrapped(draw, (left_x, y + 30), pressure, _font(10), MUTED, width - 48, line_gap=1, max_lines=1)

    y = y0 + 172
    draw.text((left_x, y), "STATICKÁ KONTROLA JEDNOHO PRVKU", font=_font(11, True), fill=NAVY)
    y += 18
    table_x = left_x
    widths = [74, 105, 105, 100, 90]
    headers = ["Účinek", "Požadavek", "Únosnost HIT", "Využití", "Výsledek"]
    x = table_x
    for label, cell_w in zip(headers, widths):
        draw.rectangle((x, y, x + cell_w, y + 24), fill=LIGHT_TEAL, outline=BORDER, width=1)
        tw = _measure(draw, label, _font(9, True))[0]
        draw.text((x + max(3, (cell_w - tw) // 2), y + 7), label, font=_font(9, True), fill=NAVY)
        x += cell_w
    checks = _check_rows(item)
    row_y = y + 24
    max_check_rows = 3
    for check in checks[:max_check_rows]:
        x = table_x
        eta = float(check.get("eta", 0.0) or 0.0)
        values = [
            _text(check.get("label")),
            f"{_number(check.get('requirement'))} {_text(check.get('unit'))}",
            f"{_number(check.get('capacity'))} {_text(check.get('unit'))}",
            _percent(eta),
            _text(check.get("result")),
        ]
        for index, (value, cell_w) in enumerate(zip(values, widths)):
            draw.rectangle((x, row_y, x + cell_w, row_y + 23), fill=WHITE, outline=BORDER, width=1)
            font = _font(9, index == 4)
            color = SUCCESS if index == 4 and eta <= 1.0 + 1e-9 else (DANGER if index == 4 else TEXT)
            tw = _measure(draw, value, font)[0]
            draw.text((x + max(3, (cell_w - tw) // 2), row_y + 6), value, font=font, fill=color)
            x += cell_w
        row_y += 23
    if len(checks) > max_check_rows:
        draw.text((table_x, row_y + 2), f"+ {len(checks) - max_check_rows} další směrové kontroly v datovém výstupu", font=_font(9), fill=MUTED)

    info_x = table_x + sum(widths) + 22
    info_w = x1 - 24 - info_x
    interaction = float(target.get("interaction_utilization", 0.0) or 0.0) if target else 0.0
    overall = float(target.get("utilization", 0.0) or 0.0) if target else 0.0
    info_lines = [
        f"Celkové využití: {_percent(overall)}",
        f"Interakce M-V: {_percent(interaction)}" if interaction > 0 else "Interakce M-V: neaplikuje se",
        f"Délka: {_text(target.get('length_relation')) if target else '-'}",
        f"Odhad typu: {_text(item.get('estimated_type'))}",
    ]
    draw.rounded_rectangle((info_x, y, x1 - 24, y + 93), radius=7, fill=LIGHT_GOLD, outline=(226, 207, 157), width=1)
    iy = y + 8
    for line in info_lines:
        _draw_wrapped(draw, (info_x + 10, iy), line, _font(10, line.startswith("Celkové")), TEXT, info_w - 20, line_gap=1, max_lines=1)
        iy += 20

    note_y = y1 - 57
    notes = item.get("notes") if isinstance(item.get("notes"), list) else []
    note_text = " • ".join(_text(value) for value in notes if _text(value) != "-")
    if not note_text:
        note_text = "Krytí, výška, izolant, délka a tlakový přenos odpovídají zvolenému převodu."
    draw.line((x0 + 20, note_y - 5, x1 - 20, note_y - 5), fill=BORDER, width=1)
    _draw_wrapped(draw, (x0 + 24, note_y), note_text, _font(10), MUTED, width - 48, line_gap=1, max_lines=2)


def _detail_pages(project_name: str, rows: list[dict[str, Any]], generated: str) -> list[Any]:
    pages: list[Any] = []
    cards_per_page = 3
    card_gap = 14
    content_top = HEADER_H + 18
    content_bottom = PAGE_H - FOOTER_H - 12
    card_h = (content_bottom - content_top - card_gap * (cards_per_page - 1)) // cards_per_page
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
    """Vytvoří profesionální vícestránkový PDF výstup tabulky záměn.

    PDF je záměrně generováno přes Pillow, které je již součástí závislostí
    parseru DoP. Nevzniká tak nová runtime závislost pouze kvůli reportu.
    """
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
