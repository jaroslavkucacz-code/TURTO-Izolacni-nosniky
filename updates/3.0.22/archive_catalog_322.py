"""Verified Czech April 2023 T KL generation 2.0 catalogue.

The two unclear printed M10 cells remain excluded, not sign-corrected.
No aliases between generations and no replacement of saved project snapshots.
"""
from functools import wraps
import json
from pathlib import Path

import catalog_engine as catalog
import designation_format_321 as formatting

DATA_FILE = Path(__file__).with_name('schoeck_t_kl_20_322.json')
CATALOG_ID = 'schoeck-t-kl-2.0-cz-2023.1-archive'


def catalog_package():
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    excluded = {(c['moment_class'], c['cover'], c['height_mm']) for c in data['excluded_cells']}
    records = []
    for line in data['table']:
        cover, height = line['cover'], line['height_mm']
        for moment, value in zip(line['moment_classes'], line['mrd_knm_per_m']):
            if (moment, cover, height) in excluded:
                continue
            if value >= 0:
                raise catalog.CatalogError('Archiv KL 2.0 obsahuje neověřený moment.')
            for shear, values in data['shear_kn_per_m'].items():
                force = dict(key='v_rd_z', label='vRd,z', kind='shear', unit='kN/m')
                if shear == 'V1':
                    force['positive'] = values['M1_M7' if int(moment[1:]) <= 7 else 'M8_M12']
                else:
                    force.update(values)
                code = f'T-KL-{moment}-{shear}-REI120-{cover}-H{height}-2.0'
                records.append(dict(
                    designation='Schöck Isokorb® T typ ' + code[2:], aliases=[code],
                    moment_class=moment, shear_class=shear, concrete_min=data['concrete'],
                    cover=cover, height_mm=str(height), fire_class=data['fire_class'],
                    element_length_mm=data['element_length_mm'],
                    insulation_thickness_mm=data['insulation_thickness_mm'],
                    source_pages=[44, 45, line['page']],
                    notes=['Archiv CZ/2023.1, duben 2023; generace 2.0, str. 44.',
                           'Statický systém a pokyny pro návrh: str. 45; únosnosti na metr délky.'],
                    results=[dict(key='m_rd_y', label='mRd,y', kind='moment', value=value, unit='kNm/m'), force]))
    return dict(schema_version=2, catalog=data['catalog'], families=[dict(
        manufacturer='Schöck', brand='Isokorb®', model='T', type='KL', generation='2.0',
        category='Volně vyložené balkóny', basis='tabulkové návrhové hodnoty únosnosti',
        insulation_thickness_mm=80, element_length_mm=1000,
        selector_labels={'moment_class': 'Momentová třída', 'shear_class': 'Smyková třída',
                         'concrete': 'Beton', 'cover': 'Krytí', 'height': 'Výška [mm]'}, records=records)])


def add_catalog(database):
    if CATALOG_ID in database.catalogs:
        return
    database._load_package(DATA_FILE, catalog_package())
    family = database.families[-1]
    for record in family['records']:
        for text in [record['designation'], *record['aliases']]:
            database._designation_index.setdefault(catalog._normalise(text), []).append((family, record))
    database._build_suggestion_index()
    database._build_selector_value_cache()


def install(_base=None):
    cls = catalog.CatalogDatabase
    if getattr(cls, '_turto_archive_322', False):
        return
    init = cls.__init__

    @wraps(init)
    def initialize(self, *args, **kwargs):
        init(self, *args, **kwargs)
        add_catalog(self)

    previous_message = formatting.missing_data_message

    @wraps(previous_message)
    def message(database, text):
        result = previous_message(database, text)
        parsed = formatting.parsed_code(text)
        if parsed and parsed.model == 'T' and parsed.fields['generation'] == '2.0':
            f = parsed.fields
            if parsed.family == 'KL' and f['moment'] == 'M10' and f['cover'] == '1' and f['height'] in ('180', '190'):
                result += ' Archiv CZ/2023.1, str. 47: nejasné znaménko momentu M10/CV1/H180 a H190; tyto hodnoty nejsou použity.'
            elif parsed.family == 'KL-U':
                result += ' Archiv CZ/2023.1 uvádí pro KL-U generaci 7.1 (str. 70); zadanou generaci 2.0 je nutné ověřit.'
            elif parsed.family == 'ZL':
                result += ' ZL je izolační mezikus bez statické funkce (CZ/2023.1, str. 135); generace 2.0 není tímto zdrojem doložena.'
        return result

    cls.__init__ = initialize
    formatting.missing_data_message = message
    cls._turto_archive_322 = True


def selftest():
    package = catalog_package()
    assert package['catalog']['id'] == CATALOG_ID
    assert len(package['families'][0]['records']) == 1002
