from __future__ import annotations

"""Source-level checks for TURTO PDF multi-selection, catalogs and current PDF overlays."""

import ast
import runpy
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


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.strip().split("."))


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

    current = (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip()
    if _version_tuple(current) >= (2, 2, 40):
        overlay = ROOT / "updates" / "2.2.40" / "pdf_context_240.py"
        text = _text(overlay)
        assert '"Záměny smykových trnů"' in text
        assert '"VRd navržené záměny"' in text
        assert '"VRd původního trnu – pouze reference"' in text
        assert '"Únosnosti nejsou interpolovány."' in text
        assert "shear_substitution_rows" in text
        namespace = runpy.run_path(str(overlay), run_name="verify_pdf_context_240")
        namespace["selftest"]()

    if _version_tuple(current) >= (2, 2, 41):
        verifier = runpy.run_path(str(ROOT / "tools" / "verify_cret_sync_241.py"), run_name="verify_cret_sync_241_entry")
        verifier["main"]()

    print(f"TURTO {current}: PDF multi-selection, catalog browser and PDF context checks OK")


if __name__ == "__main__":
    main()
