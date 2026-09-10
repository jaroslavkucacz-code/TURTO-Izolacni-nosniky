from __future__ import annotations

"""TURTO 2.2.24 – Ancon ED/ESD selection fixed in Návrh and Záměny.

The verified 2.2.23 method chain is kept intact.  This layer makes the
low-capacity Ancon sleeve choice explicit in the substitution workflow and
removes the historical hard-coded ``low_sleeve="stainless"`` path used when
rows were synchronized from the Decoder.

Ancon terminology:
- ED  = complete low-capacity connector with durable plastic sleeve,
- ESD = low-capacity connector with stainless-steel sleeve,
- ESDQ = transverse-movement variant (selected automatically from movement).

No project/database migration is performed.
"""

from copy import deepcopy
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

import shear_dowels_current_221 as _current
import shear_dowels_ui_215 as _stable
from shear_catalogs_227 import design_for_manufacturer

ED_EXPLANATION = getattr(
    _current,
    "ED_EXPLANATION",
    (
        "Ancon ED = kompletní nízkoúnosný smykový konektor: nerezový trn + "
        "odolné plastové pouzdro s přibíjecí destičkou. ED není označení "
        "samotného pouzdra."
    ),
)

ANCON_SUBSTITUTION_SLEEVES = (
    "Nerezové pouzdro (konektor ESD)",
    "Plastové pouzdro (konektor ED)",
)
GENERIC_SUBSTITUTION_SLEEVES = (
    "Nerezové pouzdro",
    "Plastové pouzdro",
)


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _low_sleeve_from_label(value: Any) -> str:
    return "plastic" if "plast" in str(value or "").strip().lower() else "stainless"


def _selected_low_sleeve(owner: Any) -> str:
    values = getattr(owner, "shear_substitution_vars", {})
    variable = values.get("sleeve") if isinstance(values, dict) else None
    try:
        return _low_sleeve_from_label(variable.get() if variable is not None else "")
    except Exception:
        return "stainless"


def _target_name(owner: Any) -> str:
    variable = getattr(owner, "shear_target_manufacturer_var", None)
    try:
        return str(variable.get() or "Schöck")
    except Exception:
        return "Schöck"


def _sleeve_options_for_target(target: Any) -> tuple[str, ...]:
    return (
        ANCON_SUBSTITUTION_SLEEVES
        if "ancon" in str(target or "").strip().lower()
        else GENERIC_SUBSTITUTION_SLEEVES
    )


def _sync_substitution_sleeve_options(owner: Any, *_args: Any) -> None:
    values = getattr(owner, "shear_substitution_vars", {})
    if not isinstance(values, dict):
        return
    variable = values.get("sleeve")
    if variable is None:
        return

    options = _sleeve_options_for_target(_target_name(owner))
    try:
        current = str(variable.get() or "")
    except Exception:
        current = ""

    want_plastic = "plast" in current.lower()
    desired = next(
        (item for item in options if ("plast" in item.lower()) == want_plastic),
        options[0],
    )
    if current not in options:
        try:
            variable.set(desired)
        except Exception:
            pass

    for attr in (
        "_turto_substitution_sleeve_combo_224",
        "_turto_decoder_transfer_sleeve_combo_224",
    ):
        combo = getattr(owner, attr, None)
        if combo is not None:
            try:
                combo.configure(
                    values=options,
                    width=max(20, min(36, max(map(len, options)) + 1)),
                )
            except Exception:
                pass


def _find_substitution_toolbar(owner: Any):
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return None
    try:
        tabs = notebook.tabs()
        tab = notebook.nametowidget(tabs[2]) if len(tabs) > 2 else None
    except Exception:
        return None
    if tab is None:
        return None

    for frame in _walk(tab):
        try:
            if not isinstance(frame, ttk.Frame):
                continue
            texts = {
                str(child.cget("text"))
                for child in frame.winfo_children()
                if isinstance(child, ttk.Button)
            }
            if "Aktualizovat z Dekodéru" in texts and "Přepočítat vše" in texts:
                return frame
        except Exception:
            pass
    return None


def _find_decoder_transfer(owner: Any):
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return None, None
    try:
        tabs = notebook.tabs()
        tab = notebook.nametowidget(tabs[0]) if tabs else None
    except Exception:
        return None, None
    if tab is None:
        return None, None

    for frame in _walk(tab):
        try:
            if not isinstance(frame, ttk.Frame):
                continue
            for child in frame.winfo_children():
                if isinstance(child, ttk.Button) and str(child.cget("text")) == "Převést do Záměn":
                    return frame, child
        except Exception:
            pass
    return None, None


def _install_substitution_sleeve_controls(owner: Any) -> None:
    values = getattr(owner, "shear_substitution_vars", {})
    if not isinstance(values, dict) or values.get("sleeve") is None:
        return
    sleeve_var = values["sleeve"]

    if getattr(owner, "_turto_substitution_sleeve_combo_224", None) is None:
        toolbar = _find_substitution_toolbar(owner)
        if toolbar is not None:
            try:
                ttk.Label(
                    toolbar,
                    text="Varianta Ancon:",
                    style="Card.TLabel",
                    font=("Calibri", 10, "bold"),
                ).grid(row=0, column=6, padx=(14, 4))
                combo = ttk.Combobox(
                    toolbar,
                    textvariable=sleeve_var,
                    state="readonly",
                    width=29,
                )
                combo.grid(row=0, column=7, padx=(0, 10))
                owner._turto_substitution_sleeve_combo_224 = combo
                try:
                    toolbar.columnconfigure(8, weight=1)
                except Exception:
                    pass
            except Exception:
                pass

    if getattr(owner, "_turto_decoder_transfer_sleeve_combo_224", None) is None:
        frame, transfer_button = _find_decoder_transfer(owner)
        if frame is not None and transfer_button is not None:
            try:
                label = ttk.Label(
                    frame,
                    text="varianta Ancon",
                    style="MutedCard.TLabel",
                )
                combo = ttk.Combobox(
                    frame,
                    textvariable=sleeve_var,
                    state="readonly",
                    width=29,
                )
                label.pack(side="left", padx=(12, 5), before=transfer_button)
                combo.pack(side="left", before=transfer_button)
                owner._turto_decoder_transfer_sleeve_combo_224 = combo
            except Exception:
                pass

    if not getattr(owner, "_turto_substitution_sleeve_trace_224", False):
        target = getattr(owner, "shear_target_manufacturer_var", None)
        try:
            if target is not None and hasattr(target, "trace_add"):
                target.trace_add(
                    "write",
                    lambda *_a: _sync_substitution_sleeve_options(owner),
                )
            owner._turto_substitution_sleeve_trace_224 = True
        except Exception:
            pass

    _sync_substitution_sleeve_options(owner)


def init_shear_workspace(owner: Any) -> None:
    _current.init_shear_workspace(owner)


def build_shear_workspace(owner: Any, parent: ttk.Frame) -> None:
    _current.build_shear_workspace(owner, parent)
    _install_substitution_sleeve_controls(owner)


def _next_name(prefix: str, rows: list[dict[str, Any]]) -> str:
    used = {str(row.get("name", "") or "").strip() for row in rows}
    index = 1
    while f"{prefix}{index:03d}" in used:
        index += 1
    return f"{prefix}{index:03d}"


def _recompute_substitution_row(
    row: dict[str, Any],
    target: str,
    low_sleeve: str,
) -> dict[str, Any]:
    data = dict(row)
    data["target_manufacturer"] = target
    data["low_sleeve"] = low_sleeve
    try:
        return _stable._substitution_from_values(data, target)
    except Exception as exc:
        data["status"] = "NELZE"
        data["error"] = str(exc)
        return data


def decoder_to_substitution(self: Any) -> None:
    """Transfer selected Decoder row(s) while honoring the visible ED/ESD choice."""
    rows = getattr(self, "shear_substitution_rows", [])
    before = len(rows)
    _stable.decoder_to_substitution(self)

    rows = getattr(self, "shear_substitution_rows", [])
    if len(rows) <= before:
        return

    target = _target_name(self)
    low_sleeve = _selected_low_sleeve(self)
    for index in range(before, len(rows)):
        row = rows[index]
        if isinstance(row, dict):
            rows[index] = _recompute_substitution_row(row, target, low_sleeve)

    try:
        self.refresh_shear_tables()
    except Exception:
        pass


def sync_substitutions_from_decoder(self: Any) -> None:
    """Rebuild Decoder-origin rows using the selected sleeve preference."""
    _stable._prev.init_shear_workspace(self)
    decoder_rows = getattr(self, "shear_decoder_rows", [])
    if not decoder_rows:
        messagebox.showinfo(
            "Záměny smykových trnů",
            "Dekodér zatím neobsahuje žádné řádky.",
            parent=self,
        )
        return

    target = _target_name(self)
    low_sleeve = _selected_low_sleeve(self)

    substitution_rows = getattr(self, "shear_substitution_rows", [])
    manual = [
        deepcopy(row)
        for row in substitution_rows
        if isinstance(row, dict) and row.get("origin") != "decoder"
    ]
    synced: list[dict[str, Any]] = []

    values = getattr(self, "shear_substitution_vars", {})
    try:
        target_cover = int(values["cover"].get())
    except Exception:
        target_cover = 30

    for row in decoder_rows:
        if not isinstance(row, dict):
            continue
        try:
            _stable._enrich_decoder_row(row)
        except Exception:
            pass

        data = {
            "name": str(row.get("name", "") or _next_name("Z", manual + synced)),
            "quantity": int(row.get("quantity", 1) or 1),
            "source_designation": str(row.get("designation", "") or ""),
            "slab_mm": float(row.get("slab_mm", 0) or 0),
            "gap_mm": float(row.get("gap_mm", 0) or 0),
            "concrete": str(row.get("concrete", "C25/30") or "C25/30"),
            "cover_mm": target_cover,
            "low_sleeve": low_sleeve,
            "origin": "decoder",
        }
        synced.append(_recompute_substitution_row(data, target, low_sleeve))

    self.shear_substitution_rows = manual + synced
    try:
        _stable._prev._mark(self)
    except Exception:
        pass
    self.refresh_shear_tables()

    try:
        self.shear_substitution_vars["name"].set(
            _next_name("Z", self.shear_substitution_rows)
        )
    except Exception:
        pass
    try:
        self.shear_notebook.select(2)
    except Exception:
        pass


def install_methods(cls: Any) -> None:
    """Install the verified historical chain, then 2.2.24 substitution overrides."""
    if getattr(cls, "_turto_shear_224_installed", False):
        return

    _stable.install_methods(cls)
    _current.install_methods(cls)

    cls.shear_decoder_to_substitution = decoder_to_substitution
    cls.sync_shear_substitutions_from_decoder = sync_substitutions_from_decoder

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
    missing = [
        name for name in required if not callable(getattr(cls, name, None))
    ]
    if missing:
        raise RuntimeError(
            "Neúplná instalace smykových trnů; chybí metody: "
            + ", ".join(missing)
        )

    cls._turto_shear_224_installed = True


__all__ = (
    "ED_EXPLANATION",
    "build_shear_workspace",
    "init_shear_workspace",
    "install_methods",
)


def selftest() -> None:
    assert _low_sleeve_from_label("Plastové pouzdro (konektor ED)") == "plastic"
    assert _low_sleeve_from_label("Nerezové pouzdro (konektor ESD)") == "stainless"

    common = dict(
        ved=5.0,
        slab_mm=200.0,
        gap_mm=20.0,
        concrete="C25/30",
        application="new",
        cover_mm=30,
    )
    plastic, error = design_for_manufacturer(
        "Ancon", movement="axial", low_sleeve="plastic", **common
    )
    assert plastic, error
    assert " ED " in f" {plastic[0].designation} "

    stainless, error = design_for_manufacturer(
        "Ancon", movement="axial", low_sleeve="stainless", **common
    )
    assert stainless, error
    assert " ESD " in f" {stainless[0].designation} "

    transverse, error = design_for_manufacturer(
        "Ancon", movement="transverse", low_sleeve="plastic", **common
    )
    assert transverse, error
    assert " ESDQ " in f" {transverse[0].designation} "


if __name__ == "__main__":
    selftest()
