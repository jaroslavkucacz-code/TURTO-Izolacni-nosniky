from __future__ import annotations

"""Static regression checks for TURTO 2.2.9."""

import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "updates" / "2.2.9"


def _read(path: Path) -> str:
    assert path.exists(), f"Missing {path}"
    return path.read_text(encoding="utf-8")


def _parse(path: Path) -> str:
    text = _read(path)
    ast.parse(text, filename=str(path))
    return text


def main() -> None:
    app = _parse(REL / "app.pyw")
    app_runtime = _parse(REL / "app_runtime.pyw")
    installer = _parse(REL / "runtime_installer.py")
    workspace = _parse(REL / "platform_workspace.py")
    pdf_scope = _parse(REL / "pdf_scope.py")
    catalog_links = _parse(REL / "catalog_links_229.py")
    catalog_access = _parse(REL / "catalog_access_229.py")

    # PDF: checkboxes + one or more independent scopes, with overlap de-duplication.
    assert "ttk.Checkbutton" in pdf_scope
    assert "tk.BooleanVar" in pdf_scope
    assert "rows_for_scopes" in pdf_scope
    assert "_section_keys_for_scopes" in pdf_scope
    assert "Překrývající se volby" in pdf_scope
    assert "Vyberte alespoň jednu položku" in pdf_scope
    assert "len(selected)" in pdf_scope
    assert "ttk.Radiobutton" not in pdf_scope

    # Catalogue access: all current thermal/historical and shear manufacturer families.
    urls = re.findall(r'"(https://[^\"]+)"', catalog_links)
    assert len(urls) == 9, urls
    assert len(set(urls)) == len(urls)
    for token in (
        "thermal.leviat.hit",
        "thermal.schoeck.isokorb",
        "thermal.pohlcon.isopro",
        "thermal.maxfrank.egcobox",
        "shear.ancon.dsd",
        "shear.schoeck.stacon-ld",
        "shear.pohlcon.hed",
        "shear.pohlcon.jdsd",
        "shear.maxfrank.egcodorn",
    ):
        assert token in catalog_links

    current_shear = _read(ROOT / "updates" / "2.2.7" / "shear_catalogs_227.py")
    match = re.search(r"TARGET_MANUFACTURERS\s*=\s*\((.*?)\)", current_shear, re.S)
    assert match, "TARGET_MANUFACTURERS missing"
    for manufacturer in ("Ancon", "Schöck", "PohlCon", "MAX FRANK"):
        assert manufacturer in match.group(1)
        assert manufacturer in catalog_links

    legacy_thermal = _read(ROOT / "updates" / "1.1.17" / "catalog_engine.py")
    for manufacturer in ("Schöck", "ISOPRO", "MAX FRANK"):
        assert manufacturer in legacy_thermal
    thermal_platform = _read(ROOT / "updates" / "2.0.0" / "platform_registry.py")
    assert "Leviat" in thermal_platform and "HIT" in thermal_platform
    assert "Katalogy / podklady" in catalog_access
    assert "Nahlédnout" in catalog_access
    assert "Načtené DoP HIT" in catalog_access
    assert '"Export PDF" in str(widget.cget("text"))' in catalog_access
    assert "apply_catalog_access(self)" in workspace

    # Release/bootstrap safety.
    assert 'WORKSPACE_VERSION = "2.2.9"' in workspace
    assert 'APP_VERSION = "2.2.9"' in app_runtime
    assert 'VERSION = "2.2.9"' in app
    assert "actions.sqlite3 is never modified" in installer
    assert 'BASE_PATH = "updates/2.2.8/runtime_installer.py"' in installer
    for name in (
        "app_runtime.pyw",
        "platform_workspace.py",
        "pdf_scope.py",
        "catalog_links_229.py",
        "catalog_access_229.py",
    ):
        assert name in installer
        assert name in app

    manifest = json.loads(_read(ROOT / "update_manifest.json"))
    assert manifest["version"] == "2.2.9"
    manifest_paths = {item["path"] for item in manifest["files"]}
    for name in ("app.pyw", "app_runtime.pyw", "platform_workspace.py", "pdf_scope.py", "catalog_links_229.py", "catalog_access_229.py"):
        assert name in manifest_paths

    assert _read(ROOT / "CURRENT_VERSION").strip() == "2.2.9"
    print("TURTO 2.2.9 verification OK")


if __name__ == "__main__":
    main()
