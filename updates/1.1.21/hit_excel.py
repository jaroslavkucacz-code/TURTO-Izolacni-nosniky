from __future__ import annotations

"""Dependency-free XLSX export for supplier inquiries from direct HIT proposals."""

from collections import defaultdict
from datetime import datetime, timezone
import math
import re
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

_INVALID_XML = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def _clean(value: Any) -> str:
    return _INVALID_XML.sub("", str(value if value is not None else ""))[:32767]


def _col(index: int) -> str:
    out = ""
    n = int(index)
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def _number(value: Any) -> float | None:
    if value in (None, "", "—", "-"):
        return None
    try:
        result = float(str(value).replace("−", "-").replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _cell(ref: str, value: Any, style: int = 0) -> str:
    if isinstance(value, bool):
        value = "Ano" if value else "Ne"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            value = ""
        else:
            return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    text = _clean(value)
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f'<c r="{ref}" t="inlineStr" s="{style}"><is><t{preserve}>{escape(text)}</t></is></c>'


def _widths(headers: Sequence[str], rows: Sequence[Sequence[Any]], *, minimum: int = 8, maximum: int = 55) -> list[float]:
    result = []
    for idx, header in enumerate(headers):
        longest = len(_clean(header))
        for row in rows:
            if idx >= len(row):
                continue
            longest = max(longest, max((len(part) for part in _clean(row[idx]).splitlines()), default=0))
        result.append(float(max(minimum, min(maximum, longest + 2))))
    return result


def _sheet_xml(
    *,
    title: str,
    meta_lines: Sequence[str],
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    widths: Sequence[float],
) -> str:
    ncols = len(headers)
    last_col = _col(ncols)
    header_row = len(meta_lines) + 3
    first_data = header_row + 1
    last_row = max(header_row, header_row + len(rows))
    cols_xml = "".join(
        f'<col min="{i}" max="{i}" width="{float(width):.2f}" customWidth="1"/>'
        for i, width in enumerate(widths, 1)
    )
    row_xml: list[str] = []
    row_xml.append(f'<row r="1" ht="26" customHeight="1">{_cell("A1", title, 3)}</row>')
    for idx, line in enumerate(meta_lines, 2):
        row_xml.append(f'<row r="{idx}">{_cell(f"A{idx}", line, 2)}</row>')
    header_cells = "".join(_cell(f"{_col(i)}{header_row}", value, 1) for i, value in enumerate(headers, 1))
    row_xml.append(f'<row r="{header_row}" ht="26" customHeight="1">{header_cells}</row>')
    for rix, row in enumerate(rows, first_data):
        cells = []
        for cix in range(1, ncols + 1):
            value = row[cix - 1] if cix - 1 < len(row) else ""
            cells.append(_cell(f"{_col(cix)}{rix}", value, 2))
        row_xml.append(f'<row r="{rix}">' + "".join(cells) + "</row>")
    merge = f'<mergeCells count="1"><mergeCell ref="A1:{last_col}1"/></mergeCells>' if ncols > 1 else ""
    table_ref = f"A{header_row}:{last_col}{last_row}"
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:{last_col}{last_row}"/>
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="{header_row}" topLeftCell="A{first_data}" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols>{cols_xml}</cols>
  <sheetData>{''.join(row_xml)}</sheetData>
  {merge}
  <autoFilter ref="{table_ref}"/>
  <pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>
  <pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"/>
</worksheet>'''


def write_hit_request_xlsx(
    path: Path | str,
    *,
    action_name: str,
    rows: Iterable[dict[str, Any]],
    include_statics: bool = False,
    creator: str = "TURTO",
) -> Path:
    data = [dict(row) for row in rows]
    if not data:
        raise ValueError("Není co exportovat.")
    target = Path(path)
    if target.suffix.lower() != ".xlsx":
        target = target.with_suffix(".xlsx")
    target.parent.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, dict[str, Any]] = {}
    for row in data:
        candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
        designation = str(candidate.get("designation", "") or "").strip()
        if not designation:
            continue
        quantity = int(row.get("quantity", 1) or 1)
        position = str(row.get("name", "") or "").strip()
        group = grouped.setdefault(designation, {"quantity": 0, "positions": []})
        group["quantity"] += quantity
        if position:
            group["positions"].append(position)
    if not grouped:
        raise ValueError("Není navržen žádný HIT pro poptávku.")

    inquiry_headers = ("Typ HIT", "Ks", "Pozice")
    inquiry_rows = [
        (designation, int(info["quantity"]), ", ".join(info["positions"]))
        for designation, info in sorted(grouped.items())
    ]
    inquiry_widths = _widths(inquiry_headers, inquiry_rows)
    if inquiry_widths:
        inquiry_widths[0] = min(55.0, max(inquiry_widths[0], 42.0))
        inquiry_widths[1] = 9.0
        inquiry_widths[2] = min(42.0, max(inquiry_widths[2], 20.0))

    sheets: list[tuple[str, str]] = []
    sheets.append((
        "Poptávka",
        _sheet_xml(
            title="Poptávka – Leviat HIT",
            meta_lines=(f"Akce: {action_name or '—'}", f"Datum: {datetime.now().strftime('%d.%m.%Y')}"),
            headers=inquiry_headers,
            rows=inquiry_rows,
            widths=inquiry_widths,
        ),
    ))

    if include_statics:
        static_headers = (
            "Pozice", "Ks", "Typ HIT", "Řada", "Typ", "h [mm]", "cnom [mm]", "Beton", "L/B [mm]",
            "MEd+ [kNm/m]", "MEd− [kNm/m]", "NEd+ [kN/m]", "NEd− [kN/m]",
            "VEd+ [kN/m]", "VEd− [kN/m]", "HEd∥ [kN/prvek]", "HEd⊥ [kN/prvek]",
            "Využití [%]", "a max [m]", "MRd / HRd∥,1", "VRd / HRd⊥,1", "MRd,2", "VRd,2",
            "Rozhoduje / kontrola", "Zdroj",
        )
        static_rows = []
        for row in data:
            candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
            if not candidate:
                continue
            actions = row.get("actions") if isinstance(row.get("actions"), dict) else {}
            util = _number(candidate.get("utilization"))
            static_rows.append((
                row.get("name", ""), int(row.get("quantity", 1) or 1), candidate.get("designation", ""),
                candidate.get("series", row.get("series", "")), candidate.get("connection_type", row.get("connection_type", "")),
                candidate.get("height", row.get("height_mm", "")), candidate.get("cover", row.get("cover_mm", "")),
                candidate.get("concrete", row.get("concrete", "")), row.get("required_length_mm", ""),
                _number(actions.get("m_pos")), _number(actions.get("m_neg")), _number(actions.get("n_pos")), _number(actions.get("n_neg")),
                _number(actions.get("v_pos")), _number(actions.get("v_neg")), _number(actions.get("h_parallel")), _number(actions.get("h_perp")),
                None if util is None else util * 100.0, _number(candidate.get("spacing_max")),
                _number(candidate.get("m1")), _number(candidate.get("v1")), _number(candidate.get("m2")), _number(candidate.get("v2")),
                candidate.get("mode", ""), candidate.get("page", ""),
            ))
        static_widths = _widths(static_headers, static_rows, maximum=48)
        for idx in (2, 23):
            if idx < len(static_widths):
                static_widths[idx] = max(static_widths[idx], 35.0 if idx == 2 else 42.0)
        sheets.append((
            "Statická data",
            _sheet_xml(
                title="Statická data – návrh Leviat HIT",
                meta_lines=(f"Akce: {action_name or '—'}", f"Datum: {datetime.now().strftime('%d.%m.%Y')}"),
                headers=static_headers,
                rows=static_rows,
                widths=static_widths,
            ),
        ))

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><sz val="11"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><color rgb="FF17324D"/><sz val="16"/><name val="Calibri"/><family val="2"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF17324D"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFD8E0E8"/></left><right style="thin"><color rgb="FFD8E0E8"/></right><top style="thin"><color rgb="FFD8E0E8"/></top><bottom style="thin"><color rgb="FFD8E0E8"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="4">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    workbook_sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, (name, _xml) in enumerate(sheets, 1)
    )
    workbook = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews>
  <sheets>{workbook_sheets}</sheets>
</workbook>'''
    rels = []
    for idx in range(1, len(sheets) + 1):
        rels.append(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>')
    rels.append(f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    workbook_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + '</Relationships>'

    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx in range(1, len(sheets) + 1)
    )
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  {overrides}
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    core = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>{escape(_clean(creator))}</dc:creator>
  <cp:lastModifiedBy>{escape(_clean(creator))}</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>'''
    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>TURTO ISO</Application></Properties>'''

    files = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": root_rels,
        "docProps/core.xml": core,
        "docProps/app.xml": app,
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": workbook_rels,
        "xl/styles.xml": styles,
    }
    for idx, (_name, xml) in enumerate(sheets, 1):
        files[f"xl/worksheets/sheet{idx}.xml"] = xml
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode("utf-8"))
    return target
