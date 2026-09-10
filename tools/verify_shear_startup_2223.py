from __future__ import annotations

"""Regression checks for TURTO 2.2.23 shear-dowel startup repair."""

import importlib.util
import runpy
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.23"


def _load_wrapper_with_stubs():
    calls: list[str] = []
    stable = types.ModuleType("shear_dowels_ui_215")
    current = types.ModuleType("shear_dowels_current_221")

    stable_names = (
        "open_shear_decoder_schedule",
        "open_shear_design_schedule",
        "add_shear_decoder_row",
        "add_shear_design_row",
        "shear_decoder_to_substitution",
        "sync_shear_substitutions_from_decoder",
        "recalculate_shear_substitutions",
        "recalculate_shear_design_all",
        "shear_edit_meta",
        "shear_duplicate_selected",
        "shear_move_selected",
        "shear_delete_selected",
        "refresh_shear_tables",
        "serialize_shear_dowels",
        "load_shear_dowels",
    )

    def stable_install(cls):
        calls.append("stable")
        for name in stable_names:
            setattr(cls, name, lambda *args, **kwargs: None)

    def current_install(cls):
        calls.append("current")
        assert callable(getattr(cls, "open_shear_decoder_schedule", None))
        cls.add_shear_design_row = lambda *args, **kwargs: "current-design"
        cls.refresh_shear_tables = lambda *args, **kwargs: "current-refresh"

    stable.install_methods = stable_install
    current.install_methods = current_install
    current.build_shear_workspace = lambda *args, **kwargs: None
    current.init_shear_workspace = lambda *args, **kwargs: None

    saved = {
        name: sys.modules.get(name)
        for name in ("shear_dowels_ui_215", "shear_dowels_current_221")
    }
    sys.modules["shear_dowels_ui_215"] = stable
    sys.modules["shear_dowels_current_221"] = current
    try:
        spec = importlib.util.spec_from_file_location(
            "turto_shear_223_test", RELEASE / "shear_dowels_current.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return module, calls


def verify_wrapper_chain() -> None:
    source = (RELEASE / "shear_dowels_current.py").read_text(encoding="utf-8")
    assert source.index("_stable.install_methods(cls)") < source.index("_current.install_methods(cls)")
    assert "open_shear_decoder_schedule" in source

    module, calls = _load_wrapper_with_stubs()

    class App:
        pass

    assert not hasattr(App, "open_shear_decoder_schedule")
    module.install_methods(App)
    assert calls == ["stable", "current"]
    assert callable(App.open_shear_decoder_schedule)
    assert App.add_shear_design_row() == "current-design"
    assert App.refresh_shear_tables() == "current-refresh"
    assert App._turto_shear_223_installed is True

    module.install_methods(App)
    assert calls == ["stable", "current"]


def verify_release_runtime() -> None:
    installer = runpy.run_path(str(RELEASE / "runtime_installer.py"))
    required = set(installer["CURRENT_REQUIRED"])
    payloads = installer["PAYLOADS"]
    for name in (
        "shear_dowels_current.py",
        "shear_dowels_current_221.py",
        "shear_dowels_schedule.py",
        "shear_dowels_schedule_guard.py",
        "shear_dowels_ui_214.py",
        "shear_dowels_schedule_215.py",
        "shear_dowels_ui_215.py",
        "historical_schoeck_dorn.py",
    ):
        assert name in required
        if name != "historical_schoeck_dorn.py" or name in payloads:
            assert name in payloads
    assert "actions.sqlite3" not in required
    assert "actions.sqlite3" not in payloads
    assert installer["RUNTIME_LAYOUT"] == "16"

    app_source = (RELEASE / "app.pyw").read_text(encoding="utf-8")
    runtime_source = (RELEASE / "app_runtime.pyw").read_text(encoding="utf-8")
    assert 'VERSION = "2.2.23"' in app_source
    assert '"shear_dowels_schedule.py"' in app_source
    assert '"shear_dowels_current_221.py"' in app_source
    assert '"open_shear_decoder_schedule"' in runtime_source
    assert '_disk_bootstrap_version() != VERSION' in app_source


def verify_installer_keeps_database() -> None:
    ns = runpy.run_path(str(RELEASE / "runtime_installer.py"))
    previous = tuple(ns["PREVIOUS_REQUIRED"])
    payloads = dict(ns["PAYLOADS"])

    with tempfile.TemporaryDirectory(prefix="turto_223_test_") as temp_name:
        root = Path(temp_name)
        program = root / "Program"
        program.mkdir()
        for name in previous:
            target = program / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"previous")
        (program / ".turto_runtime_2_2_22.ok").write_text("2.2.22", encoding="utf-8")
        database = root / "actions.sqlite3"
        original = b"sqlite-action-data-must-stay-byte-identical"
        database.write_bytes(original)

        def fake_download(commit, path, expected, agent):
            return f"{commit}:{path}:{expected}:{agent}".encode("utf-8")

        ns["_download"] = fake_download
        ns["install_runtime"].__globals__["_download"] = fake_download
        ns["install_runtime"](root)

        assert database.read_bytes() == original
        assert (program / ".turto_runtime_2_2_23.ok").read_text(encoding="utf-8") == "2.2.23"
        for name in payloads:
            assert (program / name).is_file()


def main() -> None:
    verify_wrapper_chain()
    verify_release_runtime()
    verify_installer_keeps_database()
    print("TURTO 2.2.23 shear startup regression: OK")


if __name__ == "__main__":
    main()
