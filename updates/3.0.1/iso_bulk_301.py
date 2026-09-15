from __future__ import annotations

"""Exact XT classification in the real progressive import path.

Reads existing catalogue records; does not add capacities, change catalogue
files, or replace VV by V. A complete code must never fall back to fuzzy hits.
The stored catalogue selection remains unchanged so SQLite round trips still
resolve the original static row (including a tabulated height range).
"""

from copy import deepcopy
from functools import wraps
import json
import re
import unicodedata

import bulk_import_engine as engine
import bulk_import
from catalog_engine import QueryResult, DesignationSuggestion
from isokorb_xt_parser_243 import parse_xt_designation

VERSION = "3.0.1"
MISSING = "Označení přečteno, ale chybí odpovídající katalogový záznam."
EMPTY = {"", "-", "—", "–", "NONE"}


def norm(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.upper().strip().replace(",", ".").replace("–", "-").replace("−", "-")


def height_matches(value, wanted):
    """Match the entire dedicated height field, never a number elsewhere."""
    text = norm(value).replace(" ", "")
    text = re.sub(r"MM$", "", text)
    text = re.sub(r"^H=?", "", text)
    if re.fullmatch(r"\d+", text):
        return int(text) == wanted
    match = re.fullmatch(r"(>=|≥|>|<=|≤|<)(\d+)", text)
    if match:
        op, number = match.group(1), int(match.group(2))
        return {">=": wanted >= number, "≥": wanted >= number, ">": wanted > number,
                "<=": wanted <= number, "≤": wanted <= number, "<": wanted < number}[op]
    match = re.fullmatch(r"(\d+)(?:-|\.\.|…)(\d+)", text)
    if match:
        return int(match.group(1)) <= wanted <= int(match.group(2))
    if re.fullmatch(r"\d+(?:[/;]\d+)+", text):
        return wanted in [int(x) for x in re.split(r"[/;]", text)]
    return False


def _length(record):
    values = []
    for key in ("element_length_mm", "physical_length_mm", "length_mm", "L_mm"):
        value = record.get(key)
        if value is not None and str(value).strip() not in EMPTY:
            match = re.fullmatch(r"(?:L\s*=?\s*)?(\d+)(?:\s*mm)?", str(value), re.I)
            if not match:
                return None
            values.append(int(match.group(1)))
    for text in (str(record.get("cover", "")), str(record.get("designation", ""))):
        values.extend(int(x) for x in re.findall(r"(?<![A-Z0-9])L\s*=?\s*(\d+)(?!\d)", text.upper()))
    return values[0] if values and len(set(values)) == 1 else None


def _fire(record):
    # A static table may intentionally omit the fire option. Preserve the input
    # but never claim that a static-capacity lookup verifies fire resistance.
    codes = set(re.findall(r"(?<![A-Z])(?:REI|EI)\s*\d+", str(record.get("designation", "")).upper()))
    for key in ("fire_class", "fire_resistance", "fire_rating"):
        if record.get(key):
            codes.add(norm(record[key]).replace(" ", ""))
    return {x.replace(" ", "") for x in codes}


def _record_matches(family, record, parsed, concrete):
    f = parsed.fields
    if not all(key in record for key in ("moment_class", "shear_class", "cover", "height_mm", "concrete_min")):
        return False
    if not isinstance(record.get("results"), list) or not record["results"]:
        return False
    if concrete and norm(record.get("concrete_min")) != norm(concrete):
        return False
    if parsed.family == "KL":
        if norm(record.get("moment_class")) != "M" + f["moment"]:
            return False
        if norm(record.get("shear_class")) != f["shear"]:
            return False
        if norm(record.get("cover")) != "CV" + f["cover"]:
            return False
    elif parsed.family in {"QL", "QP", "QP-Z"}:
        # Original Schöck schema stores V/VV in class 1 for pure shear families.
        shear = norm(record.get("shear_class"))
        if shear in EMPTY:
            shear = norm(record.get("moment_class"))
        if shear != f["shear"]:
            return False
    if parsed.family in {"QP", "QP-Z"} and _length(record) != int(f["length"]):
        return False
    wanted = int(f["height"])
    if not height_matches(record.get("height_mm"), wanted):
        return False
    for limits in (family, record):
        for key, valid in (("height_min", lambda h: wanted >= h), ("height_max", lambda h: wanted <= h)):
            if limits.get(key) not in (None, ""):
                try:
                    if not valid(float(limits[key])):
                        return False
                except (TypeError, ValueError):
                    return False
    supplied_fire = ("EI" if parsed.family == "ZL" else "REI") + f["fire"]
    fire = _fire(record)
    if fire and fire != {supplied_fire}:
        return False
    return True


def candidates_for(database, parsed, concrete):
    matches = []
    seen = set()
    for family in database.families:
        if norm(family.get("manufacturer")) not in {"SCHOCK", "SCHOECK"}:
            continue
        if norm(family.get("model")) != "XT" or norm(family.get("type")) != parsed.family:
            continue
        if norm(family.get("generation")) != parsed.fields["generation"]:
            continue
        if family.get("backend") == "matrix":
            continue  # unknown schema is not guessed
        catalog_id = str(family.get("catalog_id", ""))
        catalog = database.catalogs.get(catalog_id)
        if not isinstance(catalog, dict):
            continue
        for record in family.get("records", []):
            if not _record_matches(family, record, parsed, concrete):
                continue
            # Only byte-equivalent semantic records are collapsed. In particular,
            # different results or source editions are NEVER arbitrarily picked.
            key = (catalog_id, json.dumps({k: v for k, v in family.items() if k != "records"},
                                          ensure_ascii=False, sort_keys=True),
                   json.dumps(record, ensure_ascii=False, sort_keys=True))
            if key in seen:
                continue
            seen.add(key)
            enriched = deepcopy(record)
            enriched["catalog_designation"] = record.get("designation", "")
            enriched["catalog_fire_explicit"] = bool(_fire(record))
            enriched["designation"] = "Schöck Isokorb® XT typ " + parsed.canonical
            enriched["input_height_mm"] = int(parsed.fields["height"])
            enriched["input_fire_class"] = ("EI" if parsed.family == "ZL" else "REI") + parsed.fields["fire"]
            if "length" in parsed.fields:
                enriched["element_length_mm"] = int(parsed.fields["length"])
            matches.append(DesignationSuggestion(QueryResult(catalog, family, enriched), 1000.0))
    return matches


def classify_xt(database, item, parsed, concrete):
    item.result = None
    item.archive_source = None
    item.varying_keys = ()
    item.candidates = candidates_for(database, parsed, concrete)
    if len(item.candidates) == 1:
        item.result = item.candidates[0].result
        item.status = "exact"
        item.message = "Zadané parametry odpovídají jednomu záznamu katalogu."
        if not str(item.result.record.get("height_mm", "")).strip().isdigit():
            item.message += " Výška H" + parsed.fields["height"] + " zachována; statická tabulka platí pro uvedený rozsah výšek."
        if not item.result.record.get("catalog_fire_explicit"):
            item.message += " Požární provedení převzato ze vstupu; statická tabulka je neověřuje."
    elif item.candidates:
        item.status = "review"
        item.message = "Pro úplné označení existuje více různých katalogových záznamů. Ověřte zdrojové vydání a statické hodnoty; zadané parametry se znovu nedoplňují."
    else:
        item.status = "error"
        item.message = MISSING + " XT " + parsed.canonical + "; beton " + str(concrete or "neurčen") + ". Nejsou nabízeny nesouvisející typy ani záměna VV za V."


def install(_base=None):
    if getattr(engine, "_turto_iso_301", False):
        return
    previous = engine._classify_bulk_item

    @wraps(previous)
    def classify(database, item, *, preferred_concrete, suggestion_limit):
        parsed = parse_xt_designation(item.designation)
        if parsed is None:
            return previous(database, item, preferred_concrete=preferred_concrete, suggestion_limit=suggestion_limit)
        classify_xt(database, item, parsed, preferred_concrete)

    engine._classify_bulk_item = classify

    # All synchronous callers use the same progressive pipeline, without the
    # obsolete 2.2.45 post-filter that guessed from a truncated suggestion list.
    def analyze(database, text, **kwargs):
        items, skipped, _cancelled = engine.analyze_bulk_text_progressive(database, text, **kwargs)
        return items, skipped

    engine.analyze_bulk_text = analyze
    bulk_import.analyze_bulk_text = analyze
    bulk_import.analyze_bulk_text_progressive = engine.analyze_bulk_text_progressive
    cls = bulk_import.BulkImportDialog
    refresh = cls._refresh_review_tree

    @wraps(refresh)
    def refresh_tree(self, *args, **kwargs):
        refresh(self, *args, **kwargs)
        for iid, item in self._item_by_iid.items():
            parsed = parse_xt_designation(item.designation)
            if parsed and item.status == "error" and item.message.startswith(MISSING):
                self.review_tree.set(iid, "status", "Chybí data")
                self.review_tree.set(iid, "resolved", "XT " + parsed.canonical)
        self.summary_var.set(self.summary_var.get().replace("nerozpoznáno", "nevyřešeno") + " • ISO 3.0.1")

    cls._refresh_review_tree = refresh_tree
    if _base is not None:
        old_payload = _base.ThermalConnectorApp._row_payload

        @wraps(old_payload)
        def row_payload(self, row, order):
            payload, state = old_payload(self, row, order)
            parsed = parse_xt_designation(row.get("source_text", ""))
            selection = row.get("selection", {})
            tabulated_height = str(selection.get("height_mm", ""))
            if (parsed and norm(selection.get("model")) == "XT"
                    and norm(selection.get("type_name")) == parsed.family
                    and norm(selection.get("generation")) == parsed.fields["generation"]
                    and not tabulated_height.strip().isdigit()
                    and height_matches(tabulated_height, int(parsed.fields["height"]))):
                payload["height"] = parsed.fields["height"]
            return payload, state

        _base.ThermalConnectorApp._row_payload = row_payload
    engine._turto_iso_301 = True


def selftest():
    assert height_matches("≥ 180", 240)
    assert not height_matches("180-220", 240)
    assert not height_matches("L240", 240)
    assert not height_matches("neznámá", 240)
    assert _length({"cover": "L=300 mm", "designation": "QP-V1-L300-5.0"}) == 300
    assert _length({"cover": "L=300 mm", "length_mm": 400}) is None
    assert getattr(engine, "_turto_iso_301", False)
    assert bulk_import.analyze_bulk_text_progressive is engine.analyze_bulk_text_progressive
