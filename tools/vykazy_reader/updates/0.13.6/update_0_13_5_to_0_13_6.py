from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.5"
TO_VERSION = "0.13.6"
MARKER = "def _export_order_selected_floors(self):"

HELPERS = r'''
    def _order_export_profile_selected(self) -> bool:
        """Return True when the UI currently has the order-export profile selected.

        The profile control was introduced in v0.13.5.  Detect it by its displayed
        value instead of coupling this update to one Tk variable name.
        """
        target = normalize_key("Výkaz pro objednávku")
        for value in vars(self).values():
            getter = getattr(value, "get", None)
            if not callable(getter):
                continue
            try:
                current = getter()
            except Exception:
                continue
            if isinstance(current, str) and target in normalize_key(current):
                return True
        return False

    def _export_order_selected_floors(self):
        """Export a purchase schedule only for floors checked in the main window."""
        if not self.sources:
            messagebox.showinfo("Výkaz pro objednávku", "Nejprve načtěte nebo analyzujte projekt.", parent=self)
            return
        if Workbook is None:
            messagebox.showerror(
                "Výkaz pro objednávku",
                "Chybí knihovna openpyxl. Spusťte znovu INSTALOVAT.bat.\n\n" + str(XLSX_IMPORT_ERROR or ""),
                parent=self,
            )
            return

        selected = self._selected_floors()
        if not selected:
            messagebox.showinfo(
                "Výkaz pro objednávku",
                "Vyberte alespoň jedno podlaží v části Podlaží.\n\n"
                "Objednávkový výkaz se vytváří pouze z aktuálně zaškrtnutých podlaží.",
                parent=self,
            )
            return

        rows = [
            r for r in effective_floor_rows_from_sources(self.sources)
            if r.floor in selected
        ]
        if not rows:
            messagebox.showinfo(
                "Výkaz pro objednávku",
                "Ve vybraných podlažích nejsou žádné položky k objednání.",
                parent=self,
            )
            return

        order_rows = aggregate_rows(rows, "OBJEDNÁVKA")
        floors = sorted(selected, key=natural_floor_key)
        floor_text = " + ".join(floors)
        safe_project = _safe_component(self.current_project_name or "TURTO_vykaz", 72)
        safe_floors = _safe_component(floor_text, 48)
        path = filedialog.asksaveasfilename(
            title="Výkaz pro objednávku – vybraná podlaží",
            defaultextension=".xlsx",
            initialfile=f"{safe_project} - objednávka - {safe_floors}.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return

        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Objednávka"
            ws.sheet_view.showGridLines = False

            headers = ("Označení", "Množství", "MJ")
            for col, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(name="Calibri", size=11, bold=True)
                cell.alignment = Alignment(horizontal="left" if col == 1 else "center", vertical="center")

            for row_no, row in enumerate(order_rows, start=2):
                designation = row.exact_name or row.raw_name
                ws.cell(row=row_no, column=1, value=designation)
                qty = row.qty
                ws.cell(row=row_no, column=2, value=qty)
                ws.cell(row=row_no, column=3, value=row.quantity_unit or "ks")
                for col in range(1, 4):
                    ws.cell(row=row_no, column=col).font = Font(name="Calibri", size=10)
                ws.cell(row=row_no, column=2).alignment = Alignment(horizontal="right")
                ws.cell(row=row_no, column=3).alignment = Alignment(horizontal="center")

            ws.column_dimensions["A"].width = 48
            ws.column_dimensions["B"].width = 14
            ws.column_dimensions["C"].width = 10
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = f"A1:C{max(1, ws.max_row)}"
            ws.print_title_rows = "1:1"
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.page_margins.left = 0.25
            ws.page_margins.right = 0.25
            ws.page_margins.top = 0.45
            ws.page_margins.bottom = 0.45
            wb.save(path)

            # Preserve the v0.13.5 workflow: a successful Excel export marks the action
            # as exported when the database exposes the status setter.
            if self.current_project_id:
                setter = getattr(self.database, "set_project_status", None)
                if callable(setter):
                    try:
                        setter(self.current_project_id, "Exportováno")
                        self._refresh_action_header()
                    except Exception:
                        pass

            self.status_var.set(
                f"Výkaz pro objednávku uložen: {path} · podlaží: {floor_text}"
            )
        except Exception as exc:
            messagebox.showerror(
                "Výkaz pro objednávku",
                f"Excel se nepodařilo vytvořit.\n\n{exc}",
                parent=self,
            )

'''


def choose_root() -> Path:
    candidates = [Path(sys.argv[1])] if len(sys.argv) > 1 else []
    candidates.append(Path.cwd())
    for candidate in candidates:
        try:
            root = candidate.resolve()
            if (root / "app.py").exists() and (root / "VERSION.txt").exists():
                return root
        except Exception:
            pass
    raise RuntimeError("Nebyla nalezena složka programu s app.py a VERSION.txt.")


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".update_tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def main() -> int:
    root = choose_root()
    app = root / "app.py"
    version_file = root / "VERSION.txt"
    current = version_file.read_text(encoding="utf-8-sig", errors="replace").strip()
    if current == TO_VERSION:
        return 0
    if current != FROM_VERSION:
        raise RuntimeError(f"Tento krok očekává v{FROM_VERSION}, nalezena v{current or '?'}.")

    text = app.read_text(encoding="utf-8-sig", errors="strict").replace("\r\n", "\n")
    if 'APP_VERSION = "0.13.5"' not in text:
        raise RuntimeError("app.py neobsahuje očekávanou verzi v0.13.5; aktualizace nic nepřepsala.")
    if "    def _selected_floors(self) -> set[str]:" not in text:
        raise RuntimeError("V app.py chybí výběr podlaží; aktualizace byla zastavena.")
    anchor = "    def _export_xlsx(self):\n"
    if anchor not in text:
        raise RuntimeError("V app.py nebyl nalezen Excel export; aktualizace byla zastavena.")

    if MARKER not in text:
        replacement = HELPERS + anchor + "        if self._order_export_profile_selected():\n            return self._export_order_selected_floors()\n"
        text = text.replace(anchor, replacement, 1)
    text = text.replace('APP_VERSION = "0.13.5"', 'APP_VERSION = "0.13.6"', 1)

    if MARKER not in text or 'APP_VERSION = "0.13.6"' not in text:
        raise RuntimeError("Kontrola změn v app.py selhala.")
    compile(text, "app.py", "exec")

    backup_root = root / ".update_backup" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_0135_to_0136"
    )
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
        atomic_write(version_file, b"0.13.6\n")
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
