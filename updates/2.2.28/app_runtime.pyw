from __future__ import annotations

"""TURTO 2.2.28 runtime – Peikko EBEA/TEBEA decoding, substitutions and safe preselection."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "2.2.28"
PROGRAM = Path(__file__).resolve().parent
BASE_RUNTIME = PROGRAM / "app_runtime_227.pyw"

if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_app_runtime_227")
_base = _namespace.get("_base")
_hit_workspace = _namespace.get("_hit_workspace")

if _base is None:
    raise RuntimeError("Runtime 2.2.27 neposkytl app_base.")

import peikko_thermal_breaks
import peikko_workspace

peikko_workspace.install(_base)

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
    assert APP_VERSION == "2.2.28"
    assert BASE_RUNTIME.name == "app_runtime_227.pyw"
    assert _base is not None
    peikko_thermal_breaks.selftest()
    peikko_workspace.selftest()
    assert callable(getattr(_base.ThermalConnectorApp, "decode_peikko_product", None))
    assert callable(getattr(_base.ThermalConnectorApp, "peikko_substitution_candidates", None))
    assert callable(getattr(_base.ThermalConnectorApp, "peikko_design_candidates", None))


if __name__ == "__main__":
    raise SystemExit(_base.main())
