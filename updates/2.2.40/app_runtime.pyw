from __future__ import annotations
"""TURTO 2.2.40: context-aware PDF export for technical elements."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "2.2.40"
PROGRAM = Path(__file__).resolve().parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

BASE_RUNTIME = PROGRAM / "app_runtime_239.pyw"
if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ 2.2.39: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_runtime_239")
_base = _namespace["_base"]
_hit_workspace = _namespace.get("_hit_workspace")

import pdf_context_240
pdf_context_240.install(_base)

_base.APP_VERSION = APP_VERSION
_base.APP_NAME = "TURTO"
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
    assert APP_VERSION == "2.2.40"
    assert BASE_RUNTIME.name == "app_runtime_239.pyw"
    assert getattr(_base.ThermalConnectorApp, "_turto_shear_substitution_237", False)
    assert getattr(_base.ThermalConnectorApp, "_turto_cret_239", False)
    assert getattr(_base.ThermalConnectorApp, "_turto_pdf_context_240", False)
    pdf_context_240.selftest()


if __name__ == "__main__":
    raise SystemExit(_base.main())
