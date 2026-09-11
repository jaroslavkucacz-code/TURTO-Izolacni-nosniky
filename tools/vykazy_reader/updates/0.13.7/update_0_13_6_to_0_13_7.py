from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.6"
TO_VERSION = "0.13.7"

OLD_DATA_BLOCK = '            # ── Source/effective data ──────────────────────────────────────\n            effective = sorted(\n                effective_floor_rows_from_sources(self.sources),\n                key=lambda r: (natural_floor_key(r.floor), r.element_type, normalize_key(r.raw_name)),\n            )\n            schedule = [r for s in self.sources if s.kind == "floor" for r in s.rows]\n            drawing = [r for s in self.sources if s.kind == "floor" for r in s.drawing_rows]\n            floors = sorted({r.floor for r in effective if r.floor and r.floor not in ("?", "SUMÁŘ", "SUMAR")}, key=natural_floor_key)\n'
NEW_DATA_BLOCK = '            # ── Source/effective data ──────────────────────────────────────\n            # The complete audit export follows the floor selection visible in the\n            # main window. v0.13.6 limited only the order profile; the complete profile\n            # still rebuilt the whole object and could look frozen on larger projects.\n            all_effective = effective_floor_rows_from_sources(self.sources)\n            available_floors = {\n                r.floor for r in all_effective\n                if r.floor and r.floor not in ("?", "SUMÁŘ", "SUMAR")\n            }\n            selected_export_floors = self._selected_floors() & available_floors\n            if not selected_export_floors:\n                messagebox.showinfo(\n                    "Kompletní export",\n                    "Vyberte alespoň jedno podlaží v části Podlaží.",\n                    parent=self,\n                )\n                return\n\n            export_all_floors = selected_export_floors == available_floors\n            floors = sorted(selected_export_floors, key=natural_floor_key)\n            export_scope_text = "Celý objekt" if export_all_floors else ", ".join(floors)\n\n            effective = sorted(\n                [r for r in all_effective if r.floor in selected_export_floors],\n                key=lambda r: (natural_floor_key(r.floor), r.element_type, normalize_key(r.raw_name)),\n            )\n            schedule = [\n                r for s in self.sources if s.kind == "floor"\n                for r in s.rows if r.floor in selected_export_floors\n            ]\n            drawing = [\n                r for s in self.sources if s.kind == "floor"\n                for r in s.drawing_rows if r.floor in selected_export_floors\n            ]\n            self.status_var.set(f"Vytvářím kompletní Excel export · {export_scope_text}…")\n            self.update_idletasks()\n'
OLD_SUMMARY_CHECK = '            if any(s.kind == "summary" for s in self.sources):\n                part = compare_rows(effective, [r for s in self.sources if s.kind == "summary" for r in s.rows])\n                checks.extend(part)\n                check_types.extend(["Podlaží × celkový výkaz"] * len(part))\n'
NEW_SUMMARY_CHECK = '            # The object-wide PDF summary is comparable only when every floor is exported.\n            # Comparing a selected subset against the whole-object summary would create\n            # artificial differences and unnecessary workbook work.\n            if export_all_floors and any(s.kind == "summary" for s in self.sources):\n                part = compare_rows(effective, [r for s in self.sources if s.kind == "summary" for r in s.rows])\n                checks.extend(part)\n                check_types.extend(["Podlaží × celkový výkaz"] * len(part))\n'
OLD_SUMMARY_ROWS = '            summary_rows = [\n                ("Akce", self.current_project_name or "—"),\n                ("ID akce", f"A{int(self.current_project_id):04d}" if self.current_project_id else "—"),\n'
NEW_SUMMARY_ROWS = '            summary_rows = [\n                ("Akce", self.current_project_name or "—"),\n                ("Rozsah exportu", export_scope_text),\n                ("ID akce", f"A{int(self.current_project_id):04d}" if self.current_project_id else "—"),\n'
OLD_REV = '            if self.previous_sources:\n                rev_rows = compare_revisions(self.sources, self.previous_sources)\n                rev = wb.create_sheet("Revize")\n'
NEW_REV = '            if self.previous_sources:\n                rev_rows = [\n                    r for r in compare_revisions(self.sources, self.previous_sources)\n                    if r.floor in selected_export_floors\n                ]\n                rev = wb.create_sheet("Revize")\n'
OLD_SAVE = '            wb.save(path)\n            self._mark_current_project_exported()\n            self.status_var.set(f"Excel uložen: {path}")\n'
NEW_SAVE = '            self.status_var.set(f"Ukládám Excel · {export_scope_text}…")\n            self.update_idletasks()\n            wb.save(path)\n            self._mark_current_project_exported()\n            self.status_var.set(f"Excel uložen: {path} · {export_scope_text}")\n'


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
    if 'APP_VERSION = "0.13.6"' not in text:
        raise RuntimeError("app.py neobsahuje očekávanou verzi v0.13.6; aktualizace nic nepřepsala.")
    if "def _export_order_selected_floors(self):" not in text:
        raise RuntimeError("Chybí exportní profil v0.13.6; aktualizace byla zastavena.")
    for old, label in (
        (OLD_DATA_BLOCK, "blok kompletního exportu"),
        (OLD_SUMMARY_CHECK, "kontrola celkového výkazu"),
        (OLD_SUMMARY_ROWS, "souhrnný blok"),
        (OLD_REV, "revizní blok"),
        (OLD_SAVE, "závěr Excel exportu"),
    ):
        if old not in text:
            raise RuntimeError(f"Nebyl nalezen očekávaný {label} ve v0.13.6.")

    text = text.replace(OLD_DATA_BLOCK, NEW_DATA_BLOCK, 1)
    text = text.replace(OLD_SUMMARY_CHECK, NEW_SUMMARY_CHECK, 1)
    text = text.replace(OLD_SUMMARY_ROWS, NEW_SUMMARY_ROWS, 1)
    text = text.replace(OLD_REV, NEW_REV, 1)
    text = text.replace(OLD_SAVE, NEW_SAVE, 1)
    text = text.replace('APP_VERSION = "0.13.6"', 'APP_VERSION = "0.13.7"', 1)

    if 'APP_VERSION = "0.13.7"' not in text or "selected_export_floors" not in text:
        raise RuntimeError("Kontrola změn v app.py selhala.")
    compile(text, str(app), "exec")

    backup_root = root / ".update_backup" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_0136_to_0137"
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
        atomic_write(version_file, b"0.13.7\n")
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
