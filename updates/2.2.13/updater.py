from __future__ import annotations

"""Program-side proxy to the single root updater used by TURTO."""

import importlib.util
from pathlib import Path
from types import ModuleType

from runtime_paths import install_root

_ROOT_UPDATER = install_root() / "updater.py"
_MODULE: ModuleType | None = None


def _root_updater() -> ModuleType:
    global _MODULE
    if _MODULE is not None:
        return _MODULE
    if not _ROOT_UPDATER.is_file():
        raise RuntimeError(f"Chybí aktualizační modul: {_ROOT_UPDATER}")
    spec = importlib.util.spec_from_file_location("_turto_root_updater", _ROOT_UPDATER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nelze načíst aktualizační modul: {_ROOT_UPDATER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _MODULE = module
    return module


def check_and_update(parent, current_version: str) -> None:
    _root_updater().check_and_update(parent, current_version)


def selftest() -> None:
    assert _ROOT_UPDATER.name == "updater.py"
    assert _ROOT_UPDATER.parent == install_root()


if __name__ == "__main__":
    selftest()
