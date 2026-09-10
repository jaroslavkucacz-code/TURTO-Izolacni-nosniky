from __future__ import annotations

"""Regression checks for TURTO 2.2.20 central-runtime flattening."""

import ast
import hashlib
import json
import runpy
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.20"
LEGACY_CENTRAL = ROOT / "updates" / "1.1.23" / "app.pyw"


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
        "cleanup_stage8.py",
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
    assert "app_base" in runtime_imports
    assert "app_central_prev" not in runtime_imports
    assert 'APP_VERSION = "2.2.20"' in runtime_text

    for token in (
        "CombinedCatalogDatabase",
        "install_actions(",
        'self.main_notebook.add(self.project_tab, text="Dekodér ISO")',
        'self.main_notebook.add(self.hit_tab, text="Návrh HIT")',
        'self.main_notebook.add(self.substitution_tab, text="Záměny za HIT")',
        'self.project.name = "Nová akce"',
        "confirm_action_close",
        'widget.configure(text="Hromadné dekódování z výkazu")',
        '"Uložte projekt", "Uložte AKCI"',
        "install_platform_workspace(_base)",
        "install_schoeck_dorn_decoder(_base)",
        "install_shear_movement(_base)",
        "install_isokorb_compat(_base)",
        "install_substitution_guard(_base)",
    ):
        assert token in runtime_text, token

    legacy_text = LEGACY_CENTRAL.read_text(encoding="utf-8")
    for legacy_token in (
        "build_action_bar",
        "install_actions",
        "CombinedCatalogDatabase",
        "_build_body",
        "_populate_initial_data",
        "_restore_selections",
        "refresh_project_concrete_filter",
        "confirm_substitution_choice",
    ):
        assert legacy_token in legacy_text
        assert legacy_token in runtime_text

    installer = RELEASE / "runtime_installer.py"
    installer_text = installer.read_text(encoding="utf-8")
    for token in (
        'RUNTIME_LAYOUT = "13"',
        'PREVIOUS_REVISION = ".turto_runtime_2_2_19.ok"',
        'BASE_REVISION = ".turto_runtime_2_2_16.ok"',
        'PROGRAM_REVISION = ".turto_runtime_2_2_20.ok"',
        "CENTRAL_SUPPORT_REQUIRED",
        "_ensure_baseline",
        "_apply_incremental_overlay",
        "actions.sqlite3 is never modified",
    ):
        assert token in installer_text, token

    assert sha256(ROOT / "updates" / "2.2.16" / "runtime_installer.py") == literal(
        installer, "BASE_SHA256"
    )

    payloads = literal(installer, "PAYLOADS")
    assert set(payloads) == {"app_runtime.pyw", "hit_workspace.py", "cleanup_stage8.py"}
    for local, (_commit, source, expected) in payloads.items():
        source_path = ROOT / source
        assert source_path.is_file(), source
        actual = sha256(source_path)
        if actual != expected:
            raise RuntimeError(f"PAYLOAD {local}: očekáváno {expected}, skutečně {actual}")

    previous_required = set(literal(installer, "PREVIOUS_REQUIRED"))
    current_required = set(literal(installer, "CURRENT_REQUIRED"))
    support_required = set(literal(installer, "CENTRAL_SUPPORT_REQUIRED"))
    base_required = set(literal(installer, "BASE_REQUIRED"))
    assert "app_central_prev.pyw" in previous_required
    assert "app_central_prev.pyw" not in current_required
    assert "cleanup_stage7.py" in previous_required
    assert "cleanup_stage7.py" not in current_required
    assert "cleanup_stage8.py" in current_required
    assert {
        "project_ui.py",
        "action_workspace.py",
        "action_payload.py",
        "action_store.py",
        "platform_registry.py",
        "platform_state.py",
        "bulk_import.py",
        "hit_decoder_catalog.py",
    } <= support_required
    assert support_required <= base_required

    legacy_files = set(literal(ROOT / "updates" / "2.1.0" / "runtime_installer.py", "FILES"))
    assert support_required <= legacy_files

    app = RELEASE / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    assert literal(app, "INSTALLER_SHA256") == sha256(installer)
    assert 'RUNTIME_LAYOUT = "13"' in app_text
    assert 'PROGRAM_REVISION = PROGRAM / ".turto_runtime_2_2_20.ok"' in app_text
    assert 'CLEANUP_REVISION = ROOT / ".turto_cleanup_2_2_20.ok"' in app_text
    assert "from cleanup_stage8 import cleanup_stage8" in app_text
    assert "app_central_prev.pyw" not in set(literal(app, "REQUIRED_PROGRAM_FILES"))

    ns = runpy.run_path(str(installer), run_name="verify_installer_2220")
    install_runtime = ns["install_runtime"]
    payload_bytes = {
        source: (ROOT / source).read_bytes()
        for _local, (_commit, source, _expected) in payloads.items()
    }
    with tempfile.TemporaryDirectory(prefix="turto_2220_incremental_") as temp_name:
        root = Path(temp_name)
        program = root / "Program"
        program.mkdir()
        database = root / "actions.sqlite3"
        database.write_bytes(b"actions-db-byte-identical-2220")
        before = database.read_bytes()

        for name in ns["PREVIOUS_REQUIRED"]:
            path = program / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 2219\n", encoding="utf-8")
        (program / ".turto_runtime_2_2_19.ok").write_text("2.2.19", encoding="utf-8")

        calls: list[str] = []

        def fake_download(_commit: str, path: str, _expected: str, _agent: str) -> bytes:
            calls.append(path)
            if path == ns["BASE_PATH"]:
                raise AssertionError("Kompletní 2.2.19 Program nesmí spustit plnou obnovu.")
            return payload_bytes[path]

        install_runtime.__globals__["_download"] = fake_download
        install_runtime(root)

        assert database.read_bytes() == before
        assert (program / ".turto_runtime_2_2_20.ok").read_text(encoding="utf-8") == "2.2.20"
        assert not (program / ".turto_runtime_2_2_19.ok").exists()
        assert all((program / name).is_file() for name in ns["CURRENT_REQUIRED"])
        assert (program / "app_runtime.pyw").read_bytes() == runtime.read_bytes()
        assert ns["BASE_PATH"] not in calls
        assert set(calls) == {value[1] for value in payloads.values()}

        (program / "app_central_prev.pyw").write_text("VALUE = 1123\n", encoding="utf-8")
        (program / "cleanup_stage7.py").write_text("VALUE = 2219\n", encoding="utf-8")
        (root / "RELEASE_NOTES.txt").write_text("2.2.20 notes\n", encoding="utf-8")
        cleanup_ns = runpy.run_path(
            str(RELEASE / "cleanup_stage8.py"), run_name="verify_cleanup_2220"
        )
        cleanup_ns["cleanup_stage8"](
            root, program, root / "Logy", root / "Logy" / "cleanup.log"
        )

        assert database.read_bytes() == before
        assert not (program / "app_central_prev.pyw").exists()
        assert not (program / "cleanup_stage7.py").exists()
        for name in ("app_base.py", "action_workspace.py", "platform_workspace.py", "project_ui.py"):
            assert (program / name).is_file(), name
        archives = list(
            (root / "Zaloha" / "Archiv").glob("Program_legacy_layers_2.2.20_*.zip")
        )
        assert len(archives) == 1
        with zipfile.ZipFile(archives[0], "r") as archive:
            assert archive.testzip() is None
            names = set(archive.namelist())
            assert "app_central_prev.pyw" in names
            assert "cleanup_stage7.py" in names
            assert "app_base.py" not in names
            assert "action_workspace.py" not in names
        assert not (root / "RELEASE_NOTES.txt").exists()
        assert (
            root / "Dokumentace" / "Interni" / "Vydani" / "TURTO_2.2.20.txt"
        ).is_file()

    cleanup_ns = runpy.run_path(
        str(RELEASE / "cleanup_stage8.py"), run_name="verify_cleanup_fail_closed_2220"
    )
    with tempfile.TemporaryDirectory(prefix="turto_2220_fail_closed_") as temp_name:
        program = Path(temp_name) / "Program"
        program.mkdir()
        (program / "app_central_prev.pyw").write_text("VALUE = 1\n", encoding="utf-8")
        (program / "broken.py").write_text("not valid python !!!", encoding="utf-8")
        assert cleanup_ns["_safe_obsolete_files"](program) == []

    contract = json.loads((RELEASE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["version"] == "2.2.20"
    assert str(contract["runtime_layout"]) == "13"
    assert contract["central_wrapper_flattened"] is True
    assert contract["pinned_runtime_sources_verified"] is True
    assert "actions.sqlite3" in contract["preserve"]

    print(
        "OK: TURTO 2.2.20 – central AKCE wrapper flattened, support dependencies explicit, "
        "incremental delivery safe and actions.sqlite3 byte-identical."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
