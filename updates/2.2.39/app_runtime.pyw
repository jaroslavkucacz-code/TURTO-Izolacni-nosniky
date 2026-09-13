from __future__ import annotations
"""TURTO 2.2.39: Aschwanden CRET Series 100 05/2026 catalogue overlay."""

import runpy
import sys
from pathlib import Path

APP_VERSION = "2.2.39"
PROGRAM = Path(__file__).resolve().parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

BASE_RUNTIME = PROGRAM / "app_runtime_238.pyw"
if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ 2.2.38: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_runtime_238")
_base = _namespace["_base"]
_hit_workspace = _namespace.get("_hit_workspace")

import shear_cret_239
shear_cret_239.install(_base)

# Correct the inherited Ancon-only source label in the shared design table.
_original_refresh_239 = _base.ThermalConnectorApp.refresh_shear_tables
def _refresh_cret_source_239(self):
    _original_refresh_239(self)
    tree = getattr(self, "shear_design_tree", None)
    if tree is None:
        return
    try:
        columns = tuple(tree["columns"])
        if "source" not in columns:
            return
        for iid in tree.get_children(""):
            try:
                row = self.shear_design_rows[int(iid)]
            except Exception:
                continue
            candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
            if str(candidate.get("manufacturer", "")) != "Leviat / Aschwanden":
                continue
            source = "CRET Série 100 • 05/2026"
            page = str(candidate.get("page", "") or "")
            if page:
                source += f" • s. {page}"
            tree.set(iid, "source", source)
    except Exception:
        pass

_base.ThermalConnectorApp.refresh_shear_tables = _refresh_cret_source_239

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
    assert APP_VERSION == "2.2.39"
    assert BASE_RUNTIME.name == "app_runtime_238.pyw"
    assert getattr(_base.ThermalConnectorApp, "_turto_shear_substitution_237", False)
    assert getattr(_base.ThermalConnectorApp, "_turto_cret_239", False)
    assert _base.ThermalConnectorApp.refresh_shear_tables is _refresh_cret_source_239
    shear_cret_239.selftest()


if __name__ == "__main__":
    raise SystemExit(_base.main())
