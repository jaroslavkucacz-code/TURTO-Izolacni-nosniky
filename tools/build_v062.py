from __future__ import annotations

import hashlib
import json
import py_compile
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_CODE = ROOT / "updates" / "0.6.1"
CORRECTED_DATA = ROOT / "updates" / "0.6.0" / "catalogs"
OUT = ROOT / "updates" / "0.6.2"

FILES = [
    "app.pyw",
    "catalog_engine.py",
    "project_model.py",
    "project_ui.py",
    "autocomplete.py",
    "updater.py",
    "catalogs/maxfrank_egcobox_m_2022.json.gz.b64",
    "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE_CODE, OUT)

    # Corrected MAX FRANK catalogs are rebuilt by the workflow immediately before this script.
    for name in ["maxfrank_egcobox_m_2022.json.gz.b64", "maxfrank_egcobox_xl_2022.json.gz.b64"]:
        src = CORRECTED_DATA / name
        dst = OUT / "catalogs" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    app = OUT / "app.pyw"
    text = app.read_text(encoding="utf-8")
    text, count = re.subn(r'APP_VERSION = "0\.6\.1"', 'APP_VERSION = "0.6.2"', text, count=1)
    if count != 1:
        raise SystemExit("APP_VERSION 0.6.1 not found exactly once")
    app.write_text(text, encoding="utf-8")

    for name in ["app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py"]:
        py_compile.compile(str(OUT / name), doraise=True)

    # Regression test: the exact real-world designation reported by the user must exist.
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("catalog_engine", OUT / "catalog_engine.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    db = module.CatalogDatabase(OUT / "catalogs")
    qr = db.query(
        catalog_id="maxfrank-egcobox-xl-eta-19-0046-2022",
        manufacturer="MAX FRANK",
        model="XL",
        type_name="MXL",
        generation="ETA-19/0046",
        moment_class="MXL20",
        concrete_min="C25/30",
        shear_class="V6±",
        cover="C30",
        height_mm="200",
    )
    assert "MXL20" in qr.designation and "V6±" in qr.designation and "C30" in qr.designation and "h200" in qr.designation, qr.designation
    print("REGRESSION OK:", qr.designation, qr.moment_text, qr.shear_text)

    base = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.2/"
    manifest_files = []
    for rel in FILES:
        p = OUT / rel
        manifest_files.append({
            "path": rel,
            "url": base + rel,
            "sha256": sha256(p),
        })

    manifest = {
        "version": "0.6.2",
        "notes": (
            "Oprava MAX FRANK: doplněny chybějící výšky pro krytí C30 vzniklé chybou při čtení PDF tabulek. "
            "Ověřeno mimo jiné označení MXL20-V6±-C30-h200 pro C25/30. Zachována preference betonu projektu C25/30 a zápis ± jako +-/+/-."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
