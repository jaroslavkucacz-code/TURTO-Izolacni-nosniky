from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.7"
TO_VERSION = "0.13.8"

OLD_WB = '''            wb = Workbook()\n            navy = "1F2937"\n'''
NEW_WB = '''            wb = Workbook()\n            # One shared default font is much faster than assigning a new Font to\n            # every cell in every duplicated audit sheet.\n            try:\n                normal_style = next((s for s in wb._named_styles if getattr(s, "name", "") == "Normal"), None)\n                if normal_style is not None:\n                    normal_style.font = Font(name="Calibri", size=10)\n            except Exception:\n                pass\n            navy = "1F2937"\n'''

OLD_BODY_STYLE = '''                for row in sh.iter_rows(min_row=header_row + 1):\n                    for cell in row:\n                        cell.font = Font(name="Calibri", size=10, color=text_dark)\n                        cell.alignment = Alignment(vertical="top", wrap_text=True)\n                        cell.border = border\n                    if status_col and status_col <= len(row):\n                        cell = row[status_col - 1]\n                        kind = status_kind(cell.value)\n                        if kind == "error":\n                            cell.fill = PatternFill("solid", fgColor=error_fill)\n                            cell.font = Font(name="Calibri", size=10, bold=True, color="9B1C1C")\n                        elif kind == "warning":\n                            cell.fill = PatternFill("solid", fgColor=warn_fill)\n                            cell.font = Font(name="Calibri", size=10, color="7A5200")\n                        elif kind == "ok":\n                            cell.fill = PatternFill("solid", fgColor=ok_fill)\n'''
NEW_BODY_STYLE = '''                # Body cells inherit the workbook Normal style. Creating Font,\n                # Alignment and Border objects for every cell was the main bottleneck\n                # of the complete export. Only the status column needs per-row styling.\n                if status_col and status_col <= sh.max_column:\n                    for row_idx in range(header_row + 1, sh.max_row + 1):\n                        cell = sh.cell(row_idx, status_col)\n                        kind = status_kind(cell.value)\n                        if kind == "error":\n                            cell.fill = PatternFill("solid", fgColor=error_fill)\n                            cell.font = Font(name="Calibri", size=10, bold=True, color="9B1C1C")\n                        elif kind == "warning":\n                            cell.fill = PatternFill("solid", fgColor=warn_fill)\n                            cell.font = Font(name="Calibri", size=10, color="7A5200")\n                        elif kind == "ok":\n                            cell.fill = PatternFill("solid", fgColor=ok_fill)\n'''

OLD_ADD_FULL = '''            def add_full_sheet(name: str, rows: list[BeamRow]):\n                sh = wb.create_sheet(clean_sheet_name(name))\n                sh.append(full_headers)\n                for r in rows:\n                    sh.append(xlsx_row_values(r))\n                style_table_sheet(sh, widths=full_widths, status_col=16)\n'''
NEW_ADD_FULL = '''            def add_full_sheet(name: str, rows: list[BeamRow], include_raw_ocr: bool = False):\n                sh = wb.create_sheet(clean_sheet_name(name))\n                sh.append(full_headers)\n                for r in rows:\n                    values = xlsx_row_values(r)\n                    if not include_raw_ocr:\n                        values[-1] = ""\n                    sh.append(values)\n                style_table_sheet(sh, widths=full_widths, status_col=16)\n'''

OLD_DETAIL_CALLS = '''            add_full_sheet("Podlaží – vše", effective)\n            add_full_sheet("Nosníky", [r for r in effective if r.element_type == "beam"])\n            add_full_sheet("Smykové trny", [r for r in effective if r.element_type == "dowel"])\n            add_full_sheet("Mezivýplně", [r for r in effective if r.element_type == "infill"])\n'''
NEW_DETAIL_CALLS = '''            self.status_var.set(f"Zapisuji detailní listy · {export_scope_text}…")\n            self.update_idletasks()\n            add_full_sheet("Podlaží – vše", effective, include_raw_ocr=True)\n            add_full_sheet("Nosníky", [r for r in effective if r.element_type == "beam"])\n            add_full_sheet("Smykové trny", [r for r in effective if r.element_type == "dowel"])\n            add_full_sheet("Mezivýplně", [r for r in effective if r.element_type == "infill"])\n'''

OLD_REV = '''            if self.previous_sources:\n                rev_rows = [\n                    r for r in compare_revisions(self.sources, self.previous_sources)\n                    if r.floor in selected_export_floors\n                ]\n                rev = wb.create_sheet("Revize")\n'''
NEW_REV = '''            if self.previous_sources:\n                # Compare only selected floors. Filtering after compare still made the\n                # revision engine process the full twenty-floor action.\n                def export_sources_only(source_list):\n                    out = []\n                    for src in source_list:\n                        rows = [r for r in src.rows if r.floor in selected_export_floors]\n                        drawing_rows = [r for r in src.drawing_rows if r.floor in selected_export_floors]\n                        if rows or drawing_rows:\n                            out.append(SourceInfo(\n                                path=src.path, floor=src.floor, kind=src.kind, rows=rows,\n                                drawing_rows=drawing_rows, warning=src.warning, cached=src.cached,\n                            ))\n                    return out\n                rev_rows = compare_revisions(\n                    export_sources_only(self.sources), export_sources_only(self.previous_sources)\n                )\n                rev = wb.create_sheet("Revize")\n'''

OLD_HISTORY = '''                for d in self.database.list_decodings(int(self.current_project_id)):\n                    history.append([\n'''
NEW_HISTORY = '''                correction_counts = {}\n                try:\n                    with self.database.connect() as con:\n                        correction_counts = {\n                            int(r[0]): int(r[1])\n                            for r in con.execute("SELECT decoding_id,COUNT(*) FROM corrections GROUP BY decoding_id")\n                        }\n                except Exception:\n                    correction_counts = {}\n                for d in self.database.list_decodings(int(self.current_project_id)):\n                    history.append([\n'''

OLD_HISTORY_COUNT = '''                        len(self.database.list_corrections(int(d["id"]))), d["revision_note"] or "",\n'''
NEW_HISTORY_COUNT = '''                        correction_counts.get(int(d["id"]), 0), d["revision_note"] or "",\n'''


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".update_tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    app = root / "app.py"
    version_file = root / "VERSION.txt"
    if not app.exists():
        raise RuntimeError("Ve zvolené složce nebyl nalezen app.py.")
    current = version_file.read_text(encoding="utf-8-sig", errors="replace").strip() if version_file.exists() else ""
    if current == TO_VERSION:
        return 0
    if current != FROM_VERSION:
        raise RuntimeError(f"Tento krok očekává v{FROM_VERSION}, nalezena v{current or '?'}.")

    text = app.read_text(encoding="utf-8-sig", errors="strict").replace("\r\n", "\n")
    if 'APP_VERSION = "0.13.7"' not in text:
        raise RuntimeError("app.py neobsahuje očekávanou verzi v0.13.7; aktualizace nic nepřepsala.")

    replacements = [
        (OLD_WB, NEW_WB, "výchozí styl sešitu"),
        (OLD_BODY_STYLE, NEW_BODY_STYLE, "formátování datových buněk"),
        (OLD_ADD_FULL, NEW_ADD_FULL, "detailní listy"),
        (OLD_DETAIL_CALLS, NEW_DETAIL_CALLS, "zápis detailních listů"),
        (OLD_REV, NEW_REV, "porovnání revizí"),
        (OLD_HISTORY, NEW_HISTORY, "historie verzí"),
        (OLD_HISTORY_COUNT, NEW_HISTORY_COUNT, "počty ručních oprav"),
    ]
    for old, new, label in replacements:
        if old not in text:
            raise RuntimeError(f"Nebyl nalezen očekávaný blok: {label}.")
        text = text.replace(old, new, 1)

    text = text.replace('APP_VERSION = "0.13.7"', 'APP_VERSION = "0.13.8"', 1)
    if 'APP_VERSION = "0.13.8"' not in text or "export_sources_only" not in text:
        raise RuntimeError("Kontrola změn v app.py selhala.")
    compile(text, str(app), "exec")

    backup_root = root / ".update_backup" / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_0137_to_0138_fast")
    backups = []
    try:
        for target in (app, version_file):
            backup = None
            if target.exists():
                backup = backup_root / target.name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            backups.append((target, backup))
        atomic_write(app, text.encode("utf-8"))
        atomic_write(version_file, b"0.13.8\n")
        compile(app.read_text(encoding="utf-8"), str(app), "exec")
    except Exception:
        for target, backup in reversed(backups):
            try:
                if backup is not None and backup.exists():
                    shutil.copy2(backup, target)
            except Exception:
                pass
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
