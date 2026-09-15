from __future__ import annotations

"""Read physical Annex 3 columns, never rounded reinforcement density.
Repairs only the active ZVX/ZDX view for a byte-verified DoP. Customer files
and saved actions remain unchanged. An inconsistent source row is quarantined.
"""
import base64
from copy import deepcopy
from functools import wraps
import gzip
import hashlib
import json
import logging
import math
from pathlib import Path
import re

VERSION = "3.0.3"
SOURCE_SHA256 = "454a158c77f218ca709efce2f6a89f7e58982712bac290e2d882fccca0a9dd77"
SOURCE_URL = "https://downloads.halfen.com/catalogues/de/media/declarationofperformance/reinforcementsystems/CONF-DOP_HIT-HP_SP_07-23-E.pdf"
COMPLETE_SHA256 = "f4c82ee84362fadc4e411e8e8c8c24a622154c332e3544cb7daff10405c9d7ce"
DATA_FILE = Path(__file__).with_name("zvx_annex3_303.json.gz.b64")
LOG = logging.getLogger(__name__)
PRODUCT = re.compile(r"HIT-(HP|SP)\s+ZVX\s+(\d{4})-hh[^-]*-(100|050|033|025)-30-(06|08|10|12)")
HEIGHT_ROW = re.compile(r"(?m)^(\d{3})(?:-(\d{3}))?\s+(.+)$")


def _key(row):
    return tuple(row.get(k) for k in ('series', 'code', 'length_code', 'diameter', 'h_min', 'h_max', 'concrete', 'page'))


def fingerprint(rows):
    raw = json.dumps(sorted(rows, key=_key), sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def parse_zvx_pages(pdf):
    """Aliases below a header share its physical column, not inferred strength.
    Missing numbers or ambiguous geometry fail rather than dropping a table.
    """
    records = []
    if len(pdf.pages) < 100:
        raise ValueError('DoP nemá očekávaný Annex 3.')
    for pi in range(94, 100):
        page = pdf.pages[pi]
        if 'CONF-DOP_HIT-HP/SP-07-23' not in (page.extract_text() or ''):
            raise ValueError(f'Strana {pi+1}: neznámé vydání tabulky HIT.')
        events = [(h['top'], 0, h) for h in page.search(PRODUCT, x_tolerance=1, y_tolerance=2)]
        events += [(r['top'], 1, r) for r in page.search(HEIGHT_ROW, x_tolerance=1, y_tolerance=2)]
        events.sort(key=lambda e: (e[0], e[1], e[2]['x0']))
        headers, rows, blocks = [], [], []
        for _top, kind, event in events:
            if kind == 0:
                if rows:
                    blocks.append((headers, rows))
                    headers, rows = [], []
                headers.append(event)
            else:
                if not headers:
                    raise ValueError(f'Strana {pi+1}: hodnoty bez záhlaví.')
                rows.append(event)
        if headers:
            blocks.append((headers, rows))
        if not blocks:
            raise ValueError(f'Strana {pi+1}: chybí tabulky ZVX.')
        for headers, rows in blocks:
            if not rows:
                raise ValueError(f'Strana {pi+1}: záhlaví bez hodnot.')
            columns = []
            for header in sorted(headers, key=lambda h: h['x0']):
                near = [c for c in columns if abs(c[0]['x0'] - header['x0']) < 3]
                if near:
                    near[0].append(header)
                else:
                    columns.append([header])
            concrete = [h for h in page.search(r'(?:≥\s*)?C(?:20/25|25/30)')
                        if max(hh['top'] for hh in headers) < h['top'] < rows[0]['top']]
            concrete.sort(key=lambda h: h['x0'])
            if [h['text'].replace(' ', '') for h in concrete] != ['C20/25', '≥C25/30'] * len(columns):
                raise ValueError(f'Strana {pi+1}: nejednoznačné sloupce betonu.')
            for ci, column in enumerate(columns):
                center = (column[0]['x0'] + column[0]['x1']) / 2
                if not concrete[2*ci]['x0'] < center < concrete[2*ci+1]['x1']:
                    raise ValueError(f'Strana {pi+1}: posunuté sloupce hodnot.')
            unit_zone = page.crop((0, max(h['bottom'] for h in headers), page.width, rows[0]['top']))
            if '[kN/m]' not in (unit_zone.extract_text() or ''):
                raise ValueError(f'Strana {pi+1}: neověřené jednotky únosností.')
            for row in rows:
                lo, hi, values = row['groups']
                values = [float(n.replace(',', '.')) for n in values.split()]
                if (len(values) != 2 * len(columns) or not all(math.isfinite(n) and n > 0 for n in values)
                        or not 100 <= int(lo) <= int(hi or lo) <= 500):
                    raise ValueError(f'Strana {pi+1}: neúplný řádek únosností H{lo}.')
                for ci, column in enumerate(columns):
                    for header in column:
                        series, code, width, dia = header['groups']
                        for concrete_name, offset in (('C20/25', 0), ('C25/30', 1)):
                            records.append(dict(series=series, code=code, length_code=int(width),
                                diameter=dia, h_min=int(lo), h_max=int(hi or lo), concrete=concrete_name,
                                vrd=values[2*ci+offset], page=pi+1))
    if len({_key(r) for r in records}) != len(records):
        raise ValueError('Annex 3 obsahuje nejednoznačné duplicitní řádky.')
    return records


def _safe_rows(records):
    # DoP p.99 SP 0202/033/12 H170-210: C20/25 says 291.4 but >=C25/30
    # says 243.0. Retain the original in the audit; never invent a replacement.
    pairs = {_key(r): r for r in records}
    safe, blocked = [], []
    for row in records:
        high = pairs.get(_key(dict(row, concrete='C25/30')))
        if row['concrete'] == 'C20/25' and high and row['vrd'] > high['vrd'] + 1e-8:
            blocked.append(deepcopy(row))
        else:
            safe.append(deepcopy(row))
    return safe, blocked


def reference_data():
    encoded = ''.join(DATA_FILE.read_text(encoding='ascii').split())
    data = json.loads(gzip.decompress(base64.b64decode(encoded, validate=True)))
    if (data.get('source_sha256') != SOURCE_SHA256
            or data.get('complete_sha256') != COMPLETE_SHA256
            or data.get('complete_records') != 1772
            or len(data.get('added_records', [])) != 160):
        raise ValueError('Nesouhlasí původ referenčních tabulek ZVX.')
    return data


def repair_database(database, source_pdf=None):
    if getattr(database, '_zvx_tables_303', False):
        return True
    source_hash = str(getattr(database, 'source_sha256', '')).strip().lower()
    original = list(database.zvx_records)
    if len({_key(r) for r in original}) != len(original):
        raise ValueError('Databáze obsahuje duplicitní klíče ZVX; automatické doplnění zastaveno.')
    if source_hash == SOURCE_SHA256:
        reference = reference_data()
        combined = {_key(r): deepcopy(r) for r in database.zvx_records}
        for row in reference['added_records']:
            existing = combined.get(_key(row))
            if existing is not None and existing != row:
                raise ValueError('Rozdílná existující hodnota ZVX; doplnění zastaveno.')
            combined[_key(row)] = deepcopy(row)
        corrected = sorted(combined.values(), key=_key)
        if fingerprint(corrected) != reference['complete_sha256']:
            raise ValueError('Soubor HIT nemá ověřenou sadu tabulek Annexu 3; načtěte původní DoP.')
    elif source_pdf is not None and re.fullmatch(r'[0-9a-f]{64}', source_hash):
        path = Path(source_pdf)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source_hash:
            raise ValueError('Zdrojové DoP neodpovídá databázi HIT (SHA-256).')
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            corrected = parse_zvx_pages(pdf)
    else:
        return False
    old = list(database.zvx_records)
    new_by_key = {_key(r): r for r in corrected}
    if any(_key(r) not in new_by_key or r != new_by_key[_key(r)] for r in old):
        raise ValueError('Původní tabulky ZVX mají rozdílné hodnoty; automatické doplnění bylo zastaveno.')
    safe, blocked = _safe_rows(corrected)
    database.zvx_records = safe
    database._zvx_tables_303 = True
    database._zvx_tables_303_audit = dict(source_sha256=source_hash, old_records=len(old),
        table_records=len(corrected), active_records=len(safe),
        added_records=len({_key(r) for r in safe} - {_key(r) for r in old}), blocked_records=blocked)
    LOG.info('HIT Annex 3 opraven: %s', database._zvx_tables_303_audit)
    return True


def install(base):
    import hit_core
    if getattr(hit_core, '_turto_zvx_303', False):
        return
    hit_core._parse_zvx_pages = parse_zvx_pages
    previous = hit_core.HitDatabase.__init__
    @wraps(previous)
    def init(self, *args, **kwargs):
        previous(self, *args, **kwargs)
        repair_database(self)
    hit_core.HitDatabase.__init__ = init
    if base is not None:
        cls = base.ThermalConnectorApp
        previous_load = cls._load_hit_data
        @wraps(previous_load)
        def load(self, *args, **kwargs):
            result = previous_load(self, *args, **kwargs)
            database = getattr(self, 'hit_db', None)
            if result and database is not None:
                try:
                    was_repaired = getattr(database, '_zvx_tables_303', False)
                    repaired = repair_database(database, getattr(self, 'hit_source_pdf', None))
                    if repaired and not was_repaired:
                        self.recalculate_hit_all()
                    text = ' • ZVX/ZDX: sloupce opraveny 3.0.3' if repaired else ' • ZVX/ZDX: pro kontrolu úplnosti načtěte původní DoP.'
                    if repaired and database._zvx_tables_303_audit['blocked_records']:
                        text += ' (nejasné řádky C20/25 vyloučeny z návrhu: ' + str(len(database._zvx_tables_303_audit['blocked_records'])) + ')' 
                except Exception as exc:
                    LOG.exception('Nelze bezpečně doplnit Annex 3')
                    text = ' • ZVX/ZDX: doplnění zastaveno: ' + str(exc)
                self.hit_source_var.set(self.hit_source_var.get() + text)
            return result
        cls._load_hit_data = load
        previous_header = cls._build_header
        @wraps(previous_header)
        def header(self):
            previous_header(self)
            label = getattr(self, '_turto_brand_title', None)
            if label is not None:
                label.configure(text='TURTO 3.0.3 | Izolační nosníky a smykové trny')
        cls._build_header = header
    hit_core._turto_zvx_303 = True


def selftest():
    assert VERSION == '3.0.3'
    data = reference_data()
    assert data['complete_records'] == 1772 and len(data['added_records']) == 160
    assert len({_key(r) for r in data['added_records']}) == 160
