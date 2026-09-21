"""Retain incomplete schedule rows and complete them from catalogues or by hand.

Catalogue snapshots and the original imported line are retained as provenance.
Incomplete rows never acquire fabricated capacities or a passing substitution.
"""
from copy import deepcopy
from functools import wraps
import math
import re
import uuid
import tkinter as tk
from tkinter import ttk, messagebox

SELECTION_KEYS = ('catalog_id','manufacturer','model','type_name','generation',
                  'moment_class','concrete_min','shear_class','cover','height_mm')
LOAD_KEYS = ('m_pos','m_neg','n_pos','n_neg','v_pos','v_neg')
PENDING = 'Doplnit v Záměnách'


def unresolved_row(item):
    from designation_format_321 import normalize
    from project_model import normalize_project_row
    text = str(item.get('source_text') or item.get('raw') or '').strip()
    code = normalize(text)
    selection = dict.fromkeys(SELECTION_KEYS, '')
    match = re.match(r'^(T|XT|CXT)-([A-Z]+(?:-[A-Z]+)?)(?=-|$)', code)
    if match:
        selection.update(manufacturer='Schöck', model=match[1], type_name=match[2])
    for key, pattern in (('height_mm',r'(?:^|-)H(\d+)(?:-|$)'),
                         ('cover',r'(?:^|-)(CV\d+)(?:-|$)'),
                         ('moment_class',r'(?:^|-)(M\d+)(?:-|$)'),
                         ('shear_class',r'(?:^|-)(VV?\d+)(?:-|$)'),
                         ('generation',r'-(\d+\.\d+)$')):
        matches = re.findall(pattern, code)
        if len(set(matches)) == 1:
            selection[key] = matches[0]
    completion = dict(state='pending', message=str(item.get('message') or PENDING),
                      original_input=text, raw=str(item.get('raw') or text),
                      source_line=item.get('source_line'), analysis_status=item.get('status'))
    row = normalize_project_row(dict(id=uuid.uuid4().hex, position=item.get('position',''),
        quantity=item.get('quantity',1), note=item.get('note',''), source_text=text,
        selection=selection, snapshot=dict(designation=text,results=[],completion=completion)))
    if item.get('element_length_mm') is not None:
        from decoder_length_320 import set_length
        set_length(row,item['element_length_mm'])
    return row


def use_catalogue(row, result):
    from project_model import create_project_row
    old = (row.get('snapshot') or {}).get('completion') or {}
    updated = create_project_row(result, row_id=row['id'], position=row['position'],
        quantity=row['quantity'], note=row.get('note',''), source_text=row.get('source_text',''))
    if not updated['snapshot'].get('element_length_mm'):
        from iso_bulk_301 import _length
        updated['snapshot']['element_length_mm'] = _length(result.record)
    updated['snapshot']['completion'] = dict(old, state='catalogue',
        original_input=old.get('original_input') or row.get('source_text',''),
        catalogue_selection=deepcopy(updated['selection']),
        catalogue_snapshot=deepcopy(updated['snapshot']))
    # A separately supplied physical length is an explicit input, not a lookup
    # default. Keep it so an incompatible per-element catalogue remains flagged.
    overrides = (row.get('mapping') or {}).get('source_overrides') or {}
    if overrides.get('source_length_mm'):
        from decoder_length_320 import set_length
        set_length(updated,overrides['source_length_mm'])
    return updated


def positive_integer(text, label):
    if not str(text).strip():
        return None
    if not re.fullmatch(r'\d+',str(text).strip()) or not 1 <= int(text) <= 10000:
        raise ValueError(label + ': zadejte celé číslo 1–10 000, nebo pole ponechte prázdné.')
    return int(text)


def form_values(row):
    import substitution_workspace as sub
    meta = sub.source_metadata(row)
    selection, snapshot = row['selection'],row['snapshot']
    values = {key: str(selection.get(key) or '') for key in SELECTION_KEYS}
    values.update(source_text=row.get('source_text',''),
        height_mm=str(meta.get('source_height_mm') or ''),
        length=str(meta.get('source_length_mm') or ''),
        insulation=str(meta.get('source_insulation_mm') or ''),
        source_cover=str(meta.get('source_cover_mm') or ''),
        target_cover=str(meta.get('target_cover_mm') or ''),
        target_type=str((row.get('mapping') or {}).get('source_overrides',{}).get('target_type') or 'Automaticky'),
        geometry=str(meta.get('geometry_target') or 'Automaticky'),
        bx=str(meta.get('geometry_bx_mm') or ''),
        compression={'bearing':'S ložisky','without':'Bez ložisek'}.get(meta.get('source_compression_category'),'Neuvedeno'))
    # Preserve a per-metre table even while its physical length is unknown.
    results=snapshot.get('results') or []
    per_m=bool(results) and all(sub._per_m(r.get('kind'),r.get('unit')) for r in results)
    actions, _ = sub.source_actions(row) if per_m else sub.source_element_actions(row)
    values.update({key:format(getattr(actions,key),'.12g') if getattr(actions,key) else '' for key in LOAD_KEYS})
    values['basis'] = 'Na metr' if per_m else 'Na prvek'
    return values


def apply_manual(row, values, initial):
    """Save partial edits; strict numerical validation applies to supplied data."""
    from project_model import now_iso
    from catalog_engine import format_result
    updated = deepcopy(row)
    changed = {k for k,v in values.items() if v != initial.get(k,'')}
    if not changed:
        return updated
    selection, snapshot = updated['selection'],updated['snapshot']
    previous = deepcopy(snapshot)
    completion = dict(snapshot.get('completion') or {})
    completion.setdefault('original_input',row.get('source_text',''))
    if snapshot.get('results') and 'catalogue_snapshot' not in completion and completion.get('state') != 'manual':
        completion['catalogue_snapshot'] = previous
        completion['catalogue_selection'] = deepcopy(selection)
    for key in SELECTION_KEYS:
        if key in changed:
            selection[key] = values[key].strip()
    if 'source_text' in changed:
        if not values['source_text'].strip():
            raise ValueError('Označení nesmí být prázdné.')
        updated['source_text'] = values['source_text'].strip()
        snapshot['designation'] = updated['source_text']
    overrides = deepcopy(updated.get('mapping',{}).get('source_overrides') or {})
    for key, dest, label in (('length','source_length_mm','Délka'),
                             ('source_cover','source_cover_mm','Krytí zdroje'),
                             ('target_cover','target_cover_mm','Krytí HIT')):
        if key in changed:
            number = positive_integer(values[key],label)
            if key=='target_cover' and number not in (None,30,35,50):
                raise ValueError('Krytí HIT: vyberte 30, 35 nebo 50 mm.')
            if number is None: overrides.pop(dest,None)
            else: overrides[dest] = number
    if 'height_mm' in changed:
        positive_integer(values['height_mm'],'Výška')
    if 'insulation' in changed:
        snapshot['insulation_thickness_mm'] = positive_integer(values['insulation'],'Izolant')
        snapshot['insulation_text'] = (values['insulation']+' mm') if values['insulation'] else '—'
    if 'compression' in changed:
        category = {'S ložisky':'bearing','Bez ložisek':'without'}.get(values['compression'])
        if category: overrides['compression_category'] = category
        else:
            overrides.pop('compression_category',None)
            snapshot['compression_transfer'] = 'neuvedeno'
    if 'target_type' in changed:
        typ = values['target_type']
        if typ not in ('Automaticky','MVX','MVXL','ZVX','ZDX','DD','DVL','DDL'):
            raise ValueError('Vyberte platný typ HIT.')
        if typ=='Automaticky': overrides.pop('target_type',None)
        else: overrides['target_type'] = typ
    if changed & {'geometry','bx'}:
        geometry=values['geometry']
        if geometry in ('OU','OD'):
            bx=positive_integer(values['bx'],'bx')
            maximum=290 if values['insulation']=='120' else 330
            if bx is None or not 175<=bx<=maximum: raise ValueError(f'bx musí být 175–{maximum} mm.')
            overrides.update(geometry_mode='manual',geometry_variant=geometry,geometry_bx_mm=bx,
                             geometry_confirmed=True,geometry_origin='manual')
        else:
            overrides.update(geometry_mode='none' if geometry=='Bez OU/OD' else 'auto',
                geometry_variant='',geometry_bx_mm=None,geometry_confirmed=geometry=='Bez OU/OD',geometry_origin='manual')
    if changed & set(LOAD_KEYS+('basis',)):
        if values['basis'] not in ('Na prvek','Na metr'):
            raise ValueError('Vyberte jednotky na prvek nebo na metr.')
        loads={}
        for key in LOAD_KEYS:
            try: number=float(values[key].replace(',','.')) if values[key].strip() else 0.0
            except ValueError: raise ValueError('Únosnosti M/N/V musí být čísla.') from None
            if not math.isfinite(number) or number<0: raise ValueError('Únosnosti musí být konečné a nezáporné; směr určuje sloupec +/−.')
            loads[key]=number
        results=[]
        for prefix,kind,label,unit in (('m','moment','MRd','kNm'),('n','normal','NRd','kN'),('v','shear','VRd','kN')):
            if loads[prefix+'_pos'] or loads[prefix+'_neg']:
                results.append(dict(key=prefix+'_rd',label=label,kind=kind,positive=loads[prefix+'_pos'],
                    negative=-loads[prefix+'_neg'],unit=unit+('/prvek' if values['basis']=='Na prvek' else '/m')))
        snapshot['results']=results
        snapshot['results_text']='\n'.join(format_result(r) for r in results)
        for name,kind in (('moment_text','moment'),('shear_text','shear'),('other_text','normal')):
            snapshot[name]='; '.join(format_result(r) for r in results if r['kind']==kind) or '—'
        if results:
            snapshot['substitution_policy']='automatic'
            snapshot['substitution_note']=''
    elif changed & {'source_text','manufacturer','model','type_name','generation','moment_class','shear_class','concrete_min','height_mm','insulation','source_cover'}:
        # A changed product must not inherit the old product's capacities.
        # Resolve it from the catalogue or explicitly provide manual values.
        snapshot['results']=[]
        for key in ('results_text','moment_text','shear_text','other_text'):snapshot[key]='—'
        completion['message']='Změněny parametry zdroje. Znovu vyberte katalogový záznam nebo zadejte jeho únosnosti.'
    completion.update(state='manual' if snapshot.get('results') else 'pending', updated_at=now_iso(),
                      edited_fields=sorted(set(completion.get('edited_fields',[])) | changed))
    snapshot['completion']=completion
    updated['mapping']=dict(status='not_run',targets=[],selected_target_id=None,source_meta={},
        warnings=[],errors=[],estimated_type='',diameter_availability={},source_overrides=overrides)
    return updated


class CompletionDialog(tk.Toplevel):
    def __init__(self, owner, row):
        super().__init__(owner)
        self.owner=owner;self.database=owner.database;self.row=deepcopy(row);self.result=None
        self.title('Upřesnit prvek – katalog a ruční údaje')
        self.geometry('1080x740');self.minsize(860,650);self.transient(owner);self.grab_set()
        from ui_utils import place_dialog_on_parent
        place_dialog_on_parent(self,owner)
        outer=ttk.Frame(self,padding=14);outer.pack(fill='both',expand=True)
        outer.columnconfigure(0,weight=1);outer.rowconfigure(1,weight=1)
        ttk.Label(outer,text=f"{row['position']} · {row['quantity']} ks · {row.get('source_text','')}",wraplength=1000).grid(row=0,column=0,sticky='w',pady=(0,10))
        self.tabs=ttk.Notebook(outer);self.tabs.grid(row=1,column=0,sticky='nsew')
        self.catalogue=ttk.Frame(self.tabs,padding=12);self.manual=ttk.Frame(self.tabs,padding=12)
        self.tabs.add(self.catalogue,text='1. Upřesnit podle katalogu');self.tabs.add(self.manual,text='2. Ručně doplnit / opravit')
        self._build_catalogue();self._build_manual();self.fill()
        self.hint=tk.StringVar(value='Vyberte katalogovou variantu, nebo otevřete ruční doplnění. Neúplný řádek lze uložit.')
        ttk.Label(outer,textvariable=self.hint,wraplength=1000).grid(row=2,column=0,sticky='w',pady=8)
        buttons=ttk.Frame(outer);buttons.grid(row=3,column=0,sticky='e')
        ttk.Button(buttons,text='Zrušit',command=self.destroy).pack(side='right')
        ttk.Button(buttons,text='Uložit a přepočítat',command=self.save,style='Accent.TButton').pack(side='right',padx=8)
        self.bind('<Escape>',lambda e:self.destroy())
        self.search()

    def _build_catalogue(self):
        parent=self.catalogue;parent.columnconfigure(0,weight=1);parent.rowconfigure(2,weight=1)
        bar=ttk.Frame(parent);bar.grid(row=0,column=0,sticky='ew');bar.columnconfigure(0,weight=1)
        self.query=tk.StringVar(value=self.row.get('source_text',''))
        ttk.Entry(bar,textvariable=self.query).grid(row=0,column=0,sticky='ew')
        ttk.Button(bar,text='Najít odpovídající varianty',command=self.search).grid(row=0,column=1,padx=(8,0))
        ttk.Label(parent,text='Vyberte konkrétní záznam. Výběrem se převezmou dostupné údaje a jejich katalogový zdroj.',wraplength=970).grid(row=1,column=0,sticky='w',pady=8)
        frame=ttk.Frame(parent);frame.grid(row=2,column=0,sticky='nsew');frame.columnconfigure(0,weight=1);frame.rowconfigure(0,weight=1)
        self.tree=ttk.Treeview(frame,columns=('designation','catalogue','values'),show='headings',height=8,selectmode='browse')
        for key,title,width in (('designation','Katalogové označení',410),('catalogue','Katalog / vydání',220),('values','Únosnosti',280)):
            self.tree.heading(key,text=title);self.tree.column(key,width=width,minwidth=80)
        self.tree.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview);scroll.grid(row=0,column=1,sticky='ns');self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<Double-1>',lambda e:self.choose());self.tree.bind('<Return>',lambda e:self.choose())
        ttk.Button(parent,text='Použít vybranou katalogovou variantu',command=self.choose).grid(row=3,column=0,sticky='e',pady=8)
        # All loaded families are available for descriptions the parser cannot
        # recognise. A different family/edition is always an explicit choice.
        chooser=ttk.LabelFrame(parent,text='Výběr podle katalogových parametrů',padding=8)
        chooser.grid(row=4,column=0,sticky='ew');chooser.columnconfigure(1,weight=1)
        self.family_by_label={}
        for f in self.database.families:
            catalog=self.database.catalogs.get(f.get('catalog_id'),{})
            label=' · '.join(str(x or '') for x in (f.get('manufacturer'),f.get('model'),f.get('type'),f.get('generation'),catalog.get('edition'),f.get('catalog_id')))
            self.family_by_label[label]=f
        self.family_var=tk.StringVar()
        combo=ttk.Combobox(chooser,textvariable=self.family_var,values=sorted(self.family_by_label),state='readonly')
        ttk.Label(chooser,text='Řada / generace / katalog').grid(row=0,column=0,sticky='w',padx=(0,8))
        combo.grid(row=0,column=1,sticky='ew');combo.bind('<<ComboboxSelected>>',lambda e:self.selectors())
        self.selector_keys=('moment_class','concrete_min','shear_class','cover','height_mm')
        self.selector_vars={};self.selector_widgets={}
        controls=ttk.Frame(chooser);controls.grid(row=1,column=0,columnspan=2,sticky='ew',pady=8)
        for col,(key,label) in enumerate(zip(self.selector_keys,('Třída M / typ','Beton','Třída V','Krytí / varianta','Výška'))):
            ttk.Label(controls,text=label).grid(row=0,column=col,sticky='w')
            var=tk.StringVar();self.selector_vars[key]=var
            w=ttk.Combobox(controls,textvariable=var,state='readonly',width=18);w.grid(row=1,column=col,padx=(0,5),sticky='ew')
            controls.columnconfigure(col,weight=1);self.selector_widgets[key]=w
            w.bind('<<ComboboxSelected>>',lambda e,i=col:self.selectors(i+1))
        ttk.Button(chooser,text='Zobrazit tento katalogový záznam',command=self.query_selectors).grid(row=2,column=0,columnspan=2,sticky='e')

    def selectors(self,start=0):
        f=self.family_by_label.get(self.family_var.get())
        if not f:return
        db=self.database
        for index,key in enumerate(self.selector_keys):
            if index<start:continue
            v={k:x.get() for k,x in self.selector_vars.items()}
            try:
                opts=(lambda:db.moment_classes(f),lambda:db.concrete_classes(f,v['moment_class']),
                    lambda:db.shear_classes(f,v['moment_class'],v['concrete_min']),
                    lambda:db.covers(f,v['moment_class'],v['concrete_min'],v['shear_class']),
                    lambda:db.heights(f,v['moment_class'],v['concrete_min'],v['cover'],v['shear_class']))[index]()
            except (KeyError,ValueError):opts=[]
            self.selector_widgets[key].configure(values=opts)
            if v[key] not in opts:self.selector_vars[key].set(opts[0] if len(opts)==1 else '')

    def query_selectors(self):
        f=self.family_by_label.get(self.family_var.get())
        if not f:return
        try:
            result=self.database.query(catalog_id=f['catalog_id'],manufacturer=f['manufacturer'],model=f['model'],type_name=f['type'],generation=f['generation'],
                **{k:v.get() for k,v in self.selector_vars.items()})
        except Exception as e:
            self.hint.set(str(e));return
        self.show_results([result])
        self.hint.set('Zkontrolujte záznam a stiskněte Použít vybranou katalogovou variantu.')

    def show_results(self,results):
        self.matches=list(results);self.tree.delete(*self.tree.get_children())
        for i,result in enumerate(self.matches):
            self.tree.insert('', 'end',iid=str(i),values=(result.designation,
                ' · '.join(str(result.catalog.get(k) or '') for k in ('edition','publication_label')),
                result.all_results_text.replace('\n','; ')))
        if self.matches:self.tree.selection_set('0')

    def search(self):
        concrete=self.row['selection'].get('concrete_min') or self.owner.project_concrete_var.get()
        try:
            matches=self.database.suggest_designations(self.query.get(),preferred_concrete=concrete,limit=100)
            self.show_results([c.result for c in matches])
            self.hint.set(f'Nalezeno {len(matches)} variant. Výběr je nutné potvrdit.' if matches else 'Odpovídající varianta nebyla nalezena. Vyberte katalogové parametry nebo údaje doplňte ručně.')
        except Exception as e:self.hint.set(str(e))

    def choose(self):
        if not self.tree.selection():return
        self.row=use_catalogue(self.row,self.matches[int(self.tree.selection()[0])])
        self.fill();self.tabs.select(self.manual)
        self.hint.set('Katalogová data převzata do formuláře. Doplňte chybějící údaje a uložte.')

    def _build_manual(self):
        self.vars={};frame=self.manual
        fields=[('source_text','Označení',()),('manufacturer','Výrobce',()),('model','Řada',()),('type_name','Typ zdroje',()),
            ('generation','Generace',()),('moment_class','Třída M / typ',()),('shear_class','Třída V',()),
            ('concrete_min','Beton',('C20/25','C25/30','C30/37')),('height_mm','Výška [mm]',()),('length','Délka zdroje [mm]',()),
            ('insulation','Izolant [mm]',('80','120')),('source_cover','Krytí zdroje [mm]',('30','35','50')),
            ('target_cover','Krytí HIT [mm]',('','30','35','50')),('target_type','Typ HIT',('Automaticky','MVX','MVXL','ZVX','ZDX','DD','DVL','DDL')),
            ('compression','Tlakový přenos',('Neuvedeno','S ložisky','Bez ložisek')),
            ('geometry','Geometrie HIT',('Automaticky','Bez OU/OD','OU','OD')),('bx','bx [mm]',()),('basis','Jednotky únosností',('Na prvek','Na metr'))]
        fields += [(key,label,()) for key,label in zip(LOAD_KEYS,('MRd+ [kNm]','MRd− [kNm]','NRd+ [kN]','NRd− [kN]','VRd+ [kN]','VRd− [kN]'))]
        for i,(key,label,choices) in enumerate(fields):
            r,c=divmod(i,2);c*=2
            ttk.Label(frame,text=label).grid(row=r,column=c,sticky='w',padx=(0,8),pady=4)
            var=tk.StringVar();self.vars[key]=var
            readonly=key in {'target_cover','target_type','compression','geometry','basis'}
            widget=ttk.Combobox(frame,textvariable=var,values=choices,state='readonly' if readonly else 'normal') if choices else ttk.Entry(frame,textvariable=var)
            widget.grid(row=r,column=c+1,sticky='ew',padx=(0,18),pady=4);frame.columnconfigure(c+1,weight=1)
        ttk.Label(frame,text='Prázdné údaje zůstávají neznámé. Krytí HIT je samostatná volba; nedoplňuje krytí původního prvku.\nZměny únosností jsou označeny jako ruční zadání a původní katalogové hodnoty zůstanou v záznamu.',wraplength=960).grid(row=12,column=0,columnspan=4,sticky='w',pady=10)

    def fill(self):
        values=form_values(self.row)
        for k,v in self.vars.items():v.set(values.get(k,''))
        self.initial={k:v.get() for k,v in self.vars.items()}

    def save(self):
        try:self.result=apply_manual(self.row,{k:v.get() for k,v in self.vars.items()},self.initial)
        except ValueError as e:
            self.hint.set(str(e));return
        self.destroy()


def edit_source(owner):
    selected=list(owner.sub_tree.selection())
    if len(selected)!=1:return
    row=owner.project.row_by_id(selected[0])
    if row is None:return
    dialog=CompletionDialog(owner,row);owner.wait_window(dialog)
    if dialog.result is None:return
    row.clear();row.update(dialog.result)
    owner.project.touch();owner.mark_project_dirty()
    owner.refresh_project_tree(select_ids=selected);owner.refresh_substitution_tree()
    owner.sub_tree.selection_set(selected)
    if getattr(owner,'hit_db',None) is not None:owner.design_substitutions(True)


def compact_layout(owner):
    """Only table-containing rows may take the free vertical workspace."""
    for root in getattr(owner, 'product_domain_tab_by_id', {}).values():
        if root is None:continue
        from workspace_controls_317 import walk
        for frame in walk(root):
            if not isinstance(frame,ttk.Frame):continue
            children=[c for c in frame.winfo_children() if c.winfo_manager()=='grid']
            if not children:continue
            # Empty grid rows kept their old weight after manufacturer panels
            # moved down. Likewise an inherited weight stretched heading rows.
            table_rows=set()
            for child in children:
                if isinstance(child,(ttk.Treeview,tk.Canvas,ttk.Notebook)) or any(isinstance(w,(ttk.Treeview,tk.Canvas,ttk.Notebook)) for w in walk(child)):
                    info=child.grid_info();table_rows.add(int(info['row'])+int(info.get('rowspan',1))-1)
            if not table_rows:continue
            for r in range(frame.grid_size()[1]):
                frame.rowconfigure(r,weight=1 if r in table_rows else 0,minsize=0)


def install(base):
    import substitution_workspace as sub
    cls=base.ThermalConnectorApp
    if getattr(cls,'_source_completion',False):return
    cls._source_completion=True
    import hit_workspace,hit_units_310,project_model
    init_row=hit_workspace.HitInputRow.__init__
    @wraps(init_row)
    def init_hit(row,owner,row_no,defaults=None):
        defaults=dict(defaults or {})
        if str(defaults.get('required_length','')).strip()=='333' and defaults.get('connection_type','MVX') in hit_units_310.STANDARD:
            defaults['required_length']='330'
        init_row(row,owner,row_no,defaults)
    hit_workspace.HitInputRow.__init__=init_hit
    normalize=project_model.normalize_project_row
    @wraps(normalize)
    def normalize_row(raw):
        row=normalize(raw)
        if row['selection'].get('catalog_id')=='leviat_hit_2023':
            row['selection']['shear_class']=re.sub(r'^L333(?=\||$)','L330',row['selection']['shear_class'])
            if row['snapshot'].get('element_length_mm')==333:row['snapshot']['element_length_mm']=330
        mapping=row['mapping']
        if any(t.get('length_mm')==333 for t in mapping.get('targets',[]) if isinstance(t,dict)):
            overrides=deepcopy(mapping.get('source_overrides') or {})
            row['mapping']=dict(status='not_run',targets=[],selected_target_id=None,source_meta={},
                warnings=['Délka HIT byla opravena na 330 mm; záměnu znovu přepočítejte.'],errors=[],
                estimated_type='',diameter_availability={},source_overrides=overrides,substitution_acceptance={})
        return row
    hit_units_310._replace_imports('normalize_project_row',normalize,normalize_row)
    previous_meta=sub.source_metadata
    @wraps(previous_meta)
    def metadata(row):
        meta=previous_meta(row)
        overrides=row.get('mapping',{}).get('source_overrides') or {}
        source_cover=overrides.get('source_cover_mm')
        target_cover=overrides.get('target_cover_mm')
        if source_cover:
            meta['source_cover_mm']=source_cover
            if target_cover is None:target_cover=source_cover
        if target_cover in (30,35,50):
            meta['target_cover_mm']=target_cover
            meta['errors']=[e for e in meta.get('errors',[]) if e!='krytí musí být jednoznačně 30, 35 nebo 50 mm']
            meta['cover_resolution']='manual'
            meta['cover_resolution_note']='Cílové krytí HIT zvoleno ručně; krytí zdroje se tím nepotvrzuje.'
            meta.pop('fixed_shear_type',None)
        state=row.get('snapshot',{}).get('completion',{}).get('state')
        if state=='pending':meta['errors']=list(dict.fromkeys([PENDING+': chybí potvrzené katalogové nebo ručně zadané únosnosti.',*meta.get('errors',[])]))
        if state=='manual':meta['warnings']=list(dict.fromkeys([*meta.get('warnings',[]),'Parametry záměny byly ručně upřesněny.']))
        return meta
    sub.source_metadata=metadata
    previous_design=sub.design_targets
    @wraps(previous_design)
    def design(database,*,row,metadata,**kwargs):
        metadata=sub.source_metadata(row)
        if metadata.get('errors'):return [],list(metadata['errors'])
        typ=row.get('mapping',{}).get('source_overrides',{}).get('target_type')
        if typ:
            original_database=database
            class RestrictedDatabase:
                def __getattr__(self,name):return getattr(original_database,name)
                def proposal_candidates(self,connection_type,*args,**kw):
                    if connection_type!=typ:return [],'',{}
                    rows,error,info=original_database.proposal_candidates(connection_type,*args,**kw)
                    return [c for c in rows if c.connection_type==typ],error,info
            database=RestrictedDatabase()
        targets, warnings = previous_design(database,row=row,metadata=metadata,**kwargs)
        if typ:
            targets = [target for target in targets if target.get('connection_type') == typ]
            if not targets:
                warnings = list(warnings) + [f'Pro zvolený typ HIT {typ} nebyla nalezena vyhovující varianta.']
        return targets, warnings
    sub.design_targets=design
    calculate=sub.calculation
    @wraps(calculate)
    def calculation(candidate,target_actions,source_totals,metadata):
        text=calculate(candidate,target_actions,source_totals,metadata)
        if metadata.get('cover_resolution')=='manual':
            text=text.replace('cnom None→','cnom zdroj neuvedeno →')
            text+=' | '+metadata['cover_resolution_note']
        return text
    sub.calculation=calculation
    cls.edit_substitution_source=edit_source
    previous_row=cls._row_payload;previous_payload=cls._payload
    @wraps(previous_row)
    def row_payload(owner,row,order):
        payload,status=previous_row(owner,row,order)
        completion=row.get('snapshot',{}).get('completion') or {}
        if completion.get('state')=='pending':
            payload['status']=PENDING;payload['note']=' • '.join(filter(None,(payload.get('note'),completion.get('message'))));status='missing'
        elif completion.get('state')=='manual':payload['status']='Ručně upraveno';status='changed'
        return payload,status
    @wraps(previous_payload)
    def payload(owner,row):
        result,status=previous_payload(owner,row)
        if row.get('snapshot',{}).get('completion',{}).get('state')=='pending':
            result['status']=PENDING;status='review'
        return result,status
    cls._row_payload=row_payload;cls._payload=payload
    previous_body=cls._build_body
    @wraps(previous_body)
    def body(owner):
        previous_body(owner)
        compact_layout(owner)
    cls._build_body=body
    # Re-evaluate only when the visible manufacturer/design panel changes.
    import thermal_design_ui,peikko_workspace
    for name in ('show_common','show_legacy'):
        original=getattr(thermal_design_ui.SharedDesign,name)
        def wrapped(panel,*args,_original=original,**kwargs):
            result=_original(panel,*args,**kwargs);compact_layout(panel.owner);return result
        setattr(thermal_design_ui.SharedDesign,name,wrapped)
    switch=peikko_workspace._switch
    def switch_panel(owner,mode):
        result=switch(owner,mode);compact_layout(owner);return result
    peikko_workspace._switch=switch_panel
