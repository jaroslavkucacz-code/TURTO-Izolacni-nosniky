from __future__ import annotations

"""TURTO 2.2.10 – local PDF catalog library for active product sources."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
import urllib.request
import tkinter as tk
from tkinter import messagebox, ttk


CATALOG_ROOT = Path(__file__).resolve().parent / "Katalogy"


@dataclass(frozen=True)
class CatalogLink:
    domain: str
    manufacturer: str
    title: str
    relative_path: str
    source_url: str
    note: str = ""

    @property
    def local_path(self) -> Path:
        return CATALOG_ROOT / Path(self.relative_path)


CATALOGS = (
    CatalogLink(
        "Izolační nosníky",
        "Leviat / HALFEN",
        "HALFEN HIT Insulated Connection – HIT 20.2-EN ©2023",
        "Izolacni_nosniky/Leviat_HALFEN/HALFEN_HIT_20.2-EN_2023.pdf",
        "https://www.leviat.com/en-us/mwdownloads/download/link/id/898.pdf",
        "Zdrojový technický katalog používaný pro řadu HIT.",
    ),
    CatalogLink(
        "Smykové trny",
        "Ancon / Leviat",
        "Ancon DSD / DSDQ – Shear Load Connectors",
        "Smykove_trny/Ancon_Leviat/Ancon_DSD_DSDQ_Shear_Load_Connectors.pdf",
        "https://www.ancon.com.au/downloads/1975/Leviat_Ancon_AUS%20Shear%20Load%20Br%20July%202023.1.pdf",
        "Technický katalog smykových trnů Ancon DSD / DSDQ.",
    ),
    CatalogLink(
        "Smykové trny",
        "Schöck",
        "Schöck Stacon® – LD / SLD Technical Information",
        "Smykove_trny/Schoeck/Schoeck_Stacon_LD_SLD_Technical_Information.pdf",
        "https://www.schoeck.com/viewfile/3921/Technical_Information_Schoeck_Stacon_UK_Version___3921__.pdf",
        "Technické informace pro smykové trny Schöck Stacon® LD / SLD.",
    ),
    CatalogLink(
        "Smykové trny",
        "PohlCon",
        "PohlCon HED – Technical Information",
        "Smykove_trny/PohlCon/PohlCon_HED_Technical_Information.pdf",
        "https://pohlcon.com/fileadmin/crossbase/DOK/PRO/TI/DOK_PRO_TI_HED_%23SDE_%23AING.pdf",
        "Technické informace pro smykové trny HED.",
    ),
    CatalogLink(
        "Smykové trny",
        "PohlCon",
        "PohlCon JDSD / JDSDQ – Technical Information",
        "Smykove_trny/PohlCon/PohlCon_JDSD_JDSDQ_Technical_Information.pdf",
        "https://pohlcon.com/fileadmin/user_upload/jordahl-group.com/downloads/Broschueren/EN/PC-LIT-TI-JDSD-EN.pdf",
        "Technické informace JDSD / JDSDQ.",
    ),
    CatalogLink(
        "Smykové trny",
        "MAX FRANK",
        "MAX FRANK Egcodorn® / Egcodubel – Shear force dowels",
        "Smykove_trny/MAX_FRANK/MAX_FRANK_Egcodorn_Egcodubel.pdf",
        "https://www.maxfrank.com/wAssets/docs/products/brochures/egcodorn-01-shear-force-dowel-expansion-joints-BR-INTGB.pdf",
        "Technický katalog Egcodorn® / Egcodubel pro dilatační spáry.",
    ),
)


def _open_path(path: Path) -> None:
    path = path.resolve()
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def _download_catalog(item: CatalogLink) -> Path:
    destination = item.local_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    try:
        request = urllib.request.Request(
            item.source_url,
            headers={
                "User-Agent": "TURTO-2.2.10-CatalogLibrary",
                "Accept": "application/pdf,*/*;q=0.8",
                "Cache-Control": "no-cache",
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as handle:
            first = response.read(8)
            if not first.startswith(b"%PDF-"):
                content_type = str(response.headers.get("Content-Type", "") or "")
                raise RuntimeError(
                    "Zdroj nevrátil PDF soubor"
                    + (f" (Content-Type: {content_type})." if content_type else ".")
                )
            handle.write(first)
            shutil.copyfileobj(response, handle, length=1024 * 1024)
        os.replace(temporary, destination)
        return destination
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        raise


class CatalogBrowser(tk.Toplevel):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.title("Katalogy")
        self.geometry("1040x590")
        self.minsize(820, 480)
        self.transient(owner)
        try:
            self.configure(background=owner.colors["bg"])
        except Exception:
            pass

        CATALOG_ROOT.mkdir(parents=True, exist_ok=True)

        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Lokální knihovna katalogů", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Katalogy se otevírají přímo jako PDF z disku. "
                "Pokud PDF ještě není uloženo, program nabídne jeho jednorázové stažení "
                "do přehledné složky Katalogy; webová stránka se neotevírá."
            ),
            style="Muted.TLabel",
            wraplength=960,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        table = ttk.Frame(outer, style="Card.TFrame", padding=10)
        table.pack(fill="both", expand=True)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        tree = ttk.Treeview(
            table,
            columns=("domain", "manufacturer", "catalog", "status"),
            show="headings",
            selectmode="browse",
        )
        tree.heading("domain", text="Oblast")
        tree.heading("manufacturer", text="Výrobce")
        tree.heading("catalog", text="Katalog")
        tree.heading("status", text="Lokálně")
        tree.column("domain", width=150, stretch=False)
        tree.column("manufacturer", width=150, stretch=False)
        tree.column("catalog", width=545, stretch=True)
        tree.column("status", width=95, anchor="center", stretch=False)
        scroll = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree = tree
        for index, item in enumerate(CATALOGS):
            tree.insert("", "end", iid=str(index), values=self._row_values(item))

        self.note_var = tk.StringVar(master=self, value="")
        ttk.Label(
            outer,
            textvariable=self.note_var,
            style="Muted.TLabel",
            wraplength=960,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(outer, style="App.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Zavřít", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Otevřít katalog",
            style="Accent.TButton",
            command=self._open_selected,
        ).pack(side="right", padx=(0, 8))
        ttk.Button(
            buttons,
            text="Otevřít složku katalogů",
            command=self._open_catalog_folder,
        ).pack(side="left")

        tree.bind("<<TreeviewSelect>>", self._on_select)
        tree.bind("<Double-1>", lambda _event: self._open_selected())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._open_selected())
        if CATALOGS:
            tree.selection_set("0")
            tree.focus("0")
            self._on_select()

    @staticmethod
    def _row_values(item: CatalogLink) -> tuple[str, str, str, str]:
        return (
            item.domain,
            item.manufacturer,
            item.title,
            "ANO" if item.local_path.is_file() else "CHYBÍ",
        )

    def _selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except Exception:
            return None

    def _selected(self) -> CatalogLink | None:
        index = self._selected_index()
        if index is None:
            return None
        try:
            return CATALOGS[index]
        except Exception:
            return None

    def _refresh_selected_row(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        try:
            item = CATALOGS[index]
            self.tree.item(str(index), values=self._row_values(item))
        except Exception:
            pass

    def _on_select(self, _event: Any = None) -> None:
        item = self._selected()
        if item is None:
            self.note_var.set("")
            return
        self.note_var.set(
            f"{item.note}\nLokální PDF: {item.local_path}"
        )

    def _open_catalog_folder(self) -> None:
        try:
            CATALOG_ROOT.mkdir(parents=True, exist_ok=True)
            _open_path(CATALOG_ROOT)
        except Exception as exc:
            messagebox.showerror(
                "Katalogy",
                f"Složku katalogů se nepodařilo otevřít.\n\n{exc}",
                parent=self,
            )

    def _open_selected(self) -> None:
        item = self._selected()
        if item is None:
            return
        path = item.local_path

        if not path.is_file():
            download = messagebox.askyesno(
                "Katalog není uložen",
                (
                    "Tento katalog ještě není v lokální knihovně.\n\n"
                    f"Uloží se do:\n{path}\n\n"
                    "Stáhnout nyní PDF z oficiálního zdroje výrobce?"
                ),
                parent=self,
            )
            if not download:
                return
            try:
                self.configure(cursor="watch")
                self.update_idletasks()
                path = _download_catalog(item)
                self._refresh_selected_row()
                self._on_select()
            except Exception as exc:
                messagebox.showerror(
                    "Katalog",
                    (
                        "PDF se nepodařilo uložit do lokální knihovny.\n\n"
                        f"{exc}\n\n"
                        f"Soubor lze případně ručně vložit sem:\n{item.local_path}"
                    ),
                    parent=self,
                )
                return
            finally:
                try:
                    self.configure(cursor="")
                except Exception:
                    pass

        try:
            _open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Katalog",
                f"Katalog se nepodařilo otevřít.\n\n{exc}",
                parent=self,
            )


def open_catalog_browser(owner: Any) -> None:
    dialog = CatalogBrowser(owner)
    owner.wait_window(dialog)


def selftest() -> None:
    assert len(CATALOGS) == 6
    assert {item.manufacturer for item in CATALOGS} >= {
        "Leviat / HALFEN",
        "Ancon / Leviat",
        "Schöck",
        "PohlCon",
        "MAX FRANK",
    }
    assert all(item.source_url.startswith("https://") for item in CATALOGS)
    assert all(Path(item.relative_path).suffix.lower() == ".pdf" for item in CATALOGS)
    assert all(".." not in Path(item.relative_path).parts for item in CATALOGS)


if __name__ == "__main__":
    selftest()
