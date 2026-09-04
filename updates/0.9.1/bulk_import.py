from __future__ import annotations

from typing import Any, Callable, Iterable

import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk

from bulk_import_engine import (
    BulkImportItem,
    SELECTOR_LABELS,
    analyze_bulk_text,
    selector_value,
    summarize_items,
)
from catalog_engine import CatalogDatabase, DesignationSuggestion, QueryResult, concrete_label
from ui_utils import place_dialog_on_parent


class BulkImportDialog(tk.Toplevel):
    """Kontrolované hromadné vložení řádků z Excelu / schránky.

    Žádná nejednoznačná katalogová varianta se nevloží bez potvrzení uživatele.
    Jednoznačně doplnitelné řádky jsou naopak připravené automaticky.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        database: CatalogDatabase,
        colors: dict[str, str],
        preferred_concrete: str | None,
        existing_positions: Iterable[str],
        start_position: str,
        settings: dict[str, Any] | None = None,
        save_settings: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.colors = colors
        self.preferred_concrete = str(preferred_concrete or "").strip() or None
        self.existing_positions = [str(value) for value in existing_positions]
        self.start_position = str(start_position or "P001")
        self.settings = settings if isinstance(settings, dict) else {}
        self.save_settings = save_settings
        self.result: list[dict[str, Any]] | None = None
        self.items: list[BulkImportItem] = []
        self.skipped_headers = 0
        self.manual_skipped_count = 0
        self._item_by_iid: dict[str, BulkImportItem] = {}
        self._candidate_by_iid: dict[str, DesignationSuggestion] = {}

        self.title("Hromadné vložení z výkazu")
        self.geometry("1380x860")
        self.minsize(1000, 680)
        self.transient(parent)
        place_dialog_on_parent(self, parent)
        self.grab_set()
        self.configure(background=colors["bg"])
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.summary_var = tk.StringVar(value="Vložte řádky z Excelu a spusťte kontrolu.")
        self.candidate_title_var = tk.StringVar(value="Varianty vybraného řádku")
        self.candidate_hint_var = tk.StringVar(value="Po analýze vyberte žlutý řádek, který vyžaduje upřesnění.")
        self.insert_button_var = tk.StringVar(value="Vložit připravené")

        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        ttk.Label(outer, text="Hromadné vložení z výkazu", style="DialogTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            outer,
            text=(
                "Zkopírujte řádky z Excelu a vložte je sem. Program nejprve zkontroluje každý typ proti katalogu. "
                "Jednoznačné řádky připraví automaticky; u neúplných označení nabídne pouze skutečně možné varianty. "
                "Nevyřešený řádek se nikdy nevloží automaticky."
            ),
            style="Muted.TLabel",
            wraplength=1300,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 10))

        input_card = ttk.Frame(outer, style="Card.TFrame", padding=12)
        input_card.grid(row=2, column=0, sticky="ew")
        input_card.columnconfigure(0, weight=1)
        input_card.rowconfigure(1, weight=1)

        input_bar = ttk.Frame(input_card, style="Card.TFrame")
        input_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        input_bar.columnconfigure(0, weight=1)
        ttk.Label(
            input_bar,
            text=(
                "Formáty: typ | typ [TAB] ks | popis [TAB] jednotka [TAB] množství | "
                "pozice [TAB] typ | pozice [TAB] ks [TAB] typ [TAB] poznámka"
            ),
            style="MutedCard.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(input_bar, text="Vložit ze schránky", command=self._paste_clipboard).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(input_bar, text="Analyzovat", style="Accent.TButton", command=self._analyze).grid(
            row=0, column=2, padx=(8, 0)
        )

        text_frame = ttk.Frame(input_card, style="Card.TFrame")
        text_frame.grid(row=1, column=0, sticky="ew")
        text_frame.columnconfigure(0, weight=1)
        self.text = tk.Text(
            text_frame,
            height=8,
            wrap="none",
            undo=True,
            font=("Calibri", 10),
            background=colors["panel"],
            foreground=colors["text"],
            insertbackground=colors["text"],
            selectbackground=colors["accent"],
            selectforeground="#FFFFFF",
            relief="flat",
            padx=8,
            pady=8,
        )
        xscroll = ttk.Scrollbar(text_frame, orient="horizontal", command=self.text.xview)
        yscroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        self.text.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.text.grid(row=0, column=0, sticky="ew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.text.bind("<Control-a>", self._select_all)

        summary_frame = ttk.Frame(outer, style="App.TFrame")
        summary_frame.grid(row=3, column=0, sticky="ew", pady=(10, 8))
        summary_frame.columnconfigure(0, weight=1)
        ttk.Label(summary_frame, textvariable=self.summary_var, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            summary_frame,
            text=f"Beton projektu: {self.preferred_concrete or 'není určen'}",
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="e")

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.grid(row=4, column=0, sticky="nsew")

        review_card = ttk.Frame(panes, style="Card.TFrame", padding=10)
        review_card.columnconfigure(0, weight=1)
        review_card.rowconfigure(1, weight=1)
        panes.add(review_card, weight=3)

        ttk.Label(review_card, text="Kontrola řádků", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 7))
        review_frame = ttk.Frame(review_card, style="Card.TFrame")
        review_frame.grid(row=1, column=0, sticky="nsew")
        review_frame.columnconfigure(0, weight=1)
        review_frame.rowconfigure(0, weight=1)
        self.review_tree = ttk.Treeview(
            review_frame,
            columns=("line", "status", "position", "qty", "input", "resolved", "issue"),
            show="headings",
            selectmode="extended",
            style="Project.Treeview",
        )
        headings = {
            "line": ("Ř.", 44, "center"),
            "status": ("Stav", 92, "center"),
            "position": ("Pozice", 76, "center"),
            "qty": ("Ks", 48, "center"),
            "input": ("Původní označení", 250, "w"),
            "resolved": ("Rozpoznaný typ", 310, "w"),
            "issue": ("Kontrola / co doplnit", 280, "w"),
        }
        self._review_heading_labels = {column: value[0] for column, value in headings.items()}
        self._review_column_defaults = {column: (value[1], value[2]) for column, value in headings.items()}
        initial_layout = self._review_layout_state()
        initial_sort = initial_layout.get("sort", {})
        self.review_sort_column = str(initial_sort.get("column", "")) or None
        self.review_sort_reverse = bool(initial_sort.get("reverse", False))
        for column, (label, width, anchor) in headings.items():
            saved_width = int(initial_layout.get("widths", {}).get(column, width))
            self.review_tree.heading(column, text=label, command=lambda col=column: self._sort_review_table(col))
            self.review_tree.column(column, width=saved_width, minwidth=40, anchor=anchor, stretch=column in {"input", "resolved", "issue"})
        self._apply_review_layout()
        review_y = ttk.Scrollbar(review_frame, orient="vertical", command=self.review_tree.yview)
        review_x = ttk.Scrollbar(review_frame, orient="horizontal", command=self.review_tree.xview)
        self.review_tree.configure(yscrollcommand=review_y.set, xscrollcommand=review_x.set)
        self.review_tree.grid(row=0, column=0, sticky="nsew")
        review_y.grid(row=0, column=1, sticky="ns")
        review_x.grid(row=1, column=0, sticky="ew")
        self.review_tree.tag_configure("ready", foreground=colors["success"])
        self.review_tree.tag_configure("review", foreground=colors["warning_text"])
        self.review_tree.tag_configure("archive", foreground=colors["warning_text"])
        self.review_tree.tag_configure("manual", foreground=colors["muted"])
        self.review_tree.tag_configure("error", foreground=colors["danger"])
        self.review_tree.bind("<<TreeviewSelect>>", self._on_review_selected)
        self.review_tree.bind("<Button-3>", self._show_review_header_menu)
        self.review_tree.bind("<ButtonRelease-1>", self._on_review_tree_release, add="+")

        candidate_card = ttk.Frame(panes, style="Card.TFrame", padding=10)
        candidate_card.columnconfigure(0, weight=1)
        candidate_card.rowconfigure(3, weight=1)
        panes.add(candidate_card, weight=2)

        ttk.Label(candidate_card, textvariable=self.candidate_title_var, style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            candidate_card,
            textvariable=self.candidate_hint_var,
            style="MutedCard.TLabel",
            wraplength=500,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 8))

        candidate_actions = ttk.Frame(candidate_card, style="Card.TFrame")
        candidate_actions.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(candidate_actions, text="Použít na řádek", command=lambda: self._apply_candidate(False)).pack(side="left")
        ttk.Button(
            candidate_actions,
            text="Použít na označené kompatibilní řádky",
            command=lambda: self._apply_candidate(True),
        ).pack(side="left", padx=(7, 0))
        self.archive_button = ttk.Button(
            candidate_actions,
            text="Otevřít archivní katalog",
            command=self._open_archive_source,
            state="disabled",
        )
        self.archive_button.pack(side="left", padx=(7, 0))
        self.manual_button = ttk.Button(
            candidate_actions,
            text="Neřešit – zadám ručně",
            command=self._toggle_manual,
            state="disabled",
        )
        self.manual_button.pack(side="left", padx=(7, 0))

        candidate_frame = ttk.Frame(candidate_card, style="Card.TFrame")
        candidate_frame.grid(row=3, column=0, sticky="nsew")
        candidate_frame.columnconfigure(0, weight=1)
        candidate_frame.rowconfigure(0, weight=1)
        self.candidate_tree = ttk.Treeview(
            candidate_frame,
            columns=("designation", "parameters", "values"),
            show="headings",
            selectmode="browse",
            style="Data.Treeview",
        )
        self.candidate_tree.heading("designation", text="Možná varianta")
        self.candidate_tree.heading("parameters", text="Parametry")
        self.candidate_tree.heading("values", text="Statické hodnoty")
        self.candidate_tree.column("designation", width=270, anchor="w", stretch=True)
        self.candidate_tree.column("parameters", width=270, anchor="w", stretch=True)
        self.candidate_tree.column("values", width=240, anchor="w", stretch=True)
        cand_y = ttk.Scrollbar(candidate_frame, orient="vertical", command=self.candidate_tree.yview)
        cand_x = ttk.Scrollbar(candidate_frame, orient="horizontal", command=self.candidate_tree.xview)
        self.candidate_tree.configure(yscrollcommand=cand_y.set, xscrollcommand=cand_x.set)
        self.candidate_tree.grid(row=0, column=0, sticky="nsew")
        cand_y.grid(row=0, column=1, sticky="ns")
        cand_x.grid(row=1, column=0, sticky="ew")
        self.candidate_tree.bind("<Double-1>", lambda _event: self._apply_candidate(False))
        self.candidate_tree.bind("<Return>", lambda _event: self._apply_candidate(False))

        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(
            bottom,
            text=(
                "Zelené řádky jsou bezpečně připravené. Žluté vyžadují výběr varianty nebo mají dohledaný archivní zdroj. "
                "Červené nejsou rozpoznatelné. Volbou „Neřešit – zadám ručně“ lze libovolný nevyřešený řádek vědomě přeskočit; "
                "šedý řádek se hromadně nevloží a zůstává určen pro následné ruční zadání."
            ),
            style="Muted.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Zrušit", command=self._cancel).grid(row=0, column=1, padx=(8, 0))
        self.insert_button = ttk.Button(
            bottom,
            textvariable=self.insert_button_var,
            style="Accent.TButton",
            command=self._insert_ready,
            state="disabled",
        )
        self.insert_button.grid(row=0, column=2, padx=(8, 0))

        self.bind("<Escape>", lambda _event: self._cancel())
        self.bind("<Control-Return>", lambda _event: self._analyze())
        self.text.focus_set()


    # ---------- trvalé rozložení kontrolní tabulky ----------

    def _review_layout_state(self) -> dict[str, Any]:
        layouts = self.settings.setdefault("table_layouts", {})
        if not isinstance(layouts, dict):
            layouts = {}
            self.settings["table_layouts"] = layouts
        state = layouts.setdefault("bulk_review", {})
        if not isinstance(state, dict):
            state = {}
            layouts["bulk_review"] = state
        ids = list(self._review_heading_labels)
        order = [str(x) for x in state.get("order", []) if str(x) in ids]
        order.extend(column for column in ids if column not in order)
        hidden = [str(x) for x in state.get("hidden", []) if str(x) in ids]
        if len(hidden) >= len(ids):
            hidden = hidden[:-1]
        defaults = self._review_column_defaults
        raw_widths = state.get("widths", {}) if isinstance(state.get("widths", {}), dict) else {}
        widths = {}
        for column in ids:
            try:
                widths[column] = max(40, min(1400, int(raw_widths.get(column, defaults[column][0]))))
            except (TypeError, ValueError):
                widths[column] = defaults[column][0]
        sort = state.get("sort") if isinstance(state.get("sort"), dict) else {}
        sort_column = str(sort.get("column", ""))
        if sort_column not in ids:
            sort_column = ""
        state.update({"order": order, "hidden": hidden, "widths": widths, "sort": {"column": sort_column, "reverse": bool(sort.get("reverse", False))}})
        return state

    def _review_visible_columns(self) -> list[str]:
        state = self._review_layout_state()
        hidden = set(state["hidden"])
        visible = [column for column in state["order"] if column not in hidden]
        return visible or [state["order"][0]]

    def _apply_review_layout(self) -> None:
        state = self._review_layout_state()
        self.review_tree.configure(displaycolumns=tuple(self._review_visible_columns()))
        for column, (default_width, _anchor) in self._review_column_defaults.items():
            self.review_tree.column(column, width=int(state["widths"].get(column, default_width)))
        self._update_review_headings()

    def _save_review_layout(self, *, capture_widths: bool = True) -> None:
        state = self._review_layout_state()
        if capture_widths:
            for column in self._review_heading_labels:
                try:
                    state["widths"][column] = int(self.review_tree.column(column, "width"))
                except Exception:
                    pass
        state["sort"] = {"column": self.review_sort_column or "", "reverse": bool(self.review_sort_reverse)}
        if self.save_settings is not None:
            self.save_settings()

    def _update_review_headings(self) -> None:
        for column, label in self._review_heading_labels.items():
            arrow = ""
            if column == self.review_sort_column:
                arrow = " ▼" if self.review_sort_reverse else " ▲"
            self.review_tree.heading(column, text=label + arrow)

    def _sort_review_table(self, column: str, reverse: bool | None = None, *, save: bool = True) -> None:
        if reverse is not None:
            self.review_sort_column = column
            self.review_sort_reverse = bool(reverse)
        elif self.review_sort_column == column:
            self.review_sort_reverse = not self.review_sort_reverse
        else:
            self.review_sort_column = column
            self.review_sort_reverse = False

        def key(iid: str):
            value = self.review_tree.set(iid, column)
            if column in {"line", "qty"}:
                try:
                    return (0, float(str(value).replace(",", ".")))
                except ValueError:
                    return (1, str(value).casefold())
            return (1, str(value).casefold())

        rows = list(self.review_tree.get_children(""))
        rows.sort(key=key, reverse=self.review_sort_reverse)
        for index, iid in enumerate(rows):
            self.review_tree.move(iid, "", index)
        self._update_review_headings()
        if save:
            self._save_review_layout()

    def _set_review_column_visible(self, column: str, visible: bool) -> None:
        state = self._review_layout_state()
        hidden = list(state["hidden"])
        if visible:
            hidden = [value for value in hidden if value != column]
        elif column not in hidden:
            if len(self._review_visible_columns()) <= 1:
                messagebox.showinfo("Sloupce", "Alespoň jeden sloupec musí zůstat zobrazený.", parent=self)
                return
            hidden.append(column)
        state["hidden"] = hidden
        self._apply_review_layout()
        self._save_review_layout()

    def _move_review_column(self, column: str, delta: int) -> None:
        state = self._review_layout_state()
        order = list(state["order"])
        if column not in order:
            return
        old = order.index(column)
        new = max(0, min(len(order) - 1, old + delta))
        if old == new:
            return
        order.pop(old)
        order.insert(new, column)
        state["order"] = order
        self._apply_review_layout()
        self._save_review_layout()

    def _review_column_from_x(self, x: int) -> str | None:
        marker = str(self.review_tree.identify_column(x))
        try:
            index = int(marker[1:]) - 1
        except Exception:
            return None
        visible = self._review_visible_columns()
        return visible[index] if 0 <= index < len(visible) else None

    def _show_review_header_menu(self, event: tk.Event[Any]) -> str | None:
        if self.review_tree.identify_region(event.x, event.y) != "heading":
            return None
        column = self._review_column_from_x(event.x)
        if not column:
            return "break"
        menu = tk.Menu(self, tearoff=False, font=("Calibri", 10), background=self.colors["panel"], foreground=self.colors["text"], activebackground=self.colors["accent"], activeforeground="#FFFFFF")
        label = self._review_heading_labels[column]
        menu.add_command(label=f"Seřadit {label} vzestupně", command=lambda: self._sort_review_table(column, False))
        menu.add_command(label=f"Seřadit {label} sestupně", command=lambda: self._sort_review_table(column, True))
        menu.add_separator()
        menu.add_command(label="Přesunout vlevo", command=lambda: self._move_review_column(column, -1))
        menu.add_command(label="Přesunout vpravo", command=lambda: self._move_review_column(column, 1))
        menu.add_command(label="Skrýt tento sloupec", command=lambda: self._set_review_column_visible(column, False))
        columns = tk.Menu(menu, tearoff=False, font=("Calibri", 10), background=self.colors["panel"], foreground=self.colors["text"], activebackground=self.colors["accent"], activeforeground="#FFFFFF")
        variables = []
        hidden = set(self._review_layout_state()["hidden"])
        for col in self._review_layout_state()["order"]:
            variable = tk.BooleanVar(value=col not in hidden)
            variables.append(variable)
            columns.add_checkbutton(label=self._review_heading_labels[col], variable=variable, command=lambda c=col, v=variable: self._set_review_column_visible(c, bool(v.get())))
        columns._turto_vars = variables  # type: ignore[attr-defined]
        menu.add_cascade(label="Zobrazit / skrýt sloupce", menu=columns)
        menu.add_separator()
        menu.add_command(label="Výchozí rozložení", command=self._reset_review_layout)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _reset_review_layout(self) -> None:
        layouts = self.settings.setdefault("table_layouts", {})
        if isinstance(layouts, dict):
            layouts.pop("bulk_review", None)
        self.review_sort_column = None
        self.review_sort_reverse = False
        self._apply_review_layout()
        self._save_review_layout()
        self._refresh_review_tree(preserve_selection=True)

    def _on_review_tree_release(self, event: tk.Event[Any]) -> None:
        if self.review_tree.identify_region(event.x, event.y) == "separator":
            self.after_idle(self._save_review_layout)

    def _select_all(self, _event: tk.Event[Any]) -> str:
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _paste_clipboard(self) -> None:
        try:
            value = self.clipboard_get()
        except Exception:
            messagebox.showwarning("Schránka je prázdná", "Ve schránce není text vhodný k vložení.", parent=self)
            return
        if not str(value).strip():
            return
        current = self.text.get("1.0", "end-1c")
        if current.strip():
            self.text.insert("end", "\n" + str(value))
        else:
            self.text.insert("1.0", str(value))
        self.text.see("end")

    def _analyze(self) -> None:
        value = self.text.get("1.0", "end-1c")
        if not value.strip():
            messagebox.showwarning("Prázdné vložení", "Vložte alespoň jeden řádek z výkazu.", parent=self)
            return
        self.items, self.skipped_headers = analyze_bulk_text(
            self.database,
            value,
            preferred_concrete=self.preferred_concrete,
            existing_positions=self.existing_positions,
            start_position=self.start_position,
        )
        self._refresh_review_tree()
        review_iid = next((iid for iid, item in self._item_by_iid.items() if item.status == "review"), None)
        first_iid = review_iid or next(iter(self._item_by_iid), None)
        if first_iid:
            self.review_tree.selection_set(first_iid)
            self.review_tree.focus(first_iid)
            self.review_tree.see(first_iid)
            self._show_candidates_for(first_iid)

    def _refresh_review_tree(self, preserve_selection: bool = False) -> None:
        selected = list(self.review_tree.selection()) if preserve_selection else []
        focus = self.review_tree.focus() if preserve_selection else ""
        for iid in self.review_tree.get_children(""):
            self.review_tree.delete(iid)
        self._item_by_iid.clear()

        for index, item in enumerate(self.items):
            iid = f"i{index}"
            self._item_by_iid[iid] = item
            resolved = item.result.designation if item.result else ""
            if item.status == "review":
                resolved = f"{len(item.candidates)} možností"
            tag = "ready" if item.ready else ("manual" if item.status == "manual" else ("archive" if item.status == "archive" else ("review" if item.status == "review" else "error")))
            self.review_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    item.line_number,
                    item.status_text,
                    item.position,
                    item.quantity,
                    item.designation,
                    resolved,
                    item.message,
                ),
                tags=(tag,),
            )

        if self.review_sort_column:
            self._sort_review_table(self.review_sort_column, self.review_sort_reverse, save=False)

        valid = [iid for iid in selected if self.review_tree.exists(iid)]
        if valid:
            self.review_tree.selection_set(valid)
        if focus and self.review_tree.exists(focus):
            self.review_tree.focus(focus)

        summary = summarize_items(self.items, self.skipped_headers)
        parts = [
            f"{len(self.items)} řádků",
            f"{summary.ready} připraveno",
            f"{summary.review} k doplnění",
            f"{summary.archive} archivní zdroj",
            f"{summary.manual} neřešit / ručně",
            f"{summary.error} nerozpoznáno",
        ]
        if summary.skipped_headers:
            parts.append(f"{summary.skipped_headers} záhlaví přeskočeno")
        self.summary_var.set(" • ".join(parts))

        unresolved = summary.review + summary.archive + summary.error
        if summary.ready:
            if unresolved == 0 and summary.manual == 0:
                self.insert_button_var.set(f"Vložit vše ({summary.ready})")
            elif unresolved == 0:
                self.insert_button_var.set(f"Vložit {summary.ready} • {summary.manual} ručně")
            else:
                self.insert_button_var.set(f"Vložit připravené ({summary.ready})")
            self.insert_button.configure(state="normal")
        elif summary.manual and unresolved == 0:
            self.insert_button_var.set(f"Dokončit • {summary.manual} ručně")
            self.insert_button.configure(state="normal")
        else:
            self.insert_button_var.set("Vložit připravené")
            self.insert_button.configure(state="disabled")

    def _open_archive_source(self) -> None:
        iid = self._active_review_iid()
        item = self._item_by_iid.get(iid or "")
        source = item.archive_source if item is not None else None
        if not source:
            return
        url = str(source.get("source_url", "")).strip()
        if not url:
            return
        pages = source.get("source_pages") or []
        if pages:
            try:
                url += f"#page={int(pages[0])}"
            except Exception:
                pass
        try:
            webbrowser.open(url, new=2)
        except Exception as exc:
            messagebox.showerror("Archivní katalog se nepodařilo otevřít", str(exc), parent=self)

    def _active_review_iid(self) -> str | None:
        focus = self.review_tree.focus()
        if focus and focus in self._item_by_iid:
            return focus
        selected = self.review_tree.selection()
        return selected[0] if selected else None

    def _on_review_selected(self, _event: tk.Event[Any] | None = None) -> None:
        iid = self._active_review_iid()
        if iid:
            self._show_candidates_for(iid)

    def _show_candidates_for(self, iid: str) -> None:
        item = self._item_by_iid.get(iid)
        if item is None:
            return
        for row in self.candidate_tree.get_children(""):
            self.candidate_tree.delete(row)
        self._candidate_by_iid.clear()

        self.candidate_title_var.set(f"Řádek {item.line_number} • {item.position or 'bez pozice'}")
        self.archive_button.configure(state="normal" if item.archive_source and item.archive_source.get("source_url") else "disabled")
        if item.status == "manual":
            self.manual_button.configure(text="Vrátit k řešení", state="normal")
        elif item.ready:
            self.manual_button.configure(text="Neřešit – zadám ručně", state="disabled")
        else:
            self.manual_button.configure(text="Neřešit – zadám ručně", state="normal")
        if item.status == "review":
            self.candidate_hint_var.set(
                item.message + " Vyberte správnou možnost. Dvojklik ji potvrdí pouze pro tento řádek."
            )
        elif item.status == "manual":
            self.candidate_hint_var.set("Řádek je vědomě přeskočený a nebude hromadně vložen. Zadáte jej později ručně. Volbou „Vrátit k řešení“ obnovíte původní stav bez nové analýzy celého výkazu.")
        elif item.ready:
            self.candidate_hint_var.set(item.message)
        else:
            self.candidate_hint_var.set(item.message or "Řádek nebylo možné rozpoznat.")

        values = item.candidates
        if not values and item.result is not None:
            values = [DesignationSuggestion(item.result, 1000.0)]

        for index, suggestion in enumerate(values):
            result = suggestion.result
            candidate_iid = f"c{index}"
            self._candidate_by_iid[candidate_iid] = suggestion
            parameters = " • ".join(
                part
                for part in (
                    f"{selector_value(result, 'manufacturer')} {selector_value(result, 'model')} {selector_value(result, 'type')}",
                    selector_value(result, "moment_class"),
                    selector_value(result, "shear_class"),
                    concrete_label(selector_value(result, "concrete_min")),
                    selector_value(result, "cover"),
                    f"H{selector_value(result, 'height_mm')}",
                    selector_value(result, "insulation"),
                )
                if part and part not in {"—", "H"}
            )
            statics = " | ".join(
                part
                for part in (result.moment_text, result.shear_text, selector_value(result, "compression"))
                if part and part != "—"
            )
            self.candidate_tree.insert(
                "",
                "end",
                iid=candidate_iid,
                values=(result.designation, parameters, statics),
            )

        children = self.candidate_tree.get_children("")
        if children:
            self.candidate_tree.selection_set(children[0])
            self.candidate_tree.focus(children[0])
            self.candidate_tree.see(children[0])

    def _toggle_manual(self) -> None:
        iid = self._active_review_iid()
        item = self._item_by_iid.get(iid or "")
        if item is None or item.ready:
            return

        if item.status == "manual":
            previous = item.manual_previous_status
            if previous not in {"review", "archive", "error"}:
                previous = "archive" if item.archive_source else ("review" if item.candidates else "error")
            item.status = previous
            if item.manual_previous_message:
                item.message = item.manual_previous_message
            elif previous == "archive":
                item.message = "Archivní typ byl vrácen k řešení."
            elif previous == "review":
                item.message = "Řádek byl vrácen k výběru katalogové varianty."
            else:
                item.message = "Řádek byl vrácen k řešení."
            item.manual_previous_status = None
            item.manual_previous_message = ""
        else:
            item.manual_previous_status = item.status
            item.manual_previous_message = item.message
            item.status = "manual"
            item.message = "Neřešit – označeno uživatelem pro následné ruční zadání; hromadný import tento řádek přeskočí."

        self._refresh_review_tree(preserve_selection=True)
        if iid and iid in self._item_by_iid:
            self._show_candidates_for(iid)

    def _chosen_candidate(self) -> DesignationSuggestion | None:
        selected = self.candidate_tree.selection()
        if not selected:
            return None
        return self._candidate_by_iid.get(selected[0])

    @staticmethod
    def _matches_selector_values(result: QueryResult, wanted: dict[str, str]) -> bool:
        return all(selector_value(result, key) == value for key, value in wanted.items())

    def _confirm_item(self, item: BulkImportItem, result: QueryResult, *, bulk: bool = False) -> None:
        item.result = result
        item.status = "confirmed"
        if bulk and item.varying_keys:
            labels = ", ".join(SELECTOR_LABELS[key] for key in item.varying_keys)
            item.message = f"Potvrzeno hromadně podle voleb: {labels}."
        else:
            item.message = "Varianta byla potvrzena uživatelem."

    def _apply_candidate(self, to_marked: bool) -> None:
        active_iid = self._active_review_iid()
        chosen = self._chosen_candidate()
        if not active_iid or chosen is None:
            return
        active = self._item_by_iid.get(active_iid)
        if active is None or not active.candidates:
            return

        if not to_marked:
            self._confirm_item(active, chosen.result)
            self._refresh_review_tree(preserve_selection=True)
            self._show_candidates_for(active_iid)
            return

        selected_iids = list(self.review_tree.selection()) or [active_iid]
        fields = active.varying_keys
        if fields:
            wanted = {key: selector_value(chosen.result, key) for key in fields}
        else:
            wanted = {}

        applied = 0
        skipped = 0
        for iid in selected_iids:
            item = self._item_by_iid.get(iid)
            if item is None or item.status != "review":
                continue
            if iid == active_iid:
                match = chosen
            elif wanted:
                matches = [candidate for candidate in item.candidates if self._matches_selector_values(candidate.result, wanted)]
                match = matches[0] if len(matches) == 1 else None
            else:
                matches = [candidate for candidate in item.candidates if candidate.result.designation == chosen.result.designation]
                match = matches[0] if len(matches) == 1 else None
            if match is None:
                skipped += 1
                continue
            self._confirm_item(item, match.result, bulk=True)
            applied += 1

        self._refresh_review_tree(preserve_selection=True)
        if active_iid in self._item_by_iid:
            self._show_candidates_for(active_iid)
        if skipped:
            messagebox.showinfo(
                "Hromadná volba",
                f"Volba byla použita na {applied} řádků. U {skipped} označených řádků neexistovala právě jedna kompatibilní varianta.",
                parent=self,
            )

    def _insert_ready(self) -> None:
        ready = [item for item in self.items if item.ready and item.result is not None]
        manual = [item for item in self.items if item.status == "manual"]
        unresolved = [item for item in self.items if not item.ready and item.status != "manual"]
        if not ready and not manual:
            return
        if unresolved:
            if not messagebox.askyesno(
                "Nevyřešené řádky",
                f"Zbývá {len(unresolved)} skutečně nevyřešených řádků. Vložit nyní pouze {len(ready)} připravených řádků?",
                parent=self,
            ):
                return
        self.manual_skipped_count = len(manual)
        self.result = [
            {
                "position": item.position,
                "quantity": item.quantity,
                "note": item.note,
                "result": item.result,
                "source_line": item.line_number,
                "source_text": item.raw,
            }
            for item in ready
        ]
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
