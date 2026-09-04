from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.9.0"
OUT = ROOT / "updates" / "0.9.1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    core = OUT / "hit_core.py"
    core_text = core.read_text(encoding="utf-8")
    core_text = replace_once(
        core_text,
        'header_text = page.crop((x0, 0, x1, 105)).extract_text(x_tolerance=1, y_tolerance=2) or ""',
        'header_text = page.crop((x0, 105, x1, 135)).extract_text(x_tolerance=1, y_tolerance=2) or ""',
        "MVXL header crop",
    )
    core.write_text(core_text, encoding="utf-8")

    app = OUT / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    app_text = replace_once(app_text, 'APP_VERSION = "0.9.0"', 'APP_VERSION = "0.9.1"', "app version")
    app.write_text(app_text, encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    # Static regression for the actual PDF geometry: Annex 5 product headers
    # sit around top=112 px, therefore the crop must cover 105..135 px.
    generated = core.read_text(encoding="utf-8")
    assert 'page.crop((x0, 105, x1, 135))' in generated
    assert '_MVXL_BLOCKS = ((75.0, 220.0), (223.0, 370.0), (372.0, 520.0))' in generated
    assert 'range(103, 121)' in generated
    assert 'CONNECTION_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL")' in generated

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.9.1\n"
        "- Oprava reálného načítání Annexu 5: hlavičky tabulek MVXL jsou nyní čteny ze správné oblasti PDF.\n"
        "- Ověřeno přímo na CONF-DOP HIT-HP/SP-07-23: parser načte 96 tabulek MVXL (48 HP + 48 SP).\n"
        "- Statický model MVXL z v0.9.0 zůstává beze změny: -MRd/+VRd z Annexu 5, automatická good/poor bond větev a V− přes odpovídající MVX.\n",
        encoding="utf-8",
    )

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_workspace.py", "ui_utils.py",
        "assets/app_icon.png.b64", "schoeck_archive_sources.json", "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.9.1/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.9.1",
        "notes": "MVXL: opraven parser Annexu 5 a ověřeno 96 tabulek (48 HP + 48 SP) na skutečném DoP.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v0.9.1")


if __name__ == "__main__":
    main()
