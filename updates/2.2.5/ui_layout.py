from __future__ import annotations

"""TURTO 2.2.5 – sjednocená hierarchie záložek a kontextových akcí.

Vrstva nemění výpočty ani data. Upravuje pouze rozmístění, popisy a aktivní
stavy ovládacích prvků a zavádí společné pravidlo dvojklik = detail řádku.
"""

from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from ui_utils import place_dialog_on_parent
except Exception:
    place_dialog_on_parent = None


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _buttons(root: Any, text: str) -> list[ttk.Button]:
    out: list[ttk.Button] = []
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
                out.append(widget)
        except Exception:
            pass
    return out


def _first_button(root: Any, *texts: str) -> ttk.Button | None:
    for text in texts:
        found = _buttons(root, text)
        if found:
            return found[0]
    return None


def _label(root: Any, text: str) -> ttk.Label | None:
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("text")) == text:
                return widget
        except Exception:
            pass
    return None


def _hide(widget: Any) -> None:
    try:
        manager = widget.winfo_manager()
        if manager == "grid":
            widget.grid_remove()
        elif manager == "pack":
            widget.pack_forget()
        elif manager == "place":
            widget.place_forget()
    except Exception:
        pass


def _state(button: ttk.Button | None, enabled: bool) -> None:
    if button is None:
        return
    try:
        button.configure(state="normal" if enabled else "disabled")
    except Exception:
        pass


def _selection_count(tree: ttk.Treeview | None) -> int:
    if tree is None:
        return 0
    try:
        return len(tree.selection())
    except Exception:
        return 0


def _tree_heading(tree: ttk.Treeview, column: str) -> str:
    try:
        return str(tree.heading(column, "text") or column).rstrip(" ▲▼")
    except Exception:
        return str(column)


class TableRowDetailDialog(tk.Toplevel):
    def __init__(self, owner: Any, tree: ttk.Treeview, iid: str, title: str) -> None:
        super().__init__(owner)
        self.title(title)
        self.geometry("900x650")
        self.minsize(680, 480)
        self.transient(owner)
        self.grab_set()
        try:
            self.configure(background=owner.colors["bg"])
        except Exception:
            pass
        if place_dialog_on_parent:
            try:
                place_dialog_on_parent(self, owner)
            except Exception:
                pass

        outer = ttk.Frame(self, style="App.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        try:
            values = tuple(tree.item(iid, "values"))
        except Exception:
            values = ()
        try:
            columns = [str(value) for value in tree["columns"]]
        except Exception:
            columns = []
        rows = []
        for index, column in enumerate(columns):
            value = values[index] if index < len(values) else ""
            rows.append((_tree_heading(tree, column), str(value)))

        position = ""
        for label, value in rows:
            if label.lower().startswith("pozice") and value.strip():
                position = value.strip()
                break

        ttk.Label(
            outer,
            text=(title + (f" – {position}" if position else "")),
            style="DialogTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text="Přehled hodnot aktuálního řádku. Úpravy se provádějí příslušnou akcí v pracovní záložce.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))

        card = ttk.Frame(outer, style="Card.TFrame", padding=1)
        card.grid(row=2, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        text = tk.Text(
            card,
            wrap="word",
            font=("Calibri", 11),
            background=owner.colors["panel"],
            foreground=owner.colors["text"],
            insertbackground=owner.colors["text"],
            relief="flat",
            padx=14,
            pady=12,
        )
        bar = ttk.Scrollbar(card, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=bar.set)
        text.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        lines = []
        for label, value in rows:
            if value.strip():
                lines.append(f"{label}\n  {value}\n")
        text.insert("1.0", "\n".join(lines) if lines else "Řádek neobsahuje zobrazené hodnoty.")
        text.configure(state="disabled")

        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.grid(row=3, column=0, sticky="e", pady=(10, 0))
        ttk.Button(bottom, text="Zavřít", command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda _event: self.destroy())


def show_tree_detail(owner: Any, tree: ttk.Treeview | None, title: str) -> None:
    if tree is None:
        return
    selected = list(tree.selection())
    if len(selected) != 1:
        messagebox.showinfo(title, "Vyberte právě jeden řádek.", parent=owner)
        return
    TableRowDetailDialog(owner, tree, str(selected[0]), title)


def _doubleclick_detail(owner: Any, tree: ttk.Treeview, title: str, event: Any) -> str:
    try:
        iid = str(tree.identify_row(event.y) or "")
        if not iid:
            return "break"
        tree.selection_set(iid)
        tree.focus(iid)
        owner.after_idle(lambda: show_tree_detail(owner, tree, title))
    except Exception:
        pass
    return "break"


def _filter_bar(tab: Any) -> Any | None:
    label = _label(tab, "Filtr")
    return label.master if label is not None else None


def _normalize_row_bar(owner: Any, tab: Any, tree: ttk.Treeview, *, detail_title: str, iso_decoder: bool = False) -> None:
    bar = _filter_bar(tab)
    if bar is None:
        return

    detail = _first_button(bar, "Detail nosníku", "Detail prvku")
    if detail is None and not iso_decoder:
        detail = ttk.Button(bar, text="Detail prvku", command=lambda: show_tree_detail(owner, tree, detail_title))
    elif detail is not None:
        try:
            detail.configure(text="Detail prvku")
        except Exception:
            pass

    edit = _first_button(bar, "Upravit pozici / ks")
    duplicate = _first_button(bar, "Duplikovat")
    up = _first_button(bar, "Nahoru")
    down = _first_button(bar, "Dolů")
    delete = _first_button(bar, "Smazat")
    columns = _first_button(bar, "Sloupce…")

    ordered = [detail, edit, duplicate, up, down, delete, columns]
    for column, button in enumerate(ordered):
        if button is None:
            continue
        try:
            button.grid(row=0, column=column, padx=((7 if column else 0), 0))
        except Exception:
            pass

    filter_label = _label(bar, "Filtr")
    entries = [w for w in bar.winfo_children() if isinstance(w, ttk.Entry)]
    clear = _first_button(bar, "×")
    try:
        bar.columnconfigure(8, weight=1)
        if filter_label is not None:
            filter_label.grid(row=0, column=9, padx=(14, 4))
        if entries:
            entries[0].grid(row=0, column=10)
        if clear is not None:
            clear.grid(row=0, column=11, padx=(5, 0))
    except Exception:
        pass

    def update(_event: Any = None) -> None:
        count = _selection_count(tree)
        _state(detail, count == 1)
        _state(edit, count == 1)
        _state(duplicate, count >= 1)
        _state(up, count >= 1)
        _state(down, count >= 1)
        _state(delete, count >= 1)

    try:
        tree.bind("<<TreeviewSelect>>", update, add="+")
        tree.bind("<Delete>", lambda _event: delete.invoke() if delete is not None and _selection_count(tree) else None, add="+")
    except Exception:
        pass
    update()


def _normalize_iso_decoder(owner: Any) -> None:
    tab = getattr(owner, "project_tab", None)
    tree = getattr(owner, "project_tree", None)
    if tab is None or tree is None:
        return
    _normalize_row_bar(owner, tab, tree, detail_title="Detail prvku", iso_decoder=True)

    toolbar_button = _first_button(tab, "Hromadné dekódování z výkazu", "Hromadné dekódování z výkazu…")
    if toolbar_button is not None:
        master = toolbar_button.master
        order = [
            toolbar_button,
            _first_button(master, "Kopírovat pro Excel"),
            _first_button(master, "Export Excel…", "Export Excel"),
        ]
        for column, button in enumerate(order):
            if button is not None:
                try:
                    button.grid(row=0, column=column, padx=((7 if column else 0), 0))
                except Exception:
                    pass


def _normalize_shear(owner: Any) -> None:
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return
    try:
        tabs = [notebook.nametowidget(tab_id) for tab_id in notebook.tabs()]
    except Exception:
        return
    if len(tabs) < 3:
        return

    trees = [
        getattr(owner, "shear_decoder_tree", None),
        getattr(owner, "shear_design_tree", None),
        getattr(owner, "shear_substitution_tree", None),
    ]
    titles = ["Detail smykového trnu", "Detail návrhu smykového trnu", "Detail záměny smykového trnu"]

    for tab, tree, title in zip(tabs, trees, titles):
        if tree is None:
            continue
        _normalize_row_bar(owner, tab, tree, detail_title=title)
        try:
            tree.bind("<Double-1>", lambda event, t=tree, text=title: _doubleclick_detail(owner, t, text, event))
            tree.bind("<Return>", lambda _event, t=tree, text=title: (show_tree_detail(owner, t, text), "break")[1])
        except Exception:
            pass

    # Dekodér: vstup / výstup / explicitní převod.
    decoder = tabs[0]
    bulk = _first_button(decoder, "Hromadné dekódování z výkazu…", "Hromadné dekódování z výkazu")
    if bulk is not None:
        master = bulk.master
        order = [bulk, _first_button(master, "Kopírovat pro Excel"), _first_button(master, "Export Excel…")]
        for column, button in enumerate(order):
            if button is not None:
                try: button.grid(row=0, column=column, padx=((7 if column else 0), 0))
                except Exception: pass

    transfer = _first_button(decoder, "Převést do Záměn")
    decoder_tree = trees[0]
    if transfer is not None and decoder_tree is not None:
        def transfer_state(_event: Any = None) -> None:
            _state(transfer, _selection_count(decoder_tree) == 1)
        try: decoder_tree.bind("<<TreeviewSelect>>", transfer_state, add="+")
        except Exception: pass
        transfer_state()

    # Návrh: nejdřív vstup, potom přepočet/výstup, destruktivní reset až napravo.
    design = tabs[1]
    insert = _first_button(design, "Vložit výkaz…")
    if insert is not None:
        master = insert.master
        recalc = _first_button(master, "Přepočítat vše")
        copy = _first_button(master, "Kopírovat pro Excel", "Kopírovat výsledky")
        export = _first_button(master, "Export Excel…")
        clear = _first_button(master, "Vymazat vše")
        fixed = _label(master, "Výrobce návrhu: Ancon / Leviat")
        if fixed is not None:
            _hide(fixed)
        for column, button in enumerate([insert, recalc, copy, export]):
            if button is not None:
                try: button.grid(row=0, column=column, padx=((7 if column else 0), 0))
                except Exception: pass
        try:
            master.columnconfigure(8, weight=1)
            if clear is not None:
                clear.grid(row=0, column=9, padx=(18, 0), sticky="e")
        except Exception:
            pass

    # Záměny: výrobce je skutečný vstup, pak synchronizace/přepočet a výstup.
    substitution = tabs[2]
    target_label = _label(substitution, "Cílový výrobce:")
    sync = _first_button(substitution, "Aktualizovat z Dekodéru")
    if target_label is not None and sync is not None and target_label.master is sync.master:
        master = sync.master
        copy = _first_button(master, "Kopírovat pro Excel", "Kopírovat výsledky")
        export = _first_button(master, "Export Excel…")
        recalc = _first_button(master, "Přepočítat vše")
        combos = [w for w in master.winfo_children() if isinstance(w, ttk.Combobox)]
        try:
            target_label.grid(row=0, column=0)
            if combos:
                combos[0].grid(row=0, column=1, padx=(5, 12))
            sync.grid(row=0, column=2)
            if recalc is not None: recalc.grid(row=0, column=3, padx=(7, 0))
            if copy is not None: copy.grid(row=0, column=4, padx=(14, 0))
            if export is not None: export.grid(row=0, column=5, padx=(7, 0))
        except Exception:
            pass


def _normalize_iso_substitution(owner: Any) -> None:
    tab = getattr(owner, "substitution_tab", None)
    tree = getattr(owner, "sub_tree", None)
    if tab is None or tree is None:
        return
    primary = _first_button(tab, "Navrhnout vybrané")
    if primary is None:
        return
    bar = primary.master

    detail = _first_button(bar, "Detail záměny")
    if detail is None:
        detail = ttk.Button(bar, text="Detail záměny", command=lambda: show_tree_detail(owner, tree, "Detail záměny za HIT"))
    all_btn = _first_button(bar, "Navrhnout vše")
    edit = _first_button(bar, "Upřesnit zdroj / geometrii…")
    confirm_geometry = _first_button(bar, "✓ Potvrdit geometrii")
    variants = _first_button(bar, "Vybrat variantu…")
    copy = _first_button(bar, "Kopírovat tabulku", "Kopírovat pro Excel")
    export = _first_button(bar, "Export Excel", "Export Excel…")
    columns = _first_button(bar, "Sloupce…")
    pdf = _first_button(bar, "Export PDF")
    if copy is not None:
        try: copy.configure(text="Kopírovat pro Excel")
        except Exception: pass
    if export is not None:
        try: export.configure(text="Export Excel…")
        except Exception: pass
    if pdf is not None:
        _hide(pdf)

    left = [detail, primary, all_btn, edit, confirm_geometry, variants]
    for column, button in enumerate(left):
        if button is not None:
            try: button.grid(row=0, column=column, padx=((7 if column else 0), 0))
            except Exception: pass
    try:
        bar.columnconfigure(6, weight=1)
        if copy is not None: copy.grid(row=0, column=7, padx=(14, 0))
        if export is not None: export.grid(row=0, column=8, padx=(7, 0))
        if columns is not None: columns.grid(row=0, column=9, padx=(7, 0))
    except Exception:
        pass

    review_confirm = _first_button(tab, "✓ Potvrdit záměnu…")
    review_revoke = _first_button(tab, "Zrušit potvrzení")

    def update(_event: Any = None) -> None:
        count = _selection_count(tree)
        _state(detail, count == 1)
        _state(primary, count >= 1)
        _state(edit, count == 1)
        _state(confirm_geometry, count >= 1)
        _state(variants, count == 1)
        _state(review_confirm, count >= 1)
        _state(review_revoke, count >= 1)

    try:
        tree.bind("<<TreeviewSelect>>", update, add="+")
        tree.bind("<Double-1>", lambda event: _doubleclick_detail(owner, tree, "Detail záměny za HIT", event))
        tree.bind("<Return>", lambda _event: (show_tree_detail(owner, tree, "Detail záměny za HIT"), "break")[1])
    except Exception:
        pass
    update()


def _move_header_maintenance_to_help(owner: Any) -> None:
    folder = _first_button(owner, "Složka katalogů")
    check = _first_button(owner, "Kontrola katalogů", "Kontrola databáze")
    if folder is not None:
        owner._catalog_folder_button_225 = folder
        _hide(folder)
    if check is not None:
        owner._catalog_check_button_225 = check
        _hide(check)


def _patch_help() -> None:
    import ui_help
    if getattr(ui_help, "_turto_layout_help_225_installed", False):
        return
    Original = ui_help.HelpDialog

    class HelpDialog225(Original):
        def __init__(self, owner: Any) -> None:
            super().__init__(owner)
            notebook = next((w for w in _walk(self) if isinstance(w, ttk.Notebook)), None)
            if notebook is None:
                return
            data_tab = None
            try:
                for tab_id in notebook.tabs():
                    if str(notebook.tab(tab_id, "text")) == "Data a zdroje":
                        data_tab = notebook.nametowidget(tab_id)
                        break
            except Exception:
                pass
            if data_tab is None:
                return

            maintenance = _label(data_tab, "Údržba katalogu:")
            bar = maintenance.master if maintenance is not None else None
            if bar is None:
                bar = ttk.Frame(data_tab, style="App.TFrame")
                bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
                maintenance = ttk.Label(bar, text="Katalogy a zdroje:", style="Muted.TLabel")
                maintenance.pack(side="left")
            else:
                try: maintenance.configure(text="Katalogy a zdroje:")
                except Exception: pass

            folder = getattr(owner, "_catalog_folder_button_225", None)
            check = getattr(owner, "_catalog_check_button_225", None)
            existing = {str(w.cget("text")) for w in bar.winfo_children() if isinstance(w, ttk.Button)}
            if folder is not None and "Složka katalogů" not in existing:
                ttk.Button(bar, text="Složka katalogů", command=folder.invoke).pack(side="left", padx=(8, 0))
            if check is not None and "Kontrola katalogů" not in existing:
                ttk.Button(bar, text="Kontrola katalogů", command=check.invoke).pack(side="left", padx=(8, 0))

    ui_help.HelpDialog = HelpDialog225
    ui_help._turto_layout_help_225_installed = True


def apply(owner: Any) -> None:
    _patch_help()
    _normalize_iso_decoder(owner)
    _normalize_shear(owner)
    _normalize_iso_substitution(owner)
    _move_header_maintenance_to_help(owner)


def selftest() -> None:
    assert _tree_heading
    assert show_tree_detail
    assert "2.2.5" in __doc__


if __name__ == "__main__":
    selftest()
