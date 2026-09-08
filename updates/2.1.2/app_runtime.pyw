from __future__ import annotations

"""TURTO 2.1.2 runtime – startup-safe decoder hotfix over verified 2.1.0 base."""

import app_runtime_202 as _prev
from legacy_schoeck_decoder import install as install_legacy_schoeck_decoder

APP_VERSION = "2.1.2"

try:
    _prev.APP_VERSION = APP_VERSION
    _prev._BASE.APP_VERSION = APP_VERSION
    _prev._BASE.APP_NAME = "TURTO"
except Exception:
    pass

_BASE = _prev._BASE
install_legacy_schoeck_decoder(_BASE)

if __name__ == "__main__":
    raise SystemExit(_BASE.main())
