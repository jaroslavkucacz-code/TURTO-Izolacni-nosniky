from __future__ import annotations

"""Actual upgrade/Tk regression. HIT values are read from the SHA-verified DoP.
Schock source rows reproduce the user's supplied schedule, not a new catalogue.
All fixtures and generated files stay in a temporary installation.
"""
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
from types import SimpleNamespace
from urllib.parse import urlparse
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'updates/3.0.3'
BROKEN = {'P021', 'P025', 'P026', 'P027'}
EXPECTED = {
    'P021': ('HIT-SP ZVX-0403-24-050-30-12', 167.75),
    'P025': ('HIT-SP ZVX-0202-24-033-30-12', 90.0765),
    'P026': ('HIT-SP ZVX-0302-24-033-30-12', 121.8114),
    'P027': ('HIT-SP ZVX-0302-25-033-30-12', 121.8114),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(path):
    return {str(p.relative_to(path)): digest(p) for p in path.rglob('*') if p.is_file()}


def acquire_pdf(path, source_url, expected):
    mounted = os.environ.get('TURTO_DOP_FILE')
    if mounted:
        shutil.copyfile(mounted, path)
    else:
        for attempt in range(3):
            try:
                req = urllib.request.Request(source_url, headers={'User-Agent': 'TURTO-3.0.3-verification'})
                with urllib.request.urlopen(req, timeout=90) as response:
                    path.write_bytes(response.read(40 * 1024 * 1024))
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(3)
    assert digest(path) == expected, 'Manufacturer PDF changed; manual review is required.'


def main():
    cache, reads = {}, []
    report = {'version': '3.0.3', 'platform': sys.platform,
              'source_rows': 'user-supplied P014-P028 schedule; not a manufacturer catalogue',
              'hit_values': 'original SHA-verified manufacturer DoP', 'checks': []}

    def source(req, *a, **k):
        parsed = urlparse(req.full_url if hasattr(req, 'full_url') else str(req))
        assert parsed.netloc == 'raw.githubusercontent.com'
        owner, repo, commit, *parts = parsed.path.strip('/').split('/')
        assert (owner, repo) == ('jaroslavkucacz-code', 'TURTO-Izolacni-nosniky') and len(commit) == 40
        key = commit + ':' + '/'.join(parts)
        reads.append(key)
        if key not in cache:
            cache[key] = subprocess.check_output(['git', 'show', key], cwd=ROOT)
        return io.BytesIO(cache[key])

    with tempfile.TemporaryDirectory(prefix='turto_zvx303_') as folder:
        root = Path(folder)
        program = root / 'Program'
        os.environ.update(TURTO_ROOT=str(root), TURTO_PROGRAM_DIR=str(program),
                          APPDATA=str(root/'appdata'), LOCALAPPDATA=str(root/'localappdata'))
        shutil.copytree(ROOT/'updates/1.1.17/catalogs', root/'catalogs')
        customer = root/'actions.sqlite3'
        customer.write_bytes(b'TEST_ONLY_UNTOUCHED_CUSTOMER_SENTINEL')
        customer_before = digest(customer)
        with patch('urllib.request.urlopen', source):
            runpy.run_path(str(ROOT/'updates/3.0.2/runtime_installer.py'))['install_runtime'](root)
        baseline, catalogue = tree(program), tree(root/'catalogs')
        sys.path.insert(0, str(program))
        import hit_core
        import pdfplumber
        legacy_parser = hit_core._parse_zvx_pages
        fix_ns = runpy.run_path(str(RELEASE/'zvx_tables_303.py'))
        pdf_path = root/'manufacturer.pdf'
        acquire_pdf(pdf_path, fix_ns['SOURCE_URL'], fix_ns['SOURCE_SHA256'])
        data_file = root/'cached_hit_data.b64'
        # Real Annex 3 records from the legacy parser, in the existing cache schema.
        # This scoped fixture does not manufacture non-shear design values.
        with pdfplumber.open(pdf_path) as pdf:
            old_records = legacy_parser(pdf)
            complete = fix_ns['parse_zvx_pages'](pdf)
        old_data = {'schema_version': 4, 'source_document': 'CONF-DOP_HIT-HP/SP-07-23',
                    'source_sha256': fix_ns['SOURCE_SHA256'], 'zvx_records': old_records,
                    'user_extension': {'preserve': 'unchanged opaque metadata'}}
        data_file.write_bytes(base64.b64encode(gzip.compress(json.dumps(old_data).encode())))
        old_db = hit_core.HitDatabase(data_file)
        assert len(old_db.zvx_records) == 1612
        data_before = digest(data_file)
        assert len(complete) == 1772 and fix_ns['fingerprint'](complete) == fix_ns['COMPLETE_SHA256']
        new_keys = {fix_ns['_key'](r): r for r in complete}
        assert all(new_keys[fix_ns['_key'](r)] == r for r in old_db.zvx_records)
        report.update(source_sha256=digest(pdf_path), old_zvx_records=1612, complete_zvx_records=1772)

        baseline = tree(program)  # Includes bytecode created by the legacy data reader.
        installer = runpy.run_path(str(RELEASE/'runtime_installer.py'))
        installer['selftest']()
        original_replace, fault = os.replace, [False]
        def fail_once(src, dst):
            if Path(dst).name == 'zvx_tables_303.py' and not fault[0]:
                fault[0] = True
                raise OSError('TEST_ONLY write failure')
            return original_replace(src, dst)
        with patch('urllib.request.urlopen', source), patch('os.replace', fail_once):
            try:
                installer['install_runtime'](root)
            except OSError:
                pass
            else:
                raise AssertionError('Write failure not surfaced')
        assert fault[0] and tree(program) == baseline
        with patch('urllib.request.urlopen', source):
            installer['install_runtime'](root)
            count = len(reads)
            installer['install_runtime'](root)
            assert len(reads) == count
        assert digest(customer) == customer_before and digest(data_file) == data_before
        assert tree(root/'catalogs') == catalogue
        shutil.copyfile(RELEASE/'app.pyw', root/'app.pyw')
        (root/'.turto_runtime_current.ok').write_text('34', encoding='utf-8')
        boot = runpy.run_path(str(root/'app.pyw'))
        boot['selftest']()
        assert boot['_runtime_ready']()
        (program/'zvx_annex3_303.json.gz.b64').write_text('corrupted', encoding='ascii')
        assert not boot['_runtime_ready']()
        with patch('urllib.request.urlopen', source):
            boot['_repair_runtime']()
        assert boot['_runtime_ready']() and digest(customer) == customer_before
        customer.unlink()  # Remove only our temporary sentinel before actual SQLite starts.
        boot['_activate_program']()
        runtime = runpy.run_path(str(program/'app_runtime.pyw'))
        runtime['selftest']()
        import zvx_tables_303 as fix
        db = hit_core.HitDatabase(data_file)
        assert db.data == old_data and len(db.zvx_records) == 1771
        assert db.records == old_db.records and db.mvxl_records == old_db.mvxl_records
        assert db.dd_moment == old_db.dd_moment and db.dvl_moment == old_db.dvl_moment
        assert fix.repair_database(db) and digest(data_file) == data_before
        report['cache_repair'] = db._zvx_tables_303_audit
        assert len(report['cache_repair']['blocked_records']) == 1
        assert not any(r['series']=='SP' and r['code']=='0202' and r['length_code']==33
                       and r['diameter']=='12' and r['concrete']=='C20/25' and r['h_min']==170
                       for r in db.zvx_records)
        # Verify the real PDF-import helper binding, then parse the source again.
        assert hit_core.build_database_from_pdf.__globals__['_parse_zvx_pages'] is fix.parse_zvx_pages
        with pdfplumber.open(pdf_path) as pdf:
            rebuilt_rows = hit_core._parse_zvx_pages(pdf)
        assert fix.fingerprint(rebuilt_rows) == fix.COMPLETE_SHA256
        rebuilt = copy.deepcopy(old_data); rebuilt['zvx_records'] = rebuilt_rows
        (root/'rebuilt.b64').write_bytes(base64.b64encode(gzip.compress(json.dumps(rebuilt).encode())))
        assert hit_core.HitDatabase(root/'rebuilt.b64').zvx_records == db.zvx_records

        def rejects(label, rows):
            probe = SimpleNamespace(source_sha256=fix.SOURCE_SHA256, zvx_records=copy.deepcopy(rows))
            before = copy.deepcopy(probe.zvx_records)
            try:
                fix.repair_database(probe)
            except ValueError:
                pass
            else:
                raise AssertionError(label)
            assert before == probe.zvx_records
            report['checks'].append(label)
        rejects('truncated old cache', old_db.zvx_records[:-1])
        bad = copy.deepcopy(old_db.zvx_records); bad[0]['vrd'] += 1
        rejects('changed existing capacity', bad)
        rejects('duplicate key', old_db.zvx_records + old_db.zvx_records[:1])
        bad = copy.deepcopy(complete); bad[-1]['vrd'] += 1
        rejects('changed complete cache', bad)
        for sha in ('', 'OTHER', '0'*64):
            probe = SimpleNamespace(source_sha256=sha, zvx_records=copy.deepcopy(old_db.zvx_records))
            assert not fix.repair_database(probe) and probe.zvx_records == old_db.zvx_records
            report['checks'].append('unknown source not supplemented '+sha)
        with patch.object(fix, 'DATA_FILE', root/'invalid_reference'):
            (root/'invalid_reference').write_text('broken', encoding='ascii')
            try:
                fix.reference_data()
            except Exception:
                report['checks'].append('corrupted reference rejected')
            else:
                raise AssertionError('Corrupted reference accepted')
        # A missing numeric column cannot silently discard a whole table anymore.
        with pdfplumber.open(pdf_path) as pdf:
            actual = pdf.pages[94]
            class BadPage:
                def __getattr__(self, name): return getattr(actual, name)
                def search(self, pattern, **kwargs):
                    result = copy.deepcopy(actual.search(pattern, **kwargs))
                    if pattern is fix.HEIGHT_ROW:
                        lo, hi, numbers = result[0]['groups']
                        result[0]['groups'] = (lo, hi, ' '.join(numbers.split()[:-1]))
                    return result
            broken = SimpleNamespace(pages=list(pdf.pages)); broken.pages[94] = BadPage()
            try:
                fix.parse_zvx_pages(broken)
            except ValueError:
                report['checks'].append('missing physical column rejected')
            else:
                raise AssertionError('Incomplete table accepted')

        import tkinter as tk
        from tkinter import ttk, messagebox
        from PIL import ImageGrab
        import substitution_workspace as sub
        from catalog_engine import CatalogDatabase
        from project_model import create_project_row
        from isokorb_xt_parser_243 import _SAMPLE_ROWS, parse_xt_designation
        from iso_bulk_301 import candidates_for
        from action_store import ActionStore
        from action_payload import serialize_action, load_action_record
        values = [35.3,56.4,70.5,87.8,87.8,98.0,117.6,153.6,34.5,58.8,68.9,68.9,104.0,104.0,115.2]
        families = {}
        for (name, qty, typ), ved in zip(_SAMPLE_ROWS[13:28], values):
            f = parse_xt_designation(name).fields
            family = families.setdefault(typ, {'manufacturer':'Schöck','model':'XT','type':typ,
                'generation':f['generation'],'insulation_thickness_mm':120,'records':[]})
            family['records'].append({'designation':name,'moment_class':f['shear'],'shear_class':'—',
                'cover':'L='+f['length']+' mm' if 'length' in f else '—','height_mm':f['height'],
                'concrete_min':'C25/30','element_length_mm':int(f.get('length',1000)),
                'compression_transfer':'bez tlakových ložisek' if typ=='QP-Z' else 'betonová tlaková ložiska',
                'results':[{'kind':'shear','key':'user_schedule','label':'User-provided V',
                    'positive':ved,'negative':ved if typ=='QL' else 0.0,
                    'unit':'kN/m' if typ=='QL' else 'kN/element'}]})
        source_folder=root/'TEST_ONLY_SOURCE'; source_folder.mkdir()
        (source_folder/'source.json').write_text(json.dumps({'schema_version':2,
            'catalog':{'id':'USER_SCHEDULE','edition':'User supplied; test fixture'},
            'families':list(families.values())}),encoding='utf-8')
        source_db=CatalogDatabase(source_folder)
        rows=[]
        for i,(name,qty,typ) in enumerate(_SAMPLE_ROWS[13:28],14):
            choices=candidates_for(source_db,parse_xt_designation(name),'C25/30')
            assert len(choices)==1,(name,len(choices))
            rows.append(create_project_row(choices[0].result,position=f'P{i:03d}',quantity=qty,source_text=name))
        originals=copy.deepcopy(rows)
        report['old_failures']=[]
        for row in rows:
            targets,errors=sub.design_targets(old_db,row=row,metadata=sub.source_metadata(row))
            if not targets: report['old_failures'].append(row['position'])
        assert set(report['old_failures'])==BROKEN,report['old_failures']
        failures=[]
        tk.Tk.report_callback_exception=lambda self,*exc:failures.append(''.join(traceback.format_exception(*exc)))
        with patch.object(messagebox,'showerror',lambda *a,**k:failures.append(str(a))), \
             patch.object(messagebox,'showwarning',lambda *a,**k:None), \
             patch.object(messagebox,'askyesno',return_value=True):
            app=runtime['_base'].ThermalConnectorApp(); app.update()
            assert app._turto_logo_loaded and '3.0.3' in app._turto_brand_title.cget('text')
            assert app._load_hit_data(data_file,quiet=True)  # Real load lifecycle repairs the old on-disk cache.
            assert 'sloupce opraveny 3.0.3' in app.hit_source_var.get()
            app.database=source_db; app.project.rows=rows; app.refresh_substitution_tree()
            def walk(w):
                yield w
                for c in w.winfo_children(): yield from walk(c)
            buttons=[w for w in walk(app) if isinstance(w,ttk.Button) and str(w.cget('text'))=='Navrhnout vše']
            assert len(buttons)==1
            buttons[0].invoke(); app.update()
            report['rows']=[]
            for row,before in zip(rows,originals):
                target=sub.selected_target(row['mapping'])
                assert target and row['mapping']['status'] in ('ok','review'),(row['position'],row['mapping'])
                assert target['utilization']<=1.000000001
                assert target['compression_category']==('without' if row['selection']['type_name']=='QP-Z' else 'bearing')
                assert sub._length_is_allowed(target['source_length_mm'],target['length_mm'])
                assert target['height_mm']==int(row['selection']['height_mm']) and target['cover_mm']==30
                assert row['selection']==before['selection'] and row['snapshot']==before['snapshot']
                if row['position'] in EXPECTED:
                    name,capacity=EXPECTED[row['position']]
                    assert target['designation']==name,(row['position'],target['designation'],name)
                    assert abs(target['v_capacity_element']-capacity)<1e-8
                report['rows'].append({k:target[k] for k in ('designation','length_mm','v_capacity','v_capacity_element','utilization','compression_text')}|{'position':row['position']})
            # No unsafe load/length/bearing relaxation was introduced by the data repair.
            bad=copy.deepcopy(originals[7]);bad['snapshot']['results'][0]['positive']=10000
            assert not sub.design_targets(app.hit_db,row=bad,metadata=sub.source_metadata(bad))[0]
            assert not sub._length_is_allowed(400,500)
            report['checks']+=['excessive shear still rejected','no longer 500 mm replacement for 400 mm source']
            saved=copy.deepcopy(app.project.rows)
            store=ActionStore(root/'TEST_ONLY_roundtrip.sqlite3')
            action=store.save(action_name='User schedule regression',payload=serialize_action(app))
            app.project.rows=[];load_action_record(app,store.load(action['id']));app.update()
            assert len(app.project.rows) == len(saved)
            for actual, expected in zip(app.project.rows, saved):
                # Existing schema migration materializes an empty acceptance record.
                expected['mapping'].setdefault('substitution_acceptance', {})
                assert actual['mapping'] == expected['mapping']
                assert actual['selection'] == expected['selection']
                assert actual['snapshot'] == expected['snapshot']
            for tab in app.main_notebook.tabs():
                if app.main_notebook.tab(tab,'text')=='Záměny':app.main_notebook.select(tab)
            # Focus the evidence capture on the repaired positions, without changing application defaults.
            app.sub_tree.configure(displaycolumns=('position','quantity','source_length','target_length',
                'target_compression','v_pos','v_neg','target','target_v','utilization'))
            app.update()
            app.sub_tree.yview_moveto(1.0)
            time.sleep(.3);app.update()
            ImageGrab.grab().save(ROOT/f'zvx303-window-{sys.platform}.png')
            assert not failures,failures
            app.destroy();del app,store;logging.shutdown();gc.collect()
        assert digest(data_file)==data_before and tree(root/'catalogs')==catalogue
        report.update(actual_tk_button=True,old_cache_auto_repaired=True,old_cache_file_unchanged=True,
            source_cache_payload_unchanged=True,source_rows_unchanged=True,sqlite_roundtrip=True,
            upgrade_302_to_303=True,rollback=True,repair=True,idempotent=True,logo_preserved=True,
            annex3_parser_binding_verified=True,all_15_rows_have_proposals=True)
    (ROOT/f'zvx303-test-{sys.platform}.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
