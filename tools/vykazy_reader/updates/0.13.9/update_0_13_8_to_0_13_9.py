from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.8"
TO_VERSION = "0.13.9"

OLD = '    def _order_export_profile_selected(self) -> bool:\n        """Return True when the UI currently has the order-export profile selected.\n\n        The profile control was introduced in v0.13.5.  Detect it by its displayed\n        value instead of coupling this update to one Tk variable name.\n        """\n        target = normalize_key("Výkaz pro objednávku")\n        for value in vars(self).values():\n            getter = getattr(value, "get", None)\n            if not callable(getter):\n                continue\n            try:\n                current = getter()\n            except Exception:\n                continue\n            if isinstance(current, str) and target in normalize_key(current):\n                return True\n        return False\n\n'

NEW = '    def _order_export_profile_selected(self) -> bool:\n        """Return True only from the dedicated Excel export profile control.\n\n        Never probe arbitrary application objects with ``.get()``.  ``worker_queue``\n        also has a blocking ``get()`` method; probing it from the Tk main thread made\n        complete exports appear permanently frozen when the queue was empty.\n        """\n        var = getattr(self, "export_profile_var", None)\n        if var is None:\n            return False\n        try:\n            return normalize_key(str(var.get())) == normalize_key("Výkaz pro objednávku")\n        except Exception:\n            return False\n\n'


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
    if OLD not in text:
        raise RuntimeError("Nebyla nalezena chybná detekce exportního profilu; aktualizace nic nepřepsala.")

    text = text.replace(OLD, NEW, 1)
    text = text.replace('APP_VERSION = "0.13.8"', 'APP_VERSION = "0.13.9"', 1)
    if 'APP_VERSION = "0.13.9"' not in text or "worker_queue" not in NEW:
        raise RuntimeError("Kontrola změn v app.py selhala.")
    compile(text, str(app), "exec")

    backup_root = root / ".update_backup" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_0138_to_0139_export_hang"
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
