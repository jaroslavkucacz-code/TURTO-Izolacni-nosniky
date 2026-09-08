from __future__ import annotations

"""TURTO 2.1.1 UI guard for historical Schöck decoder aliases."""

from typing import Any
from tkinter import messagebox

import shear_dowels_ui_210 as _prev
from shear_dowels_ui_210 import *  # noqa: F401,F403
from shear_dowels_catalog import decode_dowel


def add_decoder(self: Any) -> None:
    _prev.init_shear_workspace(self)
    v = self.shear_decoder_vars
    try:
        info = decode_dowel(v["designation"].get())
        if not info:
            raise ValueError("Označení smykového trnu nebylo rozpoznáno.")
        row = {
            "name": v["name"].get().strip() or _prev._next("S", self.shear_decoder_rows),
            "quantity": _prev._qty(v["qty"].get()),
            "designation": v["designation"].get().strip(),
            "manufacturer": info["manufacturer"],
            "family": info["family"],
            "size": info["size"],
            "movement": info["movement"],
            "slab_mm": _prev._f(v["slab"].get()),
            "gap_mm": _prev._f(v["gap"].get()),
            "concrete": v["concrete"].get(),
            "cover_mm": int(v["cover"].get()),
            "legacy": bool(info.get("legacy", False)),
            "generation": str(info.get("generation", "") or ""),
            "decoder_only": bool(info.get("decoder_only", False)),
            "legacy_detail": str(info.get("legacy_detail", "") or ""),
            "legacy_material": str(info.get("legacy_material", "") or ""),
            "legacy_sleeve": str(info.get("legacy_sleeve", "") or ""),
        }
        self.shear_decoder_rows.append(row)
        _prev._mark(self)
        self.refresh_shear_tables()
        v["name"].set(_prev._next("S", self.shear_decoder_rows))
        if row["legacy"]:
            try:
                self.set_status(
                    f"Dekódováno historické označení {row['designation']} • pouze Dekodér, bez automatického návrhu/záměny."
                )
            except Exception:
                pass
    except Exception as exc:
        messagebox.showerror("Dekodér smykových trnů", str(exc), parent=self)


def refresh(self: Any) -> None:
    _prev.refresh(self)
    tree = getattr(self, "shear_decoder_tree", None)
    if tree is None:
        return
    for index, row in enumerate(getattr(self, "shear_decoder_rows", [])):
        if not isinstance(row, dict) or not row.get("legacy"):
            continue
        iid = str(index)
        if not tree.exists(iid):
            continue
        family = str(row.get("family", ""))
        generation = "Schöck – historické"
        movement = "axiální + příčný" if row.get("movement") == "transverse" else "axiální"
        designation = str(row.get("designation", ""))
        detail = str(row.get("legacy_detail", "") or "")
        if detail:
            designation = designation + "  •  " + detail
        tree.item(
            iid,
            values=(
                row.get("name", ""), row.get("quantity", 1), generation,
                family + " (starší)", row.get("size", ""), movement,
                designation, _prev._fmt(row.get("slab_mm"), 0),
                _prev._fmt(row.get("gap_mm"), 0), row.get("concrete", ""),
            ),
        )


def decoder_to_substitution(self: Any) -> None:
    tree = getattr(self, "shear_decoder_tree", None)
    selected = tree.selection() if tree is not None else ()
    if not selected:
        return
    try:
        row = self.shear_decoder_rows[int(selected[0])]
    except Exception:
        return
    if isinstance(row, dict) and row.get("legacy"):
        messagebox.showinfo(
            "Historické značení Schöck Dorn",
            "Tento řádek používá starší označení Schöck Dorn. TURTO jej dekóduje pro čtení starších projektů, "
            "ale záměrně jej nepřenáší do Návrhu ani Záměn, protože historická třída únosnosti se nesmí zaměnit "
            "za dnešní řadu Stacon bez odpovídajícího historického katalogu.",
            parent=self,
        )
        return
    _prev.decoder_to_substitution(self)


def install_methods(cls: Any) -> None:
    _prev.install_methods(cls)
    cls.add_shear_decoder_row = add_decoder
    cls.refresh_shear_tables = refresh
    cls.shear_decoder_to_substitution = decoder_to_substitution


# Re-export builders; they resolve catalog_summary/decode functions through the
# imported 2.1.0 module, which was loaded against the 2.1.1 catalog wrapper.
build_shear_workspace = _prev.build_shear_workspace
init_shear_workspace = _prev.init_shear_workspace
