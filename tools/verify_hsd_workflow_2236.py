from __future__ import annotations
"""Real installed 2.2.35 -> 2.2.36 integration test; no customer database."""
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.parse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'updates/2.2.36'
SAMPLES = [('CRET 122 V',5),('CRET 124',7),('CRET 128',4),('CRET 134',8),('CRET 140',6)]
TEXT = 'Nazev\tPocet\n' + '\n'.join(f'{n}\t{q}' for n,q in SAMPLES)


def main():
    cache = {}
    reads = []
    def urlopen(request,*args,**kwargs):
        url = request.full_url if hasattr(request,'full_url') else str(request)
        parsed = urllib.parse.urlparse(url)
        assert parsed.netloc == 'raw.githubusercontent.com',url
        owner,repo,ref,*parts = parsed.path.strip('/').split('/')
        assert (owner,repo)==('jaroslavkucacz-code','TURTO-Izolacni-nosniky')
        key = ref+':'+ '/'.join(parts)
        reads.append(key)
        if key not in cache:
            cache[key] = subprocess.check_output(['git','show',key],cwd=ROOT)
        return io.BytesIO(cache[key])
    with tempfile.TemporaryDirectory(prefix='hsd_e2e_') as folder:
        root=Path(folder);program=root/'Program'
        os.environ.update(TURTO_ROOT=str(root),TURTO_PROGRAM_DIR=str(program),APPDATA=str(root/'appdata'),LOCALAPPDATA=str(root/'localappdata'))
        shutil.copytree(ROOT/'updates/1.1.17/catalogs',root/'catalogs')
        with patch('urllib.request.urlopen',urlopen):
            runpy.run_path(str(ROOT/'updates/2.2.35/runtime_installer.py'))['install_runtime'](root)
        (root/'.turto_runtime_current.ok').write_text('21')
        db=root/'actions.sqlite3'
        with sqlite3.connect(db) as con:
            con.execute('CREATE TABLE sentinel (v TEXT)');con.execute("INSERT INTO sentinel VALUES ('unchanged customer data')")
        before=db.read_bytes()
        installer=runpy.run_path(str(RELEASE/'runtime_installer.py'));installer['selftest']()
        with patch('urllib.request.urlopen',urlopen):
            start=len(reads);installer['install_runtime'](root)
            assert len(reads)-start==4
            assert installer['_revision_ok'](program) and db.read_bytes()==before
            start=len(reads);installer['install_runtime'](root);assert len(reads)==start
            (program/'shear_schedule_io_236.py').write_text('# damaged')
            installer['install_runtime'](root)
            assert installer['_revision_ok'](program) and db.read_bytes()==before
        shutil.copy2(RELEASE/'app.pyw',root/'app.pyw')
        bootstrap=runpy.run_path(str(root/'app.pyw'));bootstrap['selftest']();assert bootstrap['_runtime_ready']()
        sys.path.insert(0,str(program))
        runtime=runpy.run_path(str(program/'app_runtime.pyw'));runtime['selftest']()
        import tkinter as tk
        from tkinter import messagebox,ttk
        import shear_dowels_ui as ui
        import shear_workflow_236 as workflow
        import shear_autocomplete as ac
        from shear_schedule_io_236 import read_file,parse_rows,FileText
        import halfen_hsd_2026 as hsd
        for name,qty in SAMPLES:
            assert ui.decode_dowel(name)['halfen_hsd_2026']
        assert ac.suggest_values('CRET 122 V',10)[0].designation=='HSD-CRET 122 V'
        assert any(s.designation=='HSD-CRET 140' for s in ac.all_suggestions())
        assert hsd.capacity_for('CRET 124',280,30,'C25/30')[0]['vrd']==108.8
        assert hsd.capacity_for('CRET 124 V',280,30,'C25/30')[0]['vrd']==101.4
        assert hsd.capacity_for('HSD-SET 25 V',240,30,'C25/30')[0]['vrd']==11.8
        for name,h,g,c in [('CRET 145',500,30,'C25/30'),('CRET 124',float('inf'),30,'C25/30'),('CRET 124',280,-1,'C25/30'),('HSD-SET 25',240,30,'C12/15')]:
            assert hsd.capacity_for(name,h,g,c)[0] is None
        assert ui.decode_dowel('Ancon HLD 22') and ui.decode_dowel('Schöck Dorn SLD 40')
        def parse(text):return parse_rows(text,decoder=ui.decode_dowel,defaults={},existing_names=set())
        for separator in ('\t',';',' | ',' '):
            rows=parse('\n'.join(f'{n}{separator}{q}' for n,q in SAMPLES))
            assert len(rows)==5 and [r.quantity for r in rows]==[5,7,4,8,6] and not any(r.error for r in rows)
        for text in ('CRET 124\t0','CRET 124\t2.5','CRET 124\t-2','UNKNOWN\t5'):
            assert parse(text)[0].error
        assert parse('S010 | 7 | CRET 124')[0].name=='S010'
        csvfile=root/'schedule.csv';csvfile.write_text(TEXT.replace('\t',';'),encoding='utf-8')
        assert len(parse(read_file(csvfile).text))==5
        # PDF reading order intentionally column-wise; physical positions must pair quantities.
        import fitz
        pdf=root/'schedule.pdf'
        doc=fitz.open();page=doc.new_page()
        for i,(name,qty) in enumerate(SAMPLES):page.insert_text((80,100+i*30),name)
        for i,(name,qty) in enumerate(SAMPLES):page.insert_text((400,100+i*30),str(qty))
        doc.save(pdf);doc.close()
        assert [r.quantity for r in parse(read_file(pdf).text)]==[5,7,4,8,6]
        failures=[]
        def callback_error(owner,*exc):
            failures.append(''.join(traceback.format_exception(*exc)))
            dialog=getattr(owner,'_hsd_last_import_dialog',None)
            if dialog is not None and dialog.winfo_exists():dialog._cancel()
        tk.Tk.report_callback_exception=callback_error
        with patch.object(messagebox,'showerror',lambda *a,**k:failures.append(str(a))),patch.object(messagebox,'showwarning',lambda *a,**k:failures.append(str(a))):
            app=runtime['_base'].ThermalConnectorApp();app.update()
            assert [app.main_notebook.tab(t,'text') for t in app.main_notebook.tabs()]==['Dekodér','Návrh','Záměny']
            assert app.hsd_catalog_choice.winfo_exists()
            deadline=time.monotonic()+15
            def finish_import():
                d=app._hsd_last_import_dialog
                if d.loading and time.monotonic()<deadline:
                    app.after(100,finish_import);return
                assert not d.loading,'File worker timed out'
                assert len(d.items)==5 and sum(r.quantity for r in d.items)==30
                d.insert_button.invoke()
            def choose_file():
                d=app._hsd_last_import_dialog
                d.file_button.invoke()
                app.after(100,finish_import)
            with patch.object(workflow.filedialog,'askopenfilename',return_value=str(csvfile)):
                app.after(150,choose_file)
                button=next(w for w in workflow._walk(app.shear_notebook) if isinstance(w,ttk.Button) and w.cget('text')=='Načíst výkaz ze souboru / textu…')
                button.invoke()
            app.update();assert not failures,failures
            assert len(app.shear_decoder_rows)==5 and sum(r['quantity'] for r in app.shear_decoder_rows)==30
            assert all(r.get('hsd_capacity') is None for r in app.shear_decoder_rows)
            assert all(app.shear_decoder_tree.set(i,'vrd')=='—' for i in app.shear_decoder_tree.get_children())
            # Actual modal OCR review gate, without another expensive OCR call.
            d=workflow.DecoderFileDialog(app,mode='decoder',decoder=ui.decode_dowel,defaults={},existing_names=set())
            d.set_file_text(FileText(TEXT,'raster fixture',True))
            assert str(d.insert_button['state'])=='disabled'
            d.ocr_confirmed.set(True);d._refresh();assert str(d.insert_button['state'])=='normal'
            d._cancel()
            app.shear_decoder_tree.selection_set('0');app.shear_decoder_to_substitution();app.update()
            assert app.shear_substitution_vars['source'].get()=='CRET 122 V'
            assert app.shear_substitution_vars['qty'].get()=='5'
            assert app.shear_substitution_vars['slab'].get()==''
            for row in app.shear_decoder_rows:row.update(slab_mm=400,gap_mm=30,concrete='C25/30',geometry_confirmed=True)
            app.refresh_shear_tables()
            assert [r['hsd_capacity']['vrd'] for r in app.shear_decoder_rows]==[79.4,108.8,147.9,219.3,320.8]
            from action_payload import serialize_action,load_action_record
            from action_store import ActionStore
            store=ActionStore(root/'roundtrip.sqlite3');saved=store.save(action_name='HSD regression',payload=serialize_action(app))
            app.shear_decoder_rows=[];load_action_record(app,store.load(saved['id']));app.update()
            assert len(app.shear_decoder_rows)==5 and app.shear_decoder_rows[0]['quantity']==5
            assert app.shear_decoder_rows[0]['import_source_file'].endswith('schedule.csv')
            app.shear_design_vars['ved'].set('10');app.shear_design_vars['slab'].set('250');app.shear_design_vars['gap'].set('20');app.shear_design_vars['concrete'].set('C25/30')
            app.add_shear_design_row();app.update();assert len(app.shear_design_rows)==1
            app.refresh_shear_tables();assert app.shear_design_tree.selection()
            assert not failures,failures
            app.destroy()
        ocr_status='not run on Linux CI; actual customer image checked separately with local Tesseract'
        if os.name=='nt':
            from PIL import Image,ImageDraw,ImageFont
            image=Image.new('RGB',(700,340),'white');draw=ImageDraw.Draw(image)
            font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',30)
            for i,(name,qty) in enumerate(SAMPLES):
                draw.text((40,20+i*55),name,font=font,fill='black');draw.text((550,20+i*55),str(qty),font=font,fill='black')
            imagefile=root/'ocr_fixture.png';image.save(imagefile)
            try:
                extracted=read_file(imagefile)
                assert [r.quantity for r in parse(extracted.text)]==[5,7,4,8,6],extracted.text
                ocr_status='Windows native OCR passed: five rows, thirty pieces'
            except subprocess.CalledProcessError as exc:
                error=exc.stderr.decode('utf-8',errors='replace')
                if 'Windows OCR language is unavailable' not in error:raise RuntimeError(error) from exc
                ocr_status='Windows runner has no installed OCR language; adapter returned explicit unavailable status'
        report={'version':'2.2.36','platform':sys.platform,'rows':5,'pieces':30,'runtime_install':'pass','database_bytes_preserved':True,'file_button_csv':'pass','position_based_pdf':'pass','transfer':'pass','sqlite_roundtrip':'pass','ocr':ocr_status}
        (ROOT/('hsd-test-'+sys.platform+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
