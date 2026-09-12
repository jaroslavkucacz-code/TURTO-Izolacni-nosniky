from __future__ import annotations
"""HALFEN / Leviat HSD – HSD EC 10-E, edition PDF 03/26."""
import math, re
from typing import Any
CATALOG_ID="HSD EC 10-E"
CATALOG_EDITION="R-090-E – 06/10 PDF 03/26"
CATALOG_SOURCE="Leviat / HALFEN HSD Shear Dowel System, HSD EC 10-E, 03/2026"
WIDTHS=(10,20,30,40,50,60)
GEOM={"122":("Ø22",180),"124":("Ø24",200),"128":("Ø28",240),"134":("Ø34",300),"140":("Ø40",350),"145":("45×45",420),"150":("50×50",600),"155":("55×55",650)}
_AXIAL="""122|180|54.9,54.9,54.9,54.9,53.2,44.4|68.6,68.6,68.6,66.6,53.2,44.4
122|200|61.3,61.3,61.3,61.3,53.2,44.4|76.6,76.6,76.6,66.6,53.2,44.4
122|220|67.6,67.6,67.6,66.6,53.2,44.4|84.5,84.5,81.8,66.6,53.2,44.4
122|240|74,74,74,66.6,53.2,44.4|92.5,92.5,81.8,66.6,53.2,44.4
122|250|77.2,77.2,77.2,66.6,53.2,44.4|96.5,96.5,81.8,66.6,53.2,44.4
122|260|80.4,80.4,80.4,66.6,53.2,44.4|100.5,98.2,81.8,66.6,53.2,44.4
122|280|86.8,86.8,81.8,66.6,53.2,44.4|108.5,98.2,81.8,66.6,53.2,44.4
124|200|79.8,79.8,79.8,79.8,69.1,57.6|99.7,99.7,99.7,86.4,69.1,57.6
124|220|87.7,87.7,87.7,86.4,69.1,57.6|109.7,109.7,108.8,86.4,69.1,57.6
124|240|95.7,95.7,95.7,86.4,69.1,57.6|119.6,119.6,108.8,86.4,69.1,57.6
124|250|99.7,99.7,99.7,86.4,69.1,57.6|124.6,124.6,108.8,86.4,69.1,57.6
124|260|103.7,103.7,103.7,86.4,69.1,57.6|129.6,125.6,108.8,86.4,69.1,57.6
124|280|111.7,111.7,108.8,86.4,69.1,57.6|139.6,125.6,108.8,86.4,69.1,57.6
128|240|121,121,121,121,109.8,91.5|151.2,151.2,147.9,130.2,109.8,91.5
128|250|125.6,125.6,125.6,125.6,109.8,91.5|157,157,147.9,130.2,109.8,91.5
128|260|130.3,130.3,130.3,130.2,109.8,91.5|162.8,162.8,147.9,130.2,109.8,91.5
128|280|139.6,139.6,139.6,130.2,109.8,91.5|174.5,169.1,147.9,130.2,109.8,91.5
128|300|148.9,148.9,147.5,130.2,109.8,91.5|186.1,169.1,147.9,130.2,109.8,91.5
128|320|158.2,158.2,147.5,130.2,109.8,91.5|188.2,169.1,147.9,130.2,109.8,91.5
134|300|202.9,202.9,202.9,197,175.5,162.7|253.6,239.7,219.3,198.2,175.7,162.7
134|320|213.8,213.8,213.8,197,175.5,162.7|259.5,239.7,219.3,198.2,175.7,162.7
140|350|290.4,290.4,290.4,290.4,263,250.2|363,347,320.8,293.2,263.1,250.2
140|360|296.8,296.8,296.8,291.9,263,250.2|370.9,347,320.8,293.2,263.1,250.2
140|380|309.4,309.4,309.4,291.9,263,250.2|372.1,347,320.8,293.2,263.1,250.2
140|400|322,322,317.9,291.9,263,250.2|372.1,347,320.8,293.2,263.1,250.2"""
_TRANSVERSE="""122|180|54.9,54.9,54.9,54.9,47.9,39.9|68.6,68.6,68.6,59.9,47.9,39.9
122|200|61.3,61.3,61.3,59.9,47.9,39.9|76.6,76.6,76.6,59.9,47.9,39.9
122|220|67.6,67.6,67.6,59.9,47.9,39.9|84.5,84.5,79.4,59.9,47.9,39.9
122|240|74,74,74,59.9,47.9,39.9|92.5,92.5,79.4,59.9,47.9,39.9
122|250|77.2,77.2,77.2,59.9,47.9,39.9|96.5,93.1,79.4,59.9,47.9,39.9
122|260|80.4,80.4,79.4,59.9,47.9,39.9|100.5,93.1,79.4,59.9,47.9,39.9
122|280|86.8,86.8,79.4,59.9,47.9,39.9|108.5,93.1,79.4,59.9,47.9,39.9
124|200|79.8,79.8,79.8,77.8,62.2,51.8|99.7,99.7,99.7,77.8,62.2,51.8
124|220|87.7,87.7,87.7,77.8,62.2,51.8|109.7,109.7,101.4,77.8,62.2,51.8
124|240|95.7,95.7,95.7,77.8,62.2,51.8|119.6,119.6,101.4,77.8,62.2,51.8
124|250|99.7,99.7,99.7,77.8,62.2,51.8|124.6,119,101.4,77.8,62.2,51.8
124|260|103.7,103.7,101.4,77.8,62.2,51.8|129.6,119,101.4,77.8,62.2,51.8
124|280|111.7,111.7,101.4,77.8,62.2,51.8|139.6,119,101.4,77.8,62.2,51.8
128|240|121,121,121,121,98.8,82.3|151.2,151.2,138.5,123.4,98.8,82.3
128|250|125.6,125.6,125.6,123.4,98.8,82.3|157,157,138.5,123.4,98.8,82.3
128|260|130.3,130.3,130.3,123.4,98.8,82.3|162.8,162.2,138.5,123.4,98.8,82.3
128|280|139.6,139.6,138.4,123.4,98.8,82.3|174.5,162.2,138.5,123.4,98.8,82.3
128|300|148.9,148.9,138.4,123.4,98.8,82.3|182.6,162.2,138.5,123.4,98.8,82.3
128|320|158.2,158.2,138.4,123.4,98.8,82.3|182.6,162.2,138.5,123.4,98.8,82.3
134|300|202.9,202.9,202.9,185.6,162.7,147.4|251.8,231.1,209.5,186.5,162.7,147.4
134|320|213.8,213.8,207.6,185.6,162.7,147.4|251.8,231.1,209.5,186.5,162.7,147.4
140|350|290.4,290.4,290.4,275.6,250.2,240|361.1,334.6,306.6,276.2,250.2,240
140|360|296.8,296.8,296.8,275.6,250.2,240|361.1,334.6,306.6,276.2,250.2,240
140|380|309.4,309.4,304.5,275.6,250.2,240|361.1,334.6,306.6,276.2,250.2,240
140|400|322,322,304.5,275.6,250.2,240|361.1,334.6,306.6,276.2,250.2,240"""
def _heavy(raw:str):
    out={}
    for line in raw.splitlines():
        size,h,c20,c25=line.split("|")
        item=out.setdefault(size,{"C20/25":{},"C25/30":{}})
        item["C20/25"][int(h)]=tuple(map(float,c20.split(",")))
        item["C25/30"][int(h)]=tuple(map(float,c25.split(",")))
    return out
HEAVY={"axial":_heavy(_AXIAL),"transverse":_heavy(_TRANSVERSE)}
SINGLE_WIDTHS=(10,20,30,40)
SINGLE_GEO={20:(160,310,160,10,60,80),22:(160,350,175,10,60,90),25:(175,410,200,12,70,100),30:(210,560,240,14,90,110)}
SINGLE_STEEL={"axial":{20:(14.3,9.5,7.1,5.7),22:(18.1,12.2,9.3,7.4),25:(24.8,17.1,13.1,10.6),30:(38.5,27.5,21.4,17.5)},"transverse":{20:(12.8,8.6,6.4,5.1),22:(16.3,11,8.3,6.7),25:(22.3,15.4,11.8,9.5),30:(34.6,24.7,19.2,15.7)}}
SINGLE_CONCRETE={"axial":{20:{160:14.2,180:15.8},22:{160:14.2,180:15.8,200:17.3,220:18.9,240:20.4},25:{180:20.5,200:22.4,220:24.3,240:26.2,260:28},30:{220:29.3,240:31.5,260:33.7,280:35.9,300:38.1,320:40.2}},"transverse":{20:{180:13},22:{180:12.5,200:13.9,220:15.3,240:16.7},25:{200:18,220:19.8,240:21.5,260:23.2},30:{220:24.6,240:26.7,260:28.7,280:30.7,300:32.7,320:34.7}}}
def _norm(text:str)->str:
    return re.sub(r"\s+"," ",str(text or "").upper().replace("–","-").replace("—","-")).strip()
def decode_designation(text:str)->dict[str,Any]|None:
    raw=_norm(text)
    if "HSD" not in raw:return None
    m=re.search(r"\bHSD\s*[- ]?\s*CRET\s*[- ]?\s*(122|124|128|134|140|145|150|155)\s*(V)?\b",raw)
    if m:
        size=m.group(1); trans=bool(m.group(2)); movement="transverse" if trans else "axial"; section,hmin=GEOM[size]
        return {"manufacturer":"Leviat / HALFEN","family":"HSD-CRET V" if trans else "HSD-CRET","size":size,"movement":movement,"designation":f"HSD-CRET {size}{' V' if trans else ''}","dowel_section_mm":section,"hmin_mm":hmin,"max_joint_mm":60,"complete_system":True,"component_only":False,"halfen_hsd_2026":True,"catalog":CATALOG_ID,"catalog_edition":CATALOG_EDITION,"source":CATALOG_SOURCE}
    m=re.search(r"\bHSD\s*[- ]?\s*SET\s*[- ]?\s*(20|22|25|30)\s*(V)?(?:\s*-?\s*A4)?\b",raw)
    if m:
        d=int(m.group(1)); trans=bool(m.group(2)); movement="transverse" if trans else "axial"
        return {"manufacturer":"Leviat / HALFEN","family":"HSD-SET V" if trans else "HSD-SET","size":str(d),"diameter_mm":d,"movement":movement,"designation":f"HSD-SET {d}{' V' if trans else ''}-A4","socket":"HSD-SV" if trans else "HSD-S","hmin_mm":SINGLE_GEO[d][0],"max_joint_mm":40,"complete_system":True,"component_only":False,"halfen_hsd_2026":True,"catalog":CATALOG_ID,"catalog_edition":CATALOG_EDITION,"source":CATALOG_SOURCE}
    m=re.search(r"\bHSD\s*[- ]?\s*D\s*[- ]?\s*(20|22|25|30)(?:\s*-?\s*(A4|FV))?\b",raw)
    if m:
        d=int(m.group(1)); material=m.group(2) or ""
        return {"manufacturer":"Leviat / HALFEN","family":"HSD-D","size":str(d),"diameter_mm":d,"movement":"component","designation":f"HSD-D {d}{('-'+material) if material else ''}","component_only":True,"complete_system":False,"halfen_hsd_2026":True,"catalog":CATALOG_ID,"catalog_edition":CATALOG_EDITION,"source":CATALOG_SOURCE}
    m=re.search(r"\bHSD\s*[- ]?\s*(SV|S|P)\s*[- ]?\s*(20|22|25|30)\b",raw)
    if m:
        sock=m.group(1); d=int(m.group(2)); movement="transverse" if sock=="SV" else "axial"
        return {"manufacturer":"Leviat / HALFEN","family":f"HSD-{sock}","size":str(d),"diameter_mm":d,"movement":movement,"designation":f"HSD-{sock} {d}","component_only":True,"complete_system":False,"halfen_hsd_2026":True,"catalog":CATALOG_ID,"catalog_edition":CATALOG_EDITION,"source":CATALOG_SOURCE}
    return None
def _concrete(value:str):
    m=re.search(r"C(\d+)\s*/\s*(\d+)",_norm(value).replace(" ",""))
    if not m:return None,"Beton musí být ve formátu např. C25/30."
    n=int(m.group(1))
    if n<20:return None,"Katalog HSD uvádí tabulky od C20/25."
    if n==20:return "C20/25",""
    return "C25/30",("" if n==25 else f"{value}: dle katalogu použita tabulka C25/30.")
def _gap(gap:float,widths):
    if not math.isfinite(gap) or gap<0:return None
    return next((w for w in widths if gap<=w+1e-9),None)
def _height(h:float,rows):
    vals=[v for v in rows if v<=h+1e-9]
    return max(vals) if vals else None
def capacity_for(info_or_text:dict[str,Any]|str,slab_mm:float,gap_mm:float,concrete:str="C25/30"):
    info=decode_designation(info_or_text) if isinstance(info_or_text,str) else dict(info_or_text)
    if not info or not info.get("halfen_hsd_2026"):return None,"Označení není produkt HALFEN / Leviat HSD z katalogu HSD EC 10-E."
    if info.get("component_only"):return None,"Samostatná komponenta HSD neurčuje celý komplet; VRd se proto nepřiřazuje."
    fam=str(info.get("family","")); movement=str(info.get("movement","axial")); size=str(info.get("size","")); h=float(slab_mm); gap=float(gap_mm)
    if fam.startswith("HSD-CRET"):
        if size in {"145","150","155"}:return None,f"HSD-CRET {size}: katalog uvádí dimenzační únosnosti pouze na vyžádání."
        conc,cnote=_concrete(concrete)
        if conc is None:return None,cnote
        g=_gap(gap,WIDTHS)
        if g is None:return None,"Maximální šířka spáry HSD-CRET je 60 mm."
        rows=HEAVY[movement][size][conc]; ht=_height(h,rows)
        if ht is None:return None,f"Tloušťka {h:g} mm je menší než minimální {GEOM[size][1]} mm pro HSD-CRET {size}."
        v=rows[ht][WIDTHS.index(g)]; note="Bez interpolace: h dolů, spára nahoru. Hodnota platí při předepsaném závěsném vyztužení dle katalogu."+(" "+cnote if cnote else "")
        return {"vrd":v,"VRd":v,"movement":movement,"slab_table_mm":ht,"gap_table_mm":g,"concrete_table":conc,"source":CATALOG_SOURCE,"note":note,"conditional":True},""
    if fam.startswith("HSD-SET"):
        d=int(info["diameter_mm"]); g=_gap(gap,SINGLE_WIDTHS)
        if g is None:return None,"Katalogová tabulka jednoduchých HSD-D končí šířkou spáry 40 mm."
        rows=SINGLE_CONCRETE[movement][d]; ht=_height(h,rows)
        if ht is None:return None,f"Pro HSD-SET {d}{' V' if movement=='transverse' else ''} není při h={h:g} mm číselná hodnota VRd,c. První použitelná je h={min(rows)} mm."
        vs=SINGLE_STEEL[movement][d][SINGLE_WIDTHS.index(g)]; vc=rows[ht]; v=min(vs,vc); _,cnote=_concrete(concrete)
        note="VRd=min(VRd,s; VRd,c) pro vyztužený beton, cnom=30 mm; nutné je předepsané Asx/Asy. Bez interpolace: h dolů, spára nahoru."+(" "+cnote if cnote else "")
        return {"vrd":v,"VRd":v,"vrd_steel":vs,"vrd_concrete":vc,"movement":movement,"slab_table_mm":ht,"gap_table_mm":g,"concrete_table":">= C20/25","source":CATALOG_SOURCE,"note":note,"conditional":True},""
    return None,"Pro danou komponentu HSD není přiřazena systémová únosnost."
def selftest():
    a=decode_designation("HSD-CRET-124"); v,e=capacity_for(a,280,30,"C25/30"); assert not e and v and v["vrd"]==108.8
    a=decode_designation("HSD-CRET 124 V"); v,e=capacity_for(a,280,30,"C25/30"); assert not e and v and v["vrd"]==101.4
    v,e=capacity_for("HSD-CRET 124",287,21,"C35/45"); assert not e and v and v["slab_table_mm"]==280 and v["gap_table_mm"]==30 and v["vrd"]==108.8
    v,e=capacity_for("HSD-CRET 145",500,30,"C25/30"); assert v is None and "vyžádání" in e
    a=decode_designation("HSD-SET 25 V-A4"); v,e=capacity_for(a,240,30,"C25/30"); assert not e and v and v["vrd"]==11.8
    a=decode_designation("HSD-D 22-A4"); v,e=capacity_for(a,200,20,"C25/30"); assert v is None and "komponenta" in e
if __name__=="__main__":selftest()
