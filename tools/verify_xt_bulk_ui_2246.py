from __future__ import annotations

"""Regression guard for TURTO 2.2.46 bulk-import GUI resolver binding."""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.46"


def main() -> int:
    engine = types.ModuleType("bulk_import_engine")

    def stale(*_args, **_kwargs):
        return "stale"

    engine.analyze_bulk_text = stale
    sys.modules["bulk_import_engine"] = engine

    bulk_import = types.ModuleType("bulk_import")
    bulk_import.analyze_bulk_text = stale
    exec(
        "def gui_call():\n"
        "    return analyze_bulk_text()\n",
        bulk_import.__dict__,
    )
    sys.modules["bulk_import"] = bulk_import

    resolver245 = types.ModuleType("isokorb_xt_resolver_245")

    def install245(_base=None):
        if getattr(engine, "_turto_isokorb_xt_245", False):
            return

        def family_aware(*_args, **_kwargs):
            return "family-aware"

        engine.analyze_bulk_text = family_aware
        engine._turto_isokorb_xt_245 = True

    resolver245.install = install245
    resolver245.selftest = lambda: None
    sys.modules["isokorb_xt_resolver_245"] = resolver245

    path = RELEASE / "isokorb_xt_resolver_246.py"
    spec = importlib.util.spec_from_file_location("isokorb_xt_resolver_246_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nelze načíst {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert bulk_import.gui_call() == "stale"
    module.install()
    module.selftest()

    assert engine.analyze_bulk_text is bulk_import.analyze_bulk_text
    assert bulk_import.gui_call() == "family-aware"
    assert bulk_import.analyze_bulk_text is not stale

    runtime_text = (RELEASE / "app_runtime.pyw").read_text(encoding="utf-8")
    assert "isokorb_xt_resolver_245.install(_base)" in runtime_text
    assert "isokorb_xt_resolver_246.install(_base)" in runtime_text
    assert "bulk_import.analyze_bulk_text is bulk_import_engine.analyze_bulk_text" in runtime_text

    source245 = (ROOT / "updates" / "2.2.45" / "isokorb_xt_resolver_245.py").read_text(encoding="utf-8")
    for token in (
        '"KL-M3-VV1-REI120-CV1-H240-6.2"',
        '"QL-VV1-REI120-H240-6.0"',
        '"QP-V10-REI120-H240-L500-5.0"',
        '"QP-Z-V7-REI120-H240-L400-5.0"',
        '"ZL-EI120-H240-5.3"',
        "never infer from a failed family/token filter",
    ):
        assert token in source245

    print("OK: TURTO 2.2.46 – GUI bulk-import alias používá aktivní family-aware XT resolver.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
