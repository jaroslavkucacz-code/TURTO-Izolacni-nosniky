from __future__ import annotations

"""TURTO 3.0.0 – branded major release over the verified 2.2.46 runtime."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "3.0.0"
PROGRAM = Path(__file__).resolve().parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

BASE_RUNTIME = PROGRAM / "app_runtime_246.pyw"
if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ 2.2.46: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_runtime_246")
_base = _namespace["_base"]
_hit_workspace = _namespace.get("_hit_workspace")
_previous_selftest = _namespace.get("selftest")

import branding_300

branding_300.install(_base)

_base.APP_VERSION = APP_VERSION
_base.APP_NAME = "TURTO 3.0"

try:
    import platform_workspace
    platform_workspace.WORKSPACE_VERSION = APP_VERSION
except Exception:
    pass

if _hit_workspace is not None:
    try:
        _hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    except Exception:
        pass


def selftest() -> None:
    assert APP_VERSION == "3.0.0"
    if callable(_previous_selftest):
        _previous_selftest()
    assert getattr(_base.ThermalConnectorApp, "_turto_branding_300", False)
    branding_300.selftest()


if __name__ == "__main__":
    raise SystemExit(_base.main())
