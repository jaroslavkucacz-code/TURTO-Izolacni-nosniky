from __future__ import annotations

"""Shared path model for TURTO 2.2.13 Program\ runtime layout."""

import os
from pathlib import Path

ENV_INSTALL_ROOT = "TURTO_ROOT"
ENV_PROGRAM_ROOT = "TURTO_PROGRAM_DIR"


def install_root() -> Path:
    configured = str(os.environ.get(ENV_INSTALL_ROOT, "") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    here = Path(__file__).resolve().parent
    if here.name.casefold() == "program":
        return here.parent
    return here


def program_root() -> Path:
    configured = str(os.environ.get(ENV_PROGRAM_ROOT, "") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return install_root() / "Program"


def data_directory(name: str) -> Path:
    """Prefer the installation-root data folder; fall back to Program for compatibility."""
    root_candidate = install_root() / str(name)
    if root_candidate.exists():
        return root_candidate
    return program_root() / str(name)


def root_file(name: str) -> Path:
    return install_root() / str(name)


def catalog_root() -> Path:
    return install_root() / "Katalogy"


def selftest() -> None:
    assert program_root().name == "Program"
    assert catalog_root().name == "Katalogy"
    assert root_file("actions.sqlite3").name == "actions.sqlite3"


if __name__ == "__main__":
    selftest()
