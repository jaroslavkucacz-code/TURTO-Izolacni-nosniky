"""Actual decoder input, length edits, catalogue units, SQLite and exports."""
from copy import deepcopy
from pathlib import Path
import json
import time
from unittest.mock import patch

CODE='XT-QL-VV1-REI120-H240-6.0'
QP='T-QP-VV1-REI120-H200-L300-5.0'


def exercise(app):
    from tkinter import messagebox,ttk
    from verify_workflow_317 import pump
    import decoder_length_320 as length
    import bulk_import_engine as engine,bulk_import,project_model as pm
    import action_payload,pdf_data_304,hit_pdf,substitution_workspace as sub
    for value,expected in [('0,5',500),('0.75',750),('0,333',333),('500 mm',500),('50 cm',500),('',None)]:
        assert length.parse_length(value)==expected
    for value in ('0','-0,5','nan','inf','abc','0,0005','1/2','1e3','1 0','1001 m'):
        try:length.parse_length(value)
        except ValueError:pass
        else:raise AssertionError(value)
    result=app.database.resolve_designation(CODE,preferred_concrete='C25/30')
    original=deepcopy(result.record)
    for unit,a,b in [('m','0,5','0.75'),('mm','500','750')]:
        text=f'Pozice;Ks;Označení;Délka [{unit}];Poznámka\nL1;2;{CODE};{a};Poznámka A\nL2;3;{CODE};{b};Poznámka B'
        items,skipped=engine.analyze_bulk_text(app.database,text,preferred_concrete='C25/30')
        assert skipped==1 and [i.element_length_mm for i in items]==[500,750]
        assert all(i.ready for i in items) and items[0].note=='Poznámka A'
        assert items[0].result.results==items[1].result.results==result.results
    items,_=engine.analyze_bulk_text(app.database,f'L1;2;{CODE};délka=0,5 m\nL2;3;{CODE} - 0,75 m',preferred_concrete='C25/30')
    assert all(i.ready for i in items) and [i.element_length_mm for i in items]==[500,750]
    for value in ('-1','0','abc','nan'):
        items,_=engine.analyze_bulk_text(app.database,f'Pozice;Ks;Označení;Délka [m]\nL1;2;{CODE};{value}',preferred_concrete='C25/30')
        assert not items[0].ready
    items,_=engine.analyze_bulk_text(app.database,f'L1;2;{CODE};123',preferred_concrete='C25/30')
    assert items[0].ready and items[0].element_length_mm is None and items[0].note=='123'
    items,skipped=engine.analyze_bulk_text(app.database,f'Označení;Délka [m]\n{CODE};0,5',preferred_concrete='C25/30')
    assert skipped==1 and items[0].ready and items[0].element_length_mm==500
    # Old actions, fixed per-piece lengths and catalogue data remain unchanged.
    qp=pm.create_project_row(app.database.resolve_designation(QP,preferred_concrete='C25/30'),position='LQP',source_text=QP)
    assert length.effective_length(qp)==300
    totals,_=sub.source_element_actions(qp)
    length.set_length(qp,500)
    assert sub.source_element_actions(qp)[0]==totals and length.capacity_length_issue(qp)
    assert sub.design_targets(app.hit_db,row=qp,metadata=sub.source_metadata(qp))[1]
    length.set_length(qp,None);assert length.effective_length(qp)==300 and not length.capacity_length_issue(qp)
    app.product_domain_notebook.select(app.product_domain_tab_by_id['thermal_breaks'])
    app.main_notebook.select(app.project_tab);pump(app)
    app.project.rows=[];app.refresh_project_tree()
    # Quick entry including invalid input and reset for the next product.
    app.project_quick_designation_var.set(CODE)
    app.project_quick_length_var.set('-1')
    with patch.object(messagebox,'showerror') as error:
        app.quick_add_project_row();assert error.called and not app.project.rows
    app.project_quick_length_var.set('0,5');app.quick_add_project_row();pump(app)
    row=app.project.rows[-1];row['position']='LENGTH320';row_id=row['id']
    assert length.effective_length(row)==500 and app.project_quick_length_var.get()==''
    assert app.project_tree.set(row_id,'element_length')=='0,5'
    baseline=deepcopy(row);length.set_length(baseline,1000)
    before=sub.action_values(sub.source_element_actions(baseline)[0])
    after=sub.action_values(sub.source_element_actions(row)[0])
    assert all(abs(after[k]-v*.5)<1e-9 for k,v in before.items())
    assert row['snapshot']['results']==result.results and result.record==original
    # Drive the real modal edit dialog: save, cancel, bad input, and length reset.
    def edit_to(value,cancel=False):
        def operate(dialog):
            assert dialog.length_var.get()=='0,5'
            dialog.length_var.set(value)
            dialog._cancel() if cancel else dialog._submit()
        with patch.object(app,'wait_window',side_effect=operate):app.edit_selected_project_metadata()
    app.project_tree.selection_set(row_id)
    row['mapping'].update(status='ok',targets=[{'id':'OLD'}],selected_target_id='OLD',substitution_acceptance={'confirmed':True})
    edit_to('0,75',cancel=True);assert length.effective_length(row)==500 and row['mapping']['selected_target_id']=='OLD'
    edit_to('0,75');assert length.effective_length(row)==750 and row['mapping']['status']=='not_run'
    assert row['mapping']['selected_target_id'] is None and not row['mapping'].get('substitution_acceptance')
    assert app.project_tree.set(row_id,'element_length')=='0,75'
    # Bulk dialog uses the genuine threaded analysis, then applies a shared length.
    bulk_text=f'Pozice\tKs\tOznačení\tDélka [m]\tPoznámka\nB1\t2\t{CODE}\t0,5\tA\nB2\t3\t{CODE}\t0,75\tB\nB3\t1\t{QP}\t\tC'
    def bulk_dialog(dialog):
        dialog.text.insert('1.0',bulk_text);dialog._analyze()
        deadline=time.monotonic()+20
        while dialog._analysis_running and time.monotonic()<deadline:pump(app,.04)
        assert not dialog._analysis_running and len(dialog.items)==3
        assert [length.item_length(i) for i in dialog.items]==[500,750,300]
        dialog.review_tree.selection_set(('i0','i1'));dialog.length_var.set('0,6')
        dialog.length_apply_button.invoke()
        assert [length.item_length(i) for i in dialog.items]==[600,600,300]
        dialog.length_var.set('-1')
        with patch.object(messagebox,'showwarning') as warn:
            dialog.length_apply_button.invoke();assert warn.called
        assert length.item_length(dialog.items[0])==600
        dialog.review_tree.selection_set('i1');dialog.length_var.set('0,5');dialog.length_apply_button.invoke()
        dialog.insert_button.invoke()
    with patch.object(app,'wait_window',side_effect=bulk_dialog):app.bulk_paste_project_rows()
    assert [length.effective_length(r) for r in app.project.rows]==[750,600,500,300]
    assert [r['quantity'] for r in app.project.rows]==[1,2,3,1]
    app.project_tree.selection_set(row_id);app.duplicate_selected_project_rows();pump(app)
    assert length.effective_length(app.project.rows[-1])==750
    app.project.rows.pop();app.refresh_project_tree()
    # Persist the exact source geometry through a real SQLite action and reopen.
    store=action_payload.action_store(app)
    saved=store.save(action_name='TEST_ONLY Decoder length320',payload=action_payload.serialize_action(app))
    out=Path(app.settings_path).parent
    (out/'TEST_ONLY_saved320.json').write_text(json.dumps({'action_id':saved['id']}),encoding='utf-8')
    reopen_saved(app);pump(app)
    app.project_tree.selection_set(*[r['id'] for r in app.project.rows]);app.copy_project_table()
    copied=app.clipboard_get();assert 'Délka [m]' in copied and '\t0,75\t' in copied and '\t0,6\t' in copied
    # Exercise the real XLSX export selection dialog and writer.
    xlsx=out/'TEST_ONLY_Length320.xlsx'
    def excel_options(dialog):
        dialog.result={'scope':'all','columns':[c[0] for c in app.PROJECT_COLUMNS]};dialog.destroy()
    with patch.object(messagebox,'showinfo'),patch.object(app,'wait_window',side_effect=excel_options),patch('tkinter.filedialog.asksaveasfilename',return_value=str(xlsx)),patch('os.startfile',create=True):
        app.export_project_xlsx()
    import openpyxl,pdfplumber
    book=openpyxl.load_workbook(xlsx,data_only=True);values=list(book.active.values);book.close()
    assert any('Délka [m]' in r for r in values) and '0,75' in str(values) and '0,6' in str(values),values
    rows=pdf_data_304.iso_decoder_rows(app)
    assert [r['source_meta']['source_length_mm'] for r in rows]==[750,600,500,300]
    pdf=out/'TEST_ONLY_Length320.pdf';hit_pdf.write_hit_proposal_pdf(pdf,project_name='TEST_ONLY Length320',rows=rows)
    with pdfplumber.open(pdf) as doc:
        text='\n'.join(p.extract_text() or '' for p in doc.pages)
        assert all(f'{n} mm' in text for n in (750,600,500,300)),text
        assert '35,3 kN/m' in text or '35.3 kN/m' in text
    # Detail presents actual length and offers the edit action on the stored row.
    import decoder_detail
    dialog=decoder_detail.DecoderDetailDialog(app,app.project.rows[0]);pump(app)
    pending=[dialog];texts=[]
    while pending:
        w=pending.pop();pending.extend(w.winfo_children())
        if isinstance(w,(ttk.Button,ttk.Label)):texts.append(str(w.cget('text')))
    assert '0,75 m' in texts and 'Upravit pozici / ks / délku…' in texts,texts
    dialog.destroy()
    # Clearing the manual value returns to the original catalogue, not a stale choice.
    test=deepcopy(app.project.rows[0]);length.set_length(test,None)
    assert length.effective_length(test)==1000
    return {'quick':True,'bulk_lengths_mm':[600,500,300],'edited_length_mm':750,
            'per_m_scaled_once':True,'per_piece_not_scaled':True,'old_choice_invalidated':True,
            'sqlite':True,'pdf':True,'xlsx':True}


def reopen_saved(app):
    import action_payload,decoder_length_320 as length
    data=json.loads((Path(app.settings_path).parent/'TEST_ONLY_saved320.json').read_text())
    store=action_payload.action_store(app)
    action_payload.load_action_record(app,store.load(data['action_id']))
    assert [length.effective_length(r) for r in app.project.rows]==[750,600,500,300]
