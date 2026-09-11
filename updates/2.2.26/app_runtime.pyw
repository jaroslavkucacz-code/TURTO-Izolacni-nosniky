from __future__ import annotations

"""TURTO 2.2.26 runtime – responsive forms and width-safe toolbars."""

import runpy
from pathlib import Path

APP_VERSION = "2.2.26"
BASE_RUNTIME = Path(__file__).with_name("app_runtime_221.pyw")

if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_app_runtime_221")
_base = _namespace.get("_base")
_hit_workspace = _namespace.get("hit_workspace")

if _base is None:
    raise RuntimeError("Runtime 2.2.21 neposkytl app_base.")

_required_shear_methods = (
    "open_shear_decoder_schedule",
    "open_shear_design_schedule",
    "add_shear_decoder_row",
    "add_shear_design_row",
    "shear_decoder_to_substitution",
    "sync_shear_substitutions_from_decoder",
    "recalculate_shear_substitutions",
    "recalculate_shear_design_all",
    "refresh_shear_tables",
)
_missing_shear_methods = [
    name for name in _required_shear_methods
    if not callable(getattr(_base.ThermalConnectorApp, name, None))
]
if _missing_shear_methods:
    raise RuntimeError(
        "Neúplný runtime smykových trnů; chybí metody: "
        + ", ".join(_missing_shear_methods)
    )

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
    assert APP_VERSION == "2.2.26"
    assert BASE_RUNTIME.name == "app_runtime_221.pyw"
    assert _base is not None
    assert not _missing_shear_methods


if __name__ == "__main__":
    raise SystemExit(_base.main())
