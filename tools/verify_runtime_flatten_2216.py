from __future__ import annotations

"""Regression checks for TURTO 2.2.16 runtime flattening and incremental delivery."""

import ast
import hashlib
import json
import runpy
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.16"
OBSOLETE = {
    "app_runtime_202.pyw",
    "app_runtime_200.pyw",
    "app_runtime_127.pyw",
    "app_runtime_prev.pyw",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"{path}: chybí literální přiřazení {name}")


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
    return names


def main() -> int:
    required = (
        "app.pyw",
        "app_runtime.pyw",
        "runtime_installer.py",
        "cleanup_stage5.py",
        "RELEASE_NOTES.txt",
        "release_contract.json",
    )
    for name in required:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    runtime = RELEASE / "app_runtime.pyw"
    runtime_text = runtime.read_text(encoding="utf-8")
    runtime_imports = imported_names(runtime)
    assert not ({path[:-4] for path in OBSOLETE} & runtime_imports)
    for token in (
        "import app_central_prev as _central",
        "install_substitution(substitution_workspace.SubstitutionWorkspaceMixin)",
        "import wt_safety_guard",
        "install_platform_workspace(_BASE)",
        "install_schoeck_dorn_decoder(_BASE)",
        "install_shear_movement(_BASE)",
        "install_isokorb_compat(_BASE)",
        "install_substitution_guard(_BASE)",
        'APP_VERSION = "2.2.16"',
    ):
        assert token in runtime_text, token

    installer = RELEASE / "runtime_installer.py"
    installer_text = installer.read_text(encoding="utf-8")
    assert 'RUNTIME_LAYOUT = "9"' in installer_text
    assert 'PREVIOUS_REVISION = ".turto_runtime_2_2_15.ok"' in installer_text
    assert 'PROGRAM_REVISION = ".turto_runtime_2_2_16.ok"' in installer_text
    assert "_ensure_previous_runtime" in installer_text
    assert "_apply_incremental_overlay" in installer_text
    assert "actions.sqlite3 is never modified" in installer_text

    base_hash = literal(installer, "BASE_SHA256")
    assert sha256(ROOT / "updates" / "2.2.15" / "runtime_installer.py") == base_hash
    payloads = literal(installer, "PAYLOADS")
    assert set(payloads) == {"app_runtime.pyw", "cleanup_stage5.py"}
    for _local, (_commit, source, expected) in payloads.items():
        source_path = ROOT / source
        assert source_path.is_file(), source
        assert sha256(source_path) == expected

    app = RELEASE / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    assert literal(app, "INSTALLER_SHA256") == sha256(installer)
    assert 'RUNTIME_LAYOUT = "9"' in app_text
    assert 'PROGRAM_REVISION = PROGRAM / ".turto_runtime_2_2_16.ok"' in app_text
    assert 'CLEANUP_REVISION = ROOT / ".turto_cleanup_2_2_16.ok"' in app_text
    assert "def _cleanup_needed()" in app_text
    assert "from cleanup_stage5 import cleanup_stage5" in app_text
    required_program = set(literal(app, "REQUIRED_PROGRAM_FILES"))
    assert not (OBSOLETE & required_program)
    assert {
        "app_runtime.pyw",
        "app_central_prev.pyw",
        "cleanup_stage5.py",
        "table_polish.py",
        "wt_safety_guard.py",
        "schoeck_dorn_decoder.py",
        "isokorb_compat.py",
        "substitution_guard.py",
    } <= required_program

    contract = json.loads((RELEASE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["manifest_root_only"] is True
    assert contract["runtime_directory"] == "Program"
    assert str(contract["runtime_layout"]) == "9"
    assert "actions.sqlite3" in contract["preserve"]

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    current = tuple(int(part) for part in str(manifest["version"]).split("."))
    assert current >= (2, 2, 16)
    assert int(str(manifest["runtime_layout"])) >= 9
    manifest_paths = {str(item["path"]) for item in manifest["files"]}
    assert manifest_paths == {"app.pyw", "updater.py", "RELEASE_NOTES.txt"}
    assert "actions.sqlite3" not in manifest_paths

    # Exercise the fast path. A valid 2.2.15 Program must receive only the two
    # 2.2.16 overlay payloads; the old full installer must not be downloaded.
    installer_ns = runpy.run_path(str(installer), run_name="verify_installer_2216")
    previous_required = tuple(installer_ns["PREVIOUS_REQUIRED"])
    current_required = tuple(installer_ns["CURRENT_REQUIRED"])
    install_runtime = installer_ns["install_runtime"]
    with tempfile.TemporaryDirectory(prefix="turto_2216_incremental_") as temp_name:
        root = Path(temp_name)
        program = root / "Program"
        program.mkdir()
        database = root / "actions.sqlite3"
        database.write_bytes(b"db-byte-identical")
        before = database.read_bytes()

        for name in previous_required:
            path = program / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 1\n", encoding="utf-8")
        (program / ".turto_runtime_2_2_15.ok").write_text("2.2.15", encoding="utf-8")

        payload_bytes = {
            source: (ROOT / source).read_bytes()
            for _local, (_commit, source, _expected) in payloads.items()
        }
        calls: list[str] = []

        def fake_download(_commit: str, path: str, _expected: str, _agent: str) -> bytes:
            calls.append(path)
            if path == installer_ns["BASE_PATH"]:
                raise AssertionError("Platný 2.2.15 Program nesmí spouštět plnou obnovu.")
            return payload_bytes[path]

        install_runtime.__globals__["_download"] = fake_download
        install_runtime(root)

        assert database.read_bytes() == before
        assert (program / ".turto_runtime_2_2_16.ok").read_text(encoding="utf-8") == "2.2.16"
        assert not (program / ".turto_runtime_2_2_15.ok").exists()
        assert all((program / name).is_file() for name in current_required)
        assert (program / "app_runtime.pyw").read_bytes() == runtime.read_bytes()
        assert (program / "cleanup_stage5.py").read_bytes() == (RELEASE / "cleanup_stage5.py").read_bytes()
        assert installer_ns["BASE_PATH"] not in calls
        assert set(calls) == {source for _local, (_commit, source, _expected) in payloads.items()}

        # Restore the four historical wrappers so stage-5 cleanup can prove that
        # they are now genuinely unreachable from the flattened composition.
        for name in OBSOLETE:
            (program / name).write_text("VALUE = 2215\n", encoding="utf-8")
        (root / "RELEASE_NOTES.txt").write_text("notes\n", encoding="utf-8")

        cleanup_ns = runpy.run_path(str(RELEASE / "cleanup_stage5.py"), run_name="verify_cleanup_2216")
        cleanup_ns["cleanup_stage5"](root, program, root / "Logy", root / "Logy" / "cleanup.log")

        assert database.read_bytes() == before
        assert all(not (program / name).exists() for name in OBSOLETE)
        assert (program / "app_runtime.pyw").is_file()
        archives = list((root / "Zaloha" / "Archiv").glob("Program_legacy_runtime_2.2.16_*.zip"))
        assert len(archives) == 1
        with zipfile.ZipFile(archives[0], "r") as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == OBSOLETE
        assert not (root / "RELEASE_NOTES.txt").exists()
        assert (root / "Dokumentace" / "Interni" / "Vydani" / "TURTO_2.2.16.txt").is_file()

    # Dependency analysis is fail-closed. A syntax-broken unrelated module must
    # prevent wrapper deletion rather than guessing that the wrappers are unused.
    cleanup_ns = runpy.run_path(str(RELEASE / "cleanup_stage5.py"), run_name="verify_cleanup_fail_closed_2216")
    with tempfile.TemporaryDirectory(prefix="turto_2216_fail_closed_") as temp_name:
        program = Path(temp_name) / "Program"
        program.mkdir()
        for name in OBSOLETE:
            (program / name).write_text("VALUE = 1\n", encoding="utf-8")
        (program / "broken.py").write_text("this is not valid python !!!", encoding="utf-8")
        assert cleanup_ns["_safe_obsolete_wrappers"](program) == []

    print(
        "OK: TURTO 2.2.16+ – flattened runtime composition, incremental overlay, "
        "Program-only manifest and safe wrapper cleanup."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
