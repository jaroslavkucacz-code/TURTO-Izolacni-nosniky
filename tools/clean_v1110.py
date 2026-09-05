from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "updates" / "1.1.10"
VERSION = "1.1.10"
RAW_BASE = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main"

for directory in list(TARGET.rglob("__pycache__")):
    if directory.is_dir():
        shutil.rmtree(directory)
for path in list(TARGET.rglob("*.pyc")):
    if path.is_file():
        path.unlink()

files = []
for path in sorted(TARGET.rglob("*")):
    if not path.is_file():
        continue
    relative = path.relative_to(TARGET).as_posix()
    files.append(
        {
            "path": relative,
            "url": f"{RAW_BASE}/updates/{VERSION}/{relative}",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    )
manifest = {
    "version": VERSION,
    "notes": "TURTO ISO: klávesové zkratky a profesionálně přepracovaný PDF výstup záměn.",
    "files": files,
}
(ROOT / "update_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Cleaned TURTO ISO v{VERSION}: {len(files)} update files")
