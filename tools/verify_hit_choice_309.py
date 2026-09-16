from __future__ import annotations

"""Real Tk/SQLite regression and 3.0.8 -> 3.0.9 update.
The two ZDX rows are TEST_ONLY UI fixtures, never shipped as design data.
HT/WT use the existing bundled tables. A real display is required.
"""
import base64
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
REL = ROOT / 'updates/3.0.9'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def pump(app, seconds=0.05):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        app.update()
        time.sleep(.01)


def button(parent, text):
    from tkinter import ttk
    found = [w for w in walk(parent) if isinstance(w, ttk.Button) and str(w.cget('text')) == text]
    assert len(found) == 1, (text, len(found))
    found[0].invoke()


def group(app, key):
    app.shared_thermal_design.hit_group_buttons[key].invoke()
    pump(app)


def entry(row, variable):
    from tkinter import ttk
    return next(w for w in walk(row.owner) if isinstance(w, ttk.Entry)
                and str(w.cget('textvariable')) == str(getattr(row, variable)))


def choose(row, index=1):
    assert len(row.candidates) > index, [c.designation for c in row.candidates]
    wanted = row.candidates[index].designation
    row.product_combo.current(index)
    row.product_combo.event_generate('<<ComboboxSelected>>')
    assert row.product.get() == wanted
    return wanted


def assert_choice(row, wanted):
    assert row.product.get() == wanted, (row.product.get(), wanted)
    assert row.selected_candidate.designation == wanted
    assert getattr(row, '_manual_product', getattr(row, 'manual_product', False))


def user_sequence(app, row):
    # FocusOut is the actual Tk binding caused by leaving the field/tab. Send it
    # explicitly too, so headless window managers cannot skip the regression.
    entry(row, 'ved_pos').event_generate('<FocusOut>')
    group(app, 'aux')
    button(app.hit_aux_tab, '+ HT')
    group(app, 'standard')
    pump(app, .5)


def ui(root, baseline=False):
    sys.path.insert(0, str(root/'Program'))
    runtime = runpy.run_path(str(root/'Program/app_runtime.pyw'))
    runtime['selftest']()
    import tkinter as tk
    from tkinter import messagebox
    import action_payload, hit_core
    errors = []
    tk.Tk.report_callback_exception = lambda self,*exc: errors.append(''.join(traceback.format_exception(*exc)))
    with patch.object(messagebox, 'showerror', lambda *a,**kw:errors.append(str(a))), \
         patch.object(messagebox, 'showwarning', return_value=None), \
         patch.object(messagebox, 'showinfo', return_value=None):
        app = runtime['_base'].ThermalConnectorApp()
        pump(app)
        app.hit_db = hit_core.HitDatabase(root/'TEST_ONLY_hit.b64')
        app.shared_thermal_design.show_legacy()
        group(app, 'standard')
        if baseline:
            assert not app.hit_rows and not app.aux_rows and not app.wt_rows
            app.hit_l033_var.set(True)
            button(app.hit_standard_tab, '+ ZDX')
            row = app.hit_rows[0]
            row.ved_pos.set('10'); row.ved_neg.set('10')
            entry(row, 'ved_pos').event_generate('<FocusOut>')
            pump(app)
            wanted = choose(row)
            assert_choice(row, wanted)
            assert action_payload.save_action(app, as_new=True, forced_name='TEST_ONLY manual HIT 308')
            record_id = app.action_id
            user_sequence(app, row)
            assert row.product.get() != wanted and not row._manual_product
            (root/'baseline.json').write_text(json.dumps({'id':record_id, 'wanted':wanted}), encoding='utf-8')
            assert not errors, errors
        else:
            data = json.loads((root/'baseline.json').read_text())
            store = action_payload.action_store(app)
            action_payload.load_action_record(app, store.load(data['id']))
            row = app.hit_rows[0]
            wanted = data['wanted']
            assert_choice(row, wanted)
            group(app, 'standard')
            user_sequence(app, row)
            assert_choice(row, wanted)
            row.name.set('TEST_ONLY renamed')
            row.quantity.set('2')
            for var in ('name', 'quantity', 'ved_pos'):
                entry(row, var).event_generate('<FocusOut>')
            pump(app, .5)
            assert_choice(row, wanted)

            # Change a structural input, then choose before its timer fires.
            row.ved_pos.set('11')
            row._input_changed()  # Same bound KeyRelease handler; no WM focus dependency.
            assert row._after_id and not row._manual_product
            wanted = choose(row)
            assert row._after_id is None
            pump(app, .6)
            assert_choice(row, wanted)
            assert abs(row.selected_candidate.utilization - 11/200) < 1e-8

            # Select from the real modal dialog, and separately close without use.
            import hit_workspace
            def dialog_action(index=None):
                dialog = next(w for w in walk(app) if isinstance(w, hit_workspace.HitVariantsDialog))
                if index is not None:
                    dialog.tree.selection_set(dialog.tree.get_children()[index])
                button(dialog, 'Zavřít' if index is None else 'Použít variantu')
            app.after(150, lambda:dialog_action(0))
            row.variants_button.invoke()
            first = row.candidates[0].designation
            assert_choice(row, first)
            app.recalculate_hit_all()
            assert_choice(row, first)
            app.after(150, dialog_action)
            row.variants_button.invoke()
            assert_choice(row, first)
            wanted = choose(row)

            # Real input edits retain the existing automatic recalculation rules.
            row.ved_pos.set('12')
            entry(row, 'ved_pos').event_generate('<FocusOut>')
            assert not row._manual_product and row.product.get() == row.candidates[0].designation
            choose(row)
            row.ved_pos.set('1000000'); row.ved_neg.set('1000000')
            entry(row, 'ved_pos').event_generate('<FocusOut>')
            assert row.selected_candidate is None and not row._manual_product
            row.ved_pos.set('10'); row.ved_neg.set('10')
            entry(row, 'ved_pos').event_generate('<FocusOut>')
            wanted = choose(row)

            group(app, 'aux')
            aux = app.aux_rows[0]
            aux.hed_parallel.set('1')
            entry(aux, 'hed_parallel').event_generate('<FocusOut>')
            aux_wanted = choose(aux)
            entry(aux, 'hed_parallel').event_generate('<FocusOut>')
            aux.name.set('TEST_ONLY HT'); aux.quantity.set('3')
            entry(aux, 'quantity').event_generate('<FocusOut>')
            group(app, 'wt')
            button(app.hit_wt_tab, '+ Přidat WT')
            wt = app.wt_rows[0]
            wt.med_neg.set('1')
            entry(wt, 'med_neg').event_generate('<FocusOut>')
            wt_wanted = choose(wt)
            wt.name.set('TEST_ONLY WT'); wt.quantity.set('4')
            entry(wt, 'quantity').event_generate('<FocusOut>')
            entry(wt, 'med_neg').event_generate('<FocusOut>')
            group(app, 'standard')
            pump(app, .5)
            expected = (wanted, aux_wanted, wt_wanted)
            for item, name in zip((row, aux, wt), expected):
                assert_choice(item, name)
            assert action_payload.save_action(app, as_new=True, forced_name='TEST_ONLY all manual HIT 309')
            saved = store.load(app.action_id)
            assert saved['hit_count'] == 3
            action_payload.load_action_record(app, saved)
            assert tuple(len(x) for x in (app.hit_rows, app.aux_rows, app.wt_rows)) == (1,1,1)
            # These are also the refreshes performed before the legacy PDF export.
            app.recalculate_hit_all(); app.recalculate_aux_all(); app.recalculate_wt_all()
            rows = (app.hit_rows[0], app.aux_rows[0], app.wt_rows[0])
            for item, name, qty in zip(rows, expected, ('2','3','4')):
                assert_choice(item, name)
                assert item.quantity.get() == qty
            import hit_export_ui
            exported = hit_export_ui.collect_all_hit_rows(app)
            assert len(exported) == 3
            assert {r['candidate']['designation'] for r in exported} == set(expected)
            assert not errors, errors
            del store
        app.destroy()
        del app
        logging.shutdown()
        gc.collect()


def main():
    cache = {}
    def source(request, *args, **kwargs):
        url = urlparse(request.full_url if hasattr(request, 'full_url') else str(request))
        assert url.netloc == 'raw.githubusercontent.com'
        owner, repo, commit, *parts = url.path.strip('/').split('/')
        assert (owner,repo) == ('jaroslavkucacz-code','TURTO-Izolacni-nosniky')
        key = commit+':'+ '/'.join(parts)
        if key not in cache:
            cache[key] = subprocess.check_output(['git','show',key],cwd=ROOT)
        return io.BytesIO(cache[key])
    with tempfile.TemporaryDirectory(prefix='turto309_') as folder:
        root = Path(folder); program = root/'Program'
        os.environ.update(TURTO_ROOT=str(root),TURTO_PROGRAM_DIR=str(program),
                          APPDATA=str(root/'appdata'),LOCALAPPDATA=str(root/'localappdata'))
        shutil.copytree(ROOT/'updates/1.1.17/catalogs',root/'catalogs')
        data = {'schema_version':4,'source_document':'TEST_ONLY UI fixture; NOT FOR DESIGN','zvx_records':[
            {'series':'HP','concrete':'C25/30','length_code':33,'h_min':160,'h_max':300,
             'vrd':capacity,'code':code,'diameter':'08','page':0}
            for code,capacity in [('0202',100.0),('0302',200.0)]]}
        (root/'TEST_ONLY_hit.b64').write_bytes(base64.b64encode(gzip.compress(json.dumps(data).encode())))
        with patch('urllib.request.urlopen',source):
            runpy.run_path(str(ROOT/'updates/3.0.8/runtime_installer.py'))['install_runtime'](root)
        # Real updates restart Python: old runtime patches must stay in a child.
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--baseline',str(root)],check=True)
        protected = [root/'actions.sqlite3',root/'TEST_ONLY_hit.b64'] + [program/name for name in (
            'isokorb_qp_307.py','schoeck_t_qp_307.json','shear_cover_308.py','design_rows_306.py',
            'turto_pdf_logo_305.png.b64','turto_icon_301.png.b64')]
        before = {p:digest(p) for p in protected}
        with patch('urllib.request.urlopen',source):
            installer = runpy.run_path(str(REL/'runtime_installer.py'))
            installer['install_runtime'](root); installer['install_runtime'](root)
        assert before == {p:digest(p) for p in protected}
        shutil.copyfile(REL/'app.pyw',root/'app.pyw')
        (root/'.turto_runtime_current.ok').write_text('40')
        assert runpy.run_path(str(root/'app.pyw'))['_runtime_ready']()
        ui(root)
    report = {'version':'3.0.9','platform':sys.platform,'checks':[
        'Reproduced lost manual HIT in actual 3.0.8 via FocusOut, auxiliary add and return',
        '308 to 309 upgrade/idempotency preserves saved SQLite action, catalogues, prior fixes and logos',
        'Actual Tk module buttons, metadata edits, pending timer and modal variant choice/cancel',
        'Real structural edits still recalculate; excessive load never restores stale candidate',
        'Standard, HT and WT manual selections survive SQLite save/load and PDF preparation']}
    (ROOT/f'choice309-test-{sys.platform}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--baseline':
        ui(Path(sys.argv[2]),baseline=True)
    else:
        main()
