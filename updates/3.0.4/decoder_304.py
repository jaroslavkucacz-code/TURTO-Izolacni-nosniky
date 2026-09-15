from __future__ import annotations

"""TURTO 3.0.4 - exact handling of additional Schöck schedule syntax.

Recognises only complete T-QP, CXT-AP and XT-KL-O designations.  The module
never invents a capacity and never converts VV to V.  CXT-AP is deliberately
kept on the manufacturer special-design/archive path because the archived
source uses KF/Ft/Fc interaction rather than a simple M/V table.
"""

from dataclasses import dataclass
from functools import wraps
import re
import unicodedata
from typing import Mapping, Any

import bulk_import_engine as engine
import bulk_import
from catalog_engine import DesignationSuggestion

VERSION = "3.0.4"
MISSING = "Označení přečteno, ale chybí odpovídající katalogový záznam."

_DASHES = str.maketrans({"\u2212":"-","\u2010":"-","\u2011":"-","\u2012":"-","\u2013":"-","\u2014":"-"})

@dataclass(frozen=True)
class ExtraDesignation:
    model: str
    family: str
    canonical: str
    fields: Mapping[str, str]
    archive_only: bool = False


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").translate(_DASHES))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().upper().replace(",", ".")


def _surface(value: str) -> str:
    text = str(value or "").translate(_DASHES).replace("\u00a0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"^(?:SCH[ÖO]CK\s+)?ISOKORB(?:\s*[®R])?\s+", "", text, flags=re.I)
    text = re.sub(r"^(T|XT|CXT)\s+TYP(?:E)?\s*(?::|=)?\s*", r"\1-", text, flags=re.I)
    return text.upper().replace(",", ".")


_PATTERNS = (
    ("T", "QP", re.compile(
        r"^T-QP-(?P<shear>V{1,2}\d+)-REI(?P<fire>\d+)-H(?P<height>\d+)-L(?P<length>\d+)-(?P<generation>\d+(?:\.\d+)?)$", re.I)),
    ("XT", "KL-O", re.compile(
        r"^XT-KL-O-M(?P<moment>\d+)-(?P<shear>V{1,2}\d+)-REI(?P<fire>\d+)-CV(?P<cover>\d+)-H(?P<height>\d+)-(?P<generation>\d+(?:\.\d+)?)$", re.I)),
    ("CXT", "AP", re.compile(
        r"^CXT-AP-MM(?P<moment>\d+)-(?P<shear>V{1,2}\d+)-REI(?P<fire>\d+)-LR(?P<lr>\d+)-B(?P<width>\d+)-L(?P<length>\d+)-(?P<generation>\d+(?:\.\d+)?)$", re.I)),
)


def parse_extra_designation(value: str) -> ExtraDesignation | None:
    core = _surface(value)
    for model, family, pattern in _PATTERNS:
        m = pattern.fullmatch(core)
        if not m:
            continue
        fields = {k: str(v).upper().replace(",", ".") for k, v in m.groupdict().items() if v is not None}
        return ExtraDesignation(model, family, core, fields, archive_only=(model == "CXT" and family == "AP"))
    return None


def _height_matches(value: Any, wanted: int) -> bool:
    text = norm(value).replace(" ", "")
    text = re.sub(r"MM$", "", text)
    text = re.sub(r"^H=?", "", text)
    if re.fullmatch(r"\d+", text):
        return int(text) == wanted
    m = re.fullmatch(r"(>=|≥|>|<=|≤|<)(\d+)", text)
    if m:
        op, n = m.group(1), int(m.group(2))
        return {">=":wanted>=n,"≥":wanted>=n,">":wanted>n,"<=":wanted<=n,"≤":wanted<=n,"<":wanted<n}[op]
    m = re.fullmatch(r"(\d+)(?:-|\.\.|…)(\d+)", text)
    return bool(m and int(m.group(1)) <= wanted <= int(m.group(2)))


def _record_length(record: dict[str, Any]) -> int | None:
    values: list[int] = []
    for key in ("element_length_mm", "physical_length_mm", "length_mm", "L_mm"):
        value = record.get(key)
        if value not in (None, "", "—", "-"):
            m = re.fullmatch(r"(?:L\s*=?\s*)?(\d+)(?:\s*MM)?", norm(value))
            if not m:
                return None
            values.append(int(m.group(1)))
    for text in (str(record.get("cover", "")), str(record.get("designation", ""))):
        values.extend(int(v) for v in re.findall(r"(?<![A-Z0-9])L\s*=?\s*(\d+)(?!\d)", norm(text)))
    return values[0] if values and len(set(values)) == 1 else None


def _fire(record: dict[str, Any]) -> set[str]:
    values = set(re.findall(r"(?<![A-Z])(?:REI|EI)\s*\d+", norm(record.get("designation", ""))))
    for key in ("fire_class", "fire_resistance", "fire_rating"):
        if record.get(key):
            values.add(norm(record[key]).replace(" ", ""))
    return {v.replace(" ", "") for v in values}


def _record_matches(parsed: ExtraDesignation, family: dict[str, Any], record: dict[str, Any], concrete: str | None) -> bool:
    f = parsed.fields
    if norm(family.get("manufacturer")) not in {"SCHOCK", "SCHOECK"}:
        return False
    if norm(family.get("model")) != parsed.model:
        return False
    typ = norm(family.get("type"))
    if parsed.family == "KL-O":
        if typ not in {"KL-O", "K-O"}:
            return False
    elif typ != parsed.family:
        return False
    if norm(family.get("generation")) != f["generation"]:
        return False
    if concrete and record.get("concrete_min") not in (None, "", "—", "-") and norm(record.get("concrete_min")) != norm(concrete):
        return False

    if parsed.family == "QP":
        shear = norm(record.get("shear_class")) or norm(record.get("moment_class"))
        if shear != f["shear"]:
            return False
        if _record_length(record) != int(f["length"]):
            return False
    elif parsed.family == "KL-O":
        if norm(record.get("moment_class")) != "M" + f["moment"]:
            return False
        if norm(record.get("shear_class")) != f["shear"]:
            return False
        if norm(record.get("cover")) != "CV" + f["cover"]:
            return False
    if not _height_matches(record.get("height_mm"), int(f["height"])):
        return False
    fire = _fire(record)
    supplied = "REI" + f["fire"]
    if fire and supplied not in fire:
        return False
    return True


def candidates_for(database, parsed: ExtraDesignation, concrete: str | None) -> list[DesignationSuggestion]:
    found: list[DesignationSuggestion] = []
    seen: set[tuple[str, str]] = set()
    for family in getattr(database, "families", []):
        catalog_id = str(family.get("catalog_id", ""))
        catalog = getattr(database, "catalogs", {}).get(catalog_id)
        if not isinstance(catalog, dict):
            continue
        for record in family.get("records", []) if isinstance(family.get("records"), list) else []:
            if not isinstance(record, dict) or not _record_matches(parsed, family, record, concrete):
                continue
            key = (catalog_id, str(record.get("designation", "")))
            if key in seen:
                continue
            seen.add(key)
            from catalog_engine import QueryResult
            found.append(DesignationSuggestion(QueryResult(catalog, family, record), 1000.0))
    return engine.dedupe_suggestions(found)


def classify_extra(database, item, parsed: ExtraDesignation, concrete: str | None) -> None:
    item.result = None
    item.archive_source = None
    item.varying_keys = ()
    item.candidates = []
    if parsed.archive_only:
        source = engine.find_schoeck_archive_source(parsed.canonical)
        if source is None:
            source = next((s for s in engine.load_schoeck_archive_sources() if str(s.get("id")) == "schoeck-cxt-ap-1.0"), None)
        if source:
            item.archive_source = dict(source)
            item.status = "archive"
            item.message = (
                f"Úplné označení {parsed.canonical} bylo rozpoznáno. "
                f"{source.get('edition','Oficiální archiv Schöck')}. "
                f"{source.get('note','')}"
            ).strip()
        else:
            item.status = "error"
            item.message = MISSING + " " + parsed.canonical
        return

    item.candidates = candidates_for(database, parsed, concrete)
    if len(item.candidates) == 1:
        item.result = item.candidates[0].result
        item.status = "exact"
        item.message = "Úplné označení odpovídá právě jednomu katalogovému prvku."
    elif len(item.candidates) > 1:
        item.status = "review"
        item.varying_keys = engine.varying_selector_keys(item.candidates)
        if item.varying_keys:
            labels = ", ".join(engine.SELECTOR_LABELS[k] for k in item.varying_keys)
            item.message = "Úplné označení odpovídá více katalogovým záznamům; nutno rozlišit pouze: " + labels + "."
        else:
            item.message = "Úplné označení odpovídá více různým katalogovým záznamům; ověřte vydání katalogu."
    else:
        item.status = "error"
        item.message = MISSING + f" {parsed.canonical}; beton {concrete or 'neurčen'}. Nejsou nabízeny nesouvisející typy."


def install(_base=None) -> None:
    if getattr(engine, "_turto_decoder_304", False):
        return
    previous = engine._classify_bulk_item

    @wraps(previous)
    def classify(database, item, *, preferred_concrete, suggestion_limit):
        parsed = parse_extra_designation(item.designation)
        if parsed is not None:
            return classify_extra(database, item, parsed, preferred_concrete)
        return previous(database, item, preferred_concrete=preferred_concrete, suggestion_limit=suggestion_limit)

    engine._classify_bulk_item = classify
    bulk_import.analyze_bulk_text_progressive = engine.analyze_bulk_text_progressive
    engine._turto_decoder_304 = True


def selftest() -> None:
    a = parse_extra_designation("T-QP-VV1-REI120-H200-L300-5.0")
    b = parse_extra_designation("CXT-AP-MM1-VV1-REI30-LR200-B200-L300-1.0")
    c = parse_extra_designation("XT-KL-O-M3-V1-REI120-CV1-H250-7.2")
    assert a and (a.model, a.family, a.fields["shear"], a.fields["length"]) == ("T", "QP", "VV1", "300")
    assert b and b.archive_only and b.fields["lr"] == "200" and b.fields["width"] == "200"
    assert c and (c.model, c.family, c.fields["moment"], c.fields["cover"]) == ("XT", "KL-O", "3", "1")
    assert parse_extra_designation("T-QP-VV1-H200-L300-5.0") is None
    assert parse_extra_designation("XT-KL-O-M3-V1-CV1-H250-7.2") is None


if __name__ == "__main__":
    selftest()
