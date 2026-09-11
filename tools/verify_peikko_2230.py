from __future__ import annotations
"""Reviewed table golden cells, negative design cases, serialization and local PDF cache."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'updates/2.2.30'
sys.path[:0]=[str(RELEASE),str(ROOT/'updates/1.1.17')]
from peikko_technical import data, reference, compare_loads, preselect, number, integer, format_reference, format_comparison
from peikko_thermal_breaks import decode_peikko, normalize_bulk_text
from peikko_catalog import make_result, catalog_class, CATALOG_ID
from peikko_documents import fetch_document

STANDARD='EBEA-100 RS 4x10-2 D200 SW80 L500'
def ref(text=STANDARD, **kw):
    return reference(text,concrete=kw.pop('concrete','C25/30'),geometry_confirmed=kw.pop('geometry_confirmed',True),**kw)

def choices(**kw):
    args=dict(model='100',standard_d_mm=200,insulation_mm=80,length_mm=1000,material='RS',concrete='C25/30',
        moment=-19,shear=21,geometry_confirmed=True)
    args.update(kw);return preselect(**args)

class Tables(unittest.TestCase):
    def test_01_source_counts_and_distinct_keys(self):
        d=data();self.assertEqual((len(d['bending']),len(d['shear']),len(d['tebea_components'])),(244,328,57))
        for key, fields in [('bending',('model','D','n','diameter','S11_group')),('shear',('model','D','iso','shear_count'))]:
            rows=d[key];self.assertEqual(len(rows),len({tuple(r.get(k) for k in fields) for r in rows}))
            self.assertTrue(all(r['source']=='ebea_004' and r['page'] in (15,17,25) for r in rows))
        self.assertEqual(d['sources']['ebea_004']['sha256'],'1ea1abffe83a5c6e32b37287c5fba44d79ec63863f1dd17e93e5340846f80121')
    def test_02_straight_golden(self):
        r=ref();self.assertEqual((r['MRd'],r['VRd'],r['k']),(23,76,2995));self.assertTrue(r['configuration_matched']);self.assertFalse(r['design_verified'])
        r=ref('EBEA-100 VE2 10x14-3 D200 SW120 L1000');self.assertEqual((r['MRd'],r['VRd'],r['k']),(110,93,12562))
    def test_03_corner_not_straight(self):
        r=ref('EBEA-E100 RS 4x10-3 D200 SW80 L500');self.assertEqual((r['MRd'],r['VRd'],r['k']),(20,99,2334));self.assertEqual(r['covers_mm'],[45,30])
        self.assertFalse(ref('EBEA-E100 RS 4x10-3 D140 SW80 L500')['configuration_matched'])
    def test_04_s11_changes_moment(self):
        a=ref('EBEA-700 VE1 4x10-3 D200 SW80 L1000 S11=120');b=ref('EBEA-700 VE1 4x10-3 D200 SW80 L1000 S11=370')
        self.assertEqual((a['MRd'],b['MRd'],a['k'],b['k']),(15,19,1317,1317));self.assertEqual(a['VRd'],114)
        self.assertTrue(a['configuration_matched'] and b['configuration_matched'])
    def test_05_no_s11_interpolation(self):
        for s in (100,140,180,431):
            r=ref(f'EBEA-700 VE1 4x10-3 D200 SW80 L1000 S11={s}')
            self.assertIsNone(r['MRd']);self.assertFalse(r['configuration_matched'])
        self.assertTrue(ref('EBEA-700 VE1 4x10-3 D200 SW80 L1000 S11=430')['configuration_matched'])
    def test_06_exact_rounding_not_multiplication(self):
        a=ref('EBEA-700 VE1 4x10-1 D180 SW80 L1000 S11=120');b=ref('EBEA-700 VE1 4x10-2 D180 SW80 L1000 S11=120')
        self.assertEqual((a['VRd'],b['VRd']),(33,65));self.assertNotEqual(b['VRd'],2*a['VRd'])
        self.assertEqual(ref('EBEA-700 VE1 4x10-2 D220 SW80 L1000 S11=120')['VRd'],87)
    def test_07_concrete_reduction_not_stiffness(self):
        r=ref(concrete='C20/25');self.assertAlmostEqual(r['MRd'],18.4);self.assertAlmostEqual(r['VRd'],60.8);self.assertEqual(r['k'],2995)
        self.assertEqual(ref(concrete='C50/60')['MRd'],23)
    def test_08_no_unknown_concrete(self):
        for c in ('','C16/20','C25/35','random'):
            r=ref(concrete=c);self.assertFalse(r['configuration_matched']);self.assertIsNone(r['MRd'])
        with self.assertRaises(ValueError): ref(STANDARD+' C30/37')
    def test_09_ds_dt_not_d(self):
        r=ref('EBEA-100 RS 4x10-2 Ds200 Dt200 SW80 L500');self.assertIsNone(r['MRd']);self.assertIsNone(r['standard_d_mm'])
        self.assertTrue(ref('EBEA-100 RS 4x10-2 Ds200 Dt200 SW80 L500',standard_d_mm=200)['configuration_matched'])
    def test_10_explicit_d_and_conflicts(self):
        d=decode_peikko(STANDARD);self.assertEqual(d.parameters['standard_d_mm'],200)
        self.assertEqual(decode_peikko(d.canonical).canonical,d.canonical)
        for text in (STANDARD+' D220',):
            with self.assertRaises(ValueError):decode_peikko(text)
        with self.assertRaises(ValueError):ref(standard_d_mm=220)
    def test_11_non_tabulated_bars(self):
        for code in ('5x10-4','7x10-3','8x10-7','4x12-2'):
            r=ref(f'EBEA-100 RS {code} D200 SW80 L1000');self.assertIsNone(r['MRd']);self.assertFalse(r['configuration_matched'])
    def test_12_custom_identifiers_block_comparison_but_not_reference(self):
        for text in (STANDARD+' OQ',STANDARD.replace('EBEA-100','EBEA-100-B2'),STANDARD+' CUSTOM'):
            r=ref(text);self.assertEqual(r['MRd'],23);self.assertFalse(r['configuration_matched'])
            with self.assertRaises(ValueError):compare_loads(r,moment=-10,shear=10)
    def test_13_all_14_user_samples_remain_distinct(self):
        ns=runpy.run_path(str(ROOT/'tools/verify_peikko_2229.py'),run_name='fixtures')
        try:
            samples=ns['SAMPLES'];self.assertEqual(len(samples),14)
            for pos,text in samples:
                with self.subTest(position=pos):
                    r=ref(text,standard_d_mm=200)
                    self.assertFalse(r['configuration_matched']);self.assertFalse(r['design_verified'])
                    self.assertEqual(decode_peikko(text).canonical,decode_peikko(decode_peikko(text).canonical).canonical)
            self.assertNotEqual(ref(samples[8][1],standard_d_mm=200)['MRd'],ref(samples[9][1],standard_d_mm=200)['MRd'])
        finally: sys.path[:0]=[str(RELEASE),str(ROOT/'updates/1.1.17')]
    def test_14_length_and_count_limits(self):
        for text in (STANDARD.replace('L500','L350'),STANDARD.replace('L500','L525'),STANDARD.replace('L500','L1250'),STANDARD.replace('4x10-2','4x10-4')):
            self.assertFalse(ref(text)['configuration_matched'])
        self.assertTrue(ref(STANDARD.replace('L500','L1200'))['configuration_matched'])
    def test_15_geometry_and_covers(self):
        self.assertFalse(ref(geometry_confirmed=False)['configuration_matched'])
        for extra in (' CV35',' Ds180 Dt180',' Ds200 Dt220',' S11=120'):
            self.assertFalse(ref(STANDARD+extra)['configuration_matched'])
        self.assertTrue(ref(STANDARD+' CV30')['configuration_matched'])
    def test_16_material_is_model_specific(self):
        self.assertFalse(ref('EBEA-700 RS 4x10-3 D200 SW80 L1000 S11=120')['configuration_matched'])
        self.assertFalse(ref(STANDARD.replace(' RS ', ' '))['configuration_matched'])
    def test_17_nrd_source_anomaly_preserved(self):
        r=ref('EBEA-700 VE1 4x10-3 D200 SW80 L1000 S11=120')
        self.assertEqual(r['bending']['NRd_source_unit'],'kNm/pcs');self.assertFalse(r['bending']['NRd_unit_verified'])
        with self.assertRaises(ValueError):compare_loads(r,moment=10,shear=10,axial=1)
    def test_18_component_tables_not_total_capacities(self):
        r=ref('TEBEA CM-V');self.assertEqual(len(r['component_rows']),57);self.assertIsNone(r['MRd']);self.assertIsNone(r['VRd'])
        self.assertFalse(r['configuration_matched']);self.assertTrue(all(c['full_connector'] is False for c in r['component_rows']))
        self.assertEqual([c['value'] for c in r['component_rows'] if c['kind']=='concrete_buffer'],[27.5,29.9,33.1])
    def test_19_component_golden_and_typo_excluded(self):
        rows=data()['tebea_components']
        self.assertEqual(next(c['value'] for c in rows if c['kind']=='shear_bar' and c['diameter']==10 and c['angle_deg']==45),24.1)
        self.assertEqual(next(c['value'] for c in rows if c['kind']=='compression_bar' and c['stainless_diameter']==14 and c['steel']=='1.4362'),66.6)
        self.assertFalse(any(c['kind']=='headed_compression' and c['diameter']==14 and c['steel']=='1.4362' for c in rows))
        self.assertEqual(len(data()['issues']),2)
    def test_20_unknown_models_not_scaled(self):
        for text in ('EBEA-ZS D200 SW80 L1000','EBEA-200 RS 4x10-2 D200 SW80 L1000'):
            r=ref(text);self.assertFalse(r['configuration_matched']);self.assertIsNone(r['MRd'])
    def test_21_signs_and_zero(self):
        with self.assertRaises(ValueError):compare_loads(ref(),moment=10,shear=20)
        with self.assertRaises(ValueError):compare_loads(ref(),moment=0,shear=0)
        self.assertTrue(compare_loads(ref(),moment=-10,shear=-20)['table_pass'])
    def test_22_pass_not_full_design(self):
        r=ref();c=compare_loads(r,moment=-23,shear=76)
        self.assertEqual((c['eta_M'],c['eta_V']),(1,1));self.assertTrue(c['table_pass']);self.assertFalse(c['design_verified'])
        self.assertFalse(compare_loads(r,moment=-23.01,shear=76)['table_pass'])
    def test_23_units_require_explicit_width_not_l(self):
        r=ref()
        with self.assertRaises(ValueError):compare_loads(r,moment=-30,shear=100,basis='per_metre')
        c=compare_loads(r,moment=-30,shear=100,basis='per_metre',tributary_width_mm=400)
        self.assertEqual((c['MEd_per_element'],c['VEd_per_element']),(-12,40))
        self.assertIn('400',format_comparison(c))
        for width in (0,-1,'nan','inf'):
            with self.assertRaises(ValueError):compare_loads(r,moment=-30,shear=100,basis='per_metre',tributary_width_mm=width)
    def test_24_numeric_validation(self):
        for value in (True,False,'NaN','inf','-inf',None,''):
            with self.assertRaises(ValueError):number(value,'input')
        for value in ('200.1',0,-200):
            with self.assertRaises(ValueError):integer(value,'D')
        self.assertEqual(number('-12,5','M'),-12.5)
        with self.assertRaises(ValueError):compare_loads(ref(),moment='nan',shear=1)
    def test_25_exact_preselection(self):
        rows=choices();self.assertEqual(len(rows),29)
        for row in rows:
            self.assertTrue(row['reference']['configuration_matched']);self.assertTrue(row['comparison']['table_pass']);self.assertFalse(row['comparison']['design_verified'])
            self.assertEqual(row['reference']['concrete'],'C25/30')
        self.assertLess(len(choices(concrete='C20/25')),len(rows))
    def test_26_preselection_guards(self):
        for kw in (dict(model='800'),dict(concrete='C16/20'),dict(geometry_confirmed=False),dict(moment=1),dict(axial=1),dict(basis='unknown'),dict(basis='per_metre'),dict(moment=0,shear=0),dict(model='700',material='VE1',s11_mm=180)):
            with self.subTest(kw=kw),self.assertRaises(ValueError):choices(**kw)
    def test_27_legacy_contract_no_autonomous_approval(self):
        r=make_result(STANDARD,'C25/30');self.assertEqual(r.catalog['id'],CATALOG_ID)
        self.assertEqual(r.family['generation'],'syntax-1');self.assertFalse(r.record['resistance_verified'])
        self.assertTrue(all(x['kind']=='other' for x in r.record['results']))
        self.assertEqual(r.record['height_mm'],'');self.assertEqual(r.record['substitution_policy'],'manual')
        self.assertIn('|MRd|: 23',r.record['results'][-1]['text'])
    def test_28_d_serialization_and_existing_syntax(self):
        from project_model import create_project_row, normalize_project_row, query_from_selection
        from catalog_engine import CatalogDatabase
        db=catalog_class(CatalogDatabase)(ROOT/'updates/1.1.17/catalogs')
        result=db.resolve_designation(STANDARD,preferred_concrete='C25/30')
        row=normalize_project_row(json.loads(json.dumps(create_project_row(result,position='p1'))))
        loaded=query_from_selection(db,row['selection']);self.assertEqual(loaded.record['designation'],decode_peikko(STANDARD).canonical)
        self.assertEqual(loaded.record['peikko_parameters']['standard_d_mm'],200)
    def test_29_d_bulk_continuation(self):
        text=normalize_bulk_text('e1\nEBEA-100 RS 4x10-2\nD200 SW80 L500')
        self.assertIn('D200',text);self.assertEqual(len([x for x in text.splitlines() if 'EBEA-' in x]),1)
    def test_30_reference_labels(self):
        s=format_reference(ref(STANDARD+' OQ'))
        self.assertIn('NEPOTVRZENÁ',s);self.assertIn('tabulka 3',s);self.assertIn('SHA-256',s);self.assertNotIn('vyhovuje',s.lower())

class Documents(unittest.TestCase):
    def test_31_verified_local_cache(self):
        raw=b'%PDF-1.7\nfixture';digest=hashlib.sha256(raw).hexdigest();source=dict(url='https://media.peikko.com/file/test',sha256=digest,title='ETA 23/0525')
        with tempfile.TemporaryDirectory() as d:
            calls=[]
            def opener(*a,**kw):calls.append(a);return io.BytesIO(raw)
            path=fetch_document(Path(d),source,opener=opener);self.assertTrue(path.name.startswith('TEBEA_ETA_'))
            self.assertEqual(path.read_bytes(),raw);self.assertEqual(fetch_document(Path(d),source,opener=opener),path);self.assertEqual(len(calls),1)
    def test_32_failed_download_does_not_replace_existing_file(self):
        raw=b'%PDF-1.7\nfixture';source=dict(url='https://media.peikko.com/file/test',sha256=hashlib.sha256(raw).hexdigest(),title='EBEA')
        with tempfile.TemporaryDirectory() as d:
            p=fetch_document(Path(d),source,opener=lambda *a,**k:io.BytesIO(raw));p.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):fetch_document(Path(d),source,opener=lambda *a,**k:io.BytesIO(b'<html>error</html>'))
            self.assertEqual(p.read_bytes(),b'corrupt');self.assertFalse(list(Path(d).glob('*.part')))
    def test_33_disallowed_source(self):
        with tempfile.TemporaryDirectory() as d:
            for url in ('http://media.peikko.com/test','https://evil.example/test','file:///etc/passwd'):
                with self.assertRaises(ValueError):fetch_document(Path(d),dict(url=url,sha256='a'*64,title='EBEA'))

if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    unittest.main(verbosity=2)
