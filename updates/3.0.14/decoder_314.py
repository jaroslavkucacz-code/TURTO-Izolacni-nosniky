"""Use the reviewed Schöck resolver in quick entry as well as bulk import.

Search only matching Schöck records for explicitly scoped partial input.
Never manufacture capacities or replace an unavailable type with another brand.
"""
from functools import wraps
import re

import catalog_engine as catalog
import bulk_import_engine as bulk
import isokorb_families_304 as families
import iso_bulk_301 as iso
from isokorb_xt_parser_243 import parse_xt_designation


def normalized(text):
    return iso.norm(text).translate(str.maketrans({c: '-' for c in '‐‑‒–—−'})).replace('®', '')


def context(text):
    value = normalized(text)
    branded = bool(re.match(r'^(?:SCHO(?:CK|ECK)|ISOKORB)\b', value))
    value = re.sub(r'^SCHO(?:CK|ECK)\s*', '', value)
    value = re.sub(r'^ISOKORB\s*', '', value)
    if re.match(r'^(?:SCONNEX|DORN|STACON)\b', value):
        return None
    model = re.match(r'^(CXT|XT|T)(?:\s*(?:TYP|TYPE))?(?=$|[\s-])', value)
    if model:
        model_name = model.group(1)
        value = value[model.end():].lstrip(' -')
    elif branded or re.match(r'^(?:KL|QP|QL|ZL)(?=$|[\s-])', value):
        model_name = None
    else:
        return None
    value = re.sub(r'^TYP(?:E)?\s*', '', value)
    value = re.sub(r'\s*-\s*', '-', value).strip()
    parts = value.split('-') if value else []
    family = parts.pop(0) if parts else ''
    if family in ('KL', 'K', 'QP') and parts and parts[0] in ('O', 'U', 'Z'):
        family += '-' + parts.pop(0)
    fields = []
    valid = bool(re.fullmatch(r'[A-Z]*(?:-[A-Z])?', family))
    for index, token in enumerate(parts):
        last = index == len(parts)-1 and not value.endswith('-')
        if not token and index == len(parts)-1:
            continue
        match = re.fullmatch(r'(REI|EI|CV|LR|MM|VV|M|V|H|B|L)(\d*)|(\d+\.\d*)', token)
        if not match:
            valid = False
            continue
        key = match.group(1) or 'generation'
        number = match.group(2) if match.group(1) else match.group(3)
        if any(k == key for k, _, _ in fields):
            valid = False
        fields.append((key, number, last))
    return dict(model=model_name, family=family, fields=fields, valid=valid,
                family_prefix=not parts and not value.endswith('-'))


def reviewed(text):
    text = normalized(text)
    return families.parse(text) is not None or parse_xt_designation(text) is not None


def exact_choices(database, text, concrete, preferred):
    item = bulk.BulkImportItem(1, normalized(text), '', 1, str(text))
    # These reviewed classifiers read records directly; they never recursively
    # call the quick-entry resolver for the formats accepted by reviewed().
    bulk._classify_bulk_item(database, item, preferred_concrete=concrete, suggestion_limit=500)
    choices = list(item.candidates)
    if item.result is not None and not choices:
        choices = [catalog.DesignationSuggestion(item.result, 1000.0)]
    selected = [s for s in choices if s.result.catalog['id'] == preferred]
    return selected or choices, item.message


def matches(family, record, scope, concrete):
    if iso.norm(family.get('manufacturer')) not in ('SCHOCK', 'SCHOECK'):
        return False
    if scope['model'] and families._model(family.get('model', '')) != scope['model']:
        return False
    typ = normalized(family.get('type', ''))
    if scope['family'] and (not typ.startswith(scope['family']) if scope['family_prefix'] else typ != scope['family']):
        return False
    if concrete and family.get('catalog_id') != families.AP_ID and families._concrete(record.get('concrete_min')) != families._concrete(concrete):
        return False
    for key, number, partial in scope['fields']:
        if key in ('REI', 'EI'):
            fire = iso._fire(record)
            if fire and not any(v.startswith(key+number) if partial else v == key+number for v in fire):
                return False
            continue
        if key == 'H' and number:
            if iso.height_matches(record.get('height_mm', ''), int(number)):
                continue
            value = str(record.get('height_mm', ''))
        elif key in ('M', 'MM'):
            value = normalized(record.get('moment_class', ''))
            number = key+number
        elif key in ('V', 'VV'):
            value = normalized(record.get('shear_class', ''))
            if value in iso.EMPTY:
                value = normalized(record.get('moment_class', ''))
            number = key+number
        elif key == 'CV':
            match = re.match(r'CV(\d+)', normalized(record.get('cover', '')))
            value = match.group(1) if match else ''
        elif key == 'L':
            value = str(iso._length(record) or '')
        elif key == 'generation':
            value = str(family.get('generation', ''))
        elif key in ('LR', 'B'):
            match = re.search(r'(?<![A-Z])'+key+r'(\d+)', normalized(record.get('designation', '')))
            value = match.group(1) if match else ''
        else:
            value = str(record.get('height_mm', ''))
        if not (value.startswith(number) if partial else value == number):
            return False
    return True


def partial_choices(database, scope, concrete, preferred, limit):
    if not scope['valid']:
        return []
    values = []
    for family in database.families:
        for record in family.get('records', []):
            if matches(family, record, scope, concrete):
                values.append(catalog.DesignationSuggestion(database.result_for_record(family, record), 100.0))
    values.sort(key=lambda s: (s.result.catalog['id'] != preferred, catalog.natural_key(s.designation)))
    # Preserve separate source editions/values when their printed names match.
    return values[:max(0, int(limit))]


def _patch(cls):
    if cls.__dict__.get('_turto_decoder_314'):
        return
    resolve, suggest = cls.resolve_designation, cls.suggest_designations

    @wraps(resolve)
    def resolve_scoped(self, text, preferred_catalog_id=None, preferred_concrete=None):
        scope = context(text)
        if scope is None:
            return resolve(self, text, preferred_catalog_id, preferred_concrete)
        if reviewed(text):
            choices, message = exact_choices(self, text, preferred_concrete, preferred_catalog_id)
            if len(choices) == 1:
                return choices[0].result
            raise catalog.SelectionError(message or 'Vyberte odpovídající vydání katalogu Schöck.')
        if scope['valid']:
            # Keep legacy exact aliases, but reject fuzzy/embedded matches that
            # contradict the explicitly typed model, family or parameters.
            try:
                result = resolve(self, text, preferred_catalog_id, preferred_concrete)
                if matches(result.family, result.record, scope, preferred_concrete):
                    return result
            except catalog.SelectionError:
                pass
        values = partial_choices(self, scope, preferred_concrete, preferred_catalog_id, 12)
        if not values:
            raise catalog.SelectionError('Pro toto označení a beton chybí odpovídající záznam Schöck v načtených katalogových datech. Zkontrolujte označení a dostupnost původní složky catalogs.')
        raise catalog.SelectionError('Označení Schöck není jednoznačné. Doplňte parametry nebo vyberte konkrétní typ z našeptávače.')

    @wraps(suggest)
    def suggest_scoped(self, text, preferred_catalog_id=None, preferred_concrete=None, limit=12):
        scope = context(text)
        if scope is None:
            return suggest(self, text, preferred_catalog_id, preferred_concrete, limit)
        if reviewed(text):
            return exact_choices(self, text, preferred_concrete, preferred_catalog_id)[0][:max(0, int(limit))]
        return partial_choices(self, scope, preferred_concrete, preferred_catalog_id, limit)

    cls.resolve_designation = resolve_scoped
    cls.suggest_designations = suggest_scoped
    cls._turto_decoder_314 = True


def install(base):
    _patch(catalog.CatalogDatabase)
    _patch(base.CatalogDatabase)
