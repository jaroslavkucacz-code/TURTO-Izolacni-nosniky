from __future__ import annotations

"""Regression checks for the 2.2.27 main-window restore guard."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "updates" / "2.2.27" / "app_runtime.pyw"
INSTALLER = ROOT / "updates" / "2.2.27" / "runtime_installer.py"
BOOTSTRAP = ROOT / "updates" / "2.2.27" / "app.pyw"
CONTRACT = ROOT / "updates" / "2.2.27" / "release_contract.json"


def _load_clamp():
    source = RUNTIME.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUNTIME))
    node = next(
        (
            item
            for item in tree.body
            if isinstance(item, ast.FunctionDef) and item.name == "clamp_rect_to_work_area"
        ),
        None,
    )
    if node is None:
        raise RuntimeError("Missing clamp_rect_to_work_area().")
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {}
    exec(compile(module, str(RUNTIME), "exec"), namespace)
    return namespace["clamp_rect_to_work_area"], source


def main() -> int:
    clamp, source = _load_clamp()

    assert clamp((100, 100, 1200, 800), (0, 0, 1920, 1040)) == (
        100,
        100,
        1200,
        800,
    )
    assert clamp((2500, 100, 1200, 800), (0, 0, 1920, 1040)) == (
        712,
        100,
        1200,
        800,
    )
    assert clamp((-2100, 40, 1000, 700), (-1920, 0, 0, 1040)) == (
        -1912,
        40,
        1000,
        700,
    )
    assert clamp((10, 10, 3000, 1800), (0, 0, 1920, 1040)) == (
        8,
        8,
        1904,
        1024,
    )

    required_runtime_tokens = (
        "MonitorFromWindow",
        "MONITOR_DEFAULTTONEAREST",
        "GetMonitorInfoW",
        "GetWindowRect",
        "SetWindowPos",
        '_turto_window_state_227',
        'if state == "normal":',
        "widget.after(40",
        "widget.after(220",
        "_ORIGINAL_APP_INIT_227",
        "_base.ThermalConnectorApp.__init__ = _guarded_app_init_227",
    )
    missing = [token for token in required_runtime_tokens if token not in source]
    if missing:
        raise RuntimeError("Incomplete window restore guard: " + ", ".join(missing))

    installer = INSTALLER.read_text(encoding="utf-8")
    if 'RUNTIME_LAYOUT = "20"' not in installer:
        raise RuntimeError("Installer does not use runtime layout 20.")
    if '"app_runtime.pyw"' not in installer:
        raise RuntimeError("Installer does not deliver app_runtime.pyw.")
    if '"shear_movement.py" in CURRENT_REQUIRED' not in installer:
        raise RuntimeError("Installer lost inherited shear runtime closure.")

    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    if 'VERSION = "2.2.27"' not in bootstrap or 'RUNTIME_LAYOUT = "20"' not in bootstrap:
        raise RuntimeError("Bootstrap does not identify 2.2.27 / layout 20.")
    if '"app_runtime.pyw"' not in bootstrap:
        raise RuntimeError("Bootstrap does not verify app_runtime.pyw.")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    for key in (
        "window_restore_guard",
        "multi_monitor_work_area_clamp",
        "normal_state_only_reposition",
        "win32_physical_rect",
    ):
        if contract.get(key) is not True:
            raise RuntimeError(f"Release contract missing {key}=true.")

    current = (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip()
    if current == "2.2.27":
        manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
        if manifest.get("version") != "2.2.27" or str(manifest.get("runtime_layout")) != "20":
            raise RuntimeError("Manifest does not point to 2.2.27 / layout 20.")

    print("OK: TURTO 2.2.27 window restore guard and multi-monitor clamp.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
