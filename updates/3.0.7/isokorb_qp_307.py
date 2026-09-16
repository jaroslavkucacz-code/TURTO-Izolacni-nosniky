from __future__ import annotations

"""Reviewed T QP-VV 5.0 data and one resolver for quick entry and bulk import."""

from functools import wraps
import json
from pathlib import Path
import re

import catalog_engine as catalog
import isokorb_families_304 as families

VERSION = "3.0.7"
CATALOG_ID = "schoeck-t-qp-vv-5.0-at-2025.1-reviewed"
EXAMPLE = "T-QP-VV1-REI120-H200-L300-5.0"
DATA_FILE = Path(__file__).with_name("schoeck_t_qp_307.json")


def catalog_package():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    records = []
    for entry in data["table"]:
        shear, value, length, minimum = (entry[k] for k in ("shear", "vrd_kn", "length_mm", "height_min_mm"))
        for height in range(minimum, data["height_max_mm"] + 1, 10):
            code = f"T-QP-{shear}-REI120-H{height}-L{length}-5.0"
            records.append(dict(
                designation="Schöck Isokorb® T typ " + code[2:], aliases=[code],
                moment_class=shear, shear_class="—", concrete_min="C25/30",
                cover=f"L={length} mm", height_mm=str(height), height_min=minimum,
                height_max=data["height_max_mm"], element_length_mm=length,
                insulation_thickness_mm=80, fire_class="REI120",
                compression_transfer="s tlakovými ložisky",
                source_pages=[125, 128, 131],
                notes=["Zdroj: Schöck AT/2025.1, generace 5.0; hodnoty na jeden prvek.",
                       "Připojené desky, jejich smyk a navazující výztuž vyžadují samostatné posouzení."],
                results=[dict(key="v_rd_z", label="VRd,z", kind="shear",
                              positive=value, negative=-value, unit="kN/prvek")]))
    return dict(schema_version=2, catalog=data["catalog"], families=[dict(
        manufacturer="Schöck", model="T", type="QP", generation="5.0",
        insulation_thickness_mm=80, selector_labels={"moment_class": "Třída smyku", "cover": "Délka prvku"},
        records=records)])


def add_catalog(database):
    if CATALOG_ID in database.catalogs:
        return
    database._load_package(DATA_FILE, catalog_package())
    family = database.families[-1]
    for record in family["records"]:
        for text in [record["designation"], *record["aliases"]]:
            database._designation_index.setdefault(catalog._normalise(text), []).append((family, record))
    database._build_suggestion_index()
    database._build_selector_value_cache()


def _is_qp(parsed):
    return parsed is not None and parsed.model == "T" and parsed.family == "QP"


def _malformed_qp(text):
    text = families.old.norm(text).replace("®", "")
    text = re.sub(r"^SCHO(?:CK|ECK)\s+", "", text)
    text = re.sub(r"^ISOKORB\s*", "", text)
    return bool(re.match(r"^T(?:\s*(?:TYP|TYPE))?(?:\s*-\s*|\s+)QP-", text)
                and "REI" in text and re.search(r"-H\d+", text))


def install(_base=None):
    cls = catalog.CatalogDatabase
    if getattr(cls, "_turto_qp_307", False):
        return
    init, resolve, suggest = cls.__init__, cls.resolve_designation, cls.suggest_designations
    previous_candidates = families.candidates

    @wraps(init)
    def initialize(self, *args, **kwargs):
        init(self, *args, **kwargs)
        add_catalog(self)

    @wraps(previous_candidates)
    def candidates(database, parsed, concrete):
        choices = previous_candidates(database, parsed, concrete)
        if _is_qp(parsed):
            # Fill missing data without replacing a customer's matching source
            # edition or hiding ambiguity among existing catalogue records.
            existing = [c for c in choices if c.result.catalog["id"] != CATALOG_ID]
            return existing or choices
        return choices

    def choices(self, parsed, preferred_catalog_id, preferred_concrete):
        items = previous_candidates(self, parsed, preferred_concrete)
        preferred = [c for c in items if c.result.catalog["id"] == preferred_catalog_id]
        return preferred or candidates(self, parsed, preferred_concrete)

    @wraps(resolve)
    def resolve_qp(self, text, preferred_catalog_id=None, preferred_concrete=None):
        parsed = families.parse(text)
        if _is_qp(parsed):
            items = choices(self, parsed, preferred_catalog_id, preferred_concrete)
            if len(items) == 1:
                return items[0].result
            if items:
                raise catalog.SelectionError("Označení odpovídá více zdrojovým záznamům; vyberte vydání katalogu.")
            raise catalog.SelectionError(families.MISSING + " " + parsed.canonical + "; beton "
                                         + str(preferred_concrete or "neurčen") + ".")
        if _malformed_qp(text):
            raise catalog.SelectionError("Neplatné nebo neúplné označení T-QP. Zkontrolujte parametry a generaci.")
        return resolve(self, text, preferred_catalog_id, preferred_concrete)

    @wraps(suggest)
    def suggest_qp(self, text, preferred_catalog_id=None, preferred_concrete=None, limit=12):
        parsed = families.parse(text)
        if _is_qp(parsed):
            return choices(self, parsed, preferred_catalog_id, preferred_concrete)[:limit]
        if _malformed_qp(text):
            return []
        return suggest(self, text, preferred_catalog_id, preferred_concrete, limit)

    cls.__init__, cls.resolve_designation, cls.suggest_designations = initialize, resolve_qp, suggest_qp
    families.candidates = candidates
    cls._turto_qp_307 = True


def selftest():
    package = catalog_package()
    assert package["catalog"]["id"] == CATALOG_ID
    matches = [r for r in package["families"][0]["records"] if EXAMPLE in r["aliases"]]
    assert len(matches) == 1
    row = matches[0]
    assert row["results"][0]["positive"] == 30.9 and row["results"][0]["negative"] == -30.9
    assert row["height_mm"] == "200" and row["element_length_mm"] == 300
    assert row["insulation_thickness_mm"] == 80
