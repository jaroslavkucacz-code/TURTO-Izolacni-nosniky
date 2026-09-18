"""Real pasted schedule, matching live catalogue rows, and actual entry dialogs."""
from pathlib import Path
from copy import deepcopy
import json
import time
from unittest.mock import patch

QUANTITIES = [391,1475,44,28,14,13,70,397,80,25,253,56,50]


def exercise(app):
    import bulk_import_engine as bulk, bulk_import, designation_format_321 as fmt
    import project_model, action_payload
    from catalog_engine import SelectionError
    from tkinter import messagebox
    from verify_workflow_317 import pump
    text = (Path(__file__).parent/'fixtures/schoeck_format_321.txt').read_text(encoding='utf-8')
    lines = text.splitlines()
    items,_ = bulk.analyze_bulk_text(app.database,text,preferred_concrete='C25/30')
    assert [i.quantity for i in items] == QUANTITIES
    assert sum(i.quantity for i in items) == 2896
    assert all(i.source_designation == line.split('\t')[0] for i,line in zip(items,lines))
    assert fmt.normalize(items[0].designation) == 'T-KL-M5-V1-REI120-CV1-H200-2.0'
    for n in (4,7,8,9):
        item = items[n]
        assert fmt.parsed_code(item.designation) and not item.ready and not item.candidates
        assert item.message.startswith('Označení přečteno') and '2.0' in item.message
    assert items[5].status == 'review' and len(items[5].candidates) == 1
    assert '-H200-L300-5.0' in items[5].candidates[0].designation
    assert items[11].status == 'error' and 'VV-V' in items[11].message
    # Formatting alone must match the same actual catalogue record and values.
    # These test inputs explicitly request the loaded generations (2.2 / 7.2);
    # the production normalizer never changes a requested generation.
    live = []
    for n in (0,1,2,3,4,6,8,9,10,12):
        original = items[n].designation
        generation = '7.2' if 'KL-U' in original else '2.2'
        if n == 0:
            formatted = original.replace('2,0','2,2')
        else:
            formatted = original.replace('2.0',generation)
        canonical = fmt.normalize(formatted)
        a,_=bulk.analyze_bulk_text(app.database,formatted+'\t'+str(QUANTITIES[n]),preferred_concrete='C25/30')
        b,_=bulk.analyze_bulk_text(app.database,canonical+'\t'+str(QUANTITIES[n]),preferred_concrete='C25/30')
        assert a[0].status == b[0].status and a[0].candidates
        identity=lambda c:(bulk.result_identity(c.result),c.result.results)
        assert list(map(identity,a[0].candidates)) == list(map(identity,b[0].candidates))
        suggestions=app.database.suggest_designations(formatted,preferred_concrete='C25/30',limit=100)
        assert list(map(identity,suggestions)) == list(map(identity,a[0].candidates))
        if len(suggestions)==1:
            result=app.database.resolve_designation(formatted,preferred_concrete='C25/30')
            assert result.results == a[0].result.results
            live.append(formatted)
        else:
            try:app.database.resolve_designation(formatted,preferred_concrete='C25/30')
            except SelectionError:pass
            else:raise AssertionError('Geometrical ambiguity was lost')
    assert len(live)>=7
    for original in ('HIT-SP ZDX-0202-20-100-200','CRET 122','MXL 30-WU280-180'):
        assert fmt.normalize(original)==original
    for original in (items[4].designation,items[11].designation,items[5].designation,
                     'T typ KL-M5-V1-REI120 CV9-H200-2.2',
                     'T typ KL-M5-V99-REI120 CV1-H200-2.2',
                     'T typ KL-M5-V1-REI120 CV1-H999-2.2',
                     'T typ KL-M5-M2-V1-REI120 CV1-H200-2.2'):
        try:app.database.resolve_designation(original,preferred_concrete='C25/30')
        except SelectionError:pass
        else:raise AssertionError(original)
    # Printed catalogue labels with range / geometry must still be selectable.
    for code in ('T-QP-V1-REI120-H200-L300-5.0','T-KL-U-M2-V1-REI120-CV1-H200-7.2'):
        choices=app.database.suggest_designations(code,preferred_concrete='C25/30',limit=100)
        assert choices
        for choice in choices:
            label=choice.result.record.get('catalog_designation')
            if label:
                result=app.database.resolve_designation(label,preferred_concrete='C25/30')
                assert result.results==choice.result.results
    app.product_domain_notebook.select(app.product_domain_tab_by_id['thermal_breaks'])
    app.main_notebook.select(app.project_tab);pump(app)
    app.project.rows=[];app.refresh_project_tree()
    app.project_quick_designation_var.set(live[0]);app.project_quick_length_var.set('0,5')
    app.quick_add_project_row();pump(app)
    assert len(app.project.rows)==1 and app.project.rows[0]['source_text']==live[0]
    assert app.project.rows[0]['selection']['generation']=='2.2'
    before=deepcopy(app.project.rows)
    app.project_quick_designation_var.set(items[4].designation)
    with patch.object(messagebox,'showerror') as error:
        app.quick_add_project_row();assert error.called and '2.0' in str(error.call_args)
    assert app.project.rows==before
    # Actual threaded import, missing-data feedback, confirm QP length, insert.
    def operate(dialog):
        dialog.text.insert('1.0',text+'\n'+live[1]+'\t1 475,00')
        dialog._analyze();deadline=time.monotonic()+30
        while dialog._analysis_running and time.monotonic()<deadline:pump(app,.04)
        assert not dialog._analysis_running and len(dialog.items)==14
        assert dialog.review_tree.set('i4','status')=='Chybí data'
        assert dialog.review_tree.set('i4','resolved')==fmt.normalize(items[4].designation)
        assert dialog.review_tree.set('i4','input')==items[4].designation
        item=dialog.items[5]
        dialog.review_tree.selection_set('i5');dialog._on_review_selected()
        # Use the real candidate confirmation handler.
        dialog.candidate_tree.selection_set(dialog.candidate_tree.get_children()[0])
        dialog._apply_candidate(False)
        assert item.ready and '-H200-L300-5.0' in item.result.designation
        with patch.object(messagebox,'askyesno',return_value=True):dialog.insert_button.invoke()
    with patch.object(app,'wait_window',side_effect=operate):app.bulk_paste_project_rows()
    assert len(app.project.rows)==10
    assert [r['quantity'] for r in app.project.rows]==[1,391,1475,44,28,13,70,253,50,1475]
    assert app.project.rows[5]['source_text']==items[5].source_designation
    store=action_payload.action_store(app)
    saved=store.save(action_name='TEST_ONLY formatted321',payload=action_payload.serialize_action(app))
    payload=deepcopy(app.project.rows)
    action_payload.load_action_record(app,store.load(saved['id']));pump(app)
    assert app.project.rows==payload
    (Path(app.settings_path).parent/'TEST_ONLY_saved321.json').write_text(json.dumps({'id':saved['id'],'rows':payload}),encoding='utf-8')
    return {'pasted_rows':13,'quantity':2896,'formatting_matches_catalogue':True,
            'generation_preserved':True,'ambiguous_shear_rejected':True,'qp_length_confirmed':True,'sqlite':True}


def reopen_saved(app):
    import action_payload
    record=json.loads((Path(app.settings_path).parent/'TEST_ONLY_saved321.json').read_text(encoding='utf-8'))
    store=action_payload.action_store(app)
    action_payload.load_action_record(app,store.load(record['id']))
    assert app.project.rows==record['rows']
