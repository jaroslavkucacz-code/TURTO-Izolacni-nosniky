from __future__ import annotations

"""Combined ordinary ISO + managed Leviat HIT database for Decoder ISO."""

import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from catalog_engine import CatalogDatabase as BaseCatalogDatabase, DesignationSuggestion, QueryResult, SelectionError, natural_key
from hit_core import CONCRETES, DATA_FILENAME, Candidate, DirectionalActions, HitDatabase
from hit_ht import HT_CAPACITIES, HT_PAGE, HT_WIDTH_CODE
from hit_decoder_records import (
    HIT_CATALOG_ID, WIDTH_CODE, compact, norm,
    result_from_candidate, placeholder_ht, placeholder_special,
)
from hit_decoder_suggest import hit_suggestions


class CombinedCatalogDatabase:
    """CatalogDatabase-shaped proxy with HIT products from the design data source."""

    def __init__(self, catalog_directory: Path | str):
        self.base=BaseCatalogDatabase(catalog_directory); self.catalog_directory=self.base.catalog_directory
        self._hit_db=None; self._hit_path=None; self._hit_exact_cache={}

    def __getattr__(self,name): return getattr(self.base,name)
    @property
    def catalogs(self): return self.base.catalogs
    @property
    def families(self): return self.base.families
    @property
    def load_errors(self): return self.base.load_errors

    def _hit_candidates(self):
        paths=[]; appdata=os.environ.get("APPDATA")
        if appdata: paths.append(Path(appdata)/"TURTO"/"Izolacni_nosniky"/DATA_FILENAME)
        paths.extend([self.catalog_directory.parent/DATA_FILENAME,self.catalog_directory.parent/"hit"/DATA_FILENAME])
        out=[]; seen=set()
        for path in paths:
            if str(path) not in seen: seen.add(str(path)); out.append(path)
        return out

    def _hit(self):
        if self._hit_db is not None and self._hit_path is not None and self._hit_path.exists(): return self._hit_db
        for path in self._hit_candidates():
            if not path.exists(): continue
            try: self._hit_db=HitDatabase(path); self._hit_path=path; return self._hit_db
            except Exception: continue
        return None

    @staticmethod
    def _length_parts(text: str):
        match=re.match(r"L(\d+)(?:\|(.*))?$",str(text or ""))
        if not match: raise SelectionError("Uložený záznam HIT nemá platný kód délky / varianty.")
        mm=int(match.group(1)); code={1000:100,500:50,333:33,250:25,100:10,150:15}.get(mm)
        if code is None: raise SelectionError(f"Nepodporovaná délka HIT {mm} mm.")
        return code,str(match.group(2) or "")

    def _candidate_by_components(self,*,series,typ,code,height,cover,concrete,length_code,suffix):
        db=self._hit()
        if db is None: raise SelectionError("Data HIT nejsou načtena. Otevřete kartu Návrh HIT a obnovte data z DoP.")
        rows,error=db.directional_candidates(typ,series,height,cover,concrete,DirectionalActions(),{length_code},include_offsets=(typ=="MVX"),load_distance_x=0.0)
        wanted=str(suffix or ""); m=re.match(r"^(OU|OD|WU|WD)",wanted); base=m.group(1) if m else wanted
        for cand in rows:
            if str(cand.code).upper()!=str(code).upper(): continue
            current=str(cand.suffix or "")
            if base and current not in {base,wanted}: continue
            if not base and current: continue
            if wanted and wanted!=current: cand=replace(cand,suffix=wanted)
            return cand
        if error: raise SelectionError(error)
        raise SelectionError("Přesné označení HIT nebylo nalezeno v aktuálních spravovaných datech.")

    def _parse_exact_hit(self,text: str,concrete: str):
        raw=re.sub(r"^LEVIAT\s+","",norm(text)); conc=concrete if concrete in CONCRETES else "C25/30"
        m=re.fullmatch(r"HIT-(HP|SP)\s+(MVX|MVXL)-(\d{4})-(\d{2})-(100|050|033|025)-(30|35|50)(?:-([A-Z]{2}\d*|\d{4}))?",raw)
        if m:
            series,typ,code,h,width,cover,suffix=m.groups()
            return result_from_candidate(self._candidate_by_components(series=series,typ=typ,code=code,height=int(h)*10,cover=int(cover),concrete=conc,length_code=WIDTH_CODE[width],suffix=str(suffix or "")))
        m=re.fullmatch(r"HIT-(HP|SP)\s+(ZVX|ZDX|DD|DVL|DDL)-(\d{4})-(\d{2})-(100|050|033|025)-(30|35|50)-(06|08|10|12)",raw)
        if m:
            series,typ,code,h,width,cover,dia=m.groups()
            return result_from_candidate(self._candidate_by_components(series=series,typ=typ,code=code,height=int(h)*10,cover=int(cover),concrete=conc,length_code=WIDTH_CODE[width],suffix=dia))
        m=re.fullmatch(r"HIT-(HP|SP)\s+(HT[1-5])-(\d{2})-(010|015)",raw)
        if m:
            series,ht,h,width=m.groups(); expected="010" if series=="HP" else "015"
            if width!=expected: raise SelectionError(f"HIT-{series} HT používá šířkový kód {expected}.")
            height=int(h)*10
            if not 160<=height<=350: raise SelectionError("HIT-HT má katalogový rozsah h = 160–350 mm.")
            if ht in {"HT4","HT5"}: return placeholder_ht(series,ht,height,conc)
            p,v=HT_CAPACITIES[conc][ht]
            cand=Candidate(series,"HT",ht,HT_WIDTH_CODE[series],"",height,conc,p,v,0.0,0.0,f"HIT20.2 p.{HT_PAGE[ht]}",0,height,0.0,"katalogový záznam HT","HIT 20.2-EN; HRd v kN/prvek.")
            return result_from_candidate(cand)
        m=re.fullmatch(r"HIT-(HP|SP)\s+((?:AT|FT)\d+)-(\d{2})-025",raw)
        if m:
            series,code,h=m.groups(); return placeholder_special(series,"AT" if code.startswith("AT") else "FT",code,int(h)*10,conc)
        m=re.fullmatch(r"HIT-(HP|SP)\s+(OTX[^-]*)-(\d{2})-025-(06|08|10|12)",raw)
        if m:
            series,code,h,dia=m.groups(); return placeholder_special(series,"OTX",code,int(h)*10,conc,dia)
        return None

    def resolve_designation(self,text: str,preferred_catalog_id=None,preferred_concrete=None):
        raw=str(text or "").strip()
        if re.search(r"\b(?:LEVIAT\s+)?HIT-(?:HP|SP)\b",norm(raw)):
            concrete=str(preferred_concrete or "C25/30"); key=(norm(raw),concrete)
            if key not in self._hit_exact_cache:
                result=self._parse_exact_hit(raw,concrete)
                if result is None: raise SelectionError("Označení HIT není úplné nebo zatím není rozpoznáno. Použijte úplné výrobní označení HIT z Návrhu HIT.")
                self._hit_exact_cache[key]=result
            return self._hit_exact_cache[key]
        return self.base.resolve_designation(text,preferred_catalog_id=preferred_catalog_id,preferred_concrete=preferred_concrete)

    def query(self,*,catalog_id,manufacturer,model,type_name,generation,moment_class,concrete_min,shear_class,cover,height_mm):
        if str(catalog_id)!=HIT_CATALOG_ID:
            return self.base.query(catalog_id=catalog_id,manufacturer=manufacturer,model=model,type_name=type_name,generation=generation,moment_class=moment_class,concrete_min=concrete_min,shear_class=shear_class,cover=cover,height_mm=height_mm)
        series="HP" if str(model).upper().endswith("HP") else "SP"; typ=str(type_name).upper(); code=str(moment_class); height=int(str(height_mm))
        if typ=="HT":
            result=self._parse_exact_hit(f"HIT-{series} {code.upper()}-{height//10:02d}-{'010' if series=='HP' else '015'}",str(concrete_min))
            if result is None: raise SelectionError("Uložený HIT-HT se nepodařilo znovu načíst.")
            return result
        length,suffix=self._length_parts(str(shear_class))
        if typ in {"AT","FT","OTX"}: return placeholder_special(series,typ,code,height,str(concrete_min),suffix)
        cv=30 if str(cover) in {"","—","-"} else int(str(cover))
        return result_from_candidate(self._candidate_by_components(series=series,typ=typ,code=code,height=height,cover=cv,concrete=str(concrete_min),length_code=length,suffix=suffix))

    def suggest_designations(self,text: str,preferred_catalog_id=None,preferred_concrete=None,limit: int=12):
        hit=hit_suggestions(self,text,preferred_concrete,max(limit,12))
        ordinary=self.base.suggest_designations(text,preferred_catalog_id=preferred_catalog_id,preferred_concrete=preferred_concrete,limit=max(limit,12))
        best={}
        for item in [*hit,*ordinary]:
            key=compact(item.designation)
            if key not in best or item.score>best[key].score: best[key]=item
        return sorted(best.values(),key=lambda x:(-x.score,natural_key(x.designation)))[:limit]

    def suggestion_hint(self,text: str,preferred_catalog_id=None,preferred_concrete=None,limit: int=4):
        values=self.suggest_designations(text,preferred_catalog_id=preferred_catalog_id,preferred_concrete=preferred_concrete,limit=limit)
        return "" if not values else "\nNejbližší možnosti:\n"+"\n".join(f"• {x.designation}" for x in values)

    def validation_report(self):
        errors,warnings,stats=self.base.validation_report()
        if self._hit() is None: warnings=[*warnings,"Decoder ISO: spravovaná data Leviat HIT nejsou načtena; HIT označení budou dostupná po obnovení DoP v Návrhu HIT."]
        else: stats=dict(stats); stats["catalogs"]=int(stats.get("catalogs",0))+1
        return errors,warnings,stats
