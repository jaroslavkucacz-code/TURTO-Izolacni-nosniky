from __future__ import annotations

"""Regression checks for TURTO 2.2.13 Program installation layout."""

import ast
import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.13"


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
    required = (
        "app.pyw",
        "app_runtime.pyw",
        "runtime_installer.py",
        "runtime_paths.py",
        "updater.py",
        "catalog_browser.py",
        "cleanup_stage3.py",
        "RELEASE_NOTES.txt",
        "release_contract.json",
    )
    for name in required:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    bootstrap = (RELEASE / "app.pyw").read_text(encoding="utf-8")
    installer = (RELEASE / "runtime_installer.py").read_text(encoding="utf-8")
    runtime = (RELEASE / "app_runtime.pyw").read_text(encoding="utf-8")
    paths = (RELEASE / "runtime_paths.py").read_text(encoding="utf-8")
    proxy = (RELEASE / "updater.py").read_text(encoding="utf-8")
    catalog = (RELEASE / "catalog_browser.py").read_text(encoding="utf-8")
    cleanup = (RELEASE / "cleanup_stage3.py").read_text(encoding="utf-8")

    for token in (
        'PROGRAM = ROOT / "Program"',
        'RUNTIME_LAYOUT = "6"',
        'runpy.run_path(str(PROGRAM / "app_runtime.pyw")',
        '"app_runtime_202.pyw"',
        '"app_base.py"',
        '"catalog_browser_2210.py"',
    ):
        assert token in bootstrap, token

    for token in (
        'RUNTIME_LAYOUT = "6"',
        'program = root / "Program"',
        "install(staging)",
        'staging / "catalog_browser_2210.py"',
        'root / "Zaloha"',
        "actions.sqlite3 is never modified",
        "PROGRAM_ONLY_PAYLOADS",
    ):
        assert token in installer, token

    base_sha = literal(RELEASE / "runtime_installer.py", "BASE_SHA256")
    assert sha256(ROOT / "updates" / "2.2.12" / "runtime_installer.py") == base_sha

    payloads = literal(RELEASE / "runtime_installer.py", "PAYLOADS")
    program_only = literal(RELEASE / "runtime_installer.py", "PROGRAM_ONLY_PAYLOADS")
    assert {
        "runtime_paths.py", "catalog_browser.py", "cleanup_stage3.py", "app_runtime.pyw",
    } <= set(payloads)
    assert set(program_only) == {"updater.py"}
    for local, (_commit, source, expected) in {**payloads, **program_only}.items():
        source_path = ROOT / source
        assert source_path.is_file(), source
        assert sha256(source_path) == expected, local

    installer_sha = literal(RELEASE / "app.pyw", "INSTALLER_SHA256")
    assert sha256(RELEASE / "runtime_installer.py") == installer_sha

    assert 'ENV_INSTALL_ROOT = "TURTO_ROOT"' in paths
    assert 'return install_root() / "Program"' in paths
    assert 'return install_root() / "Katalogy"' in paths
    assert '_ROOT_UPDATER = install_root() / "updater.py"' in proxy
    assert "_base.CATALOG_ROOT = CATALOG_ROOT" in catalog
    assert "_BASE.app_root = _root_aware_app_root" in runtime
    assert "_BASE.choose_data_directory = _root_aware_choose_data_directory" in runtime

    for protected in ('"app.pyw"', '"updater.py"', '"actions.sqlite3"'):
        assert protected in cleanup
    assert 'replacement = program / source.name' in cleanup

    # Real cleanup simulation: duplicated runtime is archived; root control/data files remain.
    module = runpy.run_path(str(RELEASE / "cleanup_stage3.py"), run_name="verify_cleanup_2213")
    with tempfile.TemporaryDirectory(prefix="turto_2213_cleanup_") as temp:
        root = Path(temp)
        program = root / "Program"
        program.mkdir()
        required_program = ("app_runtime.pyw", "runtime_paths.py")
        for name in required_program:
            (program / name).write_text("program", encoding="utf-8")
        (root / "app_runtime.pyw").write_text("old runtime", encoding="utf-8")
        (root / "runtime_paths.py").write_text("old paths", encoding="utf-8")
        (root / "app.pyw").write_text("bootstrap", encoding="utf-8")
        (root / "updater.py").write_text("updater", encoding="utf-8")
        database = root / "actions.sqlite3"
        database.write_bytes(b"do-not-touch")
        before = database.read_bytes()
        log_dir = root / "Logy"
        module["cleanup_stage3"](
            root,
            program,
            required_program,
            log_dir,
            log_dir / "cleanup.log",
        )
        assert (root / "app.pyw").is_file()
        assert (root / "updater.py").is_file()
        assert database.read_bytes() == before
        assert not (root / "app_runtime.pyw").exists()
        assert not (root / "runtime_paths.py").exists()
        archive = root / "Archiv" / "Runtime_pred_2.2.13"
        assert (archive / "app_runtime.pyw").is_file()
        assert (archive / "runtime_paths.py").is_file()

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    current = tuple(int(part) for part in str(manifest["version"]).split("."))
    assert current >= (2, 2, 13)
    assert int(str(manifest["runtime_layout"])) >= 6
    assert all(item["path"] != "actions.sqlite3" for item in manifest["files"])

    print("OK: TURTO Program layout – staged migration, root cleanup and data protection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
