from __future__ import annotations

"""Regression check for the visible manual shear-dowel design form (2.2.25)."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE_UI = ROOT / "updates" / "2.1.4" / "shear_dowels_ui_214.py"
BUGGY_LAYER = ROOT / "updates" / "2.2.21" / "shear_dowels_current.py"
FIXED_LAYER = ROOT / "updates" / "2.2.25" / "shear_dowels_current.py"
INSTALLER = ROOT / "updates" / "2.2.25" / "runtime_installer.py"
BOOTSTRAP = ROOT / "updates" / "2.2.25" / "app.pyw"
CONTRACT = ROOT / "updates" / "2.2.25" / "release_contract.json"


def _literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"{path}: chybí konstanta {name}")


def main() -> int:
    stable = STABLE_UI.read_text(encoding="utf-8")
    buggy = BUGGY_LAYER.read_text(encoding="utf-8")
    fixed = FIXED_LAYER.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    if 'quick.grid(row=2, column=0' not in stable:
        raise RuntimeError("Stabilní formulář Návrhu už není v řádku 2.")
    if 'text="Navrhnout a přidat"' not in stable:
        raise RuntimeError("Stabilní UI neobsahuje tlačítko Navrhnout a přidat.")
    if 'card.grid(row=2, column=0' not in buggy:
        raise RuntimeError("Nelze doložit původní překryv alternativ s formulářem.")

    form_row = _literal(FIXED_LAYER, "DESIGN_FORM_ROW")
    table_row = _literal(FIXED_LAYER, "DESIGN_TABLE_ROW")
    alternatives_row = _literal(FIXED_LAYER, "ALTERNATIVES_GRID_ROW")
    if (form_row, table_row, alternatives_row) != (2, 4, 5):
        raise RuntimeError(
            f"Neočekávané řádky Návrhu: formulář={form_row}, tabulka={table_row}, alternativy={alternatives_row}."
        )
    if len({form_row, table_row, alternatives_row}) != 3:
        raise RuntimeError("Formulář, hlavní tabulka a alternativy se znovu překrývají.")

    required_tokens = (
        "_base.build_shear_workspace(owner, parent)",
        "_fix_design_layout(owner)",
        "card.grid_configure(",
        "row=ALTERNATIVES_GRID_ROW",
        "tab.rowconfigure(DESIGN_FORM_ROW, weight=0)",
        "tab.rowconfigure(DESIGN_TABLE_ROW, weight=3)",
        "tab.rowconfigure(ALTERNATIVES_GRID_ROW, weight=2)",
    )
    missing = [token for token in required_tokens if token not in fixed]
    if missing:
        raise RuntimeError("Oprava layoutu 2.2.25 není kompletní: " + ", ".join(missing))

    for token in (
        '"shear_dowels_current_224.py"',
        '"shear_dowels_current.py"',
        '"shear_movement.py"',
    ):
        if token not in installer:
            raise RuntimeError(f"Runtime installer 2.2.25 postrádá {token}.")

    for token in (
        '"shear_dowels_current_224.py"',
        '"shear_dowels_current.py"',
    ):
        if token not in bootstrap:
            raise RuntimeError(f"Bootstrap 2.2.25 nekontroluje {token}.")

    if contract.get("shear_design_form_visible") is not True:
        raise RuntimeError("Release contract nepotvrzuje viditelný formulář Návrhu.")
    if contract.get("shear_design_alternatives_separate_row") is not True:
        raise RuntimeError("Release contract nepotvrzuje oddělený řádek alternativ.")

    current = (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip()
    if current == "2.2.25":
        manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
        if manifest.get("version") != "2.2.25" or str(manifest.get("runtime_layout")) != "18":
            raise RuntimeError("Aktuální manifest neukazuje na 2.2.25 / runtime layout 18.")

    print(
        "OK: ruční Návrh smykových trnů zůstává v řádku 2, "
        "hlavní výsledky v řádku 4 a alternativy v samostatném řádku 5."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
