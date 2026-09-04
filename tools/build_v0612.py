from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.11"
OUT = ROOT / "updates" / "0.6.12"


XLSX_EXPORT = r'''from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


_INVALID_XML = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_INVALID_SHEET = re.compile(r"[\\/*?:\[\]]")


def _clean_text(value: Any) -> str:
    text = _INVALID_XML.sub("", str(value if value is not None else ""))
    return text[:32767]


def _sheet_name(value: str) -> str:
    text = _INVALID_SHEET.sub("_", _clean_text(value)).strip(" '")
    return (text or "Export")[:31]


def _column_name(index: int) -> str:
    result = ""
    value = int(index)
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(ref: str, value: Any, style: int = 0) -> str:
    if isinstance(value, bool):
        value = "Ano" if value else "Ne"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            value = ""
        else:
            return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    text = _clean_text(value)
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f'<c r="{ref}" t="inlineStr" s="{style}"><is><t{preserve}>{escape(text)}</t></is></c>'


def _column_widths(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[float]:
    widths: list[float] = []
    for column_index, header in enumerate(headers):
        longest = len(_clean_text(header))
        for row in rows:
            if column_index >= len(row):
                continue
            text = _clean_text(row[column_index])
            line = max((len(part) for part in text.splitlines()), default=0)
            longest = max(longest, line)
        widths.append(float(max(8, min(55, longest + 2))))
    return widths


def write_xlsx(
    path: Path | str,
    *,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    sheet_name: str = "Soupis nosníků",
    creator: str = "TURTO",
) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".xlsx":
        target = target.with_suffix(".xlsx")
    target.parent.mkdir(parents=True, exist_ok=True)

    header_values = [_clean_text(value) for value in headers]
    data_rows = [list(row) for row in rows]
    if not header_values:
        raise ValueError("Excel musí obsahovat alespoň jeden sloupec.")

    widths = _column_widths(header_values, data_rows)
    last_column = _column_name(len(header_values))
    last_row = len(data_rows) + 1
    table_ref = f"A1:{last_column}{last_row}"

    cols_xml = "".join(
        f'<col min="{index}" max="{index}" width="{width:.2f}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )

    header_cells = "".join(
        _cell(f"{_column_name(index)}1", value, 1)
        for index, value in enumerate(header_values, start=1)
    )
    row_xml = [f'<row r="1" ht="25" customHeight="1">{header_cells}</row>']
    for row_number, row in enumerate(data_rows, start=2):
        cells = []
        for column_index in range(1, len(header_values) + 1):
            value = row[column_index - 1] if column_index - 1 < len(row) else ""
            cells.append(_cell(f"{_column_name(column_index)}{row_number}", value, 2))
        row_xml.append(f'<row r="{row_number}">' + "".join(cells) + "</row>")

    worksheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="{table_ref}"/>
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols>{cols_xml}</cols>
  <sheetData>{''.join(row_xml)}</sheetData>
  <autoFilter ref="{table_ref}"/>
  <pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>
  <pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"/>
</worksheet>'''

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/><family val="2"/></font>
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
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    workbook = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews>
  <sheets><sheet name="{escape(_sheet_name(sheet_name))}" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''

    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    core = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>{escape(_clean_text(creator))}</dc:creator>
  <cp:lastModifiedBy>{escape(_clean_text(creator))}</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>'''
    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>TURTO</Application></Properties>'''

    files = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": root_rels,
        "docProps/core.xml": core,
        "docProps/app.xml": app,
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": workbook_rels,
        "xl/styles.xml": styles,
        "xl/worksheets/sheet1.xml": worksheet,
    }
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value.encode("utf-8"))
    return target
'''


EXPORT_DIALOG = r'''

class ExcelExportDialog(tk.Toplevel):
    """Výběr rozsahu řádků a sloupců pro nativní XLSX export."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        colors: dict[str, str],
        columns: list[tuple[str, str]],
        visible_columns: Iterable[str],
        saved_columns: Iterable[str] | None,
        saved_scope: str | None,
        selected_count: int,
        visible_count: int,
        total_count: int,
    ) -> None:
        super().__init__(parent)
        self.result: dict[str, Any] | None = None
        self.colors = colors
        self.columns = list(columns)
        self.visible_columns = [str(value) for value in visible_columns]
        all_ids = [column for column, _label in self.columns]
        remembered = [str(value) for value in (saved_columns or []) if str(value) in all_ids]
        initial = remembered or [value for value in self.visible_columns if value in all_ids] or all_ids

        scope = str(saved_scope or "")
        if scope not in {"selected", "visible", "all"}:
            scope = "selected" if selected_count else "visible"
        if scope == "selected" and not selected_count:
            scope = "visible"

        self.scope_var = tk.StringVar(value=scope)
        self.column_vars = {column: tk.BooleanVar(value=column in initial) for column, _label in self.columns}
        self.count_var = tk.StringVar()

        self.title("Export do Excelu")
        self.geometry("900x650")
        self.minsize(720, 560)
        self.transient(parent)
        self.grab_set()
        self.configure(background=colors["bg"])
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        outer = ttk.Frame(self, style="App.TFrame", padding=20)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, text="Export vybraných dat do Excelu", style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=(
                "Zvolte rozsah řádků a zaškrtněte údaje, které chcete přenést. Pořadí exportovaných sloupců odpovídá "
                "aktuálnímu pořadí sloupců v projektové tabulce. Poslední volba se uloží pro příští export."
            ),
            style="Muted.TLabel",
            wraplength=840,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 12))

        scope_card = ttk.Frame(outer, style="Card.TFrame", padding=12)
        scope_card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(scope_card, text="Rozsah řádků", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        selected_radio = ttk.Radiobutton(
            scope_card,
            text=f"Vybrané řádky v tabulce ({selected_count})",
            variable=self.scope_var,
            value="selected",
        )
        selected_radio.grid(row=1, column=0, sticky="w", padx=(0, 24))
        if not selected_count:
            selected_radio.configure(state="disabled")
        ttk.Radiobutton(
            scope_card,
            text=f"Právě zobrazené po filtru ({visible_count})",
            variable=self.scope_var,
            value="visible",
        ).grid(row=1, column=1, sticky="w", padx=(0, 24))
        ttk.Radiobutton(
            scope_card,
            text=f"Celý projekt ({total_count})",
            variable=self.scope_var,
            value="all",
        ).grid(row=1, column=2, sticky="w")

        columns_card = ttk.Frame(outer, style="Card.TFrame", padding=12)
        columns_card.grid(row=3, column=0, sticky="nsew")
        columns_card.columnconfigure(0, weight=1)
        columns_card.columnconfigure(1, weight=1)
        columns_card.columnconfigure(2, weight=1)

        top = ttk.Frame(columns_card, style="Card.TFrame")
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="Údaje / sloupce", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="Podle zobrazených sloupců", command=lambda: self._set_columns("visible")).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(top, text="Vše", command=lambda: self._set_columns("all")).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(top, text="Nic", command=lambda: self._set_columns("none")).grid(row=0, column=3, padx=(8, 0))

        for index, (column, label) in enumerate(self.columns):
            variable = self.column_vars[column]
            variable.trace_add("write", self._update_count)
            row = 1 + index // 3
            col = index % 3
            ttk.Checkbutton(columns_card, text=label, variable=variable).grid(row=row, column=col, sticky="w", padx=(0, 18), pady=3)

        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.count_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Zrušit", command=self._cancel).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(bottom, text="Exportovat .xlsx", style="Accent.TButton", command=self._submit).grid(row=0, column=2, padx=(8, 0))

        self.bind("<Escape>", lambda _event: self._cancel())
        self._update_count()

    def _set_columns(self, mode: str) -> None:
        visible = set(self.visible_columns)
        for column, variable in self.column_vars.items():
            if mode == "all":
                variable.set(True)
            elif mode == "none":
                variable.set(False)
            else:
                variable.set(column in visible)

    def _update_count(self, *_args: Any) -> None:
        count = sum(1 for variable in self.column_vars.values() if variable.get())
        self.count_var.set(f"Vybráno {count} z {len(self.column_vars)} sloupců")

    def _submit(self) -> None:
        selected = [column for column, _label in self.columns if self.column_vars[column].get()]
        if not selected:
            messagebox.showwarning("Není vybrán žádný údaj", "Zaškrtněte alespoň jeden sloupec pro export.", parent=self)
            return
        self.result = {"scope": self.scope_var.get(), "columns": selected}
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
'''


EXPORT_METHODS = r'''

    def _rows_for_excel_scope(self, scope: str) -> list[dict[str, Any]]:
        if scope == "selected":
            selected = set(self._selected_project_ids())
            ids = [str(value) for value in self.project_tree.get_children("") if str(value) in selected]
        elif scope == "visible":
            ids = [str(value) for value in self.project_tree.get_children("")]
        else:
            return list(self.project.rows)
        rows: list[dict[str, Any]] = []
        for row_id in ids:
            row = self.project.row_by_id(row_id)
            if row is not None:
                rows.append(row)
        return rows

    def export_project_xlsx(self) -> None:
        if not self.project.rows:
            messagebox.showinfo("Projekt je prázdný", "Nejprve přidejte alespoň jeden řádek.", parent=self)
            return

        layout = self._project_layout_state()
        labels = {column: label for column, label, *_rest in self.PROJECT_COLUMNS}
        ordered_columns = [(column, labels[column]) for column in layout["order"] if column in labels]
        export_state = self.settings.get("excel_export", {})
        if not isinstance(export_state, dict):
            export_state = {}

        dialog = ExcelExportDialog(
            self,
            colors=self.colors,
            columns=ordered_columns,
            visible_columns=self._project_visible_columns(),
            saved_columns=export_state.get("columns") if isinstance(export_state.get("columns"), list) else None,
            saved_scope=str(export_state.get("scope", "")) or None,
            selected_count=len(self._selected_project_ids()),
            visible_count=len(self.project_tree.get_children("")),
            total_count=len(self.project.rows),
        )
        self.wait_window(dialog)
        if dialog.result is None:
            return

        scope = str(dialog.result["scope"])
        columns = [str(value) for value in dialog.result["columns"] if str(value) in labels]
        rows = self._rows_for_excel_scope(scope)
        if not rows:
            messagebox.showinfo("Není co exportovat", "Ve zvoleném rozsahu nejsou žádné řádky.", parent=self)
            return

        suggested = self._safe_filename(self.project.name, "projekt") + "_izolacni_nosniky.xlsx"
        initial_dir = self.settings.get("last_export_directory") or self._default_project_directory()
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Exportovat vybraná data do Excelu",
            initialdir=str(initial_dir),
            initialfile=suggested,
            defaultextension=".xlsx",
            filetypes=[("Excel sešit", "*.xlsx"), ("Všechny soubory", "*.*")],
        )
        if not path:
            return

        payloads = self._payloads_for_rows(rows)
        headers = [labels[column] for column in columns]
        data = [[payload.get(column, "") for column in columns] for payload in payloads]
        try:
            saved = write_xlsx(
                path,
                headers=headers,
                rows=data,
                sheet_name="Soupis nosníků",
                creator="TURTO – Vytvořil Ing. Jaroslav Kučera",
            )
        except Exception as exc:
            messagebox.showerror("Export do Excelu se nepodařil", str(exc), parent=self)
            return

        self.settings["excel_export"] = {"columns": columns, "scope": scope}
        self.settings["last_export_directory"] = str(saved.resolve().parent)
        if hasattr(self, "_save_settings"):
            self._save_settings()
        scope_label = {"selected": "vybraných", "visible": "zobrazených", "all": "všech"}.get(scope, "")
        self.set_status(f"Do Excelu exportováno {len(rows)} {scope_label} řádků a {len(columns)} sloupců.")
        messagebox.showinfo(
            "Export dokončen",
            f"Exportováno {len(rows)} řádků a {len(columns)} sloupců.\n\nSoubor:\n{saved.resolve()}",
            parent=self,
        )
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_app(text: str) -> str:
    return replace_once(text, 'APP_VERSION = "0.6.11"', 'APP_VERSION = "0.6.12"', "app version")


def patch_project_ui(text: str) -> str:
    text = replace_once(
        text,
        'from bulk_import import BulkImportDialog\n',
        'from bulk_import import BulkImportDialog\nfrom xlsx_export import write_xlsx\n',
        "xlsx import",
    )
    text = replace_once(text, '\n\nclass ProjectWorkspaceMixin:\n', EXPORT_DIALOG + '\n\nclass ProjectWorkspaceMixin:\n', "export dialog")

    old_filebar = '''        filebar = ttk.Frame(parent, style="App.TFrame")\n        filebar.grid(row=1, column=0, sticky="ew", pady=(10, 0))\n        filebar.columnconfigure(9, weight=1)\n        ttk.Button(filebar, text="Nový objekt", command=self.new_project).grid(row=0, column=0)\n        ttk.Button(filebar, text="Otevřít projekt", command=self.open_project).grid(row=0, column=1, padx=(7, 0))\n        ttk.Button(filebar, text="Uložit", style="Accent.TButton", command=self.save_project).grid(row=0, column=2, padx=(7, 0))\n        ttk.Button(filebar, text="Uložit jako…", command=self.save_project_as).grid(row=0, column=3, padx=(7, 0))\n        ttk.Separator(filebar, orient="vertical").grid(row=0, column=4, sticky="ns", padx=10)\n        ttk.Button(filebar, text="Hromadné vložení z výkazu", command=self.bulk_paste_project_rows).grid(row=0, column=5)\n        ttk.Button(filebar, text="Kopírovat pro Excel", command=self.copy_project_table).grid(row=0, column=6, padx=(7, 0))\n        ttk.Button(filebar, text="Export CSV", command=self.export_project_csv).grid(row=0, column=7, padx=(7, 0))\n        ttk.Label(\n            filebar,\n            text="Projektový soubor uchovává i vydání katalogu a snímek hodnot.",\n            style="Muted.TLabel",\n        ).grid(row=0, column=9, sticky="e")\n'''
    new_filebar = '''        filebar = ttk.Frame(parent, style="App.TFrame")\n        filebar.grid(row=1, column=0, sticky="ew", pady=(10, 0))\n        filebar.columnconfigure(10, weight=1)\n        ttk.Button(filebar, text="Nový objekt", command=self.new_project).grid(row=0, column=0)\n        ttk.Button(filebar, text="Otevřít projekt", command=self.open_project).grid(row=0, column=1, padx=(7, 0))\n        ttk.Button(filebar, text="Uložit", style="Accent.TButton", command=self.save_project).grid(row=0, column=2, padx=(7, 0))\n        ttk.Button(filebar, text="Uložit jako…", command=self.save_project_as).grid(row=0, column=3, padx=(7, 0))\n        ttk.Separator(filebar, orient="vertical").grid(row=0, column=4, sticky="ns", padx=10)\n        ttk.Button(filebar, text="Hromadné vložení z výkazu", command=self.bulk_paste_project_rows).grid(row=0, column=5)\n        ttk.Button(filebar, text="Kopírovat pro Excel", command=self.copy_project_table).grid(row=0, column=6, padx=(7, 0))\n        ttk.Button(filebar, text="Export Excel…", style="Accent.TButton", command=self.export_project_xlsx).grid(row=0, column=7, padx=(7, 0))\n        ttk.Button(filebar, text="Export CSV", command=self.export_project_csv).grid(row=0, column=8, padx=(7, 0))\n        ttk.Label(\n            filebar,\n            text="Projektový soubor uchovává i vydání katalogu a snímek hodnot.",\n            style="Muted.TLabel",\n        ).grid(row=0, column=10, sticky="e")\n'''
    text = replace_once(text, old_filebar, new_filebar, "filebar Excel button")

    text = replace_once(
        text,
        '        menu.add_command(label="Kopírovat pro Excel", command=self.copy_project_table)\n        menu.add_separator()\n',
        '        menu.add_command(label="Kopírovat pro Excel", command=self.copy_project_table)\n'
        '        menu.add_command(label="Export Excel…", command=self.export_project_xlsx)\n'
        '        menu.add_separator()\n',
        "context Excel export",
    )

    text = replace_once(
        text,
        '    def export_project_csv(self) -> None:\n',
        EXPORT_METHODS + '\n\n    def export_project_csv(self) -> None:\n',
        "Excel export methods",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    (OUT / "xlsx_export.py").write_text(XLSX_EXPORT, encoding="utf-8")
    app_path = OUT / "app.pyw"
    project_path = OUT / "project_ui.py"
    app_path.write_text(patch_app(app_path.read_text(encoding="utf-8")), encoding="utf-8")
    project_path.write_text(patch_project_ui(project_path.read_text(encoding="utf-8")), encoding="utf-8")

    notes = (
        "TURTO v0.6.12\n"
        "- Projektová tabulka má nový Export Excel… do nativního .xlsx bez závislosti na Microsoft Excelu.\n"
        "- Před exportem lze zaškrtávači zvolit přesné údaje/sloupce, které se mají přenést.\n"
        "- Rozsah řádků: vybrané řádky, právě zobrazené řádky po filtru, nebo celý projekt.\n"
        "- Tlačítko Podle zobrazených sloupců převezme aktuální viditelnost; pořadí exportu respektuje aktuální pořadí tabulky.\n"
        "- Poslední výběr sloupců a rozsahu se ukládá do settings.json a obnoví se při příštím exportu.\n"
        "- XLSX má záhlaví, automatický filtr, zamrzlý první řádek, Calibri a automaticky upravené šířky sloupců.\n"
    )
    (OUT / "RELEASE_NOTES.txt").write_text(notes, encoding="utf-8")

    for name in ["app.pyw", "project_ui.py", "xlsx_export.py", "bulk_import.py", "bulk_import_engine.py"]:
        py_compile.compile(str(OUT / name), doraise=True)

    # Ověření minimálního XLSX balíčku bez externích knihoven.
    import importlib.util
    spec = importlib.util.spec_from_file_location("turto_xlsx_export", OUT / "xlsx_export.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "sample.xlsx"
        module.write_xlsx(
            sample,
            headers=["Pozice", "Ks", "Úplné označení"],
            rows=[["P001", 4, "Schöck Isokorb XT-KL-M6-V3-H250-6.2"], ["P002", 2, "Egcobox MXL20-V1-C50-h200"]],
        )
        assert sample.exists() and sample.stat().st_size > 1000
        with zipfile.ZipFile(sample) as archive:
            required = {
                "[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
                "xl/styles.xml", "xl/worksheets/sheet1.xml", "docProps/core.xml", "docProps/app.xml",
            }
            assert required.issubset(set(archive.namelist()))
            for name in required:
                ET.fromstring(archive.read(name))
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
            assert "autoFilter" in sheet and "state=\"frozen\"" in sheet and "Schöck Isokorb" in sheet

    project_text = project_path.read_text(encoding="utf-8")
    app_text = app_path.read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.6.12"' in app_text
    assert "class ExcelExportDialog" in project_text
    assert "def export_project_xlsx" in project_text
    assert "Podle zobrazených sloupců" in project_text
    assert 'self.settings["excel_export"]' in project_text
    assert "Vybrané řádky v tabulce" in project_text

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "schoeck_archive_sources.json",
        "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.12/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.12",
        "notes": (
            "Výběrový export do Excelu: před vytvořením .xlsx lze zaškrtávači určit přenášené sloupce a zvolit vybrané, "
            "zobrazené nebo všechny řádky. Volba se pamatuje a pořadí respektuje uživatelské rozložení tabulky."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.6.12 OK; selective native XLSX export verified")


if __name__ == "__main__":
    main()
