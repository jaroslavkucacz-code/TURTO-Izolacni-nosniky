from __future__ import annotations

"""Regression check for TURTO 2.2.14 Program/runtime_paths startup hotfix."""

import ast
import hashlib
import json
import runpy
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.14"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"{path}: chybí literální přiřazení {name}")


def main() -> int:
    app = RELEASE / "app.pyw"
    runtime = RELEASE / "app_runtime.pyw"
    installer = RELEASE / "runtime_installer.py"
    notes = RELEASE / "RELEASE_NOTES.txt"
    for path in (app, runtime, installer, notes):
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    app_text = app.read_text(encoding="utf-8")
    for token in (
        'VERSION = "2.2.14"',
        'RUNTIME_LAYOUT = "7"',
        'PROGRAM_REVISION = PROGRAM / ".turto_runtime_2_2_14.ok"',
        "def _activate_program_imports()",
        "sys.path_importer_cache.pop(program_text, None)",
        "importlib.invalidate_caches()",
        'spec_from_file_location("runtime_paths", runtime_paths_file)',
        'sys.modules["runtime_paths"] = module',
        "_activate_program_imports()",
    ):
        assert token in app_text, token

    installer_text = installer.read_text(encoding="utf-8")
    assert 'PROGRAM_REVISION = ".turto_runtime_2_2_14.ok"' in installer_text
    assert '(program / PROGRAM_REVISION).write_text("2.2.14"' in installer_text
    assert "actions.sqlite3 is never modified" in installer_text

    base_hash = literal(installer, "BASE_SHA256")
    assert sha256(ROOT / "updates" / "2.2.13" / "runtime_installer.py") == base_hash
    payloads = literal(installer, "PAYLOADS")
    assert set(payloads) == {"app_runtime.pyw"}
    for _local, (_commit, source, expected) in payloads.items():
        source_path = ROOT / source
        assert source_path.is_file(), source
        assert sha256(source_path) == expected

    installer_hash = literal(app, "INSTALLER_SHA256")
    assert sha256(installer) == installer_hash

    # Reproduce the risky condition from 2.2.13: Program path may have a stale
    # negative importer-cache entry after the directory was replaced/created.
    namespace = runpy.run_path(str(app), run_name="verify_runtime_import_2214")
    activate = namespace["_activate_program_imports"]
    previous_runtime_paths = sys.modules.pop("runtime_paths", None)
    previous_path = list(sys.path)
    try:
        with tempfile.TemporaryDirectory(prefix="turto_2214_") as temp:
            program = Path(temp) / "Překlápěcí tabulky" / "Program"
            program.mkdir(parents=True)
            module_file = program / "runtime_paths.py"
            module_file.write_text("VALUE = 2214\n", encoding="utf-8")

            # runpy returns a copy of the globals mapping. Update the function's
            # real globals so the test exercises the exact activation code.
            activate.__globals__["PROGRAM"] = program
            program_text = str(program)
            sys.path_importer_cache[program_text] = None
            activate()

            loaded = sys.modules.get("runtime_paths")
            assert loaded is not None
            assert getattr(loaded, "VALUE", None) == 2214
            assert Path(str(getattr(loaded, "__file__", ""))).resolve() == module_file.resolve()
            assert sys.path[0] == program_text
            assert sys.path_importer_cache.get(program_text) is not None or program_text not in sys.path_importer_cache
    finally:
        sys.path[:] = previous_path
        sys.modules.pop("runtime_paths", None)
        if previous_runtime_paths is not None:
            sys.modules["runtime_paths"] = previous_runtime_paths

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2.2.14"
    assert str(manifest["runtime_layout"]) == "7"
    assert all(item["path"] != "actions.sqlite3" for item in manifest["files"])

    print("OK: TURTO 2.2.14 – runtime_paths import hotfix and stale-cache regression.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
