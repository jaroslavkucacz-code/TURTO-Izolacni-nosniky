from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from catalog_engine import CatalogDatabase, QueryResult

PROJECT_SCHEMA_VERSION = 4
PROJECT_FILE_EXTENSION = ".tinp"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_quantity(value: Any) -> int:
    try: quantity=int(str(value).strip())
    except (TypeError,ValueError) as exc: raise ValueError("Počet kusů musí být celé číslo.") from exc
    if quantity<1: raise ValueError("Počet kusů musí být alespoň 1.")
    if quantity>1_000_000: raise ValueError("Počet kusů je neobvykle vysoký.")
    return quantity


def selection_from_result(result: QueryResult) -> dict[str, Any]:
    r=result.record
    return {
        "catalog_id":str(result.catalog["id"]), "manufacturer":str(result.family["manufacturer"]),
        "model":str(result.family["model"]), "type_name":str(result.family["type"]), "generation":str(result.family["generation"]),
        "moment_class":str(r["moment_class"]), "concrete_min":str(r["concrete_min"]), "shear_class":str(r["shear_class"]),
        "cover":str(r["cover"]), "height_mm":str(r["height_mm"]),
    }


def _catalog_element_length_mm(result: QueryResult) -> int | None:
    containers = (result.record, result.family)
    keys_mm = ("element_length_mm", "unit_length_mm", "physical_length_mm", "length_mm", "element_width_mm", "width_mm")
    keys_m = ("element_length_m", "unit_length_m", "physical_length_m", "length_m", "element_width_m", "width_m")
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in keys_mm:
            value = container.get(key)
            if value in (None, "", "—"):
                continue
            match = re.search(r"\d+(?:[.,]\d+)?", str(value))
            if match:
                length = int(round(float(match.group(0).replace(",", "."))))
                if length > 0:
                    return length
        for key in keys_m:
            value = container.get(key)
            if value in (None, "", "—"):
                continue
            match = re.search(r"\d+(?:[.,]\d+)?", str(value))
            if match:
                length = int(round(float(match.group(0).replace(",", ".")) * 1000.0))
                if length > 0:
                    return length
    return None


def snapshot_from_result(result: QueryResult) -> dict[str, Any]:
    return {
        "designation":result.designation,
        "results":copy.deepcopy(result.results),
        "results_text":result.all_results_text,
        "moment_text":result.moment_text,
        "shear_text":result.shear_text,
        "other_text":result.other_text,
        "insulation_thickness_mm":result.insulation_thickness_mm,
        "insulation_text":result.insulation_text,
        "compression_transfer":result.compression_transfer,
        "element_length_mm":_catalog_element_length_mm(result),
        "substitution_policy":str(result.record.get("substitution_policy", result.family.get("substitution_policy", "automatic"))),
        "substitution_note":str(result.record.get("substitution_note", result.family.get("substitution_note", ""))),
        "catalog_edition":str(result.catalog.get("edition","")),
        "publication_label":str(result.catalog.get("publication_label","")),
        "publication_date":str(result.catalog.get("publication_date","")),
        "source_filename":str(result.catalog.get("source_filename","")),
        "source_pages":list(result.source_pages),
    }


def query_from_selection(database: CatalogDatabase, selection: dict[str, Any]) -> QueryResult:
    return database.query(
        catalog_id=str(selection["catalog_id"]), manufacturer=str(selection["manufacturer"]), model=str(selection["model"]),
        type_name=str(selection["type_name"]), generation=str(selection["generation"]), moment_class=str(selection["moment_class"]),
        concrete_min=str(selection["concrete_min"]), shear_class=str(selection["shear_class"]), cover=str(selection["cover"]),
        height_mm=str(selection["height_mm"]),
    )


def create_project_row(result: QueryResult, *, position: str, quantity: int=1, note: str="", source_text: str="", row_id: str|None=None) -> dict[str,Any]:
    return {"id":row_id or uuid.uuid4().hex,"position":str(position).strip(),"quantity":safe_quantity(quantity),"note":str(note).strip(),
            "source_text":str(source_text or result.designation).strip(),
            "selection":selection_from_result(result),"snapshot":snapshot_from_result(result),
            "mapping":{"status":"not_run","targets":[],"selected_target_id":None,"source_meta":{},"warnings":[],"errors":[],"estimated_type":"","diameter_availability":{},"source_overrides":{}}}


def _legacy_results(snapshot: dict[str,Any]) -> list[dict[str,Any]]:
    out=[]
    if "moment_value" in snapshot:
        out.append({"key":"m_rd_y","label":"mRd,y","kind":"moment","value":float(snapshot["moment_value"]),"unit":str(snapshot.get("moment_unit","kNm/m"))})
    if "shear_positive" in snapshot:
        d={"key":"v_rd_z","label":"vRd,z","kind":"shear","positive":float(snapshot["shear_positive"]),"unit":str(snapshot.get("shear_unit","kN/m"))}
        if snapshot.get("shear_negative") is not None: d["negative"]=float(snapshot["shear_negative"])
        out.append(d)
    return out


def normalize_project_row(raw: dict[str,Any]) -> dict[str,Any]:
    if not isinstance(raw,dict): raise ValueError("Řádek projektu musí být objekt.")
    selection=raw.get("selection"); snapshot=raw.get("snapshot")
    if not isinstance(selection,dict): raise ValueError("Řádku chybí výběrová data nosníku.")
    if not isinstance(snapshot,dict): raise ValueError("Řádku chybí uložený snímek statických hodnot.")
    required={"catalog_id","manufacturer","model","type_name","generation","moment_class","concrete_min","shear_class","cover","height_mm"}
    missing=sorted(required.difference(selection))
    if missing: raise ValueError("Řádku chybí pole výběru: "+", ".join(missing))
    snap=dict(snapshot)
    if not isinstance(snap.get("results"),list): snap["results"]=_legacy_results(snap)
    snap.setdefault("results_text","\n".join(str(x) for x in []))
    snap.setdefault("moment_text",str(snapshot.get("moment_text","—")))
    snap.setdefault("shear_text",str(snapshot.get("shear_text","—")))
    snap.setdefault("other_text","—")
    snap.setdefault("insulation_thickness_mm", None)
    snap.setdefault("insulation_text", "—")
    snap.setdefault("compression_transfer", "neuvedeno / dle typu")
    snap.setdefault("element_length_mm", None)
    snap.setdefault("substitution_policy", "automatic")
    snap.setdefault("substitution_note", "")
    raw_mapping=raw.get("mapping") if isinstance(raw.get("mapping"),dict) else {}
    mapping={
        "status":str(raw_mapping.get("status","not_run")),
        "targets":list(raw_mapping.get("targets",[])) if isinstance(raw_mapping.get("targets",[]),list) else [],
        "selected_target_id":raw_mapping.get("selected_target_id"),
        "source_meta":dict(raw_mapping.get("source_meta",{})) if isinstance(raw_mapping.get("source_meta",{}),dict) else {},
        "warnings":list(raw_mapping.get("warnings",[])) if isinstance(raw_mapping.get("warnings",[]),list) else [],
        "errors":list(raw_mapping.get("errors",[])) if isinstance(raw_mapping.get("errors",[]),list) else [],
        "estimated_type":str(raw_mapping.get("estimated_type","")),
        "diameter_availability":dict(raw_mapping.get("diameter_availability",{})) if isinstance(raw_mapping.get("diameter_availability",{}),dict) else {},
        "source_overrides":dict(raw_mapping.get("source_overrides",{})) if isinstance(raw_mapping.get("source_overrides",{}),dict) else {},
    }
    return {"id":str(raw.get("id") or uuid.uuid4().hex),"position":str(raw.get("position","")).strip(),"quantity":safe_quantity(raw.get("quantity",1)),"note":str(raw.get("note","")).strip(),
            "source_text":str(raw.get("source_text") or snap.get("designation","")).strip(),
            "selection":{"catalog_id":str(selection["catalog_id"]),"manufacturer":str(selection["manufacturer"]),"model":str(selection["model"]),"type_name":str(selection["type_name"]),"generation":str(selection["generation"]),"moment_class":str(selection["moment_class"]),"concrete_min":str(selection["concrete_min"]),"shear_class":str(selection["shear_class"]),"cover":str(selection["cover"]),"height_mm":str(selection["height_mm"])},
            "snapshot":snap,"mapping":mapping}


def _canonical_results(values: list[dict[str,Any]]) -> str:
    return json.dumps(values,ensure_ascii=False,sort_keys=True,separators=(",",":"))


def row_status(database: CatalogDatabase,row: dict[str,Any]) -> tuple[str,QueryResult|None,str]:
    try: result=query_from_selection(database,row["selection"])
    except Exception as exc: return "missing",None,f"Kombinace není v aktuálně načtené databázi: {exc}"
    old=row.get("snapshot",{}).get("results")
    if not isinstance(old,list): old=_legacy_results(row.get("snapshot",{}))
    if _canonical_results(old)!=_canonical_results(result.results):
        return "changed",result,"Uložené hodnoty se liší od aktuálních dat stejného katalogového vydání."
    return "ok",result,"Řádek odpovídá aktuálně načteným datům."


@dataclass
class ProjectDocument:
    name:str="Nový objekt"; note:str=""; concrete_class:str="C25/30"; rows:list[dict[str,Any]]=field(default_factory=list)
    project_id:str=field(default_factory=lambda:uuid.uuid4().hex); created_at:str=field(default_factory=now_iso); updated_at:str=field(default_factory=now_iso)
    path:Path|None=field(default=None,repr=False,compare=False)
    def touch(self)->None: self.updated_at=now_iso()
    def next_position(self)->str:
        highest=0
        for row in self.rows:
            m=re.fullmatch(r"P\s*0*(\d+)",str(row.get("position","")).strip(),flags=re.I)
            if m: highest=max(highest,int(m.group(1)))
        return f"P{highest+1:03d}"
    def row_by_id(self,row_id:str)->dict[str,Any]|None: return next((r for r in self.rows if str(r.get("id"))==str(row_id)),None)
    def index_by_id(self,row_id:str)->int|None:
        for i,r in enumerate(self.rows):
            if str(r.get("id"))==str(row_id): return i
        return None
    def add(self,row:dict[str,Any])->None:
        n=normalize_project_row(row)
        if self.row_by_id(n["id"]): n["id"]=uuid.uuid4().hex
        self.rows.append(n); self.touch()
    def replace(self,row_id:str,row:dict[str,Any])->None:
        i=self.index_by_id(row_id)
        if i is None: raise KeyError("Upravovaný řádek již v projektu neexistuje.")
        n=normalize_project_row(row); n["id"]=str(row_id); self.rows[i]=n; self.touch()
    def remove_ids(self,row_ids:Iterable[str])->int:
        rm={str(x) for x in row_ids}; n0=len(self.rows); self.rows=[r for r in self.rows if str(r.get("id")) not in rm]; removed=n0-len(self.rows)
        if removed:self.touch()
        return removed
    def to_dict(self)->dict[str,Any]:
        self.touch(); return {"schema_version":PROJECT_SCHEMA_VERSION,"application":"TURTO ISO",
                             "project":{"id":self.project_id,"name":self.name,"note":self.note,"concrete_class":self.concrete_class,"created_at":self.created_at,"updated_at":self.updated_at},
                             "rows":[normalize_project_row(r) for r in self.rows]}
    @classmethod
    def from_dict(cls,raw:dict[str,Any])->"ProjectDocument":
        if not isinstance(raw,dict): raise ValueError("Soubor projektu nemá platný formát.")
        version=int(raw.get("schema_version",0))
        if version not in {1,2,3,4}: raise ValueError("Soubor používá nepodporovanou verzi formátu projektu.")
        project=raw.get("project"); rows=raw.get("rows")
        if not isinstance(project,dict) or not isinstance(rows,list): raise ValueError("Soubor projektu je neúplný.")
        return cls(name=str(project.get("name","Nový objekt")),note=str(project.get("note","")),concrete_class=str(project.get("concrete_class","C25/30") or "C25/30"),rows=[normalize_project_row(r) for r in rows],
                   project_id=str(project.get("id") or uuid.uuid4().hex),created_at=str(project.get("created_at") or now_iso()),updated_at=str(project.get("updated_at") or now_iso()))
    @classmethod
    def load(cls,path:Path|str)->"ProjectDocument":
        source=Path(path); doc=cls.from_dict(json.loads(source.read_text(encoding="utf-8-sig"))); doc.path=source.resolve(); return doc
    def save(self,path:Path|str|None=None)->Path:
        target=Path(path) if path is not None else self.path
        if target is None: raise ValueError("Není určeno umístění projektu.")
        if target.suffix.lower()!=PROJECT_FILE_EXTENSION: target=target.with_suffix(PROJECT_FILE_EXTENSION)
        target.parent.mkdir(parents=True,exist_ok=True); tmp=target.with_suffix(target.suffix+".tmp")
        tmp.write_text(json.dumps(self.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(target); self.path=target.resolve(); return self.path
