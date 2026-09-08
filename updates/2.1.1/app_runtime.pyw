from __future__ import annotations

"""TURTO 2.1.1 runtime – historical Schöck decoder aliases."""

import app_runtime_210 as _prev

APP_VERSION = "2.1.1"
try:
    _prev.APP_VERSION = APP_VERSION
    _prev._prev.APP_VERSION = APP_VERSION
    _prev._BASE.APP_VERSION = APP_VERSION
    _prev._BASE.APP_NAME = "TURTO"
except Exception:
    pass

_BASE = _prev._BASE

if __name__ == "__main__":
    raise SystemExit(_BASE.main())
