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
LEGACY_MOVEMENT_SOURCE = ROOT / "updates" / "2.2.2" / "shear_movement.py"
LEGACY_MOVEMENT_SHA256 = "fbe257543cf6ce6ffb901c8378d2c9ebaaa71fedbeef717b2fcf20d0597caa6d"

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
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    # Newer installers may compose tuples using starred literal
                    # groups. They are declarative modules, so evaluating their
                    # top level via runpy is safe and avoids weakening the test.
                    namespace = runpy.run_path(str(path), run_name="verify_installer_assignments")
                    if name in namespace:
                        return namespace[name]
                    break
    raise RuntimeError(f"{path}: chybí přiřazení {name}")


def _source_from_manifest_item(item: dict) -> Path:
    parsed = urlparse(str(item.get("url", "")))
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 4:
        raise RuntimeError(f"Neplatná release URL: {item.get('url', '')}")
    return ROOT / "/".join(parts[3:])


def _inherited_required(installer_path: Path) -> tuple[str, ...]:
    """Resolve required runtime files through incremental overlay installers."""
    seen: set[Path] = set()
    current = installer_path.resolve()
    while True:
        if current in seen:
            raise RuntimeError("Cyklický BASE_PATH v řetězci runtime installerů.")
        seen.add(current)
        try:
            required = _assignment_literal(current, "CURRENT_REQUIRED")
            return tuple(required)
        except RuntimeError:
            try:
                base_path = str(_assignment_literal(current, "BASE_PATH"))
            except RuntimeError as exc:
                raise RuntimeError(
                    f"Installer {current.relative_to(ROOT)} nemá CURRENT_REQUIRED ani BASE_PATH."
                ) from exc
            current = (ROOT / base_path).resolve()
            if not current.is_file():
                raise RuntimeError(f"Chybí BASE installer: {current.relative_to(ROOT)}")


def _movement_source(release: Path, manifest_items: dict[str, dict], installer_path: Path) -> Path:
    movement_item = manifest_items.get("shear_movement.py")
    if isinstance(movement_item, dict):
        movement_path = _source_from_manifest_item(movement_item)
        if not movement_path.is_file():
            raise RuntimeError(f"Chybí zdroj movement modulu: {movement_path.relative_to(ROOT)}")
        if _sha256(movement_path) != str(movement_item.get("sha256", "")):
            raise RuntimeError("SHA-256 shear_movement.py neodpovídá manifestu.")
        return movement_path

    # Since 2.2.16 runtime modules are intentionally no longer copied to the
    # installation root. Incremental overlays may inherit CURRENT_REQUIRED from
    # their BASE installer, so follow BASE_PATH until the verified requirement
    # list is found.
    contract_path = release / "release_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.is_file() else {}
    if contract.get("manifest_root_only") is not True:
        raise RuntimeError("Manifest neobsahuje shear_movement.py a release není Program-only.")
    current_required = _inherited_required(installer_path)
    if "shear_movement.py" not in current_required:
        raise RuntimeError("Program-only runtime installer nevyžaduje shear_movement.py ani v BASE řetězci.")
    if not LEGACY_MOVEMENT_SOURCE.is_file():
        raise RuntimeError("Chybí ověřený zdroj shear_movement.py z 2.2.2.")
    if _sha256(LEGACY_MOVEMENT_SOURCE) != LEGACY_MOVEMENT_SHA256:
        raise RuntimeError("Ověřený zdroj shear_movement.py z 2.2.2 má jiný SHA-256.")
    return LEGACY_MOVEMENT_SOURCE


def main() -> int:
    version = (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip()
    release = ROOT / "updates" / version
    installer_path = release / "runtime_installer.py"
    if not installer_path.is_file():
        raise RuntimeError(f"Chybí {installer_path.relative_to(ROOT)}")

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    manifest_items = {str(item["path"]): item for item in manifest["files"]}
    movement_path = _movement_source(release, manifest_items, installer_path)

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
