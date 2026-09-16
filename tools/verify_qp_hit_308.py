from __future__ import annotations

"""Actual 3.0.7 -> 3.0.8, saved QP action -> HIT button -> SQLite.
Both source and target values come from shipped/reviewed manufacturer records.
A real display is required, including for the historical installer progress UI.
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
import traceback
import urllib.request
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'updates/3.0.8'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def main():
    report = dict(version='3.0.8', platform=sys.platform, checks=[])
    cache = {}

    def source(request, *args, **kwargs):
        url = urlparse(request.full_url if hasattr(request, 'full_url') else str(request))
        assert url.netloc == 'raw.githubusercontent.com'
        owner, repo, commit, *parts = url.path.strip('/').split('/')
        assert (owner, repo) == ('jaroslavkucacz-code', 'TURTO-Izolacni-nosniky')
        key = commit + ':' + '/'.join(parts)
        if key not in cache:
            cache[key] = subprocess.check_output(['git', 'show', key], cwd=ROOT)
        return io.BytesIO(cache[key])

    with tempfile.TemporaryDirectory(prefix='turto308_') as folder:
        root = Path(folder)
        program = root / 'Program'
        os.environ.update(TURTO_ROOT=str(root), TURTO_PROGRAM_DIR=str(program),
                          APPDATA=str(root/'appdata'), LOCALAPPDATA=str(root/'localappdata'))
        shutil.copytree(ROOT/'updates/1.1.17/catalogs', root/'catalogs')
        with patch('urllib.request.urlopen', source):
            runpy.run_path(str(ROOT/'updates/3.0.7/runtime_installer.py'))['install_runtime'](root)
        sys.path.insert(0, str(program))
        runtime = runpy.run_path(str(program/'app_runtime.pyw'))
        import catalog_engine, isokorb_qp_307 as qp, shear_cover_302 as shear
        import substitution_workspace as sub, zvx_tables_303 as zvx, hit_core
        from project_model import create_project_row, ProjectDocument
        from action_store import ActionStore
        import action_payload
        original = create_project_row(catalog_engine.CatalogDatabase(root/'catalogs').resolve_designation(
            qp.EXAMPLE, preferred_concrete='C25/30'), position='P001', quantity=2, source_text=qp.EXAMPLE)
        assert sub.source_metadata(original)['errors'] == [shear.COVER_ERROR]
        document = ProjectDocument(name='TEST_ONLY saved QP 307', rows=[original])
        store = ActionStore(root/'actions.sqlite3')
        record = store.save(action_name=document.name, payload={
            'schema_version':1, 'application':'TURTO ISO', 'action_name':document.name,
            'project':document.to_dict(), 'hit_design':{'schema_version':1, 'rows':[]}})
        gc.collect()
        protected = [root/'actions.sqlite3', program/'isokorb_qp_307.py', program/'schoeck_t_qp_307.json',
                     program/'design_rows_306.py', program/'turto_pdf_logo_305.png.b64', program/'turto_icon_301.png.b64']
        before = {p: digest(p) for p in protected}
        installer = runpy.run_path(str(REL/'runtime_installer.py'))
        with patch('urllib.request.urlopen', source):
            installer['install_runtime'](root)
            installer['install_runtime'](root)
        assert before == {p: digest(p) for p in protected}
        shutil.copyfile(REL/'app.pyw', root/'app.pyw')
        (root/'.turto_runtime_current.ok').write_text('39')
        assert runpy.run_path(str(root/'app.pyw'))['_runtime_ready']()
        runtime = runpy.run_path(str(program/'app_runtime.pyw'))
        runtime['selftest']()
        report['checks'].append('actual update and idempotency; saved SQLite action, source catalogue, logos and empty-row fix preserved')

        pdf_path = root/'hit-dop.pdf'
        pdf_path.write_bytes(urllib.request.urlopen(zvx.SOURCE_URL, timeout=90).read())
        assert digest(pdf_path) == zvx.SOURCE_SHA256
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            rows = zvx.parse_zvx_pages(pdf)
        assert zvx.fingerprint(rows) == zvx.COMPLETE_SHA256
        data_path = root/'hit-dop.b64'
        data_path.write_bytes(base64.b64encode(gzip.compress(json.dumps({
            'schema_version':4, 'source_document':'CONF-DOP_HIT-HP/SP-07-23',
            'source_sha256':zvx.SOURCE_SHA256, 'zvx_records':rows}).encode())))
        hit_db = hit_core.HitDatabase(data_path)
        data_hash = digest(data_path)
        meta = sub.source_metadata(original)
        assert not meta['errors'] and meta['source_cover_mm'] is None and meta['target_cover_mm'] == 30
        assert meta['fixed_shear_type'] == 'ZDX' and meta['target_series'] == 'HP'
        targets, errors = sub.design_targets(hit_db, row=original, metadata=meta)
        assert targets and not errors, errors
        assert targets[0]['designation'] == 'HIT-HP ZDX-0202-20-033-30-08'
        assert abs(targets[0]['v_capacity_element'] - 155.0 * .333) < 1e-8
        for target in targets:
            assert target['connection_type'] == 'ZDX' and target['series'] == 'HP'
            assert target['compression_category'] == 'bearing' and target['cover_mm'] == 30
            assert target['height_mm'] == 200 and target['concrete'] == 'C25/30'
            assert target['length_mm'] in (250,333)
            assert target['source_element_actions']['v_pos'] == target['source_element_actions']['v_neg'] == 30.9
            assert target['v_capacity_element'] >= 30.9 and target['utilization'] <= 1.0 + 1e-9
        report['target'] = targets[0]['designation']
        report['checks'].append('real DoP hash/table; both shear directions, bearings, 80mm insulation, H200 and 300-to-333 length rule')

        for edit in [
            lambda r:r.update(note='krytí 50 mm'),
            lambda r:r['selection'].update(cover='35'),
            lambda r:r['selection'].update(model='XT'),
            lambda r:r['selection'].update(generation='7.0'),
            lambda r:r['selection'].update(height_mm='210'),
            lambda r:r['selection'].update(moment_class='VV2'),
            lambda r:r['snapshot'].update(insulation_thickness_mm=120),
            lambda r:r['snapshot'].update(compression_transfer='bez tlakových ložisek'),
            lambda r:r['snapshot']['results'].append({'kind':'moment','value':5,'unit':'kNm/m'}),
            lambda r:r['snapshot']['results'][0].update(negative=0),
            lambda r:r['snapshot']['results'][0].update(positive='nan'),
            lambda r:r['snapshot']['results'][0].update(unit='unknown'),
            lambda r:r.update(mapping={'source_overrides':{'source_length_mm':500}}),
            lambda r:r.update(mapping={'source_overrides':{'target_cover_mm':50}}),
        ]:
            changed = copy.deepcopy(original); edit(changed)
            assert sub.source_metadata(changed).get('cover_resolution') != shear.RULE
            assert not sub.design_targets(hit_db, row=changed, metadata=meta)[0], changed
        for edit in [lambda r:r['snapshot'].update(substitution_policy='manual'),
                     lambda r:r['selection'].update(concrete_min='?'),
                     lambda r:r['snapshot']['results'][0].update(positive=1e6,negative=-1e6)]:
            changed = copy.deepcopy(original); edit(changed)
            assert not sub.design_targets(hit_db, row=changed, metadata=sub.source_metadata(changed))[0]
        wrong = copy.deepcopy(hit_db)
        wrong.zvx_records = [r for r in wrong.zvx_records if r['code'].endswith('00')]
        assert not sub.design_targets(wrong, row=original, metadata=meta)[0]
        assert not sub.design_targets(hit_db, row=original, metadata=meta, allowed_length_codes={100})[0]
        report['checks'].append('explicit cover, stale metadata, source mismatch, invalid values, capacity, length and incompatible bearings still block')

        import tkinter as tk
        from tkinter import messagebox, ttk
        failures = []
        tk.Tk.report_callback_exception = lambda self,*exc: failures.append(''.join(traceback.format_exception(*exc)))
        with patch.object(messagebox,'showerror',lambda *a,**k:failures.append(str(a))), \
             patch.object(messagebox,'showwarning',lambda *a,**k:failures.append(str(a))), \
             patch.object(messagebox,'showinfo',return_value=None):
            app = runtime['_base'].ThermalConnectorApp(); app.update()
            assert '3.0.8' in app._turto_brand_title.cget('text')
            action_payload.load_action_record(app, store.load(record['id']))
            app._settings = lambda: hit_db
            buttons = [w for w in walk(app) if isinstance(w,ttk.Button) and 'Navrhnout vše' in str(w.cget('text'))]
            assert len(buttons) == 1
            buttons[0].invoke(); app.update()
            row = app.project.rows[0]
            chosen = sub.selected_target(row['mapping'])
            assert row['mapping']['status'] in ('ok','review') and chosen, row['mapping']
            assert chosen['designation'] == report['target']
            assert row['snapshot'] == original['snapshot'] and row['selection'] == original['selection']
            assert app.sub_tree.set(row['id'],'source_cover') == 'dle typu'
            assert app.sub_tree.set(row['id'],'target_cover') == '30 mm (pevné)'
            assert action_payload.save_action(app)
            reloaded = action_payload.action_store(app).load(app.action_id)
            action_payload.load_action_record(app,reloaded)
            assert sub.selected_target(app.project.rows[0]['mapping']) == chosen
            assert len(app.project.rows) == 1 and app.project.rows[0]['quantity'] == 2
            assert not app.hit_rows and not app.aux_rows and not app.wt_rows
            assert not failures, failures
            app.destroy(); del app
            logging.shutdown(); gc.collect()
        assert digest(data_path) == data_hash
        report['checks'].append('real Navrhnout vše button on saved 307 action; visible covers, target persisted and unchanged source')
    (ROOT/f'qp308-test-{sys.platform}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
