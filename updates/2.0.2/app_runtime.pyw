from __future__ import annotations

"""TURTO 2.0.2 runtime – startup/grid hotfix over the 2.0 platform."""

import app_runtime_200 as _prev
import hit_workspace

APP_VERSION = "2.0.2"

try:
    _prev.APP_VERSION = APP_VERSION
    _prev._prev.APP_VERSION = APP_VERSION
    _prev._prev._prev.APP_VERSION = APP_VERSION
    _prev._prev._prev._prev.APP_VERSION = APP_VERSION
    _prev._prev._prev._prev._base.APP_VERSION = APP_VERSION
    _prev._prev._prev._prev._base.APP_NAME = "TURTO"
except Exception:
    pass

try:
    hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    hit_workspace._prev.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

_BASE = _prev._prev._prev._prev._base

if __name__ == "__main__":
    raise SystemExit(_BASE.main())
