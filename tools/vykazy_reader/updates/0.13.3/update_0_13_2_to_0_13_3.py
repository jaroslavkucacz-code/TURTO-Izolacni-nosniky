from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.2"
TO_VERSION = "0.13.3"
OLD_TITLE = "TURTO – Výkazy izolačních prvků"
NEW_TITLE = "TURTO – Výkazy kladecích plánů"
OLD_TITLE_UPPER = "TURTO – VÝKAZY IZOLAČNÍCH PRVKŮ"
NEW_TITLE_UPPER = "TURTO – VÝKAZY KLADECÍCH PLÁNŮ"
OLD_APP_VERSION = 'APP_VERSION = "0.13.2"'
NEW_APP_VERSION = 'APP_VERSION = "0.13.3"'


def atomic_write_text(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".patch_tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    app = root / "app.py"
    readme = root / "README.txt"
    version_file = root / "VERSION.txt"

    if not app.exists():
        raise RuntimeError("Ve zvolené složce nebyl nalezen app.py.")

    current = version_file.read_text(encoding="utf-8-sig", errors="replace").strip() if version_file.exists() else ""
    if current == TO_VERSION:
        return 0
    if current != FROM_VERSION:
        raise RuntimeError(f"Tento krok očekává v{FROM_VERSION}, nalezena v{current or '?'}.")

    app_text = app.read_text(encoding="utf-8")
    if OLD_TITLE not in app_text:
        raise RuntimeError("V app.py nebyl nalezen očekávaný původní název aplikace; aktualizace byla zastavena.")
    if OLD_APP_VERSION not in app_text:
        raise RuntimeError("app.py neodpovídá očekávané verzi v0.13.2; aktualizace byla zastavena.")

    readme_text = readme.read_text(encoding="utf-8-sig", errors="replace") if readme.exists() else None

    targets = [app, version_file] + ([readme] if readme.exists() else [])
    backup_root = root / ".update_backup" / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_patch_0133")
    backups: list[tuple[Path, Path | None]] = []

    try:
        for target in targets:
            backup = None
            if target.exists():
                backup = backup_root / target.relative_to(root)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            backups.append((target, backup))

        new_app_text = app_text.replace(OLD_TITLE, NEW_TITLE).replace(OLD_APP_VERSION, NEW_APP_VERSION)
        if OLD_TITLE in new_app_text or NEW_TITLE not in new_app_text or NEW_APP_VERSION not in new_app_text:
            raise RuntimeError("Kontrola přejmenování aplikace nebo verze selhala.")
        atomic_write_text(app, new_app_text)

        if readme_text is not None:
            new_readme = readme_text.replace(OLD_TITLE_UPPER, NEW_TITLE_UPPER).replace(OLD_TITLE, NEW_TITLE)
            atomic_write_text(readme, new_readme)

        atomic_write_text(version_file, TO_VERSION + "\n")
        return 0
    except Exception:
        for target, backup in reversed(backups):
            try:
                if backup is not None and backup.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, target)
                elif backup is None and target.exists():
                    target.unlink()
            except Exception:
                pass
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
