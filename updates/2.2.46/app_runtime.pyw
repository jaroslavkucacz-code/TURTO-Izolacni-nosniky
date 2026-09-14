from __future__ import annotations

"""TURTO 2.2.46 – active GUI binding fix for Schöck XT bulk decoding."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "2.2.46"
PROGRAM = Path(__file__).resolve().parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

BASE_RUNTIME = PROGRAM / "app_runtime_244.pyw"
if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ 2.2.44: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_runtime_244")
_base = _namespace["_base"]
_hit_workspace = _namespace.get("_hit_workspace")
_previous_selftest = _namespace.get("selftest")

import isokorb_xt_resolver_245
import isokorb_xt_resolver_246

isokorb_xt_resolver_245.install(_base)
isokorb_xt_resolver_246.install(_base)

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
    assert APP_VERSION == "2.2.46"
    if callable(_previous_selftest):
        _previous_selftest()
    import bulk_import
    import bulk_import_engine
    assert getattr(bulk_import_engine, "_turto_isokorb_xt_245", False)
    assert getattr(bulk_import_engine, "_turto_isokorb_xt_246", False)
    assert getattr(bulk_import, "_turto_isokorb_xt_246", False)
    assert bulk_import.analyze_bulk_text is bulk_import_engine.analyze_bulk_text
    isokorb_xt_resolver_245.selftest()
    isokorb_xt_resolver_246.selftest()


if __name__ == "__main__":
    raise SystemExit(_base.main())
