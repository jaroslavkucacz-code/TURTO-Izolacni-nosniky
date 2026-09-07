from __future__ import annotations

"""TURTO ISO 1.1.23 Decoder ISO layer over verified project_ui."""

from typing import Any
from tkinter import messagebox, ttk

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

    def concrete_changed(self, _event=None) -> None:
        target = self.project_concrete_var.get().strip() or "C25/30"
        self.project.concrete_class = target
        self.project.touch(); self.mark_project_dirty()
        try:
            if hasattr(self, "refresh_project_concrete_filter"): self.refresh_project_concrete_filter()
        except Exception:
            pass
        self.set_status(f"Beton AKCE nastaven na {target}. Dekodér i našeptávač zobrazují pouze tento beton.")

    def concrete(self) -> None:
        target = self.project_concrete_var.get().strip() or "C25/30"
        self.project.concrete_class = target
        if not self.project.rows:
            self.mark_project_dirty(); self.set_status(f"Beton AKCE nastaven na {target}."); return
        if not messagebox.askyesno(
            "Použít beton na AKCI",
            f"Přepočítat všechny dekódované řádky AKCE na beton {target}, pokud je pro daný typ v katalogu dostupný?",
            parent=self,
        ):
            return
        updated = 0; skipped: list[str] = []
        for row in list(self.project.rows):
            selection = dict(row.get("selection", {}))
            if str(selection.get("concrete_min", "")) == target: continue
            selection["concrete_min"] = target
            try:
                result = _base.query_from_selection(self.database, selection)
            except Exception:
                skipped.append(str(row.get("position", "")) or str(row.get("id", ""))[:8]); continue
            replacement = _base.create_project_row(
                result, row_id=str(row["id"]), position=str(row.get("position", "")),
                quantity=int(row.get("quantity", 1)), note=str(row.get("note", "")),
                source_text=str(row.get("source_text", "")),
            )
            self.project.replace(str(row["id"]), replacement); updated += 1
        self.mark_project_dirty(); self.refresh_project_tree()
        message = f"Beton AKCE: {target}. Přepočítáno {updated} řádků."
        if skipped: message += f" Beze změny zůstalo {len(skipped)} řádků, kde tato třída není dostupná."
        self.set_status(message)
        if skipped:
            messagebox.showwarning("Beton AKCE", message + "\n\nŘádky beze změny: " + ", ".join(skipped[:20]), parent=self)

    def name_changed(self, *_args) -> None:
        if self._project_var_guard: return
        self.project.name = self.project_name_var.get().strip() or "Nová akce"
        self.mark_project_dirty()

    def selection_changed(self, _event=None) -> None:
        selected = len(self.project_tree.selection()) if hasattr(self, "project_tree") else 0
        if selected: self.set_status(f"Vybráno {selected} řádků Dekodéru ISO.")

    _base.ProjectWorkspaceMixin._build_project_tab = build
    _base.ProjectWorkspaceMixin._build_project_context_menu = context
    _base.ProjectWorkspaceMixin.load_selected_project_row = show_decoder_detail
    _base.ProjectWorkspaceMixin.show_decoder_detail = show_decoder_detail
    _base.ProjectWorkspaceMixin._on_project_concrete_changed = concrete_changed
    _base.ProjectWorkspaceMixin.apply_project_concrete_to_rows = concrete
    _base.ProjectWorkspaceMixin._on_project_name_changed = name_changed
    _base.ProjectWorkspaceMixin._on_project_tree_selection = selection_changed


install()
ProjectWorkspaceMixin = _base.ProjectWorkspaceMixin
