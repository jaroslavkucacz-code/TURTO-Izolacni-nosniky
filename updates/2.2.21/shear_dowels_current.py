from __future__ import annotations

"""TURTO 2.2.21 – precise Ancon ED terminology and derived design alternatives.

ED is the complete low-capacity Ancon connector using a durable plastic sleeve;
it is not the designation of the sleeve by itself.  The primary design remains
unchanged.  Additional fully passing candidates are derived from the same
manufacturer design function and are never persisted into actions.sqlite3.
"""

from typing import Any, Iterable
import tkinter as tk
from tkinter import ttk

import shear_ui_227 as _ui227
from shear_catalogs_227 import design_for_manufacturer

_ORIGINAL_BUILD = _ui227.build_shear_workspace
_ORIGINAL_INIT = _ui227.init_shear_workspace
_ORIGINAL_INSTALL = _ui227.install_methods
_ORIGINAL_ADD = _ui227.add_design
_ORIGINAL_RECALCULATE = _ui227.recalculate_design_all
_ORIGINAL_REFRESH = _ui227.refresh

ED_EXPLANATION = (
    "Ancon ED = kompletní nízkoúnosný smykový konektor: nerezový trn + odolné "
    "plastové pouzdro s přibíjecí destičkou. ED není označení samotného pouzdra."
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


def _movement_is_transverse(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return "příčný" in text or "pricny" in text or text in {"transverse", "q"}


def _sleeve_options(manufacturer: Any, movement: Any) -> tuple[str, ...]:
    label = str(manufacturer or "").strip().lower()
    if "ancon" in label:
        if _movement_is_transverse(movement):
            return ("Pouzdro pro příčný posun (konektor ESDQ)",)
        return (
            "Nerezové pouzdro (konektor ESD)",
            "Plastové pouzdro (konektor ED)",
        )
    return ("Nerezové pouzdro", "Plastové pouzdro")


def _candidate_dict(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, dict):
        return dict(candidate)
    converter = getattr(candidate, "as_dict", None)
    return dict(converter()) if callable(converter) else {}


def _passing_alternatives(candidates: Iterable[Any], primary_designation: Any) -> list[dict[str, Any]]:
    primary = str(primary_designation or "").strip()
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        data = _candidate_dict(candidate)
        designation = str(data.get("designation", "") or "").strip()
        status = str(data.get("status", "VYHOVUJE") or "VYHOVUJE").strip().upper()
        if not designation or designation == primary or designation in seen:
            continue
        if status != "VYHOVUJE":
            continue
        seen.add(designation)
        result.append(data)
    return result


def _fmt(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value):.{decimals}f}".replace(".", ",")
    except Exception:
        return "—"


def _design_tab(owner: Any):
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return None
    try:
        tabs = notebook.tabs()
        return notebook.nametowidget(tabs[1]) if len(tabs) > 1 else None
    except Exception:
        return None


def _find_sleeve_combo(owner: Any):
    tab = _design_tab(owner)
    values = getattr(owner, "shear_design_vars", {})
    variable = values.get("sleeve") if isinstance(values, dict) else None
    if tab is None or variable is None:
        return None
    name = str(variable)
    for widget in _walk(tab):
        try:
            if isinstance(widget, ttk.Combobox) and str(widget.cget("textvariable")) == name:
                return widget
        except Exception:
            pass
    return None


def _sync_sleeve_options(owner: Any, *_args: Any) -> None:
    values = getattr(owner, "shear_design_vars", {})
    if not isinstance(values, dict) or "sleeve" not in values or "movement" not in values:
        return
    manufacturer_var = getattr(owner, "shear_design_manufacturer_var", None)
    manufacturer = manufacturer_var.get() if manufacturer_var is not None else "Ancon"
    options = _sleeve_options(manufacturer, values["movement"].get())
    variable = values["sleeve"]
    current = str(variable.get() or "")
    combo = _find_sleeve_combo(owner)
    if combo is not None:
        try:
            combo.configure(values=options, width=max(18, min(36, max(map(len, options)) + 1)))
        except Exception:
            pass

    current_is_plastic = "plast" in current.lower()
    desired = next((item for item in options if ("plast" in item.lower()) == current_is_plastic), options[0])
    if current not in options:
        variable.set(desired)


def _install_ed_help(owner: Any) -> None:
    if getattr(owner, "_turto_ed_help_221", None) is not None:
        return
    tab = _design_tab(owner)
    if tab is None:
        return
    top = None
    try:
        for child in tab.winfo_children():
            info = child.grid_info()
            if isinstance(child, ttk.Frame) and int(info.get("row", -1)) == 0:
                top = child
                break
    except Exception:
        top = None
    if top is None:
        return
    label = ttk.Label(
        top,
        text=ED_EXPLANATION,
        style="MutedCard.TLabel",
        justify="left",
        wraplength=1450,
    )
    label.grid(row=3, column=0, sticky="w", pady=(8, 0))
    owner._turto_ed_help_221 = label


def _build_alternatives_panel(owner: Any) -> None:
    if getattr(owner, "shear_design_alternatives_tree", None) is not None:
        return
    tab = _design_tab(owner)
    if tab is None:
        return

    try:
        tab.rowconfigure(1, weight=3)
        tab.rowconfigure(2, weight=2)
    except Exception:
        pass

    card = ttk.Frame(tab, style="Card.TFrame", padding=(10, 8, 10, 8))
    card.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
    card.columnconfigure(0, weight=1)
    card.rowconfigure(2, weight=1)

    ttk.Label(card, text="Další vyhovující alternativy", style="Card.TLabel", font=("Calibri", 10, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    owner.shear_design_alternatives_status = tk.StringVar(
        master=owner,
        value="Vyberte řádek návrhu. Zobrazí se další plně vyhovující typy podle stejných vstupů.",
    )
    ttk.Label(
        card,
        textvariable=owner.shear_design_alternatives_status,
        style="MutedCard.TLabel",
        justify="left",
        wraplength=1450,
    ).grid(row=1, column=0, sticky="ew", pady=(2, 6))

    frame = ttk.Frame(card, style="Card.TFrame")
    frame.grid(row=2, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    columns = ("manufacturer", "designation", "vrd", "util", "h", "gap", "source", "note")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=5, style="Data.Treeview")
    headings = (
        "Výrobce", "Alternativní trn", "VRd [kN]", "Využití", "h tab. [mm]",
        "Spára tab. [mm]", "Zdroj", "Poznámka",
    )
    widths = (105, 300, 85, 80, 95, 105, 130, 460)
    anchors = {"designation": "w", "source": "w", "note": "w"}
    for column, heading, width in zip(columns, headings, widths):
        anchor = anchors.get(column, "center")
        tree.heading(column, text=heading, anchor=anchor)
        tree.column(column, width=width, anchor=anchor, stretch=column in {"designation", "note"})
    ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
    tree.grid(row=0, column=0, sticky="nsew")
    ybar.grid(row=0, column=1, sticky="ns")
    xbar.grid(row=1, column=0, sticky="ew")
    owner.shear_design_alternatives_tree = tree

    primary = getattr(owner, "shear_design_tree", None)
    if primary is not None:
        primary.bind("<<TreeviewSelect>>", lambda _event: _refresh_alternatives(owner), add="+")


def _row_candidates(row: dict[str, Any], fallback_manufacturer: str) -> tuple[list[Any], str]:
    manufacturer = str(row.get("manufacturer") or fallback_manufacturer or "Ancon")
    try:
        return design_for_manufacturer(
            manufacturer,
            ved=abs(float(row.get("ved", 0) or 0)),
            slab_mm=float(row.get("slab_mm", 0) or 0),
            gap_mm=float(row.get("gap_mm", 0) or 0),
            concrete=str(row.get("concrete", "C25/30") or "C25/30"),
            movement=str(row.get("movement", "axial") or "axial"),
            application=str(row.get("application", "new") or "new"),
            low_sleeve=str(row.get("low_sleeve", "stainless") or "stainless"),
            cover_mm=int(row.get("cover_mm", 30) or 30),
        )
    except Exception as exc:
        return [], str(exc)


def _selected_design_index(owner: Any) -> int | None:
    tree = getattr(owner, "shear_design_tree", None)
    if tree is None:
        return None
    try:
        selection = tree.selection()
        if not selection:
            return None
        index = int(selection[0])
        rows = getattr(owner, "shear_design_rows", [])
        return index if 0 <= index < len(rows) else None
    except Exception:
        return None


def _refresh_alternatives(owner: Any) -> None:
    tree = getattr(owner, "shear_design_alternatives_tree", None)
    status_var = getattr(owner, "shear_design_alternatives_status", None)
    if tree is None:
        return
    try:
        for iid in tree.get_children(""):
            tree.delete(iid)
    except Exception:
        return

    index = _selected_design_index(owner)
    if index is None:
        if status_var is not None:
            status_var.set("Vyberte řádek návrhu. Zobrazí se další plně vyhovující typy podle stejných vstupů.")
        return

    row = owner.shear_design_rows[index]
    primary = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
    primary_designation = str(primary.get("designation", "") or "")
    manufacturer_var = getattr(owner, "shear_design_manufacturer_var", None)
    fallback = manufacturer_var.get() if manufacturer_var is not None else "Ancon"
    candidates, error = _row_candidates(row, fallback)
    alternatives = _passing_alternatives(candidates, primary_designation)

    for pos, candidate in enumerate(alternatives):
        source = str(candidate.get("manufacturer", row.get("manufacturer", "")) or "")
        page = str(candidate.get("page", "") or "")
        source_text = source + (f" p.{page}" if page else "")
        tree.insert(
            "",
            "end",
            iid=str(pos),
            values=(
                candidate.get("manufacturer", row.get("manufacturer", "")),
                candidate.get("designation", ""),
                _fmt(candidate.get("vrd")),
                _fmt(float(candidate.get("utilization", 0) or 0) * 100) + " %",
                _fmt(candidate.get("slab_table_mm"), 0),
                _fmt(candidate.get("gap_table_mm"), 0),
                source_text,
                candidate.get("note", ""),
            ),
        )

    if status_var is not None:
        if alternatives:
            status_var.set(
                f"{len(alternatives)} dalších plně vyhovujících alternativ pro {primary_designation or 'vybraný řádek'}. "
                "Typy se pouze dopočítávají a neukládají se do databáze AKCÍ."
            )
        elif error:
            status_var.set(f"Další alternativy nelze určit: {error}")
        else:
            status_var.set("Pro vybraný řádek nebyla nalezena další plně vyhovující alternativa.")


def init_shear_workspace(owner: Any) -> None:
    _ORIGINAL_INIT(owner)


def build_shear_workspace(owner: Any, parent: ttk.Frame) -> None:
    _ORIGINAL_BUILD(owner, parent)
    _install_ed_help(owner)
    _build_alternatives_panel(owner)
    _sync_sleeve_options(owner)

    if not getattr(owner, "_turto_sleeve_traces_221", False):
        manufacturer = getattr(owner, "shear_design_manufacturer_var", None)
        values = getattr(owner, "shear_design_vars", {})
        try:
            if manufacturer is not None and hasattr(manufacturer, "trace_add"):
                manufacturer.trace_add("write", lambda *_a: _sync_sleeve_options(owner))
            movement = values.get("movement") if isinstance(values, dict) else None
            if movement is not None and hasattr(movement, "trace_add"):
                movement.trace_add("write", lambda *_a: _sync_sleeve_options(owner))
            owner._turto_sleeve_traces_221 = True
        except Exception:
            pass


def add_design(self: Any) -> None:
    before = len(getattr(self, "shear_design_rows", []))
    _ORIGINAL_ADD(self)
    rows = getattr(self, "shear_design_rows", [])
    tree = getattr(self, "shear_design_tree", None)
    if tree is not None and len(rows) > before:
        iid = str(len(rows) - 1)
        try:
            tree.selection_set(iid)
            tree.focus(iid)
            tree.see(iid)
        except Exception:
            pass
    _refresh_alternatives(self)


def recalculate_design_all(self: Any) -> None:
    _ORIGINAL_RECALCULATE(self)
    _refresh_alternatives(self)


def refresh(self: Any) -> None:
    tree = getattr(self, "shear_design_tree", None)
    selected = None
    if tree is not None:
        try:
            selection = tree.selection()
            selected = selection[0] if selection else None
        except Exception:
            selected = None
    _ORIGINAL_REFRESH(self)
    tree = getattr(self, "shear_design_tree", None)
    if tree is not None and selected is not None:
        try:
            if tree.exists(selected):
                tree.selection_set(selected)
                tree.focus(selected)
        except Exception:
            pass
    _refresh_alternatives(self)


def install_methods(cls: Any) -> None:
    if getattr(cls, "_turto_shear_221_installed", False):
        return
    _ORIGINAL_INSTALL(cls)
    cls.add_shear_design_row = add_design
    cls.recalculate_shear_design_all = recalculate_design_all
    cls.refresh_shear_tables = refresh
    cls._turto_shear_221_installed = True


# Patch the public four-manufacturer layer before platform_workspace imports its
# symbols.  This keeps the stable shear_dowels_current boundary useful and
# avoids another platform wrapper solely for a UI enhancement.
_ui227.build_shear_workspace = build_shear_workspace
_ui227.init_shear_workspace = init_shear_workspace
_ui227.install_methods = install_methods


__all__ = ("build_shear_workspace", "init_shear_workspace", "install_methods")


def selftest() -> None:
    assert "ED není označení samotného pouzdra" in ED_EXPLANATION
    assert _sleeve_options("Ancon", "Podélný posun") == (
        "Nerezové pouzdro (konektor ESD)",
        "Plastové pouzdro (konektor ED)",
    )
    assert _sleeve_options("Ancon", "Podélný + příčný posun") == (
        "Pouzdro pro příčný posun (konektor ESDQ)",
    )
    sample = [
        {"designation": "A", "status": "VYHOVUJE"},
        {"designation": "B", "status": "VYHOVUJE"},
        {"designation": "C", "status": "KONTROLA DESKY"},
        {"designation": "B", "status": "VYHOVUJE"},
    ]
    assert [item["designation"] for item in _passing_alternatives(sample, "A")] == ["B"]


if __name__ == "__main__":
    selftest()
