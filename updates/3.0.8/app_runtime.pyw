from __future__ import annotations

"""TURTO 3.0.8 – T-QP-VV substitution through the verified HIT engine."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "3.0.8"
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
import isokorb_families_304
import pdf_data_304
import pdf_branding_305
import design_rows_306
import isokorb_qp_307
import shear_cover_308
from functools import wraps

branding_301.install(_base)
iso_bulk_301.install(_base)
shear_cover_302.install(_base)
zvx_tables_303.install(_base)
isokorb_families_304.install(_base)
pdf_data_304.install(_base)
pdf_branding_305.install()
design_rows_306.install(_base)
isokorb_qp_307.install(_base)
shear_cover_308.install(_base)
pdf_data_304.VERSION = APP_VERSION
_base.ThermalConnectorApp.COLUMNS = tuple(
    (key, label, max(width, 112) if key == "target_cover" else width, anchor, stretch)
    for key, label, width, anchor, stretch in _base.ThermalConnectorApp.COLUMNS
)

_base.APP_VERSION = APP_VERSION
_base.APP_NAME = "TURTO 3.0"

_previous_header = _base.ThermalConnectorApp._build_header


@wraps(_previous_header)
def _header(self):
    _previous_header(self)
    label = getattr(self, "_turto_brand_title", None)
    if label is not None:
        label.configure(text=f"TURTO {APP_VERSION} | Izolační nosníky a smykové trny")


_base.ThermalConnectorApp._build_header = _header

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
    assert APP_VERSION == "3.0.8"
    if callable(_previous_selftest):
        _previous_selftest()
    assert getattr(_base.ThermalConnectorApp, "_turto_branding_301", False)
    branding_301.selftest()
    iso_bulk_301.selftest()
    shear_cover_302.selftest()
    zvx_tables_303.selftest()
    isokorb_families_304.selftest()
    pdf_data_304.selftest()
    pdf_branding_305.selftest()
    design_rows_306.selftest()
    isokorb_qp_307.selftest()
    shear_cover_308.selftest()
    import hit_core
    assert hit_core._parse_zvx_pages is zvx_tables_303.parse_zvx_pages


if __name__ == "__main__":
    raise SystemExit(_base.main())
