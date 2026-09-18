"""Project element length, separate from immutable catalogue capacities.

The existing source_overrides field is the one persisted source of truth for
both decoder and substitutions. Never scale a catalogue value stored per piece.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from functools import wraps
import re
import unicodedata


def parse_length(value, default_unit='m'):
    text = str(value or '').strip().replace('\u00a0', ' ')
    if not text:
        return None
    match = re.fullmatch(r'([+]?(?:\d+(?:[.,]\d*)?|[.,]\d+))\s*(mm|cm|m)?', text, re.I)
    if not match:
        raise ValueError('Délka musí být kladné číslo, například 0,5 m nebo 500 mm.')
    try:
        length = Decimal(match[1].replace(',', '.')) * {'m': 1000, 'cm': 10, 'mm': 1}[(match[2] or default_unit).lower()]
    except (InvalidOperation, KeyError):
        raise ValueError('Neplatná délka prvku.') from None
    if not length.is_finite() or not 0 < length <= 1_000_000 or length != length.to_integral_value():
        raise ValueError('Zadejte kladnou délku v celých milimetrech, nejvýše 1 000 m.')
    return int(length)


def metres(length):
    if length is None:
        return ''
    return format(Decimal(str(length)) / 1000, 'f').rstrip('0').rstrip('.').replace('.', ',') if length % 1000 else str(length // 1000)


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower()) if not unicodedata.combining(c))


def header_length(parts):
    matches = []
    for index, part in enumerate(parts):
        match = re.fullmatch(r'(?:delka(?: prvku)?|length|l)\s*(?:\[(mm|cm|m)\]|\((mm|cm|m)\))?', fold(part).strip())
        if match:
            matches.append((index, match[1] or match[2] or 'm'))
    if len(matches) > 1:
        raise ValueError('Výkaz obsahuje více sloupců délky; ponechte jen jeden.')
    return matches[0] if matches else None


def is_length_header(parts):
    values = [fold(p).strip() for p in parts]
    return (any(v in {'typ', 'oznaceni', 'designation', 'nosnik', 'popis', 'nazev'} for v in values)
            and any(re.match(r'^(?:delka(?: prvku)?|length|l)(?:$|\s*[\[(])', v) for v in values))


def note_length(note):
    # Explicit metadata only. Bare numeric notes and type tokens such as
    # QP-L300, generation 5.0, and H200 are never reinterpreted as input length.
    values = []
    for part in str(note or '').split('|'):
        match = re.fullmatch(r'\s*(?:delka(?: prvku)?|length)\s*[:=]\s*(.*?)\s*', fold(part))
        if match:
            value = parse_length(match[1])
            if value is None:
                raise ValueError('Za údajem „délka“ chybí hodnota.')
            values.append(value)
    if len(set(values)) > 1:
        raise ValueError('Řádek obsahuje rozdílné údaje délky.')
    return values[0] if values else None


def effective_length(row):
    from substitution_workspace import _source_element_length_info
    return _source_element_length_info(row)[0]


def manual_length(row):
    return row.get('mapping', {}).get('source_overrides', {}).get('source_length_mm')


def set_length(row, length):
    """Changing the physical input invalidates old candidates/acceptance only."""
    before = effective_length(row)
    old = row.get('mapping') or {}
    overrides = deepcopy(old.get('source_overrides') or {})
    if length is None:
        overrides.pop('source_length_mm', None)
    else:
        overrides['source_length_mm'] = parse_length(str(length), 'mm')
    row.setdefault('mapping', {})['source_overrides'] = overrides
    if effective_length(row) != before:
        row['mapping'] = dict(status='not_run', targets=[], selected_target_id=None,
            source_meta={}, warnings=[], errors=[], estimated_type='',
            diameter_availability={}, source_overrides=overrides)


def item_length(item):
    if getattr(item, 'element_length_mm', None) is not None:
        return item.element_length_mm
    if item.result is None:
        return None
    from project_model import create_project_row
    row = create_project_row(item.result, position=item.position, note=item.note,
                             source_text=item.source_designation or item.designation)
    return effective_length(row)


def capacity_length_issue(row):
    from substitution_workspace import _per_element
    from iso_bulk_301 import _length
    snapshot = row.get('snapshot') or {}
    catalogue = snapshot.get('element_length_mm') or _length({**(row.get('selection') or {}), **snapshot})
    actual = effective_length(row)
    if not catalogue or not actual or actual == catalogue:
        return ''
    if any(r.get('kind') in {'moment', 'shear', 'normal'} and _per_element(r['kind'], r.get('unit'))
           for r in snapshot.get('results', []) if isinstance(r, dict)):
        return (f'Zadaná délka {actual} mm se liší od katalogové délky {catalogue} mm. '
                'Únosnost na prvek se délkou nepřepočítává; vyberte odpovídající katalogovou variantu nebo ověřte provedení.')
    return ''


def install(base):
    cls = base.ThermalConnectorApp
    if getattr(cls, '_decoder_length_320', False):
        return
    columns = list(cls.PROJECT_COLUMNS)
    index = next(i for i, c in enumerate(columns) if c[0] == 'quantity') + 1
    columns.insert(index, ('element_length', 'Délka [m]', 95, 'center', False))
    cls.PROJECT_COLUMNS = tuple(columns)
    import substitution_workspace as sub
    previous_metadata, previous_design = sub.source_metadata, sub.design_targets

    @wraps(previous_metadata)
    def metadata(row):
        result = previous_metadata(row)
        issue = capacity_length_issue(row)
        if issue:
            result['errors'] = list(dict.fromkeys([*result.get('errors', []), issue]))
        return result

    @wraps(previous_design)
    def design(database, *, row, metadata, **kwargs):
        issue = capacity_length_issue(row)
        if issue:
            return [], [issue]
        return previous_design(database, row=row, metadata=metadata, **kwargs)

    sub.source_metadata, sub.design_targets = metadata, design
    original = cls._build_body

    @wraps(original)
    def build(owner):
        original(owner)
        from tkinter import ttk
        from workspace_controls_317 import walk
        for widget in walk(owner.project_tab):
            if isinstance(widget, ttk.Button) and widget.cget('text') == 'Upravit pozici / ks':
                widget.configure(text='Upravit pozici / ks / délku')
        menu = owner.project_context_menu
        for index in range((menu.index('end') or 0) + 1):
            if menu.type(index) == 'command' and menu.entrycget(index, 'label') == 'Upravit pozici / ks / poznámku':
                menu.entryconfigure(index, label='Upravit pozici / ks / délku / poznámku')
    cls._build_body = build
    cls._decoder_length_320 = True
