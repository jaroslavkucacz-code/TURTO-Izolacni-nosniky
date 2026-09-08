from __future__ import annotations

"""TURTO 2.2.6 – safety guard for substitutions to Leviat HIT.

The compatibility layer keeps the verified calculation engine intact and only
adds source metadata that must be known before an automatic one-to-one
substitution is allowed. In particular it prevents a geometrically special
source element from silently falling back to a plain HIT-MVX.
"""

import re
import unicodedata
from typing import Any

VERSION = "2.2.6"


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.upper().replace("−", "-").replace("–", "-")).strip()


def _selection(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("selection")
    return value if isinstance(value, dict) else {}


def _snapshot(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("snapshot")
    return value if isinstance(value, dict) else {}


def _source_text(row: dict[str, Any], source_text: str = "") -> str:
    selection = _selection(row)
    snapshot = _snapshot(row)
    return _norm(
        " | ".join(
            (
                str(selection.get("manufacturer", "")),
                str(selection.get("model", "")),
                str(selection.get("type_name", "")),
                str(source_text or row.get("source_text") or snapshot.get("designation", "")),
                str(row.get("note", "")),
            )
        )
    )


def _is_schoeck_t_xt(selection: dict[str, Any], source_text: str) -> bool:
    manufacturer = _norm(selection.get("manufacturer", ""))
    model = _norm(selection.get("model", ""))
    source = _norm(source_text)
    if "SCHOCK" not in manufacturer and "SCHOCK" not in source:
        return False
    return model in {"T", "XT"} or bool(re.search(r"\b(?:ISOKORB\s*)?(?:T|XT)\b", source))


def _schoeck_cover(selection: dict[str, Any], source_text: str) -> int | None:
    if not _is_schoeck_t_xt(selection, source_text):
        return None
    combined = _norm(f"{selection.get('cover', '')} {source_text}")
    if re.search(r"(?:^|[-\s])CV\s*1(?:[-\s/]|$)", combined):
        return 35
    if re.search(r"(?:^|[-\s])CV\s*2(?:[-\s/]|$)", combined):
        return 50
    return None


def _schoeck_geometry_requirement(row: dict[str, Any], source_text: str = "") -> tuple[str, str, str]:
    """Return (HIT geometry, source label, fatal special-case reason)."""
    selection = _selection(row)
    combined = _source_text(row, source_text)
    if not _is_schoeck_t_xt(selection, combined):
        return "", "", ""

    # These are not one-piece standard cantilever details. The current HIT
    # substitution engine does not preserve their assembly / installation
    # concept, therefore automatic substitution must stop rather than guess.
    if re.search(r"\b(?:CL|C)-(?:L|R)\b|\bZ-C\b", combined):
        return "", "", "rohový Schöck Isokorb vyžaduje samostatné řešení; automatická záměna 1:1 za standardní HIT není povolena"
    if re.search(r"\b(?:KL|K)(?:-(?:O|U|WO|WU))?-F\b", combined):
        return "", "", "dvoukomponentní prefabrikované provedení Schöck -F vyžaduje ruční ověření montážního řešení; standardní HIT se nesmí zvolit automaticky"
    if re.search(r"\b(?:KL|K)-ID\b", combined):
        return "", "", "dodatečně instalované provedení Schöck K-ID není ekvivalent standardního monolitického HIT; záměna musí být řešena ručně"

    mappings = (
        (r"\b(?:KL|K)-WO\b", "OU", "K-WO"),
        (r"\b(?:KL|K)-WU\b", "OD", "K-WU"),
        (r"\b(?:KL|K)-O\b", "OU", "K-O"),
        (r"\b(?:KL|K)-U\b", "OD", "K-U"),
    )
    for pattern, target, label in mappings:
        if re.search(pattern, combined):
            return target, label, ""
    return "", "", ""


def _positive_int(value: Any) -> int | None:
    if value in (None, "", "—", "-"):
        return None
    match = re.search(r"\d{2,4}", str(value))
    if not match:
        return None
    number = int(match.group(0))
    return number if number > 0 else None


def _explicit_bx(row: dict[str, Any], source_text: str = "") -> int | None:
    """Read an actual component thickness, never a minimum requirement w >= ... ."""
    selection = _selection(row)
    snapshot = _snapshot(row)
    for container in (selection, snapshot):
        for key in (
            "geometry_bx_mm",
            "component_width_mm",
            "wall_width_mm",
            "wall_thickness_mm",
            "beam_width_mm",
            "beam_thickness_mm",
        ):
            value = _positive_int(container.get(key))
            if value:
                return value

    combined = _norm(f"{source_text} | {row.get('note', '')}")
    patterns = (
        r"\bBX\s*[:=]\s*(\d{2,4})\s*MM\b",
        r"\bW\s*=\s*(\d{2,4})\s*MM\b",
        r"\b(?:WALL THICKNESS|WALL WIDTH|BEAM WIDTH|BEAM THICKNESS|WANDDICKE|WANDSTAERKE)\s*[:=]\s*(\d{2,4})\s*MM\b",
    )
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            return int(match.group(1))
    return None


def _generic_geometry_marker(text: str) -> bool:
    return bool(re.search(r"(?:^|[-\s])(OU|OD|WU|WD|WO|HVS|WOS|WUS|BHS|BH)(?=[-\s]|$)", _norm(text)))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value).strip()))


def _target_has_geometry(target: dict[str, Any], expected: str, bx: int | None) -> bool:
    designation = _norm(target.get("designation", ""))
    if not expected:
        return True
    if not re.search(rf"-{re.escape(expected)}\s*\d+\b", designation):
        return False
    if bx:
        return bool(re.search(rf"-{re.escape(expected)}\s*{int(bx)}\b", designation))
    return False


def install(app_base: Any = None) -> None:
    import substitution_workspace as sub

    if getattr(sub, "_turto_substitution_guard_226_installed", False):
        return

    original_cover = sub._source_cover
    original_compression = sub._source_compression
    original_geometry = sub._source_geometry
    original_metadata = sub.source_metadata

    def source_cover(selection: dict[str, Any], source_text: str) -> int | None:
        value = original_cover(selection, source_text)
        if value in {30, 35, 50}:
            return value
        mapped = _schoeck_cover(selection, source_text)
        return mapped if mapped is not None else value

    def source_compression(row: dict[str, Any], source_text: str):
        category, text, warnings = original_compression(row, source_text)
        if category != "unknown":
            return category, text, warnings
        selection = _selection(row)
        combined = _source_text(row, source_text)
        if _is_schoeck_t_xt(selection, combined) and re.search(
            r"\b(?:KL|KP|K)(?:-(?:O|U|WO|WU))?(?:-F)?\b", combined
        ):
            return "bearing", "s tlakovými ložisky HTE-Compact®", list(warnings)
        return category, text, warnings

    def source_geometry(row: dict[str, Any], source_text: str):
        base = original_geometry(row, source_text)
        expected, label, special = _schoeck_geometry_requirement(row, source_text)
        if special or not expected:
            return base

        # Preserve any explicit/manual geometry; metadata validation below will
        # reject the wrong direction or an unsafe 'Bez OU/OD' override.
        target, bx, display, warnings, confirmed, origin = base
        if target or origin in {"manual", "confirmed_auto", "manual_none", "invalid"}:
            return base

        actual_bx = _explicit_bx(row, source_text)
        if actual_bx:
            return (
                expected,
                actual_bx,
                f"Schöck {label} → {expected}{actual_bx} • čeká na potvrzení",
                [f"geometrie {expected}{actual_bx} byla odvozena z typu Schöck a skutečného bx; před potvrzením zůstává ve stavu KONTROLA"],
                False,
                "automatic",
            )
        return (
            expected,
            None,
            f"Schöck {label} → {expected} • doplňte skutečné bx",
            ["Schöck uvádí u tohoto typu minimální šířku w; pro objednací geometrii HIT je nutná skutečná tloušťka stěny/průvlaku bx"],
            False,
            "required_bx",
        )

    sub._source_cover = source_cover
    sub._source_compression = source_compression
    sub._source_geometry = source_geometry

    def source_metadata(row: dict[str, Any]) -> dict[str, Any]:
        meta = dict(original_metadata(row))
        source_text = str(meta.get("source_text", "") or "")
        expected, label, special = _schoeck_geometry_requirement(row, source_text)
        errors = list(meta.get("errors", []))
        warnings = list(meta.get("warnings", []))

        if special:
            errors.append(special)
        elif expected:
            actual = str(meta.get("geometry_target", "") or "").upper()
            bx = _positive_int(meta.get("geometry_bx_mm"))
            if actual != expected:
                errors.append(
                    f"Schöck {label} vyžaduje odpovídající HIT-MVX-{expected}; provedení bez {expected} nebo opačná geometrie nejsou přípustné"
                )
            if not bx:
                errors.append(
                    f"pro Schöck {label} je nutné zadat skutečnou tloušťku stěny/průvlaku bx; údaj w ≥ … mm je pouze minimální požadavek, nikoli objednací bx HIT"
                )

        origin = str(meta.get("geometry_origin", "") or "")
        if origin == "unsupported":
            errors.append(
                "zdroj obsahuje geometrickou variantu, pro kterou TURTO nemá ověřené přiřazení OU/OD; automatická záměna byla z bezpečnostních důvodů zastavena"
            )
        if meta.get("geometry_target") and not _positive_int(meta.get("geometry_bx_mm")):
            errors.append("geometrická záměna OU/OD vyžaduje skutečný kladný rozměr bx")

        combined = f"{source_text} | {row.get('note', '')}"
        if not meta.get("geometry_target") and origin == "none" and _generic_geometry_marker(combined):
            errors.append(
                "v označení je geometrický kód, ale chybí jednoznačný rozměr/převod; standardní HIT bez geometrie se nesmí použít automaticky"
            )

        meta["errors"] = _dedupe(errors)
        meta["warnings"] = _dedupe(warnings)
        return meta

    sub.source_metadata = source_metadata

    cls = sub.SubstitutionWorkspaceMixin
    original_refresh = cls.refresh_substitution_tree

    def unsafe_mapping(row: dict[str, Any]) -> bool:
        mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
        targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []
        selected_id = str(mapping.get("selected_target_id") or "")
        target = next(
            (item for item in targets if isinstance(item, dict) and str(item.get("id")) == selected_id),
            next((item for item in targets if isinstance(item, dict)), None),
        )
        if not isinstance(target, dict):
            return False
        meta = source_metadata(row)
        expected, _label, special = _schoeck_geometry_requirement(row, str(meta.get("source_text", "")))
        if special or str(meta.get("geometry_origin", "")) == "unsupported":
            return True
        if expected:
            return not _target_has_geometry(target, expected, _positive_int(meta.get("geometry_bx_mm")))
        if meta.get("geometry_target"):
            return not _target_has_geometry(
                target,
                str(meta.get("geometry_target")),
                _positive_int(meta.get("geometry_bx_mm")),
            )
        return False

    def refresh(self) -> None:
        for row in list(getattr(getattr(self, "project", None), "rows", []) or []):
            if not unsafe_mapping(row):
                continue
            mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
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
        original_refresh(self)

    cls.refresh_substitution_tree = refresh
    sub._turto_substitution_guard_226_installed = True


def selftest() -> None:
    klo = {
        "selection": {"manufacturer": "Schöck", "model": "T", "type_name": "KL-O", "cover": "CV1"},
        "snapshot": {"designation": "Schöck Isokorb T typ KL-O-M2-V1-CV1-H160-7.2"},
        "note": "w ≥ 175 mm",
    }
    assert _schoeck_geometry_requirement(klo, "")[0] == "OU"
    assert _explicit_bx(klo, "") is None  # w_min must never become bx automatically
    klo["note"] = "w ≥ 175 mm; bx=210 mm"
    assert _explicit_bx(klo, "") == 210
    assert _schoeck_cover(klo["selection"], klo["snapshot"]["designation"]) == 35

    klu = {
        "selection": {"manufacturer": "Schöck", "model": "XT", "type_name": "KL-U"},
        "snapshot": {"designation": "Schöck Isokorb XT typ KL-U-M2-V1-CV2-H200"},
    }
    assert _schoeck_geometry_requirement(klu, "")[0] == "OD"
    assert _schoeck_cover({**klu["selection"], "cover": "CV2"}, klu["snapshot"]["designation"]) == 50

    corner = {
        "selection": {"manufacturer": "Schöck", "model": "XT", "type_name": "CL-L"},
        "snapshot": {"designation": "Schöck Isokorb XT typ CL-L-M1-V1-CV1-H200"},
    }
    assert _schoeck_geometry_requirement(corner, "")[2]
    assert _generic_geometry_marker("ISOPRO WU")


if __name__ == "__main__":
    selftest()
