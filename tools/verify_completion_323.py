"""Real catalogue, bulk dialog, unresolved persistence and 330 mm regression."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import math,time


def exercise(app):
    import bulk_import,bulk_import_engine as bulk,source_completion as completion
    import project_model as pm,substitution_workspace as sub,action_payload
    import hit_core,hit_units_310,hit_schedule
    from tkinter import ttk
    from workspace_controls_317 import walk
    from verify_workflow_317 import pump
    # Read the original SHA-verified manufacturer table, never invented values.
    import base64,gzip,json,zvx_tables_303,pdfplumber
    from verify_zvx_303 import acquire_pdf
    source_pdf=Path(app.settings_path).parent/'TEST_ONLY_annex3_323.pdf'
    acquire_pdf(source_pdf,zvx_tables_303.SOURCE_URL,zvx_tables_303.SOURCE_SHA256)
    with pdfplumber.open(source_pdf) as pdf:records=zvx_tables_303.parse_zvx_pages(pdf)
    assert zvx_tables_303.fingerprint(records)==zvx_tables_303.COMPLETE_SHA256
    database_file=Path(app.settings_path).parent/'TEST_ONLY_annex3_323.b64'
    database_file.write_bytes(base64.b64encode(gzip.compress(json.dumps(dict(schema_version=4,
        source_document='CONF-DOP_HIT-HP/SP-07-23',source_sha256=zvx_tables_303.SOURCE_SHA256,
        zvx_records=records)).encode())))
    app.hit_db=hit_core.HitDatabase(database_file)
    text=(Path(__file__).parent/'fixtures/schoeck_format_321.txt').read_text(encoding='utf-8')
    text+='\nNEZNAMY PRVEK H200\t7'
    items,_=bulk.analyze_bulk_text(app.database,text,preferred_concrete='C25/30')
    assert len(items)==14
    app.project.rows=[]
    def operate(dialog):
        assert isinstance(dialog,bulk_import.BulkImportDialog)
        dialog.items=items;dialog._refresh_review_tree()
        assert not dialog.insert_button.instate(['disabled'])
        dialog._insert_ready()
    with patch.object(app,'wait_window',side_effect=operate):app.bulk_paste_project_rows()
    assert len(app.project.rows)==14
    assert sum(r['quantity'] for r in app.project.rows)==2903
    assert [r['source_text'] for r in app.project.rows]==[i.source_designation or i.designation or i.raw for i in items]
    pending=[r for r in app.project.rows if r['snapshot'].get('completion',{}).get('state')=='pending']
    assert len(pending)==7
    app.design_substitutions(False)
    assert all(not r['mapping']['targets'] for r in pending)
    row=app.project.rows[5]
    assert 'QP' in row['source_text'] and 'V1' in row['source_text']
    assert row['selection']['type_name']=='QP',row['selection']
    dialog=completion.CompletionDialog(app,row)
    assert dialog.matches and len(dialog.matches)==1
    dialog.tree.selection_set('0');dialog.choose()
    assert dialog.row['snapshot']['results'] and dialog.vars['length'].get()=='300'
    assert dialog.vars['source_cover'].get()==''
    dialog.vars['target_cover'].set('30');dialog.vars['target_type'].set('ZVX');dialog.save()
    assert dialog.result is not None
    row.clear();row.update(dialog.result)
    assert row['id']==app.project.rows[5]['id'] and row['quantity']==13
    assert sub.source_metadata(row)['source_cover_mm'] is None
    assert sub.source_metadata(row)['target_cover_mm']==30
    assert not sub.source_metadata(row)['errors'],sub.source_metadata(row)
    app.refresh_substitution_tree();app.sub_tree.selection_set(row['id']);app.design_substitutions(True)
    assert row['mapping']['targets'],row['mapping']
    assert sub.selected_target(row['mapping'])['length_mm']==330
    assert all(t['connection_type']=='ZVX' and t['length_mm'] in (250,330) for t in row['mapping']['targets'])
    assert all(math.isclose(t['v_capacity_element'],t['v_capacity']*t['length_mm']/1000) for t in row['mapping']['targets'])
    for t in row['mapping']['targets']:
        assert t['cover_mm']==30 and t['utilization']<=1
    # A partially recognised row is retained even when it is the sole row.
    unknown=completion.unresolved_row(dict(source_text='Neznámý výrobek',quantity=2,position='X01'))
    initial=completion.form_values(unknown);values=dict(initial,manufacturer='Vlastní',type_name='Smykový',
        height_mm='200',length='300',insulation='80',concrete_min='C25/30',compression='Bez ložisek',
        target_cover='30',target_type='ZVX',v_pos='30,9',basis='Na prvek')
    manual=completion.apply_manual(unknown,values,initial)
    assert manual['snapshot']['completion']['state']=='manual'
    assert sub.source_element_actions(manual)[0].v_pos==30.9
    assert sub.source_metadata(manual)['source_cover_mm'] is None
    assert sub.design_targets(app.hit_db,row=manual,metadata=sub.source_metadata(manual))[0]
    for invalid in ('nan','inf','-1','text'):
        try:completion.apply_manual(unknown,dict(values,v_pos=invalid),initial)
        except ValueError:pass
        else:raise AssertionError(invalid)
    partial=completion.apply_manual(unknown,dict(initial,height_mm='200'),initial)
    assert partial['snapshot']['completion']['state']=='pending'
    assert sub.source_metadata(partial)['errors']
    # Explicit manual target cover cannot make an incompatible ZVX pass.
    incompatible=deepcopy(manual);incompatible['mapping']['source_overrides']['target_cover_mm']=50
    assert not sub.design_targets(app.hit_db,row=incompatible,metadata=sub.source_metadata(incompatible))[0]
    # Catalogue parameter selector queries actual loaded records (no synthetic values).
    dialog=completion.CompletionDialog(app,unknown)
    family=next(label for label,f in dialog.family_by_label.items() if f['manufacturer']=='Schöck' and f['model']=='T' and f['type']=='QP' and f['generation']=='5.0')
    dialog.family_var.set(family);dialog.selectors()
    f=dialog.family_by_label[family]
    for i,key in enumerate(dialog.selector_keys):
        opts=dialog.selector_widgets[key].cget('values')
        assert opts,(key,f)
        dialog.selector_vars[key].set(opts[0]);dialog.selectors(i+1)
    dialog.query_selectors();assert len(dialog.matches)==1
    dialog.choose();assert dialog.row['snapshot']['results'];dialog.destroy()
    # SQLite round-trip keeps unresolved data, provenance and manual choices.
    app.project.add(manual);app.project.add(partial)
    before=deepcopy(app.project.rows)
    store=action_payload.action_store(app)
    saved=store.save(action_name='TEST_ONLY completion323',payload=action_payload.serialize_action(app))
    action_payload.load_action_record(app,store.load(saved['id']))
    assert app.project.rows==[pm.normalize_project_row(r) for r in before], [(a['position'],[k for k in a if a[k]!=b.get(k)]) for a,b in zip(app.project.rows,[pm.normalize_project_row(r) for r in before]) if a!=b]
    assert hit_units_310.LENGTHS[33]==330
    assert hit_schedule.required_length_codes('330',{33})=={33}
    assert sub._target_length_options(300)==[(33,330),(25,250)],sub._target_length_options(300)
    # Equal physical actions at 330 mm give identical utilization in both units.
    actions=hit_core.DirectionalActions(v_pos=30.9)
    per_m=hit_units_310.scaled_actions(actions,330)
    assert math.isclose(per_m.v_pos*.330,30.9)
    candidates,_,_=app.hit_db.proposal_candidates('ZVX','HP',200,30,'C25/30',per_m,{33})
    assert candidates and all(c.physical_length_mm==330 for c in candidates)
    legacy=deepcopy(row)
    legacy['mapping']['targets'][0]['length_mm']=333
    legacy['mapping']['substitution_acceptance']={'confirmed':True}
    migrated=pm.normalize_project_row(legacy)
    assert not migrated['mapping']['targets'] and not migrated['mapping']['substitution_acceptance']
    assert migrated['mapping']['source_overrides']['target_cover_mm']==30
    # An old direct-design input is migrated and exports the physical 330 mm.
    import hit_workspace,hit_export_ui,hit_pdf,hit_excel,openpyxl,action_payload_prev
    action_payload_prev._clear_hit_rows(app)
    app.hit_l033_var.set(True)
    direct=hit_workspace.HitInputRow(app,1,dict(name='TEST_ONLY 330',connection_type='ZVX',
        series='HP',height='200',cover='30',concrete='C25/30',required_length='333',
        quantity='1',ved_pos='30.9',load_basis='per_element'))
    app.hit_rows.append(direct);app.recalculate_hit_all();pump(app)
    assert direct.required_length.get()=='330'
    assert direct.selected_candidate is not None,direct.detail.get()
    assert direct.selected_candidate.physical_length_mm==330
    exports=hit_export_ui.collect_hit_rows(app)
    output=Path(app.settings_path).parent
    hit_pdf.write_hit_proposal_pdf(output/'TEST_ONLY_330.pdf',project_name='TEST_ONLY 330',rows=exports)
    with pdfplumber.open(output/'TEST_ONLY_330.pdf') as doc:
        text='\n'.join(page.extract_text() or '' for page in doc.pages)
        assert '330' in text and '333' not in text,text
    hit_excel.write_hit_request_xlsx(output/'TEST_ONLY_330.xlsx',action_name='TEST_ONLY 330',rows=exports,include_statics=True)
    book=openpyxl.load_workbook(output/'TEST_ONLY_330.xlsx',data_only=True)
    sheet_values=str([list(sheet.values) for sheet in book]);book.close()
    assert '330' in sheet_values and '333' not in sheet_values,sheet_values
    # Inspect actual rendered grid geometry at two sizes and after tab changes.
    app.deiconify();app.product_domain_notebook.select(app.product_domain_tab_by_id['thermal_breaks'])
    for width in (1250,1900):
        app.geometry(f'{width}x900+10+10');app.main_notebook.select(app.hit_tab)
        app.shared_thermal_design.show_legacy()
        app.shared_thermal_design.show_hit_group('standard')
        pump(app)
        checks=[w for w in walk(app.hit_tab) if isinstance(w,ttk.Checkbutton) and w.cget('text') in ('1000 mm','500 mm','330 mm','250 mm')]
        assert len(checks)==4
        assert all(w.winfo_ismapped() for w in checks)
        assert len({str(w.master) for w in checks})==1
        checks.sort(key=lambda w:w.winfo_x())
        assert all(b.winfo_x()-a.winfo_x()-a.winfo_width()<20 for a,b in zip(checks,checks[1:]))
        app.main_notebook.select(app.substitution_tab);pump(app)
        parent=app.sub_tree.master
        while parent.master is not app.substitution_tab:parent=parent.master
        assert parent.winfo_y()<80,(width,parent.winfo_y())
    action_payload_prev._clear_hit_rows(app)
    return dict(imported=14,quantity=2903,unresolved_retained=7,qp_catalogue_and_manual_cover=True,
        manual_parameters=True,sqlite=True,length_mm=330,layouts=[1250,1900])
