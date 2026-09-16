from __future__ import annotations

"""Keep explicit HIT choices across focus/layout events and pending timers.

Calculations and candidate filtering stay in the existing row classes. Real
structural input edits still invalidate the choice and recalculate normally.
"""
from functools import wraps

VERSION = '3.0.9'
FIELDS = ('series', 'connection_type', 'mvx_variant', 'mvx_bx', 'height',
          'required_length', 'cover', 'concrete', 'med_pos', 'med_neg', 'ned_pos',
          'ned_neg', 'ved_pos', 'ved_neg', 'hed_parallel', 'hed_perp', 'load_x',
          'dimension', 'wall_height', 'width', 'ved_vertical', 'ved_horizontal')


def _values(row, names):
    return tuple((name, str(getattr(row, name).get()).strip())
                 for name in names if hasattr(row, name))


def _cancel(row, attr):
    job = getattr(row, attr, None)
    if job:
        try:
            row.owner.after_cancel(job)
        except Exception:
            pass  # It may already be the callback currently running.
    setattr(row, attr, None)


def _dirty(row):
    if not getattr(row.owner, '_action_loading', False):
        row.owner.mark_project_dirty()


def _install_row(cls, *, flag, timer, preserve_arg, show, events):
    if getattr(cls, '_turto_choice_309', False):
        return
    original_init = cls.__init__
    original_recalculate = cls.recalculate
    original_product = cls._product_changed

    @wraps(original_init)
    def initialize(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._turto_inputs_309 = _values(self, FIELDS)
        self._turto_metadata_309 = _values(self, ('name', 'quantity'))

    @wraps(original_recalculate)
    def recalculate(self, *args, **kwargs):
        _cancel(self, timer)
        manual = bool(getattr(self, flag, False) or getattr(self, '_saved_manual_product', False))
        requested = args[0] if args else kwargs.get(preserve_arg)
        if not requested and manual:
            requested = self.product.get()
            if args:
                args = (requested, *args[1:])
            else:
                kwargs[preserve_arg] = requested
        result = original_recalculate(self, *args, **kwargs)
        chosen = self.selected_candidate
        # The old calculators only accept names in their freshly verified list.
        # Never restore a stale candidate or old utilization after an input edit.
        keep = bool(manual and requested and chosen and chosen.designation == requested)
        if keep != bool(getattr(self, flag, False)):
            setattr(self, flag, keep)
            if chosen is not None:
                getattr(self, show)(chosen)
        self._turto_inputs_309 = _values(self, FIELDS)
        self._turto_metadata_309 = _values(self, ('name', 'quantity'))
        return result

    def guard(original):
        @wraps(original)
        def changed(self, *args, **kwargs):
            if getattr(self, '_turto_inputs_309', None) == _values(self, FIELDS):
                metadata = _values(self, ('name', 'quantity'))
                if metadata != getattr(self, '_turto_metadata_309', None):
                    _dirty(self)
                    self._turto_metadata_309 = metadata
                return None
            return original(self, *args, **kwargs)
        return changed

    def accept(self, designation):
        if not any(c.designation == designation for c in self.candidates):
            return
        setattr(self, flag, True)
        _cancel(self, timer)
        # Also validate a choice made while a debounced calculation was pending.
        self.recalculate(**{preserve_arg: designation})
        _dirty(self)

    @wraps(original_product)
    def product_changed(self, *args, **kwargs):
        result = original_product(self, *args, **kwargs)
        accept(self, self.product.get())
        return result

    cls.__init__, cls.recalculate, cls._product_changed = initialize, recalculate, product_changed
    for name in events:
        setattr(cls, name, guard(getattr(cls, name)))
    if hasattr(cls, 'open_variants'):
        original_variants = cls.open_variants

        @wraps(original_variants)
        def variants(self, *args, **kwargs):
            if getattr(self, timer, None):
                self.recalculate()
            self._turto_variant_309 = None
            result = original_variants(self, *args, **kwargs)
            selected = self._turto_variant_309
            self._turto_variant_309 = None
            if selected:
                accept(self, selected)
            return result
        cls.open_variants = variants
    cls._turto_choice_309 = True


def install(_base=None):
    import hit_workspace
    import hit_aux_ui
    import hit_wt_ui
    _install_row(hit_workspace.HitInputRow, flag='_manual_product', timer='_after_id',
                 preserve_arg='preserve_product', show='_show_candidate',
                 events=('_input_changed', '_input_changed_now', '_series_changed',
                         '_type_changed', '_mvx_variant_changed', '_mvx_bx_finished', '_cover_changed'))
    for cls in (hit_aux_ui.AuxRow, hit_wt_ui.WtRow):
        events = ['_changed', '_changed_now']
        events += [name for name in ('_type_changed', '_series_changed') if hasattr(cls, name)]
        _install_row(cls, flag='manual_product', timer='_after', preserve_arg='preserve',
                     show='_show', events=events)
    dialog = hit_workspace.HitVariantsDialog
    if not getattr(dialog, '_turto_choice_309', False):
        original_use = dialog._use_selected

        @wraps(original_use)
        def use(self, *args, **kwargs):
            result = original_use(self, *args, **kwargs)
            if self.result is not None:
                self.row._turto_variant_309 = self.result.designation
            return result
        dialog._use_selected = use
        dialog._turto_choice_309 = True


def selftest():
    import hit_workspace, hit_aux_ui, hit_wt_ui
    assert VERSION == '3.0.9'
    assert all(getattr(cls, '_turto_choice_309', False)
               for cls in (hit_workspace.HitInputRow, hit_aux_ui.AuxRow, hit_wt_ui.WtRow))
