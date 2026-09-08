from __future__ import annotations

"""Floating autocomplete for TURTO shear-dowel designations."""

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Any, Callable
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class ShearSuggestion:
    designation: str
    details: str
    aliases: tuple[str, ...] = ()


def _compact(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).upper()
    return re.sub(r"[^A-Z0-9]+", "", text)


def _movement_text(q: bool) -> str:
    return "Obousměrný" if q else "Jednosměrný"


def _build_catalog() -> list[ShearSuggestion]:
    from shear_dowels_catalog import (
        ANCON,
        EHLD,
        SCHOCK_LD_SIZES,
        SLD_SIZES as CURRENT_SLD_SIZES,
        SLDQ_SIZES as CURRENT_SLDQ_SIZES,
    )
    try:
        from historical_schoeck_dorn import SLD_SIZES as HIST_SLD_SIZES
    except Exception:
        HIST_SLD_SIZES = ("40", "50", "60", "70", "80", "120", "150")

    out: list[ShearSuggestion] = []
    seen: set[str] = set()

    def add(designation: str, details: str, *aliases: str) -> None:
        key = _compact(designation)
        if not key or key in seen:
            return
        seen.add(key)
        out.append(ShearSuggestion(designation, details, tuple(aliases)))

    family_sizes: dict[str, list[str]] = {}
    for meta in ANCON.values():
        family = str(meta.get("family", ""))
        size = str(meta.get("size", ""))
        if family and size:
            family_sizes.setdefault(family, []).append(size)
    for family in ("ESD", "HLD", "DSD", "DSDS"):
        sizes = sorted(set(family_sizes.get(family, [])), key=lambda x: int(re.sub(r"\D", "", x) or 0))
        for size in sizes:
            add(
                f"Ancon {family} {size}",
                f"Ancon / Leviat • {family} • Jednosměrný",
                f"{family} {size}",
            )
            q_family = family + "Q"
            add(
                f"Ancon {q_family} {size}",
                f"Ancon / Leviat • {q_family} • Obousměrný",
                f"{family} Q {size}",
                f"{family} {size} Q",
            )
            if family == "ESD":
                add(
                    f"Ancon ED {size}",
                    "Ancon / Leviat • ED • Jednosměrný • plastová objímka",
                    f"ED {size}",
                )

    for size in sorted(EHLD, key=lambda x: int(x)):
        add(
            f"Ancon E-HLD {size}",
            "Ancon / Leviat • E-HLD • Jednosměrný • napojení na stávající stěnu",
            f"E-HLD {size}",
            f"EHLD {size}",
        )

    for size in map(str, SCHOCK_LD_SIZES):
        add(
            f"Schöck Stacon® LD {size}",
            "Schöck Stacon® • LD • Jednosměrný",
            f"LD {size}",
        )
        add(
            f"Schöck Stacon® LD-Q {size}",
            "Schöck Stacon® • LD-Q • Obousměrný",
            f"LD Q {size}",
            f"LD {size} Q",
        )
    for size in map(str, CURRENT_SLD_SIZES):
        add(
            f"Schöck Stacon® SLD {size}",
            "Schöck Stacon® • SLD • Jednosměrný",
            f"SLD {size}",
        )
    for size in map(str, CURRENT_SLDQ_SIZES):
        add(
            f"Schöck Stacon® SLD-Q {size}",
            "Schöck Stacon® • SLD-Q • Obousměrný",
            f"SLD Q {size}",
            f"SLD {size} Q",
        )

    for size in map(str, HIST_SLD_SIZES):
        add(
            f"Schöck Dorn SLD {size}",
            "Schöck Dorn – archiv • SLD • Jednosměrný • archivní VRd",
            f"SLD {size}",
            f"Dorn SLD {size}",
        )
        add(
            f"Schöck Dorn SLD-Q {size}",
            "Schöck Dorn – archiv • SLD-Q • Obousměrný • archivní VRd",
            f"SLD Q {size}",
            f"SLD {size} Q",
            f"Dorn SLD-Q {size}",
        )

    for size in map(str, SCHOCK_LD_SIZES):
        for q in (False, True):
            family = "LD-Q" if q else "LD"
            for sleeve, sleeve_text in (("S", "nerezová objímka"), ("P", "plastová objímka"), ("F", "jednostranná plastová objímka")):
                for material in ("A4", "Zn"):
                    designation = f"Schöck Dorn {family} {size}-{sleeve}-{material}"
                    add(
                        designation,
                        f"Schöck Dorn – archiv • {family} • {_movement_text(q)} • {sleeve_text} • {material}",
                        designation.replace("Schöck Dorn ", ""),
                    )
    return out


_CACHE: list[ShearSuggestion] | None = None


def all_suggestions() -> list[ShearSuggestion]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _build_catalog()
    return list(_CACHE)


def suggest_values(text: str, limit: int = 10) -> list[ShearSuggestion]:
    query = _compact(text)
    if len(query) < 2:
        return []
    scored: list[tuple[float, ShearSuggestion]] = []
    for item in all_suggestions():
        values = (item.designation, *item.aliases)
        compacts = [_compact(value) for value in values]
        best = 0.0
        for value in compacts:
            if not value:
                continue
            if value == query:
                score = 2000.0
            elif value.startswith(query):
                score = 1200.0 - max(0, len(value) - len(query))
            elif query in value:
                score = 900.0 - max(0, len(value) - len(query))
            else:
                score = 300.0 * SequenceMatcher(None, query, value).ratio()
            best = max(best, score)
        if best >= 105.0:
            scored.append((best, item))
    scored.sort(key=lambda x: (-x[0], _compact(x[1].designation)))
    return [item for _score, item in scored[: max(4, int(limit))]]


class ShearAutocomplete:
    def __init__(
        self,
        *,
        entry: ttk.Entry,
        variable: tk.StringVar,
        owner: Any,
        submit_callback: Callable[[], Any] | None = None,
        limit: int = 10,
    ) -> None:
        self.entry = entry
        self.variable = variable
        self.owner = owner
        self.colors = owner.colors
        self.submit_callback = submit_callback
        self.limit = max(4, int(limit))
        self.popup: tk.Toplevel | None = None
        self.tree: ttk.Treeview | None = None
        self.items: dict[str, ShearSuggestion] = {}
        self.after_id: str | None = None
        self.visible = False
        self.suppress = False

        self.trace_id = variable.trace_add("write", self._changed)
        entry.bind("<Down>", self._down, add="+")
        entry.bind("<Return>", self._return, add="+")
        entry.bind("<Escape>", self._escape, add="+")
        entry.bind("<FocusIn>", self._focus, add="+")
        entry.bind("<FocusOut>", self._focus_out, add="+")
        entry.bind("<Configure>", lambda _e: self._reposition(), add="+")

    def _changed(self, *_args: Any) -> None:
        if self.suppress:
            self.suppress = False
            self.hide()
            return
        if self.after_id:
            try:
                self.entry.after_cancel(self.after_id)
            except Exception:
                pass
        try:
            self.after_id = self.entry.after(110, self.refresh)
        except Exception:
            self.after_id = None

    def refresh(self) -> None:
        self.after_id = None
        if not self.entry.winfo_exists():
            return
        values = suggest_values(self.variable.get(), self.limit)
        if not values:
            self.hide()
            return
        query = _compact(self.variable.get())
        if any(_compact(item.designation) == query for item in values):
            self.hide()
            return
        self._show(values)

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
            "ShearSuggest.Treeview",
            font=("Calibri", 10),
            rowheight=28,
            background=self.colors["panel"],
            fieldbackground=self.colors["panel"],
            foreground=self.colors["text"],
            borderwidth=0,
        )
        style.map(
            "ShearSuggest.Treeview",
            background=[("selected", self.colors["accent"])],
            foreground=[("selected", "#FFFFFF")],
        )
        tree = ttk.Treeview(
            frame,
            columns=("designation", "info"),
            show="headings",
            style="ShearSuggest.Treeview",
            selectmode="browse",
            height=8,
        )
        tree.heading("designation", text="Možné označení smykového trnu")
        tree.heading("info", text="Výrobce • řada • pohyb")
        tree.column("designation", width=520, minwidth=360, anchor="w", stretch=True)
        tree.column("info", width=470, minwidth=300, anchor="w", stretch=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tree.bind("<Return>", self._tree_accept)
        tree.bind("<Tab>", self._tree_accept)
        tree.bind("<Escape>", self._tree_escape)
        tree.bind("<ButtonRelease-1>", self._tree_click)
        tree.bind("<FocusOut>", self._focus_out, add="+")
        self.popup = top
        self.tree = tree

    def _show(self, values: list[ShearSuggestion]) -> None:
        self._ensure_popup()
        assert self.popup is not None and self.tree is not None
        self.tree.delete(*self.tree.get_children(""))
        self.items.clear()
        for index, item in enumerate(values):
            iid = f"s{index}"
            self.tree.insert("", "end", iid=iid, values=(item.designation, item.details))
            self.items[iid] = item
        children = self.tree.get_children("")
        self.tree.configure(height=min(10, max(1, len(children))))
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
        self.visible = True
        self._reposition()
        self.popup.deiconify()
        self.popup.lift()

    def _reposition(self) -> None:
        if not self.visible or self.popup is None or not self.popup.winfo_exists():
            return
        try:
            self.entry.update_idletasks()
            self.popup.update_idletasks()
            screen_w = self.entry.winfo_screenwidth()
            screen_h = self.entry.winfo_screenheight()
            x = self.entry.winfo_rootx()
            y_below = self.entry.winfo_rooty() + self.entry.winfo_height() + 2
            width = min(1030, max(760, self.entry.winfo_width() + 500, screen_w // 2))
            height = self.popup.winfo_reqheight()
            x = min(max(5, x), max(5, screen_w - width - 10))
            y = y_below if y_below + height <= screen_h - 40 else max(5, self.entry.winfo_rooty() - height - 2)
            self.popup.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def hide(self) -> None:
        self.visible = False
        if self.popup is not None and self.popup.winfo_exists():
            try:
                self.popup.withdraw()
            except Exception:
                pass

    def _selected(self) -> ShearSuggestion | None:
        if not self.visible or self.tree is None:
            return None
        selected = self.tree.selection()
        iid = selected[0] if selected else self.tree.focus()
        return self.items.get(iid)

    def accept(self) -> bool:
        item = self._selected()
        if item is None:
            return False
        self.suppress = True
        self.variable.set(item.designation)
        self.hide()
        self.entry.focus_set()
        self.entry.icursor("end")
        return True

    def _down(self, _event: Any) -> str | None:
        if not self.visible:
            self.refresh()
        if self.visible and self.tree is not None:
            children = self.tree.get_children("")
            if children:
                self.tree.focus_set()
                self.tree.selection_set(children[0])
                self.tree.focus(children[0])
                return "break"
        return None

    def _return(self, _event: Any) -> str:
        if self.visible and self.accept():
            return "break"
        if self.submit_callback is not None:
            self.submit_callback()
        return "break"

    def _escape(self, _event: Any) -> str | None:
        if self.visible:
            self.hide()
            return "break"
        return None

    def _focus(self, _event: Any) -> None:
        if self.variable.get().strip() and not self.visible and not self.after_id:
            self.after_id = self.entry.after(80, self.refresh)

    def _focus_out(self, _event: Any) -> None:
        try:
            self.entry.after(130, self._hide_if_away)
        except Exception:
            pass

    def _hide_if_away(self) -> None:
        if not self.visible:
            return
        try:
            focus = self.entry.focus_get()
            if focus is self.entry or focus is self.tree:
                return
        except Exception:
            pass
        self.hide()

    def _tree_accept(self, _event: Any) -> str:
        self.accept()
        return "break"

    def _tree_escape(self, _event: Any) -> str:
        self.hide()
        self.entry.focus_set()
        return "break"

    def _tree_click(self, event: Any) -> str | None:
        if self.tree is None:
            return None
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.accept()
            return "break"
        return None


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _entry_for_var(root: Any, variable: tk.StringVar) -> ttk.Entry | None:
    target = str(variable)
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Entry) and str(widget.cget("textvariable")) == target:
                return widget
        except Exception:
            pass
    return None


def attach(owner: Any) -> None:
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return
    old = getattr(owner, "_shear_autocompletes", None)
    if isinstance(old, list):
        for helper in old:
            try:
                helper.hide()
            except Exception:
                pass
    helpers: list[ShearAutocomplete] = []

    decoder_vars = getattr(owner, "shear_decoder_vars", {})
    if isinstance(decoder_vars, dict) and decoder_vars.get("designation") is not None:
        entry = _entry_for_var(notebook, decoder_vars["designation"])
        if entry is not None:
            helpers.append(
                ShearAutocomplete(
                    entry=entry,
                    variable=decoder_vars["designation"],
                    owner=owner,
                    submit_callback=getattr(owner, "add_shear_decoder_row", None),
                )
            )

    substitution_vars = getattr(owner, "shear_substitution_vars", {})
    if isinstance(substitution_vars, dict) and substitution_vars.get("source") is not None:
        entry = _entry_for_var(notebook, substitution_vars["source"])
        if entry is not None:
            helpers.append(
                ShearAutocomplete(
                    entry=entry,
                    variable=substitution_vars["source"],
                    owner=owner,
                    submit_callback=getattr(owner, "add_shear_substitution_row", None),
                )
            )
    owner._shear_autocompletes = helpers


def selftest() -> None:
    global _CACHE
    original = _CACHE
    try:
        _CACHE = [
            ShearSuggestion("Schöck Dorn SLD 40", "Jednosměrný", ("SLD 40",)),
            ShearSuggestion("Schöck Dorn SLD-Q 40", "Obousměrný", ("SLD Q 40", "SLD 40 Q")),
            ShearSuggestion("Ancon HLDQ 22", "Obousměrný", ("HLD 22 Q",)),
            ShearSuggestion("Ancon E-HLD 22", "Jednosměrný", ("EHLD 22",)),
        ]
        results = suggest_values("SLD 40", 10)
        names = {item.designation for item in results}
        assert "Schöck Dorn SLD 40" in names
        assert "Schöck Dorn SLD-Q 40" in names
        assert suggest_values("SLD 40 Q", 4)[0].designation == "Schöck Dorn SLD-Q 40"
        assert all("E-HLDQ" not in item.designation for item in all_suggestions())
    finally:
        _CACHE = original


if __name__ == "__main__":
    selftest()
