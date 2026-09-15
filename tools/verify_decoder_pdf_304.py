from __future__ import annotations
"""Actual installed GUI and PDF-data regression; all source fixtures TEST_ONLY.
HIT shear capacities come from the original SHA-verified manufacturer DoP.
T/XT decoder fixtures test schema matching, not manufacturer capacity approval.
No user project, user PDF, customer catalogue or production SQLite is modified.
"""
import base64,copy,gc,gzip,hashlib,io,json,logging,os,runpy,shutil,subprocess,sys,tempfile,time,traceback
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'updates/3.0.4'
LOCAL=os.environ.get('TURTO_LOCAL_SOURCE_TREE')=='1'
DEV=os.environ.get('TURTO_304_DEV')=='1'
CODES=[('P001',7,'T-KL-M1-V1-REI120-CV1-H180-2.2'),('P002',3,'T-KL-M5-V1-REI120-CV1-H180-2.2'),
 ('P003',47,'T-KL-M7-V1-REI120-CV1-H180-2.2'),('P004',48,'T-KL-M8-V1-REI120-CV1-H180-2.2'),
 ('P005',86,'T-ZL-EI120-H180-5.3'),('P006',2,'Schöck Sconnex W-N1-V1H1-B180-1.0'),
 ('P007',2,'T-QP-VV1-REI120-H200-L300-5.0'),('P008',8,'CXT-AP-MM1-VV1-REI30-LR200-B200-L300-1.0'),
 ('P009',8,'XT-KL-O-M3-V1-REI120-CV1-H250-7.2'),('P010',8,'XT-KL-M6-V3-REI120-CV1-H250-6.2')]

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def walk(w):
 yield w
 for c in w.winfo_children():yield from walk(c)
def main():
 reads=[]; cache={}; errors=[]
 report={'version':'3.0.4','platform':sys.platform,'local_tree_only':LOCAL,'development_mode':DEV,
         'fixtures':'TEST_ONLY schema and user-supplied schedule; not a reviewed Schock catalogue', 'checks':[]}
 def source(req,*a,**kw):
  url=urlparse(req.full_url if hasattr(req,'full_url') else str(req)); assert url.netloc=='raw.githubusercontent.com'
  owner,repo,commit,*parts=url.path.strip('/').split('/'); assert (owner,repo)==('jaroslavkucacz-code','TURTO-Izolacni-nosniky')
  key=commit+':'+('/'.join(parts)); reads.append(key)
  if key not in cache:cache[key]=ROOT.joinpath(*parts).read_bytes() if LOCAL else subprocess.check_output(['git','show',key],cwd=ROOT)
  return io.BytesIO(cache[key])
 with tempfile.TemporaryDirectory(prefix='turto304_') as tmp:
  root=Path(tmp); program=root/'Program'
  os.environ.update(TURTO_ROOT=str(root),TURTO_PROGRAM_DIR=str(program),APPDATA=str(root/'appdata'),LOCALAPPDATA=str(root/'localappdata'))
  shutil.copytree(ROOT/'updates/1.1.17/catalogs',root/'catalogs')
  sentinel=root/'actions.sqlite3'; sentinel.write_bytes(b'TEST_ONLY_CUSTOMER_SENTINEL'); before=digest(sentinel)
  with patch('urllib.request.urlopen',source):runpy.run_path(str(ROOT/'updates/3.0.3/runtime_installer.py'))['install_runtime'](root)
  if DEV:
   for name in ('app_runtime.pyw','isokorb_families_304.py','pdf_data_304.py'):shutil.copyfile(REL/name,program/name)
  else:
   installer=runpy.run_path(str(REL/'runtime_installer.py'))
   previous={p.name:p.read_bytes() for p in program.iterdir() if p.is_file()}
   replace=os.replace; fault=[False]
   def fail_once(src,dst):
    if Path(dst).name=='pdf_data_304.py' and not fault[0]:fault[0]=True;raise OSError('TEST_ONLY write failure')
    return replace(src,dst)
   with patch('urllib.request.urlopen',source),patch('os.replace',fail_once):
    try:installer['install_runtime'](root)
    except OSError:pass
    else:raise AssertionError('No rollback')
   assert fault[0] and {p.name:p.read_bytes() for p in program.iterdir() if p.is_file()}==previous
   with patch('urllib.request.urlopen',source):
    installer['install_runtime'](root); count=len(reads);installer['install_runtime'](root);assert len(reads)==count
   shutil.copyfile(REL/'app.pyw',root/'app.pyw');(root/'.turto_runtime_current.ok').write_text('35')
   boot=runpy.run_path(str(root/'app.pyw'));assert boot['_runtime_ready']()
   (program/'pdf_data_304.py').write_text('broken')
   assert not boot['_runtime_ready']()
   with patch('urllib.request.urlopen',source):boot['_repair_runtime']()
   assert boot['_runtime_ready']()
   report['checks']+=['actual 303 to 304 upgrade','rollback','idempotency','bootstrap repair']
  assert digest(sentinel)==before;sentinel.unlink()
  sys.path.insert(0,str(program));runtime=runpy.run_path(str(program/'app_runtime.pyw'));runtime['selftest']()
  import tkinter as tk
  from tkinter import ttk,messagebox
  import bulk_import,bulk_import_engine as engine,isokorb_families_304 as decoder,pdf_data_304 as export
  from catalog_engine import CatalogDatabase,QueryResult
  from project_model import create_project_row,query_from_selection
  import substitution_workspace as sub,hit_core,pdf_scope,fitz
  tk.Tk.report_callback_exception=lambda self,*exc:errors.append(''.join(traceback.format_exception(*exc)))
  # Concrete, generation, CV, height, length and model distractors must all be rejected.
  family={}
  for pos,qty,code in CODES:
   p=decoder.parse(code)
   if p is None or p.family=='AP':continue
   f=p.fields;fam=family.setdefault((p.model,p.family,f['generation']),dict(manufacturer='Schöck',model=p.model+' Typ',type=p.family,generation=f['generation'],records=[]))
   cover='CV'+f['cover'] if 'cover' in f else 'L='+f['length']+' mm'
   if p.family=='KL-O':cover+=' · w ≥ 210 mm'
   rec=dict(designation=code,moment_class=f.get('moment',f['shear']),shear_class=f['shear'] if 'moment' in f else '—',
    height_mm=f['height'],cover=cover,concrete_min='C25/30',element_length_mm=int(f.get('length',1000)),
    insulation_thickness_mm=80 if p.model=='T' else 120,source_pages=[1],
    results=[dict(kind='shear',label='TEST_ONLY VRd',positive=30.,negative=-30. if f['shear'].startswith('VV') else 0.,unit='kN/prvek')])
   fam['records'].append(rec)
  folder=root/'TEST_ONLY_catalogs';folder.mkdir(); shutil.copyfile(ROOT/'updates/1.1.17/catalogs/schoeck_sconnex_w_2023.json',folder/'sconnex.json')
  def savedb(fams):
   (folder/'fixtures.json').write_text(json.dumps({'schema_version':2,'catalog':{'id':'TEST_ONLY','edition':'TEST_ONLY schema fixture'},'families':fams}),encoding='utf-8')
   return CatalogDatabase(folder)
  source_db=savedb(list(family.values()))
  with patch.object(messagebox,'showerror',lambda *a,**kw:errors.append(str(a))),patch.object(messagebox,'showwarning',lambda *a,**kw:None),patch.object(messagebox,'askyesno',return_value=True):
   app=runtime['_base'].ThermalConnectorApp();app.update();assert '3.0.4' in app._turto_brand_title.cget('text')
   app.database=source_db
   d=bulk_import.BulkImportDialog(app,database=source_db,colors=app.colors,preferred_concrete='C25/30',existing_positions=[],start_position='P001')
   d.text.insert('1.0','\n'.join(f'{p}\t{q}\t{c}' for p,q,c in CODES));d.analyze_button.invoke()
   deadline=time.monotonic()+30
   while d._analysis_running and time.monotonic()<deadline:app.update();time.sleep(.02)
   app.update();assert not d._analysis_running and len(d.items)==10
   for item in d.items:
    if item.position=='P005':item.status='manual';continue
    assert item.ready,(item.position,item.message,len(item.candidates))
    raw=create_project_row(item.result,position=item.position,quantity=item.quantity,source_text=item.designation)
    assert query_from_selection(source_db,raw['selection']).results==raw['snapshot']['results']
   d._refresh_review_tree();assert d.items[4].status=='manual' and 'ISO 3.0.4' in d.summary_var.get()
   ap_item=d.items[7]; assert ap_item.result.record['substitution_policy']=='manual'
   assert all('value' not in r and 'positive' not in r for r in ap_item.result.results)
   ap_row=create_project_row(ap_item.result,position='AP_TEST',quantity=8,source_text=decoder.AP_CODE)
   report['decoder']=[{'position':x.position,'status':x.status,'candidates':len(x.candidates)} for x in d.items]
   from PIL import ImageGrab
   ImageGrab.grab().save(ROOT/f'decoder304-window-{sys.platform}.png');d.destroy()
   def classify(db,code):
    i=engine.BulkImportItem(1,code,'X',1,code);engine._classify_bulk_item(db,i,preferred_concrete='C25/30',suggestion_limit=80);return i
   q=CODES[6][2];k=CODES[8][2]
   for code in (q.replace('VV1','V1'),q.replace('H200','H240'),q.replace('L300','L400'),q.replace('5.0','7.0'),q.replace('T-','XT-',1),decoder.AP_CODE.replace('LR200','LR220'),decoder.AP_CODE.replace('B200','B220'),decoder.AP_CODE.replace('1.0','1.1'),k.replace('CV1','CV2'),q+'-extra'):
    item=classify(source_db,code);assert not item.ready and not item.candidates,(code,item.message)
    report['checks'].append('reject '+code)
   assert classify(source_db,'Schöck Isokorb® T typ QP-VV1-REI120-H200-L300-5.0').ready
   alt=copy.deepcopy(list(family.values())); f=next(f for f in alt if f['type']=='KL-O');rec=copy.deepcopy(f['records'][0]);rec['cover']='CV1 · w ≥ 230 mm';f['records'].append(rec)
   ambiguous=classify(savedb(alt),k);assert ambiguous.status=='review' and len(ambiguous.candidates)==2 and ambiguous.varying_keys==('cover',)
   source_db=savedb(list(family.values()))
   report['checks']+=['series not inferred from generation','different geometric conditions remain review','manual ignore preserved','informational AP has no invented M/V capacity']

   # Reuse the reviewed 303 manufacturer-source inspection for a real shear design.
   from verify_zvx_303 import acquire_pdf
   import zvx_tables_303 as zvx
   import pdfplumber
   pdf=root/'source.pdf';acquire_pdf(pdf,zvx.SOURCE_URL,zvx.SOURCE_SHA256)
   with pdfplumber.open(pdf) as doc:records=zvx.parse_zvx_pages(doc)
   data={'schema_version':4,'source_document':'CONF-DOP_HIT-HP/SP-07-23','source_sha256':zvx.SOURCE_SHA256,'zvx_records':records}
   hit_file=root/'TEST_ONLY_hit.b64';hit_file.write_bytes(base64.b64encode(gzip.compress(json.dumps(data).encode())))
   assert app._load_hit_data(hit_file,quiet=True)
   from isokorb_xt_parser_243 import _SAMPLE_ROWS,parse_xt_designation
   from iso_bulk_301 import candidates_for
   values=[35.3,56.4,70.5,87.8,87.8,98.0,117.6,153.6,34.5,58.8,68.9,68.9,104.,104.,115.2];fams={}
   for (code,qty,typ),v in zip(_SAMPLE_ROWS[13:28],values):
    f=parse_xt_designation(code).fields;fam=fams.setdefault(typ,dict(manufacturer='Schöck',model='XT',type=typ,generation=f['generation'],insulation_thickness_mm=120,records=[]))
    fam['records'].append(dict(designation=code,moment_class=f['shear'],shear_class='—',cover='L='+f['length']+' mm' if 'length' in f else '—',height_mm=f['height'],concrete_min='C25/30',element_length_mm=int(f.get('length',1000)),
       compression_transfer='bez tlakových ložisek' if typ=='QP-Z' else 'betonová tlaková ložiska',results=[dict(kind='shear',label='USER_SCHEDULE V',key='v',positive=v,negative=-v if typ=='QL' else 0.,unit='kN/m' if typ=='QL' else 'kN/element')]))
   app.database=savedb(list(fams.values()));app.project.rows=[]
   for i,(code,qty,typ) in enumerate(_SAMPLE_ROWS[13:28],14):
    choices=candidates_for(app.database,parse_xt_designation(code),'C25/30');assert len(choices)==1
    app.project.rows.append(create_project_row(choices[0].result,position=f'P{i:03d}',quantity=qty,source_text=code))
   app.refresh_substitution_tree();next(w for w in walk(app) if isinstance(w,ttk.Button) and str(w.cget('text'))=='Navrhnout vše').invoke();app.update()
   # Corrupt GUI labels/column order to prove that export does not scrape headings.
   for col in app.sub_tree['columns']:app.sub_tree.heading(col,text='TEST_ONLY translated heading')
   app.sub_tree.selection_set(app.sub_tree.get_children()[0])
   frozen=copy.deepcopy(app.project.rows)
   rows=pdf_scope.rows_for_scope(app,'iso.substitution');assert len(rows)==15 and app.project.rows==frozen
   assert all(r['calculation_valid'] and r['target'] for r in rows),[(r['name'],r['notes']) for r in rows if not r['calculation_valid']]
   row21=next(r for r in rows if r['name']=='P021')
   assert row21['target_designation']=='HIT-SP ZVX-0403-24-050-30-12'
   assert row21['target']['checks'][0]['requirement']==153.6 and row21['target']['checks'][0]['capacity']==167.75
   assert row21['target']['checks'][0]['unit']=='kN/prvek'
   assert abs(row21['target']['utilization']-153.6/167.75)<1e-8
   assert rows[0]['target']['checks'][1]['label']=='V−'
   app.shear_substitution_rows=[dict(name='S001',quantity=1,source_designation='Schöck Dorn LD 25-S-A4',slab_mm=200,gap_mm=20,concrete='C25/30',source={'designation':'Schöck Dorn LD 25-S-A4','vrd':31.3},target={'designation':'Ancon ESD 15 / 300','vrd':32.,'source':'TEST_ONLY user-PDF reproduction'},status='VYHOVUJE',verification_mode='catalog',capacity_ratio=32/31.3)]
   app.shear_decoder_rows=[dict(name='SD001',quantity=2,designation='Schöck Dorn LD 25-S-A4',manufacturer='Schöck',family='LD',slab_mm=200,gap_mm=20,concrete='C25/30',archive_vrd=31.3,archive_source='TEST_ONLY')]
   app.project.name='TEST_ONLY – přenos dat PDF';app.project_name_var.set(app.project.name)
   texts={}
   for label,scopes in [('substitution',['iso.substitution']),('mixed',['iso.substitution','shear.substitution']),('decoder',['iso.decoder']),('all',pdf_scope.ALL_SCOPE_IDS)]:
    path=ROOT/f'decoder304-{label}-{sys.platform}.pdf'
    with patch.object(pdf_scope.filedialog,'asksaveasfilename',return_value=str(path)),patch.object(pdf_scope,'_open'):
     pdf_scope.export_pdf(app,scopes)
    assert path.exists() and not errors,errors
    doc=fitz.open(path);text='\n'.join(p.get_text() for p in doc);texts[label]=text
    assert 'DECODED' not in text and 'Navržený HIT: Schöck' not in text
    if label!='decoder':assert '167,8' in text and '91,6 %' in text and '153,6' in text and 'HIT-SP ZVX-0403-24-050-30-12' in text
    if label=='mixed':assert 'Ancon ESD 15 / 300' in text and '102,2 %' in text and 'Technické prvky' in text
    if label=='decoder':assert 'DEKÓDOVÁNO' in text and 'VYHOVUJE' not in text
    if label=='all':assert 'SD001' in text and '31.3' in text
    if label=='substitution':
     doc[0].get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(ROOT/f'decoder304-pdf-summary-{sys.platform}.png')
     for p in doc:
      if 'P021' in p.get_text() and 'Požadavek' in p.get_text():p.get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(ROOT/f'decoder304-pdf-detail-{sys.platform}.png');break
    report[label+'_pdf_pages']=len(doc);doc.close()
   assert app.project.rows==frozen
   # A separate TEST_ONLY moment fixture checks sign, interaction, units and
   # a non-first selected alternative. It is not a manufacturer design value.
   moment=copy.deepcopy(frozen[0]);moment['position']='M_TEST';moment['source_text']='XT-KL-M3-V1-REI120-CV1-H240-6.2'
   moment['selection'].update(type_name='KL',generation='6.2',moment_class='M3',shear_class='V1',cover='CV1',height_mm='240')
   moment['snapshot']['designation']=moment['source_text']
   moment['snapshot']['results']=[dict(kind='moment',positive=0.,negative=-38.,unit='kNm/m'),dict(kind='shear',positive=21.,negative=0.,unit='kN/m')]
   t=moment['mapping']['targets'][0];t.update(id='TEST_MVX_selected',designation='TEST_ONLY HIT-SP MVX SELECTED SECOND',connection_type='MVX',cover_mm=35,
      utilization=.8,interaction_utilization=.8,m1=50.,v1=40.,m_capacity_element=50.,v_capacity_element=40.,
      source_element_actions=dict(m_pos=0.,m_neg=38.,v_pos=21.,v_neg=0.,n_pos=0.,n_neg=0.),
      checks=[dict(label='M−',requirement=38.,capacity=50.,eta=.76,unit='kNm/prvek',result='VYHOVUJE'),dict(label='V+',requirement=21.,capacity=40.,eta=.525,unit='kN/prvek',result='VYHOVUJE')])
   other=copy.deepcopy(t);other.update(id='TEST_MVX_first',designation='TEST_ONLY UNSELECTED FIRST')
   moment['mapping'].update(targets=[other,t],selected_target_id=t['id'],status='ok',warnings=[],errors=[],estimated_type='MVX')
   app.project.rows=[moment];out=export.iso_substitution_rows(app)[0]
   assert out['calculation_valid'] and out['target']['utilization']==.8,(out['notes'],out['source_meta'])
   assert out['target_designation'].endswith('SELECTED SECOND') and out['source_actions']['m_neg']==38.
   momentpath=ROOT/f'decoder304-moment-{sys.platform}.pdf'
   with patch.object(pdf_scope.filedialog,'asksaveasfilename',return_value=str(momentpath)),patch.object(pdf_scope,'_open'):pdf_scope.export_pdf(app,['iso.substitution'])
   with fitz.open(momentpath) as doc:
    mt='\n'.join(p.get_text() for p in doc)
    assert 'kNm/prvek' in mt and '80,0 %' in mt and 'SELECTED SECOND' in mt and 'UNSELECTED FIRST' not in mt
   report['checks']+=['negative moment kNm/prvek','non-first selected target','interaction utilization 80 percent preserved']
   # Existing numerical-design adapters are retained; all six scopes must be
   # present in a mixed export, including direct HIT and shear-dowel design.
   fixture_design=dict(name='DESIGN_TEST',quantity=1,connection_type='MVX',series='SP',height_mm='240',cover_mm='35',concrete='C25/30',
     required_length_mm='1000',actions=dict(m_neg=20.,v_pos=10.,m_pos=0.,v_neg=0.,n_pos=0.,n_neg=0.),status='VYHOVUJE',notes=[],
     candidate=dict(designation='TEST_ONLY DIRECT HIT',connection_type='MVX',series='SP',height=240,cover=35,concrete='C25/30',physical_length_mm=1000,
                    utilization=.5,m1=40.,v1=40.,m2=40.,v2=40.,mode='TEST_ONLY',page=1,spacing_max=0.))
   fixture_shear=dict(domain_id='shear_dowels',name='DOWEL_DESIGN_TEST',quantity=1,group='Návrh',series='Ancon',connection_type='DOWEL',height_mm=200,cover_mm=30,concrete='C25/30',required_length_mm=20,
     custom_actions=[dict(label='VEd',value='20',unit='kN')],candidate=dict(designation='TEST_ONLY DIRECT DOWEL',utilization=.5,vrd=40.,height=200,gap_mm=20),status='VYHOVUJE',notes=[])
   with patch.object(pdf_scope._legacy._thermal,'collect_all_hit_rows',return_value=[copy.deepcopy(fixture_design)]),patch.object(app,'collect_shear_report_rows',return_value=[copy.deepcopy(fixture_shear)]):
    scopes=export.collect_sections(app);assert all(scopes.get((x.domain,x.tab)) for x in pdf_scope.SCOPES)
    assert scopes[('thermal_breaks','design')][0]['candidate']==fixture_design['candidate']
    path=ROOT/f'decoder304-six-scopes-{sys.platform}.pdf'
    with patch.object(pdf_scope.filedialog,'asksaveasfilename',return_value=str(path)),patch.object(pdf_scope,'_open'):pdf_scope.export_pdf(app,pdf_scope.ALL_SCOPE_IDS)
    with fitz.open(path) as doc:
     dt='\n'.join(p.get_text() for p in doc);assert 'DESIGN_TEST' in dt and 'DOWEL_DESIGN_TEST' in dt and 'TEST_ONLY DIRECT HIT' in dt and 'TEST_ONLY DIRECT DOWEL' in dt
   report['checks']+=['six scopes with preserved numerical-design data']
   app.project.rows=frozen
   # PDF collection must not convert incomplete/stale/malformed states into zero utilization success.
   for mode in ('missing_target','missing_utilization','nan','missing_checks','changed_source','changed_height'):
    app.project.rows=copy.deepcopy(frozen[:1]);raw=app.project.rows[0];t=sub.selected_target(raw['mapping'])
    if mode=='missing_target':raw['mapping']['selected_target_id']='NONEXISTENT'
    elif mode=='missing_utilization':t.pop('utilization')
    elif mode=='nan':t['checks'][0]['eta']=float('nan')
    elif mode=='missing_checks':t['checks']=[]
    elif mode=='changed_source':raw['snapshot']['results'][0]['positive']*=1.1
    else:raw['selection']['height_mm']='250'
    out=export.iso_substitution_rows(app)[0];assert not out['status'].startswith('VYHOVUJE'),mode
    assert not out.get('candidate') or out['candidate'].get('utilization') is None or mode in {'nan','missing_checks'},mode
    report['checks'].append('no false PDF pass: '+mode)
   app.project.rows=[ap_row];ap_report=export.iso_decoder_rows(app)[0]
   assert ap_report['source_meta']['source_height_mm'] is None and ap_report['status']=='ZVLÁŠTNÍ POSOUZENÍ'
   assert not sub.design_targets(app.hit_db,row=ap_row,metadata=sub.source_metadata(ap_row))[0]
   # Round trip both selection and mapping, then export the reloaded action.
   app.project.rows=frozen
   from action_store import ActionStore
   from action_payload import serialize_action,load_action_record
   store=ActionStore(root/'TEST_ONLY_roundtrip.sqlite3');rec=store.save(action_name='TEST_ONLY304',payload=serialize_action(app))
   app.project.rows=[];load_action_record(app,store.load(rec['id']));app.update()
   reloaded=export.iso_substitution_rows(app);assert len(reloaded)==15
   assert next(r for r in reloaded if r['name']=='P021')['target']['utilization']==row21['target']['utilization']
   assert not errors,errors
   report.update(actual_analyze_button=True,actual_design_all_button=True,actual_export_entrypoint=True,
     structured_no_headings=True,selection_scope_independent=True,original_rows_unchanged=True,sqlite_roundtrip=True,
     target_units='kN/prvek',target_values_source_sha256=zvx.SOURCE_SHA256)
   app.destroy();del app,store;logging.shutdown();gc.collect()
 (ROOT/f'decoder304-test-{sys.platform}.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
