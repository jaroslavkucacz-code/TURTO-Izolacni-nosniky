from __future__ import annotations

"""TURTO ISO 1.1.27 runtime – separate supplementary HIT rows and global PDF."""

import app_runtime_prev as _prev
import hit_workspace

APP_VERSION = "1.1.27"
_prev.APP_VERSION = APP_VERSION
try:
    _prev._prev.APP_VERSION = APP_VERSION
    _prev._prev._base.APP_VERSION = APP_VERSION
except Exception:
    pass
try:
    hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    hit_workspace._prev.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

if __name__ == "__main__":
    raise SystemExit(_prev._prev._base.main())
