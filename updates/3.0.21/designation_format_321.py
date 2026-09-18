"""Normalize typography of explicit Schöck codes without changing their meaning.

No generations, load classes, dimensions or catalogue capacities are substituted.
The original input remains available in the project and bulk review.
"""
from functools import wraps
import re

import catalog_engine as catalog
import bulk_import_engine as bulk
import bulk_import
import decoder_315 as decoder
import isokorb_families_304 as families


def normalize(text):
    original = str(text or '')
    value = decoder.normalized(original)
    prefix = re.match(r'^(?:SCHO(?:CK|ECK)\s+)?(?:ISOKORB\s+)?'
                      r'(CXT|XT|T)(?:\s*(?:TYPE|TYP))?(?:\s*-\s*|\s+)', value)
    if not prefix:
        return original
    code = value[prefix.end():].strip()
    if not re.match(r'^(?:KL|QP|QL|ZL|AP)(?=$|[\s-])', code):
        return original
    # Join only a known parameter label and its number, never two numbers.
    code = re.sub(r'\b(REI|EI|CV|LR|MM|VV|M|V|H|B|L)\s+(?=\d)', r'\1', code)
    code = re.sub(r'\s*([.,])\s*', r'\1', code)
    code = re.sub(r'\s*-\s*', '-', code)
    code = re.sub(r'\s+', '-', code)
    # A decimal comma is a generation separator, not a quantity or dimension.
    code = re.sub(r'(\d+),(\d+)$', r'\1.\2', code)
    # Example from a real bill: H200.2,0 -> H200-2.0.
    code = re.sub(r'((?:H|L)\d+)\.(\d+\.\d+)$', r'\1-\2', code)
    code = re.sub(r'(?<=\d)(?=(?:REI|EI|CV|LR|MM|VV|M|V|H|B|L)\d)', '-', code)
    # Preserve exact catalogue labels with ranges / geometry annotations. They
    # must still resolve after a user selects them from the autocomplete list.
    if not re.fullmatch(r'(?:KL(?:-[OU])?|QP(?:-Z)?|QL|ZL|AP)'
                        r'(?:-(?:(?:REI|EI|CV|LR|MM|VV|M|V|H|B|L)\d*|\d+\.\d*))*-?', code):
        return original
    return prefix.group(1) + '-' + code


def parsed_code(text):
    code = normalize(text)
    parsed = families.parse(code)
    if parsed:
        return parsed
    # Recognize insulating ZL elements even when their generation is not loaded.
    match = re.fullmatch(r'(T|XT)-ZL-EI(\d+)-H(\d+)-(\d+\.\d+)', code)
    if match:
        model, fire, height, generation = match.groups()
        return families.Parsed(model, 'ZL', code, dict(fire=fire, height=height, generation=generation))
    return None


def input_issue(text):
    code = normalize(text)
    if re.match(r'^(?:T|XT)-QP(?:-Z)?-', code) and re.search(r'-VV-V\d+(?:-|$)', code):
        return ('Nejednoznačná smyková třída VV-V: ověřte, zda má být V1, VV1 nebo jiná třída. '
                'Zápis se automaticky neopravuje. Přečteno: ' + code + '.')
    return ''


def missing_length_choices(database, text, concrete, preferred=None):
    """An omitted QP length needs an explicit choice, even with one candidate."""
    code = normalize(text)
    match = re.fullmatch(r'(T|XT)-(QP(?:-Z)?)-(VV?\d+)-REI(\d+)-H(\d+)-(\d+\.\d+)', code)
    if not match:
        return None
    model, family, shear, fire, height, generation = match.groups()
    parsed = families.Parsed(model, family, code, dict(shear=shear, fire=fire, height=height, generation=generation))
    choices = families.candidates(database, parsed, concrete)
    out = []
    for choice in choices:
        length = families.old._length(choice.result.record)
        if not length:
            continue
        full = families.parse(code.rsplit('-', 1)[0] + f'-L{length}-' + generation)
        for candidate in families.candidates(database, full, concrete):
            if candidate.result.catalog['id'] == choice.result.catalog['id'] and candidate.result.record['cover'] == choice.result.record['cover']:
                out.append(candidate)
    out = bulk.dedupe_suggestions(out)
    selected = [c for c in out if c.result.catalog['id'] == preferred]
    return selected or out


def missing_data_message(database, text):
    parsed = parsed_code(text)
    if not parsed:
        return ''
    loaded = sorted({str(f.get('generation')) for f in database.families
                     if families.old.norm(f.get('manufacturer')) in ('SCHOCK', 'SCHOECK')
                     and families._model(f.get('model')) == parsed.model
                     and families.old.norm(f.get('type')) == parsed.family})
    message = families.MISSING + ' ' + parsed.canonical + '.'
    if loaded and parsed.fields['generation'] not in loaded:
        message += ' Načtené generace této řady: ' + ', '.join(loaded) + '; zadaná generace ' + parsed.fields['generation'] + ' chybí.'
    elif not loaded:
        message += ' Tato řada není v načtených katalogových datech.'
    message += ' Únosnost ani jiná generace se nedoplňuje.'
    return message


def _patch_database(cls):
    if cls.__dict__.get('_turto_format_321'):
        return
    resolve, suggest = cls.resolve_designation, cls.suggest_designations

    @wraps(resolve)
    def resolve_formatted(self, text, preferred_catalog_id=None, preferred_concrete=None):
        code = normalize(text)
        issue = input_issue(code)
        if issue:
            raise catalog.SelectionError(issue)
        choices = missing_length_choices(self, code, preferred_concrete, preferred_catalog_id)
        if choices is not None:
            raise catalog.SelectionError('Chybí délka L v označení QP. Doplňte ji nebo potvrďte konkrétní délku z našeptávače. Přečteno: ' + code + '.')
        try:
            return resolve(self, code, preferred_catalog_id, preferred_concrete)
        except catalog.SelectionError:
            # Keep existing ambiguity/geometry messages when matching data exist.
            if parsed_code(code) and not suggest(self, code, preferred_catalog_id, preferred_concrete, 1):
                raise catalog.SelectionError(missing_data_message(self, code)) from None
            raise

    @wraps(suggest)
    def suggest_formatted(self, text, preferred_catalog_id=None, preferred_concrete=None, limit=12):
        code = normalize(text)
        if input_issue(code):
            return []
        choices = missing_length_choices(self, code, preferred_concrete, preferred_catalog_id)
        if choices is not None:
            return choices[:max(0, int(limit))]
        return suggest(self, code, preferred_catalog_id, preferred_concrete, limit)

    cls.resolve_designation, cls.suggest_designations = resolve_formatted, suggest_formatted
    cls._turto_format_321 = True


def install(base):
    if getattr(bulk, '_turto_format_321', False):
        return
    previous = bulk._classify_bulk_item

    @wraps(previous)
    def classify(database, item, *, preferred_concrete, suggestion_limit):
        original = item.designation
        code = normalize(original)
        issue = input_issue(code)
        choices = missing_length_choices(database, code, preferred_concrete) if not issue else None
        if issue or choices is not None:
            item.result = None; item.candidates = choices or []; item.archive_source = None
            item.varying_keys = ('cover',) if choices else ()
            item.status = 'review' if choices else 'error'
            item.message = issue or ('Chybí délka L v označení QP. Ověřte a potvrďte katalogovou délku z nabízených možností.'
                                     if choices else 'Chybí délka L v označení QP a nebyla nalezena odpovídající katalogová varianta.')
            return
        try:
            item.designation = code
            previous(database, item, preferred_concrete=preferred_concrete, suggestion_limit=suggestion_limit)
        finally:
            item.designation = original
        if item.status == 'error' and not item.candidates:
            item.message = missing_data_message(database, code) or item.message

    bulk._classify_bulk_item = classify
    _patch_database(catalog.CatalogDatabase)
    _patch_database(base.CatalogDatabase)
    refresh = bulk_import.BulkImportDialog._refresh_review_tree

    @wraps(refresh)
    def refresh_tree(self, *args, **kwargs):
        refresh(self, *args, **kwargs)
        for iid, item in self._item_by_iid.items():
            if item.status == 'error' and parsed_code(item.designation) and item.message.startswith(families.MISSING):
                self.review_tree.set(iid, 'status', 'Chybí data')
                self.review_tree.set(iid, 'resolved', normalize(item.designation))

    bulk_import.BulkImportDialog._refresh_review_tree = refresh_tree
    bulk._turto_format_321 = True
