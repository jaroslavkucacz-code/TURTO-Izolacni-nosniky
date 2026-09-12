from __future__ import annotations

"""One actual Tk form for Leviat and Peikko; separate engines, identical inputs."""
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from functools import wraps
from thermal_design import DEFAULTS, FUNCTIONS, calculate

SPECIFIC = ('designation','D','s11','material','family','hit_type','geometry')
BASIC = ('function','height','insulation','concrete','cover','moment','shear','axial','fire','basis')


class SharedDesign(ttk.Frame):
    def __init__(self, owner, parent):
        super().__init__(parent,style='App.TFrame',padding=(0,6,0,0))
        self.owner=owner;self.busy=False;self.results=[];self.advanced=None
        self.manufacturer=owner.design_manufacturer_var.get()
        self.specific={name:{k:DEFAULTS[k] for k in SPECIFIC} for name in ('Leviat','Peikko')}
        self.values={k:tk.StringVar(master=owner,value=v) for k,v in DEFAULTS.items()}
        self.values['concrete'].set(owner.project_concrete_var.get() or 'C25/30')
        self.widgets={};self.labels={};self.columnconfigure(0,weight=1,minsize=510);self.columnconfigure(1,weight=1,minsize=400);self.rowconfigure(0,weight=1)
        style=ttk.Style(owner);style.configure('Shared.TButton',font=('Calibri',10),padding=(7,4))
        style.configure('Shared.TEntry',padding=(3,2))
        style.configure('Shared.TCombobox',padding=(3,2))
        style.configure('Shared.TLabel',font=('Calibri',10),background=owner.colors['panel'],foreground=owner.colors['text'])
        left=ttk.Frame(self,style='Card.TFrame');left.grid(row=0,column=0,sticky='nsew',padx=(0,8))
        left.columnconfigure(0,weight=1);left.rowconfigure(0,weight=1)
        canvas=tk.Canvas(left,highlightthickness=0,bg=owner.colors['panel'],width=510,height=150)
        canvas.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(left,orient='vertical',command=canvas.yview);scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=scroll.set)
        form=ttk.Frame(canvas,style='Card.TFrame',padding=(8,5));window=canvas.create_window(0,0,window=form,anchor='nw')
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        form.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        self.form=form;self.form_canvas=canvas
        for c in (1,3):form.columnconfigure(c,weight=1)
        specs=[('Funkce','function',FUNCTIONS,20),('Výška [mm]','height',None,7),
            ('Izolant [mm]','insulation',('80','120'),6),('Beton','concrete',('C20/25','C25/30','C30/37'),9),
            ('Krytí [mm]','cover',('Auto','25','30','35','45','50'),7),('MEd','moment',None,9),
            ('VEd','shear',None,9),('NEd','axial',None,9),
            ('Požární požadavek','fire',('Bez požadavku','REI60','REI90','REI120'),16),
            ('Jednotky','basis',('Na metr spoje','Na jeden prvek'),17)]
        for i,(label,key,choices,width) in enumerate(specs):
            row,col=divmod(i,2);col*=2
            self.labels[key]=ttk.Label(form,text=label,style='Shared.TLabel')
            self.labels[key].grid(row=row,column=col,sticky='w',padx=(0,5),pady=3)
            widget=self.field(form,key,choices,width)
            widget.grid(row=row,column=col+1,sticky='ew',padx=(0,12),pady=3);self.widgets[key]=widget
        self.hint=tk.StringVar(master=owner)
        ttk.Label(form,textvariable=self.hint,style='Shared.TLabel',wraplength=480).grid(row=5,column=0,columnspan=4,sticky='ew',pady=(4,0))
        toolbar=ttk.Frame(self,style='App.TFrame');toolbar.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(5,0))
        self.buttons={}
        for label,callback in [('Navrhnout',self.run),('Převzít z dekodéru',self.from_decoder),
            ('Přidat do dekodéru',self.add),('Pokročilé…',self.open_advanced),('Uložit přehled…',self.export)]:
            b=ttk.Button(toolbar,text=label,command=callback,style='Shared.TButton');b.pack(side='left',padx=(0,7));self.buttons[label]=b
        self.buttons['Přidat do dekodéru'].configure(state='disabled')
        results=ttk.Panedwindow(self,orient='vertical');results.grid(row=0,column=1,sticky='nsew')
        table_box=ttk.Frame(results);table_box.columnconfigure(0,weight=1);table_box.rowconfigure(0,weight=1)
        self.tree=ttk.Treeview(table_box,columns=('product','usage','state'),show='headings',height=4,selectmode='browse')
        for key,label,width in [('product','Navržená konfigurace',250),('usage','Využití / meze',130),('state','Stav',130)]:
            self.tree.heading(key,text=label);self.tree.column(key,width=min(width,200),minwidth=90,stretch=True)
        self.tree.grid(row=0,column=0,sticky='nsew')
        bar=ttk.Scrollbar(table_box,orient='vertical',command=self.tree.yview);bar.grid(row=0,column=1,sticky='ns');self.tree.configure(yscrollcommand=bar.set)
        output_box=ttk.Frame(results);output_box.columnconfigure(0,weight=1);output_box.rowconfigure(0,weight=1)
        self.output=tk.Text(output_box,font=('Calibri',10),wrap='word',height=5,bg=owner.colors['panel'],fg=owner.colors['text'],relief='flat',padx=8,pady=5)
        self.output.grid(row=0,column=0,sticky='nsew');bar=ttk.Scrollbar(output_box,orient='vertical',command=self.output.yview);bar.grid(row=0,column=1,sticky='ns');self.output.configure(yscrollcommand=bar.set)
        results.add(table_box,weight=1);results.add(output_box,weight=1)
        self.tree.bind('<<TreeviewSelect>>',self.choose)
        def wheel(event):
            canvas.yview_scroll(-1 if getattr(event,'num',0)==4 or getattr(event,'delta',0)>0 else 1,'units');return 'break'
        def bind_scroll(widget):
            if not isinstance(widget,ttk.Combobox):
                for event in ('<MouseWheel>','<Button-4>','<Button-5>'):widget.bind(event,wheel,add='+')
            for child in widget.winfo_children():bind_scroll(child)
        bind_scroll(form)
        for key,v in self.values.items(): v.trace_add('write',lambda *_,k=key:self.changed(k))
        self.values['basis'].trace_add('write',lambda *_:self.update_hint())
        owner.project_concrete_var.trace_add('write',self.concrete_changed)
        self.update_hint();self.invalidate()

    def field(self,parent,key,choices=None,width=12):
        options=dict(textvariable=self.values[key],width=width,font=('Calibri',10))
        widget=ttk.Combobox(parent,values=choices,state='readonly',style='Shared.TCombobox',**options) if choices else ttk.Entry(parent,style='Shared.TEntry',**options)
        widget.bind('<Return>',lambda e:self.run());return widget

    def text(self,value):
        self.output.configure(state='normal');self.output.delete('1.0','end');self.output.insert('1.0',value);self.output.configure(state='disabled')

    def update_hint(self):
        units='M: kNm/m, V/N: kN/m' if self.values['basis'].get()=='Na metr spoje' else 'M: kNm/prvek, V/N: kN/prvek'
        for key,label,unit in [('moment','MEd','kNm'),('shear','VEd','kN'),('axial','NEd','kN')]:
            self.labels[key].configure(text=label+' ['+unit+('/m' if self.values['basis'].get()=='Na metr spoje' else '/ks')+']')
        geometry=('souvislá řada, a = L = '+self.values['length'].get()+' mm' if self.values['arrangement'].get().startswith('Souvislá') else 'vlastní rozteč '+self.values['spacing'].get()+' mm')
        self.hint.set(units+'  |  MEd: záporné = konzola, kladné = opačný směr.  |  '+geometry+'. Rozmístění měňte v Pokročilých.')

    def invalidate(self):
        self.results.clear();self.tree.delete(*self.tree.get_children());self.buttons['Přidat do dekodéru'].configure(state='disabled')
        self.text('Zadejte parametry a stiskněte Navrhnout. Krytí Auto vybírá katalogové krytí; skutečná hodnota je vždy uvedena ve výsledku.\nPeikko: samostatné meze M/V, nikoli úplný statický posudek. Požární požadavek není tímto výpočtem automaticky potvrzen.')

    def changed(self,key):
        if self.busy:return
        if key in ('height','insulation','cover','designation','D','s11','material','family') and self.values['geometry'].get()!='0':
            self.busy=True;self.values['geometry'].set('0');self.busy=False
        if key=='concrete' and self.owner.project_concrete_var.get()!=self.values[key].get():
            self.owner.project_concrete_var.set(self.values[key].get())
        self.update_hint();self.invalidate();self.owner.mark_project_dirty()

    def concrete_changed(self,*_):
        value=self.owner.project_concrete_var.get()
        if value and self.values['concrete'].get()!=value:self.values['concrete'].set(value)

    def snapshot(self):
        self.specific[self.manufacturer]={k:self.values[k].get() for k in SPECIFIC}
        return dict(schema_version=1,inputs={k:v.get() for k,v in self.values.items() if k not in SPECIFIC},manufacturer_inputs={n:dict(v) for n,v in self.specific.items()})

    def restore(self,state=None):
        state=state if isinstance(state,dict) else {};self.busy=True
        try:
            common=state.get('inputs',{});common=common if isinstance(common,dict) else {}
            for key in self.values:self.values[key].set(str(common.get(key,DEFAULTS[key])))
            saved=state.get('manufacturer_inputs',{});saved=saved if isinstance(saved,dict) else {}
            self.specific={name:{k:str(saved.get(name,{}).get(k,DEFAULTS[k])) if isinstance(saved.get(name),dict) else DEFAULTS[k] for k in SPECIFIC} for name in ('Leviat','Peikko')}
            self.manufacturer=self.owner.design_manufacturer_var.get()
            for key,val in self.specific.get(self.manufacturer,{}).items():self.values[key].set(val)
            # Project-level concrete is authoritative; an old file cannot silently override it.
            self.values['concrete'].set(self.owner.project_concrete_var.get() or DEFAULTS['concrete'])
        finally:self.busy=False
        self.update_hint();self.invalidate()

    def switch(self):
        name=self.owner.design_manufacturer_var.get()
        if name!=self.manufacturer:
            self.snapshot();self.busy=True
            try:
                self.manufacturer=name
                for k in SPECIFIC:self.values[k].set(self.specific.get(name,{}).get(k,DEFAULTS[k]))
            finally:self.busy=False
            if self.advanced is not None and self.advanced.winfo_exists():self.advanced.destroy();self.advanced=None
            self.invalidate();self.owner.mark_project_dirty()
        self.show_common()

    def show_common(self):
        state=self.owner._peikko_shared_panels['design']
        for w in [state[1],*state[2],*state[3]]:w.grid_remove()
        self.owner._shared_return_bar.grid_remove()
        self.grid(row=1,column=0,rowspan=3,sticky='nsew')
        self.owner.design_catalog_var.set('HIT – původní návrhový modul' if self.manufacturer=='Leviat' else 'EBEA / TEBEA – katalogové tabulky')

    def run(self):
        self.invalidate()
        try:
            self.results=calculate({k:v.get() for k,v in self.values.items()},self.manufacturer,self.owner.hit_db)
            if not self.results:self.text('Žádná konfigurace nesplňuje zadané parametry. Výrobce, beton, krytí, geometrie ani úplné označení nebyly automaticky změněny.');return
            for i,row in enumerate(self.results):
                c=row.get('comparison')
                usage=f"M {100*c['eta_M']:.1f} % / V {100*c['eta_V']:.1f} %" if c else f"{100*row['utilization']:.1f} %"
                self.tree.insert('', 'end', iid=str(i),values=(row['designation'],usage,row['status']))
            self.tree.selection_set('0');self.choose();self.buttons['Přidat do dekodéru'].configure(state='normal')
        except (ValueError,KeyError) as exc:self.text(str(exc))
        except Exception as exc:
            self.text('Výpočet se nepodařil. Výsledek není platný: '+str(exc))

    def selected(self):
        ids=self.tree.selection()
        return self.results[int(ids[0])] if ids and int(ids[0])<len(self.results) else None

    def choose(self,*_):
        row=self.selected()
        if row:self.text(row['designation']+'\n'+row['detail'])

    def from_decoder(self):
        from peikko_workspace import _selected_source
        from peikko_thermal_breaks import decode_peikko
        row=_selected_source(self.owner)
        if row is None:self.text('Nejdříve označte řádek ve společném Dekodéru.');return
        text=row.get('snapshot',{}).get('designation','');selection=row.get('selection',{})
        try:d=decode_peikko(text)
        except ValueError as exc:self.text(str(exc));return
        if d is not None:
            self.owner.design_manufacturer_var.set('Peikko');self.switch()
            fields=dict(designation=text,family=d.family,D=str(d.standard_d_mm or ''),s11=str(d.s11_mm or ''),
                geometry='0',material=d.material or 'Auto')
            function={'100':FUNCTIONS[0],'E-100':FUNCTIONS[2],'700':FUNCTIONS[3]}.get(d.model)
            if function:fields['function']=function
            if d.ds_mm or d.dt_mm or d.standard_d_mm:fields['height']=str(d.ds_mm or d.dt_mm or d.standard_d_mm)
            if d.sw_mm:fields['insulation']=str(d.sw_mm)
            if d.length_mm:fields['length']=str(d.length_mm)
            if d.cover_mm:fields['cover']=str(d.cover_mm)
            if d.concrete:fields['concrete']=d.concrete
            if d.fire_rating:fields['fire']=d.fire_rating
        elif text.upper().startswith('HIT-'):
            self.owner.design_manufacturer_var.set('Leviat');self.switch()
            typ=selection.get('type_name','')
            fields=dict(designation=text,insulation='80' if text.upper().startswith('HIT-HP') else '120',
                function=FUNCTIONS[1] if typ in ('ZVX','ZDX') else (FUNCTIONS[3] if typ=='DD' else FUNCTIONS[0]))
            for target,source in [('height','height_mm'),('cover','cover'),('concrete','concrete_min')]:
                if selection.get(source):fields[target]=selection[source]
            import re
            match=re.search(r'-(100|050|033|025)-',text)
            if match:fields['length']={'100':'1000','050':'500','033':'333','025':'250'}[match[1]]
        else:self.text('Tento výrobek nemá návrhový adaptér. Automatická mezivýrobní záměna nebyla provedena.');return
        for key,value in fields.items():self.values[key].set(value)
        self.owner.mark_project_dirty();self.text('Převzato: '+text+'\nZachovány všechny části označení. Pro nový volný návrh vymažte pevné označení v Pokročilých. U Peikko se neznámé D, OQ ani B2 neodhadují.')

    def add(self):
        result=self.selected()
        if not result:return
        try:
            from project_model import create_project_row
            query=self.owner.database.resolve_designation(result['designation'],preferred_concrete=self.values['concrete'].get())
            row=create_project_row(query,position=self.owner.project.next_position(),source_text=result['designation'],
                note='Návrh '+self.manufacturer+'; '+result['status']+'. Požadavek: '+self.values['fire'].get()+'. '+
                ('Tabulkové porovnání, nikoli úplný statický posudek.' if self.manufacturer=='Peikko' else 'Ověřit podmínky návrhového modulu.'))
            self.owner.project.add(row);self.owner.mark_project_dirty();self.owner.refresh_project_tree(select_ids=[row['id']])
            self.text(result['detail']+'\nPřidáno do společného Dekodéru. Celou AKCI uložte obvyklým tlačítkem Uložit.')
        except Exception as exc:messagebox.showerror('Přidání návrhu',str(exc),parent=self.owner)

    def export(self):
        path=filedialog.asksaveasfilename(parent=self.owner,title='Uložit zobrazený přehled',defaultextension='.txt',filetypes=[('Text UTF-8','*.txt')])
        if path:
            try:Path(path).write_text(self.output.get('1.0','end-1c'),encoding='utf-8-sig')
            except OSError as exc:messagebox.showerror('Uložení přehledu',str(exc),parent=self.owner)

    def show_legacy(self,technical=False):
        if self.advanced is not None:self.advanced.destroy();self.advanced=None
        self.grid_remove();state=self.owner._peikko_shared_panels['design']
        for w in [state[1],*state[2],*state[3]]:w.grid_remove()
        if technical:
            panel=state[1];p=panel._peikko_values
            mapping={'designation':'designation','D':'D','sw':'insulation','length':'length','s11':'s11','family':'family','moment':'moment','shear':'shear','axial':'axial','basis':'basis'}
            for target,source in mapping.items():p[target].set(self.values[source].get())
            p['width'].set(self.values['length'].get() if self.values['arrangement'].get().startswith('Souvislá') else self.values['spacing'].get())
            if self.values['material'].get()!='Auto':p['material'].set(self.values['material'].get())
            p['geometry'].set(False)
            panel.grid(row=1,column=0,rowspan=3,sticky='nsew');panel._peikko_show()
        else:
            for w in state[2]:w.grid()
        self.owner._shared_return_bar.grid(row=4,column=0,sticky='ew',pady=3)

    def open_advanced(self):
        if self.advanced is not None and self.advanced.winfo_exists():self.advanced.lift();return
        win=tk.Toplevel(self.owner);self.advanced=win;win.title('Pokročilé parametry – '+self.manufacturer);win.transient(self.owner);win.grab_set()
        box=ttk.Frame(win,padding=14);box.pack(fill='both',expand=True);box.columnconfigure(1,weight=1)
        fields=[('Pevné označení (prázdné = návrh)','designation',None),('Délka prvku L [mm]','length',None),
            ('Rozmístění','arrangement',('Souvislá řada (a = L)','Vlastní rozteč')),('Rozteč / zatěžovací šířka [mm]','spacing',None)]
        if self.manufacturer=='Peikko':
            fields += [('Řada','family',('EBEA','TEBEA')),('Standardní D [mm] – volitelné','D',None),
                ('S11 [mm] – pouze EBEA-700','s11',None),('Provedení','material',('Auto','RS','VE1','VE2'))]
        else:fields += [('Typ HIT','hit_type',('Auto','MVX','MVXL','ZVX','ZDX','DD'))]
        for i,(label,key,choices) in enumerate(fields):
            ttk.Label(box,text=label,font=('Calibri',10)).grid(row=i,column=0,sticky='w',pady=4,padx=(0,10))
            widget=self.field(box,key,choices,42 if key=='designation' else 24);widget.grid(row=i,column=1,sticky='ew',pady=4)
            if key=='s11' and self.values['function'].get()!=FUNCTIONS[3]:widget.configure(state='disabled')
        i=len(fields)
        if self.manufacturer=='Peikko':
            ttk.Checkbutton(box,text='Převzatý výrobek: potvrzuji standardní geometrii a krytí dle tabulky.',variable=self.values['geometry'],onvalue='1',offvalue='0').grid(row=i,column=0,columnspan=2,sticky='w',pady=5);i+=1
            ttk.Label(box,text='Nový návrh vybírá standardní katalogový prvek; D, krytí a S11 jsou vždy ve výsledku.\nU převzatého označení se Ds/Dt na D nepřevádějí. OQ/B2 nejsou ignorovány.',font=('Calibri',10),wraplength=610).grid(row=i,column=0,columnspan=2,sticky='w',pady=6);i+=1
            ttk.Button(box,text='Katalogová data a zdrojové PDF…',command=lambda:self.show_legacy(True)).grid(row=i,column=0,sticky='w')
        else:
            ttk.Button(box,text='Výkaz a speciální typy HIT…',command=self.show_legacy).grid(row=i,column=0,sticky='w')
            ttk.Button(box,text='Načíst data HIT…',command=self.owner.rebuild_hit_data).grid(row=i,column=1,sticky='w')
        ttk.Button(box,text='Zavřít',command=win.destroy).grid(row=i+1,column=1,sticky='e',pady=(10,0));win.bind('<Escape>',lambda e:win.destroy())


def _persistence(cls):
    import action_payload
    old_serialize=action_payload.serialize_action;old_load=action_payload.load_action_record;old_new=action_payload.new_action
    @wraps(old_serialize)
    def serialize(owner):
        result=old_serialize(owner)
        if hasattr(owner,'shared_thermal_design'):result['thermal_design_inputs']=owner.shared_thermal_design.snapshot()
        return result
    @wraps(old_load)
    def load(owner,record):
        old_load(owner,record)
        if hasattr(owner,'shared_thermal_design'):
            payload=record.get('payload') or {};owner.shared_thermal_design.restore(payload.get('thermal_design_inputs'))
            owner.project_dirty=False;owner._update_project_title()
    @wraps(old_new)
    def new(owner):
        # Confirm once BEFORE legacy wrappers reset platform/shear state.
        if not action_payload.confirm_action_close(owner):return
        previous_project=owner.project;previous_dirty=owner.project_dirty
        owner.project_dirty=False
        try:old_new(owner)
        except Exception:
            owner.project_dirty=previous_dirty
            raise
        # Cancellation leaves the original project object untouched.
        if owner.project is not previous_project:
            if hasattr(owner,'shared_thermal_design'):owner.shared_thermal_design.restore()
    replacements={'serialize_action':serialize,'load_action_record':load,'new_action':new}
    for name,module in list(sys.modules.items()):
        if name.startswith(('action_payload','action_workspace','action_browser')) and module:
            for attr in ('serialize_action','load_action_record','new_action'):
                if callable(getattr(module,attr,None)):setattr(module,attr,replacements[attr])
    cls.new_action=new;cls.new_project=new


def install(base):
    cls=base.ThermalConnectorApp
    if getattr(cls,'_shared_design_231',False):return
    import peikko_workspace
    old_switch=peikko_workspace._switch
    def switch(owner,mode):
        if mode=='design' and hasattr(owner,'shared_thermal_design'):owner.shared_thermal_design.switch()
        else:old_switch(owner,mode)
    peikko_workspace._switch=switch
    previous=cls._build_body
    def body(self):
        previous(self)
        self._shared_return_bar=ttk.Frame(self.hit_tab,style='App.TFrame')
        ttk.Button(self._shared_return_bar,text='← Zpět na společné zadání návrhu',command=lambda:self.shared_thermal_design.show_common()).pack(side='left')
        self.shared_thermal_design=SharedDesign(self,self.hit_tab);self.shared_thermal_design.show_common()
    cls._build_body=body;_persistence(cls);cls._shared_design_231=True
