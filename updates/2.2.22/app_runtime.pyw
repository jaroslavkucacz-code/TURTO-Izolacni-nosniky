from __future__ import annotations

"""TURTO 2.2.22 runtime shim over the verified 2.2.21 application composition."""

import runpy
from pathlib import Path

APP_VERSION = "2.2.22"
BASE_RUNTIME = Path(__file__).with_name("app_runtime_221.pyw")

if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_app_runtime_221")
_base = _namespace.get("_base")
_hit_workspace = _namespace.get("hit_workspace")

if _base is None:
    raise RuntimeError("Runtime 2.2.21 neposkytl app_base.")

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
    assert APP_VERSION == "2.2.22"
    assert BASE_RUNTIME.name == "app_runtime_221.pyw"
    assert _base is not None


if __name__ == "__main__":
    raise SystemExit(_base.main())
