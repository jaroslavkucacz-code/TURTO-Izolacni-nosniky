from __future__ import annotations
"""TURTO 2.2.45 – family-aware Schöck XT resolver over verified 2.2.44 runtime."""
import runpy, sys
from pathlib import Path

APP_VERSION = "2.2.45"
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
isokorb_xt_resolver_245.install(_base)
_base.APP_VERSION = APP_VERSION
_base.APP_NAME = "TURTO"
try:
    import platform_workspace
    platform_workspace.WORKSPACE_VERSION = APP_VERSION
except Exception:
    pass
if _hit_workspace is not None:
    try: _hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    except Exception: pass

def selftest():
    assert APP_VERSION == "2.2.45"
    if callable(_previous_selftest): _previous_selftest()
    import bulk_import_engine
    assert getattr(bulk_import_engine, "_turto_isokorb_xt_245", False)
    isokorb_xt_resolver_245.selftest()

if __name__ == "__main__":
    raise SystemExit(_base.main())
