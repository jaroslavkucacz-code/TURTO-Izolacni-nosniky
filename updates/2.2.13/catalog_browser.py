from __future__ import annotations

"""TURTO 2.2.13 catalog browser path shim for the Program\ runtime layout."""

import catalog_browser_2210 as _base
from runtime_paths import catalog_root

CATALOG_ROOT = catalog_root()
_base.CATALOG_ROOT = CATALOG_ROOT

CatalogLink = _base.CatalogLink
CATALOGS = _base.CATALOGS
CatalogBrowser = _base.CatalogBrowser
open_catalog_browser = _base.open_catalog_browser


def selftest() -> None:
    _base.selftest()
    assert CATALOG_ROOT == catalog_root()
    assert CATALOG_ROOT.name == "Katalogy"


if __name__ == "__main__":
    selftest()
