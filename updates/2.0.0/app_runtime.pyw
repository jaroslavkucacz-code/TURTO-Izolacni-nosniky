from __future__ import annotations

"""TURTO 2.0.0 runtime – multi-domain / multi-manufacturer platform shell."""

import app_runtime_127 as _prev
import hit_workspace
from platform_workspace import install as install_platform_workspace

APP_VERSION = "2.0.0"

try:
    _prev.APP_VERSION = APP_VERSION
    _prev._prev.APP_VERSION = APP_VERSION
    _prev._prev._prev.APP_VERSION = APP_VERSION
    _prev._prev._prev._base.APP_VERSION = APP_VERSION
    _prev._prev._prev._base.APP_NAME = "TURTO"
except Exception:
    pass

try:
    hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    hit_workspace._prev.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

_BASE = _prev._prev._prev._base
install_platform_workspace(_BASE)


if __name__ == "__main__":
    raise SystemExit(_BASE.main())
