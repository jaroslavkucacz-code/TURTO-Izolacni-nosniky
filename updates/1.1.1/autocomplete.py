from __future__ import annotations

from typing import Any, Callable

import tkinter as tk
from tkinter import ttk

from catalog_engine import CatalogDatabase, DesignationSuggestion, QueryResult


class DesignationAutocomplete:
    """Plovoucí našeptávač nad katalogovými označeními.

    Neprovádí automatické statické rozhodnutí. Uživatel vždy vybere konkrétní
    katalogovou kombinaci, kterou komponenta pouze doplní do textového pole.
    """

    def __init__(
        self,
        *,
        entry: ttk.Entry,
        variable: tk.StringVar,
        database: CatalogDatabase,
        colors: dict[str, str],
        submit_callback: Callable[[tk.Event[Any] | None], Any] | None = None,
        on_choose: Callable[[QueryResult], None] | None = None,
        preferred_catalog_getter: Callable[[], str | None] | None = None,
        preferred_concrete_getter: Callable[[], str | None] | None = None,
        limit: int = 10,
        delay_ms: int = 130,
    ) -> None:
        self.entry = entry
        self.variable = variable
        self.database = database
        self.colors = colors
        self.submit_callback = submit_callback
        self.on_choose = on_choose
        self.preferred_catalog_getter = preferred_catalog_getter
        self.preferred_concrete_getter = preferred_concrete_getter
        self.limit = max(4, int(limit))
        self.delay_ms = max(50, int(delay_ms))
        self.popup: tk.Toplevel | None = None
        self.tree: ttk.Treeview | None = None
        self._after_id: str | None = None
        self._suggestions: dict[str, DesignationSuggestion] = {}
        self._suppress_once = False
        self._visible = False

        self._trace_id = variable.trace_add("write", self._on_variable_changed)
        entry.bind("<Return>", self._on_return)
        entry.bind("<Down>", self._on_down, add="+")
        entry.bind("<Escape>", self._on_escape, add="+")
        entry.bind("<FocusIn>", self._on_focus_in, add="+")
        entry.bind("<FocusOut>", self._on_focus_out, add="+")
        entry.bind("<Configure>", lambda _e: self._reposition(), add="+")
        entry.bind("<Destroy>", self._on_entry_destroy, add="+")

    def destroy(self) -> None:
        try:
            self.variable.trace_remove("write", self._trace_id)
        except Exception:
            pass
        self.hide()

    def _on_entry_destroy(self, _event: tk.Event[Any]) -> None:
        if self.popup is not None:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None

    def _on_variable_changed(self, *_args: Any) -> None:
        if self._suppress_once:
            self._suppress_once = False
            self.hide()
            return
        if self._after_id:
            try:
                self.entry.after_cancel(self._after_id)
            except Exception:
                pass
        try:
            self._after_id = self.entry.after(self.delay_ms, self.refresh)
        except Exception:
            self._after_id = None

    def _preferred_catalog(self) -> str | None:
        if self.preferred_catalog_getter is None:
            return None
        try:
            return self.preferred_catalog_getter()
        except Exception:
            return None

    def _preferred_concrete(self) -> str | None:
        if self.preferred_concrete_getter is None:
            return None
        try:
            value = self.preferred_concrete_getter()
            return str(value).strip() if value else None
        except Exception:
            return None

    def refresh(self) -> None:
        self._after_id = None
        if not self.entry.winfo_exists():
            return
        text = self.variable.get().strip()
        if len(self.database._suggestion_compact(text)) < 2:
            self.hide(); return
        preferred = self._preferred_catalog()
        preferred_concrete = self._preferred_concrete()
        # U hotového přesného označení popup neotvíráme. Je to důležité i při
        # programovém načtení existujícího projektového řádku do editoru.
        try:
            exact = self.database.resolve_designation(text, preferred_catalog_id=preferred, preferred_concrete=preferred_concrete)
            if self.database._suggestion_compact(exact.designation) == self.database._suggestion_compact(text):
                self.hide(); return
        except Exception:
            pass
        suggestions = self.database.suggest_designations(
            text, preferred_catalog_id=preferred, preferred_concrete=preferred_concrete, limit=self.limit
        )
        if not suggestions:
            self.hide(); return
        self._show(suggestions)

    def _ensure_popup(self) -> None:
        if self.popup is not None and self.popup.winfo_exists():
            return
        top = tk.Toplevel(self.entry)
        top.withdraw()
        top.overrideredirect(True)
        try:
            top.transient(self.entry.winfo_toplevel())
        except Exception:
            pass
        top.configure(background=self.colors["border"])
        frame = tk.Frame(top, background=self.colors["border"], bd=0, highlightthickness=0)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        style = ttk.Style(self.entry)
        style.configure(
            "Suggest.Treeview",
            font=("Calibri", 10),
            rowheight=28,
            background=self.colors["panel"],
            fieldbackground=self.colors["panel"],
            foreground=self.colors["text"],
            borderwidth=0,
        )
        style.map("Suggest.Treeview", background=[("selected", self.colors["accent"])], foreground=[("selected", "#FFFFFF")])
        style.configure(
            "Suggest.Treeview.Heading",
            font=("Calibri", 9, "bold"),
            background=self.colors["panel_alt"],
            foreground=self.colors["muted"],
            relief="flat",
            padding=(5, 5),
        )
        tree = ttk.Treeview(frame, columns=("designation", "values"), show="headings", style="Suggest.Treeview", height=8, selectmode="browse")
        tree.heading("designation", text="Možné doplnění označení")
        tree.heading("values", text="Izolant • tlakový přenos • statika")
        tree.column("designation", width=585, minwidth=360, anchor="w", stretch=True)
        tree.column("values", width=390, minwidth=290, anchor="w", stretch=False)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tree.bind("<Return>", self._tree_accept)
        tree.bind("<Tab>", self._tree_accept)
        tree.bind("<Escape>", self._tree_escape)
        tree.bind("<ButtonRelease-1>", self._tree_click)
        tree.bind("<FocusOut>", self._on_focus_out, add="+")
        self.popup = top
        self.tree = tree

    def _show(self, suggestions: list[DesignationSuggestion]) -> None:
        self._ensure_popup()
        assert self.popup is not None and self.tree is not None
        self._suggestions.clear()
        self.tree.delete(*self.tree.get_children(""))
        for i, suggestion in enumerate(suggestions):
            iid = f"s{i}"
            self.tree.insert("", "end", iid=iid, values=(suggestion.designation, suggestion.values_text))
            self._suggestions[iid] = suggestion
        children = self.tree.get_children("")
        self.tree.configure(height=min(10, max(1, len(children))))
        if children:
            self.tree.selection_set(children[0]); self.tree.focus(children[0])
        self._visible = True
        self._reposition()
        self.popup.deiconify(); self.popup.lift()

    def _reposition(self) -> None:
        if not self._visible or self.popup is None or not self.popup.winfo_exists():
            return
        try:
            self.entry.update_idletasks(); self.popup.update_idletasks()
            screen_w = self.entry.winfo_screenwidth(); screen_h = self.entry.winfo_screenheight()
            x = self.entry.winfo_rootx(); y_below = self.entry.winfo_rooty() + self.entry.winfo_height() + 2
            width = max(1000, self.entry.winfo_width() + 470)
            width = min(width, max(520, screen_w - 30))
            height = self.popup.winfo_reqheight()
            x = min(max(5, x), max(5, screen_w - width - 10))
            if y_below + height > screen_h - 40:
                y = max(5, self.entry.winfo_rooty() - height - 2)
            else:
                y = y_below
            self.popup.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def hide(self) -> None:
        self._visible = False
        if self.popup is not None and self.popup.winfo_exists():
            try:
                self.popup.withdraw()
            except Exception:
                pass

    def _selected(self) -> DesignationSuggestion | None:
        if not self._visible or self.tree is None:
            return None
        selection = self.tree.selection()
        iid = selection[0] if selection else self.tree.focus()
        if not iid:
            children = self.tree.get_children("")
            iid = children[0] if children else ""
        return self._suggestions.get(iid)

    def accept_selected(self) -> bool:
        suggestion = self._selected()
        if suggestion is None:
            return False
        self._suppress_once = True
        self.variable.set(suggestion.designation)
        self.hide()
        self.entry.focus_set()
        self.entry.icursor("end")
        if self.on_choose is not None:
            self.on_choose(suggestion.result)
        return True

    def _on_return(self, event: tk.Event[Any]) -> str:
        if self._visible and self.accept_selected():
            return "break"
        if self.submit_callback is not None:
            self.submit_callback(event)
        return "break"

    def _on_down(self, _event: tk.Event[Any]) -> str | None:
        if not self._visible:
            self.refresh()
        if self._visible and self.tree is not None:
            children = self.tree.get_children("")
            if children:
                self.tree.focus_set(); self.tree.selection_set(children[0]); self.tree.focus(children[0])
                return "break"
        return None

    def _on_escape(self, _event: tk.Event[Any]) -> str | None:
        if self._visible:
            self.hide(); return "break"
        return None

    def _on_focus_in(self, _event: tk.Event[Any]) -> None:
        if self.variable.get().strip() and not self._visible:
            if self._after_id:
                return
            self._after_id = self.entry.after(80, self.refresh)

    def _on_focus_out(self, _event: tk.Event[Any]) -> None:
        # Klik do popupu krátce změní focus; po 120 ms zkontrolujeme, kam skutečně přešel.
        try:
            self.entry.after(120, self._hide_if_focus_elsewhere)
        except Exception:
            pass

    def _hide_if_focus_elsewhere(self) -> None:
        if not self._visible:
            return
        try:
            focus = self.entry.focus_get()
            if focus is self.entry or focus is self.tree:
                return
        except Exception:
            pass
        self.hide()

    def _tree_accept(self, _event: tk.Event[Any]) -> str:
        self.accept_selected(); return "break"

    def _tree_escape(self, _event: tk.Event[Any]) -> str:
        self.hide(); self.entry.focus_set(); return "break"

    def _tree_click(self, event: tk.Event[Any]) -> str | None:
        if self.tree is None:
            return None
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row); self.tree.focus(row)
            self.accept_selected(); return "break"
        return None
