from __future__ import annotations

"""Selectable dowel alternatives, stored per row and revalidated on calculation.

Catalogue calculations stay in shear_ui_227. Only an explicit identity is saved;
capacities/utilization always come from a fresh design for the current inputs.
"""
from functools import wraps
from tkinter import ttk
import shear_dowels_current_221 as panel
import shear_ui_227 as ui

VERSION = '3.0.18'
CHOICE = 'manual_candidate'
_original_candidates = panel._row_candidates


def identity(candidate):
    return (str(candidate.get('manufacturer', '')), str(candidate.get('designation', '')))


def row_manufacturer(row, fallback_manufacturer='Ancon'):
    return str(row.get('design_manufacturer') or row.get('manufacturer')
               or (row.get('candidate') or {}).get('manufacturer') or fallback_manufacturer)


def row_candidates(row, fallback_manufacturer='Ancon'):
    manufacturer = row_manufacturer(row, fallback_manufacturer)
    if 'cret' in manufacturer.lower() or 'aschwanden' in manufacturer.lower():
        import cret_series_100_239 as cret
        try:
            return cret.design_cret(ved=abs(float(row.get('ved', 0))), slab_mm=float(row.get('slab_mm', 0)),
                gap_mm=float(row.get('gap_mm', 0)), concrete=str(row.get('concrete', 'C25/30')),
                movement=str(row.get('movement', 'axial')), application=str(row.get('application', 'new')),
                low_sleeve=str(row.get('low_sleeve', 'stainless')))
        except Exception as exc:
            return [], str(exc)
    return _original_candidates(dict(row, manufacturer=manufacturer), manufacturer)


def design_row(row, fallback_manufacturer='Ancon'):
    selected = row.get(CHOICE)
    candidates, error = row_candidates(row, fallback_manufacturer)
    if not isinstance(selected, dict) or not selected.get('designation'):
        return (panel._candidate_dict(candidates[0]), '') if candidates else (None, error or 'Nenalezen vyhovující trn.')
    for value in candidates:
        candidate = panel._candidate_dict(value)
        if identity(candidate) == identity(selected) and candidate.get('status') == 'VYHOVUJE':
            return candidate, ''
    return None, (f"Ručně zvolený typ {selected['designation']} pro aktuální zadání nevyhovuje nebo není dostupný. "
                  'Vyberte jinou alternativu nebo obnovte automatický návrh.' + (f' {error}' if error else ''))


def selected_row(owner):
    index = panel._selected_design_index(owner)
    return owner.shear_design_rows[index] if index is not None else None


def sync_buttons(owner):
    tree = owner.shear_design_alternatives_tree
    row = selected_row(owner)
    valid = row is not None and row is getattr(owner, '_alternative_row_318', None)
    selection = tree.selection()
    chosen = getattr(owner, '_alternatives_318', {}).get(selection[0]) if selection else None
    for attr, enabled in (('shear_use_alternative_button', valid and chosen is not None),
                          ('shear_auto_design_button', row is not None and bool(row.get(CHOICE)))):
        button = getattr(owner, attr, None)
        if button is not None:
            button.state(['!disabled'] if enabled else ['disabled'])


def refresh_alternatives(owner):
    tree = getattr(owner, 'shear_design_alternatives_tree', None)
    if tree is None:
        return
    row = selected_row(owner)
    same = row is not None and row is getattr(owner, '_alternative_row_318', None)
    selection = tree.selection()
    previous = getattr(owner, '_alternatives_318', {}).get(selection[0]) if same and selection else None
    owner._alternative_row_318 = row
    candidates, error = panel._row_candidates(row, owner.shear_design_manufacturer_var.get()) if row is not None else ([], '')
    primary = (row.get('candidate') or {}).get('designation', '') if row is not None else ''
    alternatives = panel._passing_alternatives(candidates, primary)
    owner._alternatives_318 = {str(i): c for i, c in enumerate(alternatives)}
    # Update existing rows in place: selection and scrolling do not flicker.
    for iid in tree.get_children(''):
        if iid not in owner._alternatives_318:
            tree.delete(iid)
    for iid, candidate in owner._alternatives_318.items():
        source = str(candidate.get('manufacturer', ''))
        page = str(candidate.get('page', '') or '')
        values = tuple(map(str, (
            source, candidate.get('designation', ''), panel._fmt(candidate.get('vrd')),
            panel._fmt(float(candidate.get('utilization', 0) or 0) * 100) + ' %',
            panel._fmt(candidate.get('slab_table_mm'), 0), panel._fmt(candidate.get('gap_table_mm'), 0),
            source + (f' p.{page}' if page else ''), candidate.get('note', ''),
        )))
        if tree.exists(iid):
            if tuple(map(str, tree.item(iid, 'values'))) != values:
                tree.item(iid, values=values)
        else:
            tree.insert('', 'end', iid=iid, values=values)
    retained = next((iid for iid, c in owner._alternatives_318.items()
                     if previous and identity(c) == identity(previous)), None)
    desired_selection = (retained,) if retained is not None else ()
    if tree.selection() != desired_selection:
        tree.selection_set(desired_selection)
    status = owner.shear_design_alternatives_status
    if row is None:
        text = 'Vyberte řádek návrhu. Poté označte alternativu a použijte ji tlačítkem nebo dvojklikem.'
    else:
        manual = row.get(CHOICE)
        prefix = (f"Ručně: {manual['designation']}. " if isinstance(manual, dict) else '')
        if row.get('error'):
            prefix = row['error'] + ' '
        if alternatives:
            text = prefix + f'{len(alternatives)} alternativ. Potvrďte tlačítkem, dvojklikem nebo Enterem.'
        else:
            text = prefix + (f'Další alternativy nelze určit: {error}' if error else 'Další vyhovující alternativa není k dispozici.')
    status.set(text)
    sync_buttons(owner)


def apply_alternative(owner):
    row = selected_row(owner)
    tree = owner.shear_design_alternatives_tree
    selection = tree.selection()
    candidate = owner._alternatives_318.get(selection[0]) if selection else None
    # An event queued for another row must never change the newly selected row.
    if row is None or row is not getattr(owner, '_alternative_row_318', None) or candidate is None:
        refresh_alternatives(owner)
        return
    choice = dict(zip(('manufacturer', 'designation'), identity(candidate)))
    proposed, error = design_row(dict(row, **{CHOICE: choice}), owner.shear_design_manufacturer_var.get())
    if proposed is None:
        current, current_error = design_row(row, owner.shear_design_manufacturer_var.get())
        row.update(candidate=current or {}, error=current_error)
        owner.mark_project_dirty()
        owner.refresh_shear_tables()
        owner.shear_design_alternatives_status.set(error)
        return
    row.update({CHOICE: choice, 'candidate': proposed, 'error': ''})
    owner.mark_project_dirty()
    owner.refresh_shear_tables()


def automatic_design(owner):
    row = selected_row(owner)
    if row is None or not row.get(CHOICE):
        return
    row.pop(CHOICE, None)
    candidate, error = design_row(row, owner.shear_design_manufacturer_var.get())
    row.update(candidate=candidate or {}, error=error)
    owner.mark_project_dirty()
    owner.refresh_shear_tables()


def build_controls(owner):
    tree = owner.shear_design_alternatives_tree
    card = tree.master.master
    card.configure(padding=(10, 4, 10, 4))
    actions = ttk.Frame(card, style='Card.TFrame')
    actions.grid(row=0, column=1, sticky='e', padx=(8, 0))
    tree.master.grid_configure(columnspan=2)
    for widget in card.winfo_children():
        if isinstance(widget, ttk.Label) and str(widget.cget('textvariable')):
            widget.grid_configure(columnspan=2)
    # Leave room for both result lists in a normal-sized window.
    owner.shear_design_tree.configure(height=4)
    card.master.rowconfigure(4, minsize=96)
    help_label = getattr(owner, '_turto_ed_help_221', None)
    if help_label is not None:
        help_label.grid_remove()
    combo = getattr(owner, '_shear_design_manufacturer_combo_227', None)
    if combo is not None:
        combo.configure(values=('Ancon', 'Schöck', 'PohlCon', 'MAXFRANK', 'Aschwanden CRET'))
        # CRET added a second selector for the same variable; keep one selector.
        for widget in panel._walk(panel._design_tab(owner)):
            if isinstance(widget, ttk.Combobox) and widget is not combo and str(widget.cget('textvariable')) == str(owner.shear_design_manufacturer_var):
                widget.master.grid_remove()
    owner.shear_use_alternative_button = ttk.Button(
        actions, text='Použít vybranou alternativu', style='Accent.TButton',
        command=lambda: apply_alternative(owner))
    owner.shear_use_alternative_button.pack(side='left')
    owner.shear_auto_design_button = ttk.Button(
        actions, text='Obnovit automatický návrh', command=lambda: automatic_design(owner))
    owner.shear_auto_design_button.pack(side='left', padx=(8, 0))
    tree.bind('<<TreeviewSelect>>', lambda _event: sync_buttons(owner), add='+')
    tree.bind('<Return>', lambda _event: (apply_alternative(owner), 'break')[1])
    def double_click(event):
        iid = tree.identify_row(event.y)
        if iid and tree.identify_region(event.x, event.y) == 'cell':
            tree.selection_set(iid)
            apply_alternative(owner)
        return 'break'
    tree.bind('<Double-1>', double_click)
    # Keep long help text inside the visible panel when the window is narrowed.
    for widget in card.winfo_children():
        if isinstance(widget, ttk.Label):
            card.bind('<Configure>', lambda event, label=widget: label.configure(wraplength=max(220, event.width - 24)), add='+')
    refresh_alternatives(owner)


def install(base):
    cls = base.ThermalConnectorApp
    if getattr(cls, '_shear_choice_318', False):
        return
    import shear_cret_239
    shear_cret_239._design = design_row
    ui._design_row = design_row
    panel._row_candidates = row_candidates
    panel._refresh_alternatives = refresh_alternatives
    previous_build, previous_load = cls._build_body, cls.load_shear_dowels
    previous_add = cls.add_shear_design_row
    previous_recalculate = cls.recalculate_shear_design_all

    @wraps(previous_build)
    def build(self, *args, **kwargs):
        previous_build(self, *args, **kwargs)
        build_controls(self)

    @wraps(previous_load)
    def load(self, payload):
        previous_load(self, payload)
        for row in self.shear_design_rows:
            if row.get(CHOICE):
                candidate, error = design_row(row, self.shear_design_manufacturer_var.get())
                row.update(candidate=candidate or {}, error=error)
        self.refresh_shear_tables()

    @wraps(previous_add)
    def add(self):
        count = len(self.shear_design_rows)
        previous_add(self)
        if len(self.shear_design_rows) > count:
            iid = str(len(self.shear_design_rows) - 1)
            self.shear_design_tree.selection_set(iid)
            self.shear_design_tree.focus(iid)
            self.shear_design_tree.see(iid)
            refresh_alternatives(self)

    @wraps(previous_recalculate)
    def recalculate(self):
        for row in self.shear_design_rows:
            # Legacy saved rows may identify their manufacturer only in the result.
            # The quick-add selector must not overwrite that identity on recalculation.
            row['design_manufacturer'] = row_manufacturer(row, self.shear_design_manufacturer_var.get())
        previous_recalculate(self)

    cls.recalculate_shear_design_all = recalculate
    cls.add_shear_design_row = add
    cls._build_body, cls.load_shear_dowels = build, load
    cls._shear_choice_318 = True
