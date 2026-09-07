from __future__ import annotations

import re
from difflib import SequenceMatcher
from catalog_engine import DesignationSuggestion, natural_key
from hit_core import CONCRETES, Candidate, DirectionalActions
from hit_ht import HT_CAPACITIES, HT_PAGE, HT_WIDTH_CODE
from hit_decoder_records import WIDTH_CODE, compact, norm, result_from_candidate


def query_type(raw: str) -> str:
    upper=norm(raw)
    for typ in ("MVXL","MVX","ZVX","ZDX","DDL","DVL","DD","OTX","FT","AT","HT"):
        if re.search(rf"\b{typ}", upper): return typ
    return ""


def hit_suggestions(owner, text: str, preferred_concrete: str | None, limit: int):
    upper=norm(text)
    if "HIT" not in upper and not any(t in upper for t in ("MVX","MVXL","ZVX","ZDX","DDL","DVL","OTX","HT")): return []
    concrete=str(preferred_concrete or "C25/30"); concrete=concrete if concrete in CONCRETES else "C25/30"
    try:
        exact=owner._parse_exact_hit(text,concrete)
        if exact is not None: return [DesignationSuggestion(exact,1200.0,())]
    except Exception: pass
    db=owner._hit()
    if db is None: return []
    series_values=["HP"] if "HP" in upper else (["SP"] if "SP" in upper else ["HP","SP"])
    typ=query_type(upper); types=[typ] if typ else ["MVX","MVXL","ZVX","ZDX","DD","DVL","DDL","HT"]
    h=re.search(r"\bH\s*=?\s*(1[6-9]0|[2-4]\d0|500)\b",upper)
    code_h=re.search(r"-\d{4}-(\d{2})(?:-|$)",upper)
    heights=[int(h.group(1))] if h else ([int(code_h.group(1))*10] if code_h else [200])
    code=re.search(r"\b(?:MVX|MVXL|ZVX|ZDX|DD|DVL|DDL)-(\d{4})",upper); wanted=code.group(1) if code else ""
    width=re.search(r"-(100|050|033|025)(?:-|$)",upper); lengths={WIDTH_CODE[width.group(1)]} if width else {100}
    cv=re.search(r"-(30|35|50)(?:-|$)",upper); covers=[int(cv.group(1))] if cv else [35,30,50]
    scored=[]; seen=set(); q=compact(upper)
    for series in series_values:
        for current in types:
            if current=="HT":
                for height in [x for x in heights if 160<=x<=350]:
                    for ht_type in ("HT1","HT2","HT3"):
                        p,v=HT_CAPACITIES[concrete][ht_type]
                        cand=Candidate(series,"HT",ht_type,HT_WIDTH_CODE[series],"",height,concrete,p,v,0.0,0.0,f"HIT20.2 p.{HT_PAGE[ht_type]}",0,height,0.0,"katalogový záznam HT","HIT 20.2-EN")
                        result=result_from_candidate(cand)
                        if result.designation in seen: continue
                        seen.add(result.designation); scored.append((80+80*SequenceMatcher(None,q,compact(result.designation)).ratio(),result))
                continue
            for height in heights:
                if not 160<=height<=500: continue
                for cover in covers:
                    if current in {"ZVX","ZDX"} and cover!=30: continue
                    try: rows,error=db.directional_candidates(current,series,height,cover,concrete,DirectionalActions(),set(lengths),include_offsets=False,load_distance_x=0.0)
                    except Exception: continue
                    if error and not rows: continue
                    if wanted: rows=[r for r in rows if str(r.code)==wanted]
                    for cand in rows[:80]:
                        result=result_from_candidate(cand)
                        if result.designation in seen: continue
                        seen.add(result.designation); score=70+90*SequenceMatcher(None,q,compact(result.designation)).ratio()
                        if current in upper: score+=25
                        if series in upper: score+=15
                        scored.append((score,result))
    scored.sort(key=lambda x:(-x[0],natural_key(x[1].designation)))
    return [DesignationSuggestion(r,s,()) for s,r in scored[:limit]]
