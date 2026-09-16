from __future__ import annotations

import ast
import hashlib
import os
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.10"
TO_VERSION = "0.13.11"
HELPER_URL = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/873b4bbab7fcb1975da397f3031342677df6719e/tools/vykazy_reader/updates/0.13.11/ocr_piece_schedule.txt"
HELPER_SHA256 = "7dff28dfecc0277433283848c30f331ea601cb0960dc122dbf41b5cdc4c91c49"


def once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Nelze bezpečně aktualizovat: {label}. Nic nebylo přepsáno.")
    return text.replace(old, new, 1)


def update_source(text: str, helper: str) -> str:
    if 'APP_VERSION = "0.13.10"' not in text:
        raise RuntimeError("app.py není očekávaná v0.13.10; aktualizace nic nepřepsala.")
    text = once(text,
        '        # Preserve current detection context; content itself comes from the identical hash.\n',
        '        # Never cache a failed or empty schedule as a successful analysis.\n'
        '        if not src.rows or src.warning:\n'
        '            return None\n'
        '        # Preserve current detection context; content itself comes from the identical hash.\n',
        "kontrola uloženého výsledku")
    text = once(text, '        src.warning = ""\n        return src\n',
                '        return src\n', "zachování upozornění")
    text = once(text,
        '            if cached is None:\n                pending.append(info)\n',
        '            if cached is None or not cached.rows or cached.warning:\n                pending.append(info)\n',
        "ochrana opakované analýzy")
    anchor = '    def _extract_page_visual(self, page, floor: str, source: str, page_no: int, kind: str) -> list[BeamRow]:\n'
    text = once(text, anchor, helper + '\n' + anchor, "doplnění čtení mezikusů")
    start = text.index(anchor)
    end = text.index('    def _parse_ocr_text(', start)
    method = text[start:end]
    method = once(method,
        '        candidates = self._table_candidates(low)\n',
        '        candidates = self._table_candidates(low)\n'
        '        # Special piece tables may be vertically below the main beam table.\n'
        '        # Read their separated cells once; keep the existing beam reader intact.\n'
        '        try:\n'
        '            infill_rows = self._extract_visual_infill_schedule(\n'
        '                page, floor, source, page_no, kind, low, candidates\n'
        '            )\n'
        '        except Exception as exc:\n'
        '            self.log(f"{source}: OCR mezikusů selhalo: {exc}")\n'
        '            infill_rows = []\n',
        "oddělené tabulky pod nosníky")
    method = once(method, '            return self._dedupe(collected)\n',
                  '            return self._dedupe(collected + infill_rows)\n', "spojení barevných tabulek")
    method = once(method, '        return best_rows\n',
                  '        return self._dedupe(best_rows + infill_rows)\n', "spojení ostatních tabulek")
    text = text[:start] + method + text[end:]
    text = once(text, 'APP_VERSION = "0.13.10"', 'APP_VERSION = "0.13.11"', "číslo verze")
    compile(text, "app.py", "exec")
    tree = ast.parse(text)
    extractor = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TableExtractor")
    if sum(isinstance(n, ast.FunctionDef) and n.name == "_extract_visual_infill_schedule" for n in extractor.body) != 1:
        raise RuntimeError("Kontrola nové čtecí funkce selhala; nic nebylo přepsáno.")
    return text


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".update_tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    app, version = root / "app.py", root / "VERSION.txt"
    current = version.read_text(encoding="utf-8-sig").strip()
    if current == TO_VERSION:
        return 0
    if current != FROM_VERSION:
        raise RuntimeError(f"Aktualizace očekává v{FROM_VERSION}, nalezena v{current}.")
    req = urllib.request.Request(HELPER_URL, headers={"Cache-Control": "no-cache", "User-Agent": "TURTO-Vykazy-0.13.11"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != HELPER_SHA256:
        raise RuntimeError("Kontrolní součet čtecí funkce nesouhlasí; aktualizace nic nepřepsala.")
    result = update_source(app.read_text(encoding="utf-8-sig"), data.decode("utf-8"))
    backup = root / ".update_backup" / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_01310_to_01311")
    backup.mkdir(parents=True, exist_ok=False)
    for path in (app, version):
        shutil.copy2(path, backup / path.name)
    try:
        atomic_write(app, result.encode("utf-8"))
        compile(app.read_bytes(), str(app), "exec")
        atomic_write(version, (TO_VERSION + "\n").encode("ascii"))
    except Exception:
        for path in (app, version):
            shutil.copy2(backup / path.name, path)
        raise
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
