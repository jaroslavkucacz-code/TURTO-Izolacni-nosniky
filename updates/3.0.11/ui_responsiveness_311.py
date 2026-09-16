from __future__ import annotations

"""Avoid tearing down an already visible HIT panel when changing its tab."""
from functools import wraps

VERSION = '3.0.11'


def install(base):
    import thermal_design_ui
    import design_groups_restore as groups

    cls = thermal_design_ui.SharedDesign
    if getattr(cls, '_turto_smooth_311', False):
        return
    original = cls.show_hit_group

    @wraps(original)
    def show(self, group):
        key = str(group or '').strip().lower()
        state = self.owner._peikko_shared_panels.get('design')
        if (key in groups._TAB_ATTR and self.owner.design_manufacturer_var.get() == 'Leviat'
                and state and state[2] and all(w.winfo_manager() == 'grid' for w in state[2])
                and self.winfo_manager() != 'grid' and self.advanced is None):
            # Notebook.select retains widgets, focus and both scroll positions.
            groups._select_group(self.owner, key)
            label = groups._CATALOG_LABEL[key]
            if self.owner.design_catalog_var.get() != label:
                self.owner.design_catalog_var.set(label)
            return
        return original(self, group)

    cls.show_hit_group = show
    cls._turto_smooth_311 = True
    base.ThermalConnectorApp._turto_smooth_311 = True


def selftest():
    import thermal_design_ui
    assert VERSION == '3.0.11' and thermal_design_ui.SharedDesign._turto_smooth_311
