from __future__ import annotations

"""Installed HIT units regression: real Annex 3 + TEST_ONLY moment fixtures.
Real Tk, SQLite, PDF and XLSX on Windows/Linux. No fixture is shipped as data.
"""
import base64
import copy
import gc
import gzip
import hashlib
import io
import json
import logging
import math
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

from verify_hit_choice_309 import walk, pump, button, group, entry, choose, assert_choice

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'updates/3.0.10'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(root):
    # Use the actual reviewed physical Annex 3 columns (including 333 mm).
    source = runpy.run_path(str(ROOT/'updates/3.0.3/zvx_tables_303.py'))
    cached = os.environ.get('TURTO_TEST_DOP_PATH')
    data = Path(cached).read_bytes() if cached else urllib.request.urlopen(source['SOURCE_URL'],timeout=90).read()
    assert hashlib.sha256(data).hexdigest() == source['SOURCE_SHA256']
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        zvx_records = source['parse_zvx_pages'](pdf)
    assert source['fingerprint'](zvx_records) == source['COMPLETE_SHA256']
    sections = []
    for series in ('HP','SP'):
        for length in (100,50,25):
            for code, scale in [('0202',1),('0404',1.5)]:
                heads = [f'HIT-{series} MVX-{code}-hh-{length:03d}-cc']
                rows = [[h, *([40*scale,100*scale,60*scale,40*scale]*3)] for h in (165,170)]
                sections.append([heads,rows,0])
    payload = dict(schema_version=4, source_document='TEST_ONLY moment fixtures; reviewed Annex 3; NOT FOR DESIGN',
                   concretes=['C20/25','C25/30','C30/37'], sections=sections, zvx_records=zvx_records,
                   dd_moment=[dict(xx='05',h_eff=170,concrete='C25/30',mrd=40)],
                   dvl_moment=[dict(xx='11',h_eff=170,concrete='C25/30',mrd=40)],
                   mvxl_records=[dict(series='HP',code='0202',length_code=length,tail='06',
                       mrd_rows=[dict(h_eff=165,values={'C25/30':150},bond='good')],
                       vrd_pos_ranges=[dict(h_min=160,h_max=300,values={'C25/30':200})],page=0)
                       for length in (100,50)])
    path = root/'TEST_ONLY_hit.b64'
    path.write_bytes(base64.b64encode(gzip.compress(json.dumps(payload).encode())))
    return path


def equivalent(actual, expected):
    a = {c.designation:c for c in actual}; b = {c.designation:c for c in expected}
    assert a.keys() == b.keys(), (a.keys()-b.keys(),b.keys()-a.keys())
    for key in a:
        for attr in ('utilization','m1','v1','m2','v2'):
            assert math.isclose(getattr(a[key],attr),getattr(b[key],attr),rel_tol=1e-10,abs_tol=1e-10), (key,attr)


def engine(database):
    import hit_units_310 as units
    from hit_core import DirectionalActions as A
    def call(mode, typ, actions, lengths, *, method='proposal_candidates', **kw):
        token = units._ELEMENT_INPUT.set(mode == 'element')
        try:
            return getattr(database,method)(typ,kw.get('series','HP'),kw.get('height',200),
                kw.get('cover',35 if typ.startswith('MVX') else 30),'C25/30',actions,lengths,
                kw.get('offsets',False))
        finally:
            units._ELEMENT_INPUT.reset(token)
    cases = [('ZDX',A(v_pos=20,v_neg=12)),('ZVX',A(v_pos=20)),
             ('MVX',A(m_neg=12,v_pos=10,v_neg=5)),('MVXL',A(m_neg=12,v_pos=10,v_neg=5)),
             ('DD',A(m_pos=10,m_neg=12,v_pos=10,v_neg=8)),
             ('DVL',A(m_neg=12,v_pos=10)),('DDL',A(m_pos=10,m_neg=12,v_pos=10,v_neg=8))]
    for typ, loads in cases:
        allowed = (100,50,33,25) if typ in ('ZDX','ZVX') else (100,50,25) if typ=='MVX' else (100,50) if typ=='MVXL' else (100,)
        for length in allowed:
            mm = units.LENGTHS[length]
            converted = A(**{k:getattr(loads,k)*1000/mm for k in units.KEYS})
            found = call('element',typ,loads,{length})[0]
            expected = call('metre',typ,converted,{length})[0]
            equivalent(found,expected)
        # Across differing lengths, compare to individually evaluated true loads.
        found = call('element',typ,loads,set(allowed))[0]
        expected=[]
        for length in allowed:
            expected += call('metre',typ,A(**{k:getattr(loads,k)*1000/units.LENGTHS[length] for k in units.KEYS}),{length})[0]
        if typ=='MVX' and any(c.connection_type=='MVX' for c in expected):
            expected=[c for c in expected if c.connection_type=='MVX']
        equivalent(found,expected)
        assert found, typ
    # Interaction and offsets still go through the original directional engine.
    for series in ('HP','SP'):
        a=call('element','MVX',A(m_neg=10,v_pos=20,v_neg=10),{50},method='directional_candidates',series=series,offsets=True)[0]
        b=call('metre','MVX',A(m_neg=20,v_pos=40,v_neg=20),{50},method='directional_candidates',series=series,offsets=True)[0]
        equivalent(a,b);assert any(c.suffix=='OU' for c in a)
    # No spurious fallback to a short MVXL when a longer preferred MVX works.
    mixed=call('element','MVX',A(m_neg=60,v_pos=20),{100,50,25})
    assert mixed[0] and all(c.connection_type=='MVX' for c in mixed[0])
    assert mixed[2]['primary_available'] and mixed[2]['alternative_count']==0
    fallback=call('element','MVX',A(m_neg=110,v_pos=20),{100,50})
    assert fallback[0] and all(c.connection_type=='MVXL' for c in fallback[0])
    assert fallback[2]['mode']=='fallback'
    assert not call('element','ZVX',A(v_pos=10,v_neg=10),{50})[0]
    assert not call('element','ZDX',A(v_pos=1e9,v_neg=1e9),{100,50,33,25})[0]
    assert not call('element','ZDX',A(v_pos=10),{50},cover=35)[0]
    for length in (0,330,-1):
        try:units.scaled_actions(A(v_pos=10),length)
        except ValueError:pass
        else:raise AssertionError(length)
    for val in (float('inf'),float('nan')):
        try:call('element','ZDX',A(v_pos=val),{50})
        except ValueError:pass
        else:raise AssertionError(val)
    assert not units._ELEMENT_INPUT.get()


def ui(root, baseline=False):
    sys.path.insert(0,str(root/'Program'))
    runtime=runpy.run_path(str(root/'Program/app_runtime.pyw'));runtime['selftest']()
    import tkinter as tk
    from tkinter import messagebox, ttk
    import hit_core, action_payload
    failures=[]
    tk.Tk.report_callback_exception=lambda self,*exc:failures.append(''.join(traceback.format_exception(*exc)))
    with patch.object(messagebox,'showerror',lambda *a,**k:failures.append(str(a))), \
         patch.object(messagebox,'showwarning',return_value=None), \
         patch.object(messagebox,'showinfo',return_value=None):
        app=runtime['_base'].ThermalConnectorApp();pump(app)
        app.hit_db=hit_core.HitDatabase(root/'TEST_ONLY_hit.b64')
        app.shared_thermal_design.show_legacy();group(app,'standard')
        if baseline:
            button(app.hit_standard_tab,'+ ZDX');row=app.hit_rows[0]
            row.required_length.set('500');row.ved_pos.set('20');row.ved_neg.set('10')
            entry(row,'ved_pos').event_generate('<FocusOut>');pump(app)
            wanted=choose(row);assert_choice(row,wanted)
            assert action_payload.save_action(app,as_new=True,forced_name='TEST_ONLY saved HIT 309')
            store=action_payload.action_store(app)
            saved=store.load(app.action_id)
            assert 'load_basis' not in saved['payload']['hit_design']['rows'][0]
            (root/'baseline.json').write_text(json.dumps(dict(id=app.action_id,wanted=wanted,database=str(store.path))),encoding='utf-8')
        else:
            import hit_units_310 as units
            engine(app.hit_db)
            data=json.loads((root/'baseline.json').read_text())
            store=action_payload.action_store(app)
            action_payload.load_action_record(app,store.load(data['id']))
            row=app.hit_rows[0]
            assert units.basis(row)=='per_metre';assert_choice(row,data['wanted'])
            assert hasattr(app,'hit_units_hint')
            assert int(row.load_basis_combo.grid_info()['column'])==10
            assert int(row.med_pos_entry.grid_info()['column'])==11
            headers={int(w.grid_info()['column']):str(w.cget('text')) for w in app.hit_rows_frame.winfo_children()
                     if isinstance(w,ttk.Label) and w.grid_info() and int(w.grid_info()['row'])==0}
            assert headers[10]=='Jednotky účinků¹' and headers[11].startswith('MEd+')
            # Same numbers, different units: 20 kN/500mm is 40 kN/m.
            row.load_basis_combo.current(1);row.load_basis_combo.event_generate('<<ComboboxSelected>>')
            expected=app.hit_db.proposal_candidates('ZDX','HP',200,30,'C25/30',hit_core.DirectionalActions(v_pos=40,v_neg=20),{50},False)[0]
            equivalent(row.candidates,expected)
            assert units.basis(row)=='per_element' and not row._manual_product
            assert row.ved_pos.get()=='20' and row.ved_neg.get()=='10'
            wanted=choose(row)
            row.quantity.set('25');entry(row,'quantity').event_generate('<FocusOut>')
            group(app,'aux');button(app.hit_aux_tab,'+ Přidat řádek');group(app,'standard');pump(app,.5)
            assert_choice(row,wanted);equivalent(row.candidates,expected)
            # Pending input callback must retain the explicit subsequent choice.
            row.ved_pos.set('21');row._input_changed();wanted=choose(row);pump(app,.5)
            assert_choice(row,wanted)
            # Unit state participates in a real input-change fingerprint.
            row.load_basis_combo.current(0);row.load_basis_combo.event_generate('<<ComboboxSelected>>')
            assert not row._manual_product and units.basis(row)=='per_metre'
            row.load_basis_combo.current(1);row.load_basis_combo.event_generate('<<ComboboxSelected>>')
            row.ved_pos.set('20');entry(row,'ved_pos').event_generate('<FocusOut>');wanted=choose(row)
            button(app.hit_standard_tab,'+ ZDX');other=app.hit_rows[-1]
            assert units.basis(other)=='per_element'  # Inherit choice for the next manually added row.
            other.load_basis_combo.current(0);other.load_basis_combo.event_generate('<<ComboboxSelected>>')
            other.ved_pos.set('40');other.ved_neg.set('20');other.required_length.set('500')
            entry(other,'ved_pos').event_generate('<FocusOut>')
            equivalent(row.candidates,other.candidates)
            # Changing units/data is scoped to the row, never the shared adapter.
            assert not units._ELEMENT_INPUT.get()
            shared=app.shared_thermal_design
            shared.values['basis'].set('Na jeden prvek');shared.update_hint()
            assert '/prvek' in shared.labels['moment'].cget('text')
            assert action_payload.save_action(app,as_new=True,forced_name='TEST_ONLY mixed units 310')
            saved=store.load(app.action_id)
            assert [r['load_basis'] for r in saved['payload']['hit_design']['rows']]==['per_element','per_metre']
            action_payload.load_action_record(app,saved);row,other=app.hit_rows
            assert_choice(row,wanted);assert row.quantity.get()=='25'
            assert units.basis(row)=='per_element' and units.basis(other)=='per_metre'
            app.recalculate_hit_all();assert_choice(row,wanted)
            import hit_export_ui,hit_pdf,hit_excel,pdf_scope
            report=hit_export_ui.collect_hit_rows(app)
            assert report[0]['actions']['v_pos']=='20'
            assert report[0]['actions_per_metre']['v_pos']==40
            assert hit_pdf._actions(report[0])[-2][2]=='kN/prvek'
            assert 'kN/prvek' in hit_pdf._input_summary(report[0])
            assert 'kN/m' in hit_pdf._input_summary(report[1])
            app.copy_hit_results();copied=app.clipboard_get()
            assert 'Jednotky V/N' in copied and 'kN/prvek' in copied and 'kNm/prvek' in copied
            actual=pdf_scope.rows_for_scope(app,'iso.design')
            assert next(r for r in actual if r.get('name')==row.name.get())['load_basis']=='per_element'
            target=ROOT/f'units310-{sys.platform}.pdf'
            hit_pdf.write_hit_proposal_pdf(target,project_name='TEST_ONLY jednotky HIT',rows=report)
            import pdfplumber
            with pdfplumber.open(target) as pdf:
                text='\n'.join(p.extract_text() or '' for p in pdf.pages)
            assert 'kN/prvek' in text and 'kN/m' in text and wanted in text
            target=ROOT/f'units310-{sys.platform}.xlsx'
            hit_excel.write_hit_request_xlsx(target,action_name='TEST_ONLY jednotky HIT',rows=report,include_statics=True)
            import openpyxl
            book=openpyxl.load_workbook(target,data_only=True);sheet=book['Statická data']
            table=list(sheet.values);headers=next(r for r in table if 'Jednotky V/N' in r)
            index=table.index(headers);a,b=table[index+1:index+3]
            assert a[headers.index('Jednotky V/N')]=='kN/prvek' and b[headers.index('Jednotky V/N')]=='kN/m'
            assert a[headers.index('VEd+')]==20 and b[headers.index('VEd+')]==40
            book.close()
            # Empty imported/legacy defaults continue using per-metre input.
            app.add_hit_row_for_type('ZDX')
            assert units.basis(app.hit_rows[-1])=='per_metre'
            # Reject nonfinite values, unsupported lengths and stale manual results.
            row.ved_pos.set('nan');entry(row,'ved_pos').event_generate('<FocusOut>')
            assert row.selected_candidate is None
            row.ved_pos.set('10000000');entry(row,'ved_pos').event_generate('<FocusOut>')
            assert row.selected_candidate is None
            row.ved_pos.set('20');row.required_length.set('330');entry(row,'required_length').event_generate('<FocusOut>')
            assert row.selected_candidate is None
            row.required_length.set('333');entry(row,'required_length').event_generate('<FocusOut>')
            assert row.candidates and all(c.physical_length_mm==333 for c in row.candidates)
            from PIL import ImageGrab
            ImageGrab.grab().save(ROOT/f'units310-window-{sys.platform}.png')
        assert not failures,failures
        app.destroy();del app,store
        logging.shutdown();gc.collect()


def main():
    cache={}
    def source(request,*a,**kw):
        u=urlparse(request.full_url if hasattr(request,'full_url') else str(request))
        assert u.netloc=='raw.githubusercontent.com'
        owner,repo,commit,*parts=u.path.strip('/').split('/')
        assert (owner,repo)==('jaroslavkucacz-code','TURTO-Izolacni-nosniky')
        key=commit+':'+ '/'.join(parts)
        if key not in cache:cache[key]=subprocess.check_output(['git','show',key],cwd=ROOT)
        return io.BytesIO(cache[key])
    with tempfile.TemporaryDirectory(prefix='turto310_') as tmp:
        root=Path(tmp);program=root/'Program'
        os.environ.update(TURTO_ROOT=str(root),TURTO_PROGRAM_DIR=str(program),APPDATA=str(root/'appdata'),
                          LOCALAPPDATA=str(root/'localappdata'),XDG_CONFIG_HOME=str(root/'xdg'))
        shutil.copytree(ROOT/'updates/1.1.17/catalogs',root/'catalogs');fixture(root)
        with patch('urllib.request.urlopen',source):
            runpy.run_path(str(ROOT/'updates/3.0.9/runtime_installer.py'))['install_runtime'](root)
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--baseline',str(root)],check=True)
        database=Path(json.loads((root/'baseline.json').read_text())['database'])
        assert database.resolve().is_relative_to(root.resolve())
        protected=[database,root/'TEST_ONLY_hit.b64']+[program/n for n in (
            'hit_core.py','hit_choice_309.py','shear_cover_308.py','isokorb_qp_307.py',
            'design_rows_306.py','turto_pdf_logo_305.png.b64','turto_icon_301.png.b64')]
        before={p:digest(p) for p in protected}
        with patch('urllib.request.urlopen',source):
            installer=runpy.run_path(str(REL/'runtime_installer.py'))
            installer['install_runtime'](root);installer['install_runtime'](root)
        assert before=={p:digest(p) for p in protected}
        shutil.copyfile(REL/'app.pyw',root/'app.pyw');(root/'.turto_runtime_current.ok').write_text('41')
        assert runpy.run_path(str(root/'app.pyw'))['_runtime_ready']()
        ui(root)
    report=dict(version='3.0.10',platform=sys.platform,checks=[
        'Actual 309 upgrade/idempotency and saved SQLite legacy manual choice; customer data/core/previous fixes/logos unchanged',
        'Per-element versus per-metre equivalence for 1000/500/333/250mm, real Annex 3 and TEST_ONLY moment interactions/offsets/fallbacks',
        'Real Tk row unit selector, header alignment, inherited defaults, quantities, pending timers and tab switching',
        'Mixed units SQLite round-trip, clipboard, scoped PDF text and Excel values/units',
        'Nonfinite/excessive loads, unsupported length, wrong cover and wrong shear direction rejected'])
    (ROOT/f'units310-test-{sys.platform}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--baseline':ui(Path(sys.argv[2]),baseline=True)
    else:main()
