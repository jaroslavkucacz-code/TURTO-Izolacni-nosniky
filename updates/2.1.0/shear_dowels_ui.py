from __future__ import annotations

from copy import deepcopy
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

from shear_dowels_catalog import catalog_summary, decode_dowel, design_ancon, propose_substitution

CONCRETES=("C25/30","C30/37","C35/45","C40/50")
MOVEMENTS=("Podélný posun","Podélný + příčný posun")
APPLICATIONS=("Nová konstrukce","Stávající betonová stěna")
LOW_SLEEVES=("Nerezová objímka","Plastová objímka")
TARGETS=("Ancon","Schöck")
COVERS=("20","30")


def _movement_code(text:str)->str:return "transverse" if "příčný" in str(text).lower() else "axial"
def _application_code(text:str)->str:return "existing_wall" if "stávající" in str(text).lower() else "new"
def _sleeve_code(text:str)->str:return "plastic" if "plast" in str(text).lower() else "stainless"
def _qty(value:Any)->int:
    q=int(str(value or "1").strip())
    if not 1<=q<=1_000_000:raise ValueError("Ks musí být celé číslo 1–1 000 000.")
    return q
def _f(value:Any)->float:return float(str(value or "").strip().replace("−","-").replace(",","."))
def _fmt(v:Any,d=1)->str:
    try:return f"{float(v):.{d}f}".replace(".",",")
    except Exception:return "—"
def _mark(owner:Any)->None:
    if not getattr(owner,"_action_loading",False) and hasattr(owner,"mark_project_dirty"):owner.mark_project_dirty()


def init_shear_workspace(owner:Any)->None:
    if hasattr(owner,"shear_decoder_rows"):return
    owner.shear_decoder_rows=[];owner.shear_design_rows=[];owner.shear_substitution_rows=[]


def _tree(parent,columns,headings,widths,anchors=None):
    frame=ttk.Frame(parent,style="Card.TFrame",padding=(8,8,8,6));frame.grid(row=1,column=0,sticky="nsew")
    frame.columnconfigure(0,weight=1);frame.rowconfigure(0,weight=1)
    tree=ttk.Treeview(frame,columns=columns,show="headings",selectmode="browse",style="Data.Treeview")
    y=ttk.Scrollbar(frame,orient="vertical",command=tree.yview);x=ttk.Scrollbar(frame,orient="horizontal",command=tree.xview)
    tree.configure(yscrollcommand=y.set,xscrollcommand=x.set);tree.grid(row=0,column=0,sticky="nsew");y.grid(row=0,column=1,sticky="ns");x.grid(row=1,column=0,sticky="ew")
    anchors=anchors or {}
    for c,h,w in zip(columns,headings,widths):
        a=anchors.get(c,"center");tree.heading(c,text=h,anchor=a);tree.column(c,width=w,anchor=a,stretch=c in {"designation","source","target","note"})
    return tree


def _section(parent,title,subtitle):
    parent.columnconfigure(0,weight=1);parent.rowconfigure(1,weight=1)
    top=ttk.Frame(parent,style="Card.TFrame",padding=(14,10));top.grid(row=0,column=0,sticky="ew",pady=(0,8))
    ttk.Label(top,text=title,style="DialogTitle.TLabel").grid(row=0,column=0,sticky="w")
    ttk.Label(top,text=subtitle,style="MutedCard.TLabel",wraplength=1450,justify="left").grid(row=1,column=0,sticky="w",pady=(3,0));return top


def build_decoder(owner,parent):
    top=_section(parent,"Dekodér smykových trnů","Rozpozná Ancon i Schöck Stacon. Geometrie se ukládá spolu s řádkem, aby šla později použít pro katalogovou záměnu.")
    form=ttk.Frame(top,style="Card.TFrame");form.grid(row=2,column=0,sticky="ew",pady=(10,0))
    v={"name":tk.StringVar(owner,"S001"),"qty":tk.StringVar(owner,"1"),"designation":tk.StringVar(owner,""),"slab":tk.StringVar(owner,"200"),"gap":tk.StringVar(owner,"20"),"concrete":tk.StringVar(owner,"C25/30"),"cover":tk.StringVar(owner,"30")};owner.shear_decoder_vars=v
    c=0
    for lab,key,w in (("Pozice","name",8),("Ks","qty",5),("Označení","designation",34),("h [mm]","slab",8),("Spára [mm]","gap",9)):
        ttk.Label(form,text=lab,style="Card.TLabel").grid(row=0,column=c,sticky="w",padx=(0,4));c+=1;ttk.Entry(form,textvariable=v[key],width=w).grid(row=0,column=c,sticky="w",padx=(0,10));c+=1
    ttk.Label(form,text="Beton",style="Card.TLabel").grid(row=0,column=c);c+=1;ttk.Combobox(form,textvariable=v["concrete"],values=CONCRETES,state="readonly",width=9).grid(row=0,column=c,padx=(4,10));c+=1
    ttk.Label(form,text="cnom Schöck",style="Card.TLabel").grid(row=0,column=c);c+=1;ttk.Combobox(form,textvariable=v["cover"],values=COVERS,state="readonly",width=5).grid(row=0,column=c,padx=(4,10));c+=1
    ttk.Button(form,text="Dekódovat a přidat",style="Accent.TButton",command=owner.add_shear_decoder_row).grid(row=0,column=c)
    cols=("name","qty","manufacturer","family","size","movement","designation","slab","gap","concrete")
    owner.shear_decoder_tree=_tree(parent,cols,("Pozice","Ks","Výrobce","Typ","Velikost","Pohyb","Označení","h [mm]","Spára [mm]","Beton"),(80,50,90,90,70,150,300,80,90,90),{"name":"w","designation":"w"})
    owner.shear_decoder_tree.bind("<Double-1>",lambda e:owner.shear_decoder_to_substitution())


def build_design(owner,parent):
    top=_section(parent,"Návrh smykových trnů","Návrh Ancon podle tabulované VRd; bez interpolace. Q varianta se volí při požadavku na příčný posun.")
    form=ttk.Frame(top,style="Card.TFrame");form.grid(row=2,column=0,sticky="ew",pady=(10,0))
    v={"name":tk.StringVar(owner,"N001"),"qty":tk.StringVar(owner,"1"),"ved":tk.StringVar(owner,""),"slab":tk.StringVar(owner,"200"),"gap":tk.StringVar(owner,"20"),"concrete":tk.StringVar(owner,"C25/30"),"movement":tk.StringVar(owner,MOVEMENTS[0]),"application":tk.StringVar(owner,APPLICATIONS[0]),"sleeve":tk.StringVar(owner,LOW_SLEEVES[0])};owner.shear_design_vars=v
    ttk.Label(form,text="Výrobce návrhu:",style="Card.TLabel",font=("Calibri",10,"bold")).grid(row=0,column=0,sticky="w");ttk.Label(form,text="Ancon / Leviat",style="MutedCard.TLabel").grid(row=0,column=1,sticky="w",padx=(5,16));c=2
    for lab,key,w in (("Pozice","name",8),("Ks","qty",5),("VEd [kN/trn]","ved",10),("h [mm]","slab",8),("Spára [mm]","gap",9)):
        ttk.Label(form,text=lab,style="Card.TLabel").grid(row=0,column=c);c+=1;ttk.Entry(form,textvariable=v[key],width=w).grid(row=0,column=c,padx=(4,9));c+=1
    ttk.Label(form,text="Beton",style="Card.TLabel").grid(row=0,column=c);c+=1;ttk.Combobox(form,textvariable=v["concrete"],values=CONCRETES,state="readonly",width=9).grid(row=0,column=c,padx=(4,9));c+=1
    ttk.Combobox(form,textvariable=v["movement"],values=MOVEMENTS,state="readonly",width=21).grid(row=0,column=c,padx=(4,9));c+=1;ttk.Combobox(form,textvariable=v["application"],values=APPLICATIONS,state="readonly",width=23).grid(row=0,column=c,padx=(4,9));c+=1;ttk.Combobox(form,textvariable=v["sleeve"],values=LOW_SLEEVES,state="readonly",width=18).grid(row=0,column=c,padx=(4,9));c+=1
    ttk.Button(form,text="Navrhnout a přidat",style="Accent.TButton",command=owner.add_shear_design_row).grid(row=0,column=c)
    cols=("name","qty","designation","vrd","util","slab","gap","concrete","movement","source","note")
    owner.shear_design_tree=_tree(parent,cols,("Pozice","Ks","Navržený Ancon","VRd [kN]","Využití","h [mm]","Spára [mm]","Beton","Pohyb","Zdroj","Poznámka"),(80,50,310,85,80,80,90,90,140,110,430),{"name":"w","designation":"w","note":"w"})


def build_substitution(owner,parent):
    top=_section(parent,"Záměny smykových trnů","Požadavek záměny je katalogová VRd původního trnu při stejné geometrii, ne pouze aktuální VEd. Cílem může být Ancon nebo Schöck Stacon.")
    form=ttk.Frame(top,style="Card.TFrame");form.grid(row=2,column=0,sticky="ew",pady=(10,0))
    v={"name":tk.StringVar(owner,"Z001"),"qty":tk.StringVar(owner,"1"),"source":tk.StringVar(owner,""),"slab":tk.StringVar(owner,"200"),"gap":tk.StringVar(owner,"20"),"concrete":tk.StringVar(owner,"C25/30"),"cover":tk.StringVar(owner,"30"),"target":tk.StringVar(owner,"Schöck"),"sleeve":tk.StringVar(owner,LOW_SLEEVES[0])};owner.shear_substitution_vars=v;c=0
    for lab,key,w in (("Pozice","name",8),("Ks","qty",5),("Původní trn","source",26),("h [mm]","slab",8),("Spára [mm]","gap",9)):
        ttk.Label(form,text=lab,style="Card.TLabel").grid(row=0,column=c);c+=1;ttk.Entry(form,textvariable=v[key],width=w).grid(row=0,column=c,padx=(4,9));c+=1
    ttk.Label(form,text="Beton",style="Card.TLabel").grid(row=0,column=c);c+=1;ttk.Combobox(form,textvariable=v["concrete"],values=CONCRETES,state="readonly",width=9).grid(row=0,column=c,padx=(4,9));c+=1;ttk.Label(form,text="cnom Schöck",style="Card.TLabel").grid(row=0,column=c);c+=1;ttk.Combobox(form,textvariable=v["cover"],values=COVERS,state="readonly",width=5).grid(row=0,column=c,padx=(4,9));c+=1;ttk.Label(form,text="Cíl",style="Card.TLabel").grid(row=0,column=c);c+=1;ttk.Combobox(form,textvariable=v["target"],values=TARGETS,state="readonly",width=10).grid(row=0,column=c,padx=(4,9));c+=1;ttk.Button(form,text="Překlopit",style="Accent.TButton",command=owner.add_shear_substitution_row).grid(row=0,column=c)
    cols=("name","qty","source","source_vrd","target","target_vrd","util","slab","gap","movement","status","note")
    owner.shear_substitution_tree=_tree(parent,cols,("Pozice","Ks","Původní trn","VRd pův. [kN]","Navržený ekvivalent","VRd cíle [kN]","Poměr","h [mm]","Spára [mm]","Pohyb","Výsledek","Poznámka"),(80,50,260,105,300,105,80,80,90,140,130,430),{"name":"w","source":"w","target":"w","note":"w"})


def build_shear_workspace(owner,parent):
    init_shear_workspace(owner);parent.columnconfigure(0,weight=1);parent.rowconfigure(1,weight=1)
    head=ttk.Frame(parent,style="Card.TFrame",padding=(14,10));head.grid(row=0,column=0,sticky="ew",pady=(0,8));ttk.Label(head,text="Smykové trny",style="ProjectTitle.TLabel").grid(row=0,column=0,sticky="w");ttk.Label(head,text=catalog_summary(),style="MutedCard.TLabel").grid(row=1,column=0,sticky="w",pady=(3,0))
    nb=ttk.Notebook(parent,style="Workspace.TNotebook");nb.grid(row=1,column=0,sticky="nsew");owner.shear_notebook=nb
    d=ttk.Frame(nb,style="App.TFrame",padding=(8,10,8,8));n=ttk.Frame(nb,style="App.TFrame",padding=(8,10,8,8));s=ttk.Frame(nb,style="App.TFrame",padding=(8,10,8,8));nb.add(d,text="Dekodér");nb.add(n,text="Návrh");nb.add(s,text="Záměny");build_decoder(owner,d);build_design(owner,n);build_substitution(owner,s);owner.refresh_shear_tables()


def _next(prefix,rows):return f"{prefix}{len(rows)+1:03d}"

def add_decoder(self):
    init_shear_workspace(self);v=self.shear_decoder_vars
    try:
        info=decode_dowel(v["designation"].get())
        if not info:raise ValueError("Označení smykového trnu nebylo rozpoznáno.")
        row={"name":v["name"].get().strip() or _next("S",self.shear_decoder_rows),"quantity":_qty(v["qty"].get()),"designation":v["designation"].get().strip(),"manufacturer":info["manufacturer"],"family":info["family"],"size":info["size"],"movement":info["movement"],"slab_mm":_f(v["slab"].get()),"gap_mm":_f(v["gap"].get()),"concrete":v["concrete"].get(),"cover_mm":int(v["cover"].get())};self.shear_decoder_rows.append(row);_mark(self);self.refresh_shear_tables();v["name"].set(_next("S",self.shear_decoder_rows))
    except Exception as exc:messagebox.showerror("Dekodér smykových trnů",str(exc),parent=self)

def add_design(self):
    init_shear_workspace(self);v=self.shear_design_vars
    try:
        candidates,error=design_ancon(ved=_f(v["ved"].get()),slab_mm=_f(v["slab"].get()),gap_mm=_f(v["gap"].get()),concrete=v["concrete"].get(),movement=_movement_code(v["movement"].get()),application=_application_code(v["application"].get()),low_sleeve=_sleeve_code(v["sleeve"].get()))
        if not candidates:raise ValueError(error or "Nenalezen vyhovující Ancon.")
        c=candidates[0];row={"name":v["name"].get().strip() or _next("N",self.shear_design_rows),"quantity":_qty(v["qty"].get()),"ved":abs(_f(v["ved"].get())),"slab_mm":_f(v["slab"].get()),"gap_mm":_f(v["gap"].get()),"concrete":v["concrete"].get(),"movement":_movement_code(v["movement"].get()),"application":_application_code(v["application"].get()),"candidate":c.as_dict()};self.shear_design_rows.append(row);_mark(self);self.refresh_shear_tables();v["name"].set(_next("N",self.shear_design_rows))
    except Exception as exc:messagebox.showerror("Návrh smykového trnu",str(exc),parent=self)

def add_substitution(self):
    init_shear_workspace(self);v=self.shear_substitution_vars
    try:
        src,tgt,error=propose_substitution(source_designation=v["source"].get(),target_manufacturer=v["target"].get(),slab_mm=_f(v["slab"].get()),gap_mm=_f(v["gap"].get()),concrete=v["concrete"].get(),cover_mm=int(v["cover"].get()),low_sleeve=_sleeve_code(v["sleeve"].get()))
        if src is None or tgt is None:raise ValueError(error or "Záměnu nelze navrhnout.")
        row={"name":v["name"].get().strip() or _next("Z",self.shear_substitution_rows),"quantity":_qty(v["qty"].get()),"source_designation":v["source"].get().strip(),"source":src.as_dict(),"target":tgt.as_dict(),"slab_mm":_f(v["slab"].get()),"gap_mm":_f(v["gap"].get()),"concrete":v["concrete"].get(),"cover_mm":int(v["cover"].get()),"status":tgt.status};self.shear_substitution_rows.append(row);_mark(self);self.refresh_shear_tables();v["name"].set(_next("Z",self.shear_substitution_rows))
    except Exception as exc:messagebox.showerror("Záměna smykového trnu",str(exc),parent=self)

def decoder_to_substitution(self):
    tree=getattr(self,"shear_decoder_tree",None);sel=tree.selection() if tree else ()
    if not sel:return
    try:
        row=self.shear_decoder_rows[int(sel[0])];v=self.shear_substitution_vars;v["source"].set(row["designation"]);v["slab"].set(str(row["slab_mm"]));v["gap"].set(str(row["gap_mm"]));v["concrete"].set(row["concrete"]);v["cover"].set(str(row.get("cover_mm",30)));self.shear_notebook.select(2)
    except Exception:pass

def _fill(tree,rows,fn):
    for iid in tree.get_children(""):tree.delete(iid)
    for i,row in enumerate(rows):tree.insert("","end",iid=str(i),values=fn(row))

def refresh(self):
    init_shear_workspace(self)
    if hasattr(self,"shear_decoder_tree"):_fill(self.shear_decoder_tree,self.shear_decoder_rows,lambda r:(r["name"],r["quantity"],r["manufacturer"],r["family"],r["size"],"axiální + příčný" if r["movement"]=="transverse" else "axiální",r["designation"],_fmt(r["slab_mm"],0),_fmt(r["gap_mm"],0),r["concrete"]))
    if hasattr(self,"shear_design_tree"):
        _fill(self.shear_design_tree,self.shear_design_rows,lambda r:(r["name"],r["quantity"],r["candidate"]["designation"],_fmt(r["candidate"]["vrd"]),_fmt(r["candidate"]["utilization"]*100)+" %",_fmt(r["slab_mm"],0),_fmt(r["gap_mm"],0),r["concrete"],"axiální + příčný" if r["movement"]=="transverse" else "axiální",f"Ancon p.{r['candidate']['page']}",r["candidate"].get("note","")))
    if hasattr(self,"shear_substitution_tree"):
        _fill(self.shear_substitution_tree,self.shear_substitution_rows,lambda r:(r["name"],r["quantity"],r["source_designation"],_fmt(r["source"]["vrd"]),r["target"]["designation"],_fmt(r["target"]["vrd"]),_fmt(r["target"]["vrd"]/r["source"]["vrd"]*100)+" %",_fmt(r["slab_mm"],0),_fmt(r["gap_mm"],0),"axiální + příčný" if r["source"]["movement"]=="transverse" else "axiální",r["target"].get("status","VYHOVUJE"),r["target"].get("note","")))

def serialize(self):init_shear_workspace(self);return {"schema_version":1,"decoder":deepcopy(self.shear_decoder_rows),"design":deepcopy(self.shear_design_rows),"substitution":deepcopy(self.shear_substitution_rows)}
def load(self,payload):
    init_shear_workspace(self);payload=payload if isinstance(payload,dict) else {};self.shear_decoder_rows=deepcopy(payload.get("decoder",[])) if isinstance(payload.get("decoder"),list) else [];self.shear_design_rows=deepcopy(payload.get("design",[])) if isinstance(payload.get("design"),list) else [];self.shear_substitution_rows=deepcopy(payload.get("substitution",[])) if isinstance(payload.get("substitution"),list) else []
    if hasattr(self,"refresh_shear_tables"):self.refresh_shear_tables()
def clear(self):self.shear_decoder_rows=[];self.shear_design_rows=[];self.shear_substitution_rows=[];self.refresh_shear_tables() if hasattr(self,"refresh_shear_tables") else None

def report_rows(self):
    out=[]
    for r in getattr(self,"shear_design_rows",[]):
        c=r.get("candidate",{})
        if not c:continue
        out.append({"domain_id":"shear_dowels","domain":"Smykové trny","group":"Návrh smykových trnů","name":r.get("name",""),"quantity":r.get("quantity",1),"series":c.get("manufacturer",""),"connection_type":"DOWEL","height_mm":r.get("slab_mm",""),"cover_mm":"","concrete":r.get("concrete",""),"required_length_mm":r.get("gap_mm",""),"custom_actions":[{"label":"VEd","value":r.get("ved",""),"unit":"kN/prvek"}],"candidate":{"designation":c.get("designation",""),"connection_type":"DOWEL","manufacturer":c.get("manufacturer",""),"physical_length_mm":c.get("length_mm") or 0,"height":r.get("slab_mm",0),"concrete":r.get("concrete",""),"utilization":c.get("utilization",0),"m1":0,"v1":c.get("vrd",0),"m2":0,"v2":0,"mode":f"VRd {c.get('vrd',0):.1f} kN • η {c.get('utilization',0)*100:.1f} %","page":c.get("page",""),"source_note":c.get("source","")},"status":c.get("status","VYHOVUJE"),"detail":c.get("note",""),"notes":[c.get("note","")] if c.get("note") else []})
    return out

def install_methods(cls):
    cls.add_shear_decoder_row=add_decoder;cls.add_shear_design_row=add_design;cls.add_shear_substitution_row=add_substitution;cls.shear_decoder_to_substitution=decoder_to_substitution;cls.refresh_shear_tables=refresh;cls.serialize_shear_dowels=serialize;cls.load_shear_dowels=load;cls.clear_shear_dowels=clear;cls.collect_shear_report_rows=report_rows
