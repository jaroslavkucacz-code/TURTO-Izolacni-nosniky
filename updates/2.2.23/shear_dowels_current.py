from __future__ import annotations

"""TURTO 2.2.23 – restore the complete verified shear-dowel method chain.

TURTO 2.2.21 added Ancon terminology and passing alternatives on top of the
2.2.7 four-manufacturer UI. That wrapper accidentally skipped the stable
2.1.5 install_methods() layer. The skipped layer owns decoder/schedule and
row-action methods used while the shear workspace is built.

This public boundary restores the 2.1.5 method layer first and then applies
the exact verified 2.2.21 enhancements. It does not persist any data.
"""

from typing import Any

import shear_dowels_ui_215 as _stable
import shear_dowels_current_221 as _current

build_shear_workspace = _current.build_shear_workspace
init_shear_workspace = _current.init_shear_workspace


def install_methods(cls: Any) -> None:
    """Install the complete historical chain, then the 2.2.21 overrides."""
    if getattr(cls, "_turto_shear_223_installed", False):
        return

    _stable.install_methods(cls)
    _current.install_methods(cls)

    required = (
        "open_shear_decoder_schedule",
        "open_shear_design_schedule",
        "add_shear_decoder_row",
        "add_shear_design_row",
        "shear_decoder_to_substitution",
        "sync_shear_substitutions_from_decoder",
        "recalculate_shear_substitutions",
        "recalculate_shear_design_all",
        "shear_edit_meta",
        "shear_duplicate_selected",
        "shear_move_selected",
        "shear_delete_selected",
        "refresh_shear_tables",
        "serialize_shear_dowels",
        "load_shear_dowels",
    )
    missing = [name for name in required if not callable(getattr(cls, name, None))]
    if missing:
        raise RuntimeError(
            "Neúplná instalace smykových trnů; chybí metody: " + ", ".join(missing)
        )

    cls._turto_shear_223_installed = True


__all__ = ("build_shear_workspace", "init_shear_workspace", "install_methods")


def selftest() -> None:
    assert callable(_stable.install_methods)
    assert callable(_current.install_methods)


if __name__ == "__main__":
    selftest()
