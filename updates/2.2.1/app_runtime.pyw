from __future__ import annotations

"""TURTO 2.2.1 runtime – stabilní vstupní vrstva po úklidu spouštění."""

import app_runtime_202 as _prev
from schoeck_dorn_decoder import install as install_schoeck_dorn_decoder

APP_VERSION = "2.2.1"

try:
    _prev.APP_VERSION = APP_VERSION
    _prev._BASE.APP_VERSION = APP_VERSION
    _prev._BASE.APP_NAME = "TURTO"
except Exception:
    pass

_BASE = _prev._BASE
install_schoeck_dorn_decoder(_BASE)

if __name__ == "__main__":
    raise SystemExit(_BASE.main())
