"""Regrese potvrzování a PDF. Číselný vzorek odpovídá obrazovce P009.

Jde o test stavu/rozhraní, ne o nové ověření statických tabulek výrobce.
Výpočtové jádro je kontrolováno samostatně byte-for-byte proti předchozí verzi.
"""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch


def fixture(sw, pm):
    source = "EGCOBOX MXL25-WU280-VS-C30-h200-REI120-SW"
    row = dict(id="p009", position="P009", quantity=2, note="", source_text=source,
        selection=dict(catalog_id="regression-egcobox", manufacturer="MAX FRANK", model="XL", type_name="MXL-WU",
                       generation="2022", moment_class="MXL25", concrete_min="C25/30", shear_class="VS", cover="C30", height_mm="200"),
        snapshot=dict(designation=source, insulation_thickness_mm=120, element_length_mm=1000,
                      compression_transfer="betonová tlaková ložiska", results=[
                          dict(kind="moment", label="M−", value=-32.1, unit="kNm/element"),
                          dict(kind="shear", label="V+", value=48.7, unit="kN/element")]),
        mapping=dict(status="not_run", targets=[], selected_target_id=None, source_overrides=dict(
            geometry_mode="manual",geometry_variant="OU",geometry_bx_mm=280,geometry_confirmed=True,geometry_origin="confirmed_auto")))
    row = pm.normalize_project_row(row)
    meta = sw.source_metadata(row)
    assert not meta["errors"], meta
    assert not meta["warnings"], meta
    assert meta["geometry_confirmed"]
    values = {k: 0.0 for k in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg")}
    values.update(m_neg=32.1,v_pos=48.7)
    targets = []
    for code, cap in (("0604",37.1), ("0704",43.0)):
        name = f"HIT-SP MVX-{code}-20-100-30-OU280"
        eta_m, eta_v = 32.1/cap, 48.7/64.0
        t = dict(id=name,designation=name, connection_type="MVX",series="SP",target_insulation_mm=120,cover_mm=30,height_mm=200,
                 concrete="C25/30",length_mm=1000,source_length_mm=1000,length_relation="shodná délka",wire_diameter_mm=None,
                 compression_category="bearing",compression_text="s tlakovými ložisky (CSB)",utilization=max(eta_m,eta_v),
                 interaction_utilization=max(eta_m,eta_v),m_capacity_element=cap,v_capacity_element=64.,n_capacity_element=0.,
                 m_capacity=cap,v_capacity=64.,n_capacity=0.,eta_m=eta_m,eta_v=eta_v,eta_n=0.,spacing_max_m=0.,
                 mode="regresní vzorek P009",page=1,m1=cap,m2=cap,v1=64.,v2=64.,
                 actions=copy.deepcopy(values),source_element_actions=copy.deepcopy(values),calculation="Vzorek uložených kontrol P009",checks=[
                     dict(label="M−",requirement=32.1,capacity=cap,unit="kNm/prvek",eta=eta_m,result="VYHOVUJE"),
                     dict(label="V+",requirement=48.7,capacity=64.0,unit="kN/prvek",eta=eta_v,result="VYHOVUJE")])
        targets.append(t)
    mapping = row["mapping"]
    mapping.update(status="review", targets=copy.deepcopy(targets), selected_target_id=targets[0]["id"], source_meta=meta,
                   warnings=["odhad MVX-0504-OU280 nebyl staticky použitelný; použita nejbližší vyhovující varianta"],
                   errors=[],estimated_type="MVX-0504-OU280")
    return row, targets


def verify(directory: Path, output: Path):
    output.mkdir(exist_ok=True,parents=True)
    sys.path.insert(0,str(directory))
    import substitution_workspace as sw
    import substitution_review as rv
    import project_model as pm
    from substitution_pdf import write_substitution_pdf
    import fitz
    row, targets = fixture(sw,pm)
    meta = sw.source_metadata(row)
    count = 0
    def check(assertion, label):
        nonlocal count
        assert assertion, label
        count += 1
    check(rv.review_state(row,meta)["status"] == "review", "geometry confirmation must not clear fallback warning")
    saved_targets = copy.deepcopy(row["mapping"]["targets"])
    rv.accept_substitution(row,meta)
    check(rv.review_state(row,meta)["accepted"], "acceptance")
    check(row["mapping"]["status"]=="ok", "accepted status")
    check(row["mapping"]["targets"] == saved_targets, "confirmation must not alter capacities or requirements")
    check(len(row["mapping"]["warnings"])==1, "raw warning kept for audit")
    check(not rv.review_state(row,meta)["warnings"], "acknowledged warning no longer pending")
    check(len(rv.review_state(row,meta)["audit_notes"])==2, "audit notes retained")
    doc = pm.ProjectDocument(name="Test P009", rows=[row]); doc.save(output/"roundtrip.tinp")
    loaded = pm.ProjectDocument.load(output/"roundtrip.tinp").rows[0]
    check(rv.review_state(loaded,sw.source_metadata(loaded))["accepted"], "save/load acceptance")
    independent = pm.ProjectDocument.from_dict(doc.to_dict()).rows[0]
    independent["mapping"]["substitution_acceptance"]["warnings"].append("x")
    check(len(row["mapping"]["substitution_acceptance"]["warnings"])==1,"deep copy acceptance")
    for label, mutate in (
        ("note", lambda r:r.__setitem__("note","nové upřesnění")),
        ("source designation",lambda r:r.__setitem__("source_text",r["source_text"]+" poznámka")),
        ("height",lambda r:r["selection"].__setitem__("height_mm","210")),
        ("cover",lambda r:r["selection"].__setitem__("cover","C35")),
        ("concrete",lambda r:r["selection"].__setitem__("concrete_min","C30/37")),
        ("length",lambda r:r["mapping"]["source_overrides"].__setitem__("source_length_mm",930)),
        ("geometry",lambda r:r["mapping"]["source_overrides"].__setitem__("geometry_bx_mm",250)),
        ("source value",lambda r:r["snapshot"]["results"][0].__setitem__("value",-33.)),
        ("target",lambda r:r["mapping"].__setitem__("selected_target_id",targets[1]["id"])),
        ("row id",lambda r:r.__setitem__("id","p010")),
        ("warning",lambda r:r["mapping"]["warnings"].append("nutno ověřit kotvení")),
    ):
        mutated=copy.deepcopy(row);mutate(mutated)
        state=rv.review_state(mutated,sw.source_metadata(mutated))
        check(not state["accepted"] and state["status"]!="ok", "invalidate: "+label)
    for key,value in (("utilization",1.01),("utilization",float("nan")),("utilization",float("inf")),("utilization",None),("utilization",True),("interaction_utilization",1.2)):
        bad=copy.deepcopy(row);bad["mapping"].pop("substitution_acceptance",None);bad["mapping"]["targets"][0][key]=value
        check(not rv.review_state(bad,meta)["can_accept"],"block invalid: "+key+str(value))
    for label, mutate in (
        ("failed check",lambda r:r["mapping"]["targets"][0]["checks"][0].__setitem__("result","NEVYHOVUJE")),
        ("bad ratio",lambda r:r["mapping"]["targets"][0]["checks"][0].__setitem__("capacity",20.)),
        ("missing check",lambda r:r["mapping"]["targets"][0]["checks"].pop()),
        ("bad selected id",lambda r:r["mapping"].__setitem__("selected_target_id","missing")),
        ("empty selected id",lambda r:r["mapping"].__setitem__("selected_target_id",None)),
        ("unconfirmed geometry",lambda r:r["mapping"].__setitem__("source_overrides",{})),
        ("other warning",lambda r:r["mapping"]["warnings"].append("tlakový přenos byl odhadnut z označení typu")),
        ("unknown unit",lambda r:r["mapping"]["warnings"].append("nelze převést: síla [bez jednotky]")),
        ("technical error",lambda r:r["mapping"]["errors"].append("nevyhovující geometrie")),
        ("failed design",lambda r:r["mapping"].__setitem__("status","error")),
        ("not calculated",lambda r:r["mapping"].__setitem__("status","not_run")),
    ):
        bad=copy.deepcopy(row);bad["mapping"].pop("substitution_acceptance",None);mutate(bad)
        check(not rv.review_state(bad,sw.source_metadata(bad))["can_accept"],"blocked: "+label)
        try:rv.accept_substitution(bad,sw.source_metadata(bad))
        except ValueError:pass
        else:raise AssertionError("unsafe confirmation: "+label)
    rv.revoke_acceptance(row,meta)
    check(rv.review_state(row,meta)["status"]=="review", "revoke")

    class App(sw.SubstitutionWorkspaceMixin,tk.Tk):
        def __init__(self):
            super().__init__()
            self.withdraw()
            self.colors=dict(bg="#FFFFFF",panel="#FFFFFF",panel_alt="#F1F4F7",success="#23643C",warning_text="#926008",danger="#A02020",muted="#566270",text="#182C40",accent="#1B7090",select="#D0E2E8")
            self.project=pm.ProjectDocument(name="Kontrola zobrazení P009",rows=[copy.deepcopy(row)])
            self._init_substitution_workspace()
            self.frame=ttk.Frame(self);self.frame.pack(fill="both",expand=True)
            self._build_substitution_tab(self.frame)
            self.sub_tree.selection_set("p009")
            self.dirty=False
            self.db_available=True
        def mark_project_dirty(self):self.dirty=True
        def refresh_project_tree(self,select_ids=None):pass
        def _settings(self):return object() if self.db_available else None

    app=App()
    calls=[];prompts=[]
    def recalc(*args,**kwargs):
        calls.append(kwargs)
        return copy.deepcopy(targets),[]
    def question(title,message,**kwargs):
        prompts.append(message);return True
    try:
        with patch.object(sw,"design_targets",side_effect=recalc), patch.object(sw.messagebox,"askyesno",side_effect=question), patch.object(sw.messagebox,"showwarning") as warn, patch.object(sw.messagebox,"showerror") as error, patch.object(sw.messagebox,"showinfo"):
            check(app._payload(app.project.rows[0])[0]["status"]=="KONTROLA", "UI before")
            before=app._pdf_report_rows()
            app.confirm_substitution_choice()
            check(len(calls)==1,"must recalculate before acceptance")
            check(len(prompts)==1 and targets[0]["designation"] in prompts[0],"exact target preview")
            check(not warn.called and not error.called,"UI confirmation succeeded")
            accepted=app.project.rows[0]
            check(app._payload(accepted)[0]["status"]=="VYHOVUJE", "UI after")
            check(app.dirty,"project dirty")
            after=app._pdf_report_rows()
            check(after[0]["status"]=="VYHOVUJE" and after[0]["acceptance_text"], "PDF after")
            check(app._output_rows()[0]["status"]=="VYHOVUJE", "XLSX payload after")
            app.design_substitutions(True)
            check(rv.review_state(accepted,sw.source_metadata(accepted))["accepted"],"identical recalc retains approval")
            app.project.save(output/"confirmed.tinp")
            saved=pm.ProjectDocument.load(output/"confirmed.tinp").rows[0]
            check(rv.review_state(saved,sw.source_metadata(saved))["accepted"],"UI save/load")
            app.revoke_substitution_choice()
            check(app._payload(accepted)[0]["status"]=="KONTROLA","UI revoke")
            app.confirm_substitution_choice()
            app.next_substitution_variant()
            check(not accepted["mapping"].get("substitution_acceptance"),"variant clears confirmation")
            check(app._payload(accepted)[0]["status"]=="KONTROLA","new variant review")
            chosen=accepted["mapping"]["selected_target_id"]
            app.design_substitutions(True)
            check(accepted["mapping"]["selected_target_id"]==chosen,"preserve chosen on recalc")
            # Cancellation and absent HIT data cannot confirm an existing snapshot.
            with patch.object(sw.messagebox,"askyesno",return_value=False):
                app.confirm_substitution_choice()
            check(not accepted["mapping"].get("substitution_acceptance"),"cancel")
            app.db_available=False
            app.confirm_substitution_choice()
            check(not accepted["mapping"].get("substitution_acceptance"),"no database")
            app.db_available=True
            with patch.object(sw,"design_targets",side_effect=RuntimeError("test failure")):
                app.confirm_substitution_choice()
            check(not accepted["mapping"].get("substitution_acceptance"),"failed recalc")
            # A real Tk event reaches the new button; no dead callback/name.
            def descendants(w):
                for ch in w.winfo_children():
                    yield ch;yield from descendants(ch)
            button=next(w for w in descendants(app) if isinstance(w,ttk.Button) and w.cget("text")=="✓ Potvrdit záměnu…")
            button.invoke()
            check(rv.review_state(accepted,sw.source_metadata(accepted))["accepted"],"Tk button invokes")
    finally:
        app.destroy()

    # Exercise actual portrait renderer, vector logo, 11pt numerical cells and long notes.
    regression=directory.parents[1]/"tools/verify_v1114_pdf.py"
    spec=importlib.util.spec_from_file_location("portrait_regression",regression)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    pdf_info=mod.verify(directory/"substitution_pdf.py",output/"portrait_regression")
    new_path=output/"TURTO_ISO_1.1.15_P009_potvrzena_zamena.pdf"
    write_substitution_pdf(new_path,project_name="P009 – kontrolní vzorek potvrzení záměny",rows=after)
    write_substitution_pdf(output/"P009_pred_potvrzenim.pdf",project_name="P009 – před potvrzením záměny",rows=before)
    with fitz.open(new_path) as pdf:
        texts=[p.get_text() for p in pdf]
        alltext="\n".join(texts)
        check("KONTROLA" not in alltext,"no pending status in confirmed PDF")
        check("VYHOVUJE" in alltext and "Záměna potvrzena uživatelem" in alltext,"PDF confirmation text")
        check("Potvrzená informace o původním odhadu" in alltext,"appendix audit retained")
        check(all("Nutno schválit statikem stavby." in text for text in texts),"footer on every page")
        check("Požární odolnost se neposuzuje." not in alltext and "Ověřit projektantem." not in alltext,"old footer absent")
        check(all(not p.get_images(full=True) for p in pdf),"no raster objects")
        check(all(abs(p.rect.width-595.2756)<.01 and abs(p.rect.height-841.8898)<.01 for p in pdf),"portrait retained")
        check(all(v in alltext for v in ["32,1","37,1","48,7","64,0","86,5 %","76,1 %"]),"unchanged P009 numbers")
        for i,p in enumerate(pdf):
            p.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(output/f"confirmed_page_{i+1}.png")
    return dict(result="PASS",checks=count,pdf=pdf_info,case="P009 source: screenshot; status/UI regression, not a new structural assessment",
                acceptance_persistence=True,acceptance_invalidation=True,explicit_dialog=True,
                matching_ui_excel_pdf_status=True,other_warnings_and_failures_not_overridden=True)
