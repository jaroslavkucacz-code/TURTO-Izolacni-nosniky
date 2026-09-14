from __future__ import annotations
"""TURTO 2.2.43: exact Schöck Isokorb XT bulk-designation analysis."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "2.2.43"
PROGRAM = Path(__file__).resolve().parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

BASE_RUNTIME = PROGRAM / "app_runtime_242.pyw"
if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ 2.2.42: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_runtime_242")
_base = _namespace["_base"]
_hit_workspace = _namespace.get("_hit_workspace")

import isokorb_xt_parser_243
isokorb_xt_parser_243.install(_base)

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
    assert APP_VERSION == "2.2.43"
    assert BASE_RUNTIME.name == "app_runtime_242.pyw"
    assert getattr(_base.ThermalConnectorApp, "_turto_shear_substitution_237", False)
    assert getattr(_base.ThermalConnectorApp, "_turto_cret_239", False)
    assert getattr(_base.ThermalConnectorApp, "_turto_pdf_context_240", False)
    assert getattr(_base.ThermalConnectorApp, "_turto_cret_sync_242", False)
    import bulk_import_engine
    assert getattr(bulk_import_engine, "_turto_isokorb_xt_243", False)
    isokorb_xt_parser_243.selftest()


if __name__ == "__main__":
    raise SystemExit(_base.main())
