from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.9"
TO_VERSION = "0.13.10"


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
    if 'APP_VERSION = "0.13.9"' not in text:
        raise RuntimeError("app.py neobsahuje očekávanou verzi v0.13.9; aktualizace nic nepřepsala.")

    # All sortable tables: heading alignment always mirrors the cell/column alignment.
    old_sort = '        current = tree.heading(col, "text")\n        tree.heading(col, text=current, command=lambda c=col: sort_col(c))\n'
    new_sort = '        current = tree.heading(col, "text")\n        anchor = tree.column(col, "anchor")\n        tree.heading(col, text=current, anchor=anchor, command=lambda c=col: sort_col(c))\n'
    if old_sort not in text:
        raise RuntimeError("Nebyl nalezen společný blok záhlaví tabulek.")
    text = text.replace(old_sort, new_sort, 1)

    # Database tables: every column participates in resizing/stretching. Native Treeview
    # separator dragging remains enabled; the table also expands naturally with the dialog.
    patterns = [
        (r'self\.projects\.heading\(c, text=t(?:, anchor=a)?\); self\.projects\.column\(c, width=w, minwidth=50, stretch=.*?, anchor=a\)',
         'self.projects.heading(c, text=t, anchor=a); self.projects.column(c, width=w, minwidth=50, stretch=True, anchor=a)', 'seznam akcí'),
        (r'self\.decodings\.heading\(c, text=t(?:, anchor=a)?\); self\.decodings\.column\(c, width=w, minwidth=46, stretch=.*?, anchor=a\)',
         'self.decodings.heading(c, text=t, anchor=a); self.decodings.column(c, width=w, minwidth=46, stretch=True, anchor=a)', 'verze podkladů'),
        (r'self\.docs\.heading\(c, text=t(?:, anchor=a)?\); self\.docs\.column\(c, width=w, minwidth=52, stretch=.*?, anchor=a\)',
         'self.docs.heading(c, text=t, anchor=a); self.docs.column(c, width=w, minwidth=52, stretch=True, anchor=a)', 'PDF podklady'),
        (r'tree\.heading\(c,text=t(?:,anchor=a)?\); tree\.column\(c,width=w,minwidth=55,stretch=.*?,anchor=a\)',
         'tree.heading(c,text=t,anchor=a); tree.column(c,width=w,minwidth=55,stretch=True,anchor=a)', 'historie oprav'),
    ]
    for pattern, replacement, label in patterns:
        text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise RuntimeError(f"Nebyla nalezena tabulka: {label}.")

    text = text.replace('APP_VERSION = "0.13.9"', 'APP_VERSION = "0.13.10"', 1)
    if 'APP_VERSION = "0.13.10"' not in text or 'anchor=anchor' not in text:
        raise RuntimeError("Kontrola změn v app.py selhala.")
    compile(text, str(app), "exec")

    backup_root = root / ".update_backup" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_0139_to_01310_db_columns"
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
        atomic_write(version_file, b"0.13.10\n")
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
