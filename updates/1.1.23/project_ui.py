from __future__ import annotations

"""TURTO ISO 1.1.23 Decoder ISO layer over verified project_ui."""

from typing import Any
from tkinter import ttk

import project_ui_base as _base
from project_ui_base import *  # noqa: F401,F403
from decoder_detail import HIT_CATALOG_ID, show_decoder_detail


def _walk(root: Any):
    stack = [root]
    while stack:
        w = stack.pop(); yield w
        try: stack.extend(w.winfo_children())
        except Exception: pass


def _button(root: Any, text: str):
    for w in _walk(root):
        try:
            if isinstance(w, ttk.Button) and str(w.cget("text")) == text: return w
        except Exception: pass
    return None


def _label(root: Any, text: str):
    for w in _walk(root):
        try:
            if isinstance(w, ttk.Label) and str(w.cget("text")) == text: return w
        except Exception: pass
    return None


def install() -> None:
    original_build = _base.ProjectWorkspaceMixin._build_project_tab
    original_context = _base.ProjectWorkspaceMixin._build_project_context_menu
    original_concrete = _base.ProjectWorkspaceMixin.apply_project_concrete_to_rows

    def build(self, parent: ttk.Frame) -> None:
        original_build(self, parent)
        if hasattr(self, "project_name_entry"): self.project_name_entry.grid_remove()
        title = _label(parent, "Soupis izolačních nosníků objektu")
        if title is not None: title.configure(text="Dekodér ISO – dekódované izolační nosníky")
        for text in ("Nový objekt", "Otevřít projekt", "Uložit", "Uložit jako…"):
            w = _button(parent, text)
            if w is not None: w.grid_remove()
        bulk = _button(parent, "Hromadné vložení z výkazu")
        if bulk is not None:
            filebar = bulk.master
            for child in filebar.winfo_children():
                if isinstance(child, ttk.Separator): child.grid_remove()
            for old, column, new in (
                ("Hromadné vložení z výkazu", 0, "Hromadné dekódování z výkazu"),
                ("Kopírovat pro Excel", 1, None), ("Export Excel…", 2, None), ("Export CSV", 3, None),
            ):
                w = _button(filebar, old)
                if w is not None:
                    if new: w.configure(text=new)
                    w.grid_configure(column=column, padx=(7, 0) if column else 0)
        for old, new in (("Beton projektu", "Beton AKCE"), ("Rychlé přidání řádku", "Rychlé dekódování")):
            w = _label(parent, old)
            if w is not None: w.configure(text=new)
        w = _button(parent, "Přidat řádek")
        if w is not None: w.configure(text="Dekódovat a přidat")
        note = _label(parent, "Projektový soubor uchovává i vydání katalogu a snímek hodnot.")
        if note is not None: note.configure(text="Dekódované řádky, záměny i Návrh HIT se ukládají společně v centrální AKCI.")

        # Old detail-editor commands disappear with the removed lookup tab.
        action = None
        for widget in _walk(parent):
            try:
                if isinstance(widget, ttk.Button) and str(widget.cget("text")) == str(self.project_detail_action_var.get()): action = widget; break
            except Exception: pass
        if action is not None: action.grid_remove()
        editor = _button(parent, "Načíst do editoru")
        if editor is not None:
            info = editor.grid_info(); editor.grid_remove()
            detail = ttk.Button(editor.master, text="Detail nosníku", command=self.show_decoder_detail)
            detail.grid(row=int(info.get("row", 0)), column=int(info.get("column", 1)), padx=(7, 0), sticky=str(info.get("sticky", "")))
            self.decoder_detail_button = detail
        try: self.project_tree.unbind("<Double-1>")
        except Exception: pass
        self.project_tree.bind("<Double-1>", self.show_decoder_detail)

        # Replace the old bottom help text even if wording differs slightly by version.
        for widget in _walk(parent):
            try:
                if isinstance(widget, ttk.Label) and "Dvojklik" in str(widget.cget("text")) and "editor" in str(widget.cget("text")):
                    widget.configure(text="Dvojklik zobrazí detail dekódovaného nosníku a jeho statické/katalogové hodnoty. Dekodér přijímá i úplná označení Leviat HIT.")
            except Exception: pass

    def context(self) -> None:
        original_context(self); menu = self.project_context_menu
        try: menu.delete(0, "end")
        except Exception: return
        menu.add_command(label="Detail nosníku", command=self.show_decoder_detail)
        menu.add_command(label="Upravit pozici / ks / poznámku", command=self.edit_selected_project_metadata)
        menu.add_command(label="Duplikovat", command=self.duplicate_selected_project_rows)
        menu.add_separator(); menu.add_command(label="Kopírovat pro Excel", command=self.copy_project_table)
        menu.add_command(label="Export Excel…", command=self.export_project_xlsx)
        menu.add_separator(); menu.add_command(label="Smazat", command=self.delete_selected_project_rows)

    def concrete(self) -> None:
        hit_ids = {str(row.get("id")) for row in self.project.rows if str((row.get("selection") or {}).get("catalog_id", "")) == HIT_CATALOG_ID}
        if not hit_ids: return original_concrete(self)
        original = list(self.project.rows); order = [str(row.get("id")) for row in original]
        normal = [row for row in original if str(row.get("id")) not in hit_ids]
        if not normal:
            self.project.concrete_class = self.project_concrete_var.get().strip() or "C25/30"
            self.project.touch(); self.mark_project_dirty(); self.set_status("Beton AKCE změněn. Již dekódované výrobky HIT zůstaly beze změny."); return
        self.project.rows = normal
        try: original_concrete(self)
        finally:
            changed = {str(row.get("id")): row for row in self.project.rows}
            changed.update({str(row.get("id")): row for row in original if str(row.get("id")) in hit_ids})
            self.project.rows = [changed[row_id] for row_id in order if row_id in changed]
            self.refresh_project_tree()

    _base.ProjectWorkspaceMixin._build_project_tab = build
    _base.ProjectWorkspaceMixin._build_project_context_menu = context
    _base.ProjectWorkspaceMixin.load_selected_project_row = show_decoder_detail
    _base.ProjectWorkspaceMixin.show_decoder_detail = show_decoder_detail
    _base.ProjectWorkspaceMixin.apply_project_concrete_to_rows = concrete


install()
ProjectWorkspaceMixin = _base.ProjectWorkspaceMixin
