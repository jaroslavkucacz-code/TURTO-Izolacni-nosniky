"""Import/UI/length regression checks. Synthetic candidates test plumbing only."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch


def verify(directory: Path, output: Path):
    output.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(directory))
    import hit_schedule as hs
    import hit_workspace as hw
    from hit_core import Candidate
    count=0
    def check(value,label):
        nonlocal count
        assert value,label
        count+=1
    def rejects(call,label):
        try:call()
        except ValueError:check(True,label)
        else:raise AssertionError(label)
    rows=hs.parse_schedule(hs.EXAMPLE)
    check(len(rows)==33,"all 33 source positions")
    check(sum(r.kind=="Ohybový" for r in rows)==28,"28 bending positions")
    check(sum(r.kind=="Smykový" for r in rows)==5,"5 shear positions")
    check(not any(r.errors for r in rows),"all supplied rows parse")
    for row,(v,m) in zip(rows,hs.SAMPLE_PAIRS):
        check((row.ved,row.med)==(v,m),"source MEd/VEd values")
    check((rows[-2].length_mm,rows[-1].length_mm)==(100,500),"source lengths in physical mm")
    marked="| "+hs.EXAMPLE.replace("\n"," |\n| ",1)
    marked=marked.replace(" |\n"," |\n| -------- |\n",1)
    check(len(hs.parse_schedule(marked))==33,"Markdown header is a real first data row")
    duplicate=hs.parse_schedule(hs.EXAMPLE+"\n"+rows[0].source)
    check(len(duplicate)==34 and duplicate[0].source==duplicate[-1].source,"do not deduplicate")
    for text in (
        "Ohybový V_ed = 21,5 kN/m M_ed = −19,3 kNm/m",
        "Ohybový MEd = 19 kN·m/m\tVEd = 21 kN/m",
        "Ohybový MEd = 19 kN.m/m, VEd = 21 kN/m",
        "Ohybový MEd = 1 234,5 kNm/m, VEd = 1 500 kN/m",
        "Smykový délky 50 cm Ved = 70 kN/m",
        "Smykový L = 500 mm Ved = 70 kN/m",
    ):
        check(not hs.parse_schedule(text)[0].errors,"accepted spelling: "+text)
    for text in (
        "Smykový Ved = 50 kN", "Smykový Ved = 50 N/m", "Smykový Ved = 50",
        "Smykový Ved = NaN kN/m", "Smykový Ved = inf kN/m", "Smykový Ved = 1e6 kN/m",
        "Smykový Ved = 50 kN/m Ved = 60 kN/m", "Ohybový Ved = 10 kN/m",
        "Smykový Ved = 10 kN/m NEd = 3 kN/m", "Smykový Ved = 0 kN/m",
        "Smykový délky 0 m Ved = 10 kN/m", "Smykový délky 0,0001 m Ved = 10 kN/m",
        "Smykový délky 1 Ved = 10 kN/m", "Smykový Ved = 50 kNm/m",
        "Ohybový Med = 20 kN/m Ved = 30 kN/m", "Smykový Med=2 kNm/m Ved=20 kN/m",
        "Smykový délky 0,5 m L=250 mm Ved=10 kN/m", "Smykový Ved- = +10 kN/m",
        "Tento řádek nelze přečíst",
    ):
        check(bool(hs.parse_schedule(text)[0].errors),"reject unsafe input: "+text)
    rejects(lambda:hs.parse_schedule("a"*1_000_001),"clipboard size guard")
    rejects(lambda:hs.parse_schedule(("Smykový Ved=1 kN/m\n")*501),"row count guard")
    d=hs.row_defaults(rows[0],hs.DEFAULTS,"N001")
    check(d["med_neg"]=="19" and d["med_pos"]=="" and d["ved_pos"]=="21","unsigned moment convention visible")
    for row in rows[28:]:
        d=hs.row_defaults(row,{**hs.DEFAULTS,"cover":"50"},"S")
        check(d["cover"]=="30","fixed shear cover follows existing workspace")
    d=hs.row_defaults(rows[-1],hs.DEFAULTS,"S")
    check(d["ved_pos"]=="70" and d["required_length"]=="500","never multiply line load by source length")
    pos=hs.parse_schedule("Ohybový Med=+19 kNm/m Ved=21 kN/m")[0]
    rejects(lambda:hs.row_defaults(pos,hs.DEFAULTS,"P"),"explicit positive moment cannot silently enter MVX M-")
    d=hs.row_defaults(pos,{**hs.DEFAULTS,"bending":"DD"},"P")
    check(d["med_pos"]=="19","positive moment retained with compatible type")
    neg=hs.parse_schedule("Smykový Ved=-21 kN/m")[0]
    rejects(lambda:hs.row_defaults(neg,hs.DEFAULTS,"P"),"negative shear must not be discarded by ZVX")
    check(hs.row_defaults(neg,{**hs.DEFAULTS,"shear":"ZDX"},"P")["ved_neg"]=="21","negative shear into ZDX")
    for key,value in (("height","200,5"),("height","201"),("height","0"),("cover","40"),("concrete","C99/100"),("series","XX")):
        rejects(lambda key=key,value=value:hs.row_defaults(rows[0],{**hs.DEFAULTS,key:value},"P"),"invalid parameter "+key)
    check(hs.required_length_codes("",{100,50})=={100,50},"blank length uses global options")
    check(hs.required_length_codes("500",{100,50})=={50},"physical 500 mm maps to code 50")
    check(hs.required_length_codes("1000",{100,50})=={100},"physical 1000 mm maps to code 100")
    for length,allowed in (("100",{100,50}),("0",{100}),("500.0",{50}),("-500",{50}),("500",{100}),("",set())):
        rejects(lambda length=length,allowed=allowed:hs.required_length_codes(length,allowed),"reject unavailable/ambiguous length "+length)
    field_map={"med_pos":"m_pos","med_neg":"m_neg","ved_pos":"v_pos","ved_neg":"v_neg"}
    for typ,directions in hs.DIRECTIONS.items():
        check({field_map[k] for k in directions}=={k for k,v in hw.HIT_ACTION_FIELD_MASKS[typ].items() if v},"existing direction mask "+typ)

    class FakeDatabase:
        def __init__(self):self.calls=[];self.force_wrong_length=False
        def proposal_candidates(self,typ,series,height,cover,concrete,actions,lengths,*args,**kwargs):
            self.calls.append(dict(typ=typ,series=series,height=height,cover=cover,concrete=concrete,actions=actions,lengths=set(lengths)))
            codes={100} if self.force_wrong_length else lengths
            return [Candidate(series=series,connection_type=typ,code="0101",length_code=code,suffix="" if typ in {"MVX","MVXL"} else "06",
                              h_table=height-cover,concrete=concrete,m1=100,v1=200,m2=120,v2=150,page=1,cover=cover,height=height,
                              utilization=0.5,mode="synthetic plumbing fixture, not a design") for code in sorted(codes,reverse=True)],"",{}
    class App(hw.HitWorkspaceMixin,tk.Tk):
        def __init__(self):
            super().__init__()
            self.geometry("1260x940+0+0");self.title("HIT import regression")
            self.colors=dict(bg="#F4F6F8",panel="#FFFFFF",panel_alt="#EEF2F5",text="#172B40",muted="#536779",border="#CCD5DF",danger="#A02020",warning_text="#926008")
            self.theme_name="light";self.style=ttk.Style(self)
            self.settings={};self.settings_path=output/"settings.json";self.root_dir=directory
            self._init_hit_workspace()
            frame=ttk.Frame(self);frame.pack(fill="both",expand=True);self._build_hit_tab(frame)
        def _try_load_hit_data(self):self.hit_db=FakeDatabase()
        def _save_settings(self):pass
    def widgets(parent):
        yield parent
        for child in parent.winfo_children():yield from widgets(child)
    app=App();app.update()
    try:
        check(any(isinstance(w,ttk.Button) and w.cget("text")=="Vložit výkaz…" for w in widgets(app)),"import entry point present in actual HIT toolbar")
        check(hasattr(app.hit_rows[0],"required_length_entry"),"physical length editable on ordinary rows")
        dialog=hs.HitScheduleDialog(app);dialog.example();app.update()
        check(len(dialog.tree.get_children())==33,"real Tk preview 33 rows")
        check(dialog.import_button.instate(["disabled"]),"acknowledgement required")
        for k,v in (("height","240"),("cover","50"),("concrete","C30/37"),("series","SP")):
            dialog.options[k].set(v)
        check(dialog.payloads[0]["height"]=="240" and dialog.payloads[0]["concrete"]=="C30/37","common inputs update preview")
        check(dialog.payloads[28]["cover"]=="30","preview shear cover locked")
        dialog.tree.selection_set("0","1")
        dialog.edit_selected();app.update()
        popup=[w for w in dialog.winfo_children() if isinstance(w,tk.Toplevel)][0]
        controls=[w for w in widgets(popup) if isinstance(w,ttk.Combobox)]
        controls[0].set("220")
        [w for w in widgets(popup) if isinstance(w,ttk.Button) and w.cget("text")=="Použít na označené"][0].invoke()
        check(dialog.payloads[0]["height"]=="220" and dialog.payloads[1]["height"]=="220" and dialog.payloads[2]["height"]=="240","selected-row parameter dialog works")
        dialog.tree.selection_set("2");dialog.include(False)
        check(2 not in dialog.included,"exclude selected row")
        dialog.include(True);check(2 in dialog.included,"include selected row")
        dialog.ack.set(True);dialog.render();check(not dialog.import_button.instate(["disabled"]),"ack enables verified import")
        dialog.options["height"].set("250")
        check(not dialog.ack.get() and dialog.import_button.instate(["disabled"]),"setting change requires renewed review")
        # Changing the text after preview must not import stale values.
        dialog.ack.set(True);dialog.render();dialog.text.insert("end","\n")
        with patch.object(hs.messagebox,"showinfo") as info:dialog.commit()
        check(len(app.hit_rows)==1 and not dialog.ack.get() and info.called,"stale preview blocked")
        dialog.ack.set(True);dialog.render();app.update()
        try:
            from PIL import ImageGrab
            ImageGrab.grab().save(output/"hit_schedule_preview.png")
        except Exception:pass
        with patch.object(hs.messagebox,"showerror",side_effect=AssertionError("unexpected import dialog error")):
            dialog.import_button.invoke()
        app.update()
        check(len(app.hit_rows)==33,"33 actual input rows after import, blank placeholder removed")
        check(len({r.name.get() for r in app.hit_rows})==33,"unique position identifiers")
        check(app.hit_rows[0].med_neg.get()=="19" and app.hit_rows[0].ved_pos.get()=="21","real input MEd/VEd")
        check(app.hit_rows[-1].ved_pos.get()=="70","real half-metre line load unchanged")
        short,last=app.hit_rows[-2:]
        check(short.required_length.get()=="100" and short.selected_candidate is None and "100 mm" in short.detail.get(),"100 mm cannot become 1000 mm candidate")
        check(last.selected_candidate.physical_length_mm==500,"500 mm row only receives 500 mm HIT")
        check(app.hit_db.calls[-1]["lengths"]=={50} and app.hit_db.calls[-1]["actions"].v_pos==70,"core receives correct length code and unchanged line load")
        check(all(call["concrete"]=="C30/37" for call in app.hit_db.calls),"no other concrete passed to candidate search")
        check(last.future_link_payload()["required_length_mm"]=="500","length in downstream payload")
        app.copy_hit_results();copied=app.clipboard_get().splitlines()
        check("L požadované [mm]" in copied[0] and "Výkaz – původní text" in copied[0],"clipboard has source audit columns")
        check(all(len(line.split("\t"))==len(copied[0].split("\t")) for line in copied),"clipboard column alignment")
        check("délky 0.5m" in copied[-1] and "\t70\t" in copied[-1],"original source text and unchanged load in export")
        app.hit_l050_var.set(False);last.recalculate()
        check(last.selected_candidate is None and "povolit" in last.detail.get(),"disabled global length blocks row")
        app.hit_l050_var.set(True);last.recalculate()
        check(last.selected_candidate is not None,"reenabling global length recalculates")
        app.hit_db.force_wrong_length=True;last.recalculate()
        check(last.selected_candidate is None,"reject wrong-length candidate even if database returns it")
        app.hit_db.force_wrong_length=False;last.recalculate()
        # Construction failure cannot replace or append a partial assignment.
        before=list(app.hit_rows);before_widgets=set(app.hit_rows_frame.winfo_children());real_class=hw.HitInputRow;calls=0
        def broken(owner,index,defaults):
            nonlocal calls
            calls+=1
            if calls==2:raise RuntimeError("injected construction failure")
            return real_class(owner,index,defaults)
        with patch.object(hw,"HitInputRow",side_effect=broken):
            try:hs.install_rows(app,[hs.row_defaults(rows[0],hs.DEFAULTS,"A"),hs.row_defaults(rows[1],hs.DEFAULTS,"B")],True)
            except RuntimeError:pass
            else:raise AssertionError("expected rollback")
        check(app.hit_rows==before and set(app.hit_rows_frame.winfo_children())==before_widgets,"construction failure preserves all previous rows and widgets")
        # Replacement is explicit and cancel leaves all rows untouched.
        dialog=hs.HitScheduleDialog(app);dialog.text.insert("1.0",rows[0].source);dialog.analyze();dialog.ack.set(True);dialog.render();dialog.replace.set(True)
        with patch.object(hs.messagebox,"askyesno",return_value=False):dialog.commit()
        check(app.hit_rows==before,"cancel replacement preserves existing assignment")
        with patch.object(hs.messagebox,"askyesno",return_value=True):dialog.commit()
        check(len(app.hit_rows)==1 and app.hit_rows[0] not in before,"confirmed replacement works")
    finally:app.destroy()
    result=dict(checks=count,source_positions=33,bending_positions=28,shear_positions=5,
                tested_real_tk_widgets=True,length_100_mm_blocked=True,length_500_mm_filtered=True,
                load_units_unchanged=True,design_fixture="Synthetic candidates validate integration only; no new verification of manufacturer capacities.")
    (output/"import_checks.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS HIT schedule:",count,"checks")
    return result
