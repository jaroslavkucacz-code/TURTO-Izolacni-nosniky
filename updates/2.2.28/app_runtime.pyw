from __future__ import annotations

"""TURTO 2.2.28 runtime – Peikko EBEA/TEBEA identification with safe substitution guard."""

import runpy
from pathlib import Path

APP_VERSION = "2.2.28"
BASE_RUNTIME = Path(__file__).with_name("app_runtime_227.pyw")

if not BASE_RUNTIME.is_file():
    raise RuntimeError(f"Chybí ověřený runtime základ 2.2.27: {BASE_RUNTIME}")

_namespace = runpy.run_path(str(BASE_RUNTIME), run_name="turto_app_runtime_227")
_base = _namespace.get("_base")
_hit_workspace = _namespace.get("_hit_workspace") or _namespace.get("hit_workspace")

if _base is None:
    raise RuntimeError("Runtime 2.2.27 neposkytl app_base.")

import peikko_connectors as _peikko
import substitution_workspace as _substitution_workspace

if _peikko.MODULE_VERSION != APP_VERSION:
    raise RuntimeError(
        f"Nesouhlasí verze Peikko dekodéru: {_peikko.MODULE_VERSION}; očekáváno {APP_VERSION}."
    )

_ORIGINAL_COLLECT_SOURCE_ACTIONS_228 = getattr(
    _substitution_workspace, "_turto_original_collect_source_actions_228", None
)
if _ORIGINAL_COLLECT_SOURCE_ACTIONS_228 is None:
    _ORIGINAL_COLLECT_SOURCE_ACTIONS_228 = _substitution_workspace._collect_source_actions
    _substitution_workspace._turto_original_collect_source_actions_228 = _ORIGINAL_COLLECT_SOURCE_ACTIONS_228


def _peikko_guarded_collect_source_actions_228(
    row,
    *,
    per_m_factor: float,
    per_element_factor: float,
):
    selection = row.get("selection") if isinstance(row, dict) and isinstance(row.get("selection"), dict) else {}
    snapshot = row.get("snapshot") if isinstance(row, dict) and isinstance(row.get("snapshot"), dict) else {}
    source_text = row.get("source_text", "") if isinstance(row, dict) else ""
    combined = " ".join(
        str(value or "")
        for value in (
            selection.get("manufacturer"),
            selection.get("model"),
            selection.get("type_name"),
            selection.get("type"),
            snapshot.get("designation"),
            source_text,
        )
    )
    decoded = _peikko.decode_peikko_designation(combined)
    if decoded.get("recognized"):
        reason = _peikko.substitution_block_reason(decoded)
        raise RuntimeError(reason or _peikko.UNVERIFIED_STATUS)
    return _ORIGINAL_COLLECT_SOURCE_ACTIONS_228(
        row,
        per_m_factor=per_m_factor,
        per_element_factor=per_element_factor,
    )


_substitution_workspace._collect_source_actions = _peikko_guarded_collect_source_actions_228

try:
    _base.APP_VERSION = APP_VERSION
    _base.APP_NAME = "TURTO"
except Exception:
    pass

try:
    if _hit_workspace is not None:
        _hit_workspace.HIT_MODULE_VERSION = APP_VERSION
        if hasattr(_hit_workspace, "_base"):
            _hit_workspace._base.HIT_MODULE_VERSION = APP_VERSION
except Exception:
    pass

try:
    import platform_workspace as _platform_workspace
    _platform_workspace.WORKSPACE_VERSION = APP_VERSION
except Exception:
    pass


def selftest() -> None:
    _peikko.selftest()
    d = _peikko.decode_peikko_designation("Peikko TEBEA CM-V 120 mm")
    assert d["recognized"] and d["function_class"] == "moment_shear"
    assert d["verified_capacity"] is False
    try:
        _peikko_guarded_collect_source_actions_228(
            {"source_text": "Peikko EBEA 100 80 mm"},
            per_m_factor=1.0,
            per_element_factor=1.0,
        )
    except RuntimeError as exc:
        assert "statické ověření" in str(exc)
    else:
        raise AssertionError("Peikko source was not blocked from automatic substitution.")


if __name__ == "__main__":
    raise SystemExit(_base.main())
