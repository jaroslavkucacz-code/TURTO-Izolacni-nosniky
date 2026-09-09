from __future__ import annotations

"""TURTO 2.2.13 runtime – clean Program\ layout with root-aware data paths."""

import os
from pathlib import Path

from runtime_paths import data_directory, install_root, program_root

ROOT = install_root()
PROGRAM = program_root()
os.environ["TURTO_ROOT"] = str(ROOT)
os.environ["TURTO_PROGRAM_DIR"] = str(PROGRAM)

import app_runtime_202 as _prev
from schoeck_dorn_decoder import install as install_schoeck_dorn_decoder
from shear_movement import install as install_shear_movement
from isokorb_compat import install as install_isokorb_compat
from substitution_guard import install as install_substitution_guard

APP_VERSION = "2.2.13"
_BASE = _prev._BASE


def _root_aware_app_root() -> Path:
    return ROOT


def _root_aware_bundled_root() -> Path:
    # Source/runtime modules live in Program; editable data stay in the install root.
    return PROGRAM


def _root_aware_choose_data_directory(name: str) -> Path:
    return data_directory(name)


# The legacy base resolves these helpers dynamically when the application object is created.
# Repoint them before _BASE.main() constructs the UI.
try:
    _BASE.app_root = _root_aware_app_root
    _BASE.bundled_root = _root_aware_bundled_root
    _BASE.choose_data_directory = _root_aware_choose_data_directory
except Exception:
    pass

try:
    _prev.APP_VERSION = APP_VERSION
    _BASE.APP_VERSION = APP_VERSION
    _BASE.APP_NAME = "TURTO"
except Exception:
    pass

try:
    import platform_workspace as _platform_workspace
    _platform_workspace.WORKSPACE_VERSION = APP_VERSION
except Exception:
    pass

install_schoeck_dorn_decoder(_BASE)
install_shear_movement(_BASE)
install_isokorb_compat(_BASE)
install_substitution_guard(_BASE)


def selftest() -> None:
    assert ROOT == install_root()
    assert PROGRAM == program_root()
    assert PROGRAM.name == "Program"
    assert _root_aware_choose_data_directory("Katalogy").parent in {ROOT, PROGRAM}


if __name__ == "__main__":
    raise SystemExit(_BASE.main())
