"""Dimensional substitution of Schöck ZL insulation infills.

These rows do not supply load-bearing capacities, candidates or utilization.
The description is derived from current inputs, so manual edits and old AKCE
records use the same result without keeping a stale target designation.
"""
from copy import deepcopy
from functools import wraps
import re


def dimensions(row):
    from designation_format_321 import normalize
    selection = row.get('selection') or {}
    snapshot = row.get('snapshot') or {}
    edited = set((snapshot.get('completion') or {}).get('edited_fields') or [])
    source = str(row.get('source_text') or snapshot.get('designation') or '')
    code = normalize(source)
    match = re.match(r'^(T|XT|CXT)-ZL(?=-|$)', code)
    manufacturer = str(selection.get('manufacturer') or '').strip().upper()
    schoeck = manufacturer in ('SCHOCK', 'SCHOECK', 'SCHÖCK')
    family = str(selection.get('type_name') or '').strip().upper()
    if not ((schoeck and family == 'ZL') or (match and not manufacturer)):
        return None
    model = str(selection.get('model') or (match[1] if match else '')).upper().replace(' TYP', '').strip()
    height = selection.get('height_mm')
    if not height and 'height_mm' not in edited:
        heights = set(re.findall(r'(?:^|-)H(\d+)(?=-|$)', code))
        if len(heights) == 1:
            height = heights.pop()
    thickness = snapshot.get('insulation_thickness_mm')
    if not thickness and 'insulation' not in edited:
        thickness = {'T': 80, 'XT': 120}.get(model)
    def positive(value):
        try:
            number = int(str(value))
            return number if 0 < number <= 10000 else None
        except (TypeError, ValueError):
            return None
    height, thickness = positive(height), positive(thickness)
    missing = [label for value, label in ((thickness, 'tloušťku izolantu'), (height, 'výšku')) if value is None]
    designation = f'Mezivýplň tl. {thickness} mm, výšky {height} mm' if not missing else 'Mezivýplň – doplnit rozměry'
    return dict(source=source, source_insulation_mm=thickness, source_height_mm=height,
                designation=designation, missing=missing)


def assign(row):
    data = dimensions(row)
    if data is None:
        return
    overrides = deepcopy((row.get('mapping') or {}).get('source_overrides') or {})
    row['mapping'] = dict(status='infill_pending' if data['missing'] else 'infill',
        targets=[], selected_target_id=None, source_meta=data, warnings=[], errors=[],
        estimated_type='Mezivýplň', diameter_availability={}, source_overrides=overrides,
        substitution_acceptance={})


def payload(owner, row):
    data = dimensions(row)
    result = dict.fromkeys((c for c, *_ in owner.COLUMNS), '')
    status = 'Doplnit rozměry' if data['missing'] else 'MEZIVÝPLŇ'
    note = ('Doplňte '+', '.join(data['missing'])+' v „Upřesnit zdroj / geometrii…“.') if data['missing'] else 'Nenosná mezivýplň; bez statického posouzení.'
    result.update(position=row.get('position', ''), quantity=row.get('quantity', 1),
        manufacturer=(row.get('selection') or {}).get('manufacturer') or 'Schöck',
        source=data['source'], target=data['designation'], estimated_type='Mezivýplň',
        target_type='Mezivýplň', status=status, note=' • '.join(filter(None, (row.get('note'), note))))
    for key in ('source_insulation', 'source_height', 'target_height'):
        value = data['source_insulation_mm' if key == 'source_insulation' else 'source_height_mm']
        result[key] = f'{value} mm' if value else ''
    return result, 'infill_pending' if data['missing'] else 'infill'


def report_row(owner, row):
    data = dimensions(row)
    display, _ = payload(owner, row)
    source = data['source']
    return dict(domain_id='thermal_breaks', domain='Izolační nosníky', group='Záměny',
        report_tab='substitution', report_kind='iso.substitution', non_structural=True,
        name=str(row.get('position', '')), position=str(row.get('position', '')),
        quantity=row.get('quantity', 1), source=source, source_designation=source,
        target_designation=data['designation'], source_meta=data, source_actions={},
        target={}, candidate=None, source_catalog='', source_snapshot=deepcopy(row.get('snapshot') or {}),
        status=display['status'], acceptance_text='', notes=[display['note']],
        display=display, calculation_valid=False)


def install(base):
    import source_completion
    cls = base.ThermalConnectorApp
    previous_payload, previous_row = cls._payload, cls._row_payload
    previous_mapping = cls._mapping_text
    @wraps(previous_payload)
    def substitution(owner, row):
        return payload(owner, row) if dimensions(row) else previous_payload(owner, row)
    @wraps(previous_row)
    def decoder(owner, row, order):
        result, status = previous_row(owner, row, order)
        data = dimensions(row)
        if data:
            display, _ = payload(owner, row)
            result.update(status=display['status'], note=display['note'],
                          insulation=display['source_insulation'],
                          height=str(data['source_height_mm'] or ''),
                          compression='', moment='', shear='', extra='')
            status = 'missing' if data['missing'] else 'ok'
        return result, status
    def mapping(owner, row):
        data = dimensions(row)
        return data['designation'] if data else previous_mapping(owner, row)
    cls._payload, cls._row_payload, cls._mapping_text = substitution, decoder, mapping
    previous_form = source_completion.form_values
    def form_values(row):
        result = previous_form(row)
        data = dimensions(row)
        if data:
            result['height_mm'] = str(data['source_height_mm'] or '')
            result['insulation'] = str(data['source_insulation_mm'] or '')
        return result
    source_completion.form_values = form_values
