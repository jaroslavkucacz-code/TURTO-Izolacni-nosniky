from __future__ import annotations
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk
try:
    from ui_utils import place_dialog_on_parent
except Exception:
    place_dialog_on_parent=None

DECODER_COLUMNS=(
("order","Poř.",52,"center",False),("position","Pozice",86,"w",False),("quantity","Ks",54,"center",False),
("manufacturer","Výrobce",105,"w",False),("model","Řada",100,"center",False),("type_name","Typ",82,"center",False),
("generation","Generace",74,"center",False),("moment_class","Momentová třída",112,"center",False),("shear_class","Smyková třída",112,"center",False),
("concrete","Beton",88,"center",False),("cover","Krytí / varianta",126,"center",False),("height","Výška / rozměr",112,"center",False),
("insulation","Izolant",76,"center",False),("compression","Tlakový přenos",176,"w",False),("moment","MRd / moment",138,"center",False),
("shear","VRd / síla",154,"center",False),("extra","Další únosnosti",220,"w",False),("designation","Úplné označení",380,"w",True),
("catalog","Zdroj / katalog",190,"w",False),("pages","Str.",58,"center",False),("mapping","Záměna HIT",130,"center",False),
("note","Poznámka",250,"w",True),("status","Stav dat",116,"center",False),)
SUBSTITUTION_LABELS={"m_pos":"MEd+ / prvek","m_neg":"MEd− / prvek","n_pos":"NEd+ / prvek","n_neg":"NEd− / prvek","v_pos":"VEd+ / prvek","v_neg":"VEd− / prvek","estimated_type":"Odhad HIT","target_type":"Typ HIT","wire_diameter":"Ø drátu","target":"Navržený HIT","target_m":"MRd / prvek","target_v":"VRd / prvek","target_n":"NRd / prvek","utilization":"Využití","alternatives":"Varianty / průměry","calculation":"Statická kontrola","status":"Výsledek","confirmation":"Potvrzení","note":"Poznámka / omezení"}

class ColumnLayoutDialog(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.title("Sloupce Dekodéru ISO");self.geometry("760x650");self.minsize(620,520);self.transient(owner);self.grab_set();self.configure(background=owner.colors["bg"])
        if place_dialog_on_parent:
            try:place_dialog_on_parent(self,owner)
            except Exception:pass
        outer=ttk.Frame(self,style="App.TFrame",padding=16);outer.pack(fill="both",expand=True);outer.columnconfigure(0,weight=1);outer.rowconfigure(2,weight=1)
        ttk.Label(outer,text="Rozložení sloupců Dekodéru ISO",style="DialogTitle.TLabel").grid(row=0,column=0,sticky="w")
        ttk.Label(outer,text="Vyberte sloupec a použijte šipky pro přesun. Dvojklik přepíná zobrazení. Změny se ukládají automaticky.",style="Muted.TLabel",wraplength=700,justify="left").grid(row=1,column=0,sticky="ew",pady=(4,10))
        box=ttk.Frame(outer,style="Card.TFrame",padding=1);box.grid(row=2,column=0,sticky="nsew");box.columnconfigure(0,weight=1);box.rowconfigure(0,weight=1)
        self.tree=ttk.Treeview(box,columns=("visible","name","width"),show="headings",selectmode="browse",style="Project.Treeview")
        for c,t,a,w in (("visible","Zobrazen","center",80),("name","Sloupec","w",460),("width","Šířka","center",90)):
            self.tree.heading(c,text=t,anchor=a);self.tree.column(c,width=w,minwidth=60,anchor=a,stretch=c=="name")
        y=ttk.Scrollbar(box,orient="vertical",command=self.tree.yview);self.tree.configure(yscrollcommand=y.set);self.tree.grid(row=0,column=0,sticky="nsew");y.grid(row=0,column=1,sticky="ns")
        self.tree.bind("<Double-1>",lambda _e:self.toggle());self.tree.bind("<space>",lambda _e:(self.toggle(),"break")[1])
        controls=ttk.Frame(outer,style="App.TFrame");controls.grid(row=3,column=0,sticky="ew",pady=(10,0));controls.columnconfigure(9,weight=1)
        ttk.Button(controls,text="↑ Nahoru",command=lambda:self.move(-1)).grid(row=0,column=0);ttk.Button(controls,text="↓ Dolů",command=lambda:self.move(1)).grid(row=0,column=1,padx=(6,0))
        ttk.Button(controls,text="⇤ Na začátek",command=lambda:self.edge("first")).grid(row=0,column=2,padx=(12,0));ttk.Button(controls,text="⇥ Na konec",command=lambda:self.edge("last")).grid(row=0,column=3,padx=(6,0))
        ttk.Separator(controls,orient="vertical").grid(row=0,column=4,sticky="ns",padx=10);ttk.Button(controls,text="Zobrazit / skrýt",command=self.toggle).grid(row=0,column=5);ttk.Button(controls,text="Automatická šířka",command=self.fit).grid(row=0,column=6,padx=(6,0));ttk.Button(controls,text="Zobrazit vše",command=self.show_all).grid(row=0,column=7,padx=(12,0));ttk.Button(controls,text="Výchozí",command=self.reset).grid(row=0,column=8,padx=(6,0));ttk.Button(controls,text="Zavřít",style="Accent.TButton",command=self.destroy).grid(row=0,column=10,sticky="e")
        self.bind("<Escape>",lambda _e:self.destroy());self.refresh()
    def selected(self):
        s=self.tree.selection();return str(s[0]) if s else None
    def refresh(self,select=None):
        previous=select or self.selected();self.tree.delete(*self.tree.get_children(""));state=self.owner._project_layout_state();hidden=set(state.get("hidden",[]));labels=self.owner._project_heading_labels
        for col in state["order"]:
            width=int(state.get("widths",{}).get(col,self.owner.project_tree.column(col,"width")));self.tree.insert("","end",iid=col,values=("✓" if col not in hidden else "—",labels.get(col,col),f"{width} px"))
        if previous and self.tree.exists(previous):self.tree.selection_set(previous);self.tree.focus(previous);self.tree.see(previous)
    def move(self,delta):
        c=self.selected();
        if c:self.owner._move_project_column(c,delta);self.refresh(c)
    def edge(self,edge):
        c=self.selected();
        if c:self.owner._move_project_column(c,edge=edge);self.refresh(c)
    def toggle(self):
        c=self.selected();
        if c:self.owner._set_project_column_visible(c,c in set(self.owner._project_layout_state().get("hidden",[])));self.refresh(c)
    def fit(self):
        c=self.selected();
        if c:self.owner._fit_project_column(c);self.refresh(c)
    def show_all(self):self.owner._show_all_project_columns();self.refresh()
    def reset(self):
        if messagebox.askyesno("Výchozí rozložení","Obnovit výchozí pořadí, viditelnost a šířky sloupců Dekodéru ISO?",parent=self):self.owner._reset_project_column_layout();self.refresh()

def install(project_mixin:Any,substitution_mixin:Any|None=None)->None:
    project_mixin.PROJECT_COLUMNS=DECODER_COLUMNS;old_apply=project_mixin._apply_project_column_layout;old_update=project_mixin._update_project_heading_labels;old_build=project_mixin._build_project_tab
    def align(self):
        if not hasattr(self,"project_tree"):return
        for c,_l,_w,a,_s in self.PROJECT_COLUMNS:
            try:self.project_tree.heading(c,anchor=a)
            except Exception:pass
    def apply(self):old_apply(self);align(self)
    def update(self):old_update(self);align(self)
    def fit(self,column):
        if not hasattr(self,"project_tree"):return
        label=self._project_heading_labels.get(column,column);longest=len(str(label));count=0
        for iid in self.project_tree.get_children(""):
            try:v=str(self.project_tree.set(iid,column))
            except Exception:continue
            longest=max(longest,min(70,len(v)));count+=1
            if count>=250:break
        width=max(54,min(560,22+longest*8));self.project_tree.column(column,width=width);self._project_layout_state().setdefault("widths",{})[column]=width;self.capture_project_table_layout();self.set_status(f"Sloupec „{label}“: automatická šířka {width} px.")
    def manager(self):ColumnLayoutDialog(self)
    def header(self,event):
        if self.project_tree.identify_region(event.x,event.y)!="heading":return None
        column=self._project_column_from_x(event.x)
        if not column:return "break"
        label=self._project_heading_labels.get(column,column);menu=tk.Menu(self,tearoff=False,font=("Calibri",10),background=self.colors["panel"],foreground=self.colors["text"],activebackground=self.colors["accent"],activeforeground="#FFFFFF")
        menu.add_command(label=f"↑ Seřadit „{label}“ vzestupně",command=lambda:self.sort_project_table(column,reverse=False));menu.add_command(label=f"↓ Seřadit „{label}“ sestupně",command=lambda:self.sort_project_table(column,reverse=True));menu.add_separator();menu.add_command(label="← Posunout o sloupec vlevo",command=lambda:self._move_project_column(column,-1));menu.add_command(label="→ Posunout o sloupec vpravo",command=lambda:self._move_project_column(column,1));menu.add_command(label="Automatická šířka",command=lambda:self._fit_project_column(column));menu.add_separator();menu.add_command(label="Skrýt tento sloupec",command=lambda:self._set_project_column_visible(column,False));menu.add_command(label="Nastavit všechny sloupce…",command=self.open_project_columns_manager)
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:
            try:menu.grab_release()
            except Exception:pass
        return "break"
    def build(self,parent):old_build(self,parent);align(self);button=getattr(self,"project_columns_button",None);button.configure(text="Sloupce…",command=self.open_project_columns_manager) if button is not None else None
    project_mixin._apply_project_column_layout=apply;project_mixin._update_project_heading_labels=update;project_mixin._fit_project_column=fit;project_mixin.open_project_columns_manager=manager;project_mixin._show_project_columns_button_menu=manager;project_mixin._show_project_header_menu=header;project_mixin._build_project_tab=build
    if substitution_mixin is not None:install_substitution(substitution_mixin)

def install_substitution(substitution_mixin:Any)->None:
    if getattr(substitution_mixin,"_turto_heading_polish_installed",False):return
    substitution_mixin._turto_heading_polish_installed=True;old=list(substitution_mixin.COLUMNS);substitution_mixin.COLUMNS=tuple((k,SUBSTITUTION_LABELS.get(k,l),w,a,s) for k,l,w,a,s in old);old_build=substitution_mixin._build_substitution_tab
    def build(self,parent):
        old_build(self,parent)
        if hasattr(self,"sub_tree"):
            for k,_l,_w,a,_s in self.COLUMNS:
                try:self.sub_tree.heading(k,anchor=a)
                except Exception:pass
    substitution_mixin._build_substitution_tab=build
