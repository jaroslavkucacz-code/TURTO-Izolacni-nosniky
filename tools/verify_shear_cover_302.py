from __future__ import annotations

"""Installed 3.0.1 -> 3.0.2 tests. TEST_ONLY fixtures are NOT manufacturer data."""
import base64
import copy
import gc
import gzip
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'updates/3.0.2'


def digest_tree(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def main():
    cache, reads = {}, []
    report = {'version': '3.0.2', 'platform': sys.platform,
              'fixture_is_not_manufacturer_data': True, 'tests': []}

    def source(request, *args, **kwargs):
        parsed = urlparse(request.full_url if hasattr(request, 'full_url') else str(request))
        assert parsed.netloc == 'raw.githubusercontent.com'
        owner, repo, ref, *parts = parsed.path.strip('/').split('/')
        assert (owner, repo) == ('jaroslavkucacz-code', 'TURTO-Izolacni-nosniky') and len(ref) == 40
        key = ref + ':' + '/'.join(parts)
        reads.append(key)
        if key not in cache:
            cache[key] = subprocess.check_output(['git', 'show', key], cwd=ROOT)
        return io.BytesIO(cache[key])

    with tempfile.TemporaryDirectory(prefix='turto_shear302_') as folder:
        root = Path(folder)
        program = root / 'Program'
        os.environ.update(TURTO_ROOT=str(root), TURTO_PROGRAM_DIR=str(program),
                          APPDATA=str(root/'appdata'), LOCALAPPDATA=str(root/'localappdata'))
        shutil.copytree(ROOT/'updates/1.1.17/catalogs', root/'catalogs')
        database = root/'actions.sqlite3'
        original_db = b'TEST_ONLY CUSTOMER DATA SENTINEL'
        database.write_bytes(original_db)
        with patch('urllib.request.urlopen', source):
            runpy.run_path(str(ROOT/'updates/3.0.1/runtime_installer.py'))['install_runtime'](root)
        baseline = digest_tree(program)
        catalog_before = digest_tree(root/'catalogs')
        installer = runpy.run_path(str(RELEASE/'runtime_installer.py'))
        installer['selftest']()
        replace, fault = os.replace, [False]

        def fail_once(src, dst):
            if Path(dst).name == 'shear_cover_302.py' and not fault[0]:
                fault[0] = True
                raise OSError('TEST_ONLY injected write failure')
            return replace(src, dst)

        with patch('urllib.request.urlopen', source), patch('os.replace', fail_once):
            try:
                installer['install_runtime'](root)
            except OSError:
                pass
            else:
                raise AssertionError('Update did not surface write failure')
        assert fault[0] and digest_tree(program) == baseline
        assert database.read_bytes() == original_db
        with patch('urllib.request.urlopen', source):
            installer['install_runtime'](root)
            count = len(reads)
            installer['install_runtime'](root)
            assert len(reads) == count
        assert installer['_revision_ok'](program)
        assert digest_tree(root/'catalogs') == catalog_before
        assert database.read_bytes() == original_db
        shutil.copy2(RELEASE/'app.pyw', root/'app.pyw')
        (root/'.turto_runtime_current.ok').write_text('33', encoding='utf-8')
        boot = runpy.run_path(str(root/'app.pyw'))
        boot['selftest']()
        assert boot['_runtime_ready']()
        (program/'shear_cover_302.py').write_text('# damaged', encoding='utf-8')
        assert not boot['_runtime_ready']()
        with patch('urllib.request.urlopen', source):
            boot['_repair_runtime']()
        assert boot['_runtime_ready']() and database.read_bytes() == original_db
        database.unlink()  # Remove ONLY the temporary test sentinel for actual application SQLite.
        boot['_activate_program']()
        runtime = runpy.run_path(str(program/'app_runtime.pyw'))
        runtime['selftest']()

        import tkinter as tk
        from tkinter import messagebox, ttk
        import substitution_workspace as sub
        import shear_cover_302 as shear
        from catalog_engine import CatalogDatabase
        from project_model import create_project_row, query_from_selection
        from isokorb_xt_parser_243 import _SAMPLE_ROWS, parse_xt_designation
        from iso_bulk_301 import candidates_for
        from hit_core import HitDatabase
        from action_store import ActionStore
        from action_payload import serialize_action, load_action_record
        from PIL import ImageGrab

        failures = []
        tk.Tk.report_callback_exception = lambda self, *exc: failures.append(''.join(traceback.format_exception(*exc)))
        fixture = root/'TEST_ONLY'
        fixture.mkdir()
        families = {}
        for name, _qty, fam_name in _SAMPLE_ROWS[13:28]:
            f = parse_xt_designation(name).fields
            family = families.setdefault(fam_name, {
                'manufacturer':'Schöck', 'model':'XT', 'type':fam_name, 'generation':f['generation'],
                'insulation_thickness_mm':120, 'records':[]})
            record = {'designation':'TEST_ONLY '+name, 'moment_class':f['shear'], 'shear_class':'—',
                'cover':'L='+f['length']+' mm' if 'length' in f else '—',
                'height_mm':f['height'], 'concrete_min':'C25/30',
                'element_length_mm':int(f.get('length', 1000)),
                'compression_transfer':'bez tlakových ložisek' if fam_name == 'QP-Z' else 'betonová tlaková ložiska',
                'results':[{'kind':'shear','key':'test','label':'TEST_ONLY V', 'positive':20.0,
                            'negative':20.0 if f['shear'].startswith('VV') else 0.0,
                            'unit':'kN/m' if fam_name == 'QL' else 'kN/element'}]}
            family['records'].append(record)
        (fixture/'source.json').write_text(json.dumps({'schema_version':2,
            'catalog':{'id':'TEST_ONLY','edition':'TEST_ONLY'},'families':list(families.values())}), encoding='utf-8')
        db = CatalogDatabase(fixture)
        hit_data = {'schema_version':4,'source_document':'TEST_ONLY; NOT FOR DESIGN','zvx_records':[
            {'series':'SP','concrete':concrete,'length_code':length,'h_min':160,'h_max':300,
             'vrd':150.0,'code':code,'diameter':'06','page':0}
            for concrete in ('C20/25','C25/30') for length in (100,50,33,25) for code in ('0601','0600')]}
        hit_file = fixture/'hit.b64'
        hit_file.write_bytes(base64.b64encode(gzip.compress(json.dumps(hit_data).encode())))
        hit_db = HitDatabase(hit_file)
        rows = []
        for index, (name, qty, fam_name) in enumerate(_SAMPLE_ROWS[13:28],14):
            choices = candidates_for(db, parse_xt_designation(name), 'C25/30')
            assert len(choices) == 1, (name,len(choices))
            rows.append(create_project_row(choices[0].result, position=f'P{index:03d}', quantity=qty, source_text=name))
        original_rows = copy.deepcopy(rows)

        with patch.object(messagebox, 'showerror', lambda *a, **k: failures.append(str(a))), \
             patch.object(messagebox, 'showwarning', lambda *a, **k: None), \
             patch.object(messagebox, 'askyesno', return_value=True):
            app = runtime['_base'].ThermalConnectorApp()
            app.update()
            assert app._turto_logo_loaded and '3.0.2' in app._turto_brand_title.cget('text')
            app.database = db
            app.project.rows = rows
            app._settings = lambda: hit_db
            app.refresh_substitution_tree()
            assert all(shear.COVER_ERROR not in sub.source_metadata(r)['errors'] for r in rows), [(r['position'],r['source_text'],r['selection'],sub.source_metadata(r),sub.source_actions(r)) for r in rows if shear.COVER_ERROR in sub.source_metadata(r)['errors']]
            assert all(sub.source_metadata(r)['source_cover_mm'] is None for r in rows)

            def walk(w):
                yield w
                for child in w.winfo_children():
                    yield from walk(child)
            buttons = [w for w in walk(app) if isinstance(w, ttk.Button) and 'Navrhnout vše' in str(w.cget('text'))]
            assert len(buttons) == 1, len(buttons)
            buttons[0].invoke()  # Real UI action, not just the metadata helper.
            app.update()
            report['rows'] = []
            for row, before in zip(rows,original_rows):
                mapping = row['mapping']
                target = sub.selected_target(mapping)
                assert mapping['status'] in ('ok','review') and target, (row['position'],mapping)
                expected = 'ZDX' if row['selection']['type_name']=='QL' else 'ZVX'
                assert target['connection_type']==expected and target['cover_mm']==30
                assert sub._length_is_allowed(mapping['source_meta']['source_length_mm'],target['length_mm'])
                pressure = 'without' if row['selection']['type_name']=='QP-Z' else 'bearing'
                assert target['compression_category']==pressure
                assert target['utilization'] <= 1.000000001
                assert row['snapshot']==before['snapshot'] and row['selection']==before['selection']
                payload,_status = app._payload(row)
                assert payload['source_cover']=='dle typu' and payload['target_cover']=='30 mm (pevné)'
                assert shear.EXPLANATION in payload['calculation'] and shear.EXPLANATION in payload['note']
                assert app.sub_tree.set(row['id'],'source_cover')=='dle typu'
                assert app.sub_tree.set(row['id'],'target_cover')=='30 mm (pevné)'
                report['rows'].append({'position':row['position'],'status':mapping['status'],
                    'type':expected,'source_cover':None,'target_cover':30,'pressure':pressure})

            # Explicit source/project CV, non-shear loads, wrong families and malformed data must not infer cover.
            checks = 0
            def rejected(label, edit, sample=0):
                nonlocal checks
                row=copy.deepcopy(original_rows[sample]); edit(row)
                assert sub.source_metadata(row).get('cover_resolution') != shear.RULE, label
                checks+=1; report['tests'].append(label)
            for cv in (30,35,50,45):
                rejected('explicit source cover '+str(cv),lambda r,c=cv:r['selection'].update(cover=str(c)))
            for note in ('cnom 35 mm','CV2','krytí 50 mm','cover 50','C=35'):
                rejected('project note '+note,lambda r,n=note:r.update(note=n))
            rejected('moment',lambda r:r['snapshot']['results'].append({'kind':'moment','value':5,'unit':'kNm/m'}))
            rejected('normal force',lambda r:r['snapshot']['results'].append({'kind':'normal','value':5,'unit':'kN/m'}))
            for value in ('bad','nan','inf'):
                rejected('invalid load '+value,lambda r,v=value:r['snapshot']['results'][0].update(positive=v))
            rejected('unknown units',lambda r:r['snapshot']['results'][0].update(unit='unknown'))
            rejected('missing reverse VV',lambda r:r['snapshot']['results'][0].update(negative=0))
            rejected('reverse V',lambda r:r['snapshot']['results'][0].update(negative=1),7)
            rejected('no load',lambda r:r['snapshot'].update(results=[]))
            rejected('different insulation',lambda r:r['snapshot'].update(insulation_thickness_mm=80))
            rejected('different generation',lambda r:r['selection'].update(generation='9.9'))
            rejected('different manufacturer',lambda r:r['selection'].update(manufacturer='OTHER'))
            rejected('different family',lambda r:r['selection'].update(type_name='KL'))
            rejected('different model',lambda r:r['selection'].update(model='T'))
            rejected('conflicting pressure',lambda r:r['snapshot'].update(compression_transfer='bez tlakových ložisek'))
            rejected('manual cover override',lambda r:r.update(mapping={'source_overrides':{'target_cover_mm':50}}))
            # Metadata may resolve cover but all other errors and mechanics still block invalid proposals.
            def no_target(label, edit, altered_db=None):
                nonlocal checks
                row=copy.deepcopy(original_rows[0]); edit(row)
                targets,errors=sub.design_targets(altered_db or hit_db,row=row,metadata=sub.source_metadata(row))
                assert not targets, label
                checks+=1; report['tests'].append(label)
            no_target('manual-only policy',lambda r:r['snapshot'].update(substitution_policy='manual'))
            no_target('unknown concrete',lambda r:r['selection'].update(concrete_min='?'))
            no_target('invalid height',lambda r:r['selection'].update(height_mm='245'))
            no_target('over capacity',lambda r:r['snapshot']['results'][0].update(positive=10000,negative=10000))
            weak=copy.deepcopy(hit_db);weak.zvx_records=[]
            no_target('no verified HIT records',lambda r:None,weak)
            wrong=copy.deepcopy(hit_db);wrong.zvx_records=[r for r in wrong.zvx_records if r['code']=='0600']
            no_target('only incompatible bearings',lambda r:None,wrong)
            old_meta=sub.source_metadata(original_rows[0])
            changed=copy.deepcopy(original_rows[0]); changed['note']='krytí 50 mm'
            assert not sub.design_targets(hit_db,row=changed,metadata=old_meta)[0]
            checks+=1;report['tests'].append('stale inferred cover rejected')
            for unit,length,wanted in [('kN/element',500,40),('kN/m',500,20),('kN/m',333,20*.5/.333)]:
                row=copy.deepcopy(original_rows[7]);row['snapshot']['results'][0]['unit']=unit
                actions,warnings=sub.source_actions(row,target_length_mm=length)
                assert not warnings and abs(actions.v_pos-wanted)<1e-8, (unit,length,actions,wanted)
                checks+=1;report['tests'].append(f'units {unit} to L{length}')
            assert not sub._length_is_allowed(400,500) and sub._length_is_allowed(300,333)
            checks+=1;report['tests'].append('length restriction and existing 300 to 333 exception')
            # SQLite persists the distinction instead of fabricating source CV on reload.
            saved_rows=copy.deepcopy(app.project.rows)
            store=ActionStore(root/'TEST_ONLY_roundtrip.sqlite3')
            saved=store.save(action_name='TEST_ONLY',payload=serialize_action(app))
            app.project.rows=[]
            load_action_record(app,store.load(saved['id']))
            app.update()
            assert len(app.project.rows)==15
            for row,before in zip(app.project.rows,saved_rows):
                assert row['selection']==before['selection'] and row['snapshot']==before['snapshot']
                assert row['mapping']['source_meta']['source_cover_mm'] is None
                assert row['mapping']['source_meta']['target_cover_mm']==30
                query_from_selection(db,row['selection'])
            # Take real application evidence, with only test records visible.
            for tab in app.main_notebook.tabs():
                if app.main_notebook.tab(tab,'text')=='Záměny':
                    app.main_notebook.select(tab)
            app.update()
            ImageGrab.grab().save(ROOT/f'shear302-window-{sys.platform}.png')
            assert not failures, failures
            app.destroy(); del app, store
            logging.shutdown();gc.collect()
        report.update(update_from_301=True,rollback=True,repair=True,idempotent=True,
            catalogue_bytes_unchanged=True,database_bytes_preserved=True,actual_tk_button=True,
            source_selection_preserved=True,sqlite_roundtrip=True,tested_shear_rows=15,
            negative_and_unit_tests=checks,logo_loaded=True)
    (ROOT/f'shear302-test-{sys.platform}.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
