"""Regression for missing current dowel VRd plus all workspace navigation."""
from copy import deepcopy
import json
from pathlib import Path
import time


def pump(app, seconds=.15):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        app.update();time.sleep(.01)


def exercise(app):
    from tkinter import ttk
    import shear_dowels_ui as ui
    import shear_workflow_236 as workflow
    from verify_stacon_316 import TEXT
    from shear_capacity_317 import enrich
    from workspace_controls_317 import walk,visible
    from action_payload import serialize_action,load_action_record,action_store
    from pdf_data_304 import shear_decoder_rows
    # Exercise acceptance into the actual owner table, not only the import preview.
    def accept_dialog():
        dialog=app._hsd_last_import_dialog
        dialog.text.insert('1.0',TEXT)
        dialog.use_geometry.set(True);dialog._analyze();dialog.insert_button.invoke()
    values=app.shear_decoder_vars
    values['slab'].set('240');values['gap'].set('20');values['concrete'].set('C25/30')
    app.shear_decoder_rows=[]
    app.after(100,accept_dialog);app.open_shear_decoder_schedule();pump(app)
    assert [r['quantity'] for r in app.shear_decoder_rows]==[1,9]
    tree=app.shear_decoder_tree
    assert tree.set('0','vrd')=='45,1', tree.item('0','values')
    assert tree.set('1','vrd')=='33,5', tree.item('1','values')
    assert 'Stacon' in tree.set('1','source')
    assert app.shear_decoder_rows[1]['vrd']==33.5
    assert not app.hsd_catalog_choice.winfo_manager()
    modern=deepcopy(app.shear_decoder_rows[1])
    for changes,word in [({'geometry_confirmed':False},'Doplňte'),({'slab_mm':100},'nelze'),({'gap_mm':100},'nelze'),({'concrete':'C12/15'},'C20/25')]:
        row=dict(modern,**changes);enrich(row)
        assert row['vrd'] is None and not row.get('catalog_capacity'),row
        assert word.lower() in row['note'].lower(),row
    sld=dict(modern,designation='Schöck Stacon SLD 220');sld.pop('cover_mm',None);enrich(sld)
    assert sld['vrd'] is None and 'cnom' in sld['note']
    sld['cover_mm']=30;enrich(sld)
    assert sld['vrd'] and 'KONTROLA DESKY' in sld['note'],sld
    report=shear_decoder_rows(app)[1]['decoder_data']
    assert report['vrd']==33.5 and 'Stacon' in report['source']
    app.copy_shear_table('decoder');assert '33,5' in app.clipboard_get()
    # Existing saved rows missing computed metadata are repaired on load.
    payload=serialize_action(app)
    for row in payload['shear_dowels']['decoder']:
        for key in ('vrd','source','note','catalog_capacity','current_catalogue'):row.pop(key,None)
    store=action_store(app)
    record=store.save(payload=payload,action_name='TEST_ONLY 317 Stacon actual table')
    # Store API returns the action id.
    (Path(app.settings_path).parent/'TEST_ONLY_saved317.json').write_text(json.dumps({'action_id':record['id']}),encoding='utf-8')
    saved=store.load(record['id'])
    load_action_record(app,saved);pump(app)
    assert app.shear_decoder_tree.set('1','vrd')=='33,5'
    assert [r['quantity'] for r in app.shear_decoder_rows]==[1,9]
    # Actual transfer and add button must use the same source capacity.
    tree.selection_set('1');pump(app);app.shear_decoder_to_substitution();pump(app)
    assert app.shear_substitution_vars['source'].get()==modern['designation']
    app.shear_target_manufacturer_var.set('Ancon')
    app.add_shear_substitution_row();pump(app)
    sub=app.shear_substitution_rows[-1]
    assert sub['source']['vrd']==33.5 and sub['quantity']==9,sub
    # All main tabs, both thermal manufacturers, and the three restored HIT groups.
    checked=[]
    for width in (1280,1120):
        app.geometry(f'{width}x850');pump(app)
        for domain,tab in app.product_domain_tab_by_id.items():
            if domain not in ('thermal_breaks','shear_dowels'):continue
            app.product_domain_notebook.select(tab)
            nb=app.main_notebook if domain=='thermal_breaks' else app.shear_notebook
            for page in nb.tabs():
                if nb.tab(page,'state')!='normal':continue
                nb.select(page);pump(app)
                for toolbar in app._flow_toolbars_317:
                    if not visible(toolbar.frame):continue
                    right=app.winfo_rootx()+app.winfo_width()
                    for widget in toolbar.items:
                        if visible(widget):assert widget.winfo_rootx()+widget.winfo_width()<=right+2,(nb.tab(page,'text'),widget,widget.winfo_rootx(),widget.winfo_width(),right)
                checked.append(f'{domain}/{nb.tab(page,"text")}@{width}')
    app.product_domain_notebook.select(app.product_domain_tab_by_id['thermal_breaks'])
    app.main_notebook.select(app.hit_tab)
    for brand in ('Peikko','Leviat'):
        app.design_manufacturer_var.set(brand);app.shared_thermal_design.switch();pump(app)
        checked.append('thermal design '+brand)
    before=(len(app.hit_rows),len(app.aux_rows),len(app.wt_rows))
    for group in ('standard','aux','wt','standard'):
        app.shared_thermal_design.show_hit_group(group);pump(app)
    assert before==(len(app.hit_rows),len(app.aux_rows),len(app.wt_rows))
    app.product_domain_notebook.select(app.product_domain_tab_by_id['shear_dowels']);app.shear_notebook.select(0);pump(app)
    filt=app.shear_decoder_filter_var
    filt.set('S002');app.refresh_shear_tables();pump(app)
    entry=next(w for w in walk(app) if isinstance(w,ttk.Entry) and str(w.cget('textvariable'))==str(filt) and visible(w))
    assert entry.cget('style')=='ActiveFilter.TEntry'
    filt.set('');app.refresh_shear_tables();pump(app)
    assert entry.cget('style')!='ActiveFilter.TEntry'
    assert app.shear_decoder_tree.set('1','vrd')=='33,5'
    # All empty-selection actions are disabled, then recover with selection.
    app.shear_decoder_tree.selection_remove(*app.shear_decoder_tree.selection());pump(app)
    controls=next(buttons for table,buttons,_ in app._selection_actions_317 if table is app.shear_decoder_tree)
    assert controls and all(b.instate(['disabled']) for b in controls)
    app.shear_decoder_tree.selection_set('1');pump(app)
    assert any(not b.instate(['disabled']) for b in controls)
    # Different SLD cover values survive row transfer and bulk synchronization.
    sld.update(name='S003',quantity=2,cover_mm=20,geometry_confirmed=True)
    enrich(sld);app.shear_decoder_rows.append(sld);app.refresh_shear_tables();pump(app)
    app.shear_decoder_tree.selection_set('2');app.shear_decoder_to_substitution()
    assert app.shear_substitution_vars['cover'].get()=='20'
    app.sync_shear_substitutions_from_decoder();pump(app)
    synced=next(r for r in app.shear_substitution_rows if r.get('origin')=='decoder' and r['name']=='S003')
    assert synced['cover_mm']==20 and synced['source']['vrd']==sld['vrd'],synced
    app.shear_decoder_rows=app.shear_decoder_rows[:2]
    app.shear_substitution_rows=[r for r in app.shear_substitution_rows if r['name']!='S003']
    app.refresh_shear_tables();pump(app)
    return dict(vrd=[45.1,33.5],quantities=[1,9],saved_action=True,substitution_source=33.5,tabs=checked)


def reopen_saved(app):
    from action_payload import action_store,load_action_record
    saved=json.loads((Path(app.settings_path).parent/'TEST_ONLY_saved317.json').read_text(encoding='utf-8'))
    load_action_record(app,action_store(app).load(saved['action_id']));pump(app)
    assert [r['quantity'] for r in app.shear_decoder_rows]==[1,9]
    assert app.shear_decoder_tree.set('0','vrd')=='45,1'
    assert app.shear_decoder_tree.set('1','vrd')=='33,5'
    assert 'Stacon' in app.shear_decoder_tree.set('1','source')
