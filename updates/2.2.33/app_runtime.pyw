from __future__ import annotations

"""TURTO 2.2.33 runtime – restore direct access to every verified Leviat HIT design group."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "2.2.33"
PROGRAM = Path(__file__).resolve().parent
BASE_RUNTIME = PROGRAM / "app_runtime_232.pyw"

if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ 2.2.32: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_app_runtime_232")
_base = _namespace.get("_base")
_hit_workspace = _namespace.get("_hit_workspace")

if _base is None:
    raise RuntimeError("Runtime 2.2.32 neposkytl app_base.")

import design_groups_restore

design_groups_restore.install(_base)

try:
    _base.APP_VERSION = APP_VERSION
    _base.APP_NAME = "TURTO"
except Exception:
    pass

try:
    if _hit_workspace is not None:
        _hit_workspace.HIT_MODULE_VERSION = APP_VERSION
        if hasattr(_hit_workspace, "_base"):
            _hit_workspace._base.HIT_MODULE_VERSION = APP_VERSION
except Exception:
    pass

try:
    import platform_workspace as _platform_workspace
    _platform_workspace.WORKSPACE_VERSION = APP_VERSION
except Exception:
    pass


def selftest() -> None:
    assert APP_VERSION == "2.2.33"
    assert BASE_RUNTIME.name == "app_runtime_232.pyw"
    assert _base is not None
    design_groups_restore.selftest()
    import thermal_design_ui
    assert getattr(thermal_design_ui.SharedDesign, "_schedule_restore_232", False)
    assert getattr(thermal_design_ui.SharedDesign, "_design_groups_restore_233", False)
    assert getattr(_base.ThermalConnectorApp, "_design_groups_restore_233", False)


if __name__ == "__main__":
    raise SystemExit(_base.main())
