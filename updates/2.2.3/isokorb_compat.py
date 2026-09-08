from __future__ import annotations

"""TURTO 2.2.3 – compatibility rules for Schöck Isokorb source metadata.

This module does not change source catalog values. It translates published
Schöck variant codes used by the decoder into the explicit metadata required
by the HIT substitution engine.
"""

from copy import deepcopy
import re
from typing import Any

_CV_COVER = {"CV1": 35, "CV2": 50}
_STALE_COVER_ERROR = "krytí musí být jednoznačně 30, 35 nebo 50 mm"
_STALE_COMPRESSION_ERROR = "není jednoznačné, zda je původní prvek s tlakovými ložisky, nebo bez nich"


def _ascii_upper(value: Any) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).upper().replace("–", "-").replace("—", "-")


def is_schoeck_klo(selection: dict[str, Any], source_text: str = "") -> bool:
    manufacturer = _ascii_upper(selection.get("manufacturer", ""))
    model = _ascii_upper(selection.get("model", ""))
    type_name = _ascii_upper(selection.get("type_name", ""))
    source = _ascii_upper(source_text)
    if "SCHOCK" not in manufacturer and "SCHOECK" not in manufacturer and "ISOKORB" not in source:
        return False
    type_match = type_name in {"KL-O", "K-O"} or bool(re.search(r"\b(?:KL-O|K-O)\b", source))
    model_match = model in {"T", "XT", ""} or bool(re.search(r"\b(?:T|XT)\b", source))
    return bool(type_match and model_match)


def schoeck_cover_mm(selection: dict[str, Any], source_text: str = "") -> int | None:
    if not is_schoeck_klo(selection, source_text):
        return None
    joined = f"{selection.get('cover', '')} {source_text}".upper().replace(" ", "")
    for code, cover in _CV_COVER.items():
        if code in joined:
            return cover
    return None


def schoeck_compression(
    selection: dict[str, Any],
    source_text: str = "",
) -> tuple[str, str, list[str]] | None:
    if not is_schoeck_klo(selection, source_text):
        return None
    return (
        "bearing",
        "s tlakovými ložisky HTE-Compact®",
        [],
    )


def enriched_detail_row(row: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(row)
    selection = result.get("selection") if isinstance(result.get("selection"), dict) else {}
    snapshot = result.get("snapshot") if isinstance(result.get("snapshot"), dict) else {}
    source_text = str(result.get("source_text") or snapshot.get("designation", "") or "")
    if not is_schoeck_klo(selection, source_text):
        return result

    cover = schoeck_cover_mm(selection, source_text)
    raw_cover = str(selection.get("cover", "") or "").strip()
    if cover:
        code = next((code for code in _CV_COVER if code in raw_cover.upper()), "")
        suffix = ""
        if "·" in raw_cover:
            suffix = raw_cover.split("·", 1)[1].strip()
        elif "•" in raw_cover:
            suffix = raw_cover.split("•", 1)[1].strip()
        label = f"{code} = {cover} mm" if code else f"{cover} mm"
        if suffix:
            label += f" · {suffix}"
        selection["cover"] = label
    snapshot["compression_transfer"] = "HTE-Compact® – s tlakovými ložisky"
    result["selection"] = selection
    result["snapshot"] = snapshot
    return result


def _mapping_errors(mapping: dict[str, Any]) -> list[str]:
    errors = mapping.get("errors") if isinstance(mapping.get("errors"), list) else []
    selected = str(mapping.get("selected_target_id") or "")
    if selected and str(mapping.get("status", "")) == "error":
        errors = [*errors, *selected.split(" | ")]
    return [str(value) for value in errors]


def migrate_stale_mapping(row: dict[str, Any]) -> bool:
    selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    source_text = str(row.get("source_text") or snapshot.get("designation", "") or "")
    if not is_schoeck_klo(selection, source_text):
        return False
    mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
    if not mapping:
        return False
    errors = _mapping_errors(mapping)
    stale = any(_STALE_COVER_ERROR in value for value in errors) or any(
        _STALE_COMPRESSION_ERROR in value for value in errors
    )
    if not stale:
        return False

    overrides = dict(mapping.get("source_overrides", {})) if isinstance(mapping.get("source_overrides"), dict) else {}
    row["mapping"] = {
        "status": "not_run",
        "targets": [],
        "selected_target_id": None,
        "source_meta": {},
        "warnings": [],
        "errors": [],
        "estimated_type": "",
        "diameter_availability": {},
        "source_overrides": overrides,
    }
    return True


def install(app_base: Any | None = None) -> None:
    import decoder_detail
    import substitution_workspace as substitution

    if getattr(substitution, "_turto_isokorb_223_installed", False):
        return

    original_cover = substitution._source_cover
    original_compression = substitution._source_compression

    def source_cover(selection: dict[str, Any], source_text: str) -> int | None:
        value = original_cover(selection, source_text)
        if value in {30, 35, 50}:
            return value
        mapped = schoeck_cover_mm(selection, source_text)
        return mapped if mapped is not None else value

    def source_compression(row: dict[str, Any], source_text: str):
        category, label, warnings = original_compression(row, source_text)
        if category != "unknown":
            return category, label, warnings
        selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
        mapped = schoeck_compression(selection, source_text)
        return mapped if mapped is not None else (category, label, warnings)

    substitution._source_cover = source_cover
    substitution._source_compression = source_compression

    mixin = substitution.SubstitutionWorkspaceMixin
    original_refresh = mixin.refresh_substitution_tree

    def refresh_substitution_tree(self) -> None:
        try:
            for row in getattr(self.project, "rows", []):
                if isinstance(row, dict):
                    migrate_stale_mapping(row)
        except Exception:
            pass
        original_refresh(self)

    mixin.refresh_substitution_tree = refresh_substitution_tree

    OriginalDetail = decoder_detail.DecoderDetailDialog

    class DecoderDetailDialog223(OriginalDetail):
        def __init__(self, owner: Any, row: dict[str, Any]) -> None:
            try:
                migrate_stale_mapping(row)
            except Exception:
                pass
            super().__init__(owner, enriched_detail_row(row))

    decoder_detail.DecoderDetailDialog = DecoderDetailDialog223
    substitution._turto_isokorb_223_installed = True


def selftest() -> None:
    selection = {
        "manufacturer": "Schöck",
        "model": "T",
        "type_name": "KL-O",
        "cover": "CV1 · w ≥ 210 mm",
    }
    source = "Schöck Isokorb® T typ KL-O-M1-V1-CV1-H240-7.2-w ≥ 210 mm"
    assert is_schoeck_klo(selection, source)
    assert schoeck_cover_mm(selection, source) == 35
    selection2 = dict(selection, cover="CV2")
    assert schoeck_cover_mm(selection2, source.replace("CV1", "CV2")) == 50
    category = schoeck_compression(selection, source)
    assert category and category[0] == "bearing"

    unrelated = {
        "manufacturer": "Schöck",
        "model": "T",
        "type_name": "XYZ",
        "cover": "CV1",
    }
    assert schoeck_cover_mm(unrelated, "Schöck XYZ CV1") is None


if __name__ == "__main__":
    selftest()
