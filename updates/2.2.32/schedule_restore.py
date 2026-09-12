from __future__ import annotations

"""TURTO 2.2.32 – restore the verified schedule import entry in the shared design UI."""

from tkinter import ttk, messagebox

RESTORE_VERSION = "2.2.32"


def _open_schedule(self) -> None:
    """Open the verified unified schedule importer from the shared design form."""
    try:
        from unified_schedule import open_unified_schedule
    except Exception as exc:
        messagebox.showerror(
            "Vložit výkaz",
            "Import výkazu není v runtime dostupný.\n\n" + str(exc),
            parent=self.owner,
        )
        return

    before = (
        len(getattr(self.owner, "hit_rows", [])),
        len(getattr(self.owner, "aux_rows", [])),
        len(getattr(self.owner, "wt_rows", [])),
    )
    open_unified_schedule(self.owner)
    after = (
        len(getattr(self.owner, "hit_rows", [])),
        len(getattr(self.owner, "aux_rows", [])),
        len(getattr(self.owner, "wt_rows", [])),
    )

    if after != before:
        # The historical importer intentionally targets the verified Leviat/HIT
        # row engines (standard / supplementary / WT). Show those imported rows
        # immediately instead of leaving the user on the single-item form.
        try:
            if self.owner.design_manufacturer_var.get() != "Leviat":
                self.owner.design_manufacturer_var.set("Leviat")
                self.switch()
            self.show_legacy()
        except Exception:
            pass
        try:
            self.owner.mark_project_dirty()
        except Exception:
            pass


def _install_button(shared_cls) -> None:
    if getattr(shared_cls, "_schedule_restore_232", False):
        return

    original_init = shared_cls.__init__

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        anchor = self.buttons.get("Navrhnout")
        if anchor is None:
            return
        toolbar = anchor.master
        button = ttk.Button(
            toolbar,
            text="Vložit výkaz…",
            command=lambda: _open_schedule(self),
            style="Shared.TButton",
        )
        button.pack(side="left", padx=(0, 7), before=self.buttons.get("Převzít z dekodéru"))
        self.buttons["Vložit výkaz…"] = button

    shared_cls.__init__ = __init__
    shared_cls.open_schedule = _open_schedule
    shared_cls._schedule_restore_232 = True


def install(base) -> None:
    import thermal_design_ui

    shared_cls = getattr(thermal_design_ui, "SharedDesign", None)
    if shared_cls is None:
        raise RuntimeError("Společný formulář návrhu 2.2.31 není dostupný.")
    _install_button(shared_cls)

    try:
        base.ThermalConnectorApp._schedule_restore_232 = True
    except Exception:
        pass


def selftest() -> None:
    assert RESTORE_VERSION == "2.2.32"
    assert callable(_open_schedule)
    assert callable(_install_button)


if __name__ == "__main__":
    selftest()
