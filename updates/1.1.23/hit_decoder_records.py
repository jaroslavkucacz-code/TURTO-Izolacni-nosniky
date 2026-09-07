from __future__ import annotations

import re
from typing import Any
from catalog_engine import QueryResult
from hit_core import Candidate
from hit_ht import HT_WIDTH_MM

HIT_CATALOG_ID = "leviat_hit_2023"
HIT_GENERATION = "07-23"
WIDTH_CODE = {"100": 100, "050": 50, "033": 33, "025": 25}


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").upper().replace("−", "-").replace("–", "-")).strip()


def compact(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", norm(value))


def pages(value: Any) -> list[int]:
    out = []
    for token in re.findall(r"\d{1,3}", str(value or "")):
        n = int(token)
        if 1 <= n <= 500 and n not in out: out.append(n)
    return out


def compression(candidate: Candidate) -> str:
    typ = candidate.connection_type.upper()
    if typ in {"MVX", "MVXL"}: return "s tlakovými ložisky (CSB)"
    if typ in {"ZVX", "ZDX"}:
        code = str(candidate.code)
        if len(code) >= 4 and code[:4].isdigit():
            return "s tlakovými ložisky (CSB)" if int(code[2:4]) > 0 else "bez tlakových ložisek"
    if typ in {"DD", "DVL", "DDL", "AT", "FT", "OTX"}: return "bez tlakových ložisek – tlačené pruty"
    return "dle typu HIT"


def result_from_candidate(candidate: Candidate) -> QueryResult:
    typ = candidate.connection_type.upper(); series = candidate.series.upper(); results = []
    if typ == "HT":
        if candidate.m1: results.append({"key":"h_rd_parallel","label":"HRd∥","kind":"horizontal","value":abs(float(candidate.m1)),"unit":"kN/prvek"})
        if candidate.v1: results.append({"key":"h_rd_perp","label":"HRd⊥","kind":"horizontal","value":abs(float(candidate.v1)),"unit":"kN/prvek"})
    elif typ in {"AT", "FT", "OTX"}:
        if candidate.nrd: results.append({"key":"n_rd","label":"NRd","kind":"normal","value":abs(float(candidate.nrd)),"unit":"kN/m"})
        if candidate.m1: results.append({"key":"m_rd","label":"MRd","kind":"moment","value":abs(float(candidate.m1)),"unit":"kNm/m"})
        if candidate.v1: results.append({"key":"v_rd","label":"VRd","kind":"shear","value":abs(float(candidate.v1)),"unit":"kN/m"})
        if candidate.spacing_max: results.append({"key":"a_max","label":"a max","kind":"other","value":float(candidate.spacing_max),"unit":"m"})
    else:
        if candidate.m1: results.append({"key":"m_rd_1","label":"MRd,1","kind":"moment","value":abs(float(candidate.m1)),"unit":"kNm/m"})
        if candidate.v1: results.append({"key":"v_rd_1","label":"VRd,1","kind":"shear","positive":abs(float(candidate.v1)),"negative":-abs(float(candidate.v1)),"unit":"kN/m"})
        if candidate.m2: results.append({"key":"m_rd_2","label":"MRd,2","kind":"other","value":abs(float(candidate.m2)),"unit":"kNm/m"})
        if candidate.v2: results.append({"key":"v_rd_2","label":"VRd,2","kind":"other","value":abs(float(candidate.v2)),"unit":"kN/m"})
    catalog = {"id":HIT_CATALOG_ID,"manufacturer":"Leviat","edition":"CONF-DOP HIT-HP/SP-07-23","publication_label":"ETA-18/0189 / HIT 20.2-EN 2023","publication_date":"2023-07-06","source_filename":"CONF-DOP_HIT-HP_SP_07-23-E.pdf"}
    family = {"catalog_id":HIT_CATALOG_ID,"manufacturer":"Leviat","brand":"HIT","model":f"HIT-{series}","type":typ,"generation":HIT_GENERATION,"source_pages":pages(candidate.page),"insulation_thickness_mm":80 if series=="HP" else 120,"compression_transfer":compression(candidate)}
    suffix = str(candidate.suffix or ""); selector = f"L{candidate.physical_length_mm}" + (f"|{suffix}" if suffix else "")
    record = {"moment_class":str(candidate.code),"shear_class":selector,"concrete_min":str(candidate.concrete),"cover":"—" if typ=="HT" else str(candidate.cover),"height_mm":str(candidate.height),"designation":candidate.designation,"aliases":[candidate.designation.replace("HIT-","Leviat HIT-")],"results":results,"source_pages":pages(candidate.page),"insulation_thickness_mm":80 if series=="HP" else 120,"compression_transfer":compression(candidate),"element_length_mm":candidate.physical_length_mm,"substitution_policy":"none","substitution_note":"Prvek je již Leviat HIT; další záměna za HIT se neprovádí.","notes":[str(candidate.source_note)] if str(candidate.source_note or "").strip() else []}
    family["records"]=[record]; return QueryResult(catalog,family,record)


def placeholder_ht(series: str, typ: str, height: int, concrete: str) -> QueryResult:
    width=HT_WIDTH_MM[series]; designation=f"HIT-{series} {typ}-{height//10:02d}-{'010' if series=='HP' else '015'}"
    catalog={"id":HIT_CATALOG_ID,"manufacturer":"Leviat","edition":"HIT 20.2-EN 2023","publication_label":"HT4/HT5 – kombinované použití s MVX","publication_date":"2023-01-01","source_filename":"HIT 20.2-EN"}
    family={"catalog_id":HIT_CATALOG_ID,"manufacturer":"Leviat","brand":"HIT","model":f"HIT-{series}","type":"HT","generation":HIT_GENERATION,"insulation_thickness_mm":80 if series=="HP" else 120,"compression_transfer":"dle kombinace s MVX"}
    record={"moment_class":typ,"shear_class":f"B{width}","concrete_min":concrete,"cover":"—","height_mm":str(height),"designation":designation,"aliases":[],"results":[{"key":"note","label":"Omezení","kind":"other","text":"Únosnost HT4/HT5 je nutno posoudit v předepsané kombinaci s HIT-MVX.","unit":""}],"source_pages":[],"insulation_thickness_mm":80 if series=="HP" else 120,"compression_transfer":"dle kombinace s MVX","element_length_mm":width,"substitution_policy":"none","substitution_note":"Prvek je již Leviat HIT."}
    family["records"]=[record]; return QueryResult(catalog,family,record)


def placeholder_special(series: str, typ: str, code: str, height: int, concrete: str, suffix: str = "") -> QueryResult:
    typ=typ.upper(); designation=f"HIT-{series} {code}-{height//10:02d}-025"; pages_=[132,133] if typ=="AT" else [140,141]
    note=f"{typ} používá katalogové interakční tabulky M/N/V; konkrétní únosnost závisí na návrhových účincích. Posoudit v Návrhu HIT."
    if typ=="OTX":
        designation += f"-{suffix or '06'}"; pages_=[144,145]
        note="Únosnost a maximální rozteč OTX závisejí na NEd/VEd a vzdálenosti zatížení x; posoudit v Návrhu HIT."
    catalog={"id":HIT_CATALOG_ID,"manufacturer":"Leviat","edition":"HALFEN HIT 20.2-EN 2023","publication_label":"ETA-18/0189 / speciální HIT","publication_date":"2023-01-01","source_filename":"HIT 20.2-EN"}
    family={"catalog_id":HIT_CATALOG_ID,"manufacturer":"Leviat","brand":"HIT","model":f"HIT-{series}","type":typ,"generation":HIT_GENERATION,"source_pages":pages_,"insulation_thickness_mm":80 if series=="HP" else 120,"compression_transfer":"bez tlakových ložisek – tlačené pruty"}
    record={"moment_class":code,"shear_class":f"L250|{suffix}" if suffix else "L250","concrete_min":concrete,"cover":"30","height_mm":str(height),"designation":designation,"aliases":[designation.replace("HIT-","Leviat HIT-")],"results":[{"key":"interaction_note","label":"Statické posouzení","kind":"other","text":note,"unit":""}],"source_pages":pages_,"insulation_thickness_mm":80 if series=="HP" else 120,"compression_transfer":"bez tlakových ložisek – tlačené pruty","element_length_mm":250,"substitution_policy":"none","substitution_note":"Prvek je již Leviat HIT; další záměna za HIT se neprovádí."}
    family["records"]=[record]; return QueryResult(catalog,family,record)
