"""Clipboard schedule import. Loads remain in kN/m and kNm/m; no capacity logic."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
import unicodedata
import tkinter as tk
from tkinter import messagebox, ttk

LENGTH_CODES = {1000: 100, 500: 50, 333: 33, 250: 25}
DEFAULTS = dict(height="200", cover="35", concrete="C25/30", series="HP",
                bending="MVX", shear="ZVX", moment="MEd− (konzola)")
PARAMS = (
    ("height", "Výška h [mm]", tuple(str(n) for n in range(160, 401, 10))),
    ("cover", "Krytí cnom [mm]", ("30", "35", "50")),
    ("concrete", "Beton", ("C20/25", "C25/30", "C30/37")),
    ("series", "Řada", ("HP", "SP")),
    ("bending", "Ohybové prvky →", ("MVX", "MVXL", "DD", "DVL", "DDL")),
    ("shear", "Smykové prvky →", ("ZVX", "ZDX")),
    ("moment", "MEd bez znaménka →", ("MEd− (konzola)", "MEd+")),
)
# These describe the existing UI's input directions, not product capacities.
DIRECTIONS = {
    "MVX": {"med_neg", "ved_pos", "ved_neg"},
    "MVXL": {"med_neg", "ved_pos", "ved_neg"},
    "DD": {"med_pos", "med_neg", "ved_pos", "ved_neg"},
    "DVL": {"med_pos", "med_neg", "ved_pos"},
    "DDL": {"med_pos", "med_neg", "ved_pos", "ved_neg"},
    "ZVX": {"ved_pos"}, "ZDX": {"ved_pos", "ved_neg"},
}
NUMBER = r"[+-]?\s*(?:\d{1,3}(?:[ ]\d{3})+|\d+)(?:[.,]\d+)?"
FIELD = re.compile(r"(?<![a-z])([mv])\s*_?\s*e\s*_?\s*d\s*([+-]?)\s*[=:]")
LENGTH = re.compile(r"\b(?:delky|delka|l)\s*[=:]?\s*(" + NUMBER + r")\s*(mm|cm|m)\b")


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("−", "-").replace("–", "-")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()


def number(text: str) -> float:
    value = float(text.replace(" ", "").replace(",", "."))
    if not math.isfinite(value) or abs(value) > 1e9:
        raise ValueError("Číslo je mimo podporovaný rozsah.")
    return value


def text_number(value: float) -> str:
    return format(value, ".12g").replace(".", ",")


@dataclass
class ScheduleRecord:
    line: int
    source: str
    kind: str
    med: float | None = None
    ved: float | None = None
    m_sign: str = ""
    v_sign: str = ""
    length_mm: int | None = None
    errors: list[str] = field(default_factory=list)


def parse_schedule(text: str) -> list[ScheduleRecord]:
    if len(text) > 1_000_000:
        raise ValueError("Výkaz je příliš dlouhý; vložte nejvýše 1 MB textu.")
    result = []
    for lineno, original in enumerate(text.splitlines(), 1):
        source = original.strip().strip("|").strip()
        if not source or re.fullmatch(r"[\s|:\-–]+", source):
            continue
        value = normalized(source)
        if re.fullmatch(r"(?:popis|nazev|polozka|oznaceni)(?:\s+(?:prvku|polozky))?", value):
            continue
        matches = list(FIELD.finditer(value))
        kind = "Smykový" if "smykov" in value else "Ohybový" if "ohybov" in value else (
            "Ohybový" if any(m[1] == "m" for m in matches) else "Smykový")
        row = ScheduleRecord(lineno, source, kind)
        if not matches:
            row.errors.append("Nerozpoznané zadání: očekáváno VEd = … kN/m a případně MEd = … kNm/m.")
        if re.search(r"\bn\s*_?e\s*_?d\s*[+-]?\s*[=:]", value):
            row.errors.append("Import NEd není podporován; tento řádek zadejte ručně.")
        seen = set()
        for index, match in enumerate(matches):
            key = match[1]
            label = "MEd" if key == "m" else "VEd"
            if key in seen:
                row.errors.append(f"{label} je uvedeno vícekrát; řádek musí obsahovat jednu hodnotu pro každý účinek.")
                continue
            seen.add(key)
            tail = value[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(value)]
            numeric = re.match(r"\s*(" + NUMBER + r")", tail)
            if not numeric:
                row.errors.append(f"{label}: chybí platné číslo.")
                continue
            try:
                amount = number(numeric[1])
            except ValueError:
                row.errors.append(f"{label}: neplatné číslo.")
                continue
            unit_match = re.match(r"\s*(kn\s*(?:[*.·]\s*)?m?\s*(?:/\s*(?:m|ks|prvek|element))?)(?![a-z0-9/])", tail[numeric.end():])
            unit = re.sub(r"[\s*.·]", "", unit_match[1]) if unit_match else ""
            expected = "knm/m" if key == "m" else "kn/m"
            if unit != expected:
                row.errors.append(f"{label}: očekávány {'kNm/m' if key == 'm' else 'kN/m'}; síly na kus ani chybějící jednotky se nepřevádějí automaticky.")
            raw_sign = numeric[1].strip()[:1]
            explicit = raw_sign if raw_sign in {"+", "-"} else ""
            if match[2] and explicit and match[2] != explicit:
                row.errors.append(f"{label}: rozporná znaménka názvu pole a hodnoty.")
            sign = match[2] or explicit
            if key == "m":
                row.med, row.m_sign = abs(amount), sign
            else:
                row.ved, row.v_sign = abs(amount), sign
        lengths = list(LENGTH.finditer(value))
        if len(lengths) > 1:
            row.errors.append("Délka je uvedena vícekrát; ponechte jednu jednoznačnou délku.")
        if lengths:
            try:
                millimetres = number(lengths[0][1]) * {"m": 1000, "cm": 10, "mm": 1}[lengths[0][2]]
                if not 0 < millimetres <= 100_000 or not math.isclose(millimetres, round(millimetres), abs_tol=1e-6):
                    raise ValueError()
                row.length_mm = round(millimetres)
            except ValueError:
                row.errors.append("Délka musí být kladná a vyjádřitelná v celých mm.")
        elif re.search(r"\b(?:delky|delka)\b|\bl\s*[=:]", value):
            row.errors.append("Délka nebyla rozpoznána; použijte např. délky 0,5 m nebo L = 500 mm.")
        if row.ved is None:
            row.errors.append("Chybí VEd.")
        if kind == "Ohybový" and row.med is None:
            row.errors.append("U ohybového prvku chybí MEd.")
        if kind == "Smykový" and row.med:
            row.errors.append("Smykový prvek obsahuje nenulový MEd; opravte druh prvku.")
        if row.ved is not None and row.ved == 0 and (row.med or 0) == 0:
            row.errors.append("Všechny návrhové účinky jsou nulové.")
        result.append(row)
        if len(result) > 500:
            raise ValueError("Najednou lze vložit nejvýše 500 pozic; výkaz rozdělte na části.")
    return result


def row_defaults(row: ScheduleRecord, options: dict[str, str], name: str) -> dict[str, str]:
    if row.errors:
        raise ValueError(" • ".join(row.errors))
    options = {**DEFAULTS, **options}
    try:
        height = int(options["height"].strip())
        if height <= 0 or height > 1000 or height % 10:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Výška musí být kladné celé číslo v mm po 10 mm (např. 200).") from None
    for key, _label, choices in PARAMS[1:]:
        if options[key] not in choices:
            raise ValueError("Neplatná hodnota: " + _label)
    typ = options["bending"] if row.kind == "Ohybový" else options["shear"]
    result = dict(name=name, height=str(height), cover="30" if typ in {"ZVX", "ZDX"} else options["cover"],
                  concrete=options["concrete"], series=options["series"], connection_type=typ,
                  required_length=str(row.length_mm or ""), import_source_text=row.source,
                  import_source_line=str(row.line), mvx_variant="Bez", mvx_bx="",
                  med_pos="", med_neg="", ved_pos="", ved_neg="", ned_pos="", ned_neg="", load_x="")
    if row.med is not None:
        sign = row.m_sign or ("-" if options["moment"] == "MEd− (konzola)" else "+")
        key = "med_neg" if sign == "-" else "med_pos"
        if row.med and key not in DIRECTIONS[typ]:
            raise ValueError(f"{typ} nepřijímá MEd{sign}; změňte přiřazení typu nebo směr podle skutečného zadání.")
        result[key] = text_number(row.med)
    key = "ved_neg" if row.v_sign == "-" else "ved_pos"
    if row.ved and key not in DIRECTIONS[typ]:
        raise ValueError(f"{typ} nepřijímá VEd−; pro oba směry lze v přiřazení zvolit ZDX.")
    result[key] = text_number(row.ved or 0)
    return result


def required_length_codes(text: str, allowed: set[int]) -> set[int]:
    text = str(text).strip()
    if not text:
        if not allowed:
            raise ValueError("Není povolena žádná délka HIT.")
        return set(allowed)
    try:
        length = int(text)
        if str(length) != text or length <= 0:
            raise ValueError()
    except ValueError:
        raise ValueError("L požadované: zadejte kladné celé mm, nebo nechte pole prázdné.") from None
    if length not in LENGTH_CODES:
        raise ValueError(f"L = {length} mm: v tomto návrháři není shodná katalogová délka HIT. Délku je nutné vyřešit; automatická záměna není provedena.")
    code = LENGTH_CODES[length]
    if code not in allowed:
        raise ValueError(f"Pro tento řádek je nutné nahoře povolit délku {length} mm.")
    return {code}


SAMPLE_PAIRS = ((21,19),(27,27),(28,27),(30,10),(31,29),(32,35),(90,10),(10,8),(11,6),
                (15,14),(23,11),(25,20),(25,21),(30,21),(32,19),(34,30),(36,32),(40,18),
                (40,23),(42,30),(43,32),(45,16),(60,27),(65,35),(100,10),(100,16),(155,18),(155,27))
EXAMPLE = "\n".join([f"Ohybový isonosník · Ved = {v} kN/m, Med = {m} kNm/m" for v,m in SAMPLE_PAIRS] +
                    [f"Smykový isonosník · Ved = {v} kN/m" for v in (30,65,90)] +
                    ["Smykový isonosník délky 0.1m · Ved = 50 kN/m", "Smykový isonosník délky 0.5m · Ved = 70 kN/m"])


def install_rows(owner, defaults: list[dict[str, str]], replace_existing: bool = False) -> list:
    """Construct every row first. On construction failure keep the original assignment."""
    from hit_workspace import HitInputRow
    previous = list(owner.hit_rows)
    created = []
    before_widgets = set(owner.hit_rows_frame.winfo_children())
    try:
        for values in defaults:
            created.append(HitInputRow(owner, len(previous) + len(created) + 1, values))
    except Exception:
        for row in created:
            row.destroy()
        for widget in set(owner.hit_rows_frame.winfo_children()) - before_widgets:
            widget.destroy()
        raise
    blank = (len(previous) == 1 and previous[0].name.get() == "N1" and
             all(not getattr(previous[0], key).get().strip() for key in
                 ("med_pos", "med_neg", "ved_pos", "ved_neg", "ned_pos", "ned_neg", "load_x", "required_length")))
    if replace_existing or blank:
        for row in previous:
            row.destroy()
        previous = []
    owner.hit_rows[:] = previous + created
    for index, row in enumerate(owner.hit_rows, 1):
        row.regrid(index)
    owner._on_hit_rows_configure()
    for row in created:
        try:
            row.recalculate()
        except Exception as exc:
            row._set_error("Výpočet se nezdařil: " + str(exc))
    owner.update_hit_status()
    return created


class HitScheduleDialog(tk.Toplevel):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.title("Hromadné zadání HIT z výkazu")
        self.geometry("1180x800")
        self.minsize(920, 650)
        self.configure(background=owner.colors["bg"])
        self.transient(owner)
        self.records: list[ScheduleRecord] = []
        self.included: set[int] = set()
        self.overrides: dict[int, dict[str,str]] = {}
        self.payloads: dict[int, dict[str,str]] = {}
        self.last_text = ""
        self.ack = tk.BooleanVar(self, False)
        self.replace = tk.BooleanVar(self, False)
        initial = dict(DEFAULTS)
        if owner.hit_rows:
            for key in ("height", "cover", "concrete", "series"):
                initial[key] = getattr(owner.hit_rows[-1], key).get()
        self.options = {k: tk.StringVar(self, v) for k,v in initial.items()}
        outer = ttk.Frame(self, padding=16, style="App.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)
        ttk.Label(outer, text="Výkaz → hromadný návrh HIT", style="DialogTitle.TLabel").grid(row=0,column=0,sticky="w")
        ttk.Label(outer, text="Vložte celý sloupec z Excelu nebo textový výkaz. Pořadí i stejné položky zůstanou zachované.", style="Muted.TLabel").grid(row=1,column=0,sticky="w",pady=(3,8))
        source_frame = ttk.Frame(outer)
        source_frame.grid(row=2,column=0,sticky="ew")
        source_frame.columnconfigure(0,weight=1)
        self.text = tk.Text(source_frame,height=5,wrap="none",undo=True,font=("Calibri",11),
                            background=owner.colors["panel"],foreground=owner.colors["text"],insertbackground=owner.colors["text"])
        self.text.grid(row=0,column=0,sticky="ew")
        scroll=ttk.Scrollbar(source_frame,command=self.text.yview)
        scroll.grid(row=0,column=1,sticky="ns"); self.text.configure(yscrollcommand=scroll.set)
        bar=ttk.Frame(outer);bar.grid(row=3,column=0,sticky="ew",pady=(6,10))
        ttk.Button(bar,text="Vložit ze schránky",command=self.paste).pack(side="left")
        ttk.Button(bar,text="Načíst náhled",command=self.analyze).pack(side="left",padx=6)
        ttk.Button(bar,text="Ukázkový výkaz (33 pozic)",command=self.example).pack(side="left")
        params=ttk.LabelFrame(outer,text="Společné parametry (jednotlivé pozice lze upravit zvlášť)",padding=8)
        params.grid(row=4,column=0,sticky="ew",pady=(0,8))
        self.param_controls=self.build_parameters(params,self.options)
        box=ttk.Frame(outer);box.grid(row=5,column=0,sticky="nsew");box.columnconfigure(0,weight=1);box.rowconfigure(0,weight=1)
        columns=("use","name","kind","m","v","length","height","cover","concrete","series","type","check")
        self.tree=ttk.Treeview(box,columns=columns,show="headings",selectmode="extended",height=10,style="Data.Treeview")
        labels=("✓","Pozice","Druh","MEd [kNm/m]","VEd [kN/m]","L [mm]","h [mm]","cnom","Beton","Řada","Typ HIT","Kontrola")
        widths=(34,64,78,108,100,65,60,55,85,50,65,285)
        for c,label,width in zip(columns,labels,widths):
            self.tree.heading(c,text=label);self.tree.column(c,width=width,minwidth=30,stretch=(c=="check"))
        self.tree.grid(row=0,column=0,sticky="nsew")
        sy=ttk.Scrollbar(box,orient="vertical",command=self.tree.yview);sy.grid(row=0,column=1,sticky="ns")
        sx=ttk.Scrollbar(box,orient="horizontal",command=self.tree.xview);sx.grid(row=1,column=0,sticky="ew")
        self.tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        self.tree.tag_configure("error",foreground=owner.colors.get("danger","#a02020"))
        self.tree.tag_configure("warning",foreground=owner.colors.get("warning_text","#926008"))
        self.tree.bind("<<TreeviewSelect>>",self.show_source)
        actions=ttk.Frame(outer);actions.grid(row=6,column=0,sticky="ew",pady=6)
        ttk.Button(actions,text="Parametry označených…",command=self.edit_selected).pack(side="left")
        ttk.Button(actions,text="Vynechat označené",command=lambda:self.include(False)).pack(side="left",padx=6)
        ttk.Button(actions,text="Zahrnout označené",command=lambda:self.include(True)).pack(side="left")
        self.detail=tk.StringVar(self,"Původní text vybrané pozice se zobrazí zde.")
        ttk.Label(outer,textvariable=self.detail,wraplength=1090,style="Muted.TLabel").grid(row=7,column=0,sticky="ew")
        ttk.Label(outer,text="ZVX/ZDX mají v návrháři pevné cnom 30 mm. Uvedená délka je závazný požadavek, prázdná používá horní volbu délek. Síly zůstávají na metr. Nejde o schválení statického řešení.",wraplength=1090,style="Muted.TLabel").grid(row=8,column=0,sticky="ew",pady=6)
        ttk.Checkbutton(outer,text="Potvrzuji přiřazení typů a směrů MEd/VEd podle skutečného zadání (viz náhled).",variable=self.ack,command=self.render).grid(row=9,column=0,sticky="w")
        ttk.Checkbutton(outer,text="Nahradit dosavadní řádky návrhu (jinak připojit)",variable=self.replace).grid(row=10,column=0,sticky="w")
        bottom=ttk.Frame(outer);bottom.grid(row=11,column=0,sticky="ew",pady=(8,0))
        self.summary=tk.StringVar(self,"Nejprve vložte výkaz a načtěte náhled.")
        ttk.Label(bottom,textvariable=self.summary,style="Muted.TLabel").pack(side="left")
        ttk.Button(bottom,text="Zrušit",command=self.destroy).pack(side="right")
        self.import_button=ttk.Button(bottom,text="Přidat do návrhu HIT",command=self.commit,state="disabled",style="Accent.TButton")
        self.import_button.pack(side="right",padx=8)
        for variable in self.options.values(): variable.trace_add("write",self.options_changed)
        self.bind("<Escape>",lambda event:self.destroy())
        self.update_idletasks()
        from ui_utils import place_dialog_on_parent
        place_dialog_on_parent(self,owner)
        self.grab_set()

    @staticmethod
    def build_parameters(parent,variables):
        controls={}
        for i,(key,label,choices) in enumerate(PARAMS):
            r,c=divmod(i,4)
            ttk.Label(parent,text=label).grid(row=r*2,column=c,sticky="w",padx=5,pady=(3,0))
            control=ttk.Combobox(parent,textvariable=variables[key],values=choices,
                                 state="normal" if key=="height" else "readonly",width=23 if key=="moment" else 15)
            control.grid(row=r*2+1,column=c,sticky="ew",padx=5,pady=(2,5))
            parent.columnconfigure(c,weight=1);controls[key]=control
        return controls

    def paste(self):
        try: value=self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Schránka","Schránka neobsahuje dostupný text.",parent=self);return
        self.text.delete("1.0","end");self.text.insert("1.0",value);self.analyze()

    def example(self):
        self.text.delete("1.0","end");self.text.insert("1.0",EXAMPLE);self.analyze()

    def analyze(self):
        text=self.text.get("1.0","end-1c")
        try: records=parse_schedule(text)
        except ValueError as exc:
            messagebox.showerror("Výkaz",str(exc),parent=self);return
        self.last_text=text;self.records=records
        self.included=set(range(len(records)));self.overrides.clear();self.ack.set(False);self.render()

    def options_changed(self,*_):
        self.ack.set(False);self.render()

    def render(self):
        selected=self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self.payloads={};errors=warnings=0
        common={k:v.get() for k,v in self.options.items()}
        existing={r.name.get() for r in self.owner.hit_rows}
        names=set(existing)
        n=1
        for i,row in enumerate(self.records):
            while f"N{n:03d}" in names:n+=1
            name=f"N{n:03d}";names.add(name);n+=1
            opt={**common,**self.overrides.get(i,{})}
            try:
                payload=row_defaults(row,opt,name);self.payloads[i]=payload
                check="Připraveno";tag=()
                try:required_length_codes(payload["required_length"],self.owner.allowed_hit_lengths())
                except ValueError as exc:
                    check=str(exc);tag=("warning",)
                    if i in self.included:warnings+=1
                m=("−" if payload["med_neg"] else "+")+(payload["med_neg"] or payload["med_pos"] or "0")
                v=("−" if payload["ved_neg"] else "+")+(payload["ved_neg"] or payload["ved_pos"] or "0")
                typ=payload["connection_type"];cover=payload["cover"]
            except ValueError as exc:
                check=str(exc);tag=("error",);m="—" if row.med is None else text_number(row.med);v="—" if row.ved is None else text_number(row.ved)
                typ=opt["bending"] if row.kind=="Ohybový" else opt["shear"];cover=opt["cover"]
                if i in self.included:errors+=1
            self.tree.insert("","end",iid=str(i),tags=tag,values=("✓" if i in self.included else "—",name,row.kind,m,v,row.length_mm or "—",opt["height"],cover,opt["concrete"],opt["series"],typ,check))
        restored=[iid for iid in selected if self.tree.exists(iid)]
        if restored:self.tree.selection_set(restored)
        self.summary.set(f"{len(self.included)} z {len(self.records)} pozic • {errors} chyb • {warnings} upozornění")
        self.import_button.configure(text=f"Přidat do návrhu HIT ({len(self.included)})",state="normal" if self.included and not errors and self.ack.get() else "disabled")

    def include(self,include):
        selected={int(i) for i in self.tree.selection()}
        if include:self.included.update(selected)
        else:self.included.difference_update(selected)
        self.ack.set(False);self.render()

    def show_source(self,_event=None):
        selected=self.tree.selection()
        if selected:
            row=self.records[int(selected[0])]
            self.detail.set(f"Řádek {row.line}: {row.source}")

    def edit_selected(self):
        selected=[int(i) for i in self.tree.selection()]
        if not selected:
            messagebox.showinfo("Parametry pozic","Nejprve označte jeden nebo více řádků (Ctrl / Shift).",parent=self);return
        popup=tk.Toplevel(self);popup.title(f"Parametry {len(selected)} pozic");popup.transient(self)
        opts={k:tk.StringVar(popup,v.get()) for k,v in self.options.items()}
        for k,v in self.overrides.get(selected[0],{}).items():opts[k].set(v)
        frame=ttk.Frame(popup,padding=12);frame.pack(fill="both",expand=True)
        self.build_parameters(frame,opts)
        def save():
            values={k:v.get() for k,v in opts.items()}
            for i in selected:self.overrides[i]=dict(values)
            self.ack.set(False);self.render();popup.destroy();self.grab_set()
        ttk.Button(frame,text="Použít na označené",command=save).grid(row=5,column=0,columnspan=2,pady=10)
        ttk.Button(frame,text="Zrušit",command=lambda:(popup.destroy(),self.grab_set())).grid(row=5,column=2,pady=10)
        popup.protocol("WM_DELETE_WINDOW",lambda:(popup.destroy(),self.grab_set()))
        from ui_utils import place_dialog_on_parent
        popup.update_idletasks();place_dialog_on_parent(popup,self);popup.grab_set()

    def commit(self):
        if self.text.get("1.0","end-1c")!=self.last_text:
            self.analyze()
            messagebox.showinfo("Výkaz se změnil","Náhled byl obnoven. Zkontrolujte jej a znovu potvrďte přiřazení typů a směrů.",parent=self);return
        if not self.ack.get() or not self.included or any(i not in self.payloads for i in self.included):return
        if self.replace.get() and self.owner.hit_rows and not messagebox.askyesno("Nahradit zadání HIT","Nahradit dosavadní řádky Návrhu HIT? Projekt záměn ani katalogová data se nemění.",parent=self):return
        values=[self.payloads[i] for i in sorted(self.included)]
        try: install_rows(self.owner,values,self.replace.get())
        except Exception as exc:
            messagebox.showerror("Import HIT","Import se nezdařil: "+str(exc),parent=self);return
        self.destroy()
