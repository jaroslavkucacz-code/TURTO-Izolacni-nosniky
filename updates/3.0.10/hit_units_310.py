from __future__ import annotations

"""Row-specific HIT input units, using the existing verified calculation engines.

The catalogue capacities stay per metre. An element input is divided by EACH
candidate's physical length (033 = 333 mm), never by its quantity or spacing.
Only direct standard HIT row calculations enter the scoped adapter.
"""
from contextvars import ContextVar
from dataclasses import replace
from functools import wraps
import math
import tkinter as tk
from tkinter import ttk

VERSION = '3.0.10'
METRE = 'kN/m · kNm/m'
ELEMENT = 'kN/prvek · kNm/prvek'
LABELS = {'per_metre': METRE, 'per_element': ELEMENT}
LENGTHS = {100: 1000, 50: 500, 33: 333, 25: 250}
STANDARD = {'MVX', 'MVXL', 'ZVX', 'ZDX', 'DD', 'DVL', 'DDL'}
KEYS = ('m_pos', 'm_neg', 'n_pos', 'n_neg', 'v_pos', 'v_neg')
ACTION_LABELS = ('MEd+', 'MEd−', 'NEd+', 'NEd−', 'VEd+', 'VEd−')
_ELEMENT_INPUT = ContextVar('turto_hit_element_input', default=False)


def basis(row):
    value = row.load_basis.get()
    if value not in LABELS.values():
        raise ValueError('Vyberte jednotky účinků na metr nebo na prvek.')
    return 'per_element' if value == ELEMENT else 'per_metre'


def scaled_actions(actions, length_mm):
    if length_mm not in LENGTHS.values():
        raise ValueError('Chybí ověřená fyzická délka HIT pro převod jednotek.')
    values = {k: float(getattr(actions, k)) * 1000 / length_mm for k in KEYS}
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError('Návrhové účinky musí být konečná čísla.')
    return replace(actions, **values)


def _install_engine(database):
    if getattr(database, '_turto_units_310', False):
        return
    proposal, directional = database.proposal_candidates, database.directional_candidates

    def converted(original, is_proposal):
        @wraps(original)
        def calculate(self, connection_type, series, height, cover, concrete,
                      actions, lengths, include_offsets=False, load_distance_x=0.0):
            args = (connection_type, series, height, cover, concrete)
            if not _ELEMENT_INPUT.get():
                return original(self, *args, actions, lengths, include_offsets, load_distance_x)
            if connection_type.upper() not in STANDARD:
                raise ValueError('Volba jednotek tohoto řádku je určena pro deskové a balkonové HIT.')
            rows, errors = [], []
            # Avoid converting twice when proposal delegates to directional.
            token = _ELEMENT_INPUT.set(False)
            try:
                for code in sorted(lengths, reverse=True):
                    if code not in LENGTHS:
                        raise ValueError('Neznámá délka HIT; nelze přepočítat účinky na prvek.')
                    loads = scaled_actions(actions, LENGTHS[code])
                    result = original(self, *args, loads, {code}, include_offsets, load_distance_x)
                    found, error = result[:2]
                    errors += [error] if error else []
                    for candidate in found:
                        if candidate.physical_length_mm != LENGTHS[code]:
                            raise ValueError('Výsledek HIT neodpovídá délce použité při přepočtu.')
                        if not math.isfinite(candidate.utilization):
                            raise ValueError('Výpočet HIT vrátil neplatné využití.')
                        rows.append(candidate)
            finally:
                _ELEMENT_INPUT.reset(token)
            typ = connection_type.upper()
            rows = list({c.designation: c for c in rows}.values())
            primary = [c for c in rows if c.connection_type == typ]
            other = [c for c in rows if c.connection_type != typ]
            # Preserve the original family policy across ALL allowed lengths:
            # MVX falls back to MVXL only when no preferred MVX is suitable.
            if typ == 'MVX' and primary:
                other = []
            order = lambda c: (-c.utilization, -c.length_code, c.designation)
            rows = sorted(primary, key=order) + sorted(other, key=order)
            error = '' if rows else '\n'.join(dict.fromkeys(errors))
            if not is_proposal:
                return rows, error
            alternative = {'MVX': 'MVXL', 'MVXL': 'MVX'}.get(typ, '')
            fallback = not primary and bool(other)
            note = ('MVX nevyhovuje; nabídnuta vyhovující náhrada MVXL.' if fallback and typ == 'MVX'
                    else 'MVXL vyhovuje; k dispozici je také alternativa MVX.' if primary and other else '')
            info = dict(preferred_type=typ, primary_available=bool(primary),
                        alternative_type=alternative, alternative_count=len(other),
                        mode='fallback' if fallback else 'related' if other else 'preferred', note=note)
            return rows, error, info
        return calculate

    database.proposal_candidates = converted(proposal, True)
    database.directional_candidates = converted(directional, False)
    database._turto_units_310 = True


def _units(row):
    suffix = '/prvek' if basis(row) == 'per_element' else '/m'
    return ['kNm' + suffix if k.startswith('m') else 'kN' + suffix for k in KEYS]


def _replace_imports(name, old, new):
    # Historical runtime layers import these functions by identity.
    import sys
    for module in tuple(sys.modules.values()):
        if module is not None and vars(module).get(name) is old:
            setattr(module, name, new)


def _headers(owner):
    frame = getattr(owner, 'hit_rows_frame', None)
    if frame is None or getattr(frame, '_turto_units_310', False):
        return
    for w in frame.winfo_children():
        if not isinstance(w, ttk.Label):
            continue
        info = w.grid_info()
        if not info or int(info.get('row', -1)) != 0:
            continue
        col = int(info['column'])
        if col >= 10:
            w.grid_configure(column=col + 1)
        text = str(w.cget('text'))
        if text.startswith(('MEd', 'VEd')):
            w.configure(text=text.split(' [')[0] + '¹')
    ttk.Label(frame, text='Jednotky účinků¹', style='Card.TLabel', anchor='center').grid(
        row=0, column=10, sticky='ew', padx=2, pady=2)
    frame._turto_units_310 = True


def install(base_app=None):
    import hit_core, hit_workspace, hit_choice_309, hit_design_ui, hit_export_ui
    cls = hit_workspace.HitInputRow
    if getattr(cls, '_turto_units_310', False):
        return
    _install_engine(hit_core.HitDatabase)
    hit_choice_309.FIELDS += ('load_basis',)
    old_init, old_recalc = cls.__init__, cls.recalculate
    old_defaults, old_show = cls.defaults_for_next, cls._show_candidate
    old_summary, old_read = cls.action_summary, cls._read_values
    old_future = cls.future_link_payload

    @wraps(old_init)
    def initialize(self, owner, row_no, defaults=None):
        values = dict(defaults or {})
        self.load_basis = tk.StringVar(master=owner, value=LABELS.get(values.get('load_basis', 'per_metre'),
                                                                   values.get('load_basis', METRE)))
        old_init(self, owner, row_no, values)
        control = ttk.Combobox(owner.hit_rows_frame, textvariable=self.load_basis,
                              values=(METRE, ELEMENT), state='readonly', width=23, justify='center')
        self.load_basis_combo = control
        control.bind('<<ComboboxSelected>>', self._input_changed_now)
        control.bind('<MouseWheel>', owner._on_hit_mousewheel)
        self.widgets.append(control)
        widgets = list(self._hit_base_widgets)
        widgets.insert(widgets.index(self.med_pos_entry), control)
        self._hit_base_widgets = widgets
        self.regrid(row_no)

    @wraps(old_recalc)
    def recalculate(self, *args, **kwargs):
        try:
            mode = basis(self)
        except ValueError as exc:
            hit_choice_309._cancel(self, '_after_id')
            self._manual_product = False
            self._set_error(str(exc))
            return
        token = _ELEMENT_INPUT.set(mode == 'per_element')
        try:
            return old_recalc(self, *args, **kwargs)
        finally:
            _ELEMENT_INPUT.reset(token)

    @wraps(old_read)
    def read(self):
        result = old_read(self)
        if result is not None and not all(math.isfinite(getattr(result[2], key)) for key in KEYS):
            raise ValueError('Návrhové účinky musí být konečná čísla.')
        return result

    def defaults(self):
        return {**old_defaults(self), 'load_basis': basis(self)}

    def summary(self):
        if basis(self) == 'per_metre':
            return old_summary(self)
        actions = self.effective_action_texts()
        return ' • '.join(f'{label} {actions.get(key) or "—"} {unit}'
                          for key, label, unit in zip(KEYS, ACTION_LABELS, _units(self))
                          if self._active_action_mask().get(key, False))

    @wraps(old_show)
    def show(self, candidate):
        old_show(self, candidate)
        if basis(self) == 'per_element':
            length = candidate.physical_length_mm
            self.detail.set(self.detail.get() + f' • zadání na prvek, L = {length} mm; katalogové únosnosti na metr')

    def future(self):
        result = old_future(self)
        if result is not None:
            result['load_basis'] = basis(self)
            result['input_units'] = dict(zip(KEYS, _units(self)))
        return result

    cls.__init__, cls.recalculate, cls._read_values = initialize, recalculate, read
    cls.defaults_for_next, cls.action_summary, cls._show_candidate = defaults, summary, show
    cls.future_link_payload = future
    cls._turto_units_310 = True

    mixin = hit_workspace.HitWorkspaceMixin
    build_class = base_app.ThermalConnectorApp if base_app is not None else mixin
    old_build = build_class._build_hit_tab
    @wraps(old_build)
    def build(self, parent):
        result = old_build(self, parent)
        _headers(self)
        # This is part of the standard module, so it remains visible on return.
        bar = ttk.Frame(self.hit_standard_tab, style='App.TFrame')
        bar.grid(row=2, column=0, sticky='ew', pady=(4, 0))
        label = ttk.Label(bar, style='Muted.TLabel', text=(
            '¹ Jednotky zvolte u každého řádku. Přepnutí ponechá zadaná čísla. '
            'Na prvek: posouzení podle délky každé varianty, nikoli podle počtu kusů.'))
        label.pack(fill='x')
        bar.bind('<Configure>', lambda e: label.configure(wraplength=max(300, e.width - 10)))
        self.hit_units_hint = label
        return result
    build_class._build_hit_tab = build

    old_serialize = hit_design_ui.serialize_hit_design
    @wraps(old_serialize)
    def serialize(owner):
        result = old_serialize(owner)
        for data, row in zip(result['rows'], owner.hit_rows):
            data['load_basis'] = basis(row)
        return result
    _replace_imports('serialize_hit_design', old_serialize, serialize)
    mixin._serialize_hit_design = serialize

    old_collect = hit_export_ui.collect_hit_rows
    @wraps(old_collect)
    def collect(owner):
        result = old_collect(owner)
        for data, row in zip(result, owner.hit_rows):
            mode = basis(row)
            data['load_basis'] = mode
            data['input_units'] = dict(zip(KEYS, _units(row)))
            if mode == 'per_element':
                data['custom_actions'] = [dict(label=label, value=data['actions'].get(key, ''), unit=unit)
                                          for key, label, unit in zip(KEYS, ACTION_LABELS, _units(row))]
                c = row.selected_candidate
                if c is not None:
                    values = row._read_values()
                    normalized = scaled_actions(values[2], c.physical_length_mm) if values else None
                    data['actions_per_metre'] = {k: getattr(normalized, k) for k in KEYS} if normalized else {}
                    data['notes'].append(f'Zadání na jeden prvek. Převod pro posouzení: účinek / '
                                         f'{c.physical_length_mm / 1000:g} m. Katalogové únosnosti jsou na metr.')
        return result
    _replace_imports('collect_hit_rows', old_collect, collect)

    # Existing supplier export already respects custom_actions. Keep the legacy
    # plain clipboard equally explicit when rows use different input bases.
    def copy(self):
        rows = [r for r in collect(self) if r.get('candidate')]
        if not rows:
            self.hit_status_var.set('Není co kopírovat – nejprve navrhněte alespoň jeden HIT.')
            return
        lines = [['Pozice', 'Ks', 'Řada', 'Typ', 'h [mm]', 'cnom [mm]', 'Beton', 'L [mm]',
                  'Jednotky M', 'Jednotky V/N', *ACTION_LABELS, 'Navržený HIT', 'Využití [%]',
                  'M1 [kNm/m]', 'V1 [kN/m]', 'M2 [kNm/m]', 'V2 [kN/m]', 'Zdroj']]
        for r in rows:
            c = r['candidate']; a = r['actions']; u = r['input_units']
            lines.append([r['name'], r['quantity'], r['series'], c['connection_type'], r['height_mm'],
                          r['cover_mm'], r['concrete'], c['physical_length_mm'], u['m_neg'], u['v_pos'],
                          *[a.get(k, '') for k in KEYS], c['designation'], f"{c['utilization']*100:.1f}",
                          *[c.get(k, '') for k in ('m1','v1','m2','v2')], c['page']])
        self.clipboard_clear()
        self.clipboard_append('\n'.join('\t'.join(str(v).replace('\t',' ').replace('\n',' ') for v in line)
                                        for line in lines))
        self.hit_status_var.set(f'Do schránky zkopírováno {len(rows)} návrhů HIT včetně jednotek.')
    mixin.copy_hit_results = copy

    # Use the same visible unit spelling in the existing shared form.
    import thermal_design_ui
    original_hint = thermal_design_ui.SharedDesign.update_hint
    @wraps(original_hint)
    def hint(self):
        original_hint(self)
        for key in ('moment', 'shear', 'axial'):
            label = self.labels[key]
            label.configure(text=str(label.cget('text')).replace('/ks', '/prvek'))
    thermal_design_ui.SharedDesign.update_hint = hint


def selftest():
    import hit_core, hit_workspace
    assert VERSION == '3.0.10'
    assert hit_core.HitDatabase._turto_units_310 and hit_workspace.HitInputRow._turto_units_310
    a = scaled_actions(hit_core.DirectionalActions(m_neg=10, v_pos=5), 500)
    assert a.m_neg == 20 and a.v_pos == 10
    assert not _ELEMENT_INPUT.get()
