from __future__ import annotations

"""TURTO 2.2.46 – bind the Schöck XT family resolver to the actual bulk-import GUI path.

2.2.45 correctly patched ``bulk_import_engine.analyze_bulk_text`` but the GUI module
had imported that function by name much earlier. ``BulkImportDialog._analyze``
therefore kept calling the stale module-global alias.  This bridge deliberately
rebinds both locations to the same verified resolver without changing catalogue,
static-capacity or project data.
"""

import bulk_import
import bulk_import_engine as _engine
import isokorb_xt_resolver_245 as _resolver_245

VERSION = "2.2.46"


def install(_base=None) -> None:
    # Ensure the family-aware 2.2.45 wrapper exists first. This call is idempotent.
    _resolver_245.install(_base)
    active = _engine.analyze_bulk_text

    # Critical fix: BulkImportDialog._analyze() resolves this name from the
    # bulk_import module globals, not dynamically from bulk_import_engine.
    bulk_import.analyze_bulk_text = active

    _engine._turto_isokorb_xt_246 = True
    bulk_import._turto_isokorb_xt_246 = True


def selftest() -> None:
    assert VERSION == "2.2.46"
    assert getattr(_engine, "_turto_isokorb_xt_245", False)
    assert getattr(_engine, "_turto_isokorb_xt_246", False)
    assert getattr(bulk_import, "_turto_isokorb_xt_246", False)
    # End-to-end binding guard: this is the exact global used by
    # BulkImportDialog._analyze() when the user presses Analyzovat.
    assert bulk_import.analyze_bulk_text is _engine.analyze_bulk_text


if __name__ == "__main__":
    install()
    selftest()
