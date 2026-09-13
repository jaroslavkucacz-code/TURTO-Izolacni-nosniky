from __future__ import annotations
"""TURTO 2.2.37: transparent catalogue/actual-VEd shear-dowel substitutions."""
import runpy
import sys
from pathlib import Path

APP_VERSION = "2.2.37"
PROGRAM = Path(__file__).resolve().parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

_namespace = runpy.run_path(str(PROGRAM / "app_runtime_236.pyw"), run_name="turto_runtime_236")
_base = _namespace["_base"]
_hit_workspace = _namespace.get("_hit_workspace")

import shear_substitution_237
shear_substitution_237.install(_base)

_base.APP_VERSION = APP_VERSION
_base.APP_NAME = "TURTO"
import platform_workspace
platform_workspace.WORKSPACE_VERSION = APP_VERSION
if _hit_workspace is not None:
    _hit_workspace.HIT_MODULE_VERSION = APP_VERSION


def selftest():
    assert _base.ThermalConnectorApp._turto_hsd_workflow_236
    assert _base.ThermalConnectorApp._turto_shear_substitution_237
    shear_substitution_237.selftest()


if __name__ == "__main__":
    raise SystemExit(_base.main())
