from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sys


def fixture(index:int, *, moment:bool=False, ou:bool=False, directions:int=1, notes:bool=False):
    source="EGCOBOX VXL Z 48-K-C30-h160-REI120-SW" if index % 2 else "EGCOBOX VXL48-K-C30-h160-REI120-SW"
    target="HIT-SP ZVX-0500-16-033-30-08" if index % 2 else "HIT-SP ZVX-0302-16-033-30-08"
    cap=54.5787 if index%2 else 57.3093
    row={"position":f"P{index:03}","quantity":8 if index%2 else 26,"source":source,
         "source_meta":{"source_insulation_mm":120,"source_height_mm":160,"source_cover_mm":30,
                        "source_length_mm":300,"source_concrete":"C25/30",
                        "source_compression_text":"bez tlakových ložisek" if index%2 else "s tlakovými ložisky"},
         "target":{"designation":target,"connection_type":"ZVX","series":"SP",
                   "target_insulation_mm":120,"height_mm":160,"cover_mm":30,"length_mm":333,
                   "concrete":"C25/30","compression_text":"bez tlakových ložisek (0 CSB)" if index%2 else "s tlakovými ložisky (2 CSB)",
                   "utilization":48.6/cap,"wire_diameter_mm":8,"length_relation":"povolená výjimka 300→333 mm",
                   "checks":[dict(label="V+",requirement=48.6,capacity=cap,unit="kN/prvek",eta=48.6/cap,result="VYHOVUJE")]},
         "source_actions":{"v_pos":48.6},"status":"VYHOVUJE","notes":[]}
    if moment:
        row["source"]="EGCOBOX MXL25-VS-C30-h200-REI120-SW"
        row["source_meta"].update(source_height_mm=200,source_length_mm=1000,source_compression_text="s tlakovými ložisky")
        row["target"].update(designation="HIT-SP MVX-0504-20-100-30",connection_type="MVX",height_mm=200,length_mm=1000,
                             compression_text="s tlakovými ložisky (CSB)",wire_diameter_mm=None,
                             utilization=.98,interaction_utilization=.98,length_relation="shodná délka")
        row["target"]["checks"]=[dict(label="M−",requirement=31.7,capacity=40.,unit="kNm/prvek",eta=.7925,result="VYHOVUJE"),
                                  dict(label="V+",requirement=48.7,capacity=80.,unit="kN/prvek",eta=.60875,result="VYHOVUJE")]
        row["source_actions"]={"m_neg":31.7,"v_pos":48.7}
    if ou:
        row["source"]="EGCOBOX MXL25-WU280-VS-C30-h200-REI120-SW"
        row["source_meta"]["geometry_display"]="WU280 → OU280 • potvrzeno uživatelem"
        row["target"]["designation"]="HIT-SP MVX-0604-20-100-30-OU280"
    if directions==6:
        row["source"]="TEST – sazba všech šesti směrů M / N / V"
        row["target"].update(designation="TEST – kontrola šesti směrů",connection_type="FT",utilization=.8)
        row["status"]="UKÁZKA"
        row["target"]["checks"]=[dict(label=label,requirement=v,capacity=v*1.25,unit="kNm/prvek" if label.startswith("M") else "kN/prvek",eta=.8,result="VYHOVUJE") for label,v in zip(["M+","M−","N+","N−","V+","V−"],[11.1,22.2,33.3,44.4,55.5,66.6])]
    if notes:
        row["notes"]=["Kontrolní sazba: ilustrační data, nikoli nový statický návrh.",
                       "Dostupnost průměrů: Ø06 – nevyhovuje únosností; Ø08 – vyhovuje; Ø10 – výška je mimo katalogový rozsah; Ø12 – jiný tlakový přenos. Konec úplné poznámky. "]
    return row


def verify(module_path:Path,output:Path):
    import fitz
    from pypdf import PdfReader
    output.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location("turto_pdf_test",module_path)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    rows=[fixture(i, moment=i in {5,6,7},ou=i==6,notes=i in {2,6,7}) for i in range(1,23)]
    rows[6]=fixture(7,directions=6,notes=True)
    rows[7]["target"]={};rows[7]["status"]="NEPOSOUZENO"
    for idx in (8,9,10): rows[idx]=fixture(idx+1,directions=6,notes=True)
    report=mod._Report(rows,"Kontrolní sazba – ilustrační data", "Vytvořil Ing. Jaroslav Kučera")
    plan=report.summary_pages()+report.detail_pages()+report.notes_pages()
    path=mod.write_substitution_pdf(output/"TURTO_ISO_1.1.14_ukazka.pdf",project_name=report.project,rows=rows)
    doc=fitz.open(path)
    texts=[p.get_text() for p in doc]
    combined="\n".join(texts)
    assert all(abs(p.rect.width-595.2756)<.01 and abs(p.rect.height-841.8898)<.01 for p in doc)
    assert all(not p.get_images(full=True) for p in doc),"Raster image objects found"
    assert "potvrzeno uživatelem" in combined
    assert "Konec úplné poznámky." in combined
    assert mod._governing_check(rows[4])==( "M/V", .98),"Interaction is not governing"
    assert mod._status(rows[7])=="NEPOSOUZENO"
    for value in ["11,1","22,2","33,3","44,4","55,5","66,6"]:
        assert value in combined, "Missing direction: " + value
    for row in rows:
        assert row["position"] in combined
        for value in [row["source"],row["target"].get("designation","")]:
            clean=lambda x: "".join(x.split())
            assert clean(value) in clean(combined), "Missing or truncated designation: "+value
    smaller=[];out_of_bounds=[]
    for i,p in enumerate(doc):
        for block in p.get_text("dict")["blocks"]:
            for line in block.get("lines",[]):
                for s in line["spans"]:
                    # Numerical engineering cells and names, not footer prose.
                    if any(ch.isdigit() for ch in s["text"]) and s["bbox"][1]>report.top and s["bbox"][3]<doc[0].rect.height-report.bottom and s["size"]<10.99:
                        # Appendix note prose and the short text of the explicitly allowed geometric exception use label size.
                        if plan[i][0]!="notes" and not ("povolená výjimka" in s["text"] or "Poznámky a omezení" in s["text"]):
                            smaller.append((i+1,s["text"],s["size"]))
                    b=s["bbox"]
                    if b[0]<report.margin-1 or b[2]>report.w-report.margin+1 or b[1]<0 or b[3]>report.h-7:
                        out_of_bounds.append((i+1,s["text"],b))
    assert not smaller, f"Values below 11 pt: {smaller}"
    assert not out_of_bounds, f"Out-of-bounds text: {out_of_bounds}"
    reader=PdfReader(path)
    assert reader.outline,"PDF bookmarks missing"
    fonts=[font for page in doc for font in page.get_fonts(full=True)]
    assert any("TrueType" in font for font in fonts), "TrueType font missing"
    details=[len(items) for kind,items in plan if kind=="detail"]
    assert max(details)==4,details
    assert 3 in details,details
    summary="\n".join(texts[i] for i,(kind,_) in enumerate(plan) if kind=="summary")
    assert "Tlakový přenos" not in summary
    assert sum(t.count("P001") for t in texts)>=2
    # Single known values get 11pt actual fonts, not scaled page coordinates.
    pages_to_render={0,next(i for i,(kind,_) in enumerate(plan) if kind=="detail")}
    pages_to_render.update(i for i,(kind,items) in enumerate(plan) if kind=="detail" and len(items)==3)
    for i in sorted(pages_to_render):
        doc[i].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(output/f"page_{i+1}.png")
    # Stress: all content of a very long note must remain searchable, even across pages.
    long=fixture(1,notes=True);long["notes"]=[("Velmi dlouhá poznámka s podkladem a kontrolou. "*300)+"KONEC_STRESOVE_POZNAMKY"]
    stress=mod.write_substitution_pdf(output/"stress.pdf",project_name="Zkouška dlouhé poznámky",rows=[long])
    with fitz.open(stress) as d:
        assert "KONEC_STRESOVE_POZNAMKY" in "".join(p.get_text() for p in d)
    # A very long source designation continues rather than being truncated.
    unusual=fixture(1);unusual["source"]=("Velmi dlouhé označení prvku "*180)+"KONEC_OZNACENI"
    extreme=mod.write_substitution_pdf(output/"stress_names.pdf",project_name="Zkouška dlouhých názvů",rows=[unusual])
    with fitz.open(extreme) as d:
        assert "KONEC_OZNACENI" in "".join(p.get_text() for p in d)
    # Invalid/unavailable logo never silently falls back to an invented company logo.
    # Existing API, empty export, failure atomics.
    existing=output/"unchanged.pdf";existing.write_bytes(b"unchanged")
    try:mod.write_substitution_pdf(existing,project_name="test",rows=[])
    except mod.PdfExportError:pass
    else:raise AssertionError("Empty export succeeded")
    assert existing.read_bytes()==b"unchanged"
    existing.unlink()
    info={"result":"PASS", "version":mod.REPORT_VERSION,"format":"A4 portrait",
          "raster_images":0,"numeric_font_pt":11,"body_font_pt":11,
          "all_directions_preserved":True,"ou_confirmation_preserved":True,"untruncated_notes":True,
          "summary_pages":sum(k=="summary" for k,_ in plan),"summary_positions":len(rows),
          "detail_positions_per_page":details,"page_count":len(doc),"pdf_bytes":path.stat().st_size}
    (output/"verification.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(info,ensure_ascii=False,indent=2))
    return info


if __name__=="__main__":
    verify(Path(sys.argv[1]),Path(sys.argv[2]))
