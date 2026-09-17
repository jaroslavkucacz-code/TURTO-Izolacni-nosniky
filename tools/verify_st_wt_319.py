"""Catalogue boundaries, real ST/WT UI choices, persisted actions and exports."""
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def engine_checks(core):
    def calc(typ='ST',**changes):
        data=dict(connection_type=typ,series='HP',wall_height_mm=400 if typ=='ST' else 1500,
                  width_mm=220 if typ=='ST' else 150,concrete='C25/30',med_neg=1,ved_vertical=0,ved_horizontal=0)
        data.update(changes)
        return core.design_connector(**data)
    # Independent printed p.155 anchors, both concrete columns and top/bottom.
    assert [c.mrd for c in calc()[0]] == [29.6,39.2,51.8,71.4]
    assert [c.vrd_vertical for c in calc()[0]] == [30.9,48.3,69.5,94.7]
    c=calc(concrete='C20/25',wall_height_mm=1000)[0][-1]
    assert (c.mrd,c.vrd_vertical,c.page)==(191.8,82.2,155)
    assert calc(series='SP',wall_height_mm=1000)[0][-1].mrd==223.2
    assert calc(series='SP')[0][-1].joint_spacing_m==13.5
    for height in (401,450,499,500,550,599,999,1000):
        rows,error=calc(wall_height_mm=height);assert rows and not error
        lower=height//100*100
        reference=calc(wall_height_mm=lower)[0]
        assert [c.mrd for c in rows]==[c.mrd for c in reference]
        assert all(c.table_height_mm==lower and c.wall_height_mm==height for c in rows)
    # A demand just above the lower cell must NOT pass using the upper cell.
    assert calc(wall_height_mm=499,med_neg=29.61)[0][0].load_range==2
    assert calc(wall_height_mm=500,med_neg=29.61)[0][0].load_range==1
    for height in (399,1001,0,400.5,float('nan'),float('inf')):
        assert not calc(wall_height_mm=height)[0],height
    for values in (dict(width_mm=210),dict(width_mm=350),dict(width_mm=220.5),
                   dict(ved_horizontal=1),dict(med_neg=float('nan')),dict(ved_vertical=float('inf')),
                   dict(series='OTHER'),dict(concrete='C16/20'),dict(med_neg=0)):
        assert not calc(**values)[0],values
    assert calc(wall_height_mm=555)[0][0].designation=='HIT-HP ST-1-55.5-22'
    assert all(c.vrd_horizontal is None for c in calc()[0])
    for height in (1000,1001,1249,1250,1251,1620,3499,3500):
        rows,error=calc('WT',wall_height_mm=height);assert rows and not error
        assert all(c.table_height_mm==height//250*250 for c in rows)
        if height<1250:assert all(c.load_range>=5 for c in rows)
    for height in (999,3501):assert not calc('WT',wall_height_mm=height)[0]
    # Every previously valid WT table result remains numerically identical.
    path=ROOT/'updates/1.1.25/hit_wt.py'
    spec=importlib.util.spec_from_file_location('test_legacy_wt',path)
    old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
    count=0
    for series in ('HP','SP'):
        for concrete in ('C20/25','C25/30','C30/37'):
            for h in range(1000,3501,250):
                args=dict(series=series,concrete=concrete,wall_height_mm=h,width_mm=150,med_neg=1,ved_vertical=0,ved_horizontal=0)
                before=old.design_wt(**args)[0];after=core.design_wt(**args)[0]
                assert [(c.designation,c.mrd,c.vrd_vertical,c.vrd_horizontal,c.utilization) for c in before]==[(c.designation,c.mrd,c.vrd_vertical,c.vrd_horizontal,c.utilization) for c in after]
                count+=len(after)
    return dict(wt_unchanged_candidates=count,st_boundaries=True,no_interpolation=True,no_extrapolation=True)


def exercise(app):
    import hit_wt,hit_export_ui_127,hit_pdf,action_payload
    from tkinter import ttk,font as tkfont
    from verify_workflow_317 import pump
    proof=engine_checks(hit_wt)
    app.product_domain_notebook.select(app.product_domain_tab_by_id['thermal_breaks'])
    app.main_notebook.select(app.hit_tab);app.shared_thermal_design.show_hit_group('wt');pump(app)
    app.clear_wt_rows(mark_dirty=False)
    # Exercise the actual add-ST button. Default unused rows must stay absent.
    pending=[app.hit_wt_tab];buttons={}
    while pending:
        w=pending.pop();pending.extend(w.winfo_children())
        if isinstance(w,ttk.Button):buttons[str(w.cget('text'))]=w
    assert '+ Přidat ST' in buttons and '+ Přidat WT' in buttons,buttons
    buttons['+ Přidat ST'].invoke();pump(app)
    assert len(app.wt_rows)==1
    row=app.wt_rows[0];assert row.connection_type.get()=='ST'
    row.wall_height.set('550');row.med_neg.set('40');row._changed_now();pump(app)
    assert row.selected_candidate.load_range==2 and row.table_height.get()=='500'
    assert len(row.candidates)>1
    row.product_combo.current(1);row.product_combo.event_generate('<<ComboboxSelected>>');pump(app)
    chosen=row.selected_candidate.designation;assert row.manual_product
    wt=app.add_wt_row(dict(name='TEST_ONLY WT319',wall_height='1620',width='150',med_neg='70',quantity=3))
    # Combination stays KONTROLA; no invented M-V interaction.
    row.ved_vertical.set('5');row.recalculate(preserve=chosen)
    assert 'KONTROLA KOMBINACE' in row.status.get()
    for group in ('standard','aux','wt'):
        app.shared_thermal_design.show_hit_group(group);pump(app)
    app.recalculate_wt_all();pump(app)
    assert row.selected_candidate.designation==chosen and row.manual_product
    assert wt.selected_candidate.wall_height_mm==1620 and wt.selected_candidate.table_height_mm==1500
    store=action_payload.action_store(app)
    saved=store.save(action_name='TEST_ONLY ST-WT319',payload=action_payload.serialize_action(app))
    meta=dict(action_id=saved['id'],chosen=chosen)
    (Path(app.settings_path).parent/'TEST_ONLY_saved319.json').write_text(json.dumps(meta),encoding='utf-8')
    reopen_saved(app);pump(app)
    rows=[r for r in hit_export_ui_127.collect_all_hit_rows(app) if r['connection_type'] in {'ST','WT'}]
    assert len(rows)==2 and rows[0]['status']=='KONTROLA'
    assert rows[0]['candidate']['connection_type']=='ST' and rows[0]['candidate']['table_height_mm']==500
    assert rows[0]['candidate']['vrd_horizontal'] is None
    app.copy_wt_table();copied=app.clipboard_get();assert chosen in copied and 'h tab. pro únosnost' in copied
    out=Path(app.settings_path).parent
    xlsx=out/'TEST_ONLY_ST_WT319.xlsx'
    with patch('tkinter.filedialog.asksaveasfilename',return_value=str(xlsx)),patch('os.startfile',create=True):
        app.export_wt_excel()
    import openpyxl,pdfplumber
    book=openpyxl.load_workbook(xlsx,data_only=True)
    values=list(book.active.values);book.close()
    assert values[1][2:7]==('ST','HP','550',500,'220'),values
    assert values[1][11]==chosen and values[1][15]=='—'
    pdf=out/'TEST_ONLY_ST_WT319.pdf'
    hit_pdf.write_hit_proposal_pdf(pdf,project_name='TEST_ONLY ST-WT319',rows=rows)
    with pdfplumber.open(pdf) as doc:
        text='\n'.join(p.extract_text() or '' for p in doc.pages)
        assert chosen in text and '550 mm' in text and '500 mm' in text and '1500 mm' in text
        assert 'KONTROLA' in text and 'Nosníky ST' in text and any(p.images for p in doc.pages)
    # Old saved WT rows without the new type field load as WT, retaining choice.
    legacy=app.wt_rows[1].payload();legacy.pop('connection_type')
    app.load_wt_design({'rows':[legacy]});pump(app)
    assert app.wt_rows[0].connection_type.get()=='WT' and app.wt_rows[0].selected_candidate.wall_height_mm==1620
    reopen_saved(app)
    # Edits outside the source range / unsupported loads never retain a result.
    row=app.wt_rows[0];row.ved_horizontal.set('1');row._changed_now();pump(app)
    assert row.selected_candidate is None and 'VEd,h' in row.status.get()
    row.ved_horizontal.set('');row.wall_height.set('1001');row._changed_now();pump(app)
    assert row.selected_candidate is None
    reopen_saved(app)
    font=tkfont.Font(app,font=app.style.lookup('Treeview','font'))
    assert app.tk.splitlist(app.style.lookup('Treeview','font'))[:2]==('Calibri','11')
    assert int(app.style.lookup('Treeview','rowheight')) >= font.metrics('linespace')+6
    if sys.platform=='win32':
        assert font.actual('family')=='Calibri' and font.actual('size')==11
        import ctypes
        awareness=ctypes.c_int()
        assert ctypes.windll.shcore.GetProcessDpiAwareness(None,ctypes.byref(awareness))==0
        assert awareness.value==1,awareness.value
    proof.update(saved_manual_choice=chosen,actual_height=550,table_height=500,pdf_xlsx=True)
    app.clear_wt_rows(mark_dirty=False)
    return proof


def reopen_saved(app):
    import action_payload
    from verify_workflow_317 import pump
    meta=json.loads((Path(app.settings_path).parent/'TEST_ONLY_saved319.json').read_text(encoding='utf-8'))
    action_payload.load_action_record(app,action_payload.action_store(app).load(meta['action_id']));pump(app)
    assert len(app.wt_rows)==2
    row,wt=app.wt_rows
    assert row.connection_type.get()=='ST' and row.manual_product
    assert row.selected_candidate.designation==meta['chosen']
    assert row.wall_height.get()=='550' and row.selected_candidate.table_height_mm==500
    assert wt.connection_type.get()=='WT' and wt.wall_height.get()=='1620'


if __name__=='__main__':
    sys.path.insert(0,str(ROOT/'updates/3.0.19'))
    import hit_wt
    print(json.dumps(engine_checks(hit_wt)))
