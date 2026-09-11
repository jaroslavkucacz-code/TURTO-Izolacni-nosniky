from __future__ import annotations

"""Static regression checks for width-safe UI layout introduced in 2.2.26."""

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEAR = ROOT / "updates" / "2.2.26" / "shear_dowels_current.py"
HIT = ROOT / "updates" / "2.2.26" / "hit_workspace.py"
INSTALLER = ROOT / "updates" / "2.2.26" / "runtime_installer.py"
CONTRACT = ROOT / "updates" / "2.2.26" / "release_contract.json"

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    shear = SHEAR.read_text(encoding="utf-8")
    hit = HIT.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    ast.parse(shear, filename=str(SHEAR))
    ast.parse(hit, filename=str(HIT))

    shear_tokens = (
        "def _two_lines(",
        "def _rebuild_decoder_form(",
        "def _rebuild_design_form(",
        "def _rebuild_substitution_form(",
        "def _rebuild_decoder_transfer(",
        "def _rebuild_substitution_toolbar(",
        'text="Navrhnout a přidat"',
        'text="Navrhnout záměnu"',
        'text="Dekódovat a přidat"',
        'text="Převést do Záměn"',
        'owner._turto_substitution_sleeve_combo_224 = sleeve',
        'owner._turto_decoder_transfer_sleeve_combo_224 = sleeve',
    )
    missing = [token for token in shear_tokens if token not in shear]
    if missing:
        raise RuntimeError("Responsive shear UI není kompletní: " + ", ".join(missing))

    hit_tokens = (
        "def _reflow_standard_toolbar(",
        "def _wrap_global_summary(",
        '"Export Excel – desky"',
        '"Uložit návrh"',
        '"Návrhy…"',
        "wraplength=760",
        "row=1",
    )
    missing = [token for token in hit_tokens if token not in hit]
    if missing:
        raise RuntimeError("Responsive HIT UI není kompletní: " + ", ".join(missing))

    for token in (
        '"shear_dowels_current_225.py"',
        '"shear_dowels_current.py"',
        '"hit_workspace_219.py"',
        '"hit_workspace.py"',
    ):
        if token not in installer:
            raise RuntimeError(f"Installer 2.2.26 postrádá runtime soubor {token}.")

    expected_flags = (
        "shear_design_two_line_form",
        "shear_decoder_two_line_form",
        "shear_substitution_two_line_form",
        "hit_toolbar_second_row",
        "right_edge_actions_visible",
    )
    for name in expected_flags:
        if contract.get(name) is not True:
            raise RuntimeError(f"Release contract nepotvrzuje {name}.")

    current = (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip()
    if current == "2.2.26":
        manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
        if manifest.get("version") != "2.2.26" or str(manifest.get("runtime_layout")) != "19":
            raise RuntimeError("Manifest neukazuje na 2.2.26 / runtime layout 19.")

    print(
        "OK: 2.2.26 keeps right-edge actions visible in shear-dowel forms "
        "and reflows dense HIT toolbar actions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
