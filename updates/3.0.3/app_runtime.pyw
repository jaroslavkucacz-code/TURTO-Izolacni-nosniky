from __future__ import annotations

"""TURTO 3.0.3 – physical Annex 3 columns and verified ZVX/ZDX cache repair."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "3.0.3"
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

import branding_301
import iso_bulk_301
import shear_cover_302
import zvx_tables_303

branding_301.install(_base)
iso_bulk_301.install(_base)
shear_cover_302.install(_base)
zvx_tables_303.install(_base)
_base.ThermalConnectorApp.COLUMNS = tuple(
    (key, label, max(width, 112) if key == "target_cover" else width, anchor, stretch)
    for key, label, width, anchor, stretch in _base.ThermalConnectorApp.COLUMNS
)

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
    assert APP_VERSION == "3.0.3"
    if callable(_previous_selftest):
        _previous_selftest()
    assert getattr(_base.ThermalConnectorApp, "_turto_branding_301", False)
    branding_301.selftest()
    iso_bulk_301.selftest()
    shear_cover_302.selftest()
    zvx_tables_303.selftest()
    import hit_core
    assert hit_core._parse_zvx_pages is zvx_tables_303.parse_zvx_pages


if __name__ == "__main__":
    raise SystemExit(_base.main())
