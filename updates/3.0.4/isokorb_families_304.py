from __future__ import annotations

"""Strict explicit T/XT/CXT identifiers in the actual progressive import path.
No catalogue capacities are created. The documented CXT AP example is an
informational record only: KF/Ft/Fc design and all substitutions remain manual.
Generation is not insulation thickness. Original selection keys are preserved.
"""
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
import json
from pathlib import Path
import re

import catalog_engine as catalog
import bulk_import_engine as engine
import bulk_import
import iso_bulk_301 as old

VERSION = '3.0.4'
MISSING = 'Označení přečteno, ale chybí odpovídající katalogový záznam.'
AP_ID = 'schoeck-cxt-ap-cz-2024-1-identification'
AP_CODE = 'CXT-AP-MM1-VV1-REI30-LR200-B200-L300-1.0'
AP_URL = 'https://www.schoeck.com/viewfile/8304/Technicke_informace_Schoeck_Isokorb_CXT_typ_AP__8304__.pdf'
AP_NOTE = ('Identifikace podle Technických informací Schöck CXT AP/CZ/2024.1, str. 19. '
           'Neobsahuje skalární únosnost M/V. Statické posouzení vyžaduje postup KF a grafy Ft/Fc '
           '(str. 22–23); automatická záměna není povolena. LR je délka zabudování a B šířka, nikoliv výška desky.')

@dataclass(frozen=True)
class Parsed:
    model: str
    family: str
    canonical: str
    fields: dict[str, str]


def parse(text):
    value = old.norm(text).replace('®', '')
    value = re.sub(r'^SCHO(?:CK|ECK)\s+', '', value)
    value = re.sub(r'^ISOKORB\s*', '', value)
    match = re.match(r'^(CXT|XT|T)(?:\s*(?:TYP|TYPE))?(?:\s*-\s*|\s+)', value)
    if not match:
        return None
    model = match.group(1)
    code = re.sub(r'\s+', '', value[match.end():])
    gen = r'(?P<generation>\d+\.\d+)'
    patterns = [
        (r'(?P<family>KL(?:-O|-U)?)-(?P<moment>M\d+)-(?P<shear>VV?\d+)-REI(?P<fire>\d+)-CV(?P<cover>\d+)-H(?P<height>\d+)-'+gen),
        (r'(?P<family>QL|QP(?:-Z)?)-(?P<shear>VV?\d+)-REI(?P<fire>\d+)-H(?P<height>\d+)(?:-L(?P<length>\d+))?-'+gen),
        (r'(?P<family>AP)-(?P<moment>MM\d+)-(?P<shear>VV?\d+)-REI(?P<fire>\d+)-LR(?P<anchorage>\d+)-B(?P<width>\d+)-L(?P<length>\d+)-'+gen),
    ]
    for pattern in patterns:
        m = re.fullmatch(pattern, code)
        if not m:
            continue
        fields = {k:v for k,v in m.groupdict().items() if v is not None}
        family = fields.pop('family')
        if (family == 'AP') != (model == 'CXT'):
            return None
        if family.startswith('QP') and 'length' not in fields:
            return None
        if family == 'QL' and 'length' in fields:
            return None
        return Parsed(model, family, model+'-'+code, fields)
    return None


def _model(text):
    return re.sub(r'\s+TYP(?:E)?$', '', old.norm(text))


def _concrete(text):
    return old.norm(text).replace('≥', '').replace('>=', '').replace(' ', '')


def _matches(family, record, parsed, concrete):
    f = parsed.fields
    if not all(k in record for k in ('moment_class','shear_class','cover','height_mm','concrete_min')):
        return False
    if not isinstance(record.get('results'), list) or not record['results']:
        return False
    info = family.get('catalog_id') == AP_ID
    if not info and concrete and _concrete(record['concrete_min']) != _concrete(concrete):
        return False
    if parsed.family.startswith('KL') or parsed.family == 'AP':
        if old.norm(record['moment_class']) != f['moment'] or old.norm(record['shear_class']) != f['shear']:
            return False
    else:
        shear = old.norm(record['shear_class'])
        if shear in old.EMPTY:
            shear = old.norm(record['moment_class'])
        if shear != f['shear']:
            return False
    if 'cover' in f:
        cv = re.match(r'^CV(\d+)(?:$|[\s·;,])', old.norm(record['cover']))
        if cv is None or cv.group(1) != f['cover']:
            return False
        if not parsed.family.startswith(('KL-O', 'KL-U')) and old.norm(record['cover']) != 'CV'+f['cover']:
            return False
    if 'height' in f:
        h = int(f['height'])
        if not old.height_matches(record['height_mm'], h):
            return False
        for source in (family, record):
            for key, lower in (('height_min',True),('height_max',False)):
                if source.get(key) not in (None,''):
                    try:
                        if (h < float(source[key]) if lower else h > float(source[key])):
                            return False
                    except (ValueError,TypeError):
                        return False
    if 'length' in f and old._length(record) != int(f['length']):
        return False
    if parsed.family == 'AP':
        # Geometry must be explicitly documented in this record, not guessed
        # from a coincidental number in a strength or unrelated dimension.
        geometry = old.norm(str(record.get('designation',''))+' '+str(record['cover']))
        for name, token in (('anchorage','LR'),('width','B')):
            values = re.findall(r'(?<![A-Z0-9])'+token+r'\s*=?\s*(\d+)(?!\d)', geometry)
            if not values or set(values) != {f[name]}:
                return False
    fire = old._fire(record)
    return not fire or fire == {'REI'+f['fire']}


def candidates(database, parsed, concrete):
    out, seen = [], set()
    for family in database.families:
        if (old.norm(family.get('manufacturer')) not in {'SCHOCK','SCHOECK'}
                or _model(family.get('model')) != parsed.model
                or old.norm(family.get('type')) != parsed.family
                or old.norm(family.get('generation')) != parsed.fields['generation']
                or family.get('backend') == 'matrix'):
            continue
        cat = database.catalogs.get(str(family.get('catalog_id')))
        if not isinstance(cat, dict):
            continue
        for record in family.get('records', []):
            if not _matches(family, record, parsed, concrete):
                continue
            key = (cat['id'], json.dumps({k:v for k,v in family.items() if k not in {'records','catalog'}},sort_keys=True,ensure_ascii=False),
                   json.dumps(record, sort_keys=True,ensure_ascii=False))
            if key in seen:
                continue
            seen.add(key)
            enriched = deepcopy(record)
            enriched['catalog_designation'] = record.get('designation','')
            enriched['catalog_fire_explicit'] = bool(old._fire(record))
            enriched['designation'] = 'Schöck Isokorb® '+parsed.model+' typ '+parsed.canonical[len(parsed.model)+1:]
            if parsed.family in {'KL-O','KL-U'}:
                suffix = re.sub(r'^CV\d+\s*[·;,]?\s*','',str(record['cover']))
                if suffix:
                    enriched['designation'] += ' • '+suffix
            if 'height' in parsed.fields:
                enriched['input_height_mm'] = int(parsed.fields['height'])
            if parsed.family == 'AP':
                enriched['substitution_policy'] = 'manual'
                enriched['substitution_note'] = AP_NOTE
            out.append(catalog.DesignationSuggestion(catalog.QueryResult(cat, family, enriched),1000.0))
    # A real geometrically matched AP record takes priority over metadata only.
    rich = [c for c in out if c.result.catalog['id'] != AP_ID]
    return rich or out


def add_ap_reference(database):
    if AP_ID in database.catalogs:
        return
    cat = dict(id=AP_ID, edition='CXT AP/CZ/2024.1 – pouze identifikace',
        publication_label='únor 2024, bez návrhových únosností', publication_date='2024-02-12',
        source_filename='Technicke_informace_Schoeck_Isokorb_CXT_typ_AP__8304__.pdf', source_url=AP_URL)
    rec = dict(moment_class='MM1',shear_class='VV1',concrete_min='—',cover='LR200 · B200 · L300',height_mm='—',
        designation='Schöck Isokorb® CXT typ AP-MM1-VV1-REI30-LR200-B200-L300-1.0',
        element_length_mm=300,insulation_thickness_mm=120,source_pages=[19,22,23],
        substitution_policy='manual',substitution_note=AP_NOTE,
        results=[dict(key='special_design',label='Posouzení',kind='other',text='KF a grafy Ft/Fc – vyžaduje samostatné posouzení',unit='')])
    family = dict(catalog_id=AP_ID,catalog=cat,manufacturer='Schöck',model='CXT',type='AP',generation='1.0',
        records=[rec],selector_labels={'cover':'Rozměry LR / B / L','height':'Výška desky nezadána'},
        insulation_thickness_mm=120,substitution_policy='manual',substitution_note=AP_NOTE)
    database.catalogs[AP_ID]=cat
    database.families.append(family)
    database._build_suggestion_index()
    database._build_selector_value_cache()


def install(base):
    if getattr(engine,'_turto_families_304',False):
        return
    init = catalog.CatalogDatabase.__init__
    @wraps(init)
    def db_init(self,*a,**kw):
        init(self,*a,**kw)
        add_ap_reference(self)
    catalog.CatalogDatabase.__init__ = db_init
    previous = engine._classify_bulk_item
    @wraps(previous)
    def classify(database,item,*,preferred_concrete,suggestion_limit):
        p = parse(item.designation)
        if p is None:
            explicit=re.sub(r'\s+','',old.norm(item.designation))
            if re.match(r'^(?:T|XT|CXT)-(?:KL(?:-O|-U)?|QP(?:-Z)?|QL|AP)-',explicit) and ('REI' in explicit and re.search(r'-H\d+|-LR\d+',explicit)):
                item.result=None; item.archive_source=None; item.candidates=[]; item.varying_keys=()
                item.status='error'; item.message='Označení má neplatné nebo neúplné parametry. Zkontrolujte rozměry, pořadí tokenů a generaci; jiný typ se nedoplňuje.'
                return
            return previous(database,item,preferred_concrete=preferred_concrete,suggestion_limit=suggestion_limit)
        item.result=None; item.archive_source=None; item.varying_keys=()
        item.candidates=candidates(database,p,preferred_concrete)
        if len(item.candidates)==1:
            item.result=item.candidates[0].result; item.status='exact'
            item.message='Zadaná řada, generace a parametry odpovídají jednomu katalogovému záznamu.'
            if p.family=='AP':
                item.message=AP_NOTE
            elif not item.result.record.get('catalog_fire_explicit'):
                item.message+=' Požární provedení převzato ze vstupu; statická tabulka je neověřuje.'
            if p.family in {'KL-O','KL-U'}:
                item.message+=' Podmínka geometrie: '+str(item.result.record['cover'])+'.'
        elif item.candidates:
            item.status='review'
            covers={str(c.result.record['cover']) for c in item.candidates}
            item.varying_keys=('cover',) if len(covers)>1 else ()
            item.message=('Nutno vybrat podmínku šířky stěny / geometrie z odpovídajících katalogových řádků.'
                          if p.family in {'KL-O','KL-U'} and len(covers)>1 else
                          'Úplné označení odpovídá více zdrojovým záznamům; ověřte vydání a hodnoty katalogu.')
        else:
            item.status='error'; item.message=MISSING+' '+p.canonical+'. Žádná jiná generace, řada ani VV/V se nezaměňuje.'
    engine._classify_bulk_item=classify
    refresh=bulk_import.BulkImportDialog._refresh_review_tree
    @wraps(refresh)
    def refresh_tree(self,*a,**kw):
        refresh(self,*a,**kw)
        for iid,item in self._item_by_iid.items():
            p=parse(item.designation)
            if p and item.status=='error' and item.message.startswith(MISSING):
                self.review_tree.set(iid,'status','Chybí data')
                self.review_tree.set(iid,'resolved',p.canonical)
            elif p and p.family=='AP' and item.ready:
                self.review_tree.set(iid,'status','Rozpoznáno (KF)')
        self.summary_var.set(self.summary_var.get().replace('ISO 3.0.1','ISO 3.0.4'))
    bulk_import.BulkImportDialog._refresh_review_tree=refresh_tree
    if base is not None:
        cls=base.ThermalConnectorApp; prev=cls._build_header
        @wraps(prev)
        def header(self):
            prev(self)
            label=getattr(self,'_turto_brand_title',None)
            if label is not None:
                label.configure(text='TURTO 3.0.4 | Izolační nosníky a smykové trny')
        cls._build_header=header
    engine._turto_families_304=True


def selftest():
    p=parse('T-QP-VV1-REI120-H200-L300-5.0')
    assert p and p.model=='T' and p.fields['shear']=='VV1' and p.fields['generation']=='5.0'
    assert parse(AP_CODE).fields['width']=='200'
    assert parse('XT-KL-O-M3-V1-REI120-CV1-H250-7.2').family=='KL-O'
    assert parse('T-QP-VV1-REI120-H200-L300-5.0-extra') is None
