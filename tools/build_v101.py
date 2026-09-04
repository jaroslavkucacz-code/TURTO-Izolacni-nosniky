from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.0.0"
OUT = ROOT / "updates" / "1.0.1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def compile_sources(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.suffix not in {".py", ".pyw"}:
            continue
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    workspace = OUT / "hit_workspace.py"
    ws = workspace.read_text(encoding="utf-8")
    ws = replace_once(ws, 'HIT_MODULE_VERSION = "1.0.0"', 'HIT_MODULE_VERSION = "1.0.1"', "module version")
    ws = replace_once(
        ws,
        '                if probe.schema_version >= 3:\n',
        '                if probe.schema_version >= 4:\n',
        "schema migration threshold",
    )
    workspace.write_text(ws, encoding="utf-8")

    app = OUT / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    app_text = replace_once(app_text, 'APP_VERSION = "1.0.0"', 'APP_VERSION = "1.0.1"', "app version")
    app.write_text(app_text, encoding="utf-8")

    compile_sources(OUT)

    generated = workspace.read_text(encoding="utf-8")
    assert 'if probe.schema_version >= 4:' in generated
    assert 'DATA_FILENAME' in generated
    assert 'HIT_MODULE_VERSION = "1.0.1"' in generated
    assert not any(OUT.rglob("*.pyc"))
    assert not any(p.name == "__pycache__" for p in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v1.0.1\n"
        "- Opravena automatická migrace HIT databáze po přechodu z v0.9.x / schema 3.\n"
        "- Při startu se stará HIT databáze již nepoužije jako aktuální; ze spravované kopie CONF-DOP se automaticky vytvoří schema 4.\n"
        "- Zachován kompletní aktuální návrh HIT: MVX, MVXL, ZVX, ZDX, DD, DVL, DDL, AT, FT a OTX včetně Annexu 2 OD/OU/WD/WU.\n"
        "- Historické HIT typy zůstávají mimo automatický návrh.\n",
        encoding="utf-8",
    )

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_special.py", "hit_workspace.py", "ui_utils.py",
        "assets/app_icon.png.b64", "schoeck_archive_sources.json", "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.0.1/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.0.1",
        "notes": "HIT: kompletní aktuální typy + oprava automatické migrace schema 3 → 4 po aktualizaci.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v1.0.1")


if __name__ == "__main__":
    main()
