from __future__ import annotations

"""Regression checks for one-way / two-way shear-dowel handling."""

import ast
import hashlib
import json
import runpy
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assignment_literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"{path}: chybí literální přiřazení {name}")


def _source_from_manifest_item(item: dict) -> Path:
    parsed = urlparse(str(item.get("url", "")))
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 4:
        raise RuntimeError(f"Neplatná release URL: {item.get('url', '')}")
    return ROOT / "/".join(parts[3:])


def main() -> int:
    version = (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip()
    release = ROOT / "updates" / version
    installer_path = release / "runtime_installer.py"
    if not installer_path.is_file():
        raise RuntimeError(f"Chybí {installer_path.relative_to(ROOT)}")

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    manifest_items = {str(item["path"]): item for item in manifest["files"]}
    movement_item = manifest_items.get("shear_movement.py")
    if not isinstance(movement_item, dict):
        raise RuntimeError("Manifest neobsahuje shear_movement.py")
    movement_path = _source_from_manifest_item(movement_item)
    if not movement_path.is_file():
        raise RuntimeError(f"Chybí zdroj movement modulu: {movement_path.relative_to(ROOT)}")
    if _sha256(movement_path) != str(movement_item.get("sha256", "")):
        raise RuntimeError("SHA-256 shear_movement.py neodpovídá manifestu.")

    module = runpy.run_path(str(movement_path), run_name="turto_shear_movement_test")
    module["selftest"]()

    assert module["normalize_movement"]("Jednosměrný") == "axial"
    assert module["normalize_movement"]("Obousměrný") == "transverse"
    assert module["explicit_q_variant"]("SLD 40 Q") == ("SLD", "40")
    assert module["explicit_q_variant"]("SLD Q 40") == ("SLD", "40")
    assert module["explicit_q_variant"]("SLD-Q 40") == ("SLD", "40")
    assert module["explicit_q_variant"]("LD 20 Q") == ("LD", "20")
    assert module["explicit_q_variant"]("HLD 22 Q") == ("HLD", "22")
    assert module["validate_ancon_application"]("existing_wall", "transverse")
    assert not module["validate_ancon_application"]("existing_wall", "axial")

    payloads = _assignment_literal(installer_path, "PAYLOADS")
    for local, (commit, source, expected) in payloads.items():
        source_path = ROOT / source
        if not source_path.is_file():
            raise RuntimeError(f"Runtime payload chybí v repozitáři: {source}")
        actual = _sha256(source_path)
        if actual != expected:
            raise RuntimeError(
                f"Runtime installer: SHA-256 nesouhlasí pro {local}: "
                f"očekáváno {expected}, skutečně {actual}"
            )
        item = manifest_items.get(local)
        if item is not None:
            expected_url = (
                "https://raw.githubusercontent.com/"
                "jaroslavkucacz-code/TURTO-Izolacni-nosniky/"
                f"{commit}/{source}"
            )
            if item["url"] != expected_url or item["sha256"] != expected:
                raise RuntimeError(
                    f"Runtime installer a manifest se rozcházejí pro {local}."
                )

    print(
        f"OK: TURTO {version} – pohyb smykových trnů, historické Q zápisy, "
        "E-HLD ochrana a runtime payloady."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
