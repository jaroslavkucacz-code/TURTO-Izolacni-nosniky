from __future__ import annotations

"""TURTO 2.2.9 – catalog browser for all active product sources."""

from dataclasses import dataclass
import webbrowser
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk


@dataclass(frozen=True)
class CatalogLink:
    domain: str
    manufacturer: str
    title: str
    url: str
    note: str = ""


CATALOGS = (
    CatalogLink(
        "Izolační nosníky",
        "Leviat / HALFEN",
        "HALFEN HIT Insulated Connection – HIT 20.2-EN ©2023",
        "https://www.leviat.com/en-us/mwdownloads/download/link/id/898.pdf",
        "Zdrojový technický katalog používaný pro řadu HIT.",
    ),
    CatalogLink(
        "Smykové trny",
        "Ancon / Leviat",
        "Ancon Shear Load Connectors – DSD / DSDQ a související řady",
        "https://www.leviat.com/en-au/mwdownloads/download/link/id/288.pdf",
        "Aktuální souhrnný katalog Structural Connections se sekcí smykových trnů Ancon.",
    ),
    CatalogLink(
        "Smykové trny",
        "Schöck",
        "Schöck Stacon® – LD / SLD, technické informace a ETA",
        "https://www.schoeck.com/en/stacon",
        "Oficiální stránka obsahuje aktuální technické informace a dokumenty ke stažení.",
    ),
    CatalogLink(
        "Smykové trny",
        "PohlCon",
        "PohlCon HED – Technical Information",
        "https://pohlcon.com/en-de/construction-support/connection/dowels/shear-dowel-hed",
        "Oficiální stránka s aktuálním katalogem HED v němčině a angličtině.",
    ),
    CatalogLink(
        "Smykové trny",
        "PohlCon",
        "PohlCon JDSD / JDSDQ – Technical Information",
        "https://pohlcon.com/en-de/construction-support/connection/dowels/double-shear-dowel-jdsd",
        "Oficiální stránka s technickými informacemi JDSD/JDSDQ a souvisejícími dokumenty.",
    ),
    CatalogLink(
        "Smykové trny",
        "MAX FRANK",
        "MAX FRANK Egcodorn® / Egcodubel – shear force dowels",
        "https://www.maxfrank.com/intl-en/products/reinforcement-technologies/03-shear-force-dowel-egcodorn/",
        "Oficiální produktová stránka s katalogem Egcodorn a dokumenty ke stažení.",
    ),
)


class CatalogBrowser(tk.Toplevel):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.title("Katalogy")
        self.geometry("980x560")
        self.minsize(780, 460)
        self.transient(owner)
        try:
            self.configure(background=owner.colors["bg"])
        except Exception:
            pass

        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Katalogy a technické zdroje", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Z jednoho místa lze otevřít všechny katalogy, ze kterých aktuální program čerpá. Dvojklik otevře vybraný zdroj v prohlížeči.",
            style="Muted.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        table = ttk.Frame(outer, style="Card.TFrame", padding=10)
        table.pack(fill="both", expand=True)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        tree = ttk.Treeview(table, columns=("domain", "manufacturer", "catalog"), show="headings", selectmode="browse")
        tree.heading("domain", text="Oblast")
        tree.heading("manufacturer", text="Výrobce")
        tree.heading("catalog", text="Katalog / zdroj")
        tree.column("domain", width=155, stretch=False)
        tree.column("manufacturer", width=155, stretch=False)
        tree.column("catalog", width=560, stretch=True)
        scroll = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        for index, item in enumerate(CATALOGS):
            tree.insert("", "end", iid=str(index), values=(item.domain, item.manufacturer, item.title))
        self.tree = tree

        self.note_var = tk.StringVar(master=self, value="")
        ttk.Label(outer, textvariable=self.note_var, style="Muted.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=(10, 0))
        buttons = ttk.Frame(outer, style="App.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Zavřít", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Otevřít katalog", style="Accent.TButton", command=self._open_selected).pack(side="right", padx=(0, 8))
        tree.bind("<<TreeviewSelect>>", self._on_select)
        tree.bind("<Double-1>", lambda _event: self._open_selected())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._open_selected())
        if CATALOGS:
            tree.selection_set("0")
            tree.focus("0")
            self._on_select()

    def _selected(self) -> CatalogLink | None:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return CATALOGS[int(selection[0])]
        except Exception:
            return None

    def _on_select(self, _event: Any = None) -> None:
        item = self._selected()
        self.note_var.set(item.note if item else "")

    def _open_selected(self) -> None:
        item = self._selected()
        if item is None:
            return
        try:
            if not webbrowser.open(item.url):
                raise RuntimeError("Systémový prohlížeč odkaz nepřevzal.")
        except Exception as exc:
            messagebox.showerror("Katalog", f"Katalog se nepodařilo otevřít.\n\n{exc}", parent=self)


def open_catalog_browser(owner: Any) -> None:
    dialog = CatalogBrowser(owner)
    owner.wait_window(dialog)


def selftest() -> None:
    assert len(CATALOGS) == 6
    assert {item.manufacturer for item in CATALOGS} >= {"Leviat / HALFEN", "Ancon / Leviat", "Schöck", "PohlCon", "MAX FRANK"}
    assert all(item.url.startswith("https://") for item in CATALOGS)


if __name__ == "__main__":
    selftest()
