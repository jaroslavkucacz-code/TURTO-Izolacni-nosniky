"""Current dowel catalogue data throughout decoder, saved actions and exports."""
from functools import wraps
import math
import re


def enrich(row):
    import shear_dowels_ui as ui
    import shear_catalogs_227 as catalog
    # Remove only fields owned by this adapter when a row is edited.
    if row.pop('current_catalogue', False):
        for key in ('vrd', 'source', 'note', 'catalog_capacity', 'catalog_error'):
            row.pop(key, None)
    info = ui.decode_dowel(str(row.get('designation') or ''))
    if not info or info.get('legacy') or info.get('manufacturer') not in ('Schöck','Ancon','PohlCon','MAX FRANK'):
        return
    row['current_catalogue'] = True
    for key in ('manufacturer','family','size','movement'):
        row[key] = info.get(key, '')
    # Clear old derived archive metadata when a stored designation becomes modern.
    for key in tuple(row):
        if key.startswith('archive_'):
            row.pop(key, None)
    row.update(vrd=None, source='', note='')
    error = ''
    try:
        h, gap = float(row.get('slab_mm') or 0), float(row.get('gap_mm') or 0)
        concrete = str(row.get('concrete') or '')
        if row.get('geometry_confirmed') is False or not concrete or h == 0:
            error = 'Doplňte h, návrhovou spáru a beton.'
        elif not math.isfinite(h) or not math.isfinite(gap) or h < 0 or gap < 0:
            error = 'Neplatná tloušťka desky nebo šířka spáry.'
        elif info.get('decoder_only'):
            error = str(info.get('legacy_detail') or 'Samostatná komponenta neurčuje celý komplet.')
        elif info['manufacturer'] == 'Schöck' and concrete not in ('C20/25','C25/30','C30/37','C35/45','C40/50','C45/55','C50/60'):
            error = 'Tabulky Schöck Stacon platí pro beton C20/25 až C50/60.'
        elif info['manufacturer'] == 'Schöck' and info['base_family'] == 'SLD' and row.get('cover_mm') not in (20,30,20.0,30.0):
            error = 'Doplňte zdrojové cnom Stacon SLD: 20 nebo 30 mm.'
        else:
            candidate, error = catalog.capacity_from_designation(
                str(row['designation']), slab_mm=h, gap_mm=gap, concrete=concrete,
                cover_mm=int(row.get('cover_mm') or 30))
            if candidate:
                data = candidate.as_dict()
                row.update(catalog_capacity=data, vrd=data['vrd'], source=data['source'],
                           note=' • '.join(str(v) for v in (data.get('status'), data.get('note')) if v))
                return
    except (ValueError, TypeError, OverflowError):
        error = 'Neplatná geometrie; upravte parametry řádku.'
    row['catalog_error'] = error or 'Pro zadané parametry není katalogová únosnost k dispozici.'
    row['note'] = row['catalog_error']


def install(base):
    import shear_dowels_ui_215 as ui
    cls = base.ThermalConnectorApp
    if getattr(cls, '_turto_capacity_317', False):
        return
    original_enrich = ui._enrich_decoder_row
    @wraps(original_enrich)
    def enrich_row(row):
        original_enrich(row)
        enrich(row)
    ui._enrich_decoder_row = enrich_row
    original_refresh = cls.refresh_shear_tables
    @wraps(original_refresh)
    def refresh(owner):
        original_refresh(owner)
        tree = owner.shear_decoder_tree
        for iid in tree.get_children(''):
            row = owner.shear_decoder_rows[int(iid)]
            if not row.get('current_catalogue'):
                continue
            cap = row.get('catalog_capacity')
            if cap:
                text = f"{cap['source']} • str. {cap['page']} • h tab. {cap['slab_table_mm']} mm • spára tab. {cap['gap_table_mm']} mm"
                if cap.get('status') != 'VYHOVUJE':
                    text += ' • '+str(cap.get('status',''))+' • '+str(cap.get('note',''))
                tree.set(iid, 'vrd', ui._prev._fmt(cap['vrd']))
                tree.set(iid, 'source', text)
                tree.item(iid, tags=('archive' if cap.get('status') == 'VYHOVUJE' else 'archive_error',))
            else:
                tree.set(iid, 'vrd', '—')
                tree.set(iid, 'source', row['catalog_error'])
                tree.item(iid, tags=('archive_error',))
    cls.refresh_shear_tables = refresh
    original_sync = cls.sync_shear_substitutions_from_decoder
    @wraps(original_sync)
    def sync(owner):
        original_sync(owner)
        sources={(str(r.get('name','')),str(r.get('designation',''))):r for r in owner.shear_decoder_rows}
        for index, row in enumerate(owner.shear_substitution_rows):
            source=sources.get((str(row.get('name','')),str(row.get('source_designation',''))))
            if row.get('origin') != 'decoder' or not source or not source.get('current_catalogue') or source.get('family') not in ('SLD','SLD-Q'):
                continue
            if source.get('cover_mm') in (20,30):
                row['cover_mm']=source['cover_mm']
                owner.shear_substitution_rows[index]=ui._substitution_from_values(dict(row),owner.shear_target_manufacturer_var.get())
            else:
                row.update(source={},target={},status='NELZE',error='Doplňte zdrojové cnom Stacon SLD v Dekodéru.')
        owner.refresh_shear_tables()
    cls.sync_shear_substitutions_from_decoder = sync
    cls._turto_capacity_317 = True
