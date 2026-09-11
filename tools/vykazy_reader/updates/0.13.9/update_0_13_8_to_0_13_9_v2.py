from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.8"
TO_VERSION = "0.13.9"

NEW_FUNCTION = '''    def _order_export_profile_selected(self) -> bool:\n        \"\"\"Return True only from the dedicated Excel export profile control.\n\n        Never probe arbitrary application objects with ``.get()``. The internal\n        worker_queue also exposes a blocking ``get()`` method; probing it from the\n        Tk main thread could freeze the export before Excel generation even started.\n        \"\"\"\n        var = getattr(self, \"export_profile_var\", None)\n        if var is None:\n            return False\n        try:\n            return normalize_key(str(var.get())) == normalize_key(\"Výkaz pro objednávku\")\n        except Exception:\n            return False\n\n'''


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
    if 'APP_VERSION = "0.13.8"' not in text:
        raise RuntimeError("app.py neobsahuje očekávanou verzi v0.13.8; aktualizace nic nepřepsala.")

    pattern = re.compile(
        r"(?ms)^    def _order_export_profile_selected\(self\) -> bool:\n.*?(?=^    def _export_order_selected_floors\(self\):)"
    )
    text, count = pattern.subn(NEW_FUNCTION, text, count=1)
    if count != 1:
        raise RuntimeError("Nebyla nalezena funkce detekce exportního profilu; aktualizace nic nepřepsala.")

    text = text.replace('APP_VERSION = "0.13.8"', 'APP_VERSION = "0.13.9"', 1)
    if 'APP_VERSION = "0.13.9"' not in text:
        raise RuntimeError("Kontrola změny verze selhala.")
    compile(text, str(app), "exec")

    backup_root = root / ".update_backup" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_0138_to_0139_export_hang_v2"
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
        atomic_write(version_file, b"0.13.9\n")
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
