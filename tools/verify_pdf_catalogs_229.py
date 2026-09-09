from __future__ import annotations

"""Source-level checks for TURTO 2.2.9 PDF multi-selection and catalog browser."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "updates" / "2.2.9" / "pdf_scope.py"
CATALOG = ROOT / "updates" / "2.2.9" / "catalog_browser.py"
WORKSPACE = ROOT / "updates" / "2.2.9" / "platform_workspace.py"
INSTALLER = ROOT / "updates" / "2.2.9" / "runtime_installer.py"


def _text(path: Path) -> str:
    value = path.read_text(encoding="utf-8")
    ast.parse(value, filename=str(path))
    return value


def main() -> None:
    pdf = _text(PDF)
    catalog = _text(CATALOG)
    workspace = _text(WORKSPACE)
    installer = _text(INSTALLER)

    assert "ttk.Checkbutton" in pdf, "PDF dialog must use multi-select checkboxes"
    assert "ttk.Radiobutton" not in pdf, "Single-choice PDF radio buttons must not return"
    assert "rows_for_scopes" in pdf and "normalize_scope_ids" in pdf
    for scope in (
        "iso.decoder", "iso.design", "iso.substitution",
        "shear.decoder", "shear.design", "shear.substitution",
    ):
        assert scope in pdf, f"Missing PDF section: {scope}"
    assert "Vyberte alespoň jednu položku" in pdf

    required_catalog_markers = (
        "Leviat / HALFEN", "Ancon / Leviat", "Schöck", "PohlCon", "MAX FRANK",
        "HIT", "HED", "JDSD / JDSDQ", "Egcodorn",
    )
    for marker in required_catalog_markers:
        assert marker in catalog, f"Missing catalog marker: {marker}"
    assert catalog.count("CatalogLink(") >= 6, "Expected at least six catalog entries"
    assert catalog.count("https://") >= 6, "Every catalog entry needs an HTTPS source"

    assert "Katalogy…" in workspace
    assert "open_catalog_browser" in workspace
    assert "export_pdf_dialog" in workspace
    assert "actions.sqlite3" in installer and "never modified" in installer

    print("TURTO 2.2.9: PDF multi-selection and catalog browser checks OK")


if __name__ == "__main__":
    main()
