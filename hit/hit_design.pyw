from __future__ import annotations
import base64, gzip, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, urllib.request
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "TURTO – Návrh nosníků HIT"
APP_VERSION = "0.1.0"
CREATOR = "Vytvořil Ing. Jaroslav Kučera"
REPO_RAW = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main"
MANIFEST_URL = REPO_RAW + "/hit/update_manifest.json"
DATA_FILENAME = "hit_mvx_2023.json.gz.b64"
CONCRETES = ("C20/25","C25/30","C30/37")
COVERS = (30,35,50)

def root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def fmt(v: float, d: int=1) -> str:
    return f"{v:.{d}f}".replace(".", ",")

def version_tuple(v: str):
    return tuple(int(''.join(c for c in p if c.isdigit()) or 0) for p in str(v).split("."))

@dataclass(frozen=True)
class Candidate:
    series: str
    code: str
    length_mm: int
    suffix: str
    h_table: int
    concrete: str
    m1: float
    v1: float
    m2: float
    v2: float
    page: int
    cover: int
    height: int
    utilization: float
    mode: str

    @property
    def designation(self) -> str:
        tail = f"-{self.suffix}" if self.suffix else ""
        return f"HIT-{self.series} MVX-{self.code}-{self.height}-{self.length_mm:03d}-{self.cover}{tail}"

def _group_lines(words, tol: float=1.5):
    groups=[]
    for w in sorted(words,key=lambda z:(z["top"],z["x0"])):
        hit=None
        for g in groups[-3:]:
            if abs(g["top"]-w["top"]) <= tol:
                hit=g; break
        if hit is None:
            hit={"top":w["top"],"words":[]}; groups.append(hit)
        hit["words"].append(w)
    for g in groups:
        g["text"]=" ".join(x["text"] for x in sorted(g["words"],key=lambda z:z["x0"]))
    return groups

def _parse_side(page, x0: float, x1: float):
    words=[w for w in page.extract_words(x_tolerance=1,y_tolerance=2) if x0 <= w["x0"] < x1]
    lines=_group_lines(words)
    concrete_lines=[i for i,g in enumerate(lines) if g["text"].startswith("C20/25")]
    sections=[]
    for ci in concrete_lines:
        ctop=lines[ci]["top"]
        heads=[]
        for j in range(ci-1,-1,-1):
            if ctop-lines[j]["top"]>35: break
            if "HIT-" in lines[j]["text"]:
                heads.extend(re.findall(r"HIT-(?:HP|SP) MVX-[^\s]+",lines[j]["text"]))
        heads=heads[::-1]
        if not heads:
            continue
        end=page.height-40
        for g in lines[ci+1:]:
            if "HIT-" in g["text"] and g["top"]>ctop+20:
                end=g["top"]-2; break
        rows=[]
        for g in lines[ci+1:]:
            if g["top"]>=end: break
            toks=g["text"].split()
            if not toks or not toks[0].isdigit(): continue
            try:
                h=int(toks[0])
                vals=[float(t.replace(",",".")) for t in toks[1:13]]
            except Exception:
                continue
            if 100 <= h <= 500 and len(vals)==12:
                rows.append([h,*vals])
        if rows:
            sections.append([heads,rows])
    return sections

def build_database_from_pdf(pdf_path: Path, out_path: Path):
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("Chybí knihovna pdfplumber. Nainstalujte ji příkazem: py -m pip install pdfplumber") from exc
    sections=[]
    with pdfplumber.open(str(pdf_path)) as pdf:
        if len(pdf.pages) < 54:
            raise RuntimeError("Vybraný dokument nemá očekávaný rozsah DoP HIT-HP/SP-07-23.")
        for pi in range(3,54):
            page=pdf.pages[pi]
            for x0,x1 in ((35,page.width/2),(page.width/2,page.width-25)):
                for heads,rows in _parse_side(page,x0,x1):
                    sections.append([heads,rows,pi+1])
    if len(sections) < 190:
        raise RuntimeError(f"Z DoP se podařilo načíst jen {len(sections)} tabulek; očekáváno přibližně 200.")
    payload={
        "schema_version":1,
        "catalog_id":"leviat_hit_hp_sp_07_23",
        "source_document":"CONF-DOP_HIT-HP/SP-07-23",
        "source_sha256":hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "covers_mm":[30,35,50],
        "concretes":["C20/25","C25/30","C30/37"],
        "ratio_min_m":0.15,
        "sections":sections,
    }
    raw=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    out_path.write_text(base64.b64encode(gzip.compress(raw,9)).decode("ascii"),encoding="ascii")
    return payload

class HitDatabase:
    def __init__(self, path: Path):
        text=path.read_text(encoding="ascii").strip()
        raw=gzip.decompress(base64.b64decode(text))
        self.data=json.loads(raw.decode("utf-8"))
        self.records=[]
        concretes=self.data.get("concretes",list(CONCRETES))
        for heads,rows,page in self.data["sections"]:
            for head in heads:
                m=re.match(r"HIT-(HP|SP) MVX-(\d{4})-hh-(100|050|025)-cc(?:-(OD|OU|WD|WU))?$",head)
                if not m: continue
                series,code,length,suffix=m.groups()
                for row in rows:
                    h=int(row[0]); vals=row[1:]
                    for ci,conc in enumerate(concretes):
                        m1,v1,m2,v2=vals[ci*4:(ci+1)*4]
                        self.records.append([series,code,int(length),suffix or "",h,conc,m1,v1,m2,v2,page])

    def candidates(self, series: str, height: int, cover: int, concrete: str, med: float, ved: float,
                   lengths: set[int], include_offsets: bool=False):
        htab=height-cover
        if htab < 0:
            return [], f"Výška h − krytí = {htab} mm není platná."
        q = math.inf if abs(ved) < 1e-12 else abs(med)/abs(ved)
        if abs(ved)>1e-12 and q < float(self.data.get("ratio_min_m",0.15))-1e-12:
            return [], f"Poměr |MEd| / |VEd| = {fmt(q,3)} m je menší než požadovaných 0,150 m."
        out=[]
        for r in self.records:
            s,code,L,suffix,h,conc,m1,v1,m2,v2,page=r
            if s != series or int(h)!=htab or conc!=concrete or int(L) not in lengths:
                continue
            if suffix and not include_offsets:
                continue
            u,mode = utilization(abs(med),abs(ved),abs(float(m1)),abs(float(v1)),abs(float(m2)),abs(float(v2)))
            if u <= 1.0 + 1e-9:
                out.append(Candidate(s,code,int(L),suffix,int(h),conc,float(m1),float(v1),float(m2),float(v2),
                                     int(page),cover,height,u,mode))
        out.sort(key=lambda x:(x.utilization, x.length_mm, x.code), reverse=True)
        return out, ""

def utilization(M: float, V: float, M1: float, V1: float, M2: float, V2: float):
    if M < 1e-12 and V < 1e-12:
        return 0.0, "nulové zatížení"
    lambdas=[]
    if V > 1e-12:
        lam=V1/V
        if lam*M <= M1 + 1e-9:
            lambdas.append((lam,"V1"))
    if M > 1e-12:
        lam=M2/M
        if lam*V <= V2 + 1e-9:
            lambdas.append((lam,"M2"))
    dx=M2-M1; dy=V2-V1
    den=M*dy - V*dx
    if abs(den)>1e-12:
        lam=(M1*dy - V1*dx)/den
        if lam>=0:
            if abs(dx)>=abs(dy):
                t=(lam*M-M1)/dx if abs(dx)>1e-12 else 0
            else:
                t=(lam*V-V1)/dy if abs(dy)>1e-12 else 0
            if -1e-9 <= t <= 1+1e-9:
                lambdas.append((lam,"interpolace M–V"))
    valid=[x for x in lambdas if x[0]>=0]
    if not valid:
        return math.inf, "mimo obálku"
    lam=max(valid, key=lambda x:x[0])
    if lam[0] <= 1e-12:
        return math.inf, lam[1]
    return 1.0/lam[0], lam[1]

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1250x780"); self.minsize(1050,650)
        self.option_add("*Font", ("Calibri",10))
        self.data_path=root_dir()/DATA_FILENAME
        if not self.data_path.exists():
            self.withdraw()
            pdf=filedialog.askopenfilename(title="Vyberte CONF-DOP HIT-HP/SP-07-23",filetypes=[("PDF","*.pdf")])
            if not pdf:
                messagebox.showerror("TURTO HIT","Pro první spuštění je nutné vybrat zdrojové DoP.")
                self.destroy(); return
            try:
                build_database_from_pdf(Path(pdf),self.data_path)
            except Exception as exc:
                messagebox.showerror("TURTO HIT",f"Databázi se nepodařilo vytvořit:\n{exc}")
                self.destroy(); return
            self.deiconify()
        self.db=HitDatabase(self.data_path)
        self.series=tk.StringVar(value="HP")
        self.height=tk.StringVar(value="200")
        self.cover=tk.StringVar(value="35")
        self.concrete=tk.StringVar(value="C25/30")
        self.med=tk.StringVar(value="-40")
        self.ved=tk.StringVar(value="30")
        self.l100=tk.BooleanVar(value=True); self.l050=tk.BooleanVar(value=True); self.l025=tk.BooleanVar(value=False)
        self.offsets=tk.BooleanVar(value=False)
        self.status=tk.StringVar(value="Zadejte návrhové účinky a spusťte návrh.")
        self._build()

    def _build(self):
        style=ttk.Style(self); style.theme_use("clam")
        style.configure("Title.TLabel",font=("Calibri",18,"bold"))
        style.configure("Sub.TLabel",font=("Calibri",10))
        style.configure("Good.TLabel",font=("Calibri",11,"bold"))
        outer=ttk.Frame(self,padding=18); outer.pack(fill="both",expand=True)
        hdr=ttk.Frame(outer); hdr.pack(fill="x")
        ttk.Label(hdr,text="TURTO | Návrh nosníků Leviat HIT",style="Title.TLabel").pack(side="left")
        ttk.Button(hdr,text="Aktualizace",command=self.check_updates).pack(side="right")
        ttk.Button(hdr,text="Obnovit data z DoP",command=self.rebuild_data).pack(side="right",padx=(0,8))
        ttk.Label(outer,text="Automatický výběr HIT-HP/SP MVX podle MEd a VEd • " + CREATOR,style="Sub.TLabel").pack(anchor="w",pady=(2,14))
        top=ttk.LabelFrame(outer,text="Vstupní údaje",padding=14); top.pack(fill="x")
        fields=[("Řada",self.series,("HP","SP")),("Výška desky h [mm]",self.height,None),("Krytí cnom [mm]",self.cover,tuple(map(str,COVERS))),
                ("Beton",self.concrete,CONCRETES),("MEd [kNm/m]",self.med,None),("VEd [kN/m]",self.ved,None)]
        for i,(lab,var,vals) in enumerate(fields):
            c=i%3; r=(i//3)*2
            ttk.Label(top,text=lab).grid(row=r,column=c,sticky="w",padx=(0,18),pady=(0,3))
            if vals:
                w=ttk.Combobox(top,textvariable=var,values=vals,state="readonly",width=20)
            else:
                w=ttk.Entry(top,textvariable=var,width=22)
            w.grid(row=r+1,column=c,sticky="ew",padx=(0,18),pady=(0,10))
            top.columnconfigure(c,weight=1)
        opt=ttk.Frame(top); opt.grid(row=4,column=0,columnspan=3,sticky="ew")
        ttk.Label(opt,text="Délky prvku:").pack(side="left")
        ttk.Checkbutton(opt,text="1000 mm",variable=self.l100).pack(side="left",padx=(8,0))
        ttk.Checkbutton(opt,text="500 mm",variable=self.l050).pack(side="left",padx=(8,0))
        ttk.Checkbutton(opt,text="250 mm",variable=self.l025).pack(side="left",padx=(8,0))
        ttk.Checkbutton(opt,text="zahrnout OD/OU/WD/WU",variable=self.offsets).pack(side="left",padx=(20,0))
        ttk.Button(opt,text="NAVRHNOUT",command=self.design).pack(side="right")
        info=ttk.Frame(outer); info.pack(fill="x",pady=(12,8))
        ttk.Label(info,textvariable=self.status,style="Good.TLabel").pack(anchor="w")
        cols=("designation","util","m1","v1","m2","v2","page","mode")
        self.tree=ttk.Treeview(outer,columns=cols,show="headings",height=16)
        heads={"designation":"Navržený výrobek","util":"Využití","m1":"MRd,1","v1":"VRd,1","m2":"MRd,2","v2":"VRd,2","page":"DoP str.","mode":"Rozhodující větev"}
        widths={"designation":300,"util":90,"m1":90,"v1":85,"m2":90,"v2":85,"page":70,"mode":135}
        for c in cols:
            self.tree.heading(c,text=heads[c]); self.tree.column(c,width=widths[c],anchor="center" if c!="designation" else "w")
        self.tree.pack(fill="both",expand=True)
        self.tree.bind("<Double-1>",self.copy_selected)
        foot=ttk.Label(outer,text="Výpočet používá zjednodušenou lineární interakční obálku mezi body (MRd,1; VRd,1) a (MRd,2; VRd,2) z DoP. Platí podmínka |MEd|/|VEd| ≥ 0,15 m. Před finálním použitím ověřte zdrojový dokument a geometrii konstrukce.",wraplength=1150,justify="left")
        foot.pack(fill="x",pady=(10,0))

    def design(self):
        try:
            h=int(float(self.height.get().replace(",","."))); c=int(self.cover.get())
            m=float(self.med.get().replace(",",".")); v=float(self.ved.get().replace(",","."))
        except ValueError:
            messagebox.showerror("Vstup","Výška, krytí, MEd a VEd musí být číselné."); return
        lengths={L for L,var in ((100,self.l100),(50,self.l050),(25,self.l025)) if var.get()}
        if not lengths:
            messagebox.showwarning("Vstup","Vyberte alespoň jednu délku prvku."); return
        res,err=self.db.candidates(self.series.get(),h,c,self.concrete.get(),m,v,lengths,self.offsets.get())
        self.tree.delete(*self.tree.get_children())
        if err:
            self.status.set("NELZE POSOUDIT: "+err); return
        if not res:
            self.status.set(f"Nenalezen vyhovující prvek pro h−cnom = {h-c} mm."); return
        self.status.set(f"Nalezeno {len(res)} vyhovujících variant. První řádek je nejlépe využitá varianta.")
        for i,x in enumerate(res[:100]):
            vals=(x.designation,fmt(x.utilization*100)+" %",fmt(x.m1),fmt(x.v1),fmt(x.m2),fmt(x.v2),x.page,x.mode)
            self.tree.insert("","end",values=vals)
        ch=self.tree.get_children()
        if ch: self.tree.selection_set(ch[0]); self.tree.focus(ch[0])

    def copy_selected(self,_event=None):
        sel=self.tree.selection()
        if not sel:return
        vals=self.tree.item(sel[0],"values")
        self.clipboard_clear(); self.clipboard_append("\t".join(map(str,vals)))

    def rebuild_data(self):
        pdf=filedialog.askopenfilename(title="Vyberte CONF-DOP HIT-HP/SP-07-23",filetypes=[("PDF","*.pdf")])
        if not pdf: return
        try:
            build_database_from_pdf(Path(pdf),self.data_path)
            self.db=HitDatabase(self.data_path)
            self.status.set("Databáze HIT byla znovu vytvořena ze zvoleného DoP.")
            messagebox.showinfo("TURTO HIT","Databáze byla úspěšně obnovena.")
        except Exception as exc:
            messagebox.showerror("TURTO HIT",f"Databázi se nepodařilo vytvořit:\n{exc}")

    def check_updates(self):
        try:
            req=urllib.request.Request(MANIFEST_URL,headers={"User-Agent":"TURTO-HIT-Updater"})
            with urllib.request.urlopen(req,timeout=20) as f: manifest=json.loads(f.read().decode("utf-8"))
            latest=str(manifest.get("version","0"))
            if version_tuple(latest)<=version_tuple(APP_VERSION):
                messagebox.showinfo("Aktualizace",f"Používáte aktuální HIT verzi {APP_VERSION}."); return
            if not messagebox.askyesno("Aktualizace",f"Je dostupná HIT verze {latest}.\n\n{manifest.get('notes','')}\n\nNainstalovat?"): return
            temp=Path(tempfile.mkdtemp(prefix="turto_hit_"))
            files=manifest.get("files",[])
            for item in files:
                req=urllib.request.Request(item["url"],headers={"User-Agent":"TURTO-HIT-Updater"})
                with urllib.request.urlopen(req,timeout=30) as f: b=f.read()
                if hashlib.sha256(b).hexdigest().lower()!=item["sha256"].lower(): raise RuntimeError("Nesouhlasí SHA-256: "+item["path"])
                p=temp/item["path"]; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
            script=temp/"apply.py"
            paths=[x["path"] for x in files]
            script.write_text("import os,shutil,sys,time\nfrom pathlib import Path\ntime.sleep(1.2)\ns=Path(__file__).parent; d=Path(sys.argv[1])\n"
                              +f"paths={paths!r}\n"
                              +"[( (d/p).parent.mkdir(parents=True,exist_ok=True), shutil.copy2(s/p,d/p)) for p in paths]\n"
                              +"try: os.startfile(str(d/'hit_design.pyw'))\nexcept Exception: pass\n",encoding="utf-8")
            subprocess.Popen([sys.executable,str(script),str(root_dir())],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            self.after(200,self.destroy)
        except Exception as exc:
            messagebox.showerror("Aktualizace",f"Aktualizaci se nepodařilo provést:\n{exc}")

if __name__=="__main__":
    App().mainloop()
