"""Reproduce the reviewed subset from ORIGINAL Peikko PDFs (not OCR).

Developer-only tool: python build_peikko_tables_2230.py EBEA.pdf TEBEA-ETA.pdf
Requires PyMuPDF for extraction; the installed application uses only stdlib JSON.
All numeric rows are exact transcriptions. No inferred or interpolated capacities.
"""
from pathlib import Path
import hashlib
import gzip
import json
import re
import sys

EBEA_SHA = '1ea1abffe83a5c6e32b37287c5fba44d79ec63863f1dd17e93e5340846f80121'
ETA_SHA = '9cabd5553b35636e03c91ed06ca0d45bef924bc4ada596129bda5fd5cf0d250d'
ROOT = Path(__file__).resolve().parents[1]

def build(ebea_path, eta_path):
    import fitz
    for path, expected in ((ebea_path, EBEA_SHA), (eta_path, ETA_SHA)):
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError('Different source revision; repeat visual review before extraction: ' + str(path))
    doc = fitz.open(ebea_path)
    def grid(page, table, end, first, cols, rows):
        text = doc[page-1].get_text().split('Table ' + str(table) + '.', 1)[1]
        text = re.split(r'(?m)^' + str(first) + r'\s*$', text, maxsplit=1)[1]
        text = str(first) + '\n' + text.split(end, 1)[0]
        numbers = [int(x) for x in re.findall(r'\d+', text)]
        assert len(numbers) == cols*rows, (page, table, len(numbers), cols*rows)
        result = [numbers[i:i+cols] for i in range(0, len(numbers), cols)]
        assert [r[0] for r in result] == list(range(first, first+20*rows, 20))
        return result
    columns = [(2,10),(2,14),(4,10),(6,10),(4,14),(6,14),(8,14),(10,14)]
    constraints = [(1,1,200),(1,1,200),(1,3,400),(1,5,600),(1,3,400),(1,5,600),(2,7,800),(2,7,1000)]
    bending=[]; shear=[]
    models = {
      '100': {'covers_mm':[30,25], 'materials':['RS','VE1','VE2'], 'moment_sign':'negative', 'bending_table':3,'shear_table':4,'page':15,'geometry_page':14,'min_D':140},
      'E-100': {'covers_mm':[45,30], 'materials':['RS','VE1','VE2'], 'moment_sign':'negative','bending_table':6,'shear_table':7,'page':17,'geometry_page':16,'min_D':160},
      '700': {'covers_mm':[30,30], 'materials':['VE1','VE2'], 'moment_sign':'both','bending_table':16,'shear_table':17,'page':25,'geometry_page':24,'min_D':140},
    }
    for model,page,bt,st,first,rows in [('100',15,3,4,140,9),('E-100',17,6,7,160,8)]:
        for row in grid(page,bt,'Quantity of shear',first,17,rows):
            for i,(n,diameter) in enumerate(columns):
                low,high,lmin=constraints[i]
                bending.append(dict(model=model,D=row[0],n=n,diameter=diameter,MRd=row[1+2*i],k=row[2+2*i],
                    shear_min=low,shear_max=high,Lmin=lmin,source='ebea_004',page=page,table=str(bt)))
        for row in grid(page,st,'Note:',first,16,rows):
            for iso,offset in [(80,2),(120,9)]:
                for i in range(7):
                    shear.append(dict(model=model,D=row[0],H=row[1],iso=iso,shear_count=i+1,VRd=row[offset+i],source='ebea_004',page=page,table=str(st)))
    for row in grid(25,16,'NRd [',140,25,9):
        for group,s11 in enumerate([120,160,200]):
            for i,n in enumerate([2,3,4,6]):
                idx=1+group*8+i*2
                bending.append(dict(model='700',D=row[0],n=n,diameter=10,S11_group=s11,MRd=row[idx],k=row[idx+1],
                    NRd_source_value=[124,186,248,372][i],NRd_source_unit='kNm/pcs',NRd_unit_verified=False,
                    shear_min=1,shear_max=[1,2,3,5][i],Lmin=[200,300,400,600][i],source='ebea_004',page=25,table='16'))
    for row in grid(25,17,'Note:',140,12,9):
        for iso,offset in [(80,2),(120,7)]:
            for i in range(5):
                shear.append(dict(model='700',D=row[0],H=row[1],iso=iso,shear_count=i+1,VRd=row[offset+i],source='ebea_004',page=25,table='17'))
    components=[]
    def part(table,page,kind,**kwargs):
        components.append(dict(source='tebea_eta01',table=table,page=page,kind=kind,unit='kN/component',full_connector=False,**kwargs))
    for concrete,value in [('C20/25',27.5),('C25/30',29.9),('>=C30/37',33.1)]:
        part('A2.2',7,'concrete_buffer',concrete=concrete,c1_min_mm=50,value=value,limit_state='concrete_edge_failure')
    for steel,values in [('1.4482',[21.9,30.6,47.8,66.9]),('1.4362',[21.9,28.4,44.4,63.9])]:
        for i,(black,stainless) in enumerate([(8,8),(10,8),(12,10),(14,12)]):
            part('A3.1',8,'tension',steel=steel,black_diameter=black,stainless_diameter=stainless,iso=120,
                 lap_length_mm=[445,545,722,865][i],lap_extension_mm=[0,20,17,15][i],value=values[i],lap_condition='C25/30; H <= 250 mm')
        part('A3.1',8,'headed_tension',steel=steel,black_diameter=12,stainless_diameter=10,iso=120,
             lap_length_mm=722,lap_extension_mm=17,value=values[2],concrete_min='C25/30',lap_condition='C25/30; H <= 250 mm')
    for diameter,values in [(8,[12.5,13.3,14.0,14.8,15.5,16.1,16.7,17.3,17.9,18.4,18.9]),
                            (10,[19.6,20.8,21.9,23.1,24.1,25.2,26.2,27.1,28.0,28.8,29.6]),
                            (12,[28.2,29.9,31.6,33.2,34.8,36.3,37.7,39.0,40.3,41.5,42.6])]:
        for i,value in enumerate(values):
            part('A5.1',10,'shear_bar',diameter=diameter,angle_deg=35+2.5*i,value=value,steel_yield_MPa=500,condition='HM-W requires concrete >= C25/30; angle measured as in ETA diagram')
    for steel,values in [('1.4482',[18.4,33.8,50.9,69.4]),('1.4362',[18.3,29.8,42.5,66.6])]:
        for i,diameter in enumerate([8,10,12,14]):
            part('A5.2',10,'compression_bar',steel=steel,stainless_diameter=diameter,black_diameter=[None,12,14,16][i],
                anchorage_mm=[275,350,445,525][i],anchorage_extension_mm=[None,17,15,13][i],value=values[i],limit_state='buckling',anchorage_condition='C25/30; H <= 250 mm')
    for diameter,steel,value in [(12,'1.4482',43.9),(14,'1.4482',43.9),(12,'1.4362',42.5)]:
        part('A6.1',11,'headed_compression',diameter=diameter,steel=steel,iso=120,value=value,concrete_min='C20/25',plate_mm=[40,40,12],limit_state='minimum of concrete edge and buckling')
    data=dict(schema_version=1,data_version='2.2.30',reviewed_on='2026-09-12',
      sources={
        'ebea_004':dict(title='Peikko EBEA Technical Manual',revision='004; 08/2023',country_scope='Peikko Group; manuál odkazovaný českou stránkou výrobce',sha256=EBEA_SHA,
            url='https://media.peikko.com/file/dl/i/OGas3A/Nous9DJNosZwZjufJk_Uiw/EBEA_Peikko_Group_004_Technical_Manual_Web.pdf?fv=5548',filename='EBEA_004_2023.pdf',visual_review_pages=[14,15,16,17,24,25]),
        'tebea_eta01':dict(title='ETA 23/0525',revision='01; 2025-02-10',country_scope='Evropské technické posouzení; zde pouze údaje součástí',sha256=ETA_SHA,
            url='https://media.peikko.com/file/dl/i/cPI0Nw/75qMwAS9V0SMGRPKy9iGbg/ETA_23-0525_version-01_Peikko_TEBEA.pdf?fv=f80a',filename='TEBEA_ETA_23-0525_v01.pdf',visual_review_pages=[7,8,10,11])},
      models=models,bending=bending,shear=shear,tebea_components=components,
      concrete_reduction={'C20/25':0.8,'C25/30_and_higher':1.0,'source':'ebea_004','page':7,'applies_to':'resistance, NOT stiffness'},
      issues=[{'source':'ebea_004','page':25,'table':'16','issue':'Axial NRd source unit is printed kNm/pcs. Preserve raw values; no automated M+N check until unit is independently confirmed.'},
              {'source':'tebea_eta01','page':11,'table':'A6.1','issue':'Last row (diameter 14, 1.4362) prints insulation 1 mm. Excluded from usable component rows; do not silently correct to 120.'}],
      limitations=['No full design approval or automatic substitutions.','D is the standard connector height, not inferred from Ds/Dt.','OQ, B2 and custom configurations require manufacturer confirmation.','No interpolation or bar-count scaling.','TEBEA component values are never total connector capacities.'])
    assert len(bending)==244 and len(shear)==328 and len(components)==57
    # Deterministic compressed JSON keeps the incremental runtime small.
    # Inspect with: gzip -cd peikko_technical_data.json.gz | python -m json.tool
    target=ROOT/'updates/2.2.30/peikko_technical_data.json.gz'
    target.write_bytes(gzip.compress(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8'),mtime=0))
    print(f'{target}: {len(bending)} bending rows; {len(shear)} shear rows; {len(components)} component rows')

if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('Usage: build_peikko_tables_2230.py EBEA.pdf TEBEA-ETA.pdf')
    build(sys.argv[1],sys.argv[2])
