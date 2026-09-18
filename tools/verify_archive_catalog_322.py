"""Archive source identity, actual user schedule, HIT demands and persistence."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch


def exercise(app):
    import archive_catalog_322 as archive
    import catalog_browser, bulk_import_engine as bulk, project_model as pm
    import action_payload, decoder_length_320 as length
    import substitution_workspace as sub, pdf_data_304, hit_pdf
    from catalog_engine import SelectionError
    from tkinter import messagebox
    from verify_workflow_317 import pump
    text=(Path(__file__).parent/'fixtures/schoeck_format_321.txt').read_text(encoding='utf-8')
    items,_=bulk.analyze_bulk_text(app.database,text,preferred_concrete='C25/30')
    expected={0:(-34.9,61.8),1:(-16.7,61.8),2:(-40.5,154.5),
              3:(-49.4,92.7),6:(-34.9,154.5),10:(-23.7,61.8),12:(-29.3,61.8)}
    assert {i for i,item in enumerate(items) if item.ready}==set(expected)
    assert sum(item.quantity for item in items if item.ready)==2311
    for n,(moment,shear) in expected.items():
        r=items[n].result
        assert r.catalog['id']==archive.CATALOG_ID and r.family['generation']=='2.0'
        assert r.results==[dict(key='m_rd_y',label='mRd,y',kind='moment',value=moment,unit='kNm/m'),
                           dict(key='v_rd_z',label='vRd,z',kind='shear',positive=shear,unit='kN/m')]
        assert r.record['source_pages']==[44,45,47 if n==3 else 46]
        assert r.catalog['source_sha256']=='9b60590c4e8d91c5752da49506942ef1058e7eb14652037d01f19b9ea61ebf6c'
        quick=app.database.resolve_designation(items[n].designation,preferred_concrete='C25/30')
        assert quick.results==r.results
    assert '7.1' in items[4].message and 'bez statické funkce' in items[7].message
    assert items[5].status=='review' and not items[11].ready
    def resolve(tail):
        return app.database.resolve_designation('T-KL-'+tail,preferred_concrete='C25/30')
    for tail,moment in [('M1-V1-REI120-CV1-H160-2.0',-7.6),
                        ('M6-V2-REI120-CV2-H180-2.0',-28.5),
                        ('M10-V1-REI120-CV2-H180-2.0',-49.2),
                        ('M12-VV1-REI120-CV2-H300-2.0',-153.6),
                        ('M12-V2-REI120-CV1-H300-2.0',-164.7)]:
        assert resolve(tail).results[0]['value']==moment
    vv=resolve('M12-VV1-REI120-CV2-H300-2.0').results[1]
    assert vv['positive']==92.7 and vv['negative']==-61.8
    for tail in ('M10-V1-REI120-CV1-H180-2.0','M10-V2-REI120-CV1-H190-2.0',
                 'M1-V1-REI120-CV2-H170-2.0','M1-V1-REI120-CV1-H205-2.0',
                 'M1-V1-REI120-CV1-H310-2.0','M1-V1-REI120-CV1-H200-9.9'):
        try:resolve(tail)
        except SelectionError as e:
            if tail.startswith('M10'):assert 'nejasné znaménko' in str(e)
        else:raise AssertionError(tail)
        failed,_=bulk.analyze_bulk_text(app.database,'T-KL-'+tail,preferred_concrete='C25/30')
        assert not failed[0].ready and not failed[0].candidates
    family=app.database.get_family(archive.CATALOG_ID,'Schöck','T','KL','2.0')
    assert len(family['records'])==1002
    links=[c for c in catalog_browser.CATALOGS if c.source_url==items[0].result.catalog['source_url']]
    assert len(links)==1 and '2023.1' in links[0].title
    # Reinstalling data is idempotent and never mutates a customer's same-ID data.
    base=app.database
    while hasattr(base,'base'):base=base.base
    before=deepcopy(base.catalogs[archive.CATALOG_ID]);count=len(base.families)
    archive.add_catalog(base)
    assert len(base.families)==count and base.catalogs[archive.CATALOG_ID]==before
    # Actual quick entry with the original pasted spelling and custom length.
    app.product_domain_notebook.select(app.product_domain_tab_by_id['thermal_breaks'])
    app.main_notebook.select(app.project_tab);pump(app)
    app.project.rows=[];app.refresh_project_tree()
    app.project_quick_designation_var.set(items[0].designation)
    app.project_quick_length_var.set('0,5');app.quick_add_project_row();pump(app)
    row=app.project.rows[0]
    assert row['source_text']==items[0].designation and row['selection']['generation']=='2.0'
    assert length.effective_length(row)==500
    totals,warnings=sub.source_element_actions(row)
    assert totals.m_neg==17.45 and totals.v_pos==30.9 and not warnings
    # Verify the real substitution pipeline receives the archived capacities.
    # The test supplies no invented HIT capacities or passing alternatives.
    calls=[]
    class TargetProbe:
        def proposal_candidates(self,*args,**kwargs):
            calls.append(args)
            return [],'',None
    sub.design_targets(TargetProbe(),row=row,metadata=sub.source_metadata(row))
    assert calls
    for call in calls:
        actions=call[5];code=next(iter(call[6]));millimetres={25:250,33:333,50:500,100:1000}[code]
        assert abs(actions.m_neg*millimetres/1000-17.45)<1e-8
        assert abs(actions.v_pos*millimetres/1000-30.9)<1e-8
    # SQLite retains source edition and capacities; they are not upgraded to 2.2.
    store=action_payload.action_store(app)
    saved=store.save(action_name='TEST_ONLY archive322',payload=action_payload.serialize_action(app))
    out=Path(app.settings_path).parent
    (out/'TEST_ONLY_saved322.json').write_text(json.dumps({'id':saved['id'],'rows':app.project.rows}),encoding='utf-8')
    reopen_saved(app);pump(app)
    pdf_rows=pdf_data_304.iso_decoder_rows(app)
    pdf=out/'TEST_ONLY_Archive322.pdf'
    hit_pdf.write_hit_proposal_pdf(pdf,project_name='TEST_ONLY archive322',rows=pdf_rows)
    import pdfplumber,openpyxl
    with pdfplumber.open(pdf) as doc:
        printed='\n'.join(p.extract_text() or '' for p in doc.pages)
    assert '2023.1' in printed and '46' in printed and '500 mm' in printed,printed
    assert '34,9' in printed or '34.9' in printed,printed
    xlsx=out/'TEST_ONLY_Archive322.xlsx'
    def options(dialog):
        dialog.result={'scope':'all','columns':[c[0] for c in app.PROJECT_COLUMNS]};dialog.destroy()
    with patch.object(messagebox,'showinfo'),patch.object(app,'wait_window',side_effect=options),patch('tkinter.filedialog.asksaveasfilename',return_value=str(xlsx)),patch('os.startfile',create=True):
        app.export_project_xlsx()
    book=openpyxl.load_workbook(xlsx,data_only=True);values=str(list(book.active.values));book.close()
    assert '2023.1' in values and ('34,9' in values or '34.9' in values),values
    return {'archive_records':1002,'user_rows_ready':7,'user_quantity_ready':2311,
            'unclear_cells_excluded':True,'hit_demands':True,'sqlite':True,'pdf':True,'xlsx':True}


def reopen_saved(app):
    import action_payload
    record=json.loads((Path(app.settings_path).parent/'TEST_ONLY_saved322.json').read_text(encoding='utf-8'))
    store=action_payload.action_store(app)
    action_payload.load_action_record(app,store.load(record['id']))
    assert app.project.rows==record['rows']
