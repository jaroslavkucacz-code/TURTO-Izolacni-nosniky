from __future__ import annotations

"""TURTO 2.2.33 – expose every verified Leviat HIT design group in the shared Návrh workspace.

This module does not add or alter structural calculations. It only routes the
shared design screen to the existing verified HIT workspaces for:
- slabs / balconies (including DVL / DDL),
- supplementary elements HT / AT / FT / OTX,
- wall elements HIT-WT.
"""

from tkinter import ttk, messagebox

RESTORE_VERSION = "2.2.33"

GROUPS = (
    ("standard", "Desky / balkony", "MVX · MVXL · ZVX · ZDX · DD · DVL · DDL"),
    ("aux", "Doplňkové prvky", "HT · AT · FT · OTX"),
    ("wt", "Stěny WT", "HIT-WT"),
)

_TAB_ATTR = {
    "standard": "hit_standard_tab",
    "aux": "hit_aux_tab",
    "wt": "hit_wt_tab",
}

_CATALOG_LABEL = {
    "standard": "Leviat HIT – Desky / balkony (včetně DVL / DDL)",
    "aux": "Leviat HIT – Doplňkové prvky HT / AT / FT / OTX",
    "wt": "Leviat HIT – Stěny WT",
}


def _select_group(owner, group: str) -> None:
    """Select an already-built verified HIT sub-workspace."""
    key = str(group or "").strip().lower()
    attr = _TAB_ATTR.get(key)
    if attr is None:
        raise ValueError("Neznámá návrhová skupina HIT.")
    notebook = getattr(owner, "hit_design_notebook", None)
    tab = getattr(owner, attr, None)
    if notebook is None or tab is None:
        raise RuntimeError("Ověřený návrhový modul HIT není v runtime dostupný.")
    notebook.select(tab)


def _show_hit_group(self, group: str) -> None:
    """Leave the compact shared form and open the requested verified HIT group."""
    key = str(group or "").strip().lower()
    try:
        if key not in _TAB_ATTR:
            raise ValueError("Neznámá návrhová skupina HIT.")
        if self.owner.design_manufacturer_var.get() != "Leviat":
            self.owner.design_manufacturer_var.set("Leviat")
            self.switch()

        if self.advanced is not None and self.advanced.winfo_exists():
            self.advanced.destroy()
        self.advanced = None

        state = self.owner._peikko_shared_panels["design"]
        self.grid_remove()
        for widget in [state[1], *state[2], *state[3]]:
            widget.grid_remove()
        for widget in state[2]:
            widget.grid()

        _select_group(self.owner, key)
        self.owner._shared_return_bar.grid(row=4, column=0, sticky="ew", pady=3)
        self.owner.design_catalog_var.set(_CATALOG_LABEL[key])
    except Exception as exc:
        messagebox.showerror("Návrh Leviat HIT", str(exc), parent=self.owner)


def _update_group_bar(self) -> None:
    bar = getattr(self, "hit_group_bar", None)
    if bar is None:
        return
    if self.owner.design_manufacturer_var.get() == "Leviat":
        bar.grid()
    else:
        bar.grid_remove()


def _install_group_bar(shared_cls) -> None:
    if getattr(shared_cls, "_design_groups_restore_233", False):
        return

    original_init = shared_cls.__init__
    original_switch = shared_cls.switch
    original_show_common = shared_cls.show_common

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        bar = ttk.Frame(self, style="App.TFrame")
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        self.hit_group_bar = bar

        ttk.Label(
            bar,
            text="Další ověřené moduly Leviat HIT:",
            font=("Calibri", 10, "bold"),
        ).pack(side="left", padx=(0, 8))

        self.hit_group_buttons = {}
        for key, label, detail in GROUPS:
            button = ttk.Button(
                bar,
                text=label,
                command=lambda value=key: self.show_hit_group(value),
                style="Shared.TButton",
            )
            button.pack(side="left", padx=(0, 7))
            self.hit_group_buttons[key] = button
            # Keep the full type list available to regression tests without
            # changing the structural engine or overloading the visible caption.
            button._turto_group_detail = detail

        ttk.Label(
            bar,
            text="Původní ověřené moduly; bez změny statického výpočtu.",
            style="Muted.TLabel",
        ).pack(side="left", padx=(3, 0))

        self._update_hit_group_bar()

    def switch(self):
        result = original_switch(self)
        self._update_hit_group_bar()
        return result

    def show_common(self):
        result = original_show_common(self)
        self._update_hit_group_bar()
        return result

    shared_cls.__init__ = __init__
    shared_cls.switch = switch
    shared_cls.show_common = show_common
    shared_cls.show_hit_group = _show_hit_group
    shared_cls._update_hit_group_bar = _update_group_bar
    shared_cls._design_groups_restore_233 = True


def install(base) -> None:
    import thermal_design_ui

    shared_cls = getattr(thermal_design_ui, "SharedDesign", None)
    if shared_cls is None:
        raise RuntimeError("Společný formulář návrhu 2.2.31 není dostupný.")
    _install_group_bar(shared_cls)

    # Runtime guard: the release must route only to already-installed verified
    # workspaces, never to a replacement calculator.
    required = (
        "hit_design_notebook",
        "hit_standard_tab",
        "hit_aux_tab",
        "hit_wt_tab",
    )
    base.ThermalConnectorApp._design_groups_required_233 = required
    base.ThermalConnectorApp._design_groups_restore_233 = True


def selftest() -> None:
    assert RESTORE_VERSION == "2.2.33"
    assert tuple(key for key, _label, _detail in GROUPS) == ("standard", "aux", "wt")
    assert "DVL" in GROUPS[0][2] and "DDL" in GROUPS[0][2]
    assert "HT" in GROUPS[1][2] and "OTX" in GROUPS[1][2]
    assert "WT" in GROUPS[2][2]
    assert callable(_select_group)
    assert callable(_show_hit_group)


if __name__ == "__main__":
    selftest()
