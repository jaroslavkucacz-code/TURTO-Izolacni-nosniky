from __future__ import annotations

"""Peikko reference-data adapter for the existing catalog/project contract.

A full designation is the type key so every parameter survives even the legacy
selection normalizer. Reference capacities stay in non-design results; substitutions remain blocked.
"""
from catalog_engine import QueryResult, DesignationSuggestion
from peikko_thermal_breaks import decode_peikko, is_peikko, format_decode, DESIGN_STATUS

CATALOG_ID = "peikko_syntax_1"
BLOCK_REASON = (
    "EBEA/TEBEA: katalogová data nejsou úplné statické posouzení konkrétní konfigurace. "
    "Automatickou záměnu ani statické vyhovění nelze potvrdit."
)
CATALOG = {"id": CATALOG_ID, "manufacturer": "Peikko", "edition": "Dekódování + doložené referenční tabulky",
           "publication_label": "Peikko 004 / ETA 23/0525; ne úplné statické posouzení",
           "publication_date": "", "source_filename": ""}


def make_result(text: str, concrete: str | None = None) -> QueryResult:
    d = decode_peikko(text)
    if d is None:
        raise ValueError("Nepodporované označení EBEA/TEBEA.")
    if d.concrete and concrete and d.concrete.casefold() != str(concrete).strip().casefold():
        raise ValueError(f"Označení obsahuje beton {d.concrete}, akce požaduje {concrete}.")
    # This is the action's concrete, not a verified Peikko concrete class.
    action_concrete = d.concrete or str(concrete or "").strip()
    # Do not include drawing prefixes in results; they remain in source_text/note.
    detail = format_decode(decode_peikko(d.canonical))
    from peikko_technical import reference, format_reference
    technical = reference(d.canonical, concrete=action_concrete)
    results = [{"key": "peikko_status", "label": "Stav", "kind": "other", "text": DESIGN_STATUS},
               {"key": "peikko_details", "label": "Rozpoznané označení", "kind": "other", "text": detail},
               {"key": "peikko_reference", "label": "Doložené podklady a podmínky", "kind": "other", "text": format_reference(technical)}]
    family = {"catalog_id": CATALOG_ID, "manufacturer": "Peikko", "brand": d.family,
              "model": d.family, "type": d.canonical, "generation": "syntax-1",
              "source_pages": [], "insulation_thickness_mm": d.sw_mm,
              "compression_transfer": "neuvedeno / dle typu", "substitution_policy": "manual"}
    record = {"designation": d.canonical, "aliases": [str(text)],
              "moment_class": d.reinforcement, "shear_class": d.material,
              "concrete_min": action_concrete, "cover": str(d.cover_mm or ""),
              "height_mm": "",  # Ds/Dt are NOT silently mapped to connector height.
              "element_length_mm": d.length_mm, "insulation_thickness_mm": d.sw_mm,
              "results": results, "source_pages": [], "substitution_policy": "manual",
              "substitution_note": BLOCK_REASON,
              "peikko_parameters": d.parameters, "peikko_technical_reference": technical, "resistance_verified": False}
    family["records"] = [record]
    return QueryResult(dict(CATALOG), family, record)


def catalog_class(previous):
    class PeikkoCatalogDatabase(previous):
        def resolve_designation(self, text, preferred_catalog_id=None, preferred_concrete=None):
            if is_peikko(text):
                if preferred_catalog_id not in (None, "", CATALOG_ID):
                    raise ValueError("EBEA/TEBEA nepatří do zvoleného katalogu.")
                return make_result(text, preferred_concrete)
            return super().resolve_designation(text, preferred_catalog_id=preferred_catalog_id,
                                                preferred_concrete=preferred_concrete)

        def query(self, *, catalog_id, manufacturer, model, type_name, generation,
                  moment_class, concrete_min, shear_class, cover, height_mm):
            if catalog_id == CATALOG_ID:
                result = make_result(type_name, concrete_min)
                if manufacturer != "Peikko" or model != result.family["model"] or generation != "syntax-1":
                    raise ValueError("Nekonzistentní uložený výběr EBEA/TEBEA.")
                for field, value in (("moment_class", moment_class), ("shear_class", shear_class),
                                     ("cover", cover), ("height_mm", height_mm)):
                    if str(value) != str(result.record[field]):
                        raise ValueError("Parametry EBEA/TEBEA neodpovídají úplnému označení: " + field)
                return result
            return super().query(catalog_id=catalog_id, manufacturer=manufacturer, model=model,
                                 type_name=type_name, generation=generation, moment_class=moment_class,
                                 concrete_min=concrete_min, shear_class=shear_class, cover=cover, height_mm=height_mm)

        def suggest_designations(self, text, preferred_catalog_id=None, preferred_concrete=None, limit=12):
            if is_peikko(text):
                if int(limit) <= 0 or preferred_catalog_id not in (None, "", CATALOG_ID):
                    return []
                try:
                    result = make_result(text, preferred_concrete)
                except ValueError:
                    return []
                return [DesignationSuggestion(result=result, score=100.0)]
            return super().suggest_designations(text, preferred_catalog_id=preferred_catalog_id,
                                                preferred_concrete=preferred_concrete, limit=limit)

        def suggestion_hint(self, *args, **kwargs):
            if args and is_peikko(str(args[0])):
                return DESIGN_STATUS
            return super().suggestion_hint(*args, **kwargs)

    return PeikkoCatalogDatabase
