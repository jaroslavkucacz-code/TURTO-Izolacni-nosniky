from __future__ import annotations

"""Actual Tk performance regression: count full-tree walks, not machine speed.
Uses TEST_ONLY capacities exclusively; no fixture is shipped in the runtime.
"""
import base64
import gc
import gzip
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
from unittest.mock import patch

from verify_hit_choice_309 import pump, group, entry, choose, assert_choice
ROOT = Path(__file__).resolve().parents[1]
REL = ROOT/'updates/3.0.11'
COUNT = 80


def ui(root, baseline=False):
    sys.path.insert(0,str(root/'Program'))
    runtime=runpy.run_path(str(root/'Program/app_runtime.pyw'));runtime['selftest']()
    import tkinter as tk
    from tkinter import ttk,messagebox
    import hit_core,hit_workspace,hit_units_310,table_controls,action_payload,hit_export_ui
    errors=[]
    tk.Tk.report_callback_exception=lambda self,*exc:errors.append(''.join(traceback.format_exception(*exc)))
    with patch.object(messagebox,'showerror',lambda *a,**k:errors.append(str(a))), \
         patch.object(messagebox,'showwarning',return_value=None), \
         patch.object(messagebox,'showinfo',return_value=None):
        app=runtime['_base'].ThermalConnectorApp();app.geometry('1400x880');pump(app)
        app.main_notebook.select(app.hit_tab);pump(app)
        app.hit_db=hit_core.HitDatabase(root/'TEST_ONLY_hit.b64')
        shared=app.shared_thermal_design;shared.show_legacy();group(app,'standard')
        assert app.hit_canvas.winfo_ismapped() and app.hit_canvas.winfo_height()>50
        assert app._turto_universal_tables_224_installed
        stats={'scans':0,'visits':0,'calculations':0,'notebook_unmaps':0}
        original_scan=table_controls.scan; original_walk=table_controls._walk_widgets
        original_calc=app.hit_db.proposal_candidates
        def scan(*args):stats['scans']+=1;return original_scan(*args)
        def walk(*args):
            for widget in original_walk(*args):stats['visits']+=1;yield widget
        def calculate(*args,**kw):stats['calculations']+=1;return original_calc(*args,**kw)
        def unmap(event):
            if event.widget is app.hit_design_notebook:stats['notebook_unmaps']+=1
        app.hit_design_notebook.bind('<Unmap>',unmap,add='+')
        def snapshot():
            return [(r.name.get(),r.quantity.get(),hit_units_310.basis(r),r.product.get(),r.util.get(),
                     r.selected_candidate.utilization,r._manual_product) for r in app.hit_rows]
        with patch.object(table_controls,'scan',scan),patch.object(table_controls,'_walk_widgets',walk), \
             patch.object(app.hit_db,'proposal_candidates',calculate):
            start=time.perf_counter()
            for i in range(COUNT):
                row=hit_workspace.HitInputRow(app,i+1,dict(name=f'TEST_ONLY {i+1:03}',connection_type='ZDX',
                    series='HP',height='200',cover='30',concrete='C25/30',required_length='500',quantity='2',
                    ved_pos='20',ved_neg='10',load_basis='per_element' if i%2==0 else 'per_metre'))
                app.hit_rows.append(row)
            app._hit_reconfigure_row_minsizes();app.recalculate_hit_all();pump(app,.15)
            assert len(app.hit_rows)==COUNT and all(r.selected_candidate for r in app.hit_rows)
            row=app.hit_rows[0];wanted=choose(row);pump(app)
            initial=dict(stats);load_seconds=time.perf_counter()-start
            print('Initial', '310' if baseline else '311', initial, 'seconds',round(load_seconds,3),flush=True)
            before=snapshot();calc_start=stats['calculations']
            for _ in range(3):
                group(app,'aux');group(app,'wt');group(app,'standard')
            pump(app,.1)
            assert snapshot()==before;assert_choice(row,wanted)
            if not baseline:
                assert stats['notebook_unmaps']==0,stats
                assert stats['calculations']==calc_start,stats
            # Wheel and track/thumb/programmatic moves must all mount the viewport.
            def visible():
                canvas=app.hit_canvas;h=canvas.winfo_height();y0=canvas.canvasy(0)
                visible_rows=[r for r in app.hit_rows if y0 <= app.hit_rows_frame.grid_bbox(0,r.row_no,0,r.row_no)[1] < y0+h]
                assert visible_rows,(y0,h,canvas.cget('scrollregion'),app.hit_rows_frame.grid_bbox(),errors)
                assert all(r.product_combo.winfo_ismapped() for r in visible_rows),[(r.row_no,r._hit_grid_visible) for r in visible_rows]
            width=app.hit_rows_frame.winfo_reqwidth()
            for fraction in (.25,.7,1.0,.4,0.0):
                app.hit_canvas.yview_moveto(fraction)
                if baseline:app._hit_schedule_virtual_refresh() # Old thumb path only.
                pump(app,.05)
                if not baseline:
                    visible();assert app.hit_rows_frame.winfo_reqwidth()>=width
                    assert stats['scans']<=initial['scans']+1,stats
            for delta in (-120,-120,120):
                app._on_hit_mousewheel(SimpleNamespace(delta=delta));pump(app)
                if not baseline:visible()
            assert snapshot()==before;assert stats['calculations']==calc_start,stats
            scroll_stats=dict(stats)
            if not baseline:
                # Small moves reuse the buffered rows; hidden tabs retain their mapping.
                mounted=tuple(r._hit_grid_visible for r in app.hit_rows)
                group(app,'aux');app._hit_schedule_virtual_refresh();pump(app)
                assert mounted==tuple(r._hit_grid_visible for r in app.hit_rows)
                group(app,'standard')
                app.hit_canvas.yview_moveto(0);pump(app)
                row.ved_pos_entry.focus_force();pump(app)
                app.hit_canvas.yview_moveto(1);pump(app);visible()
                assert row.ved_pos_entry.winfo_manager()=='grid'  # No synthetic FocusOut while scrolling.
                app.hit_canvas.focus_force();app.hit_canvas.yview_moveto(0);pump(app)
                for geometry in ('1100x680','1550x900','1200x740'):
                    app.geometry(geometry);pump(app);visible()
                assert snapshot()==before
                # Real edits still recalculate and invalidate an old manual result.
                row.ved_pos.set('1000000');entry(row,'ved_pos').event_generate('<FocusOut>');pump(app)
                assert row.selected_candidate is None and stats['calculations']>calc_start
                row.ved_pos.set('20');entry(row,'ved_pos').event_generate('<FocusOut>');wanted=choose(row)
                # Pending calculation survives a tab change and is then retained.
                row.ved_pos.set('21');row._input_changed();group(app,'aux');group(app,'standard');pump(app,.4)
                assert row.selected_candidate and row.ved_pos.get()=='21'
                wanted=choose(row);pump(app,.4);assert_choice(row,wanted)
                # Removing/adding a row and reloading the same row count invalidate viewport caches.
                app.remove_hit_row(app.hit_rows[-1]);app.add_hit_row_for_type('ZDX');pump(app)
                assert len(app.hit_rows)==COUNT;app.hit_canvas.yview_moveto(1);pump(app);visible()
                app.remove_hit_row(app.hit_rows[-1]);pump(app)
                assert action_payload.save_action(app,as_new=True,forced_name='TEST_ONLY smooth 311')
                store=action_payload.action_store(app);saved=store.load(app.action_id)
                action_payload.load_action_record(app,saved);pump(app)
                assert len(app.hit_rows)==COUNT-1;assert_choice(app.hit_rows[0],wanted)
                assert hit_units_310.basis(app.hit_rows[0])=='per_element'
                app.hit_canvas.yview_moveto(.6);pump(app);visible()
                report=hit_export_ui.collect_hit_rows(app)
                assert report[0]['input_units']['v_pos']=='kN/prvek' and report[0]['actions_per_metre']['v_pos']==42
                # A new Treeview still gains sorting/column controls exactly once.
                win=tk.Toplevel(app);tree=ttk.Treeview(win,columns=('value',),show='headings');tree.pack()
                tree.heading('value',text='Hodnota');tree.insert('','end',iid='a',values=('10',));tree.insert('','end',iid='b',values=('2',));pump(app)
                controller=table_controls.controller_for(app,tree);assert controller is not None
                controller.sort('value',False);assert tree.get_children()==('b','a')
                win.withdraw();win.deiconify();pump(app);assert table_controls.controller_for(app,tree) is controller
                win.destroy()
                # Refresh storms schedule only one reapply, preserving existing controls.
                with patch.object(table_controls,'reapply') as reapply:
                    for _ in range(20):table_controls._schedule_reapply(app)
                    pump(app);assert reapply.call_count==1,reapply.call_count
                # Auxiliary and wall modules retain their own edits and navigation.
                group(app,'aux');app.add_aux_row_for_type('HT');aux=app.aux_rows[-1]
                aux.hed_parallel.set('5');aux.recalculate();assert aux.selected_candidate
                group(app,'wt');app.add_wt_row();wt=app.wt_rows[-1]
                wt.med_neg.set('5');wt.recalculate();assert wt.selected_candidate
                group(app,'standard');group(app,'aux');assert aux.selected_candidate
                group(app,'wt');assert wt.selected_candidate;group(app,'standard')
                from PIL import ImageGrab
                ImageGrab.grab().save(ROOT/f'smooth311-window-{sys.platform}.png')
            assert not errors,errors
            result={'initial':initial,'scroll':scroll_stats,'load_seconds':round(load_seconds,3),'rows':COUNT}
            if baseline:
                (root/'baseline311.json').write_text(json.dumps(result))
            else:
                old=json.loads((root/'baseline311.json').read_text())
                assert old['initial']['scans']>40,old
                assert initial['scans']<=3,result
                assert initial['visits']<old['initial']['visits']/10,(old,result)
                result={'baseline310':old,'current311':result,'checks':['80 mixed-unit HIT rows, real Tk map/scroll/tab/resize',
                    'At least 10x fewer widget-walk visits; no calculation on navigation',
                    'Manual choices, pending edits, dynamic tables and SQLite/export data preserved']}
                (ROOT/f'smooth311-test-{sys.platform}.json').write_text(json.dumps(result,indent=2))
                print(json.dumps(result,indent=2))
        app.destroy();del app
        logging.shutdown();gc.collect()


def main():
    cache={}
    def source(request,*a,**kw):
        u=urlparse(request.full_url if hasattr(request,'full_url') else str(request));assert u.netloc=='raw.githubusercontent.com'
        owner,repo,commit,*parts=u.path.strip('/').split('/');assert (owner,repo)==('jaroslavkucacz-code','TURTO-Izolacni-nosniky')
        key=commit+':'+ '/'.join(parts)
        if key not in cache:cache[key]=subprocess.check_output(['git','show',key],cwd=ROOT)
        return io.BytesIO(cache[key])
    with tempfile.TemporaryDirectory(prefix='turto311_') as folder:
        root=Path(folder);program=root/'Program'
        os.environ.update(TURTO_ROOT=str(root),TURTO_PROGRAM_DIR=str(program),APPDATA=str(root/'appdata'),
                          LOCALAPPDATA=str(root/'localappdata'),XDG_CONFIG_HOME=str(root/'xdg'))
        shutil.copytree(ROOT/'updates/1.1.17/catalogs',root/'catalogs')
        data={'schema_version':4,'source_document':'TEST_ONLY UI FIXTURE; NOT FOR DESIGN','zvx_records':[
            {'series':'HP','concrete':'C25/30','length_code':length,'h_min':160,'h_max':300,'vrd':capacity,'code':code,'diameter':'08','page':0}
            for length in (100,50,33,25) for code,capacity in [('0202',100.0),('0302',200.0)]]}
        (root/'TEST_ONLY_hit.b64').write_bytes(base64.b64encode(gzip.compress(json.dumps(data).encode())))
        with patch('urllib.request.urlopen',source):runpy.run_path(str(ROOT/'updates/3.0.10/runtime_installer.py'))['install_runtime'](root)
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--baseline',str(root)],check=True)
        protected=[p for p in program.iterdir() if p.name in ('hit_core.py','hit_choice_309.py','hit_units_310.py','hit_excel.py','turto_pdf_logo_305.png.b64')]
        before={p:p.read_bytes() for p in protected}
        with patch('urllib.request.urlopen',source):
            installer=runpy.run_path(str(REL/'runtime_installer.py'));installer['install_runtime'](root);installer['install_runtime'](root)
        assert before=={p:p.read_bytes() for p in protected}
        shutil.copyfile(REL/'app.pyw',root/'app.pyw');(root/'.turto_runtime_current.ok').write_text('42')
        assert runpy.run_path(str(root/'app.pyw'))['_runtime_ready']()
        ui(root)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--baseline':ui(Path(sys.argv[2]),True)
    else:main()
