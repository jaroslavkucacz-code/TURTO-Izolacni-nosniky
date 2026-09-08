from __future__ import annotations

"""Cross-domain UI consistency for TURTO 2.2.4."""

import os
import re
import sys
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from table_controls import open_columns, scan, reapply

_VERBOSE_PREFIXES = (
    "Krytí, výška, beton, izolant, skutečná délka",
    "Převádí se katalogová momentová, smyková",
    "Přijetí vyhovujícího HIT místo původního odhadu",
    "Ruční záměnu lze stále doplnit níže",
)


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try: stack.extend(widget.winfo_children())
        except Exception: pass


def _find_buttons(root: Any, text: str) -> list[ttk.Button]:
    out = []
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text: out.append(widget)
        except Exception: pass
    return out


def _hide(widget: Any) -> None:
    try:
        manager = widget.winfo_manager()
        if manager == "grid": widget.grid_remove()
        elif manager == "pack": widget.pack_forget()
        elif manager == "place": widget.place_forget()
    except Exception: pass


def _hide_empty_parent(widget: Any) -> None:
    parent = getattr(widget, "master", None)
    if parent is None: return
    try:
        managed = [child for child in parent.winfo_children() if child.winfo_manager()]
        if not managed: _hide(parent)
    except Exception: pass


def _strip_sort_marker(value: str) -> str:
    return str(value or "").rstrip(" ▲▼")


def _export_tree_xlsx(owner: Any, kind: str, tree: ttk.Treeview) -> None:
    try:
        display = [str(c) for c in tree["displaycolumns"]]
        if not display or display == ["#all"]: display = [str(c) for c in tree["columns"]]
    except Exception:
        display = [str(c) for c in tree["columns"]]
    if not display: return
    selected = list(tree.selection()); items = selected or list(tree.get_children(""))
    if not items:
        messagebox.showinfo("Export Excel", "Tabulka neobsahuje žádné zobrazené řádky.", parent=owner); return
    headers = [_strip_sort_marker(str(tree.heading(c, "text") or c)) for c in display]
    rows = [[tree.set(iid, c) for c in display] for iid in items]
    project = getattr(owner, "project", None); name = str(getattr(project, "name", "AKCE") or "AKCE")
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "AKCE"
    suffix = {"decoder": "Smykove_trny_Dekoder", "design": "Smykove_trny_Navrh", "substitution": "Smykove_trny_Zameny"}.get(kind, "Smykove_trny")
    path = filedialog.asksaveasfilename(parent=owner, title="Export tabulky do Excelu", defaultextension=".xlsx", initialfile=f"{suffix}_{name}.xlsx", filetypes=[("Excel", "*.xlsx")])
    if not path: return
    try:
        from xlsx_export import write_xlsx
        target = write_xlsx(Path(path), headers=headers, rows=rows, sheet_name=suffix[:31], creator="TURTO – Vytvořil Ing. Jaroslav Kučera")
    except Exception as exc:
        messagebox.showerror("Export Excel", str(exc), parent=owner); return
    try:
        if sys.platform == "win32": os.startfile(str(target))  # type: ignore[attr-defined]
    except Exception: pass
    status_var = getattr(owner, f"shear_{kind}_status_var", None)
    if status_var is not None:
        try: status_var.set(f"Exportováno {len(rows)} řádků: {Path(target).name}")
        except Exception: pass


def _filter_bar_for_tab(tab: Any) -> ttk.Frame | None:
    for widget in _walk(tab):
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("text")) == "Filtr": return widget.master
        except Exception: pass
    return None


def _add_columns_button(owner: Any, tab: Any, tree: ttk.Treeview) -> None:
    bar = _filter_bar_for_tab(tab)
    if bar is None: return
    for child in bar.winfo_children():
        try:
            if isinstance(child, ttk.Button) and str(child.cget("text")) == "Sloupce…": return
        except Exception: pass
    ttk.Button(bar, text="Sloupce…", command=lambda: open_columns(owner, tree)).grid(row=0, column=5, padx=(7, 0))


def _add_export_button(owner: Any, tab: Any, tree: ttk.Treeview, kind: str) -> None:
    anchor = None
    for text in ("Kopírovat pro Excel", "Kopírovat výsledky"):
        buttons = _find_buttons(tab, text)
        if buttons:
            anchor = buttons[0]; break
    if anchor is None: return
    master = anchor.master
    for child in master.winfo_children():
        try:
            if isinstance(child, ttk.Button) and str(child.cget("text")) == "Export Excel…": return
        except Exception: pass
    try:
        info = anchor.grid_info(); column = int(info.get("column", 0)) + 1
        occupied = {int(child.grid_info().get("column", -1)) for child in master.winfo_children() if child.winfo_manager() == "grid" and child is not anchor}
        while column in occupied: column += 1
        ttk.Button(master, text="Export Excel…", command=lambda: _export_tree_xlsx(owner, kind, tree)).grid(row=int(info.get("row", 0)), column=column, padx=(7, 0))
    except Exception: pass


def _clean_shear_tabs(owner: Any) -> None:
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None: return
    try: tabs = [notebook.nametowidget(tab_id) for tab_id in notebook.tabs()]
    except Exception: return
    if len(tabs) < 3: return
    trees = (getattr(owner, "shear_decoder_tree", None), getattr(owner, "shear_design_tree", None), getattr(owner, "shear_substitution_tree", None))
    kinds = ("decoder", "design", "substitution")
    for index in (0, 2):
        for button in _find_buttons(tabs[index], "Vymazat vše"): _hide(button)
    for tab in tabs:
        for button in _find_buttons(tab, "Kopírovat výsledky"):
            try: button.configure(text="Kopírovat pro Excel")
            except Exception: pass
    for tab, tree, kind in zip(tabs, trees, kinds):
        if tree is None: continue
        _add_columns_button(owner, tab, tree); _add_export_button(owner, tab, tree, kind)


def _clean_iso_decoder(owner: Any) -> None:
    decoder = getattr(owner, "project_tab", None)
    if decoder is None: return
    for button in _find_buttons(decoder, "Export CSV"): _hide(button)


def _clean_iso_design(owner: Any) -> None:
    design = getattr(owner, "hit_tab", None)
    if design is None: return
    for text in ("Aktualizovat katalog", "Otevřít zdroj"):
        for button in _find_buttons(design, text): _hide(button)


def _clean_iso_substitution(owner: Any) -> None:
    tab = getattr(owner, "substitution_tab", None)
    if tab is None: return
    for text in ("Aktualizovat z Dekodéru", "Aktualizovat z projektu"):
        for button in _find_buttons(tab, text): _hide(button)
    for widget in list(_walk(tab)):
        try:
            if isinstance(widget, ttk.Label):
                value = str(widget.cget("text") or "").strip()
                if any(value.startswith(prefix) for prefix in _VERBOSE_PREFIXES):
                    _hide(widget); _hide_empty_parent(widget)
        except Exception: pass
    tree = getattr(owner, "sub_tree", None)
    if tree is not None:
        candidate_bar = None
        for text in ("Navrhnout vybrané", "Navrhnout vše"):
            buttons = _find_buttons(tab, text)
            if buttons:
                candidate_bar = buttons[0].master; break
        if candidate_bar is not None:
            exists = any(isinstance(child, ttk.Button) and str(child.cget("text")) == "Sloupce…" for child in candidate_bar.winfo_children())
            if not exists: ttk.Button(candidate_bar, text="Sloupce…", command=lambda: open_columns(owner, tree)).grid(row=0, column=0)


def _patch_help_dialog() -> None:
    import ui_help
    if getattr(ui_help, "_turto_help_tools_224_installed", False): return
    Original = ui_help.HelpDialog
    class HelpDialog224(Original):
        def __init__(self, owner: Any) -> None:
            super().__init__(owner)
            notebook = next((w for w in _walk(self) if isinstance(w, ttk.Notebook)), None)
            if notebook is None: return
            data_tab = None
            try:
                for tab_id in notebook.tabs():
                    if str(notebook.tab(tab_id, "text")) == "Data a zdroje": data_tab = notebook.nametowidget(tab_id); break
            except Exception: pass
            if data_tab is None: return
            data_tab.rowconfigure(0, weight=1)
            bar = ttk.Frame(data_tab, style="App.TFrame"); bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            ttk.Label(bar, text="Údržba katalogu:", style="Muted.TLabel").pack(side="left")
            if hasattr(owner, "rebuild_hit_data"): ttk.Button(bar, text="Aktualizovat data HIT", command=owner.rebuild_hit_data).pack(side="left", padx=(8, 0))
            if hasattr(owner, "open_hit_source"): ttk.Button(bar, text="Otevřít zdroj HIT", command=owner.open_hit_source).pack(side="left", padx=(8, 0))
    ui_help.HelpDialog = HelpDialog224; ui_help._turto_help_tools_224_installed = True


def apply(owner: Any) -> None:
    _patch_help_dialog(); scan(owner); _clean_iso_decoder(owner); _clean_iso_design(owner); _clean_iso_substitution(owner); _clean_shear_tabs(owner); reapply(owner)


def selftest() -> None:
    assert any(prefix.startswith("Krytí") for prefix in _VERBOSE_PREFIXES)


if __name__ == "__main__": selftest()
