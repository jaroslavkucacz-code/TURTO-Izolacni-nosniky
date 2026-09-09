from __future__ import annotations

"""Regression checks for TURTO 2.2.17 HIT-workspace flattening."""

import ast
import hashlib
import runpy
import sys
import tempfile
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.17"
OBSOLETE_HIT = {
    "hit_workspace_201.py",
    "hit_workspace_200.py",
    "hit_workspace_127.py",
}
OBSOLETE_APP = {
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


def _exercise_flattened_import(hit_path: Path) -> None:
    saved: dict[str, object | None] = {}
    names = ("hit_workspace_125", "hit_aux_ui", "unified_schedule", "supplier_export")
    for name in names:
        saved[name] = sys.modules.get(name)

    base = types.ModuleType("hit_workspace_125")

    class HitInputRow:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

    class HitWorkspaceMixin:
        def _build_hit_tab(self, *_args, **_kwargs) -> None:
            pass

        def add_hit_row_for_type(self, *_args, **_kwargs) -> None:
            pass

    base.HitInputRow = HitInputRow
    base.HitWorkspaceMixin = HitWorkspaceMixin
    base.HIT_MODULE_VERSION = "old"
    base._prev = types.SimpleNamespace(HIT_MODULE_VERSION="old")
    base.__all__ = ["HitInputRow", "HitWorkspaceMixin"]

    aux = types.ModuleType("hit_aux_ui")
    aux.AUX_TYPES = ("HT", "AT", "FT", "OTX")

    def install_aux(module) -> None:
        def add_aux_row_for_type(self, *_args, **_kwargs):
            return None

        def build_aux_tab(self, *_args, **_kwargs):
            return None

        module.HitWorkspaceMixin.add_aux_row_for_type = add_aux_row_for_type
        module.HitWorkspaceMixin._build_aux_tab = build_aux_tab

    aux.install = install_aux

    unified = types.ModuleType("unified_schedule")
    unified.open_unified_schedule = lambda *_args, **_kwargs: None
    supplier = types.ModuleType("supplier_export")
    supplier.export_supplier_excel = lambda *_args, **_kwargs: None

    sys.modules["hit_workspace_125"] = base
    sys.modules["hit_aux_ui"] = aux
    sys.modules["unified_schedule"] = unified
    sys.modules["supplier_export"] = supplier
    try:
        namespace = runpy.run_path(str(hit_path), run_name="verify_hit_workspace_2217")
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
    required = (
        "app_runtime.pyw",
        "hit_workspace.py",
        "runtime_installer.py",
        "cleanup_stage6.py",
    )
    for name in required:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    hit = RELEASE / "hit_workspace.py"
    hit_text = hit.read_text(encoding="utf-8")
    hit_imports = imported_names(hit)
    assert not ({name[:-3] for name in OBSOLETE_HIT} & hit_imports)
    assert "hit_workspace_125" in hit_imports
    for token in (
        'HIT_MODULE_VERSION = "2.2.17"',
        'STANDARD_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL")',
        "_install_aux(_base125)",
        "hidden_base_indices = {11, 12, 15, 16, 17}",
        "open_unified_schedule(self)",
        "export_supplier_excel(self)",
        'return self.add_aux_row_for_type("HT")',
        "_remove_generated_initial_row(self)",
        "def _clear_hit_rows(self)",
        "_base125.HitWorkspaceMixin._build_hit_tab = _build_final",
    ):
        assert token in hit_text, token
    _exercise_flattened_import(hit)

    runtime = RELEASE / "app_runtime.pyw"
    runtime_text = runtime.read_text(encoding="utf-8")
    assert 'APP_VERSION = "2.2.17"' in runtime_text
    assert "import hit_workspace" in runtime_text
    assert not ({name[:-4] for name in OBSOLETE_APP} & imported_names(runtime))

    installer = RELEASE / "runtime_installer.py"
    installer_text = installer.read_text(encoding="utf-8")
    for token in (
        'RUNTIME_LAYOUT = "10"',
        'PREVIOUS_REVISION = ".turto_runtime_2_2_16.ok"',
        'PROGRAM_REVISION = ".turto_runtime_2_2_17.ok"',
        "_ensure_previous_runtime",
        "_apply_incremental_overlay",
        "actions.sqlite3 is never modified",
    ):
        assert token in installer_text, token

    base_hash = literal(installer, "BASE_SHA256")
    actual_base = sha256(ROOT / "updates" / "2.2.16" / "runtime_installer.py")
    if actual_base != base_hash:
        raise RuntimeError(f"BASE_SHA256: očekáváno {base_hash}, skutečně {actual_base}")

    payloads = literal(installer, "PAYLOADS")
    assert set(payloads) == {"app_runtime.pyw", "hit_workspace.py", "cleanup_stage6.py"}
    for local, (_commit, source, expected) in payloads.items():
        source_path = ROOT / source
        actual = sha256(source_path)
        if actual != expected:
            raise RuntimeError(f"PAYLOAD {local}: očekáváno {expected}, skutečně {actual}")

    previous_required = set(literal(installer, "PREVIOUS_REQUIRED"))
    current_required = set(literal(installer, "CURRENT_REQUIRED"))
    assert "hit_workspace_125.py" in previous_required
    assert "hit_workspace_prev.py" in previous_required
    assert "hit_workspace_base.py" in previous_required
    assert "hit_aux_ui.py" in previous_required
    assert "hit_wt_ui.py" in previous_required
    assert "cleanup_stage6.py" in current_required
    assert not (OBSOLETE_HIT & current_required)
    assert not (OBSOLETE_APP & current_required)

    installer_ns = runpy.run_path(str(installer), run_name="verify_installer_2217")
    install_runtime = installer_ns["install_runtime"]
    payload_bytes = {
        source: (ROOT / source).read_bytes()
        for _local, (_commit, source, _expected) in payloads.items()
    }
    with tempfile.TemporaryDirectory(prefix="turto_2217_incremental_") as temp_name:
        root = Path(temp_name)
        program = root / "Program"
        program.mkdir()
        database = root / "actions.sqlite3"
        database.write_bytes(b"db-must-stay-byte-identical")
        before = database.read_bytes()

        for name in installer_ns["PREVIOUS_REQUIRED"]:
            path = program / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 2216\n", encoding="utf-8")
        (program / ".turto_runtime_2_2_16.ok").write_text("2.2.16", encoding="utf-8")

        calls: list[str] = []

        def fake_download(_commit: str, path: str, _expected: str, _agent: str) -> bytes:
            calls.append(path)
            if path == installer_ns["BASE_PATH"]:
                raise AssertionError("Platný 2.2.16 Program nesmí spouštět plnou obnovu.")
            return payload_bytes[path]

        install_runtime.__globals__["_download"] = fake_download
        install_runtime(root)

        assert database.read_bytes() == before
        assert (program / ".turto_runtime_2_2_17.ok").read_text(encoding="utf-8") == "2.2.17"
        assert not (program / ".turto_runtime_2_2_16.ok").exists()
        assert all((program / name).is_file() for name in installer_ns["CURRENT_REQUIRED"])
        assert (program / "hit_workspace.py").read_bytes() == hit.read_bytes()
        assert installer_ns["BASE_PATH"] not in calls
        assert set(calls) == {source for _local, (_commit, source, _expected) in payloads.items()}

        for name in OBSOLETE_APP | OBSOLETE_HIT:
            (program / name).write_text("VALUE = 1\n", encoding="utf-8")
        cache = program / "__pycache__"
        cache.mkdir()
        (cache / "x.pyc").write_bytes(b"cache")
        (root / "RELEASE_NOTES.txt").write_text("2.2.17 notes\n", encoding="utf-8")

        cleanup_ns = runpy.run_path(str(RELEASE / "cleanup_stage6.py"), run_name="verify_cleanup_2217")
        cleanup_ns["cleanup_stage6"](root, program, root / "Logy", root / "Logy" / "cleanup.log")

        assert database.read_bytes() == before
        assert all(not (program / name).exists() for name in OBSOLETE_APP | OBSOLETE_HIT)
        assert not cache.exists()
        assert not (root / "RELEASE_NOTES.txt").exists()
        assert (root / "Dokumentace" / "Interni" / "Vydani" / "TURTO_2.2.17.txt").is_file()

        runtime_archives = list((root / "Zaloha" / "Archiv").glob("Program_legacy_runtime_2.2.17_*.zip"))
        hit_archives = list((root / "Zaloha" / "Archiv").glob("Program_legacy_HIT_2.2.17_*.zip"))
        assert len(runtime_archives) == 1
        assert len(hit_archives) == 1
        with zipfile.ZipFile(runtime_archives[0], "r") as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == OBSOLETE_APP
        with zipfile.ZipFile(hit_archives[0], "r") as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == OBSOLETE_HIT

    cleanup_ns = runpy.run_path(str(RELEASE / "cleanup_stage6.py"), run_name="verify_cleanup_fail_closed_2217")
    with tempfile.TemporaryDirectory(prefix="turto_2217_fail_closed_") as temp_name:
        program = Path(temp_name) / "Program"
        program.mkdir()
        for name in OBSOLETE_HIT:
            (program / name).write_text("VALUE = 1\n", encoding="utf-8")
        (program / "broken.py").write_text("not valid python !!!", encoding="utf-8")
        assert cleanup_ns["_safe_obsolete_wrappers"](program, tuple(OBSOLETE_HIT)) == []

    print(
        "OK: TURTO 2.2.17 – flattened HIT workspace, incremental overlay, "
        "safe wrapper archives and byte-identical action database."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
