"""Real restored catalogues and saved QL/QP rows; no fabricated capacities."""
from pathlib import Path
import base64
import copy
import gzip
import hashlib
import json
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = 'schoeck-cz-2024.1-2024-09'


def verify_originals(program):
    source = json.loads((ROOT/'updates/3.0.15/catalogue_sources.json').read_text(encoding='utf-8'))
    packages = []
    for item in source['catalogues']:
        encoded = (Path(program)/item['name']).read_bytes()
        assert hashlib.sha256(encoded).hexdigest() == item['sha256']
        raw = gzip.decompress(base64.b64decode(encoded))
        assert hashlib.sha256(raw).hexdigest() == item['original_sha256']
        package = json.loads(raw)
        assert package['catalog']['id'] == item['catalog_id']
        assert len(package['families']) == item['families']
        assert sum(len(f.get('records', [])) for f in package['families']) == item['records']
        packages.append(package)
    return packages


def pump(app, seconds=.2):
    until = time.monotonic()+seconds
    while time.monotonic() < until:
        app.update(); time.sleep(.01)


def exercise(app):
    from tkinter import ttk
    import bulk_import, bulk_import_engine as engine
    from isokorb_xt_parser_243 import _SAMPLE_ROWS, parse_xt_designation
    from project_model import create_project_row, normalize_project_row, row_status, query_from_selection
    from action_payload import serialize_action, load_action_record, action_store
    from catalog_engine import SelectionError
    import catalog_engine
    database = app.database
    core = database
    while hasattr(core, 'base'):
        core = core.base
    assert not core.load_errors, core.load_errors
    packages = verify_originals(Path(catalog_engine.__file__).parent)
    for package in packages:
        cid = package['catalog']['id']
        loaded = [f for f in database.families if f['catalog_id'] == cid]
        assert len(loaded) == len(package['families']), cid
        for original in package['families']:
            family = next(f for f in loaded if all(f[k] == original[k] for k in ('model','type','generation')))
            assert family['records'] == original['records'], (cid, original['type'])
    codes = [r[0] for r in _SAMPLE_ROWS if parse_xt_designation(r[0]).family != 'ZL']
    assert len(codes) == 28
    rows = []
    for index, code in enumerate(codes, 1):
        item = engine.BulkImportItem(index, code, '', 1, code)
        engine._classify_bulk_item(database, item, preferred_concrete='C25/30', suggestion_limit=100)
        assert item.ready and len(item.candidates) == 1, (code, item.message)
        result = database.resolve_designation(code, preferred_concrete='C25/30')
        assert result.catalog['id'] == SOURCE_ID
        assert result.results == item.result.results
        assert [s.result.results for s in database.suggest_designations(code, preferred_concrete='C25/30')] == [result.results]
        row = normalize_project_row(create_project_row(result, position=f'P{index:03d}', quantity=2, source_text=code))
        # Reproduce the old action shown by the user: the saved key is a
        # concrete height, although its original static table contains a range.
        row['selection']['height_mm'] = parse_xt_designation(code).fields['height']
        assert row_status(database, row)[0] == 'ok', code
        rows.append(row)
    expected = [35.3,56.4,70.5,87.8,87.8,98.,117.6,153.6,34.5,58.8,68.9,68.9,104.,104.,115.2]
    for row, capacity in zip(rows[13:], expected):
        result = query_from_selection(database, row['selection'])
        r = result.results[0]
        assert r.get('positive', r.get('value')) == capacity, row['position']
        assert r['unit'] == ('kN/m' if row['selection']['type_name']=='QL' else 'kN/prvek')
    for key, value in [('height_mm','150'), ('moment_class','VV99'), ('cover','L=777 mm'), ('generation','9.9'), ('catalog_id','missing-edition')]:
        invalid = copy.deepcopy(rows[13]); invalid['selection'][key] = value
        assert row_status(database, invalid)[0] == 'missing', (key, value)
    changed = copy.deepcopy(rows[13]); changed['snapshot']['results'][0]['positive'] += 1
    assert row_status(database, changed)[0] == 'changed'
    printed = query_from_selection(database, rows[13]['selection']).designation
    try:
        database.resolve_designation(printed, preferred_concrete='C30/37')
    except SelectionError:
        pass
    else:
        raise AssertionError('Original label must still respect the requested concrete')
    for code in ['XT-QL-VV99-REI120-H240-6.0', 'XT-ZL-EI120-H240-5.3']:
        assert not database.suggest_designations(code, preferred_concrete='C25/30')
        try:
            database.resolve_designation(code, preferred_concrete='C25/30')
        except SelectionError:
            pass
        else:
            raise AssertionError(code)
    # A populated existing catalogue must win without duplicate-ID warnings.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='turto315-existing-') as folder:
        original = copy.deepcopy(packages[1])
        original['catalog']['notes'].append('TEST_ONLY existing catalogue retained')
        path = Path(folder)/'original.json'
        path.write_text(json.dumps(original), encoding='utf-8')
        before = path.read_bytes()
        existing = catalog_engine.CatalogDatabase(folder)
        assert existing.catalogs[SOURCE_ID]['_data_file'] == str(path)
        assert existing.catalogs[SOURCE_ID]['notes'][-1] == 'TEST_ONLY existing catalogue retained'
        assert not existing.load_errors and path.read_bytes() == before
        assert len([f for f in existing.families if f['catalog_id']==SOURCE_ID]) == 30
        del existing

    app.main_notebook.select(app.project_tab); pump(app)
    app.project.rows = rows; app.refresh_project_tree(); pump(app)
    assert all(app.project_tree.set(r['id'],'status') == 'OK' for r in rows)
    # Preserve an already selected HIT mapping exactly, including its identity.
    rows[13]['mapping'].update(status='ok', selected_target_id='TEST_ONLY_KEEP', targets=[
        {'id':'TEST_ONLY_KEEP','designation':'HIT-SP ZDX-0202','notes':['TEST_ONLY identity preservation']}])
    saved_rows = copy.deepcopy(rows)
    store = action_store(app)
    saved = store.save(action_name='TEST_ONLY 315 saved catalogue rows', payload=serialize_action(app))
    app.project.rows=[]; load_action_record(app, store.load(saved['id'])); pump(app)
    assert app.project.rows == saved_rows
    assert all(app.project_tree.set(r['id'],'status') == 'OK' for r in app.project.rows)
    (Path(app.settings_path).parent/'TEST_ONLY_saved315.json').write_text(json.dumps(
        {'action_id':saved['id'], 'rows':saved_rows}), encoding='utf-8')

    app.project.rows=[]; app.refresh_project_tree(); pump(app)
    entry=app.project_quick_entry; entry.focus_force(); pump(app)
    entry.delete(0,'end'); entry.insert(0,'XT-QL-VV'); pump(app)
    ac=app.project_autocomplete
    assert ac._visible and ac.tree.get_children()
    assert all(s.result.record['moment_class'].startswith('VV') for s in ac._suggestions.values())
    ac.tree.focus_set(); ac.tree.event_generate('<Return>'); pump(app)
    button=next(w for w in entry.master.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Dekódovat a přidat')
    button.invoke(); pump(app)
    assert len(app.project.rows)==1, entry.get()
    assert row_status(database, app.project.rows[0])[0]=='ok'
    for code in ('T-KL-M1-V1-REI120-CV1-H180-2.2', 'T-QP-VV1-REI120-H200-L300-5.0'):
        entry.delete(0,'end'); entry.insert(0,code)
        before=len(app.project.rows); button.invoke(); pump(app)
        assert len(app.project.rows)==before+1, code
        assert row_status(database,app.project.rows[-1])[0]=='ok'
    assert app.project.rows[-1]['snapshot']['results'][0]['positive']==30.9
    dialog=bulk_import.BulkImportDialog(app,database=database,colors=app.colors,
        preferred_concrete='C25/30',existing_positions=[],start_position='P001')
    dialog.text.insert('1.0','\n'.join(f'P{i:03d}\t1\t{code}' for i,code in enumerate(codes,1)))
    dialog.analyze_button.invoke()
    deadline=time.monotonic()+30
    while dialog._analysis_running and time.monotonic()<deadline:
        pump(app,.03)
    assert not dialog._analysis_running and len(dialog.items)==28
    assert all(item.ready for item in dialog.items)
    dialog.destroy()
    app.project.rows=[]; app.refresh_project_tree(); pump(app)
    return dict(real_source_records=14217, source_catalogues=2, screenshot_rows=15,
        saved_action_rows=28, checks=['original data hashes and all loaded records',
        'legacy H240/H250 range lookup', 'unchanged saved rows and HIT choice',
        'actual table status OK', 'actual popup selection then add',
        'quick/bulk agreement on real catalogues', 'existing catalogue priority',
        'changed values and invalid selections still detected'])


def reopen_saved(app):
    from action_payload import action_store, load_action_record
    from project_model import row_status
    saved = json.loads((Path(app.settings_path).parent/'TEST_ONLY_saved315.json').read_text(encoding='utf-8'))
    load_action_record(app, action_store(app).load(saved['action_id'])); pump(app)
    assert app.project.rows == saved['rows']
    assert len(app.project.rows) == 28
    assert all(row_status(app.database, row)[0] == 'ok' for row in app.project.rows)
    assert all(app.project_tree.set(row['id'], 'status') == 'OK' for row in app.project.rows)
