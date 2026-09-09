from __future__ import annotations

"""TURTO 2.2.17 runtime – flattened app composition with flattened HIT workspace."""

import os
from pathlib import Path
from tkinter import ttk

from runtime_paths import data_directory, install_root, program_root

ROOT = install_root()
PROGRAM = program_root()
os.environ["TURTO_ROOT"] = str(ROOT)
os.environ["TURTO_PROGRAM_DIR"] = str(PROGRAM)

import app_central_prev as _central
import hit_workspace
import substitution_workspace
from table_polish import install_substitution
import wt_safety_guard  # noqa: F401
from platform_workspace import install as install_platform_workspace
from schoeck_dorn_decoder import install as install_schoeck_dorn_decoder
from shear_movement import install as install_shear_movement
from isokorb_compat import install as install_isokorb_compat
from substitution_guard import install as install_substitution_guard

APP_VERSION = "2.2.17"
_BASE = _central._base


def _root_aware_app_root() -> Path:
    return ROOT


def _root_aware_bundled_root() -> Path:
    return PROGRAM


def _root_aware_choose_data_directory(name: str) -> Path:
    return data_directory(name)


_BASE.app_root = _root_aware_app_root
_BASE.bundled_root = _root_aware_bundled_root
_BASE.choose_data_directory = _root_aware_choose_data_directory

install_substitution(substitution_workspace.SubstitutionWorkspaceMixin)


def _walk(root):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


_ORIGINAL_HEADER = _BASE.ThermalConnectorApp._build_header


def _header(self) -> None:
    _ORIGINAL_HEADER(self)
    for widget in _walk(self):
        if not isinstance(widget, ttk.Label):
            continue
        try:
            text = str(widget.cget("text"))
            if text.startswith("Jedna AKCE • Dekodér ISO"):
                widget.configure(
                    text="Jedna AKCE • Dekodér ISO • Návrh HIT pro desky i WT stěny • "
                    "Záměny za HIT • společné centrální uložení"
                )
        except Exception:
            pass


_BASE.ThermalConnectorApp._build_header = _header
install_platform_workspace(_BASE)

try:
    _central.APP_VERSION = APP_VERSION
    _BASE.APP_VERSION = APP_VERSION
    _BASE.APP_NAME = "TURTO"
except Exception:
    pass

try:
    hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    if hasattr(hit_workspace, "_prev"):
        hit_workspace._prev.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
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
    assert APP_VERSION == "2.2.17"
    assert hit_workspace.HitWorkspaceMixin is not None


if __name__ == "__main__":
    raise SystemExit(_BASE.main())
