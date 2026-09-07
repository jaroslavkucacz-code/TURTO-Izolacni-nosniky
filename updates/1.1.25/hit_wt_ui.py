from __future__ import annotations

import os, re
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from hit_wt import WtCandidate, design_wt
from xlsx_export import write_xlsx

WT_HEADERS = (
    ("name","Pozice","w"),("quantity","Ks","center"),("series","Řada","center"),
    ("wall_height","Výška stěny h [mm]","center"),("width","Šířka B [mm]","center"),("concrete","Beton","center"),
    ("med_neg","MEd− [kNm/prvek]","center"),("ved_vertical","VEd,v+ [kN/prvek]","center"),("ved_horizontal","VEd,h± [kN/prvek]","center"),
    ("product","Návrh HIT-WT","w"),("util","Využití","center"),("capacity","MRd / VRd,v / VRd,h","center"),
    ("joint","s_joint max.","center"),("source","Zdroj","center"),("status","Výsledek / kontrola","w"),("remove","","center"),
)

def _num(text:str)->float:
    v=str(text or "").strip().replace("−","-").replace(",",".")
    return 0.0 if not v else abs(float(v))

def _qty(text:str)->int:
    v=int(str(text or "1").strip())
    if not 1<=v<=1_000_000: raise ValueError("Počet kusů musí být celé číslo 1–1 000 000.")
    return v

class WtRow:
    def __init__(self, owner:Any, parent:ttk.Frame, row_no:int, defaults:dict[str,Any]|None=None)->None:
        self.owner=owner; self.parent=parent; self.row_no=row_no; d=dict(defaults or {})
        self.name=tk.StringVar(master=owner,value=str(d.get("name",f"W{row_no:03d}")))
        self.quantity=tk.StringVar(master=owner,value=str(d.get("quantity","1")))
        self.series=tk.StringVar(master=owner,value=str(d.get("series","HP")))
        self.wall_height=tk.StringVar(master=owner,value=str(d.get("wall_height","1500")))
        self.width=tk.StringVar(master=owner,value=str(d.get("width","150")))
        self.concrete=tk.StringVar(master=owner,value=str(d.get("concrete","C25/30")))
        self.med_neg=tk.StringVar(master=owner,value=str(d.get("med_neg","")))
        self.ved_vertical=tk.StringVar(master=owner,value=str(d.get("ved_vertical","")))
        self.ved_horizontal=tk.StringVar(master=owner,value=str(d.get("ved_horizontal","")))
        self.product=tk.StringVar(master=owner,value="—"); self.util=tk.StringVar(master=owner,value="—")
        self.capacity=tk.StringVar(master=owner,value="—"); self.joint=tk.StringVar(master=owner,value="—")
        self.source=tk.StringVar(master=owner,value="HIT20.2"); self.status=tk.StringVar(master=owner,value="čeká na zatížení")
        self.saved_designation=str(d.get("selected_designation","") or ""); self.manual_product=bool(d.get("manual_product",False))
        self.candidates:list[WtCandidate]=[]; self.selected_candidate:WtCandidate|None=None; self._after:str|None=None; self.widgets=[]
        self._build(); self.recalculate(preserve=self.saved_designation or None)

    def _entry(self,var,width,justify="center"):
        w=ttk.Entry(self.parent,textvariable=var,width=width,justify=justify); self.widgets.append(w)
        w.bind("<KeyRelease>",self._changed); w.bind("<FocusOut>",self._changed_now); w.bind("<Return>",self._changed_now); w.bind("<MouseWheel>",self.owner._on_wt_mousewheel)
        return w
    def _combo(self,var,values,width):
        w=ttk.Combobox(self.parent,textvariable=var,values=values,state="readonly",width=width,justify="center"); self.widgets.append(w)
        w.bind("<<ComboboxSelected>>",self._changed_now); w.bind("<MouseWheel>",self.owner._on_wt_mousewheel); return w
    def _build(self):
        self._entry(self.name,9,"left"); self._entry(self.quantity,5); self._combo(self.series,("HP","SP"),5)
        self._entry(self.wall_height,11); self._entry(self.width,8); self._combo(self.concrete,("C20/25","C25/30","C30/37"),9)
        self._entry(self.med_neg,11); self._entry(self.ved_vertical,11); self._entry(self.ved_horizontal,11)
        self.product_combo=ttk.Combobox(self.parent,textvariable=self.product,values=(),state="readonly",width=34,justify="left"); self.widgets.append(self.product_combo)
        self.product_combo.bind("<<ComboboxSelected>>",self._product_changed); self.product_combo.bind("<MouseWheel>",self.owner._on_wt_mousewheel)
        self.widgets.append(ttk.Label(self.parent,textvariable=self.util,width=10,anchor="center",style="Card.TLabel"))
        self.widgets.append(ttk.Label(self.parent,textvariable=self.capacity,width=25,anchor="center",style="Card.TLabel"))
        self.widgets.append(ttk.Label(self.parent,textvariable=self.joint,width=12,anchor="center",style="Card.TLabel"))
        self.widgets.append(ttk.Label(self.parent,textvariable=self.source,width=12,anchor="center",style="Card.TLabel"))
        self.status_label=ttk.Label(self.parent,textvariable=self.status,width=38,anchor="w",style="MutedCard.TLabel"); self.widgets.append(self.status_label)
        self.widgets.append(ttk.Button(self.parent,text="×",width=3,command=lambda:self.owner.remove_wt_row(self))); self.regrid(self.row_no)
    def regrid(self,row_no):
        self.row_no=row_no
        for col,w in enumerate(self.widgets): w.grid(row=row_no,column=col,sticky="ew",padx=2,pady=2)
    def destroy(self):
        if self._after:
            try:self.owner.after_cancel(self._after)
            except Exception:pass
        for w in self.widgets:
            try:w.destroy()
            except Exception:pass
    def _mark_dirty(self):
        if not getattr(self.owner,"_action_loading",False) and hasattr(self.owner,"mark_project_dirty"): self.owner.mark_project_dirty()
    def _changed(self,_event=None):
        self.manual_product=False; self.status.set("počítám…"); self._mark_dirty()
        if self._after:
            try:self.owner.after_cancel(self._after)
            except Exception:pass
        self._after=self.owner.after(300,self.recalculate)
    def _changed_now(self,_event=None):
        self.manual_product=False; self._mark_dirty()
        if self._after:
            try:self.owner.after_cancel(self._after)
            except Exception:pass
        self._after=None; self.recalculate()
    def recalculate(self,preserve:str|None=None):
        self._after=None
        try:
            self.quantity.set(str(_qty(self.quantity.get()))); h=int(self.wall_height.get().strip()); b=int(self.width.get().strip())
            m=_num(self.med_neg.get()); vv=_num(self.ved_vertical.get()); vh=_num(self.ved_horizontal.get())
        except Exception as exc: self._error(str(exc) or "Neplatný číselný vstup."); return
        rows,error=design_wt(series=self.series.get(),wall_height_mm=h,width_mm=b,concrete=self.concrete.get(),med_neg=m,ved_vertical=vv,ved_horizontal=vh)
        self.candidates=rows
        if error:
            (self._waiting if max(m,vv,vh)<=1e-9 else self._error)(error); return
        names=[r.designation for r in rows]; self.product_combo.configure(values=names); chosen=rows[0]
        if preserve and preserve in names: chosen=rows[names.index(preserve)]
        self.product.set(chosen.designation); self.selected_candidate=chosen; self.manual_product=bool(preserve and preserve==chosen.designation and chosen is not rows[0])
        self._show(chosen); self.owner.update_wt_status()
    def _show(self,row:WtCandidate):
        self.selected_candidate=row; self.util.set(f"{row.utilization*100:.1f} %".replace(".",","))
        self.capacity.set(f"{row.mrd:.1f} / {row.vrd_vertical:.1f} / {row.vrd_horizontal:.1f}".replace(".",",")); self.joint.set(f"{row.joint_spacing_m:.1f} m".replace(".",",")); self.source.set(f"HIT20.2 p.{row.page}")
        self.status.set(row.mode+(" • ručně zvoleno" if self.manual_product else "")+" • kontroly M/Vv/Vh samostatně"); self.status_label.configure(style="Good.TLabel")
    def _product_changed(self,_event=None):
        value=self.product.get()
        for i,row in enumerate(self.candidates):
            if row.designation==value:
                self.manual_product=i!=0; self._mark_dirty(); self._show(row); self.owner.update_wt_status(); return
    def _reset_result(self,text,style):
        self.candidates=[]; self.selected_candidate=None; self.product_combo.configure(values=()); self.product.set("—"); self.util.set("—"); self.capacity.set("—"); self.joint.set("—"); self.source.set("HIT20.2"); self.status.set(text); self.status_label.configure(style=style); self.owner.update_wt_status()
    def _waiting(self,text): self._reset_result(text,"MutedCard.TLabel")
    def _error(self,text): self._reset_result(text,"Bad.TLabel")
    def payload(self):
        return {"name":self.name.get().strip(),"quantity":_qty(self.quantity.get()),"series":self.series.get().strip(),"wall_height":self.wall_height.get().strip(),"width":self.width.get().strip(),"concrete":self.concrete.get().strip(),"med_neg":self.med_neg.get().strip(),"ved_vertical":self.ved_vertical.get().strip(),"ved_horizontal":self.ved_horizontal.get().strip(),"selected_designation":self.selected_candidate.designation if self.selected_candidate else "","manual_product":bool(self.manual_product)}

def install(base:Any)->None:
    original_init=base.HitWorkspaceMixin._init_hit_workspace
    def init(self): original_init(self); self.wt_rows=[]; self.wt_status_var=tk.StringVar(master=self,value="WT: připraveno.")
    def build_wt(self,parent):
        parent.columnconfigure(0,weight=1); parent.rowconfigure(2,weight=1)
        head=ttk.Frame(parent,style="Card.TFrame",padding=(16,12)); head.grid(row=0,column=0,sticky="ew"); head.columnconfigure(0,weight=1)
        ttk.Label(head,text="Návrh HIT-WT – stěnové prvky",style="ProjectTitle.TLabel").grid(row=0,column=0,sticky="w")
        ttk.Label(head,text="Samostatný návrh konzolových stěn. Účinky jsou na jeden WT prvek: MEd−, svislý VEd,v+ a vodorovný VEd,h±. Zadává se výška stěny h a šířka B.",style="MutedCard.TLabel").grid(row=1,column=0,sticky="w",pady=(3,0))
        bar=ttk.Frame(parent,style="App.TFrame"); bar.grid(row=1,column=0,sticky="ew",pady=(10,8))
        ttk.Button(bar,text="+ Přidat WT",style="Accent.TButton",command=self.add_wt_row).grid(row=0,column=0); ttk.Button(bar,text="Přepočítat vše",command=self.recalculate_wt_all).grid(row=0,column=1,padx=(7,0)); ttk.Button(bar,text="Vymazat vše",command=self.clear_wt_rows).grid(row=0,column=2,padx=(7,0)); ttk.Button(bar,text="Kopírovat tabulku",command=self.copy_wt_table).grid(row=0,column=3,padx=(14,0)); ttk.Button(bar,text="Export Excel",command=self.export_wt_excel).grid(row=0,column=4,padx=(7,0)); bar.columnconfigure(20,weight=1); ttk.Label(bar,textvariable=self.wt_status_var,style="Muted.TLabel").grid(row=0,column=20,sticky="e")
        card=ttk.Frame(parent,style="Card.TFrame",padding=(10,10,10,8)); card.grid(row=2,column=0,sticky="nsew"); card.columnconfigure(0,weight=1); card.rowconfigure(0,weight=1)
        canvas=tk.Canvas(card,highlightthickness=0,background=self.colors["panel"]); y=ttk.Scrollbar(card,orient="vertical",command=canvas.yview); x=ttk.Scrollbar(card,orient="horizontal",command=canvas.xview); canvas.configure(yscrollcommand=y.set,xscrollcommand=x.set); canvas.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); x.grid(row=1,column=0,sticky="ew")
        frame=ttk.Frame(canvas,style="Card.TFrame"); window=canvas.create_window((0,0),window=frame,anchor="nw"); self.wt_canvas=canvas; self.wt_rows_frame=frame; self.wt_canvas_window=window
        for col,(_key,label,anchor) in enumerate(WT_HEADERS): ttk.Label(frame,text=label,style="Card.TLabel",font=("Calibri",10,"bold"),anchor=("w" if anchor=="w" else "center")).grid(row=0,column=col,sticky="ew",padx=2,pady=(0,5)); frame.columnconfigure(col,weight=1 if anchor=="w" else 0)
        frame.bind("<Configure>",lambda _e:canvas.configure(scrollregion=canvas.bbox("all"))); canvas.bind("<Configure>",lambda e:canvas.itemconfigure(window,width=max(e.width,frame.winfo_reqwidth()))); canvas.bind("<MouseWheel>",self._on_wt_mousewheel)
        ttk.Label(parent,text="Katalog HIT 20.2-EN: B = 150–250 mm. WT1–WT4 mají tabulované h = 1250–3500 mm, WT5–WT7 h = 1000–3500 mm. Automatický návrh používá tabulované kroky 250 mm; netabulované geometrie se neinterpolují. MRd, VRd,v a VRd,h se kontrolují samostatně.",style="Muted.TLabel",wraplength=1500,justify="left").grid(row=3,column=0,sticky="ew",pady=(8,0))
        if not self.wt_rows:self.add_wt_row(mark_dirty=False)
    def wheel(self,event):
        d=int(getattr(event,"delta",0) or 0)
        if d and hasattr(self,"wt_canvas"):self.wt_canvas.yview_scroll(-1 if d>0 else 1,"units")
        return "break"
    def add(self,defaults=None,*,mark_dirty=True):
        row=WtRow(self,self.wt_rows_frame,len(self.wt_rows)+1,defaults); self.wt_rows.append(row)
        if mark_dirty and not getattr(self,"_action_loading",False) and hasattr(self,"mark_project_dirty"):self.mark_project_dirty()
        self.update_wt_status(); return row
    def remove(self,row):
        if row not in self.wt_rows:return
        row.destroy();self.wt_rows.remove(row)
        for i,item in enumerate(self.wt_rows,1):item.regrid(i)
        if not getattr(self,"_action_loading",False) and hasattr(self,"mark_project_dirty"):self.mark_project_dirty()
        self.update_wt_status()
    def clear(self,*,mark_dirty=True):
        for row in list(self.wt_rows):row.destroy()
        self.wt_rows.clear()
        if mark_dirty and not getattr(self,"_action_loading",False) and hasattr(self,"mark_project_dirty"):self.mark_project_dirty()
        self.update_wt_status()
    def recalc(self):
        for row in self.wt_rows:row.recalculate(preserve=row.product.get() if row.manual_product else None)
        self.update_wt_status()
    def status(self):
        if not hasattr(self,"wt_status_var"):return
        ok=sum(1 for r in self.wt_rows if r.selected_candidate is not None); pieces=0
        for r in self.wt_rows:
            try:pieces+=_qty(r.quantity.get())
            except Exception:pass
        self.wt_status_var.set(f"{len(self.wt_rows)} řádků • {pieces} ks • {ok} navrženo")
    def serialize(self):return {"schema_version":1,"rows":[r.payload() for r in self.wt_rows]}
    def load(self,payload):
        self.clear_wt_rows(mark_dirty=False); rows=payload.get("rows") if isinstance(payload,dict) else []
        if isinstance(rows,list):
            for raw in rows:
                if isinstance(raw,dict):self.add_wt_row(raw,mark_dirty=False)
        if not self.wt_rows and getattr(self,"wt_rows_frame",None) is not None:self.add_wt_row(mark_dirty=False)
        self.update_wt_status()
    def copy(self):
        lines=["Pozice\tKs\tŘada\th [mm]\tB [mm]\tBeton\tMEd−\tVEd,v+\tVEd,h±\tNávrh HIT-WT\tVyužití\tMRd\tVRd,v\tVRd,h"]
        for r in self.wt_rows:
            c=r.selected_candidate; lines.append("\t".join([r.name.get(),r.quantity.get(),r.series.get(),r.wall_height.get(),r.width.get(),r.concrete.get(),r.med_neg.get(),r.ved_vertical.get(),r.ved_horizontal.get(),c.designation if c else "—",f"{c.utilization*100:.1f} %" if c else "—",f"{c.mrd:.1f}" if c else "—",f"{c.vrd_vertical:.1f}" if c else "—",f"{c.vrd_horizontal:.1f}" if c else "—"]))
        self.clipboard_clear();self.clipboard_append("\n".join(lines));self.set_status(f"WT: zkopírováno {len(self.wt_rows)} řádků.")
    def export(self):
        if not self.wt_rows:messagebox.showinfo("WT","Není co exportovat.",parent=self);return
        rows=[]
        for r in self.wt_rows:
            c=r.selected_candidate; rows.append([r.name.get(),_qty(r.quantity.get()),r.series.get(),r.wall_height.get(),r.width.get(),r.concrete.get(),r.med_neg.get(),r.ved_vertical.get(),r.ved_horizontal.get(),c.designation if c else "—",round(c.utilization*100,1) if c else "",c.mrd if c else "",c.vrd_vertical if c else "",c.vrd_horizontal if c else "",c.joint_spacing_m if c else "",f"HIT20.2 p.{c.page}" if c else ""])
        name=getattr(getattr(self,"project",None),"name","AKCE") or "AKCE"; safe=re.sub(r'[<>:"/\\|?*]+',"_",str(name)).strip(" ._") or "AKCE"
        path=filedialog.asksaveasfilename(parent=self,title="Export HIT-WT do Excelu",initialfile=safe+"_HIT_WT.xlsx",defaultextension=".xlsx",filetypes=[("Excel sešit","*.xlsx"),("Všechny soubory","*.*")])
        if not path:return
        try:saved=write_xlsx(path,headers=["Pozice","Ks","Řada","h stěny [mm]","B [mm]","Beton","MEd− [kNm/prvek]","VEd,v+ [kN/prvek]","VEd,h± [kN/prvek]","Návrh HIT-WT","Využití [%]","MRd [kNm/prvek]","VRd,v [kN/prvek]","VRd,h [kN/prvek]","s_joint max. [m]","Zdroj"],rows=rows,sheet_name="HIT-WT",creator="TURTO – Vytvořil Ing. Jaroslav Kučera")
        except Exception as exc:messagebox.showerror("Export HIT-WT",str(exc),parent=self);return
        try:
            if os.name=="nt":os.startfile(str(Path(saved).resolve()))
        except Exception:pass
        self.set_status(f"WT exportován do {Path(saved).name}.")
    base.HitWorkspaceMixin._init_hit_workspace=init; base.HitWorkspaceMixin._build_wt_tab=build_wt; base.HitWorkspaceMixin._on_wt_mousewheel=wheel
    base.HitWorkspaceMixin.add_wt_row=add; base.HitWorkspaceMixin.remove_wt_row=remove; base.HitWorkspaceMixin.clear_wt_rows=clear; base.HitWorkspaceMixin.recalculate_wt_all=recalc; base.HitWorkspaceMixin.update_wt_status=status; base.HitWorkspaceMixin.serialize_wt_design=serialize; base.HitWorkspaceMixin.load_wt_design=load; base.HitWorkspaceMixin.copy_wt_table=copy; base.HitWorkspaceMixin.export_wt_excel=export
