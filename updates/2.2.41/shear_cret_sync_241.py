from __future__ import annotations
"""TURTO 2.2.41 – keep CRET 05/2026 source VRd through substitutions.

TURTO 2.2.39 installed the current CRET calculation route, but the older
2.2.37 add/recalculate/sync methods had captured their substitution function
in closures. Decoder rows therefore could be recalculated by the obsolete
route when copied to Substitutions. This overlay keeps the original UI
workflow and then re-evaluates CRET rows through the current dynamic
substitution function.
"""
from typing import Any

LOGIC_VERSION = 241
_INSTALLED = False

def _cret_row(row: dict[str, Any]) -> bool:
    try:
        import cret_series_100_239 as cret
        return bool(cret.decode_designation(str(row.get("source_designation", "") or "")))
    except Exception:
        return False

def _dynamic(owner: Any, row: dict[str, Any], target: str) -> dict[str, Any]:
    fn = getattr(owner, "_turto_substitution_237", None)
    if not callable(fn):
        import shear_dowels_ui_215 as ui215
        fn = ui215._substitution_from_values
    result = fn(dict(row), target)
    return result if isinstance(result, dict) else dict(row)

def _repair_cret_rows(owner: Any, *, only_decoder: bool = False, start: int = 0) -> int:
    rows = getattr(owner, "shear_substitution_rows", None)
    if not isinstance(rows, list):
        return 0
    try:
        target = owner.shear_target_manufacturer_var.get()
    except Exception:
        target = "Ancon"
    changed = 0
    for index in range(max(0, int(start)), len(rows)):
        row = rows[index]
        if not isinstance(row, dict):
            continue
        if only_decoder and row.get("origin") != "decoder":
            continue
        if not _cret_row(row):
            continue
        rows[index] = _dynamic(owner, row, target)
        changed += 1
    return changed

def _refresh(owner: Any) -> None:
    try:
        import shear_dowels_ui_214 as ui214
        ui214._mark(owner)
    except Exception:
        try:
            owner.mark_project_dirty()
        except Exception:
            pass
    try:
        owner.refresh_shear_tables()
    except Exception:
        pass

def install(app_base: Any) -> None:
    global _INSTALLED
    cls = app_base.ThermalConnectorApp
    if getattr(cls, "_turto_cret_sync_241", False):
        _INSTALLED = True
        return
    stale_sync = cls.sync_shear_substitutions_from_decoder
    stale_recalc = cls.recalculate_shear_substitutions_all
    stale_add = cls.add_shear_substitution_row

    def sync(owner: Any) -> None:
        stale_sync(owner)
        if _repair_cret_rows(owner, only_decoder=True):
            _refresh(owner)

    def recalc(owner: Any) -> None:
        stale_recalc(owner)
        if _repair_cret_rows(owner):
            _refresh(owner)

    def add(owner: Any) -> None:
        rows = getattr(owner, "shear_substitution_rows", None)
        before = len(rows) if isinstance(rows, list) else 0
        stale_add(owner)
        rows = getattr(owner, "shear_substitution_rows", None)
        after = len(rows) if isinstance(rows, list) else 0
        if after > before and _repair_cret_rows(owner, start=before):
            _refresh(owner)

    cls.sync_shear_substitutions_from_decoder = sync
    cls.recalculate_shear_substitutions_all = recalc
    cls.add_shear_substitution_row = add
    cls._turto_cret_sync_241 = True
    _INSTALLED = True

def selftest() -> None:
    assert LOGIC_VERSION == 241
    assert callable(_cret_row)
    assert callable(_dynamic)
    assert callable(_repair_cret_rows)

if __name__ == "__main__":
    selftest()
