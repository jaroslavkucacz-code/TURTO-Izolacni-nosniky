from __future__ import annotations

"""TURTO 2.1.4 – sjednocené UI smykových trnů.

Pracovní postup kopíruje principy oblasti Izolační nosníky:
Dekodér / Návrh / Záměny, hromadné vložení z výkazu, společné akce nad řádky,
filtr a převod Dekodér -> Záměny. Výpočtové jádro 2.1.0 se nemění.
"""

from copy import deepcopy
from typing import Any
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import shear_dowels_ui as _base
from shear_dowels_catalog import design_ancon, propose_substitution
from shear_dowels_schedule import ShearScheduleDialog


CONCRETES = ("C25/30", "C30/37", "C35/45", "C40/50")
MOVEMENTS = ("Podélný posun", "Podélný + příčný posun")
APPLICATIONS = ("Nová konstrukce", "Stávající betonová stěna")
LOW_SLEEVES = ("Nerezová objímka", "Plastová objímka")
TARGETS = ("Ancon", "Schöck")
COVERS = ("20", "30")


def _movement_code(text: str) -> str:
    return "transverse" if "příčný" in str(text).lower() else "axial"


def _movement_label(code: str) -> str:
    return "Podélný + příčný posun" if str(code) == "transverse" else "Podélný posun"


def _application_code(text: str) -> str:
    return "existing_wall" if "stávající" in str(text).lower() else "new"


def _application_label(code: str) -> str:
    return "Stávající betonová stěna" if str(code) == "existing_wall" else "Nová konstrukce"


def _sleeve_code(text: str) -> str:
    return "plastic" if "plast" in str(text).lower() else "stainless"


def _sleeve_label(code: str) -> str:
    return "Plastová objímka" if str(code) == "plastic" else "Nerezová objímka"


def _qty(value: Any) -> int:
    q = int(str(value or "1").strip())
    if not 1 <= q <= 1_000_000:
        raise ValueError("Ks musí být celé číslo 1–1 000 000.")
    return q


def _f(value: Any) -> float:
    return float(str(value or "").strip().replace("−", "-").replace(",", "."))


def _fmt(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value):.{decimals}f}".replace(".", ",")
    except Exception:
        return "—"


def _mark(owner: Any) -> None:
    if not getattr(owner, "_action_loading", False) and hasattr(owner, "mark_project_dirty"):
        owner.mark_project_dirty()


def _next(prefix: str, rows: list[dict[str, Any]]) -> str:
    used = {str(row.get("name", "")).strip() for row in rows}
    index = 1
    while f"{prefix}{index:03d}" in used:
        index += 1
    return f"{prefix}{index:03d}"


def init_shear_workspace(owner: Any) -> None:
    if not hasattr(owner, "shear_decoder_rows"):
        owner.shear_decoder_rows = []
    if not hasattr(owner, "shear_design_rows"):
        owner.shear_design_rows = []
    if not hasattr(owner, "shear_substitution_rows"):
        owner.shear_substitution_rows = []
    if not hasattr(owner, "shear_target_manufacturer_var"):
        owner.shear_target_manufacturer_var = tk.StringVar(master=owner, value="Schöck")


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _header(parent: ttk.Frame, title: str, subtitle: str, status_var: tk.StringVar) -> ttk.Frame:
    parent.columnconfigure(0, weight=1)
    head = ttk.Frame(parent, style="Card.TFrame", padding=(14, 10))
    head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    head.columnconfigure(1, weight=1)
    ttk.Label(head, text=title, style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(head, textvariable=status_var, style="MutedCard.TLabel").grid(row=0, column=2, sticky="e")
    ttk.Label(
        head,
        text=subtitle,
        style="MutedCard.TLabel",
        wraplength=1250,
        justify="left",
    ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(3, 0))
    return head


def _tree(
    parent: ttk.Frame,
    *,
    row: int,
    columns: tuple[str, ...],
    headings: tuple[str, ...],
    widths: tuple[int, ...],
    anchors: dict[str, str] | None = None,
) -> ttk.Treeview:
    frame = ttk.Frame(parent, style="Card.TFrame", padding=(8, 8, 8, 6))
    frame.grid(row=row, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    tree = ttk.Treeview(
        frame,
        columns=columns,
        show="headings",
        selectmode="extended",
        style="Data.Treeview",
    )
    ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
    tree.grid(row=0, column=0, sticky="nsew")
    ybar.grid(row=0, column=1, sticky="ns")
    xbar.grid(row=1, column=0, sticky="ew")
    anchors = anchors or {}
    for column, heading, width in zip(columns, headings, widths):
        anchor = anchors.get(column, "center")
        tree.heading(column, text=heading, anchor=anchor)
        tree.column(
            column,
            width=width,
            minwidth=45,
            anchor=anchor,
            stretch=column in {"designation", "source", "target", "note", "error"},
        )
    return tree


def _filter_matches(row: dict[str, Any], text: str) -> bool:
    query = str(text or "").strip().lower()
    if not query:
        return True
    return query in str(row).lower()


def _selected_indices(tree: ttk.Treeview | None) -> list[int]:
    if tree is None:
        return []
    out: list[int] = []
    for iid in tree.selection():
        try:
            out.append(int(iid))
        except Exception:
            pass
    return sorted(set(out))


def _rows_for_kind(owner: Any, kind: str) -> tuple[list[dict[str, Any]], ttk.Treeview | None, str]:
    mapping = {
        "decoder": ("shear_decoder_rows", "shear_decoder_tree", "S"),
        "design": ("shear_design_rows", "shear_design_tree", "N"),
        "substitution": ("shear_substitution_rows", "shear_substitution_tree", "Z"),
    }
    rows_attr, tree_attr, prefix = mapping[kind]
    return getattr(owner, rows_attr), getattr(owner, tree_attr, None), prefix


def _row_actions(owner: Any, parent: ttk.Frame, *, row: int, kind: str, filter_var: tk.StringVar) -> None:
    bar = ttk.Frame(parent, style="App.TFrame")
    bar.grid(row=row, column=0, sticky="ew", pady=(0, 8))
    bar.columnconfigure(7, weight=1)
    ttk.Button(bar, text="Upravit pozici / ks", command=lambda: owner.shear_edit_meta(kind)).grid(row=0, column=0)
    ttk.Button(bar, text="Duplikovat", command=lambda: owner.shear_duplicate_selected(kind)).grid(row=0, column=1, padx=(7, 0))
    ttk.Button(bar, text="Nahoru", command=lambda: owner.shear_move_selected(kind, -1)).grid(row=0, column=2, padx=(7, 0))
    ttk.Button(bar, text="Dolů", command=lambda: owner.shear_move_selected(kind, 1)).grid(row=0, column=3, padx=(7, 0))
    ttk.Button(bar, text="Smazat", command=lambda: owner.shear_delete_selected(kind)).grid(row=0, column=4, padx=(7, 0))
    ttk.Label(bar, text="Filtr", style="Muted.TLabel").grid(row=0, column=8, padx=(14, 4))
    entry = ttk.Entry(bar, textvariable=filter_var, width=28)
    entry.grid(row=0, column=9)
    entry.bind("<KeyRelease>", lambda _event: owner.refresh_shear_tables())
    ttk.Button(bar, text="×", width=3, command=lambda: (filter_var.set(""), owner.refresh_shear_tables())).grid(row=0, column=10, padx=(5, 0))


def build_decoder(owner: Any, parent: ttk.Frame) -> None:
    parent.rowconfigure(5, weight=1)
    owner.shear_decoder_status_var = tk.StringVar(master=owner, value="0 řádků • 0 ks")
    owner.shear_decoder_filter_var = tk.StringVar(master=owner, value="")
    _header(
        parent,
        "Dekodér smykových trnů",
        "Stejně jako u izolačních nosníků lze zadávat jednotlivě nebo hromadně z výkazu. Geometrie zůstává s řádkem pro pozdější Záměny.",
        owner.shear_decoder_status_var,
    )

    toolbar = ttk.Frame(parent, style="App.TFrame")
    toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    toolbar.columnconfigure(5, weight=1)
    ttk.Button(toolbar, text="Hromadné dekódování z výkazu…", command=owner.open_shear_decoder_schedule).grid(row=0, column=0)
    ttk.Button(toolbar, text="Kopírovat pro Excel", command=lambda: owner.copy_shear_table("decoder")).grid(row=0, column=1, padx=(7, 0))
    ttk.Button(toolbar, text="Vymazat vše", command=lambda: owner.clear_shear_kind("decoder")).grid(row=0, column=2, padx=(7, 0))
    ttk.Label(
        toolbar,
        text="Dekódované řádky, návrhy a záměny se ukládají společně v centrální AKCI.",
        style="Muted.TLabel",
    ).grid(row=0, column=6, sticky="e")

    quick = ttk.Frame(parent, style="Card.TFrame", padding=(12, 9))
    quick.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    values = {
        "name": tk.StringVar(master=owner, value=_next("S", owner.shear_decoder_rows)),
        "qty": tk.StringVar(master=owner, value="1"),
        "designation": tk.StringVar(master=owner, value=""),
        "slab": tk.StringVar(master=owner, value="200"),
        "gap": tk.StringVar(master=owner, value="20"),
        "concrete": tk.StringVar(master=owner, value="C25/30"),
        "cover": tk.StringVar(master=owner, value="30"),
    }
    owner.shear_decoder_vars = values
    column = 0
    for label, key, width in (
        ("Pozice", "name", 8),
        ("Ks", "qty", 5),
        ("Označení", "designation", 34),
        ("h [mm]", "slab", 8),
        ("Spára [mm]", "gap", 9),
    ):
        ttk.Label(quick, text=label, style="Card.TLabel").grid(row=0, column=column, sticky="w")
        column += 1
        ttk.Entry(quick, textvariable=values[key], width=width).grid(row=0, column=column, padx=(4, 10))
        column += 1
    ttk.Label(quick, text="Beton", style="Card.TLabel").grid(row=0, column=column)
    column += 1
    ttk.Combobox(quick, textvariable=values["concrete"], values=CONCRETES, state="readonly", width=9).grid(row=0, column=column, padx=(4, 10))
    column += 1
    ttk.Label(quick, text="cnom Schöck", style="Card.TLabel").grid(row=0, column=column)
    column += 1
    ttk.Combobox(quick, textvariable=values["cover"], values=COVERS, state="readonly", width=5).grid(row=0, column=column, padx=(4, 10))
    column += 1
    ttk.Button(quick, text="Dekódovat a přidat", style="Accent.TButton", command=owner.add_shear_decoder_row).grid(row=0, column=column)

    transfer = ttk.Frame(parent, style="Card.TFrame", padding=(12, 8))
    transfer.grid(row=3, column=0, sticky="ew", pady=(0, 8))
    ttk.Label(transfer, text="Záměna vybraného řádku:", style="Card.TLabel", font=("Calibri", 10, "bold")).pack(side="left")
    ttk.Label(transfer, text="zaměnit za", style="MutedCard.TLabel").pack(side="left", padx=(12, 5))
    ttk.Combobox(transfer, textvariable=owner.shear_target_manufacturer_var, values=TARGETS, state="readonly", width=12).pack(side="left")
    ttk.Button(transfer, text="Převést do Záměn", style="Accent.TButton", command=owner.shear_decoder_to_substitution).pack(side="left", padx=(8, 0))
    ttk.Label(transfer, text="Dvojklik na řádek provede stejný převod.", style="MutedCard.TLabel").pack(side="left", padx=(12, 0))

    _row_actions(owner, parent, row=4, kind="decoder", filter_var=owner.shear_decoder_filter_var)
    columns = ("name", "qty", "manufacturer", "family", "size", "movement", "designation", "slab", "gap", "concrete")
    owner.shear_decoder_tree = _tree(
        parent,
        row=5,
        columns=columns,
        headings=("Pozice", "Ks", "Výrobce", "Typ", "Velikost", "Pohyb", "Označení", "h [mm]", "Spára [mm]", "Beton"),
        widths=(80, 50, 100, 100, 75, 150, 320, 80, 90, 90),
        anchors={"name": "w", "designation": "w"},
    )
    owner.shear_decoder_tree.bind("<Double-1>", lambda _event: owner.after_idle(owner.shear_decoder_to_substitution))


def build_design(owner: Any, parent: ttk.Frame) -> None:
    parent.rowconfigure(4, weight=1)
    owner.shear_design_status_var = tk.StringVar(master=owner, value="0 řádků • 0 navrženo")
    owner.shear_design_filter_var = tk.StringVar(master=owner, value="")
    _header(
        parent,
        "Návrh smykových trnů",
        "Návrh Ancon / Leviat podle tabulované VRd bez interpolace. Stejně jako u HIT lze vložit jeden řádek nebo celý výkaz a zkontrolovat náhled před převzetím.",
        owner.shear_design_status_var,
    )

    toolbar = ttk.Frame(parent, style="App.TFrame")
    toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    toolbar.columnconfigure(6, weight=1)
    ttk.Button(toolbar, text="Vložit výkaz…", style="Accent.TButton", command=owner.open_shear_design_schedule).grid(row=0, column=0)
    ttk.Button(toolbar, text="Přepočítat vše", command=owner.recalculate_shear_design_all).grid(row=0, column=1, padx=(7, 0))
    ttk.Button(toolbar, text="Vymazat vše", command=lambda: owner.clear_shear_kind("design")).grid(row=0, column=2, padx=(7, 0))
    ttk.Button(toolbar, text="Kopírovat výsledky", command=lambda: owner.copy_shear_table("design")).grid(row=0, column=3, padx=(7, 0))
    ttk.Label(toolbar, text="Výrobce návrhu: Ancon / Leviat", style="Muted.TLabel").grid(row=0, column=7, sticky="e")

    quick = ttk.Frame(parent, style="Card.TFrame", padding=(12, 9))
    quick.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    values = {
        "name": tk.StringVar(master=owner, value=_next("N", owner.shear_design_rows)),
        "qty": tk.StringVar(master=owner, value="1"),
        "ved": tk.StringVar(master=owner, value=""),
        "slab": tk.StringVar(master=owner, value="200"),
        "gap": tk.StringVar(master=owner, value="20"),
        "concrete": tk.StringVar(master=owner, value="C25/30"),
        "movement": tk.StringVar(master=owner, value=MOVEMENTS[0]),
        "application": tk.StringVar(master=owner, value=APPLICATIONS[0]),
        "sleeve": tk.StringVar(master=owner, value=LOW_SLEEVES[0]),
    }
    owner.shear_design_vars = values
    column = 0
    for label, key, width in (
        ("Pozice", "name", 8),
        ("Ks", "qty", 5),
        ("VEd [kN/trn]", "ved", 10),
        ("h [mm]", "slab", 8),
        ("Spára [mm]", "gap", 9),
    ):
        ttk.Label(quick, text=label, style="Card.TLabel").grid(row=0, column=column)
        column += 1
        ttk.Entry(quick, textvariable=values[key], width=width).grid(row=0, column=column, padx=(4, 9))
        column += 1
    ttk.Label(quick, text="Beton", style="Card.TLabel").grid(row=0, column=column)
    column += 1
    ttk.Combobox(quick, textvariable=values["concrete"], values=CONCRETES, state="readonly", width=9).grid(row=0, column=column, padx=(4, 9))
    column += 1
    ttk.Combobox(quick, textvariable=values["movement"], values=MOVEMENTS, state="readonly", width=21).grid(row=0, column=column, padx=(4, 9))
    column += 1
    ttk.Combobox(quick, textvariable=values["application"], values=APPLICATIONS, state="readonly", width=23).grid(row=0, column=column, padx=(4, 9))
    column += 1
    ttk.Combobox(quick, textvariable=values["sleeve"], values=LOW_SLEEVES, state="readonly", width=18).grid(row=0, column=column, padx=(4, 9))
    column += 1
    ttk.Button(quick, text="Navrhnout a přidat", style="Accent.TButton", command=owner.add_shear_design_row).grid(row=0, column=column)

    _row_actions(owner, parent, row=3, kind="design", filter_var=owner.shear_design_filter_var)
    columns = ("name", "qty", "designation", "vrd", "util", "slab", "gap", "concrete", "movement", "source", "note")
    owner.shear_design_tree = _tree(
        parent,
        row=4,
        columns=columns,
        headings=("Pozice", "Ks", "Navržený Ancon", "VRd [kN]", "Využití", "h [mm]", "Spára [mm]", "Beton", "Pohyb", "Zdroj", "Poznámka"),
        widths=(80, 50, 310, 85, 80, 80, 90, 90, 150, 110, 430),
        anchors={"name": "w", "designation": "w", "note": "w"},
    )


def build_substitution(owner: Any, parent: ttk.Frame) -> None:
    parent.rowconfigure(4, weight=1)
    owner.shear_substitution_status_var = tk.StringVar(master=owner, value="0 řádků • 0 vyhodnoceno")
    owner.shear_substitution_filter_var = tk.StringVar(master=owner, value="")
    _header(
        parent,
        "Záměny smykových trnů",
        "Stejný princip jako u izolačních nosníků: cílový výrobce se zvolí jednou a tabulku lze aktualizovat z celého Dekodéru. Požadavek záměny vychází z katalogové VRd původního trnu při stejné geometrii.",
        owner.shear_substitution_status_var,
    )

    toolbar = ttk.Frame(parent, style="Card.TFrame", padding=(12, 8))
    toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    toolbar.columnconfigure(8, weight=1)
    ttk.Label(toolbar, text="Cílový výrobce:", style="Card.TLabel", font=("Calibri", 10, "bold")).grid(row=0, column=0)
    ttk.Combobox(toolbar, textvariable=owner.shear_target_manufacturer_var, values=TARGETS, state="readonly", width=12).grid(row=0, column=1, padx=(5, 12))
    ttk.Button(toolbar, text="Aktualizovat z Dekodéru", style="Accent.TButton", command=owner.sync_shear_substitutions_from_decoder).grid(row=0, column=2)
    ttk.Button(toolbar, text="Přepočítat vše", command=owner.recalculate_shear_substitutions).grid(row=0, column=3, padx=(7, 0))
    ttk.Button(toolbar, text="Vymazat vše", command=lambda: owner.clear_shear_kind("substitution")).grid(row=0, column=4, padx=(7, 0))
    ttk.Button(toolbar, text="Kopírovat výsledky", command=lambda: owner.copy_shear_table("substitution")).grid(row=0, column=5, padx=(7, 0))
    ttk.Label(toolbar, text="Ruční záměnu lze stále doplnit níže.", style="MutedCard.TLabel").grid(row=0, column=9, sticky="e")

    quick = ttk.Frame(parent, style="Card.TFrame", padding=(12, 9))
    quick.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    values = {
        "name": tk.StringVar(master=owner, value=_next("Z", owner.shear_substitution_rows)),
        "qty": tk.StringVar(master=owner, value="1"),
        "source": tk.StringVar(master=owner, value=""),
        "slab": tk.StringVar(master=owner, value="200"),
        "gap": tk.StringVar(master=owner, value="20"),
        "concrete": tk.StringVar(master=owner, value="C25/30"),
        "cover": tk.StringVar(master=owner, value="30"),
        "target": owner.shear_target_manufacturer_var,
        "sleeve": tk.StringVar(master=owner, value=LOW_SLEEVES[0]),
    }
    owner.shear_substitution_vars = values
    column = 0
    for label, key, width in (
        ("Pozice", "name", 8),
        ("Ks", "qty", 5),
        ("Původní trn", "source", 28),
        ("h [mm]", "slab", 8),
        ("Spára [mm]", "gap", 9),
    ):
        ttk.Label(quick, text=label, style="Card.TLabel").grid(row=0, column=column)
        column += 1
        ttk.Entry(quick, textvariable=values[key], width=width).grid(row=0, column=column, padx=(4, 9))
        column += 1
    ttk.Label(quick, text="Beton", style="Card.TLabel").grid(row=0, column=column)
    column += 1
    ttk.Combobox(quick, textvariable=values["concrete"], values=CONCRETES, state="readonly", width=9).grid(row=0, column=column, padx=(4, 9))
    column += 1
    ttk.Label(quick, text="cnom Schöck", style="Card.TLabel").grid(row=0, column=column)
    column += 1
    ttk.Combobox(quick, textvariable=values["cover"], values=COVERS, state="readonly", width=5).grid(row=0, column=column, padx=(4, 9))
    column += 1
    ttk.Combobox(quick, textvariable=values["sleeve"], values=LOW_SLEEVES, state="readonly", width=18).grid(row=0, column=column, padx=(4, 9))
    column += 1
    ttk.Button(quick, text="Navrhnout záměnu", style="Accent.TButton", command=owner.add_shear_substitution_row).grid(row=0, column=column)

    _row_actions(owner, parent, row=3, kind="substitution", filter_var=owner.shear_substitution_filter_var)
    columns = ("name", "qty", "source", "source_vrd", "target", "target_vrd", "util", "slab", "gap", "movement", "status", "note")
    owner.shear_substitution_tree = _tree(
        parent,
        row=4,
        columns=columns,
        headings=("Pozice", "Ks", "Původní trn", "VRd pův. [kN]", "Navržený ekvivalent", "VRd cíle [kN]", "Poměr", "h [mm]", "Spára [mm]", "Pohyb", "Výsledek", "Poznámka"),
        widths=(80, 50, 260, 105, 300, 105, 80, 80, 90, 150, 130, 430),
        anchors={"name": "w", "source": "w", "target": "w", "note": "w"},
    )


def build_shear_workspace(owner: Any, parent: ttk.Frame) -> None:
    init_shear_workspace(owner)
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)
    head = ttk.Frame(parent, style="Card.TFrame", padding=(14, 10))
    head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    head.columnconfigure(0, weight=1)
    ttk.Label(head, text="Smykové trny", style="ProjectTitle.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(head, text=_base.catalog_summary(), style="MutedCard.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))

    notebook = ttk.Notebook(parent, style="Workspace.TNotebook")
    notebook.grid(row=1, column=0, sticky="nsew")
    owner.shear_notebook = notebook
    decoder = ttk.Frame(notebook, style="App.TFrame", padding=(8, 10, 8, 8))
    design = ttk.Frame(notebook, style="App.TFrame", padding=(8, 10, 8, 8))
    substitution = ttk.Frame(notebook, style="App.TFrame", padding=(8, 10, 8, 8))
    notebook.add(decoder, text="Dekodér")
    notebook.add(design, text="Návrh")
    notebook.add(substitution, text="Záměny")
    build_decoder(owner, decoder)
    build_design(owner, design)
    build_substitution(owner, substitution)
    owner.refresh_shear_tables()


def add_decoder(self: Any) -> None:
    init_shear_workspace(self)
    values = self.shear_decoder_vars
    try:
        info = _base.decode_dowel(values["designation"].get())
        if not info:
            raise ValueError("Označení smykového trnu nebylo rozpoznáno.")
        row = {
            "name": values["name"].get().strip() or _next("S", self.shear_decoder_rows),
            "quantity": _qty(values["qty"].get()),
            "designation": values["designation"].get().strip(),
            "manufacturer": info.get("manufacturer", ""),
            "family": info.get("family", ""),
            "size": info.get("size", ""),
            "movement": info.get("movement", "axial"),
            "slab_mm": _f(values["slab"].get()),
            "gap_mm": _f(values["gap"].get()),
            "concrete": values["concrete"].get(),
            "cover_mm": int(values["cover"].get()),
        }
        self.shear_decoder_rows.append(row)
        _mark(self)
        self.refresh_shear_tables()
        values["name"].set(_next("S", self.shear_decoder_rows))
        values["designation"].set("")
    except Exception as exc:
        messagebox.showerror("Dekodér smykových trnů", str(exc), parent=self)


def _design_from_values(values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    try:
        candidates, error = design_ancon(
            ved=abs(float(values["ved"])),
            slab_mm=float(values["slab_mm"]),
            gap_mm=float(values["gap_mm"]),
            concrete=str(values["concrete"]),
            movement=str(values.get("movement", "axial")),
            application=str(values.get("application", "new")),
            low_sleeve=str(values.get("low_sleeve", "stainless")),
        )
    except Exception as exc:
        return None, str(exc)
    if not candidates:
        return None, error or "Nenalezen vyhovující Ancon."
    return candidates[0].as_dict(), ""


def add_design(self: Any) -> None:
    init_shear_workspace(self)
    values = self.shear_design_vars
    try:
        data = {
            "name": values["name"].get().strip() or _next("N", self.shear_design_rows),
            "quantity": _qty(values["qty"].get()),
            "ved": abs(_f(values["ved"].get())),
            "slab_mm": _f(values["slab"].get()),
            "gap_mm": _f(values["gap"].get()),
            "concrete": values["concrete"].get(),
            "movement": _movement_code(values["movement"].get()),
            "application": _application_code(values["application"].get()),
            "low_sleeve": _sleeve_code(values["sleeve"].get()),
        }
        candidate, error = _design_from_values(data)
        if candidate is None:
            raise ValueError(error)
        data["candidate"] = candidate
        self.shear_design_rows.append(data)
        _mark(self)
        self.refresh_shear_tables()
        values["name"].set(_next("N", self.shear_design_rows))
        values["ved"].set("")
    except Exception as exc:
        messagebox.showerror("Návrh smykového trnu", str(exc), parent=self)


def _substitution_from_values(values: dict[str, Any], target_manufacturer: str) -> dict[str, Any]:
    result = dict(values)
    source_designation = str(result.get("source_designation", "") or "").strip()
    info = _base.decode_dowel(source_designation)
    if isinstance(info, dict) and info.get("decoder_only"):
        result.update({
            "source": {},
            "target": {},
            "status": "POUZE DEKODÉR",
            "error": "Historické značení Schöck Dorn je záměrně pouze pro Dekodér; bez historického katalogu se automaticky nezaměňuje.",
            "target_manufacturer": target_manufacturer,
        })
        return result
    try:
        source, target, error = propose_substitution(
            source_designation=source_designation,
            target_manufacturer=target_manufacturer,
            slab_mm=float(result.get("slab_mm", 0)),
            gap_mm=float(result.get("gap_mm", 0)),
            concrete=str(result.get("concrete", "C25/30")),
            cover_mm=int(result.get("cover_mm", 30)),
            low_sleeve=str(result.get("low_sleeve", "stainless")),
        )
    except Exception as exc:
        source, target, error = None, None, str(exc)
    result["source"] = source.as_dict() if source is not None else {}
    result["target"] = target.as_dict() if target is not None else {}
    result["target_manufacturer"] = target_manufacturer
    if source is None or target is None:
        result["status"] = "NELZE"
        result["error"] = error or "Záměnu nelze navrhnout."
    else:
        result["status"] = target.status
        result["error"] = ""
    return result


def add_substitution(self: Any) -> None:
    init_shear_workspace(self)
    values = self.shear_substitution_vars
    try:
        data = {
            "name": values["name"].get().strip() or _next("Z", self.shear_substitution_rows),
            "quantity": _qty(values["qty"].get()),
            "source_designation": values["source"].get().strip(),
            "slab_mm": _f(values["slab"].get()),
            "gap_mm": _f(values["gap"].get()),
            "concrete": values["concrete"].get(),
            "cover_mm": int(values["cover"].get()),
            "low_sleeve": _sleeve_code(values["sleeve"].get()),
            "origin": "manual",
        }
        computed = _substitution_from_values(data, self.shear_target_manufacturer_var.get())
        if not computed.get("target"):
            raise ValueError(computed.get("error") or "Záměnu nelze navrhnout.")
        self.shear_substitution_rows.append(computed)
        _mark(self)
        self.refresh_shear_tables()
        values["name"].set(_next("Z", self.shear_substitution_rows))
        values["source"].set("")
    except Exception as exc:
        messagebox.showerror("Záměna smykového trnu", str(exc), parent=self)


def decoder_to_substitution(self: Any) -> None:
    tree = getattr(self, "shear_decoder_tree", None)
    indices = _selected_indices(tree)
    if not indices:
        messagebox.showinfo("Záměna z Dekodéru", "Nejprve vyberte řádek v tabulce Dekodéru.", parent=self)
        return
    row = self.shear_decoder_rows[indices[0]]
    values = self.shear_substitution_vars
    values["name"].set(str(row.get("name", "") or _next("Z", self.shear_substitution_rows)))
    values["qty"].set(str(row.get("quantity", 1)))
    values["source"].set(str(row.get("designation", "")))
    values["slab"].set(str(row.get("slab_mm", "")))
    values["gap"].set(str(row.get("gap_mm", "")))
    values["concrete"].set(str(row.get("concrete", "C25/30")))
    values["cover"].set(str(row.get("cover_mm", 30)))
    try:
        self.shear_notebook.select(2)
        self.update_idletasks()
    except Exception:
        pass


def open_decoder_schedule(self: Any) -> None:
    values = self.shear_decoder_vars
    dialog = ShearScheduleDialog(
        self,
        mode="decoder",
        decoder=_base.decode_dowel,
        defaults={
            "slab": values["slab"].get(),
            "gap": values["gap"].get(),
            "concrete": values["concrete"].get(),
            "cover": values["cover"].get(),
            "movement": MOVEMENTS[0],
            "application": APPLICATIONS[0],
            "sleeve": LOW_SLEEVES[0],
        },
        existing_names={str(row.get("name", "")) for row in self.shear_decoder_rows},
    )
    self.wait_window(dialog)
    if not dialog.result:
        return
    if bool(dialog.replace_existing.get()):
        self.shear_decoder_rows = []
    for payload in dialog.result:
        row = dict(payload)
        row.pop("import_source_text", None)
        self.shear_decoder_rows.append(row)
    _mark(self)
    self.refresh_shear_tables()
    values["name"].set(_next("S", self.shear_decoder_rows))


def open_design_schedule(self: Any) -> None:
    values = self.shear_design_vars
    dialog = ShearScheduleDialog(
        self,
        mode="design",
        design=design_ancon,
        defaults={
            "slab": values["slab"].get(),
            "gap": values["gap"].get(),
            "concrete": values["concrete"].get(),
            "cover": "30",
            "movement": values["movement"].get(),
            "application": values["application"].get(),
            "sleeve": values["sleeve"].get(),
        },
        existing_names={str(row.get("name", "")) for row in self.shear_design_rows},
    )
    self.wait_window(dialog)
    if not dialog.result:
        return
    if bool(dialog.replace_existing.get()):
        self.shear_design_rows = []
    for payload in dialog.result:
        row = dict(payload)
        source = row.pop("import_source_text", "")
        if source:
            row["import_source_text"] = source
        self.shear_design_rows.append(row)
    _mark(self)
    self.refresh_shear_tables()
    values["name"].set(_next("N", self.shear_design_rows))


def sync_substitutions_from_decoder(self: Any) -> None:
    init_shear_workspace(self)
    if not self.shear_decoder_rows:
        messagebox.showinfo("Záměny smykových trnů", "Dekodér zatím neobsahuje žádné řádky.", parent=self)
        return
    target = self.shear_target_manufacturer_var.get()
    manual = [deepcopy(row) for row in self.shear_substitution_rows if row.get("origin") != "decoder"]
    synced: list[dict[str, Any]] = []
    for row in self.shear_decoder_rows:
        data = {
            "name": str(row.get("name", "") or _next("Z", manual + synced)),
            "quantity": int(row.get("quantity", 1) or 1),
            "source_designation": str(row.get("designation", "")),
            "slab_mm": float(row.get("slab_mm", 0) or 0),
            "gap_mm": float(row.get("gap_mm", 0) or 0),
            "concrete": str(row.get("concrete", "C25/30")),
            "cover_mm": int(row.get("cover_mm", 30) or 30),
            "low_sleeve": "stainless",
            "origin": "decoder",
        }
        synced.append(_substitution_from_values(data, target))
    self.shear_substitution_rows = manual + synced
    _mark(self)
    self.refresh_shear_tables()
    self.shear_substitution_vars["name"].set(_next("Z", self.shear_substitution_rows))
    try:
        self.shear_notebook.select(2)
    except Exception:
        pass


def recalculate_design_all(self: Any) -> None:
    failed = 0
    for row in self.shear_design_rows:
        candidate, error = _design_from_values(row)
        if candidate is None:
            row["candidate"] = {}
            row["error"] = error
            failed += 1
        else:
            row["candidate"] = candidate
            row["error"] = ""
    _mark(self)
    self.refresh_shear_tables()
    if failed:
        messagebox.showwarning("Návrh smykových trnů", f"Přepočet dokončen. {failed} řádků nyní nelze navrhnout.", parent=self)


def recalculate_substitutions(self: Any) -> None:
    target = self.shear_target_manufacturer_var.get()
    self.shear_substitution_rows = [
        _substitution_from_values(dict(row), target)
        for row in self.shear_substitution_rows
    ]
    _mark(self)
    self.refresh_shear_tables()


def shear_edit_meta(self: Any, kind: str) -> None:
    rows, tree, _prefix = _rows_for_kind(self, kind)
    indices = _selected_indices(tree)
    if not indices:
        return
    row = rows[indices[0]]
    name = simpledialog.askstring("Upravit řádek", "Pozice:", initialvalue=str(row.get("name", "")), parent=self)
    if name is None:
        return
    qty = simpledialog.askinteger("Upravit řádek", "Ks:", initialvalue=int(row.get("quantity", 1) or 1), minvalue=1, maxvalue=1_000_000, parent=self)
    if qty is None:
        return
    row["name"] = name.strip() or row.get("name", "")
    row["quantity"] = qty
    _mark(self)
    self.refresh_shear_tables()


def shear_duplicate_selected(self: Any, kind: str) -> None:
    rows, tree, prefix = _rows_for_kind(self, kind)
    indices = _selected_indices(tree)
    if not indices:
        return
    source = deepcopy(rows[indices[0]])
    source["name"] = _next(prefix, rows)
    rows.insert(indices[0] + 1, source)
    _mark(self)
    self.refresh_shear_tables()
    if tree is not None and tree.exists(str(indices[0] + 1)):
        tree.selection_set(str(indices[0] + 1))


def shear_move_selected(self: Any, kind: str, direction: int) -> None:
    rows, tree, _prefix = _rows_for_kind(self, kind)
    indices = _selected_indices(tree)
    if not indices:
        return
    index = indices[0]
    target = index + int(direction)
    if not 0 <= target < len(rows):
        return
    rows[index], rows[target] = rows[target], rows[index]
    _mark(self)
    self.refresh_shear_tables()
    if tree is not None and tree.exists(str(target)):
        tree.selection_set(str(target))
        tree.see(str(target))


def shear_delete_selected(self: Any, kind: str) -> None:
    rows, tree, _prefix = _rows_for_kind(self, kind)
    indices = _selected_indices(tree)
    if not indices:
        return
    for index in sorted(indices, reverse=True):
        if 0 <= index < len(rows):
            rows.pop(index)
    _mark(self)
    self.refresh_shear_tables()


def clear_shear_kind(self: Any, kind: str) -> None:
    rows, _tree_widget, _prefix = _rows_for_kind(self, kind)
    if rows and not messagebox.askyesno("Vymazat vše", "Opravdu vymazat všechny řádky v této části?", parent=self):
        return
    rows.clear()
    _mark(self)
    self.refresh_shear_tables()


def copy_shear_table(self: Any, kind: str) -> None:
    _rows, tree, _prefix = _rows_for_kind(self, kind)
    if tree is None:
        return
    columns = list(tree["columns"])
    selected = list(tree.selection())
    iids = selected or list(tree.get_children(""))
    if not iids:
        return
    headers = [str(tree.heading(column, "text")) for column in columns]
    lines = ["\t".join(headers)]
    for iid in iids:
        values = tree.item(iid, "values")
        lines.append("\t".join(str(value) for value in values))
    self.clipboard_clear()
    self.clipboard_append("\n".join(lines))
    self.update_idletasks()


def _fill(tree: ttk.Treeview, rows: list[dict[str, Any]], formatter, filter_text: str) -> None:
    for iid in tree.get_children(""):
        tree.delete(iid)
    for index, row in enumerate(rows):
        if not _filter_matches(row, filter_text):
            continue
        values, tag = formatter(row)
        tree.insert("", "end", iid=str(index), values=values, tags=(tag,) if tag else ())


def refresh(self: Any) -> None:
    init_shear_workspace(self)
    if hasattr(self, "shear_decoder_tree"):
        _fill(
            self.shear_decoder_tree,
            self.shear_decoder_rows,
            lambda row: ((
                row.get("name", ""),
                row.get("quantity", 1),
                row.get("manufacturer", ""),
                row.get("family", ""),
                row.get("size", ""),
                "axiální + příčný" if row.get("movement") == "transverse" else "axiální",
                row.get("designation", ""),
                _fmt(row.get("slab_mm"), 0),
                _fmt(row.get("gap_mm"), 0),
                row.get("concrete", ""),
            ), ""),
            self.shear_decoder_filter_var.get() if hasattr(self, "shear_decoder_filter_var") else "",
        )
        if hasattr(self, "shear_decoder_status_var"):
            self.shear_decoder_status_var.set(f"{len(self.shear_decoder_rows)} řádků • {sum(int(r.get('quantity',1) or 1) for r in self.shear_decoder_rows)} ks")

    if hasattr(self, "shear_design_tree"):
        def design_values(row):
            candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
            ok = bool(candidate)
            note = candidate.get("note", "") if ok else row.get("error", "")
            return ((
                row.get("name", ""),
                row.get("quantity", 1),
                candidate.get("designation", "NELZE NAVRHNOUT" if not ok else ""),
                _fmt(candidate.get("vrd")) if ok else "—",
                (_fmt(candidate.get("utilization", 0) * 100) + " %") if ok else "—",
                _fmt(row.get("slab_mm"), 0),
                _fmt(row.get("gap_mm"), 0),
                row.get("concrete", ""),
                "axiální + příčný" if row.get("movement") == "transverse" else "axiální",
                (f"Ancon p.{candidate.get('page','')}" if ok else "—"),
                note,
            ), "" if ok else "error")
        self.shear_design_tree.tag_configure("error", foreground=self.colors["danger"])
        _fill(
            self.shear_design_tree,
            self.shear_design_rows,
            design_values,
            self.shear_design_filter_var.get() if hasattr(self, "shear_design_filter_var") else "",
        )
        if hasattr(self, "shear_design_status_var"):
            ok = sum(1 for row in self.shear_design_rows if isinstance(row.get("candidate"), dict) and row.get("candidate"))
            self.shear_design_status_var.set(f"{len(self.shear_design_rows)} řádků • {ok} navrženo")

    if hasattr(self, "shear_substitution_tree"):
        def substitution_values(row):
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            target = row.get("target") if isinstance(row.get("target"), dict) else {}
            source_vrd = float(source.get("vrd", 0) or 0)
            target_vrd = float(target.get("vrd", 0) or 0)
            ratio = (target_vrd / source_vrd * 100.0) if source_vrd > 0 and target_vrd > 0 else None
            status = str(row.get("status", "") or (target.get("status") if target else "NELZE"))
            note = str(target.get("note", "") if target else row.get("error", ""))
            return ((
                row.get("name", ""),
                row.get("quantity", 1),
                row.get("source_designation", ""),
                _fmt(source_vrd) if source_vrd else "—",
                target.get("designation", "—"),
                _fmt(target_vrd) if target_vrd else "—",
                (_fmt(ratio) + " %") if ratio is not None else "—",
                _fmt(row.get("slab_mm"), 0),
                _fmt(row.get("gap_mm"), 0),
                "axiální + příčný" if source.get("movement") == "transverse" else ("axiální" if source else "—"),
                status,
                note,
            ), "error" if status in {"NELZE", "POUZE DEKODÉR"} else "")
        self.shear_substitution_tree.tag_configure("error", foreground=self.colors["danger"])
        _fill(
            self.shear_substitution_tree,
            self.shear_substitution_rows,
            substitution_values,
            self.shear_substitution_filter_var.get() if hasattr(self, "shear_substitution_filter_var") else "",
        )
        if hasattr(self, "shear_substitution_status_var"):
            ok = sum(1 for row in self.shear_substitution_rows if row.get("target"))
            self.shear_substitution_status_var.set(f"{len(self.shear_substitution_rows)} řádků • {ok} vyhodnoceno")


def serialize(self: Any) -> dict[str, Any]:
    init_shear_workspace(self)
    return {
        "schema_version": 2,
        "decoder": deepcopy(self.shear_decoder_rows),
        "design": deepcopy(self.shear_design_rows),
        "substitution": deepcopy(self.shear_substitution_rows),
    }


def load(self: Any, payload: Any) -> None:
    init_shear_workspace(self)
    data = payload if isinstance(payload, dict) else {}
    self.shear_decoder_rows = deepcopy(data.get("decoder", [])) if isinstance(data.get("decoder"), list) else []
    self.shear_design_rows = deepcopy(data.get("design", [])) if isinstance(data.get("design"), list) else []
    self.shear_substitution_rows = deepcopy(data.get("substitution", [])) if isinstance(data.get("substitution"), list) else []
    if hasattr(self, "refresh_shear_tables"):
        self.refresh_shear_tables()


def clear(self: Any) -> None:
    self.shear_decoder_rows = []
    self.shear_design_rows = []
    self.shear_substitution_rows = []
    if hasattr(self, "refresh_shear_tables"):
        self.refresh_shear_tables()


def report_rows(self: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in getattr(self, "shear_design_rows", []):
        candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
        if not candidate:
            continue
        out.append({
            "domain_id": "shear_dowels",
            "domain": "Smykové trny",
            "group": "Návrh smykových trnů",
            "name": row.get("name", ""),
            "quantity": row.get("quantity", 1),
            "series": candidate.get("manufacturer", ""),
            "connection_type": "DOWEL",
            "height_mm": row.get("slab_mm", ""),
            "cover_mm": "",
            "concrete": row.get("concrete", ""),
            "required_length_mm": row.get("gap_mm", ""),
            "custom_actions": [{"label": "VEd", "value": row.get("ved", ""), "unit": "kN/prvek"}],
            "candidate": {
                "designation": candidate.get("designation", ""),
                "connection_type": "DOWEL",
                "manufacturer": candidate.get("manufacturer", ""),
                "physical_length_mm": candidate.get("length_mm") or 0,
                "height": row.get("slab_mm", 0),
                "concrete": row.get("concrete", ""),
                "utilization": candidate.get("utilization", 0),
                "m1": 0,
                "v1": candidate.get("vrd", 0),
                "m2": 0,
                "v2": 0,
                "mode": f"VRd {candidate.get('vrd',0):.1f} kN • η {candidate.get('utilization',0)*100:.1f} %",
                "page": candidate.get("page", ""),
                "source_note": candidate.get("source", ""),
            },
            "status": candidate.get("status", "VYHOVUJE"),
            "detail": candidate.get("note", ""),
            "notes": [candidate.get("note", "")] if candidate.get("note") else [],
        })
    return out


def install_methods(cls: Any) -> None:
    cls.add_shear_decoder_row = add_decoder
    cls.add_shear_design_row = add_design
    cls.add_shear_substitution_row = add_substitution
    cls.shear_decoder_to_substitution = decoder_to_substitution
    cls.open_shear_decoder_schedule = open_decoder_schedule
    cls.open_shear_design_schedule = open_design_schedule
    cls.sync_shear_substitutions_from_decoder = sync_substitutions_from_decoder
    cls.recalculate_shear_design_all = recalculate_design_all
    cls.recalculate_shear_substitutions = recalculate_substitutions
    cls.shear_edit_meta = shear_edit_meta
    cls.shear_duplicate_selected = shear_duplicate_selected
    cls.shear_move_selected = shear_move_selected
    cls.shear_delete_selected = shear_delete_selected
    cls.clear_shear_kind = clear_shear_kind
    cls.copy_shear_table = copy_shear_table
    cls.refresh_shear_tables = refresh
    cls.serialize_shear_dowels = serialize
    cls.load_shear_dowels = load
    cls.clear_shear_dowels = clear
    cls.collect_shear_report_rows = report_rows


# Historical Schöck patch imports shear_dowels_ui after this overlay is loaded.
# Expose the new hooks through the old module so its decoder-only safety wrapper
# wraps the 2.1.4 workflow rather than the 2.1.0 one.
_base.refresh = refresh
_base.decoder_to_substitution = decoder_to_substitution
