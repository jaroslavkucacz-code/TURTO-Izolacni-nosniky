from __future__ import annotations

"""Peikko inside the SAME decoder, design and substitution workspace.

Adapters are installed before Tk widgets are built. Manufacturer changes hide
only the existing manufacturer's controls, not its data. Shared project rows
and platform selection use the existing central AKCE serialization.
"""
from dataclasses import replace
from functools import wraps
from typing import Any
import tkinter as tk
from tkinter import ttk, messagebox

from peikko_thermal_breaks import (
    decode_peikko, normalize_bulk_text, is_peikko, format_decode, proposal_models,
    compatible_models, ROLE_LABELS, ROLE_MOMENT_SHEAR, DESIGN_STATUS,
)
from peikko_catalog import catalog_class, CATALOG_ID, BLOCK_REASON, make_result

WORKSPACE_VERSION = "2.2.30"


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _is_source(row):
    return (row.get("selection", {}).get("catalog_id") == CATALOG_ID
            or is_peikko(row.get("snapshot", {}).get("designation", "")))


def _install_bulk():
    import bulk_import_engine as engine
    import bulk_import
    original = engine.analyze_bulk_text_progressive
    @wraps(original)
    def analyze(database, text, **kwargs):
        return original(database, normalize_bulk_text(text), **kwargs)
    engine.analyze_bulk_text_progressive = analyze
    bulk_import.analyze_bulk_text_progressive = analyze
    classify = engine._classify_bulk_item
    @wraps(classify)
    def classify_item(database, item, **kwargs):
        if not is_peikko(item.designation):
            return classify(database, item, **kwargs)
        try:
            item.result = database.resolve_designation(item.designation,
                preferred_concrete=kwargs.get("preferred_concrete"))
            d = decode_peikko(item.designation)
            item.status = "exact"  # exact syntax, NOT confirmed structural capacity
            item.message = DESIGN_STATUS
            if d.position_reference:
                item.note = " | ".join(x for x in (item.note, "Reference: " + d.position_reference) if x)
        except ValueError as exc:
            item.result = None
            item.status = "error"
            item.message = str(exc)
    engine._classify_bulk_item = classify_item
    # Avoid destructive Egcobox-specific suffix preprocessing for Peikko.
    preprocess = engine.preprocess_bulk_designation
    def peikko_preprocess(designation, note=""):
        return (str(designation).strip(), note) if is_peikko(designation) else preprocess(designation, note)
    engine.preprocess_bulk_designation = peikko_preprocess
    import project_ui_base
    project_ui_base.preprocess_bulk_designation = peikko_preprocess


def _install_guards():
    import substitution_workspace as sw
    original = sw.design_targets
    @wraps(original)
    def design_targets(database, *, row, metadata, **kwargs):
        if _is_source(row):
            return [], [BLOCK_REASON]
        return original(database, row=row, metadata=metadata, **kwargs)
    sw.design_targets = design_targets
    previous_meta = sw.source_metadata
    @wraps(previous_meta)
    def metadata(row):
        result = previous_meta(row)
        if _is_source(row):
            result["substitution_policy"] = "manual"
            result["substitution_note"] = BLOCK_REASON
            result["errors"] = [BLOCK_REASON]
            result["warnings"] = list(dict.fromkeys([*result.get("warnings", []),
                "Ds/Dt, S11, B2 a OQ jsou zachovány; nepředstavují ověřené návrhové parametry."]))
        return result
    sw.source_metadata = metadata


def _selected_source(owner):
    selected = list(owner.project_tree.selection()) if hasattr(owner, "project_tree") else []
    for row in getattr(getattr(owner, "project", None), "rows", []):
        if row.get("id") in selected:
            return row
    return None


def _set_text(widget, text):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")


def _build_panel(owner, parent, mode):
    from peikko_technical import (reference, format_reference, compare_loads,
        format_comparison, preselect, data, DISCLAIMER)
    from tkinter import filedialog
    from peikko_documents import open_source_async
    panel = ttk.Frame(parent, style='App.TFrame', padding=8)
    panel.columnconfigure(0, weight=1, minsize=590)
    panel.columnconfigure(1, weight=1, minsize=380)
    panel.rowconfigure(1, weight=1)
    defaults = dict(family='EBEA', role=ROLE_LABELS[ROLE_MOMENT_SHEAR], sw='80', designation='',
        model='100', D='', length='1000', material='RS', s11='', moment='0', shear='0', axial='0',
        basis='Na jeden prvek', width='', candidate='')
    values = {key: tk.StringVar(master=owner, value=value) for key, value in defaults.items()}
    values['geometry'] = tk.BooleanVar(master=owner, value=False)
    panel._peikko_values = values
    candidates = []
    muted = [False]
    # The legacy window can leave only 350 px to the workspace. Scroll INPUTS,
    # not the complete panel: the numerical result and all action buttons remain visible.
    left=ttk.Frame(panel,style='App.TFrame');left.grid(row=1,column=0,sticky='nsew',padx=(0,8))
    left.columnconfigure(0,weight=1);left.rowconfigure(0,weight=1)
    canvas=tk.Canvas(left,highlightthickness=0,bg=owner.colors['bg'],width=565,height=160)
    canvas.grid(row=0,column=0,sticky='nsew')
    form_scroll=ttk.Scrollbar(left,orient='vertical',command=canvas.yview)
    form_scroll.grid(row=0,column=1,sticky='ns');canvas.configure(yscrollcommand=form_scroll.set)
    form=ttk.Frame(canvas,style='App.TFrame',padding=(0,0,5,5))
    ttk.Label(form, text='Peikko – katalogová data a tabulkové porovnání',
        font=('Calibri', 11, 'bold')).pack(anchor='w', pady=(0, 6))
    window=canvas.create_window(0,0,window=form,anchor='nw')
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
    form.bind('<Configure>',lambda _e:canvas.configure(scrollregion=canvas.bbox('all')))
    right=ttk.Frame(panel,style='App.TFrame');right.grid(row=1,column=1,sticky='nsew')
    right.columnconfigure(0,weight=1);right.rowconfigure(1,weight=1)
    def label_entry(parent, label, key, width=9, choices=None):
        ttk.Label(parent, text=label).pack(side='left', padx=(0,4))
        cls=ttk.Combobox if choices else ttk.Entry
        extra=dict(values=choices,state='readonly') if choices else {}
        widget=cls(parent,textvariable=values[key],width=width,**extra)
        widget.pack(side='left',padx=(0,8));return widget
    def line(parent=form):
        row=ttk.Frame(parent,style='App.TFrame');row.pack(fill='x',pady=3);return row
    selectors=line()
    family=label_entry(selectors,'Řada:','family',7,('EBEA','TEBEA'))
    label_entry(selectors,'Funkce:','role',18,tuple(ROLE_LABELS.values()))
    sw=label_entry(selectors,'ISO:','sw',5,('80','120'))
    ttk.Label(form,text='Úplné označení (má přednost před volbami modelu):').pack(anchor='w',pady=(5,0))
    entry=ttk.Entry(form,textvariable=values['designation'],font=('Calibri',10))
    entry.pack(fill='x',pady=3)
    ttk.Label(form,text='STANDARDNÍ TABULKOVÁ KONFIGURACE',font=('Calibri',10,'bold')).pack(anchor='w',pady=(8,2))
    dimensions=line()
    label_entry(dimensions,'Model:','model',7,('100','E-100','700'))
    label_entry(dimensions,'D [mm]:','D',6)
    label_entry(dimensions,'L [mm]:','length',7)
    dline=line()
    mat=label_entry(dline,'Provedení:','material',6,('RS','VE1','VE2'))
    label_entry(dline,'S11 [mm]:','s11',6)
    style=ttk.Style(owner)
    # The application-wide button padding consumes two tall rows on Windows.
    # Keep these contextual actions compact, without changing other workspaces.
    style.configure('Peikko.TButton', font=('Calibri', 10), padding=(8, 4))
    style.configure('Peikko.TCheckbutton',background=owner.colors['bg'],foreground=owner.colors['text'],font=('Calibri',10))
    ttk.Checkbutton(form,variable=values['geometry'],style='Peikko.TCheckbutton',
        text='Potvrzuji standardní geometrii, výztuž a krytí.').pack(anchor='w',pady=3)
    ttk.Label(form,text='D není automaticky Ds/Dt. Krytí nahoře/dole: 100 = 30/25; E-100 = 45/30; 700 = 30/30 mm. '
        'Model, L, provedení a S11 zde slouží pro předvýběr bez úplného označení.',wraplength=540).pack(anchor='w')
    ttk.Label(form,text='NÁVRHOVÉ ÚČINKY',font=('Calibri',10,'bold')).pack(anchor='w',pady=(8,2))
    loads=line()
    for label,key in [('MEd:','moment'),('VEd:','shear'),('NEd:','axial')]:label_entry(loads,label,key,7)
    units=line()
    basis=label_entry(units,'Jednotky:','basis',16,('Na jeden prvek','Na metr spoje'))
    width=label_entry(units,'Zatěž. šířka [mm]:','width',7);width.configure(state='disabled')
    ttk.Label(form,text='M [kNm], V/N [kN]; na metr: kNm/m a kN/m. 100/E-100: záporné MEd. '
        'Nenulové NEd blokováno. Zatěžovací šířka se neodvozuje z L.',wraplength=540).pack(anchor='w')
    picker=ttk.Combobox(right,textvariable=values['candidate'],state='disabled',width=38)
    picker.grid(row=0,column=0,columnspan=2,sticky='ew',pady=(0,5))
    output=tk.Text(right,font=('Calibri',10),wrap='word',height=8,width=35,relief='flat',
        bg=owner.colors['panel'],fg=owner.colors['text'],padx=10,pady=8)
    output.grid(row=1,column=0,sticky='nsew')
    scroll=ttk.Scrollbar(right,command=output.yview);scroll.grid(row=1,column=1,sticky='ns')
    output.configure(yscrollcommand=scroll.set)
    buttons=ttk.Frame(panel,style='App.TFrame');buttons.grid(row=2,column=0,sticky='ew',pady=(6,3))
    actions=ttk.Frame(panel,style='App.TFrame');actions.grid(row=3,column=0,sticky='ew')
    exports=ttk.Frame(panel,style='App.TFrame');exports.grid(row=2,column=1,rowspan=2,sticky='ew')
    # Mouse wheel scroll is local to the form; combobox wheel keeps its native behavior.
    def wheel(event):
        if getattr(event,'num',None)==4:delta=-1
        elif getattr(event,'num',None)==5:delta=1
        else:delta=-1 if event.delta>0 else 1
        canvas.yview_scroll(delta*3,'units');return 'break'
    for widget in _walk(form):
        if not isinstance(widget,ttk.Combobox):
            for event in ('<MouseWheel>','<Button-4>','<Button-5>'):widget.bind(event,wheel,add='+')
    panel._peikko_form_canvas=canvas
    panel._peikko_action_frames=(buttons,actions,exports)
    _set_text(output, 'Zadejte označení nebo převezměte řádek z Dekodéru.\n'
        'Pro tabulkové porovnání je nutné výslovné D, beton akce a potvrzení standardní geometrie.\n'+DISCLAIMER)
    def designation():
        text = values['designation'].get().strip()
        d = decode_peikko(text)
        if d is None: raise ValueError('Zadejte konkrétní označení EBEA/TEBEA.')
        # Persist an explicitly provided D, never infer it from Ds/Dt.
        if values['D'].get().strip() and d.standard_d_mm is None and d.family == 'EBEA':
            from peikko_technical import integer
            text += ' D' + str(integer(values['D'].get(), 'D'))
        return text
    def report():
        return reference(designation(), standard_d_mm=values['D'].get(),
            concrete=owner.project_concrete_var.get(), geometry_confirmed=values['geometry'].get())
    def load_args():
        return dict(moment=values['moment'].get(), shear=values['shear'].get(), axial=values['axial'].get(),
            basis='per_metre' if values['basis'].get()=='Na metr spoje' else 'element',
            tributary_width_mm=values['width'].get())
    def show():
        try:
            if values['designation'].get().strip():
                r = report()
                _set_text(output, format_reference(r))
            elif values['family'].get()=='TEBEA':
                _set_text(output, format_reference(reference('TEBEA CM-V')))
            else:
                role = next(k for k, v in ROLE_LABELS.items() if v==values['role'].get())
                models = proposal_models(family='EBEA', role=role, insulation_mm=int(values['sw'].get()))
                _set_text(output, 'Funkční přehled (bez numerického výběru).\n'
                    'Ověřené tabulky: 100, E-100, 700. Vyplňte standardní D, zatížení a použijte Tabulkový předvýběr.\n\n'+
                    '\n'.join(s.canonical+' – '+s.description for s in models))
        except (ValueError, StopIteration) as exc: _set_text(output, str(exc))
    def check():
        try:
            r=report(); text=format_reference(r)
            try: text=format_comparison(compare_loads(r, **load_args()))+'\n\n'+text
            except ValueError as exc: text+='\n\nPOROVNÁNÍ NEPROVEDENO: '+str(exc)
            _set_text(output, text)
        except ValueError as exc: _set_text(output, str(exc))
    def select_tables():
        if values['designation'].get().strip():
            # Fully specified product: never broaden silently to unrelated types.
            check(); return
        try:
            if values['family'].get()!='EBEA':
                raise ValueError('TEBEA: data součástí nelze použít jako únosnost celého nosníku. K dispozici je přehled ETA.')
            role = next(k for k, v in ROLE_LABELS.items() if v==values['role'].get())
            if role != ROLE_MOMENT_SHEAR:
                raise ValueError('Tabulkový předvýběr v této verzi pokrývá pouze řady 100/E-100/700 (moment + smyk).')
            rows=preselect(model=values['model'].get(), standard_d_mm=values['D'].get(),
                insulation_mm=values['sw'].get(), length_mm=values['length'].get(), material=values['material'].get(),
                concrete=owner.project_concrete_var.get(), s11_mm=values['s11'].get(),
                geometry_confirmed=values['geometry'].get(), **load_args())
            candidates[:]=rows
            picker.configure(values=tuple(r['designation'] for r in rows), state='readonly' if rows else 'disabled')
            values['candidate'].set('Vyberte tabulkovou konfiguraci ('+str(len(rows))+')' if rows else '')
            lines=['Tabulkový předvýběr – '+str(len(rows))+' konfigurací v rámci samostatných mezí M/V.', DISCLAIMER]
            for item in rows:
                lines += ['\n'+item['designation'], format_comparison(item['comparison'])]
            if not rows: lines.append('Žádná přesná tabulková sestava nesplňuje zadané parametry a účinky.')
            _set_text(output, '\n'.join(lines))
        except (ValueError, StopIteration) as exc: _set_text(output, str(exc))
    def choose(_event=None):
        index=picker.current()
        if index<0 or index>=len(candidates): return
        muted[0]=True
        try:
            values['designation'].set(candidates[index]['designation'])
            values['geometry'].set(False)
        finally: muted[0]=False
        show()
    picker.bind('<<ComboboxSelected>>', choose)
    def from_decoder():
        row=_selected_source(owner)
        if row is None:
            _set_text(output, 'Nejdříve označte řádek ve společném Dekodéru.');return
        text=row.get('snapshot',{}).get('designation','')
        d=decode_peikko(text)
        if d is None:
            values['designation'].set('')
            _set_text(output, 'Zdroj: '+text+'\nMezivýrobní záměna není automaticky potvrzena.');return
        values['designation'].set(text)
        values['D'].set(str(d.standard_d_mm or ''))
        values['geometry'].set(False)
        show()
    def add_to_decoder():
        try:
            text=designation(); r=report()  # D / concrete conflict checked before storing
            from project_model import create_project_row
            result=owner.database.resolve_designation(text, preferred_concrete=owner.project_concrete_var.get())
            row=create_project_row(result, position=owner.project.next_position(), source_text=text,
                note='Peikko – katalogová reference; nikoli potvrzené statické posouzení nebo záměna.')
            owner.project.add(row);owner.mark_project_dirty()
            owner.refresh_project_tree(select_ids=[row['id']]);owner.main_notebook.select(owner.project_tab)
        except ValueError as exc: messagebox.showwarning('Peikko', str(exc), parent=owner)
    def export():
        path=filedialog.asksaveasfilename(parent=owner, title='Uložit zobrazený přehled Peikko',
            defaultextension='.txt', filetypes=[('Text UTF-8','*.txt')], initialfile='Peikko_katalogove_porovnani.txt')
        if not path:return
        try:
            from pathlib import Path
            Path(path).write_text(output.get('1.0','end-1c')+'\n\n'+DISCLAIMER+'\n', encoding='utf-8-sig')
        except OSError as exc: messagebox.showerror('Peikko', str(exc), parent=owner)
    pdf_button = None
    def source_pdf():
        try: d=decode_peikko(values['designation'].get())
        except ValueError as exc:
            messagebox.showwarning('Peikko',str(exc),parent=owner);return
        family_name=d.family if d else values['family'].get()
        source=data()['sources']['tebea_eta01' if family_name=='TEBEA' else 'ebea_004']
        open_source_async(owner, pdf_button, source)
    for label,callback in [('Katalogová data',show),('Porovnat M/V',check),('Tabulkový předvýběr',select_tables)]:
        ttk.Button(buttons, text=label, command=callback, style='Peikko.TButton').pack(side='left', padx=(0,7))
    for label,callback in [('Převzít z Dekodéru',from_decoder),('Uložit do Dekodéru',add_to_decoder)]:
        ttk.Button(actions, text=label, command=callback, style='Peikko.TButton').pack(side='left', padx=(0,7))
    ttk.Button(exports,text='Uložit přehled TXT',command=export,style='Peikko.TButton').pack(side='left',padx=(0,7))
    pdf_button=ttk.Button(exports, text='Zdrojové PDF (lokální)', command=source_pdf, style='Peikko.TButton')
    pdf_button.pack(side='left')
    def clear_candidates(*_):
        if muted[0]:return
        candidates.clear();picker.configure(values=(),state='disabled');values['candidate'].set('')
        _set_text(output, 'Zadání změněno. Znovu zobrazte katalogová data / tabulkové porovnání.\n'+DISCLAIMER)
    def geometry_changed(*_):
        if not muted[0]: values['geometry'].set(False)
        clear_candidates()
    for key in ('designation','D','model','sw','length','material','s11','family'):
        values[key].trace_add('write', geometry_changed)
    for key in ('moment','shear','axial','width','geometry','role'):
        values[key].trace_add('write', clear_candidates)
    owner.project_concrete_var.trace_add('write', clear_candidates)
    def units_changed(*_):
        width.configure(state='normal' if values['basis'].get()=='Na metr spoje' else 'disabled');clear_candidates()
    values['basis'].trace_add('write', units_changed)
    def family_changed(*_):
        sw.configure(values=('120',) if values['family'].get()=='TEBEA' else ('80','120'))
        if values['family'].get()=='TEBEA': values['sw'].set('120')
    family.bind('<<ComboboxSelected>>', family_changed)
    def model_changed(*_):
        choices=('VE1','VE2') if values['model'].get()=='700' else ('RS','VE1','VE2')
        mat.configure(values=choices)
        if values['material'].get() not in choices: values['material'].set(choices[0])
    values['model'].trace_add('write', model_changed)
    entry.bind('<Return>', lambda _e: show())
    panel._peikko_output=output;panel._peikko_show=show;panel._peikko_check=check
    panel._peikko_preselect=select_tables;panel._peikko_candidates=candidates;panel._peikko_picker=picker
    panel._peikko_add=add_to_decoder;panel._peikko_choose=choose;panel._peikko_from_decoder=from_decoder
    return panel

def _install_manufacturers(base):
    import platform_registry as registry
    import platform_workspace_200 as platform
    if not any(m.id == "peikko" for m in registry.domain("thermal_breaks").manufacturers):
        spec = registry.ManufacturerSpec(id="peikko", label="Peikko", product_line="EBEA / TEBEA",
            catalog_label="Katalogová data a tabulkové porovnání",
            design_adapter="peikko_preselection", substitution_adapter="peikko_preselection", enabled=True)
        registry.DOMAINS = tuple(replace(d, manufacturers=d.manufacturers + (spec,))
            if d.id == "thermal_breaks" else d for d in registry.DOMAINS)
    previous = platform._manufacturer_changed
    def manufacturer_changed(owner, mode):
        variable = owner.design_manufacturer_var if mode == "design" else owner.substitution_manufacturer_var
        if variable.get() != "Peikko":
            previous(owner, mode)
        elif not getattr(owner, "_action_loading", False):
            owner.mark_project_dirty()
        _switch(owner, mode)
    platform._manufacturer_changed = manufacturer_changed


def _switch(owner, mode):
    state = getattr(owner, "_peikko_shared_panels", {}).get(mode)
    if not state:
        return
    parent, panel, original, controls = state
    variable = owner.design_manufacturer_var if mode == "design" else owner.substitution_manufacturer_var
    active = variable.get() == "Peikko"
    for child in original + controls:
        if active:
            child.grid_remove()
        else:
            child.grid()
    if active:
        panel.grid(row=1, column=0, rowspan=3, sticky="nsew")
    else:
        panel.grid_remove()
    if mode == "design":
        owner.design_catalog_var.set("Katalogové tabulky – ne úplné posouzení" if active else "HALFEN / Leviat HIT 20.2-EN 2023")


def install(base_module: Any) -> None:
    cls = base_module.ThermalConnectorApp
    if getattr(cls, "_peikko_shared_229", False):
        return
    base_module.CatalogDatabase = catalog_class(base_module.CatalogDatabase)
    _install_bulk()
    _install_guards()
    _install_manufacturers(base_module)
    previous_payload = cls._row_payload
    def row_payload(self, row, order):
        payload, status = previous_payload(self, row, order)
        if _is_source(row):
            payload["status"] = "K ověření" if status == "ok" else payload["status"]
            payload["moment_class"] = "—"
            payload["shear_class"] = "—"
            payload["moment"] = "neověřeno"
            payload["shear"] = "neověřeno"
            payload["extra"] = DESIGN_STATUS
        return payload, status
    cls._row_payload = row_payload
    previous = cls._build_body
    def body(self):
        previous(self)
        self._peikko_shared_panels = {}
        for mode, parent in (("design", self.hit_tab), ("substitution", self.substitution_tab)):
            original, controls = [], []
            for child in parent.winfo_children():
                info = child.grid_info()
                if not info:
                    continue
                if int(info.get("row", 0)) > 0:
                    original.append(child)
                else:
                    for widget in child.winfo_children():
                        wi = widget.grid_info()
                        if wi and int(wi.get("column", 0)) >= (4 if mode == "design" else 2):
                            controls.append(widget)
            panel = _build_panel(self, parent, mode)
            self._peikko_shared_panels[mode] = (parent, panel, original, controls)
            var = self.design_manufacturer_var if mode == "design" else self.substitution_manufacturer_var
            var.trace_add("write", lambda *_args, m=mode: _switch(self, m))
            _switch(self, mode)
        # Row labels retain generic workflow names; NO additional notebook tab.
    cls._build_body = body
    cls.decode_peikko_product = lambda _self, text: decode_peikko(text)
    cls.peikko_substitution_candidates = lambda _self, text: compatible_models(text)
    cls.peikko_design_candidates = lambda _self, **kwargs: proposal_models(**kwargs)
    cls._peikko_shared_229 = True


def selftest():
    assert WORKSPACE_VERSION == "2.2.30"
    assert decode_peikko("EBEA-ZS Ds200 Dt200 SW80 L1000 REI120") is not None
