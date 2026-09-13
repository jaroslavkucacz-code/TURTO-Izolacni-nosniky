from __future__ import annotations
"""Installed 2.2.35 -> 2.2.36 end-to-end, disposable databases only.

Raster OCR accuracy is reported separately from the mandatory human-review
workflow. A corrected preview is never misreported as flawless automatic OCR.
"""
import gc
import io
import json
import logging
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

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'updates/2.2.36'
SAMPLES=[('CRET 122 V',5),('CRET 124',7),('CRET 128',4),('CRET 134',8),('CRET 140',6)]
TEXT='Název\tPočet\n'+'\n'.join(f'{n}\t{q}' for n,q in SAMPLES)


def main():
    cache={};reads=[];report={'version':'2.2.36','platform':sys.platform}
    def urlopen(request,*args,**kwargs):
        url=request.full_url if hasattr(request,'full_url') else str(request)
        parsed=urllib.parse.urlparse(url)
        assert parsed.netloc=='raw.githubusercontent.com',url
        owner,repo,ref,*parts=parsed.path.strip('/').split('/')
        assert (owner,repo)==('jaroslavkucacz-code','TURTO-Izolacni-nosniky')
        assert len(ref)==40,ref
        key=ref+':'+ '/'.join(parts);reads.append(key)
        if key not in cache:cache[key]=subprocess.check_output(['git','show',key],cwd=ROOT)
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
            con.execute('CREATE TABLE sentinel(v TEXT)');con.execute("INSERT INTO sentinel VALUES ('unchanged customer data')")
        con.close();before=db.read_bytes()
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
        import shear_schedule_io_236 as intake
        from shear_schedule_io_236 import read_file,parse_rows,FileText
        import halfen_hsd_2026 as hsd
        for name,qty in SAMPLES:assert ui.decode_dowel(name)['halfen_hsd_2026']
        assert len(ac.suggest_values('CRET 122 V',10))==1
        assert ac.suggest_values('CRET 122 V',10)[0].designation=='HSD-CRET 122 V'
        assert any(s.designation=='HSD-CRET 140' for s in ac.all_suggestions())
        for name,h,g,c,want in [('CRET 124',280,30,'C25/30',108.8),('CRET 124 V',280,30,'C25/30',101.4),('HSD-SET 25 V',240,30,'C25/30',11.8)]:
            assert hsd.capacity_for(name,h,g,c)[0]['vrd']==want
        for name,h,g,c in [('CRET 145',500,30,'C25/30'),('CRET 124',float('inf'),30,'C25/30'),('CRET 124',280,-1,'C25/30'),('HSD-SET 25',240,30,'C12/15')]:
            assert hsd.capacity_for(name,h,g,c)[0] is None
        assert ui.decode_dowel('Ancon HLD 22') and ui.decode_dowel('Schöck Dorn SLD 40')
        def parse(text):return parse_rows(text,decoder=ui.decode_dowel,defaults={},existing_names=set())
        def check_rows(rows):
            assert len(rows)==5,[repr(r) for r in rows]
            assert [r.quantity for r in rows]==[5,7,4,8,6],[repr(r) for r in rows]
            assert not any(r.error for r in rows),[repr(r) for r in rows]
            assert [r.values['canonical_designation'] for r in rows]==['HSD-'+n for n,q in SAMPLES]
        for separator in ('\t',';',' | ',' '):check_rows(parse('\n'.join(f'{n}{separator}{q}' for n,q in SAMPLES)))
        for text in ('CRET 124\t0','CRET 124\t2.5','CRET 124\t-2','UNKNOWN\t5','CRET 124','CRET 124\t','CRET 124\t1000001'):
            assert parse(text)[0].error,text
        assert parse('CRET 124')[0].quantity==0
        assert parse('S010 | 7 | CRET 124')[0].name=='S010'
        assert parse('S010 | CRET 124 | 7\nS010 | CRET 128 | 4')[1].error
        csvfile=root/'schedule.csv';csvfile.write_text(TEXT.replace('\t',';'),encoding='utf-8')
        check_rows(parse(read_file(csvfile).text))
        from openpyxl import Workbook
        book=Workbook();sheet=book.active;sheet.append(['Název','Počet'])
        for row in SAMPLES:sheet.append(row)
        xlsx=root/'schedule.xlsx';book.save(xlsx);book.close();check_rows(parse(read_file(xlsx).text))
        # Text objects deliberately ordered column-wise, not row-wise.
        from reportlab.pdfgen.canvas import Canvas
        pdf=root/'schedule.pdf';canvas=Canvas(str(pdf))
        for i,(name,qty) in enumerate(SAMPLES):canvas.drawString(80,740-i*30,name)
        for i,(name,qty) in enumerate(SAMPLES):canvas.drawString(400,740-i*30,str(qty))
        canvas.save();check_rows(parse(read_file(pdf).text))
        imagefile=ROOT/'tools/fixtures/hsd_schedule_from_screenshot.png'
        scan=root/'scan.pdf';canvas=Canvas(str(scan));canvas.drawImage(str(imagefile),40,300,width=500,height=375);canvas.save()
        with patch.object(intake,'_ocr_image',return_value=TEXT):
            assert read_file(scan).review_required
        ocr=FileText('CRET 122 V\t5\nCRET 12A\t7\nCRET 128\nCRET 13A\t8\nCRET 1AO\t6',str(imagefile),True,'OCR vyžaduje kontrolu.')
        if os.name=='nt':
            ocr=read_file(imagefile)  # One native OCR call; corrections are explicit below.
            assert ocr.review_required and ocr.text.strip()
            print('OCR_TEXT_JSON:',json.dumps(ocr.text,ensure_ascii=True),flush=True)
            try:check_rows(parse(ocr.text));raw_exact=True
            except AssertionError:raw_exact=False
            report['ocr']={'native_windows_executed':True,'raw_ocr_exact':raw_exact,'raw_text':ocr.text,'manual_correction_and_review_tested':True}
        else:
            report['ocr']={'native_windows_executed':False,'synthetic_damaged_text_review_tested':True}
        failures=[];warnings=[]
        def callback_error(owner,*exc):
            failures.append(''.join(traceback.format_exception(*exc)))
            dialog=getattr(owner,'_hsd_last_import_dialog',None)
            if dialog is not None and dialog.winfo_exists():dialog._cancel()
        tk.Tk.report_callback_exception=callback_error
        with patch.object(messagebox,'showerror',lambda *a,**k:failures.append(str(a))),patch.object(messagebox,'showwarning',lambda *a,**k:warnings.append(str(a))),patch.object(messagebox,'askyesno',return_value=True):
            app=runtime['_base'].ThermalConnectorApp();app.update()
            assert [app.main_notebook.tab(t,'text') for t in app.main_notebook.tabs()]==['Dekodér','Návrh','Záměny']
            def show_decoder():
                app.product_domain_notebook.select(app.product_domain_tab_by_id['shear_dowels']);app.shear_notebook.select(0);app.update()
            show_decoder();assert app.hsd_catalog_choice.winfo_ismapped()
            assert 'HSD-CRET 122 V' in app.hsd_catalog_choice['values']
            for path in (csvfile,xlsx,pdf):
                deadline=time.monotonic()+15
                def finish_import():
                    d=app._hsd_last_import_dialog
                    if d.loading and time.monotonic()<deadline:app.after(100,finish_import);return
                    assert not d.loading,'File worker timed out'
                    check_rows(d.items)
                    d.replace_existing.set(True);d.insert_button.invoke()
                def choose_file():
                    app._hsd_last_import_dialog.file_button.invoke();app.after(100,finish_import)
                with patch.object(workflow.filedialog,'askopenfilename',return_value=str(path)):
                    app.after(100,choose_file)
                    button=next(w for w in workflow._walk(app.shear_notebook) if isinstance(w,ttk.Button) and w.cget('text')=='Načíst výkaz ze souboru / textu…')
                    button.invoke()
                app.update();assert not failures,failures
                assert len(app.shear_decoder_rows)==5 and sum(r['quantity'] for r in app.shear_decoder_rows)==30
                assert all(r.get('hsd_capacity') is None for r in app.shear_decoder_rows)
                assert all(app.shear_decoder_tree.set(i,'vrd')=='—' for i in app.shear_decoder_tree.get_children())
            saved_rows=json.dumps(app.shear_decoder_rows,sort_keys=True)
            d=workflow.DecoderFileDialog(app,mode='decoder',decoder=ui.decode_dowel,defaults={},existing_names=set())
            d.set_file_text(ocr);app.update()
            assert str(d.insert_button['state'])=='disabled'
            # A missing quantity must block acceptance even after attempted review.
            d.text.delete('1.0','end');d.text.insert('1.0','CRET 124');d._analyze();d.ocr_check.invoke();app.update()
            assert d.items[0].quantity==0 and d.items[0].error
            assert str(d.insert_button['state'])=='disabled'
            # Correct according to original screenshot; no hidden OCR digit substitution.
            d.text.delete('1.0','end');d.text.insert('1.0',TEXT);d._analyze();app.update()
            assert str(d.insert_button['state'])=='disabled'
            d.ocr_check.invoke();app.update();assert str(d.insert_button['state'])=='normal'
            d.text.insert('end','\n');app.update();assert str(d.insert_button['state'])=='disabled'
            d._analyze();assert not d.ocr_confirmed.get()
            d.ocr_check.invoke();app.update();assert str(d.insert_button['state'])=='normal'
            from PIL import ImageGrab
            ImageGrab.grab().save(ROOT/f'hsd-evidence-preview-{sys.platform}.png')
            d.insert_button.invoke();assert len(d.result)==5 and sum(r['quantity'] for r in d.result)==30
            assert all(r['import_method']=='ocr-reviewed' for r in d.result)
            assert json.dumps(app.shear_decoder_rows,sort_keys=True)==saved_rows
            d=workflow.DecoderFileDialog(app,mode='decoder',decoder=ui.decode_dowel,defaults={},existing_names=set())
            d.set_file_text(FileText(TEXT,'cancel'));d._cancel()
            assert d.result is None and json.dumps(app.shear_decoder_rows,sort_keys=True)==saved_rows
            # Actual visible Decoder, not the hidden thermal tab or an autocomplete popup.
            sizes={}
            for size in ('1366x768','1024x768'):
                show_decoder();app.geometry(size+'+0+0')
                for _ in range(8):app.update();time.sleep(.03)
                tree=app.shear_decoder_tree
                assert tree.winfo_ismapped() and tree.winfo_height()>=150,(size,tree.winfo_geometry())
                assert len(tree.get_children())==5
                assert not any(h.popup and h.popup.winfo_ismapped() for h in app._shear_autocompletes)
                for w in workflow._walk(app.shear_notebook.nametowidget(app.shear_notebook.tabs()[0])):
                    if isinstance(w,(ttk.Button,ttk.Combobox,ttk.Entry)) and w.winfo_ismapped():
                        assert w.winfo_rootx()+w.winfo_width()<=app.winfo_rootx()+app.winfo_width(),(size,w,w.winfo_geometry())
                sizes[size]={'window':app.geometry(),'table_height':tree.winfo_height()}
                ImageGrab.grab().save(ROOT/f'hsd-evidence-decoder-{sys.platform}-{size}.png')
            app.shear_decoder_tree.selection_set('0');app.shear_decoder_to_substitution();app.update()
            assert app.shear_substitution_vars['source'].get()=='CRET 122 V'
            assert app.shear_substitution_vars['qty'].get()=='5' and app.shear_substitution_vars['slab'].get()==''
            # Preserve unknown geometry through SQLite as well as rendered rows.
            from action_payload import serialize_action,load_action_record
            from action_store import ActionStore
            store=ActionStore(root/'roundtrip.sqlite3');saved=store.save(action_name='HSD regression',payload=serialize_action(app))
            app.shear_decoder_rows=[];load_action_record(app,store.load(saved['id']));app.update()
            assert len(app.shear_decoder_rows)==5 and app.shear_decoder_rows[0]['quantity']==5
            assert app.shear_decoder_rows[0]['geometry_confirmed'] is False
            assert app.shear_decoder_rows[0]['import_source_file'].split(' | ')[0].endswith('schedule.pdf')
            for row in app.shear_decoder_rows:row.update(slab_mm=400,gap_mm=30,concrete='C25/30',geometry_confirmed=True)
            app.refresh_shear_tables()
            assert [r['hsd_capacity']['vrd'] for r in app.shear_decoder_rows]==[79.4,108.8,147.9,219.3,320.8]
            show_decoder()
            app.shear_decoder_vars['name'].set('MANUAL');app.shear_decoder_vars['designation'].set('CRET 124');app.shear_decoder_vars['qty'].set('2')
            app.add_shear_decoder_row();app.update()
            assert len(app.shear_decoder_rows)==6 and app.shear_decoder_rows[-1]['geometry_confirmed'] is False
            assert app.shear_decoder_rows[-1]['quantity']==2
            app.shear_design_vars['ved'].set('10');app.shear_design_vars['slab'].set('250');app.shear_design_vars['gap'].set('20');app.shear_design_vars['concrete'].set('C25/30')
            app.add_shear_design_row();app.update();assert len(app.shear_design_rows)==1
            app.refresh_shear_tables();assert app.shear_design_tree.selection()
            assert not failures,failures
            app.destroy();logging.shutdown();del app,store;gc.collect()
        report.update(rows=5,pieces=30,runtime_install='pass',database_bytes_preserved=True,file_buttons=['CSV','XLSX','text PDF'],scan_pdf_routing='pass',missing_quantity_blocked=True,stale_ocr_review_blocked=True,manual_entry='pass',cancel_unchanged=True,transfer='pass',sqlite_roundtrip='pass',small_screens=sizes)
        (ROOT/f'hsd-test-{sys.platform}.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(report,indent=2,ensure_ascii=True))

if __name__=='__main__':main()
