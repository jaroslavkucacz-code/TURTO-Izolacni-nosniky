from __future__ import annotations

"""Separate non-selectable source cover from fixed HIT ZVX/ZDX bottom cover.

Scope: fully specified Schock XT QL 6.0 and QP/QP-Z 5.0 with no supplied CV.
No source cover, catalogue capacity, load, pressure bearing or length is changed.
Target cnom=30 comes from the existing HIT engine, not from a guessed source CV.
Reference: HALFEN HIT 20.2-EN, product type description ZVX/ZDX, printed p.77.
"""
from functools import wraps
import math
import re
import unicodedata

import substitution_workspace as sub
from isokorb_xt_parser_243 import parse_xt_designation

VERSION = "3.0.2"
RULE = "schock_xt_shear_fixed_target_cover_v1"
COVER_ERROR = "krytí musí být jednoznačně 30, 35 nebo 50 mm"
SOURCE_REFERENCE = "HALFEN HIT 20.2-EN, str. 77: ZVX/ZDX – dolní krytí 30 mm, horní nejméně 30 mm."
EXPLANATION = (
    "Zdrojové označení této smykové řady nemá volbu CV; číselné krytí zdroje se nedoplňuje. "
    "Pro návrh HIT ZVX/ZDX je použito pevné dolní krytí 30 mm. "
    "Nejde o potvrzení shodného krytí obou výrobků; požadavky projektu na krytí zůstávají k ověření."
)


def _norm(value):
    text = unicodedata.normalize("NFKD", str("" if value is None else value))
    return "".join(c for c in text if not unicodedata.combining(c)).upper().strip()


def _blank(value):
    return _norm(value) in {"", "-", "—", "–", "NONE"}


def fixed_target_type(row, meta):
    """Return a single allowed shear family, or None (keep all old validation)."""
    selection = row.get("selection") or {}
    snapshot = row.get("snapshot") or {}
    if not isinstance(selection, dict) or not isinstance(snapshot, dict):
        return None
    source = str(row.get("source_text") or snapshot.get("designation", ""))
    parsed = parse_xt_designation(source)
    if parsed is None or (parsed.family, parsed.fields["generation"]) not in {
        ("QL", "6.0"), ("QP", "5.0"), ("QP-Z", "5.0")
    }:
        return None
    if _norm(selection.get("manufacturer")) not in {"SCHOCK", "SCHOECK"}:
        return None
    model = re.sub(r"\s+TYP(?:E)?$", "", _norm(selection.get("model")))
    if (model != "XT" or _norm(selection.get("type_name")) != parsed.family
            or _norm(selection.get("generation")) != parsed.fields["generation"]):
        return None
    if (meta.get("source_cover_mm") is not None or meta.get("source_insulation_mm") != 120
            or meta.get("geometry_target") or meta.get("geometry_origin") == "invalid"):
        return None
    # In the legacy catalogue, QP's selection.cover stores element length, not CV.
    raw_cover = selection.get("cover")
    if not _blank(raw_cover):
        length = re.fullmatch(r"L\s*=?\s*(\d+)\s*(?:MM)?", _norm(raw_cover))
        if length is None or str(int(length.group(1))) != parsed.fields.get("length"):
            return None
    for data in (selection, snapshot, (row.get("mapping") or {}).get("source_overrides") or {}):
        for key in ("source_cover_mm", "target_cover_mm", "cover_mm", "cnom", "cnom_mm", "concrete_cover_mm"):
            if not _blank(data.get(key)):
                return None
    # Never override a cover requirement deliberately supplied in a note.
    if re.search(r"(?<![A-Z])(?:CV|CNOM|C_NOM|KRYTI|COVER|C\s*=)", _norm(row.get("note"))):
        return None
    actions, warnings = sub.source_actions(row)
    values = sub.action_values(actions)
    if warnings or not all(math.isfinite(x) for x in values.values()):
        return None
    if any(values[k] > sub._TOL for k in ("m_pos", "m_neg", "n_pos", "n_neg")):
        return None
    # Do not let the legacy float parser silently discard malformed load values.
    for result in snapshot.get("results", []):
        if not isinstance(result, dict):
            return None
        if result.get("kind") not in {"moment", "normal", "shear"}:
            continue
        for key in ("value", "positive", "negative"):
            if result.get(key) not in (None, ""):
                try:
                    if not math.isfinite(float(str(result[key]).replace(",", "."))):
                        return None
                except (ValueError, TypeError):
                    return None
    both = parsed.fields["shear"].startswith("VV")
    if (values["v_pos"] <= sub._TOL or (both and values["v_neg"] <= sub._TOL)
            or (not both and values["v_neg"] > sub._TOL)):
        return None
    expected_pressure = "without" if parsed.family == "QP-Z" else "bearing"
    if meta.get("source_compression_category") != expected_pressure:
        return None
    return "ZDX" if both else "ZVX"


class _ShearDatabase:
    """Delegate unchanged mechanics; do not reuse inferred cover for moment types."""
    def __init__(self, database, allowed_type):
        self._database, self._allowed_type = database, allowed_type

    def __getattr__(self, name):
        return getattr(self._database, name)

    def proposal_candidates(self, connection_type, *args, **kwargs):
        if connection_type != self._allowed_type:
            return [], "", {}
        candidates, error, info = self._database.proposal_candidates(connection_type, *args, **kwargs)
        candidates = [c for c in candidates if c.connection_type == self._allowed_type and c.cover == 30]
        return candidates, error, info


def install(base):
    if getattr(sub, "_turto_shear_cover_302", False):
        return
    previous_meta, previous_design = sub.source_metadata, sub.design_targets
    previous_calculation = sub.calculation

    @wraps(previous_meta)
    def metadata(row):
        meta = previous_meta(row)
        typ = fixed_target_type(row, meta)
        if typ:
            meta = dict(meta)
            meta.update(target_cover_mm=30, cover_resolution=RULE, fixed_shear_type=typ,
                        cover_resolution_note=EXPLANATION, cover_resolution_reference=SOURCE_REFERENCE)
            meta["errors"] = [e for e in meta.get("errors", []) if e != COVER_ERROR]
        return meta

    @wraps(previous_design)
    def design(database, *, row, metadata, allowed_length_codes=None):
        live = sub.source_metadata(row)
        if live.get("cover_resolution") == RULE:
            if live.get("errors"):
                return [], list(live["errors"])
            targets, errors = previous_design(_ShearDatabase(database, live["fixed_shear_type"]),
                row=row, metadata=live, allowed_length_codes=allowed_length_codes)
            if not targets and not errors:
                errors = [f"Nenalezen vyhovující {live['fixed_shear_type']} při pevném dolním krytí 30 mm; "
                          "ověřte načtená data HIT, únosnost, délku, výšku, beton a tlaková ložiska."]
            return targets, errors
        if metadata.get("cover_resolution") == RULE:
            return [], list(live.get("errors", [])) or ["Změnily se parametry zdroje; pevné krytí HIT nelze převzít ze starého návrhu."]
        return previous_design(database, row=row, metadata=metadata, allowed_length_codes=allowed_length_codes)

    @wraps(previous_calculation)
    def calculation(candidate, target_actions, source_totals, metadata):
        text = previous_calculation(candidate, target_actions, source_totals, metadata)
        if metadata.get("cover_resolution") == RULE:
            text = text.replace(f"cnom {metadata.get('source_cover_mm')}→{candidate.cover} mm",
                                f"cnom zdroj dle provedení; HIT {candidate.cover} mm (pevné dolní krytí)")
            text += " | " + EXPLANATION
        return text

    sub.source_metadata, sub.design_targets, sub.calculation = metadata, design, calculation
    cls = base.ThermalConnectorApp
    previous_payload, previous_header = cls._payload, cls._build_header

    @wraps(previous_payload)
    def payload(self, row):
        result, status = previous_payload(self, row)
        meta = sub.source_metadata(row)
        if meta.get("cover_resolution") == RULE:
            result["source_cover"] = "dle typu"
            target = sub.selected_target(row.get("mapping") or {})
            if target is None or target.get("connection_type") in {"ZVX", "ZDX"}:
                result["target_cover"] = "30 mm (pevné)"
            result["note"] = " • ".join(x for x in (result.get("note", ""), EXPLANATION) if x)
        return result, status

    @wraps(previous_header)
    def header(self):
        previous_header(self)
        title = getattr(self, "_turto_brand_title", None)
        if title is not None:
            title.configure(text="TURTO 3.0.2 | Izolační nosníky a smykové trny")

    cls._payload, cls._build_header = payload, header
    sub._turto_shear_cover_302 = True


def selftest():
    assert VERSION == "3.0.2"
    assert getattr(sub, "_turto_shear_cover_302", False)
