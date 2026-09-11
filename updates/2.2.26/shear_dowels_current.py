from __future__ import annotations

"""TURTO 2.2.26 – responsive shear-dowel workspace.

The 2.2.25 layout restored the manual design form, but the form still used one
very wide row. At common Windows scaling the final action button could be
clipped. This layer keeps the 2.2.25 calculation/model chain unchanged and
rebuilds only dense input/tool rows into width-safe two-line layouts.
"""

from typing import Any
from tkinter import ttk

import shear_dowels_current_225 as _base
import shear_ui_227 as _ui227

ED_EXPLANATION = _base.ED_EXPLANATION
FORM_LAYOUT_REVISION = 2
RESPONSIVE_TABS = ("decoder", "design", "substitution")


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _tab(owner: Any, index: int):
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return None
    try:
        tabs = notebook.tabs()
        return notebook.nametowidget(tabs[index]) if len(tabs) > index else None
    except Exception:
        return None


def _find_button(root: Any, text: str):
    if root is None:
        return None
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
                return widget
        except Exception:
            pass
    return None


def _combo_values(frame: Any, variable: Any, fallback: tuple[str, ...] = ()) -> tuple[str, ...]:
    name = str(variable)
    for widget in _walk(frame):
        try:
            if isinstance(widget, ttk.Combobox) and str(widget.cget("textvariable")) == name:
                values = tuple(str(item) for item in widget.cget("values"))
                return values or fallback
        except Exception:
            pass
    return fallback


def _clear(frame: Any) -> None:
    for child in list(frame.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass
    for column in range(20):
        try:
            frame.columnconfigure(column, weight=0, minsize=0)
        except Exception:
            pass
    for row in range(4):
        try:
            frame.rowconfigure(row, weight=0, minsize=0)
        except Exception:
            pass


def _entry(parent: Any, variable: Any, width: int) -> ttk.Entry:
    return ttk.Entry(parent, textvariable=variable, width=width)


def _combo(parent: Any, variable: Any, values: tuple[str, ...], width: int) -> ttk.Combobox:
    return ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=width)


def _field_pair(parent: Any, *, column: int, label: str, widget: Any, padx: tuple[int, int] = (4, 12)) -> int:
    ttk.Label(parent, text=label, style="Card.TLabel").grid(row=0, column=column, sticky="w")
    widget.grid(row=0, column=column + 1, sticky="ew", padx=padx)
    return column + 2


def _two_lines(frame: Any) -> tuple[ttk.Frame, ttk.Frame]:
    _clear(frame)
    frame.columnconfigure(0, weight=1)
    line1 = ttk.Frame(frame, style="Card.TFrame")
    line2 = ttk.Frame(frame, style="Card.TFrame")
    line1.grid(row=0, column=0, sticky="ew")
    line2.grid(row=1, column=0, sticky="ew", pady=(8, 0))
    return line1, line2


def _rebuild_decoder_form(owner: Any) -> None:
    tab = _tab(owner, 0)
    button = _find_button(tab, "Dekódovat a přidat")
    if button is None:
        return
    frame = button.master
    values = getattr(owner, "shear_decoder_vars", {})
    if not isinstance(values, dict):
        return

    concrete_values = _combo_values(
        frame, values.get("concrete"), ("C20/25", "C25/30", "C30/37", "C35/45", "C40/50")
    )
    line1, line2 = _two_lines(frame)
    line1.columnconfigure(5, weight=1)

    col = 0
    col = _field_pair(line1, column=col, label="Pozice", widget=_entry(line1, values["name"], 8))
    col = _field_pair(line1, column=col, label="Ks", widget=_entry(line1, values["qty"], 5))
    ttk.Label(line1, text="Označení", style="Card.TLabel").grid(row=0, column=col, sticky="w")
    designation = _entry(line1, values["designation"], 34)
    designation.grid(row=0, column=col + 1, sticky="ew", padx=(4, 12))
    line1.columnconfigure(col + 1, weight=1)
    ttk.Button(
        line1, text="Dekódovat a přidat", style="Accent.TButton", command=owner.add_shear_decoder_row
    ).grid(row=0, column=col + 2, sticky="e")

    col = 0
    col = _field_pair(line2, column=col, label="h [mm]", widget=_entry(line2, values["slab"], 8))
    col = _field_pair(line2, column=col, label="Spára [mm]", widget=_entry(line2, values["gap"], 9))
    _field_pair(
        line2, column=col, label="Beton", widget=_combo(line2, values["concrete"], concrete_values, 10)
    )
    owner._turto_decoder_form_226 = frame


def _rebuild_design_form(owner: Any) -> None:
    tab = _tab(owner, 1)
    button = _find_button(tab, "Navrhnout a přidat")
    if button is None:
        return
    frame = button.master
    values = getattr(owner, "shear_design_vars", {})
    if not isinstance(values, dict):
        return

    concrete_values = _combo_values(frame, values.get("concrete"), ("C25/30", "C30/37", "C35/45", "C40/50"))
    movement_values = _combo_values(frame, values.get("movement"))
    application_values = _combo_values(frame, values.get("application"))
    sleeve_values = _combo_values(frame, values.get("sleeve"))
    line1, line2 = _two_lines(frame)

    col = 0
    col = _field_pair(line1, column=col, label="Pozice", widget=_entry(line1, values["name"], 8))
    col = _field_pair(line1, column=col, label="Ks", widget=_entry(line1, values["qty"], 5))
    col = _field_pair(line1, column=col, label="VEd [kN/trn]", widget=_entry(line1, values["ved"], 10))
    col = _field_pair(line1, column=col, label="h [mm]", widget=_entry(line1, values["slab"], 8))
    col = _field_pair(line1, column=col, label="Spára [mm]", widget=_entry(line1, values["gap"], 9))
    _field_pair(
        line1, column=col, label="Beton", widget=_combo(line1, values["concrete"], concrete_values, 10), padx=(4, 0)
    )

    for column in (1, 3, 5):
        line2.columnconfigure(column, weight=1)
    ttk.Label(line2, text="Pohyb", style="Card.TLabel").grid(row=0, column=0, sticky="w")
    _combo(line2, values["movement"], movement_values, 22).grid(row=0, column=1, sticky="ew", padx=(4, 14))
    ttk.Label(line2, text="Aplikace", style="Card.TLabel").grid(row=0, column=2, sticky="w")
    _combo(line2, values["application"], application_values, 23).grid(row=0, column=3, sticky="ew", padx=(4, 14))
    ttk.Label(line2, text="Varianta Ancon", style="Card.TLabel").grid(row=0, column=4, sticky="w")
    sleeve = _combo(line2, values["sleeve"], sleeve_values, 30)
    sleeve.grid(row=0, column=5, sticky="ew", padx=(4, 14))
    ttk.Button(
        line2, text="Navrhnout a přidat", style="Accent.TButton", command=owner.add_shear_design_row
    ).grid(row=0, column=6, sticky="e")
    owner._turto_design_form_226 = frame


def _rebuild_substitution_form(owner: Any) -> None:
    tab = _tab(owner, 2)
    button = _find_button(tab, "Navrhnout záměnu")
    if button is None:
        return
    frame = button.master
    values = getattr(owner, "shear_substitution_vars", {})
    if not isinstance(values, dict):
        return

    concrete_values = _combo_values(frame, values.get("concrete"), ("C25/30", "C30/37", "C35/45", "C40/50"))
    cover_values = _combo_values(frame, values.get("cover"), ("20", "30"))
    sleeve_values = _combo_values(frame, values.get("sleeve"))
    line1, line2 = _two_lines(frame)
    line1.columnconfigure(5, weight=1)

    col = 0
    col = _field_pair(line1, column=col, label="Pozice", widget=_entry(line1, values["name"], 8))
    col = _field_pair(line1, column=col, label="Ks", widget=_entry(line1, values["qty"], 5))
    ttk.Label(line1, text="Původní trn", style="Card.TLabel").grid(row=0, column=col, sticky="w")
    source = _entry(line1, values["source"], 28)
    source.grid(row=0, column=col + 1, sticky="ew", padx=(4, 12))
    line1.columnconfigure(col + 1, weight=1)
    col += 2
    col = _field_pair(line1, column=col, label="h [mm]", widget=_entry(line1, values["slab"], 8))
    col = _field_pair(line1, column=col, label="Spára [mm]", widget=_entry(line1, values["gap"], 9))
    _field_pair(
        line1, column=col, label="Beton", widget=_combo(line1, values["concrete"], concrete_values, 10), padx=(4, 0)
    )

    line2.columnconfigure(3, weight=1)
    ttk.Label(line2, text="cnom Schöck", style="Card.TLabel").grid(row=0, column=0, sticky="w")
    _combo(line2, values["cover"], cover_values, 7).grid(row=0, column=1, sticky="w", padx=(4, 14))
    ttk.Label(line2, text="Varianta Ancon", style="Card.TLabel").grid(row=0, column=2, sticky="w")
    sleeve = _combo(line2, values["sleeve"], sleeve_values, 30)
    sleeve.grid(row=0, column=3, sticky="ew", padx=(4, 14))
    ttk.Button(
        line2, text="Navrhnout záměnu", style="Accent.TButton", command=owner.add_shear_substitution_row
    ).grid(row=0, column=4, sticky="e")
    owner._turto_substitution_sleeve_combo_224 = sleeve
    owner._turto_substitution_form_226 = frame


def _rebuild_decoder_toolbar(owner: Any) -> None:
    tab = _tab(owner, 0)
    anchor = _find_button(tab, "Hromadné dekódování z výkazu…")
    if anchor is None:
        return
    frame = anchor.master
    _clear(frame)
    frame.columnconfigure(3, weight=1)
    ttk.Button(
        frame, text="Hromadné dekódování z výkazu…", style="Accent.TButton", command=owner.open_shear_decoder_schedule
    ).grid(row=0, column=0)
    ttk.Button(frame, text="Kopírovat pro Excel", command=lambda: owner.copy_shear_table("decoder")).grid(
        row=0, column=1, padx=(7, 0)
    )
    ttk.Button(frame, text="Vymazat vše", command=lambda: owner.clear_shear_kind("decoder")).grid(
        row=0, column=2, padx=(7, 0)
    )
    ttk.Label(
        frame,
        text="Dekódované řádky, návrhy a záměny se ukládají společně v centrální AKCI.",
        style="Muted.TLabel",
        justify="left",
        wraplength=1200,
    ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))


def _rebuild_decoder_transfer(owner: Any) -> None:
    tab = _tab(owner, 0)
    anchor = _find_button(tab, "Převést do Záměn")
    values = getattr(owner, "shear_substitution_vars", {})
    if anchor is None or not isinstance(values, dict) or values.get("sleeve") is None:
        return
    frame = anchor.master
    target_values = _combo_values(
        frame, getattr(owner, "shear_target_manufacturer_var", None), ("Ancon", "Schöck", "PohlCon", "MAX FRANK")
    )
    sleeve_values = _combo_values(
        frame,
        values["sleeve"],
        ("Nerezové pouzdro (konektor ESD)", "Plastové pouzdro (konektor ED)"),
    )
    _clear(frame)
    frame.columnconfigure(3, weight=1)
    ttk.Label(
        frame, text="Záměna vybraného řádku:", style="Card.TLabel", font=("Calibri", 10, "bold")
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text="Cílový výrobce", style="MutedCard.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 5))
    _combo(frame, owner.shear_target_manufacturer_var, target_values, 14).grid(row=0, column=2, sticky="w")
    ttk.Label(frame, text="Varianta Ancon", style="MutedCard.TLabel").grid(row=0, column=3, sticky="e", padx=(14, 5))
    sleeve = _combo(frame, values["sleeve"], sleeve_values, 30)
    sleeve.grid(row=0, column=4, sticky="e")
    ttk.Button(
        frame, text="Převést do Záměn", style="Accent.TButton", command=owner.shear_decoder_to_substitution
    ).grid(row=0, column=5, sticky="e", padx=(8, 0))
    ttk.Label(frame, text="Dvojklik na řádek provede stejný převod.", style="MutedCard.TLabel").grid(
        row=1, column=0, columnspan=6, sticky="w", pady=(6, 0)
    )
    owner._turto_decoder_transfer_sleeve_combo_224 = sleeve


def _rebuild_substitution_toolbar(owner: Any) -> None:
    tab = _tab(owner, 2)
    anchor = _find_button(tab, "Aktualizovat z Dekodéru")
    values = getattr(owner, "shear_substitution_vars", {})
    if anchor is None or not isinstance(values, dict) or values.get("sleeve") is None:
        return
    frame = anchor.master
    target_values = _combo_values(frame, owner.shear_target_manufacturer_var, ("Ancon", "Schöck", "PohlCon", "MAX FRANK"))
    sleeve_values = _combo_values(
        frame,
        values["sleeve"],
        ("Nerezové pouzdro (konektor ESD)", "Plastové pouzdro (konektor ED)"),
    )
    _clear(frame)
    frame.columnconfigure(3, weight=1)
    ttk.Label(
        frame, text="Cílový výrobce:", style="Card.TLabel", font=("Calibri", 10, "bold")
    ).grid(row=0, column=0, sticky="w")
    _combo(frame, owner.shear_target_manufacturer_var, target_values, 14).grid(
        row=0, column=1, sticky="w", padx=(5, 14)
    )
    ttk.Label(frame, text="Varianta Ancon:", style="Card.TLabel").grid(row=0, column=2, sticky="e")
    sleeve = _combo(frame, values["sleeve"], sleeve_values, 30)
    sleeve.grid(row=0, column=3, sticky="e", padx=(5, 0))
    ttk.Button(
        frame, text="Aktualizovat z Dekodéru", style="Accent.TButton", command=owner.sync_shear_substitutions_from_decoder
    ).grid(row=1, column=0, pady=(8, 0), sticky="w")
    ttk.Button(frame, text="Přepočítat vše", command=owner.recalculate_shear_substitutions).grid(
        row=1, column=1, padx=(7, 0), pady=(8, 0), sticky="w"
    )
    ttk.Button(frame, text="Vymazat vše", command=lambda: owner.clear_shear_kind("substitution")).grid(
        row=1, column=2, padx=(7, 0), pady=(8, 0), sticky="w"
    )
    ttk.Button(frame, text="Kopírovat výsledky", command=lambda: owner.copy_shear_table("substitution")).grid(
        row=1, column=3, padx=(7, 0), pady=(8, 0), sticky="w"
    )
    owner._turto_substitution_sleeve_combo_224 = sleeve


def _make_shear_ui_responsive(owner: Any) -> None:
    _rebuild_decoder_toolbar(owner)
    _rebuild_decoder_form(owner)
    _rebuild_design_form(owner)
    _rebuild_substitution_form(owner)
    _rebuild_decoder_transfer(owner)
    _rebuild_substitution_toolbar(owner)
    owner._turto_shear_responsive_226 = True


def init_shear_workspace(owner: Any) -> None:
    _base.init_shear_workspace(owner)


def build_shear_workspace(owner: Any, parent: ttk.Frame) -> None:
    _base.build_shear_workspace(owner, parent)
    _make_shear_ui_responsive(owner)


def install_methods(cls: Any) -> None:
    if getattr(cls, "_turto_shear_226_installed", False):
        return
    _base.install_methods(cls)
    cls._turto_shear_226_installed = True


_ui227.build_shear_workspace = build_shear_workspace
_ui227.init_shear_workspace = init_shear_workspace
_ui227.install_methods = install_methods

__all__ = ("ED_EXPLANATION", "build_shear_workspace", "init_shear_workspace", "install_methods")


def selftest() -> None:
    assert FORM_LAYOUT_REVISION == 2
    assert RESPONSIVE_TABS == ("decoder", "design", "substitution")
    assert callable(_rebuild_design_form)
    assert callable(_rebuild_substitution_form)


if __name__ == "__main__":
    selftest()
