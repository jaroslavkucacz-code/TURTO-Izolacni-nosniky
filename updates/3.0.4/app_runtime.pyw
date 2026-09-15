from __future__ import annotations

"""TURTO 3.0.4 - exact additional Schöck syntax and live PDF export data."""

import runpy
import sys
from functools import wraps
from pathlib import Path

APP_VERSION = "3.0.4"
PROGRAM = Path(__file__).resolve().parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

BASE_RUNTIME = PROGRAM / "app_runtime_303.pyw"
if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ 3.0.3: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_runtime_303")
_base = _namespace["_base"]
_hit_workspace = _namespace.get("_hit_workspace")
_previous_selftest = _namespace.get("selftest")

import decoder_304
import pdf_export_304

decoder_304.install(_base)
pdf_export_304.install(_base)

# The 3.0.3 wrapper owns the previous title patch. Apply the final release title
# after it so the visible application always reports the running version.
_previous_header = _base.ThermalConnectorApp._build_header

@wraps(_previous_header)
def _header_304(self):
    _previous_header(self)
    label = getattr(self, "_turto_brand_title", None)
    if label is not None:
        label.configure(text="TURTO 3.0.4 | Izolační nosníky a smykové trny")

_base.ThermalConnectorApp._build_header = _header_304
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
    assert APP_VERSION == "3.0.4"
    if callable(_previous_selftest):
        _previous_selftest()
    decoder_304.selftest()
    pdf_export_304.selftest()
    import bulk_import_engine as engine
    assert getattr(engine, "_turto_decoder_304", False)
    assert getattr(_base.ThermalConnectorApp, "_turto_pdf_export_304", False)


if __name__ == "__main__":
    raise SystemExit(_base.main())
