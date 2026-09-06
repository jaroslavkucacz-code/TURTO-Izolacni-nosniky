from __future__ import annotations

"""Vektorový PDF výstup tabulky záměn TURTO ISO.

Všechny texty, tabulky, rámečky, grafy využití i firemní logo TURTO se kreslí přímo do PDF
pomocí ReportLabu. Dokument je na A4 na výšku, neobsahuje rastrové snímky stránek,
text je vyhledávatelný a lze jej označit a kopírovat.
"""

from dataclasses import dataclass
from datetime import datetime
import importlib
import importlib.util
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import site
from typing import Any, Iterable


class PdfExportError(RuntimeError):
    pass


_REPORTLAB_REQUIREMENT = "reportlab>=4.2,<5"
_BACKEND: "_Backend | None" = None


@dataclass(frozen=True)
class _Backend:
    canvas_module: Any
    pagesizes: Any
    colors: Any
    pdfmetrics: Any
    ttfont: Any
    regular_font: str
    bold_font: str


def _install_reportlab() -> None:
    """Jednorázově doplní ReportLab do stejného Pythonu, ze kterého běží TURTO."""
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--quiet",
        _REPORTLAB_REQUIREMENT,
    ]
    # Mimo virtuální prostředí je uživatelská instalace bezpečnější a nevyžaduje
    # administrátorská práva. Ve venv se --user použít nesmí.
    in_venv = getattr(sys, "base_prefix", sys.prefix) != sys.prefix
    if not in_venv and not getattr(sys, "frozen", False):
        command.insert(-1, "--user")

    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        raise PdfExportError(
            "Vektorový PDF modul ReportLab není dostupný a automatickou instalaci se nepodařilo spustit.\n\n"
            f"Spusťte ručně: {sys.executable} -m pip install reportlab\n\n{exc}"
        ) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "neznámá chyba pip").strip()
        if len(detail) > 1800:
            detail = detail[-1800:]
        raise PdfExportError(
            "Vektorový PDF modul ReportLab není dostupný a automatická instalace selhala.\n\n"
            f"Spusťte ručně: {sys.executable} -m pip install reportlab\n\n{detail}"
        )
    try:
        site.addsitedir(site.getusersitepackages())
    except Exception:
        pass
    importlib.invalidate_caches()


def _font_pairs() -> list[tuple[Path, Path]]:
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = [
        (windows / "calibri.ttf", windows / "calibrib.ttf"),
        (windows / "arial.ttf", windows / "arialbd.ttf"),
        (windows / "aptos.ttf", windows / "aptos-bold.ttf"),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ),
        (
            Path("/Library/Fonts/Arial.ttf"),
            Path("/Library/Fonts/Arial Bold.ttf"),
        ),
    ]
    return [(regular, bold) for regular, bold in candidates if regular.exists() and bold.exists()]


def _load_backend() -> _Backend:
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND

    if importlib.util.find_spec("reportlab") is None:
        _install_reportlab()

    try:
        from reportlab.lib import colors, pagesizes
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas as canvas_module
    except Exception as exc:
        raise PdfExportError(
            "ReportLab je nainstalovaný, ale vektorový PDF modul se nepodařilo načíst.\n\n"
            f"{exc}"
        ) from exc

    regular_name = "Helvetica"
    bold_name = "Helvetica-Bold"
    # Na běžných Windows použijeme přednostně Calibri, dále Arial/Aptos;
    # na CI a Linuxu DejaVu Sans. Každá dvojice má vlastní registrační jméno,
    # takže neúspěch jednoho fontu neblokuje další bezpečný fallback.
    for index, pair in enumerate(_font_pairs()):
        candidate_regular = f"TURTOBody{index}"
        candidate_bold = f"TURTOBodyBold{index}"
        try:
            registered = set(pdfmetrics.getRegisteredFontNames())
            if candidate_regular not in registered:
                pdfmetrics.registerFont(TTFont(candidate_regular, str(pair[0])))
            if candidate_bold not in registered:
                pdfmetrics.registerFont(TTFont(candidate_bold, str(pair[1])))
        except Exception:
            continue
        regular_name = candidate_regular
        bold_name = candidate_bold
        break

    _BACKEND = _Backend(
        canvas_module=canvas_module,
        pagesizes=pagesizes,
        colors=colors,
        pdfmetrics=pdfmetrics,
        ttfont=TTFont,
        regular_font=regular_name,
        bold_font=bold_name,
    )
    return _BACKEND


def ensure_vector_pdf_backend() -> None:
    """Veřejný preflight volaný z UI před vlastním exportem."""
    _load_backend()


# Barvy odpovídají grafice TURTO ISO. Všechny prvky se kreslí vektorově.
NAVY = "#17324D"
NAVY_2 = "#254862"
TEAL = "#0E6E8E"
GOLD = "#B88B30"
TEXT = "#1B222C"
MUTED = "#5B6878"
BORDER = "#D0DAE4"
PANEL = "#F7F9FB"
WHITE = "#FFFFFF"
SUCCESS = "#2C7A54"
WARNING = "#9E6D16"
DANGER = "#A63D40"
LIGHT_TEAL = "#E7F3F7"
LIGHT_GOLD = "#FCF6E5"
LIGHT_GREEN = "#EAF6EF"
LIGHT_RED = "#FDEDEE"
SHADOW = "#E2E8EE"


@dataclass(frozen=True)
class _Layout:
    page_w: float
    page_h: float
    margin: float = 18.0
    header_h: float = 47.0
    footer_h: float = 15.0


_LAYOUT: _Layout | None = None


def _layout(backend: _Backend) -> _Layout:
    global _LAYOUT
    if _LAYOUT is None:
        # Technický výstup je záměrně na A4 na výšku. Pro souhrn i detail
        # tak vzniká přirozený dokument vhodný k tisku a založení.
        page_w, page_h = backend.pagesizes.A4
        _LAYOUT = _Layout(float(page_w), float(page_h))
    return _LAYOUT

def _text(value: Any) -> str:
    if value in (None, ""):
        return "-"
    text = str(value).replace("\u00a0", " ").strip()
    # ReportLab/TTF zvládá češtinu i symboly, ale typografické pomlčky v datech
    # sjednotíme kvůli konzistentnímu kopírování textu z PDF.
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    return text or "-"


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
    try:
        diameter = int(target.get("wire_diameter_mm") or 0)
    except (TypeError, ValueError):
        diameter = 0
    if diameter in {6, 8, 10, 12}:
        return f"Ø {diameter:02d}"
    match = re.search(r"-(06|08|10|12)(?:$|[-\s])", _text(target.get("designation")))
    return f"Ø {match.group(1)}" if match else "-"


def _status_palette(status: str) -> tuple[str, str]:
    value = _text(status).upper()
    if value == "VYHOVUJE":
        return SUCCESS, LIGHT_GREEN
    if value in {"KONTROLA", "NEPOSOUZENO", "JIŽ HIT"}:
        return WARNING, LIGHT_GOLD
    if value in {"NELZE", "CHYBA", "NEVYHOVUJE"}:
        return DANGER, LIGHT_RED
    return MUTED, PANEL


def _check_rows(item: dict[str, Any]) -> list[dict[str, Any]]:
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    checks = target.get("checks") if isinstance(target.get("checks"), list) else []
    result = [dict(check) for check in checks if isinstance(check, dict)]
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
        if not target:
            eta = float("nan")
            result_text = "NEPOSOUZENO"
        else:
            eta = requirement / capacity if capacity > 1e-9 else float("inf")
            result_text = "VYHOVUJE" if eta <= 1.0 + 1e-9 else "NEVYHOVUJE"
        result.append(
            {
                "label": labels[key],
                "requirement": requirement,
                "capacity": capacity if target else None,
                "unit": units[key[0]],
                "eta": eta,
                "result": result_text,
            }
        )
    return result


def _governing_check(item: dict[str, Any]) -> tuple[str, float]:
    checks = _check_rows(item)
    if checks:
        finite = [check for check in checks if math.isfinite(_safe_float(check.get("eta"), float("nan")))]
        if finite:
            check = max(finite, key=lambda value: _safe_float(value.get("eta"), -1.0))
            return _text(check.get("label")), max(0.0, _safe_float(check.get("eta")))
        return _text(checks[0].get("label")), float("nan")
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    utilization = max(0.0, _safe_float(target.get("utilization")))
    return ("eta max" if target else "-"), utilization


def _geometry_summary(item: dict[str, Any], target: dict[str, Any]) -> str:
    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}
    insulation = target.get("target_insulation_mm", target.get("insulation_mm", meta.get("source_insulation_mm")))
    height = target.get("height_mm", meta.get("source_height_mm"))
    cover = target.get("cover_mm", meta.get("source_cover_mm"))
    values = [_integer(insulation), _integer(height), _integer(cover)]
    return " / ".join(values) if any(value != "-" for value in values) else "-"


def _length_summary(item: dict[str, Any], target: dict[str, Any]) -> str:
    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}
    source = _integer(meta.get("source_length_mm"))
    destination = _integer(target.get("length_mm")) if target else "-"
    if source == "-" and destination == "-":
        return "-"
    if destination == "-":
        return source
    return f"{source} -> {destination}"


def _rl_color(backend: _Backend, value: str):
    return backend.colors.HexColor(value)


def _set_fill(c, backend: _Backend, color: str) -> None:
    c.setFillColor(_rl_color(backend, color))


def _set_stroke(c, backend: _Backend, color: str) -> None:
    c.setStrokeColor(_rl_color(backend, color))


def _rect(c, backend: _Backend, layout: _Layout, x: float, y: float, w: float, h: float, *,
          fill: str | None = None, stroke: str | None = None, width: float = 0.5, radius: float = 0.0) -> None:
    if fill:
        _set_fill(c, backend, fill)
    if stroke:
        _set_stroke(c, backend, stroke)
    c.setLineWidth(width)
    bottom = layout.page_h - y - h
    if radius > 0:
        c.roundRect(x, bottom, w, h, radius, stroke=1 if stroke else 0, fill=1 if fill else 0)
    else:
        c.rect(x, bottom, w, h, stroke=1 if stroke else 0, fill=1 if fill else 0)


def _line(c, backend: _Backend, layout: _Layout, x1: float, y1: float, x2: float, y2: float,
          color: str = BORDER, width: float = 0.5) -> None:
    _set_stroke(c, backend, color)
    c.setLineWidth(width)
    c.line(x1, layout.page_h - y1, x2, layout.page_h - y2)


def _text_width(backend: _Backend, value: str, font: str, size: float) -> float:
    return float(backend.pdfmetrics.stringWidth(_text(value), font, size))


def _split_token(backend: _Backend, token: str, font: str, size: float, max_width: float) -> list[str]:
    if _text_width(backend, token, font, size) <= max_width:
        return [token]
    pieces: list[str] = []
    rest = token
    while rest:
        lo, hi = 1, len(rest)
        best = 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if _text_width(backend, rest[:mid], font, size) <= max_width:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        pieces.append(rest[:best])
        rest = rest[best:]
    return pieces


def _wrap_text(backend: _Backend, value: Any, font: str, size: float, max_width: float,
               max_lines: int | None = None) -> list[str]:
    paragraphs = _text(value).splitlines() or ["-"]
    lines: list[str] = []
    for paragraph in paragraphs:
        words: list[str] = []
        for raw_word in paragraph.split() or [""]:
            words.extend(_split_token(backend, raw_word, font, size, max_width))
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if not current or _text_width(backend, candidate, font, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        tail = lines[-1].rstrip()
        suffix = "..."
        while tail and _text_width(backend, tail + suffix, font, size) > max_width:
            tail = tail[:-1]
        lines[-1] = tail.rstrip() + suffix
    return lines or ["-"]


def _draw_text(c, backend: _Backend, layout: _Layout, value: Any, x: float, y: float, *,
               size: float = 7.0, color: str = TEXT, bold: bool = False,
               max_width: float | None = None, max_lines: int | None = None,
               leading: float | None = None, align: str = "left") -> float:
    font = backend.bold_font if bold else backend.regular_font
    line_height = leading or size * 1.22
    lines = _wrap_text(backend, value, font, size, max_width, max_lines) if max_width else [_text(value)]
    _set_fill(c, backend, color)
    c.setFont(font, size)
    for index, line in enumerate(lines):
        baseline = layout.page_h - (y + size + index * line_height)
        tx = x
        if max_width is not None and align in {"center", "right"}:
            width = _text_width(backend, line, font, size)
            tx = x + (max_width - width) / 2 if align == "center" else x + max_width - width
        c.drawString(tx, baseline, line)
    return max(line_height, len(lines) * line_height)


def _draw_centered(c, backend: _Backend, layout: _Layout, value: Any, x: float, y: float,
                   w: float, h: float, *, size: float = 7.0, color: str = TEXT, bold: bool = False,
                   max_lines: int = 1) -> None:
    font = backend.bold_font if bold else backend.regular_font
    lines = _wrap_text(backend, value, font, size, max(1.0, w - 6), max_lines)
    leading = size * 1.15
    total_h = len(lines) * leading
    start_y = y + max(1.0, (h - total_h) / 2)
    _draw_text(c, backend, layout, "\n".join(lines), x + 3, start_y, size=size, color=color, bold=bold,
               max_width=w - 6, max_lines=max_lines, leading=leading, align="center")



def _draw_turto_logo(
    c,
    backend: _Backend,
    layout: _Layout,
    x: float,
    y: float,
    w: float = 116.0,
    h: float = 36.0,
) -> None:
    # Kompaktní vektorová varianta firemního loga TURTO pro záhlaví PDF.
    # Logo je sestaveno výhradně z PDF čar a textu.
    _rect(c, backend, layout, x, y, w, h, fill=WHITE, stroke="#C8D2DC", width=0.45, radius=4.2)

    sx = x + 6.0
    sy = y + 5.0
    _set_stroke(c, backend, "#111820")
    c.setLineCap(1)
    c.setLineJoin(1)
    c.setLineWidth(1.25)
    segments = (
        (0, 25, 0, 11), (0, 11, 10, 5), (10, 5, 10, 25),
        (7, 25, 7, 16), (7, 16, 18, 9), (18, 9, 27, 15), (27, 15, 27, 25),
        (13, 25, 13, 19), (13, 19, 20, 15), (20, 15, 35, 23), (35, 23, 35, 25),
    )
    for x1, y1, x2, y2 in segments:
        _line(c, backend, layout, sx + x1, sy + y1, sx + x2, sy + y2, "#111820", 1.25)

    brand_red = "#B81720"
    text_x = x + 44.0
    _draw_text(c, backend, layout, "TURTO", text_x, y + 4.4, size=12.8, color=brand_red, bold=True)
    _draw_text(c, backend, layout, "ISO", x + w - 22.0, y + 5.5, size=6.3, color=GOLD, bold=True)
    _draw_text(
        c,
        backend,
        layout,
        "PRVKY DO MONOLITU",
        text_x,
        y + 22.4,
        size=3.55,
        color="#111820",
        bold=True,
        max_width=w - 49.0,
        max_lines=1,
    )


def _header(c, backend: _Backend, layout: _Layout, project_name: str, subtitle: str, generated: str) -> None:
    _rect(c, backend, layout, 0, 0, layout.page_w, layout.header_h, fill=NAVY)
    _rect(c, backend, layout, 0, layout.header_h - 2.8, layout.page_w, 2.8, fill=GOLD)

    logo_w = 116.0
    _draw_turto_logo(c, backend, layout, layout.margin, 5.0, logo_w, 36.0)

    right_w = 156.0
    subtitle_x = layout.margin + logo_w + 10.0
    subtitle_w = layout.page_w - layout.margin - right_w - 10.0 - subtitle_x
    _draw_text(
        c,
        backend,
        layout,
        subtitle,
        subtitle_x,
        8.0,
        size=8.7,
        color="#E1EDF5",
        bold=True,
        max_width=max(80.0, subtitle_w),
        max_lines=2,
        leading=10.2,
    )
    _draw_text(
        c,
        backend,
        layout,
        f"Projekt: {_text(project_name)}",
        layout.page_w - layout.margin - right_w,
        6.0,
        size=6.4,
        color=WHITE,
        bold=True,
        max_width=right_w,
        max_lines=1,
        align="right",
    )
    _draw_text(
        c,
        backend,
        layout,
        f"Vygenerováno: {generated}",
        layout.page_w - layout.margin - right_w,
        20.0,
        size=5.5,
        color="#D7E3ED",
        max_width=right_w,
        max_lines=1,
        align="right",
    )

def _footer(c, backend: _Backend, layout: _Layout, page_no: int, total_pages: int, creator: str) -> None:
    y = layout.page_h - layout.footer_h
    _line(c, backend, layout, layout.margin, y, layout.page_w - layout.margin, y, BORDER, 0.6)
    _draw_text(c, backend, layout, creator, layout.margin, y + 5.0, size=5.7, color=MUTED, bold=True)
    note = "Předběžná katalogová záměna M/N/V a základní geometrie; požární odolnost se neposuzuje. Ověřit projektantem."
    _draw_text(c, backend, layout, note, layout.margin + 150, y + 5.0, size=5.3, color=MUTED,
               max_width=layout.page_w - 2 * layout.margin - 300, max_lines=1, align="center")
    _draw_text(c, backend, layout, f"Strana {page_no}/{total_pages}", layout.page_w - layout.margin - 70,
               y + 5.0, size=5.7, color=MUTED, max_width=70, align="right")


def _draw_kpi_card(c, backend: _Backend, layout: _Layout, x: float, y: float, w: float, h: float,
                   label: str, value: str, accent: str, note: str = "") -> None:
    _rect(c, backend, layout, x + 1.2, y + 1.5, w, h, fill=SHADOW, radius=3.8)
    _rect(c, backend, layout, x, y, w, h, fill=WHITE, stroke=BORDER, width=0.35, radius=3.8)
    _rect(c, backend, layout, x, y + 2.5, 3.1, h - 5.0, fill=accent, radius=1.1)
    _draw_text(c, backend, layout, label.upper(), x + 8.0, y + 4.2, size=4.15, color=MUTED, bold=True)
    _draw_text(c, backend, layout, value, x + 8.0, y + 12.2, size=9.4, color=accent, bold=True)
    if note:
        _draw_text(
            c,
            backend,
            layout,
            note,
            x + 8.0,
            y + h - 7.4,
            size=3.65,
            color=MUTED,
            max_width=w - 13.0,
            max_lines=1,
            align="right",
        )

def _draw_utilization_bar(c, backend: _Backend, layout: _Layout, x: float, y: float, w: float, h: float,
                          utilization: float) -> None:
    value = max(0.0, _safe_float(utilization))
    _rect(c, backend, layout, x, y, w, h, fill="#E8EDF2", radius=h / 2)
    ratio = min(value / 1.20, 1.0)
    fill_w = w * ratio
    color = SUCCESS if value <= 0.90 else (WARNING if value <= 1.0 else DANGER)
    if fill_w > 0.5:
        _rect(c, backend, layout, x, y, fill_w, h, fill=color, radius=min(h / 2, fill_w / 2))
    limit_x = x + w * (1.0 / 1.20)
    _line(c, backend, layout, limit_x, y - 1.4, limit_x, y + h + 1.4, DANGER, 0.8)
    _draw_text(c, backend, layout, "100 %", limit_x - 9, y - 7.7, size=4.5, color=DANGER, bold=True)


def _summary_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    quantity = sum(max(0, int(_safe_float(row.get("quantity"), 0))) for row in rows)
    ok = sum(1 for row in rows if _text(row.get("status")).upper() == "VYHOVUJE")
    review = sum(1 for row in rows if _text(row.get("status")).upper() != "VYHOVUJE")
    utilizations = [
        _safe_float((row.get("target") or {}).get("utilization"))
        for row in rows if isinstance(row.get("target"), dict)
    ]
    return {
        "positions": len(rows),
        "quantity": quantity,
        "ok": ok,
        "review": review,
        "max_utilization": max(utilizations, default=0.0),
    }


def _summary_row_values(item: dict[str, Any]) -> dict[str, str]:
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    governing_label, governing_eta = _governing_check(item)
    status = _text(item.get("status"))
    return {
        "position": _text(item.get("position")),
        "quantity": _text(item.get("quantity")),
        "source": _text(item.get("source")),
        "target": _text(target.get("designation")) if target else "-",
        "length": _length_summary(item, target),
        "geometry": _geometry_summary(item, target),
        "wire": _wire_diameter(target) if target else "-",
        "governing": f"{governing_label} • {_percent(governing_eta)}" if governing_label != "-" else "-",
        "status": status,
    }


def _summary_capacities(layout: _Layout) -> tuple[int, int]:
    row_h = 27.0
    first_table_top = 111.0
    other_table_top = 69.0
    table_header_h = 16.0
    bottom = layout.page_h - layout.footer_h - 5.0
    reserve_for_note = 20.0
    first = max(1, int((bottom - first_table_top - table_header_h - reserve_for_note) // row_h))
    other = max(1, int((bottom - other_table_top - table_header_h - reserve_for_note) // row_h))
    return first, other

def _summary_chunks(rows: list[dict[str, Any]], layout: _Layout) -> list[list[dict[str, Any]]]:
    first_cap, other_cap = _summary_capacities(layout)
    if not rows:
        return [[]]
    chunks = [rows[:first_cap]]
    index = first_cap
    while index < len(rows):
        chunks.append(rows[index:index + other_cap])
        index += other_cap
    return chunks


def _draw_summary_table(c, backend: _Backend, layout: _Layout, rows: list[dict[str, Any]], y: float) -> float:
    content_w = layout.page_w - 2 * layout.margin
    fixed = [
        ("position", "Poz.", 28.0, "center"),
        ("quantity", "Ks", 20.0, "center"),
        ("source", "Původní prvek", 132.0, "left"),
        ("target", "Navržený HIT", 147.0, "left"),
        ("length", "L [mm]", 48.0, "center"),
        ("geometry", "I/h/c", 45.0, "center"),
        ("wire", "Ø", 22.0, "center"),
        ("governing", "Rozhoduje", 58.0, "center"),
    ]
    used = sum(width for _key, _label, width, _align in fixed)
    columns = [*fixed, ("status", "Stav", max(48.0, content_w - used), "center")]

    header_h = 16.0
    row_h = 27.0
    x = layout.margin
    for _key, label, width, _align in columns:
        _rect(c, backend, layout, x, y, width, header_h, fill=NAVY, stroke=WHITE, width=0.3)
        _draw_centered(c, backend, layout, label, x, y, width, header_h, size=4.8, color=WHITE, bold=True)
        x += width
    y += header_h

    for index, item in enumerate(rows):
        values = _summary_row_values(item)
        fill = WHITE if index % 2 == 0 else PANEL
        x = layout.margin
        governing_eta = _governing_check(item)[1]
        status_color, status_fill = _status_palette(values["status"])
        for key, _label, width, _align in columns:
            _rect(c, backend, layout, x, y, width, row_h, fill=fill, stroke=BORDER, width=0.28)
            value = values[key]
            if key in {"source", "target"}:
                _draw_text(
                    c,
                    backend,
                    layout,
                    value,
                    x + 4.0,
                    y + 3.4,
                    size=4.75,
                    color=TEXT,
                    bold=(key == "target" and value != "-"),
                    max_width=width - 8.0,
                    max_lines=3,
                    leading=5.55,
                )
            elif key == "status":
                pill_w = max(39.0, width - 7.0)
                _rect(
                    c,
                    backend,
                    layout,
                    x + (width - pill_w) / 2,
                    y + 7.0,
                    pill_w,
                    13.0,
                    fill=status_fill,
                    stroke=status_color,
                    width=0.35,
                    radius=4.5,
                )
                _draw_centered(
                    c,
                    backend,
                    layout,
                    value,
                    x + (width - pill_w) / 2,
                    y + 7.0,
                    pill_w,
                    13.0,
                    size=4.35,
                    color=status_color,
                    bold=True,
                )
            elif key == "governing":
                color = (
                    status_color
                    if not math.isfinite(governing_eta)
                    else (SUCCESS if governing_eta <= 0.90 else (WARNING if governing_eta <= 1.0 else DANGER))
                )
                _draw_centered(
                    c,
                    backend,
                    layout,
                    value,
                    x + 1.5,
                    y + 1.5,
                    width - 3.0,
                    row_h - 3.0,
                    size=4.55,
                    color=color,
                    bold=True,
                    max_lines=2,
                )
            else:
                _draw_centered(
                    c,
                    backend,
                    layout,
                    value,
                    x + 1.5,
                    y + 1.5,
                    width - 3.0,
                    row_h - 3.0,
                    size=4.45,
                    color=TEXT,
                    max_lines=2,
                )
            x += width
        y += row_h
    return y

def _draw_summary_page(c, backend: _Backend, layout: _Layout, project_name: str, rows: list[dict[str, Any]],
                       generated: str, page_index: int, total_summary_pages: int,
                       all_rows: list[dict[str, Any]]) -> None:
    subtitle = "Tabulka záměn - souhrn" if page_index == 0 else "Tabulka záměn - pokračování"
    _header(c, backend, layout, project_name, subtitle, generated)
    y = layout.header_h + 6.0

    if page_index == 0:
        _draw_text(c, backend, layout, "Přehled navržených záměn", layout.margin, y, size=9.6, color=NAVY, bold=True)
        _draw_text(
            c,
            backend,
            layout,
            "Kompaktní souhrn původního prvku, navrženého HIT, základních rozměrů a rozhodujícího využití.",
            layout.margin,
            y + 12.5,
            size=4.75,
            color=MUTED,
            max_width=layout.page_w - 2 * layout.margin,
            max_lines=1,
        )
        stats = _summary_stats(all_rows)
        card_y = y + 24.0
        gap = 5.0
        card_w = (layout.page_w - 2 * layout.margin - 4 * gap) / 5.0
        cards = [
            ("Pozice", str(stats["positions"]), NAVY, "řádků"),
            ("Množství", str(stats["quantity"]), TEAL, "kusů"),
            ("Vyhovuje", str(stats["ok"]), SUCCESS, "pozic"),
            ("K posouzení", str(stats["review"]), WARNING, "pozic"),
            ("Max. využití", _percent(stats["max_utilization"]), GOLD, "eta max"),
        ]
        x = layout.margin
        for label, value, accent, note in cards:
            _draw_kpi_card(c, backend, layout, x, card_y, card_w, 24.0, label, value, accent, note)
            x += card_w + gap
        table_y = card_y + 29.0
    else:
        _draw_text(
            c,
            backend,
            layout,
            f"Přehled navržených záměn - část {page_index + 1}/{total_summary_pages}",
            layout.margin,
            y,
            size=8.9,
            color=NAVY,
            bold=True,
        )
        _draw_text(
            c,
            backend,
            layout,
            "Pokračování kompaktní souhrnné tabulky.",
            layout.margin,
            y + 11.5,
            size=4.7,
            color=MUTED,
        )
        table_y = y + 18.0

    end_y = _draw_summary_table(c, backend, layout, rows, table_y)
    note_y = min(layout.page_h - layout.footer_h - 15.0, end_y + 4.0)
    _rect(
        c,
        backend,
        layout,
        layout.margin,
        note_y,
        layout.page_w - 2 * layout.margin,
        10.5,
        fill=LIGHT_TEAL,
        stroke="#BDD7E2",
        width=0.3,
        radius=2.5,
    )
    _draw_text(
        c,
        backend,
        layout,
        "Rozhoduje = nejvyšší poměr požadavek / únosnost. Úplná směrová kontrola a tlakový přenos jsou v detailních listech.",
        layout.margin + 5.0,
        note_y + 2.9,
        size=4.35,
        color=NAVY,
        max_width=layout.page_w - 2 * layout.margin - 10.0,
        max_lines=1,
    )

def _draw_source_target_box(c, backend: _Backend, layout: _Layout, x: float, y: float, w: float, h: float,
                            label: str, value: str, accent: str) -> None:
    compact = h <= 29.0
    _rect(c, backend, layout, x, y, w, h, fill=PANEL, stroke=BORDER, width=0.35, radius=3.5)
    _rect(c, backend, layout, x, y + 2.5, 2.8, h - 5.0, fill=accent, radius=1.0)
    _draw_text(c, backend, layout, label.upper(), x + 6.5, y + 3.6, size=3.9 if compact else 4.3, color=accent, bold=True)
    _draw_text(
        c,
        backend,
        layout,
        value,
        x + 6.5,
        y + (11.5 if compact else 13.0),
        size=5.0 if compact else 5.7,
        color=TEXT,
        bold=True,
        max_width=w - 12.0,
        max_lines=2,
        leading=5.9 if compact else 6.9,
    )

def _draw_checks_table(c, backend: _Backend, layout: _Layout, item: dict[str, Any], x: float, y: float,
                       w: float, max_rows: int = 6, compact: bool = False) -> float:
    headers = ["Účinek", "Požadavek", "Únosnost HIT", "Využití", "Výsledek"]
    proportions = (0.12, 0.235, 0.235, 0.155, 0.255)
    widths = [w * value for value in proportions]
    widths[-1] += w - sum(widths)
    header_h = 9.5 if compact else 11.0
    row_h = 8.9 if compact else 10.2
    header_size = 3.55 if compact else 3.9
    body_size = 3.65 if compact else 4.05

    xx = x
    for label, cell_w in zip(headers, widths):
        _rect(c, backend, layout, xx, y, cell_w, header_h, fill=NAVY, stroke=WHITE, width=0.25)
        _draw_centered(c, backend, layout, label, xx, y, cell_w, header_h, size=header_size, color=WHITE, bold=True)
        xx += cell_w
    y += header_h

    checks = _check_rows(item)
    for index, check in enumerate(checks[:max_rows]):
        xx = x
        eta = _safe_float(check.get("eta"), float("inf"))
        values = [
            _text(check.get("label")),
            f"{_number(check.get('requirement'))} {_text(check.get('unit'))}",
            f"{_number(check.get('capacity'))} {_text(check.get('unit'))}",
            _percent(eta),
            _text(check.get("result")),
        ]
        fill = WHITE if index % 2 == 0 else PANEL
        for col_index, (value, cell_w) in enumerate(zip(values, widths)):
            _rect(c, backend, layout, xx, y, cell_w, row_h, fill=fill, stroke=BORDER, width=0.25)
            color = TEXT
            bold = col_index in {0, 3, 4}
            if col_index == 4:
                color = SUCCESS if eta <= 1.0 + 1e-9 else DANGER
            _draw_centered(
                c,
                backend,
                layout,
                value,
                xx + 1.0,
                y + 0.3,
                cell_w - 2.0,
                row_h - 0.6,
                size=body_size,
                color=color,
                bold=bold,
                max_lines=1,
            )
            xx += cell_w
        y += row_h

    if not checks:
        _rect(c, backend, layout, x, y, w, row_h, fill=PANEL, stroke=BORDER, width=0.25)
        _draw_centered(
            c,
            backend,
            layout,
            "Není k dispozici směrová statická kontrola.",
            x,
            y,
            w,
            row_h,
            size=body_size,
            color=MUTED,
        )
        y += row_h
    elif len(checks) > max_rows:
        _draw_text(
            c,
            backend,
            layout,
            f"+ {len(checks) - max_rows} další kontroly",
            x,
            y + 1.2,
            size=3.7 if compact else 4.0,
            color=MUTED,
        )
        y += 7.0 if compact else 8.0
    return y

def _draw_technical_match(c, backend: _Backend, layout: _Layout, item: dict[str, Any], x: float, y: float,
                          w: float, h: float, compact: bool = False) -> None:
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}
    _rect(c, backend, layout, x, y, w, h, fill=LIGHT_GOLD, stroke="#E2CF9D", width=0.35, radius=3.2)

    title_size = 3.8 if compact else 4.25
    body_size = 3.65 if compact else 4.05
    _draw_text(c, backend, layout, "TECHNICKÁ SHODA", x + 5.0, y + 3.5, size=title_size, color=GOLD, bold=True)

    overall = _safe_float(target.get("utilization")) if target else float("nan")
    interaction = _safe_float(target.get("interaction_utilization")) if target else 0.0
    geometry = _text(meta.get("geometry_display")) if meta.get("geometry_display") else _text(item.get("estimated_type"))

    def pressure_short(value: Any) -> str:
        text = _text(value).lower()
        if "bez" in text and "lož" in text:
            return "bez ložisek"
        if "lož" in text or "csb" in text:
            return "s ložisky"
        if "prut" in text:
            return "tlačené pruty"
        return _text(value)

    source_pressure = pressure_short(meta.get("source_compression_text"))
    target_pressure = pressure_short(target.get("compression_text")) if target else "-"

    if compact:
        lines = [
            ("η celkem", _percent(overall), True),
            ("L / geometrie", f"{_text(target.get('length_relation')) if target else '-'} • {geometry}", False),
            ("Tlak", f"{source_pressure} -> {target_pressure}", False),
        ]
        yy = y + 12.0
        step = 8.1
    else:
        lines = [
            ("Celkové využití", _percent(overall), True),
            ("Interakce M-V", _percent(interaction) if interaction > 0 else "neaplikuje se", False),
            ("Délka", _text(target.get("length_relation")) if target else "-", False),
            ("Tlakový přenos", f"{source_pressure} -> {target_pressure}", False),
            ("Geometrie", geometry, False),
        ]
        yy = y + 14.0
        step = 9.2

    for label, value, important in lines:
        _draw_text(c, backend, layout, f"{label}:", x + 5.0, yy, size=body_size, color=TEXT, bold=True)
        label_w = _text_width(backend, f"{label}:", backend.bold_font, body_size)
        _draw_text(
            c,
            backend,
            layout,
            value,
            x + 7.5 + label_w,
            yy,
            size=body_size,
            color=TEXT,
            bold=important,
            max_width=max(10.0, w - 12.5 - label_w),
            max_lines=1,
        )
        yy += step

def _draw_detail_card(c, backend: _Backend, layout: _Layout, box: tuple[float, float, float, float],
                      item: dict[str, Any]) -> None:
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    compact = h < 210.0
    status = _text(item.get("status"))
    status_color, status_fill = _status_palette(status)
    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    meta = item.get("source_meta") if isinstance(item.get("source_meta"), dict) else {}

    shadow = 1.4 if compact else 2.0
    radius = 4.5 if compact else 5.5
    _rect(c, backend, layout, x0 + shadow, y0 + shadow, w, h, fill=SHADOW, radius=radius)
    _rect(c, backend, layout, x0, y0, w, h, fill=WHITE, stroke=BORDER, width=0.5, radius=radius)
    _rect(c, backend, layout, x0, y0, 3.2, h, fill=status_color, radius=1.6)

    header_h = 18.0 if compact else 21.0
    _rect(c, backend, layout, x0 + 3.2, y0, w - 3.2, header_h, fill=NAVY, radius=radius)
    _draw_text(
        c,
        backend,
        layout,
        f"POZICE {_text(item.get('position'))}   •   {_text(item.get('quantity'))} ks",
        x0 + 9.0,
        y0 + (5.0 if compact else 6.0),
        size=5.35 if compact else 6.0,
        color=WHITE,
        bold=True,
    )
    badge_w = 48.0 if compact else 54.0
    badge_h = 10.5 if compact else 12.0
    _rect(
        c,
        backend,
        layout,
        x1 - badge_w - 7.0,
        y0 + (3.8 if compact else 4.5),
        badge_w,
        badge_h,
        fill=status_fill,
        stroke=status_color,
        width=0.35,
        radius=4.0,
    )
    _draw_centered(
        c,
        backend,
        layout,
        status,
        x1 - badge_w - 7.0,
        y0 + (3.8 if compact else 4.5),
        badge_w,
        badge_h,
        size=3.85 if compact else 4.25,
        color=status_color,
        bold=True,
    )

    inner_x = x0 + 8.0
    inner_w = w - 16.0
    gap = 6.0
    col_w = (inner_w - gap) / 2.0
    boxes_y = y0 + header_h + 3.0
    box_h = 27.0 if compact else 31.0
    _draw_source_target_box(
        c, backend, layout, inner_x, boxes_y, col_w, box_h,
        "Původní prvek", _text(item.get("source")), TEAL,
    )
    _draw_source_target_box(
        c, backend, layout, inner_x + col_w + gap, boxes_y, col_w, box_h,
        "Navržený HIT", _text(target.get("designation")) if target else "Bez navrženého HIT", GOLD,
    )

    strip_y = boxes_y + box_h + 3.0
    strip_h = 12.0 if compact else 14.0
    _rect(c, backend, layout, inner_x, strip_y, inner_w, strip_h, fill=LIGHT_TEAL, stroke="#C1DBE5", width=0.3, radius=2.5)
    source_params = (
        f"I {_integer(meta.get('source_insulation_mm'))} • h {_integer(meta.get('source_height_mm'))} • "
        f"c {_integer(meta.get('source_cover_mm'))} • L {_integer(meta.get('source_length_mm'))} mm • "
        f"{_text(meta.get('source_concrete'))}"
    )
    target_params = (
        f"HIT-{_text(target.get('series'))} • h {_integer(target.get('height_mm'))} • "
        f"c {_integer(target.get('cover_mm'))} • L {_integer(target.get('length_mm'))} mm • {_wire_diameter(target)}"
        if target else "-"
    )
    strip_size = 3.75 if compact else 4.05
    _draw_text(c, backend, layout, source_params, inner_x + 4.0, strip_y + 3.4, size=strip_size, color=NAVY,
               max_width=col_w - 7.0, max_lines=1)
    _draw_text(c, backend, layout, target_params, inner_x + col_w + gap + 3.0, strip_y + 3.4, size=strip_size, color=NAVY,
               max_width=col_w - 7.0, max_lines=1)

    governing_label, governing_eta = _governing_check(item)
    gov_y = strip_y + strip_h + 3.0
    gov_color = (
        status_color
        if not math.isfinite(governing_eta)
        else (SUCCESS if governing_eta <= 0.90 else (WARNING if governing_eta <= 1.0 else DANGER))
    )
    _draw_text(c, backend, layout, "ROZHODUJÍCÍ KONTROLA", inner_x, gov_y, size=3.8 if compact else 4.2, color=MUTED, bold=True)
    _draw_text(
        c,
        backend,
        layout,
        f"{governing_label}  |  eta = {_percent(governing_eta)}",
        inner_x,
        gov_y + (7.0 if compact else 8.0),
        size=6.5 if compact else 7.2,
        color=gov_color,
        bold=True,
    )
    bar_x = inner_x + (104.0 if compact else 116.0)
    _draw_utilization_bar(
        c,
        backend,
        layout,
        bar_x,
        gov_y + (10.0 if compact else 11.5),
        max(40.0, inner_w - (104.0 if compact else 116.0)),
        4.2 if compact else 5.0,
        governing_eta,
    )

    section_y = gov_y + (19.0 if compact else 22.0)
    table_w = inner_w * 0.66
    info_gap = 6.0
    info_w = inner_w - table_w - info_gap
    _draw_text(
        c,
        backend,
        layout,
        "STATICKÁ KONTROLA JEDNOHO PRVKU",
        inner_x,
        section_y,
        size=3.9 if compact else 4.3,
        color=NAVY,
        bold=True,
    )
    max_rows = 3 if compact else 6
    table_top = section_y + (7.0 if compact else 8.0)
    table_end = _draw_checks_table(
        c, backend, layout, item, inner_x, table_top, table_w, max_rows=max_rows, compact=compact
    )
    panel_h = max(36.0 if compact else 58.0, table_end - table_top)
    _draw_technical_match(
        c,
        backend,
        layout,
        item,
        inner_x + table_w + info_gap,
        table_top,
        info_w,
        panel_h,
        compact=compact,
    )

    note_h = 14.0 if compact else 19.0
    note_y = y1 - note_h - 3.0
    _line(c, backend, layout, inner_x, note_y - 2.0, x1 - 7.0, note_y - 2.0, BORDER, 0.3)
    notes = item.get("notes") if isinstance(item.get("notes"), list) else []
    note_text = " • ".join(_text(value) for value in notes if _text(value) != "-")
    if not note_text:
        note_text = "Základní geometrie a statická únosnost odpovídají; ostatní projektové podmínky ověřte projektantem."
    _draw_text(c, backend, layout, "POZNÁMKA:", inner_x, note_y + 1.0, size=3.65 if compact else 4.0, color=MUTED, bold=True)
    _draw_text(
        c,
        backend,
        layout,
        note_text,
        inner_x + (34.0 if compact else 38.0),
        note_y + 1.0,
        size=3.65 if compact else 4.0,
        color=MUTED,
        max_width=inner_w - (34.0 if compact else 38.0),
        max_lines=1 if compact else 2,
        leading=4.6 if compact else 5.0,
    )

def _detail_chunks(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    # Čtyři běžné nebo tři obsahově náročnější pozice na jednu A4.
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    used = 0.0

    for item in rows:
        checks = len(_check_rows(item))
        notes = item.get("notes") if isinstance(item.get("notes"), list) else []
        note_length = sum(len(_text(value)) for value in notes)
        status = _text(item.get("status")).upper()
        complex_item = checks > 3 or note_length > 220 or status not in {"VYHOVUJE", "JIŽ HIT"}
        weight = 1.32 if complex_item else 1.0

        if current and (len(current) >= 4 or used + weight > 4.01):
            chunks.append(current)
            current = []
            used = 0.0
        current.append(item)
        used += weight

    if current:
        chunks.append(current)
    return chunks

def _draw_detail_page(c, backend: _Backend, layout: _Layout, project_name: str, rows: list[dict[str, Any]],
                      generated: str) -> None:
    _header(c, backend, layout, project_name, "Stručný statický výpočet", generated)
    content_top = layout.header_h + 5.0
    content_bottom = layout.page_h - layout.footer_h - 6.0
    count = max(1, len(rows))
    gap = 5.5
    available = content_bottom - content_top - gap * (count - 1)
    computed_h = available / count
    # Na poslední neúplné stránce jediný blok zbytečně neroztahujeme.
    target_h = 188.0 if count >= 4 else 239.0
    card_h = min(computed_h, target_h)

    y = content_top
    for item in rows:
        _draw_detail_card(
            c,
            backend,
            layout,
            (layout.margin, y, layout.page_w - layout.margin, y + card_h),
            item,
        )
        y += card_h + gap

def _draw_document(
    c,
    backend: _Backend,
    layout: _Layout,
    *,
    project_name: str,
    rows: list[dict[str, Any]],
    creator: str,
    generated: str,
) -> None:
    summary_chunks = _summary_chunks(rows, layout)
    detail_chunks = _detail_chunks(rows)
    total_pages = len(summary_chunks) + len(detail_chunks)
    page_no = 0

    c.bookmarkPage("summary")
    c.addOutlineEntry("Souhrn záměn", "summary", level=0, closed=False)
    for index, chunk in enumerate(summary_chunks):
        page_no += 1
        if index:
            key = f"summary_{index + 1}"
            c.bookmarkPage(key)
            c.addOutlineEntry(f"Souhrn - část {index + 1}", key, level=1, closed=False)
        _draw_summary_page(
            c, backend, layout, project_name, chunk, generated, index, len(summary_chunks), rows
        )
        _footer(c, backend, layout, page_no, total_pages, creator)
        c.showPage()

    for index, chunk in enumerate(detail_chunks):
        page_no += 1
        first_position = _text(chunk[0].get("position")) if chunk else str(index + 1)
        last_position = _text(chunk[-1].get("position")) if chunk else first_position
        key = f"detail_{index + 1}"
        c.bookmarkPage(key)
        label = f"Detail {first_position}" if first_position == last_position else f"Detail {first_position} - {last_position}"
        c.addOutlineEntry(label, key, level=0, closed=False)
        _draw_detail_page(c, backend, layout, project_name, chunk, generated)
        _footer(c, backend, layout, page_no, total_pages, creator)
        c.showPage()


def write_substitution_pdf(
    path: Path | str,
    *,
    project_name: str,
    rows: Iterable[dict[str, Any]],
    creator: str = "Vytvořil Ing. Jaroslav Kučera",
) -> Path:
    """Vytvoří skutečný vektorový, prohledávatelný PDF výstup.

    Text, tabulky, čáry, rámečky, stavové štítky i grafy využití jsou PDF
    grafické objekty. Do dokumentu se nevkládá rastrový obraz celé stránky.
    """
    backend = _load_backend()
    layout = _layout(backend)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = [dict(row) for row in rows if isinstance(row, dict)]
    if not data:
        raise PdfExportError("Není co exportovat do PDF.")

    generated = datetime.now().strftime("%d.%m.%Y %H:%M")
    try:
        c = backend.canvas_module.Canvas(
            str(target),
            pagesize=(layout.page_w, layout.page_h),
            pageCompression=1,
            invariant=0,
        )
        c.setTitle(f"TURTO ISO - Tabulka záměn - {_text(project_name)}")
        c.setAuthor(creator)
        c.setSubject("Předběžná katalogová záměna izolačních nosníků za Leviat HIT")
        c.setCreator("TURTO ISO")
        c.setKeywords("TURTO ISO, HIT, izolační nosníky, tabulka záměn, statický výpočet")
        _draw_document(
            c,
            backend,
            layout,
            project_name=project_name,
            rows=data,
            creator=creator,
            generated=generated,
        )
        c.save()
    except PdfExportError:
        raise
    except Exception as exc:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        raise PdfExportError(f"Vektorové PDF se nepodařilo vytvořit.\n\n{exc}") from exc

    if not target.exists() or target.stat().st_size < 4_000:
        raise PdfExportError("Vektorové PDF se nepodařilo korektně vytvořit.")
    return target
