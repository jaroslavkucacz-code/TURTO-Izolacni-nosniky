from __future__ import annotations

"""TURTO 3.0.20 – Editable source element length in individual and bulk decoding."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "3.0.20"
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
import hit_choice_309
import hit_units_310
import ui_responsiveness_311
import decoder_315
import shear_capacity_317
import workspace_controls_317
import shear_choice_318
import st_workspace_319
import readability_319
import decoder_length_320
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
hit_choice_309.install(_base)
hit_units_310.install(_base)
ui_responsiveness_311.install(_base)
decoder_315.install(_base)
shear_capacity_317.install(_base)
workspace_controls_317.install(_base)
shear_choice_318.install(_base)
st_workspace_319.install(_base)
readability_319.install(_base)
decoder_length_320.install(_base)
pdf_data_304.VERSION = APP_VERSION
_base.ThermalConnectorApp.COLUMNS = tuple(
    (key, label, max(width, 112) if key == "target_cover" else width, anchor, stretch)
    for key, label, width, anchor, stretch in _base.ThermalConnectorApp.COLUMNS
)

_base.APP_VERSION = APP_VERSION
_base.APP_NAME = "TURTO Statika"

_previous_header = _base.ThermalConnectorApp._build_header


@wraps(_previous_header)
def _header(self):
    _previous_header(self)
    label = getattr(self, "_turto_brand_title", None)
    if label is not None:
        label.configure(text=f"TURTO Statika {APP_VERSION} | Izolační nosníky a smykové trny")


_base.ThermalConnectorApp._build_header = _header

_previous_init = _base.ThermalConnectorApp.__init__


@wraps(_previous_init)
def _init(self, *args, **kwargs):
    feedback = sys.modules.get('_turto_startup_feedback')
    if feedback:
        feedback.message('Načítám katalogy a připravuji okno…')
    _previous_init(self, *args, **kwargs)
    if feedback:
        feedback.message('Připravuji vyhledávání…')
    # Catalogue extensions invalidate the index several times. Prepare it once
    # after ALL extensions so the first fuzzy query does not pause the editor.
    database = self.database
    while hasattr(database, "base"):
        database = database.base
    database._ensure_suggestion_index()
    # The platform workspace assigns its own legacy title during construction.
    # Set the final product name while retaining AKCE name and dirty indicator.
    self.base_window_title = f"TURTO Statika {APP_VERSION}"
    self._update_project_title()
    if feedback:
        self.after_idle(feedback.close)


_base.ThermalConnectorApp.__init__ = _init

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
    assert APP_VERSION == "3.0.20"
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
    hit_choice_309.selftest()
    hit_units_310.selftest()
    ui_responsiveness_311.selftest()
    import hit_core
    assert hit_core._parse_zvx_pages is zvx_tables_303.parse_zvx_pages


if __name__ == "__main__":
    raise SystemExit(_base.main())
