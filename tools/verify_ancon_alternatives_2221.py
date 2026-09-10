from __future__ import annotations

"""Regression checks for TURTO 2.2.21 Ancon terminology and design alternatives."""

import ast
import hashlib
import json
import runpy
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.21"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"{path}: chybí literální přiřazení {name}")


def exercise_shear_module(path: Path) -> None:
    names = ("shear_ui_227", "shear_catalogs_227")
    saved = {name: sys.modules.get(name) for name in names}

    ui = types.ModuleType("shear_ui_227")
    ui.build_shear_workspace = lambda *_a, **_k: None
    ui.init_shear_workspace = lambda *_a, **_k: None
    ui.install_methods = lambda *_a, **_k: None
    ui.add_design = lambda *_a, **_k: None
    ui.recalculate_design_all = lambda *_a, **_k: None
    ui.refresh = lambda *_a, **_k: None

    catalogs = types.ModuleType("shear_catalogs_227")
    catalogs.design_for_manufacturer = lambda *_a, **_k: ([], "")

    sys.modules["shear_ui_227"] = ui
    sys.modules["shear_catalogs_227"] = catalogs
    try:
        ns = runpy.run_path(str(path), run_name="verify_shear_dowels_2221")
        ns["selftest"]()
        alternatives = ns["_passing_alternatives"](
            [
                {"designation": "Ancon ED 10", "status": "VYHOVUJE"},
                {"designation": "Ancon ED 15", "status": "VYHOVUJE"},
                {"designation": "Ancon ED 18", "status": "KONTROLA DESKY"},
                {"designation": "Ancon ED 20", "status": "VYHOVUJE"},
                {"designation": "Ancon ED 15", "status": "VYHOVUJE"},
            ],
            "Ancon ED 10",
        )
        assert [item["designation"] for item in alternatives] == ["Ancon ED 15", "Ancon ED 20"]
        assert ns["_sleeve_options"]("Ancon", "Podélný posun") == (
            "Nerezové pouzdro (konektor ESD)",
            "Plastové pouzdro (konektor ED)",
        )
        assert ns["_sleeve_options"]("Ancon", "Podélný + příčný posun") == (
            "Pouzdro pro příčný posun (konektor ESDQ)",
        )
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def main() -> int:
    for name in (
        "app.pyw",
        "app_runtime.pyw",
        "runtime_installer.py",
        "shear_dowels_current.py",
        "RELEASE_NOTES.txt",
        "release_contract.json",
    ):
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    shear = RELEASE / "shear_dowels_current.py"
    text = shear.read_text(encoding="utf-8")
    for token in (
        "ED není označení samotného pouzdra",
        "Plastové pouzdro (konektor ED)",
        "Nerezové pouzdro (konektor ESD)",
        "Pouzdro pro příčný posun (konektor ESDQ)",
        "Další vyhovující alternativy",
        'status != "VYHOVUJE"',
        "design_for_manufacturer(",
    ):
        assert token in text, token
    assert "serialize_shear_dowels =" not in text
    exercise_shear_module(shear)

    # The verified Ancon engine already maps plastic axial sleeves to the ED
    # connector.  2.2.21 changes wording/presentation, not source capacities.
    legacy = ROOT / "updates" / "2.1.0" / "shear_dowels_catalog.py"
    legacy_text = legacy.read_text(encoding="utf-8")
    assert '("ED" if low_sleeve == "plastic" else "ESD")' in legacy_text
    assert 'prefix = "ESDQ" if q else' in legacy_text

    installer = RELEASE / "runtime_installer.py"
    assert literal(installer, "BASE_COMMIT") == "ea32f509b221a63e55478618690ea3d6ad438bca"
    assert literal(installer, "BASE_PATH") == "updates/2.2.20/runtime_installer.py"
    assert sha256(ROOT / "updates" / "2.2.20" / "runtime_installer.py") == literal(installer, "BASE_SHA256")
    assert literal(installer, "RUNTIME_LAYOUT") == "14"
    assert literal(installer, "PREVIOUS_REVISION") == ".turto_runtime_2_2_20.ok"
    assert literal(installer, "PROGRAM_REVISION") == ".turto_runtime_2_2_21.ok"

    payloads = literal(installer, "PAYLOADS")
    assert set(payloads) == {"app_runtime.pyw", "shear_dowels_current.py"}
    for local, (_commit, source, expected) in payloads.items():
        actual = sha256(ROOT / source)
        if actual != expected:
            raise RuntimeError(f"PAYLOAD {local}: očekáváno {expected}, skutečně {actual}")

    app = RELEASE / "app.pyw"
    assert literal(app, "VERSION") == "2.2.21"
    assert literal(app, "RUNTIME_LAYOUT") == "14"
    assert literal(app, "INSTALLER_SHA256") == sha256(installer)
    assert set(literal(app, "REQUIRED_PROGRAM_FILES")) == set(literal(installer, "CURRENT_REQUIRED"))

    # Healthy 2.2.20 installation must use only the two-file overlay and keep
    # the action database byte-identical.
    ns = runpy.run_path(str(installer), run_name="verify_installer_2221")
    payload_bytes = {
        source: (ROOT / source).read_bytes()
        for _local, (_commit, source, _expected) in payloads.items()
    }
    with tempfile.TemporaryDirectory(prefix="turto_2221_fast_") as temp_name:
        root = Path(temp_name)
        program = root / "Program"
        program.mkdir()
        database = root / "actions.sqlite3"
        database.write_bytes(b"actions-db-byte-identical-2221")
        before = database.read_bytes()

        for name in ns["PREVIOUS_REQUIRED"]:
            path = program / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 2220\n", encoding="utf-8")
        (program / ".turto_runtime_2_2_20.ok").write_text("2.2.20", encoding="utf-8")

        calls: list[str] = []

        def fake_download(_commit: str, path: str, _expected: str, _agent: str) -> bytes:
            calls.append(path)
            if path == ns["BASE_PATH"]:
                raise AssertionError("Kompletní 2.2.20 Program nesmí spustit plnou obnovu.")
            return payload_bytes[path]

        ns["install_runtime"].__globals__["_download"] = fake_download
        ns["install_runtime"](root)

        assert database.read_bytes() == before
        assert (program / ".turto_runtime_2_2_21.ok").read_text(encoding="utf-8") == "2.2.21"
        assert not (program / ".turto_runtime_2_2_20.ok").exists()
        assert set(calls) == {value[1] for value in payloads.values()}
        assert (program / "shear_dowels_current.py").read_bytes() == shear.read_bytes()

    contract = json.loads((RELEASE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["version"] == "2.2.21"
    assert str(contract["runtime_layout"]) == "14"
    assert contract["manifest_root_only"] is True
    assert contract["shear_alternatives_persisted"] is False
    assert contract["ancon_ed_is_complete_connector"] is True
    assert "actions.sqlite3" in contract["preserve"]

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    current = (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip()
    if current == "2.2.21":
        assert manifest["version"] == "2.2.21"
        assert str(manifest["runtime_layout"]) == "14"
        assert {item["path"] for item in manifest["files"]} == {"app.pyw", "updater.py", "RELEASE_NOTES.txt"}

    print(
        "OK: TURTO 2.2.21 – Ancon ED terminology, explicit ESD/ED/ESDQ sleeve choices, "
        "passing alternatives and byte-identical actions.sqlite3."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
