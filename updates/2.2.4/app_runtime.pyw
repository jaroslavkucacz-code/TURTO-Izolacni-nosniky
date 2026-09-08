from __future__ import annotations

"""TURTO 2.2.4 runtime – unified tables and cross-domain UI cleanup."""

import app_runtime_202 as _prev
from schoeck_dorn_decoder import install as install_schoeck_dorn_decoder
from shear_movement import install as install_shear_movement
from isokorb_compat import install as install_isokorb_compat

APP_VERSION = "2.2.4"

try:
    _prev.APP_VERSION = APP_VERSION
    _prev._BASE.APP_VERSION = APP_VERSION
    _prev._BASE.APP_NAME = "TURTO"
except Exception:
    pass

_BASE = _prev._BASE
install_schoeck_dorn_decoder(_BASE)
install_shear_movement(_BASE)
install_isokorb_compat(_BASE)

if __name__ == "__main__":
    raise SystemExit(_BASE.main())
