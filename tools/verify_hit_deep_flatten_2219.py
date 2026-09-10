from __future__ import annotations

"""Regression checks for TURTO 2.2.19 deep HIT flattening and post-run cleanup."""

import ast
import hashlib
import json
import runpy
import sys
import tempfile
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.19"

OBSOLETE = {
    "app_runtime_202.pyw",
    "app_runtime_200.pyw",
    "app_runtime_127.pyw",
    "app_runtime_prev.pyw",
    "hit_workspace_201.py",
    "hit_workspace_200.py",
    "hit_workspace_127.py",
    "hit_workspace_125.py",
    "hit_workspace_prev.py",
    "cleanup_stage3.py",
    "cleanup_stage4.py",
    "cleanup_stage5.py",
    "cleanup_stage6.py",
}

DIRECT_HELPERS = {
    "hit_row_extension",
    "hit_virtual_scroll",
    "hit_design_ui",
    "hit_export_ui",
    "hit_wt_ui",
    "hit_aux_ui",
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


def _exercise_direct_import(hit_path: Path) -> None:
    module_names = [
        "hit_workspace_base",
        "hit_row_extension",
        "hit_virtual_scroll",
        "hit_design_ui",
        "hit_export_ui",
        "hit_wt_ui",
        "hit_aux_ui",
        "unified_schedule",
        "supplier_export",
    ]
    saved = {name: sys.modules.get(name) for name in module_names}

    base = types.ModuleType("hit_workspace_base")

    class HitInputRow:
        def __init__(self, *_args, **_kwargs) -> None:
            self.widgets = []
            self._hit_base_widgets = []

        def regrid(self, *_args, **_kwargs) -> None:
            pass

    class HitWorkspaceMixin:
        def _build_hit_tab(self, *_args, **_kwargs) -> None:
            pass

        def add_hit_row(self) -> None:
            pass

        def remove_hit_row(self, *_args, **_kwargs) -> None:
            pass

        def _init_hit_workspace(self) -> None:
            pass

        def _on_hit_canvas_configure(self, *_args, **_kwargs) -> None:
            pass

    base.HitInputRow = HitInputRow
    base.HitWorkspaceMixin = HitWorkspaceMixin
    base.HIT_MODULE_VERSION = "base"
    base.__all__ = ["HitInputRow", "HitWorkspaceMixin"]

    def install_noop(_module) -> None:
        return None

    row = types.ModuleType("hit_row_extension")
    row.install = install_noop
    scroll = types.ModuleType("hit_virtual_scroll")
    scroll.install = install_noop

    design = types.ModuleType("hit_design_ui")

    def install_design(module) -> None:
        module.HitWorkspaceMixin.save_hit_design = lambda self, *a, **k: None
        module.HitWorkspaceMixin.open_hit_design_browser = lambda self, *a, **k: None

    design.install = install_design

    export = types.ModuleType("hit_export_ui")

    def install_export(module) -> None:
        module.HitWorkspaceMixin.export_hit_pdf = lambda self, *a, **k: None
        module.HitWorkspaceMixin.export_hit_excel = lambda self, *a, **k: None

    export.install = install_export

    wt = types.ModuleType("hit_wt_ui")

    def install_wt(module) -> None:
        module.HitWorkspaceMixin._build_wt_tab = lambda self, *a, **k: None

    wt.install = install_wt

    aux = types.ModuleType("hit_aux_ui")
    aux.AUX_TYPES = ("HT", "AT", "FT", "OTX")

    def install_aux(module) -> None:
        module.HitWorkspaceMixin._build_aux_tab = lambda self, *a, **k: None
        module.HitWorkspaceMixin.add_aux_row_for_type = lambda self, *a, **k: None

    aux.install = install_aux

    unified = types.ModuleType("unified_schedule")
    unified.open_unified_schedule = lambda *_a, **_k: None
    supplier = types.ModuleType("supplier_export")
    supplier.export_supplier_excel = lambda *_a, **_k: None

    replacements = {
        "hit_workspace_base": base,
        "hit_row_extension": row,
        "hit_virtual_scroll": scroll,
        "hit_design_ui": design,
        "hit_export_ui": export,
        "hit_wt_ui": wt,
        "hit_aux_ui": aux,
        "unified_schedule": unified,
        "supplier_export": supplier,
    }

    sys.modules.update(replacements)
    try:
        namespace = runpy.run_path(str(hit_path), run_name="verify_hit_workspace_2219")
        namespace["selftest"]()
        assert namespace["HitInputRow"] is HitInputRow
        assert namespace["HitWorkspaceMixin"] is HitWorkspaceMixin
        assert HitWorkspaceMixin._build_hit_tab is namespace["_build_final"]
        assert HitWorkspaceMixin.clear_hit_rows is namespace["_clear_hit_rows"]
        assert HitWorkspaceMixin.add_aux_row is namespace["_add_aux_row"]
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
        "hit_workspace.py",
        "runtime_installer.py",
        "cleanup_stage7.py",
        "RELEASE_NOTES.txt",
        "release_contract.json",
    ):
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    hit = RELEASE / "hit_workspace.py"
    hit_text = hit.read_text(encoding="utf-8")
    hit_imports = imported_names(hit)
    assert "hit_workspace_base" in hit_imports
    assert DIRECT_HELPERS <= hit_imports
    assert "hit_workspace_125" not in hit_imports
    assert "hit_workspace_prev" not in hit_imports
    for token in (
        'HIT_MODULE_VERSION = "2.2.19"',
        "_install_rows(_base)",
        "_install_scroll(_base)",
        "_install_design(_base)",
        "_install_export(_base)",
        "_install_wt(_base)",
        "_install_aux(_base)",
        "_base.HitWorkspaceMixin._build_hit_tab = _build_final",
    ):
        assert token in hit_text, token
    assert hit_text.index("_install_rows(_base)") < hit_text.index("_install_scroll(_base)")
    assert hit_text.index("_install_scroll(_base)") < hit_text.index("_install_design(_base)")
    assert hit_text.index("_install_design(_base)") < hit_text.index("_install_export(_base)")
    assert hit_text.index("_install_export(_base)") < hit_text.index("_install_wt(_base)")
    assert hit_text.index("_install_wt(_base)") < hit_text.index("_install_aux(_base)")
    _exercise_direct_import(hit)

    runtime = RELEASE / "app_runtime.pyw"
    assert 'APP_VERSION = "2.2.19"' in runtime.read_text(encoding="utf-8")

    installer = RELEASE / "runtime_installer.py"
    installer_text = installer.read_text(encoding="utf-8")
    for token in (
        'RUNTIME_LAYOUT = "12"',
        'PREVIOUS_REVISION = ".turto_runtime_2_2_18.ok"',
        'BASE_REVISION = ".turto_runtime_2_2_16.ok"',
        'PROGRAM_REVISION = ".turto_runtime_2_2_19.ok"',
        "_ensure_baseline",
        "_apply_incremental_overlay",
        "actions.sqlite3 is never modified",
    ):
        assert token in installer_text, token

    assert sha256(ROOT / "updates" / "2.2.16" / "runtime_installer.py") == literal(
        installer, "BASE_SHA256"
    )
    payloads = literal(installer, "PAYLOADS")
    assert set(payloads) == {"app_runtime.pyw", "hit_workspace.py", "cleanup_stage7.py"}
    for local, (_commit, source, expected) in payloads.items():
        actual = sha256(ROOT / source)
        if actual != expected:
            raise RuntimeError(f"PAYLOAD {local}: očekáváno {expected}, skutečně {actual}")

    previous_required = set(literal(installer, "PREVIOUS_REQUIRED"))
    current_required = set(literal(installer, "CURRENT_REQUIRED"))
    for helper in (
        "hit_row_extension.py",
        "hit_virtual_scroll.py",
        "hit_design_ui.py",
        "hit_export_ui.py",
    ):
        assert helper in previous_required
        assert helper in current_required
    assert "hit_workspace_base.py" in current_required
    assert "hit_workspace_125.py" not in current_required
    assert "hit_workspace_prev.py" not in current_required
    for old_cleanup in ("cleanup_stage3.py", "cleanup_stage4.py", "cleanup_stage5.py"):
        assert old_cleanup not in current_required
    assert "cleanup_stage7.py" in current_required

    # Healthy 2.2.18 -> fast three-file overlay, no base rebuild.
    installer_ns = runpy.run_path(str(installer), run_name="verify_installer_2219")
    payload_bytes = {
        source: (ROOT / source).read_bytes()
        for _local, (_commit, source, _expected) in payloads.items()
    }
    with tempfile.TemporaryDirectory(prefix="turto_2219_fast_") as temp_name:
        root = Path(temp_name)
        program = root / "Program"
        program.mkdir()
        database = root / "actions.sqlite3"
        database.write_bytes(b"db-byte-identical-2219")
        before = database.read_bytes()

        for name in installer_ns["PREVIOUS_REQUIRED"]:
            path = program / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 2218\n", encoding="utf-8")
        (program / ".turto_runtime_2_2_18.ok").write_text("2.2.18", encoding="utf-8")

        calls: list[str] = []

        def fake_download(_commit: str, path: str, _expected: str, _agent: str) -> bytes:
            calls.append(path)
            if path == installer_ns["BASE_PATH"]:
                raise AssertionError("Kompletní 2.2.18 nesmí spouštět úplnou obnovu.")
            return payload_bytes[path]

        installer_ns["install_runtime"].__globals__["_download"] = fake_download
        installer_ns["install_runtime"](root)

        assert database.read_bytes() == before
        assert (program / ".turto_runtime_2_2_19.ok").read_text(encoding="utf-8") == "2.2.19"
        assert not (program / ".turto_runtime_2_2_18.ok").exists()
        assert all((program / name).is_file() for name in installer_ns["CURRENT_REQUIRED"])
        assert set(calls) == {source for _local, (_commit, source, _expected) in payloads.items()}

        # Cleanup happens only after the new runtime has already been installed.
        cleanup = runpy.run_path(str(RELEASE / "cleanup_stage7.py"), run_name="verify_cleanup_2219")
        for name in cleanup["OBSOLETE_PROGRAM_FILES"]:
            (program / name).write_text("VALUE = 1\n", encoding="utf-8")
        cache = program / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "hit_workspace_prev.cpython-312.pyc").write_bytes(b"stale")
        (cache / "active_module.cpython-312.pyc").write_bytes(b"keep")
        (root / "RELEASE_NOTES.txt").write_text("2.2.19 notes\n", encoding="utf-8")

        cleanup["cleanup_stage7"](root, program, root / "Logy", root / "Logy" / "cleanup.log")

        assert database.read_bytes() == before
        assert all(not (program / name).exists() for name in cleanup["OBSOLETE_PROGRAM_FILES"])
        assert not (cache / "hit_workspace_prev.cpython-312.pyc").exists()
        assert (cache / "active_module.cpython-312.pyc").is_file()
        assert not (root / "RELEASE_NOTES.txt").exists()
        assert (root / "Dokumentace" / "Interni" / "Vydani" / "TURTO_2.2.19.txt").is_file()

        archives = list((root / "Zaloha" / "Archiv").glob("Program_legacy_layers_2.2.19_*.zip"))
        assert len(archives) == 1
        with zipfile.ZipFile(archives[0], "r") as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == set(cleanup["OBSOLETE_PROGRAM_FILES"])

    # Any syntax uncertainty must keep candidates in place.
    cleanup = runpy.run_path(str(RELEASE / "cleanup_stage7.py"), run_name="verify_cleanup_fail_closed_2219")
    with tempfile.TemporaryDirectory(prefix="turto_2219_fail_closed_") as temp_name:
        program = Path(temp_name) / "Program"
        program.mkdir()
        for name in cleanup["OBSOLETE_PROGRAM_FILES"]:
            (program / name).write_text("VALUE = 1\n", encoding="utf-8")
        (program / "broken.py").write_text("not valid python !!!", encoding="utf-8")
        assert cleanup["_safe_obsolete_files"](program) == []

    app = RELEASE / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    assert literal(app, "INSTALLER_SHA256") == sha256(installer)
    assert 'RUNTIME_LAYOUT = "12"' in app_text
    assert 'PROGRAM_REVISION = PROGRAM / ".turto_runtime_2_2_19.ok"' in app_text
    assert "def _post_run_cleanup()" in app_text
    assert app_text.index('runpy.run_path(str(PROGRAM / "app_runtime.pyw"') < app_text.index(
        "if exit_code == 0:"
    )
    required_program = set(literal(app, "REQUIRED_PROGRAM_FILES"))
    assert required_program == current_required

    contract = json.loads((RELEASE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["manifest_root_only"] is True
    assert str(contract["runtime_layout"]) == "12"
    assert contract["cleanup_strategy"] == "post-successful-run-fail-closed"
    assert "actions.sqlite3" in contract["preserve"]

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2.2.19"
    assert str(manifest["runtime_layout"]) == "12"
    assert {item["path"] for item in manifest["files"]} == {
        "app.pyw",
        "updater.py",
        "RELEASE_NOTES.txt",
    }
    assert (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip() == "2.2.19"

    print(
        "OK: TURTO 2.2.19 – direct HIT base composition, explicit helper closure, "
        "three-file overlay, post-run cleanup and byte-identical actions database."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
