"""Actual quick entry/popup/bulk/SQLite regression with isolated TEST_ONLY data.

The fixture tests the legacy catalogue schema, never manufacturer capacities.
It is written only to a disposable installation, never to the shipped package.
"""
from pathlib import Path
import json
import time


def fixture(root):
    from isokorb_xt_parser_243 import _SAMPLE_ROWS, parse_xt_designation
    codes = [row[0] for row in _SAMPLE_ROWS]
    codes += ['T-KL-M1-V1-REI120-CV1-H180-2.2',
              'T-KL-M5-V1-REI120-CV1-H180-2.2',
              'XT-KL-O-M3-V1-REI120-CV1-H250-7.2']
    import isokorb_families_304 as parser
    families = {}
    for index, code in enumerate(codes):
        p = parser.parse(code)
        if p:
            model, kind, fields = p.model, p.family, dict(p.fields)
        else:
            p = parse_xt_designation(code)
            assert p, code
            model, kind, fields = 'XT', p.family, dict(p.fields)
            if 'moment' in fields:
                fields['moment'] = 'M'+fields['moment']
        family = families.setdefault((model, kind, fields['generation']), dict(
            manufacturer='Schöck', model=model, type=kind, generation=fields['generation'],
            insulation_thickness_mm=120 if model == 'XT' else 80, records=[]))
        record = dict(designation='TEST_ONLY schema '+str(index), aliases=[],
                      moment_class=fields.get('moment', fields.get('shear', '—')),
                      shear_class=fields.get('shear', '—') if 'moment' in fields else '—',
                      cover='CV'+fields['cover'] if 'cover' in fields else '—',
                      height_mm=fields['height'], concrete_min='C25/30',
                      source_pages=[1], results=[dict(key='test_only', label='TEST_ONLY',
                      kind='shear', positive=10+index, negative=-10-index, unit='kN/m')])
        if kind == 'KL-O':
            record['cover'] += ' · W ≥ 200'
        if 'length' in fields:
            record['element_length_mm'] = int(fields['length'])
        family['records'].append(record)
    package = dict(schema_version=2, catalog=dict(id='TEST_ONLY_314',
        edition='TEST_ONLY; NOT FOR DESIGN', publication_date='2026-01-01',
        source_filename='TEST_ONLY.pdf'), families=list(families.values()))
    path = Path(root)/'catalogs/TEST_ONLY_314.json'
    path.write_text(json.dumps(package), encoding='utf-8')
    return codes


def pump(app, seconds=.25):
    until = time.monotonic()+seconds
    while time.monotonic() < until:
        app.update(); time.sleep(.01)


def exercise(app, codes):
    from tkinter import ttk, messagebox
    from unittest.mock import patch
    import bulk_import, bulk_import_engine as engine
    from catalog_engine import SelectionError
    from project_model import query_from_selection
    from action_payload import serialize_action, load_action_record
    from action_store import ActionStore
    db = app.database
    for code in codes:
        item = engine.BulkImportItem(1, code, 'TEST_ONLY', 1, code)
        engine._classify_bulk_item(db, item, preferred_concrete='C25/30', suggestion_limit=100)
        assert item.ready, (code, item.message)
        quick = db.resolve_designation(code, preferred_concrete='C25/30')
        popup = db.suggest_designations(code, preferred_concrete='C25/30')
        assert len(popup) == 1, (code, len(popup))
        assert quick.results == item.result.results == popup[0].result.results, code
        assert quick.designation == item.result.designation, code
    # No unrelated model, concrete, cover or VV/V when those were supplied.
    partial = db.suggest_designations('XT-KL-M3-VV1-', preferred_concrete='C25/30', limit=100)
    assert partial and all(s.result.family['model']=='XT' and s.result.record['shear_class']=='VV1' for s in partial)
    assert not db.suggest_designations('XT-KL-M3-VV1-', preferred_concrete='C30/37')
    missing = 'XT-KL-M99-V1-REI120-CV35-H250-6.2'
    for code in [missing, codes[0]+'-extra', codes[0].replace('6.2','9.9')]:
        assert not db.suggest_designations(code, preferred_concrete='C25/30'), code
        try:
            db.resolve_designation(code, preferred_concrete='C25/30')
        except SelectionError:
            pass
        else:
            raise AssertionError(code)
    # Keep the existing concrete/Schöck Sconnex route and ordinary products.
    sconnex='Schöck Sconnex W-N1-V1H1-B180-1.0'
    assert db.resolve_designation(sconnex, preferred_concrete='C25/30').family['type']=='W'
    assert db.suggest_designations('egcobx', preferred_concrete='C25/30')
    qp = 'T-QP-VV1-REI120-H200-L300-5.0'
    assert db.resolve_designation(qp, preferred_concrete='C25/30').record['results'][0]['positive']==30.9

    app.main_notebook.select(app.project_tab); pump(app)
    app.project_quick_entry.focus_force(); pump(app)
    assert app.project_quick_entry.winfo_ismapped()
    app.project_quick_entry.delete(0,'end')
    app.project_quick_entry.insert(0,'XT-KL-M3-VV1-'); pump(app)
    ac = app.project_autocomplete
    assert ac._visible and ac.tree.get_children(), 'Typing must show the real popup'
    assert all(s.result.record['shear_class']=='VV1' for s in ac._suggestions.values())
    ac.tree.focus_set(); ac.tree.event_generate('<Return>'); pump(app)
    assert not ac._visible
    assert 'TEST_ONLY' in app.project_quick_entry.get()
    # Full production-form code through the actual add button and Enter path.
    button = next(w for w in app.project_quick_entry.master.winfo_children()
                  if isinstance(w,ttk.Button) and w.cget('text')=='Dekódovat a přidat')
    for code in (codes[0], codes[-3], qp):
        app.project_quick_entry.delete(0,'end'); app.project_quick_entry.insert(0,code)
        app.project_quick_position_var.set('TEST_ONLY '+str(len(app.project.rows)+1))
        before=len(app.project.rows); button.invoke(); pump(app)
        assert len(app.project.rows)==before+1, code
        row=app.project.rows[-1]
        assert query_from_selection(db,row['selection']).results==row['snapshot']['results']
    before=len(app.project.rows)
    app.project_quick_entry.delete(0,'end'); app.project_quick_entry.insert(0,missing); pump(app)
    assert not ac._visible
    warnings=[]
    with patch.object(messagebox,'showerror',lambda *a,**k:warnings.append(a)):
        button.invoke(); pump(app)
    assert warnings and len(app.project.rows)==before

    # Real progressive import UI (not just its backend function).
    dialog=bulk_import.BulkImportDialog(app,database=db,colors=app.colors,
        preferred_concrete='C25/30',existing_positions=[],start_position='P001')
    dialog.text.insert('1.0','\n'.join(f'P{i:03d}\t1\t{code}' for i,code in enumerate(codes,1)))
    dialog.analyze_button.invoke()
    deadline=time.monotonic()+30
    while dialog._analysis_running and time.monotonic()<deadline:
        pump(app,.03)
    assert not dialog._analysis_running
    assert len(dialog.items)==len(codes) and all(i.ready for i in dialog.items), [(i.designation,i.message) for i in dialog.items if not i.ready]
    dialog.destroy()
    saved_rows=json.loads(json.dumps(app.project.rows))
    store=ActionStore(Path(app.settings_path).parent/'TEST_ONLY_decoder314.sqlite3')
    saved=store.save(action_name='TEST_ONLY decoder314',payload=serialize_action(app))
    app.project.rows=[];load_action_record(app,store.load(saved['id']));pump(app)
    assert [r['selection'] for r in app.project.rows]==[r['selection'] for r in saved_rows]
    assert [r['snapshot'] for r in app.project.rows]==[r['snapshot'] for r in saved_rows]
    app.project.rows=[];app.refresh_project_tree();pump(app)
    return dict(codes=len(codes), checks=['exact quick/bulk/popup parity', 'strict partial parameters',
        'missing/invalid type rejection', 'real typing and Return selection', 'real add button',
        'bulk Analyze button', 'SQLite roundtrip', 'Sconnex and Egcobox', 'real T-QP 30.9 kN'])
