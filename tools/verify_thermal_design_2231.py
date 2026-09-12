from __future__ import annotations

"""Offline installed UI, guarded adapters, persistence and update regression.

HIT numeric fixtures below are SYNTHETIC TEST VALUES, never product data.
Peikko tests use the immutable reviewed 2.2.30 data without modifying it.
"""
from contextlib import ExitStack
import gc
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
import urllib.parse
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'updates/2.2.31'


def raises(call, text=''):
    try:call()
    except ValueError as exc:
        assert text.lower() in str(exc).lower(), (text,str(exc))
    else:raise AssertionError('Expected a guarded rejection: '+text)


def engines():
    from thermal_design import DEFAULTS, FUNCTIONS, common, peikko_candidates, leviat_candidates
    from hit_core import HitDatabase, DirectionalActions
    q={**DEFAULTS,'moment':'-19','shear':'21','cover':'30'}
    original=dict(q);rows=peikko_candidates(q);assert rows and q==original
    assert all(not r['design_verified'] and '30/25' in r['detail'] for r in rows)
    for change in ({'moment':'nan'},{'shear':'inf'},{'height':'0'},{'height':'201'},
        {'cover':'35'},{'axial':'1'},{'family':'TEBEA'},{'function':FUNCTIONS[1]},
        {'arrangement':'Vlastní rozteč','spacing':'400'}):
        raises(lambda change=change:peikko_candidates({**q,**change}))
    assert all('požár k ověření' in r['status'] for r in peikko_candidates({**q,'fire':'REI120'}))
    # Exact products remain exact; imported nonstandard clauses never disappear.
    exact={**q,'designation':'EBEA-100 RS 4x10-2 D200 SW80 L500','length':'500','geometry':'1'}
    checked=peikko_candidates(exact);assert len(checked)==1
    first=checked[0]['comparison']
    equivalent=peikko_candidates({**exact,'basis':'Na jeden prvek','moment':'-9.5','shear':'10.5'})[0]['comparison']
    assert first['eta_M']==equivalent['eta_M'] and first['eta_V']==equivalent['eta_V']
    spaced=peikko_candidates({**exact,'arrangement':'Vlastní rozteč','spacing':'1000'})[0]['comparison']
    assert math.isclose(spaced['eta_M'],2*first['eta_M'])
    for change in ({'geometry':'0'},{'insulation':'120'},{'length':'1000'},{'material':'VE1'},
        {'designation':exact['designation']+' OQ'},{'designation':exact['designation'].replace('EBEA-100','EBEA-100-B2')},
        {'designation':exact['designation'].replace(' D200',' Ds200 Dt200')},
        {'designation':exact['designation'].replace('4x10-2','99x10-2')}):
        raises(lambda change=change:peikko_candidates({**exact,**change}))
    for function,cover in ((FUNCTIONS[2],'45'),(FUNCTIONS[3],'30')):
        found=peikko_candidates({**q,'function':function,'cover':cover,'moment':'-1','shear':'1'})
        assert found
        if function==FUNCTIONS[3]:assert all('S11=' in r['designation'] for r in found)
    # Native HIT engine with explicitly synthetic rows, separate from production data.
    db=HitDatabase.__new__(HitDatabase);db.data={};db.schema_version=4
    db.source_document='SYNTHETIC TEST FIXTURE - NOT PRODUCT DATA'
    db.records=[[series,'0404',length,'',200-cover,concrete,-40,200,-100,120,1]
        for series in ('HP','SP') for length in (100,50) for cover in (30,35,50)
        for concrete in ('C20/25','C25/30','C30/37')]
    db.mvxl_records=[];db.dd_moment=[];db.dvl_moment=[]
    db.zvx_records=[dict(series='HP',concrete='C25/30',length_code=100,h_min=160,h_max=250,
        vrd=100,code='0404',diameter='06',page=1)]
    direct,error,_=db.proposal_candidates('MVX','HP',200,30,'C25/30',DirectionalActions(m_neg=19,v_pos=21),{100})
    assert not error and direct
    hit=leviat_candidates({**q,'hit_type':'MVX'},db)
    assert len(hit)==1 and hit[0]['utilization']==direct[0].utilization
    assert hit[0]['designation'].startswith('HIT-HP')
    assert leviat_candidates({**q,'insulation':'120'},db)[0]['designation'].startswith('HIT-SP')
    half=leviat_candidates({**q,'length':'500','basis':'Na jeden prvek','moment':'-9.5','shear':'10.5'},db)
    assert half and half[0]['utilization']==hit[0]['utilization']
    assert all(r['candidate'].cover==35 for r in leviat_candidates({**q,'cover':'35'},db))
    assert all(r['candidate'].concrete=='C20/25' for r in leviat_candidates({**q,'concrete':'C20/25'},db))
    shear=leviat_candidates({**q,'function':FUNCTIONS[1],'moment':'0'},db)
    assert shear and all(r['candidate'].suffix=='06' for r in shear), 'Diameter suffix must not be rejected as an offset'
    raises(lambda:leviat_candidates({**q,'axial':'1'},db),'NEd')
    raises(lambda:leviat_candidates(q,None),'načtena')
    assert not leviat_candidates({**q,'designation':'HIT-HP MVX-not-a-real-type'},db)
    return db


def main():
    cache={};reads=[]
    def urlopen(request,*args,**kwargs):
        url=request.full_url if hasattr(request,'full_url') else str(request);reads.append(url)
        parsed=urllib.parse.urlparse(url);assert parsed.netloc=='raw.githubusercontent.com'
        parts=parsed.path.strip('/').split('/');assert parts[:2]==['jaroslavkucacz-code','TURTO-Izolacni-nosniky']
        key=parts[2]+':'+('/'.join(parts[3:]))
        if key not in cache:cache[key]=subprocess.check_output(['git','show',key],cwd=ROOT)
        return io.BytesIO(cache[key])
    with tempfile.TemporaryDirectory(prefix='turto_shared_231_') as folder, ExitStack() as cleanup:
        cleanup.callback(gc.collect);cleanup.callback(logging.shutdown)
        root=Path(folder);program=root/'Program'
        os.environ.update(TURTO_ROOT=str(root),TURTO_PROGRAM_DIR=str(program),APPDATA=str(root/'appdata'),LOCALAPPDATA=str(root/'localappdata'))
        shutil.copytree(ROOT/'updates/1.1.17/catalogs',root/'catalogs')
        with patch('urllib.request.urlopen',urlopen):runpy.run_path(str(ROOT/'updates/2.2.30/runtime_installer.py'))['install_runtime'](root)
        (root/'.turto_runtime_current.ok').write_text('21',encoding='utf-8')
        database=root/'actions.sqlite3';database.write_bytes(b'TEST CUSTOMER DATABASE SENTINEL')
        before=database.read_bytes()
        if (RELEASE/'runtime_installer.py').exists():
            with patch('urllib.request.urlopen',urlopen):
                installer=runpy.run_path(str(RELEASE/'runtime_installer.py'));installer['selftest']()
                n=len(reads);installer['install_runtime'](root);assert len(reads)-n==3
                assert installer['_revision_ok'](program) and database.read_bytes()==before
                n=len(reads);installer['install_runtime'](root);assert len(reads)==n
                # Transaction rollback on a failed atomic replacement.
                (program/'app_runtime.pyw').write_bytes((ROOT/'updates/2.2.30/app_runtime.pyw').read_bytes())
                old={name:(program/name).read_bytes() for name in installer['PAYLOADS']}
                original_replace=os.replace;failed=False
                def fail_once(source,target):
                    nonlocal failed
                    if not failed and Path(target).name=='thermal_design_ui.py':failed=True;raise OSError('Injected replacement failure')
                    return original_replace(source,target)
                with tempfile.TemporaryDirectory() as temp, patch('os.replace',fail_once):
                    try:installer['_install_payloads'](program,Path(temp))
                    except OSError:pass
                    else:raise AssertionError('Expected injected failure')
                assert all((program/name).read_bytes()==value for name,value in old.items())
                (program/'thermal_design.py').write_text('# damaged',encoding='utf-8')
                assert not installer['_revision_ok'](program)
                installer['install_runtime'](root);assert installer['_revision_ok'](program)
                assert database.read_bytes()==before
            shutil.copy2(RELEASE/'app.pyw',root/'app.pyw')
            bootstrap=runpy.run_path(str(root/'app.pyw'));bootstrap['selftest']();assert bootstrap['_runtime_ready']()
        else:
            for name in ('app_runtime.pyw','thermal_design.py','thermal_design_ui.py'):shutil.copy2(RELEASE/name,program/name)
        database.unlink()  # remove fake sentinel before exercising real SQLite below
        sys.path.insert(0,str(program))
        ns=runpy.run_path(str(program/'app_runtime.pyw'));ns['selftest']();hit=engines()
        import tkinter as tk
        from tkinter import messagebox
        failures=[];dialogs=[]
        tk.Tk.report_callback_exception=lambda self,*args:failures.append(args)
        with patch.object(messagebox,'showwarning',lambda *a,**k:dialogs.append(a)),patch.object(messagebox,'showerror',lambda *a,**k:dialogs.append(a)):
            app=ns['_base'].ThermalConnectorApp();cleanup.callback(app.destroy);app.update()
            app.geometry('1180x704');app.main_notebook.select(app.hit_tab);app.update()
            u=app.shared_thermal_design;v=u.values;widgets=dict(u.widgets)
            assert tuple(widgets)==('function','height','insulation','concrete','cover','moment','shear','axial','fire','basis')
            app.hit_db=hit
            v['moment'].set('-19');v['shear'].set('21');v['cover'].set('30')
            for name in ('Leviat','Peikko','Leviat','Peikko'):
                app.design_manufacturer_var.set(name);app.update();u.run();app.update()
                assert u.widgets==widgets and u.winfo_ismapped() and u.results
                assert v['moment'].get()=='-19' and v['shear'].get()=='21'
                assert not app._peikko_shared_panels['design'][1].winfo_ismapped()
                assert not any(w.winfo_ismapped() for w in app._peikko_shared_panels['design'][2])
                assert u.output.winfo_height()>=35 and u.tree.winfo_height()>=35
                for b in u.buttons.values():assert b.winfo_rooty()+b.winfo_height()<=app.hit_tab.winfo_rooty()+app.hit_tab.winfo_height()
            assert not app._load_hit_data(root/'missing-test-data',quiet=True)
            assert not u.results and app.hit_db is None
            app.hit_db=hit
            v['fire'].set('REI120');assert not u.results
            u.run();u.add();assert len(app.project.rows)==1
            app.project_concrete_var.set('C20/25');assert v['concrete'].get()=='C20/25' and not u.results
            v['concrete'].set('C25/30');assert app.project_concrete_var.get()=='C25/30'
            v['basis'].set('Na jeden prvek');assert '/ks' in u.labels['moment'].cget('text');v['basis'].set('Na metr spoje')
            u.open_advanced();app.update();assert u.advanced.winfo_exists();u.advanced.destroy()
            u.show_legacy(True);app.update();assert app._peikko_shared_panels['design'][1].winfo_ismapped()
            u.show_common();app.update();assert u.winfo_ismapped()
            app.design_manufacturer_var.set('Leviat');u.show_legacy();app.update()
            assert any(w.winfo_ismapped() for w in app._peikko_shared_panels['design'][2]);u.show_common()
            app.design_manufacturer_var.set('Peikko')
            # Original 14 reference rows, exact import, unknown clauses and persistence.
            fixture=runpy.run_path(str(ROOT/'tools/verify_peikko_2229.py'),run_name='fixture_only')
            sys.path[:]=[str(program)]+[p for p in sys.path if p not in {str(program),str(ROOT/'updates/2.2.29'),str(ROOT/'updates/1.1.17')}]
            from bulk_import_engine import analyze_bulk_text_progressive
            from project_model import create_project_row
            items,skipped,cancelled=analyze_bulk_text_progressive(app.database,fixture['pasted_samples'](),preferred_concrete='C25/30')
            assert len(items)==14 and all(i.ready for i in items)
            for item in items:app.project.add(create_project_row(item.result,position=item.position,source_text=item.source_designation))
            app.refresh_project_tree();app.project_tree.selection_set(app.project.rows[1]['id'])
            u.from_decoder();assert 'OQ' in v['designation'].get() and v['D'].get()==''
            u.run();assert not u.results
            v['D'].set('200');v['geometry'].set('1');u.run();assert not u.results
            from action_payload import serialize_action,load_action_record,save_action,action_store
            from action_store import ActionStore
            snapshot=u.snapshot();project=app.project;app.project_dirty=True
            with patch.object(messagebox,'askyesnocancel',lambda *a,**k:None):app.new_action()
            assert app.project is project and u.snapshot()==snapshot and app.project_dirty
            payload=serialize_action(app);assert payload['thermal_design_inputs']==snapshot
            store=ActionStore(root/'roundtrip.sqlite3');saved=store.save(action_name='Shared input test',payload=payload);record=store.load(saved['id'])
            with patch.object(messagebox,'askyesnocancel',lambda *a,**k:False):app.new_action()
            assert not app.project.rows and v['moment'].get()=='0'
            load_action_record(app,record);app.update()
            assert u.snapshot()==snapshot and len(app.project.rows)==15 and not u.results
            assert not app.project_dirty
            v['moment'].set('-18');assert save_action(app,as_new=True,forced_name='Shared save command')
            saved_record=action_store(app).load(app.action_id)
            assert saved_record['payload']['thermal_design_inputs']['inputs']['moment']=='-18'
            old=dict(record);old['payload']=dict(record['payload']);old['payload'].pop('thermal_design_inputs')
            load_action_record(app,old);assert v['moment'].get()=='0'
            # Original runtime remains usable; no dedicated Peikko main tab returns.
            assert len(app.main_notebook.tabs())==3
            import shear_dowels_current
            shear_dowels_current.selftest()
            app.main_notebook.select(app.substitution_tab);app.substitution_manufacturer_var.set('Peikko');app.update()
            assert app._peikko_shared_panels['substitution'][1].winfo_ismapped()
            assert callable(app.rebuild_hit_data) and callable(app.open_shear_design_schedule)
            assert not failures,failures
            assert not dialogs,dialogs
    print('OK 2.2.31: common widgets, native HIT parity, Peikko guards, 14 imports, SQLite save/load, cancelled new, update/repair/rollback.')


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
