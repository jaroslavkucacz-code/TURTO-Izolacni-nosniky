from __future__ import annotations

"""TURTO 2.2.3 – consolidated in-app help and compact main workspace."""

from typing import Any
import tkinter as tk
from tkinter import ttk

HELP_INLINE_PREFIXES = (
    "Jedna AKCE •",
    "PDF je nadřazené produktovým oblastem",
    "Dekodér pracuje se všemi katalogy",
    "Dekódované řádky, záměny",
    "Stačí i část názvu",
    "Dvojklik zobrazí detail dekódovaného nosníku",
    "Stejně jako u izolačních nosníků",
    "Historické Schöck Dorn",
    "Návrh Ancon / Leviat podle tabulované",
    "Stejný princip jako u izolačních nosníků",
    "Požadavek záměny je katalogová",
    "Výběr výrobce je uložen v AKCI",
    "Cílový výrobce je určen nahoře",
)


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _forget(widget: Any) -> None:
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


def _is_inline_help(text: str) -> bool:
    value = str(text or "").strip()
    if any(value.startswith(prefix) for prefix in HELP_INLINE_PREFIXES):
        return True
    if value.startswith("Ancon:") and "Schöck" in value:
        return True
    return False


def compact_inline_help(owner: Any) -> None:
    for widget in _walk(owner):
        try:
            if isinstance(widget, ttk.Label) and _is_inline_help(str(widget.cget("text"))):
                _forget(widget)
        except Exception:
            pass

    source_var = getattr(owner, "hit_source_var", None)
    if source_var is not None:
        target = str(source_var)
        for widget in _walk(owner):
            try:
                if isinstance(widget, ttk.Label) and str(widget.cget("textvariable")) == target:
                    _forget(widget)
            except Exception:
                pass

    decoder = getattr(owner, "project_tab", None)
    if decoder is not None:
        try:
            decoder.grid_rowconfigure(0, minsize=58)
            decoder.grid_rowconfigure(1, minsize=44)
            decoder.grid_rowconfigure(2, minsize=96)
        except Exception:
            pass


def _readonly_text(parent: Any, text: str, owner: Any) -> tk.Text:
    box = tk.Text(
        parent,
        wrap="word",
        font=("Calibri", 11),
        background=owner.colors["panel"],
        foreground=owner.colors["text"],
        insertbackground=owner.colors["text"],
        relief="flat",
        padx=14,
        pady=12,
    )
    box.insert("1.0", text.strip())
    box.configure(state="disabled")
    return box


def _tab(notebook: ttk.Notebook, owner: Any, title: str, text: str) -> None:
    frame = ttk.Frame(notebook, style="App.TFrame", padding=10)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    notebook.add(frame, text=title)
    box = _readonly_text(frame, text, owner)
    bar = ttk.Scrollbar(frame, orient="vertical", command=box.yview)
    box.configure(yscrollcommand=bar.set)
    box.grid(row=0, column=0, sticky="nsew")
    bar.grid(row=0, column=1, sticky="ns")


class HelpDialog(tk.Toplevel):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.title("TURTO – Nápověda")
        self.geometry("1040x740")
        self.minsize(820, 600)
        self.transient(owner)
        self.configure(background=owner.colors["bg"])
        try:
            from ui_utils import place_dialog_on_parent
            place_dialog_on_parent(self, owner)
        except Exception:
            pass

        outer = ttk.Frame(self, style="App.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text="Nápověda TURTO", style="DialogTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        notebook = ttk.Notebook(outer, style="Workspace.TNotebook")
        notebook.grid(row=1, column=0, sticky="nsew")

        _tab(notebook, owner, "Základ", """
TURTO pracuje s jednou společnou AKCÍ. Do stejné AKCE se ukládají dekódované
izolační nosníky, jejich návrhy a záměny i data smykových trnů.

Hlavní postup:
• Dekodér: rozpoznání existujícího označení výrobku.
• Návrh: výběr nového výrobku podle požadovaných účinků a geometrie.
• Záměny: převod známého zdrojového výrobku na vyhovující cílový výrobek.
• Export PDF AKCE: společný výstup z aktivních produktových oblastí.

U tabulek je dvojklik určen pro detail nebo hlavní akci dané tabulky. Enter
potvrzuje běžné dialogy a Escape je zavírá. U našeptávačů lze použít šipku dolů
a Enter.
""")
        _tab(notebook, owner, "Izolační nosníky", """
DEKODÉR
Do pole označení lze psát i část názvu nebo neúplný zápis. Našeptávač nabídne
katalogové varianty. Detail nosníku zachovává katalogové vydání, stránky,
statické hodnoty a další technické údaje.

NÁVRH
Řádky se vkládají pouze uživatelem. Lze zadat jednotlivý prvek nebo vložit
výkaz. Výběr respektuje beton, výšku, krytí, délku a další podmínky dané
rodiny HIT.

ZÁMĚNY
Záměna vychází z katalogových únosností původního prvku, jeho fyzické délky,
izolantu, krytí, výšky a způsobu tlakového přenosu. Automaticky rozpoznaná
geometrie OU/OD se musí podle potřeby potvrdit. Technické zdroje zůstávají
viditelné v Detailu nosníku; nejsou součástí trvalých popisků hlavního okna.
""")
        _tab(notebook, owner, "Smykové trny", """
DEKODÉR
Pole Označení má stejný plovoucí našeptávač jako izolační nosníky. Nabízí
Ancon / Leviat, současný Schöck Stacon a podporovaná historická označení
Schöck Dorn. Šipka dolů otevře návrhy, Enter vybraný návrh doplní.

POHYB
Jednosměrný = podélný posun ve směru osy trnu.
Obousměrný = podélný + příčný posun.
Q varianty jsou obousměrné: např. SLD-Q / LD-Q, ESDQ, HLDQ, DSDQ a DSDSQ.
Historické zápisy SLD-Q 40, SLD Q 40 i SLD 40 Q se interpretují stejně.

NÁVRH A VÝKAZ
Lze zadat jednotlivý VEd v kN/trn nebo vložit výkaz. Hodnota kN/m se
automaticky nesmí zaměnit za kN/trn.

ZÁMĚNY
Cílový výrobce může být Ancon nebo Schöck. Záměna zachovává požadovanou
posuvnost zdrojového trnu a vychází z katalogové VRd při dané geometrii.
""")
        _tab(notebook, owner, "Záměny / PDF", """
Záměny používají katalogové hodnoty původního prvku; nejde pouze o porovnání
aktuálně zadaného zatížení. Když zdrojový katalog neobsahuje jednoznačný údaj
nutný pro technickou záměnu, TURTO výsledek zablokuje nebo označí ke kontrole.

U Schöck Isokorb se některé údaje zapisují kódem výrobce. TURTO převádí pouze
ověřená pravidla pro konkrétní rodiny; neznámé kódy se neodhadují obecně.

Export PDF AKCE je společný výstup nad produktovými oblastmi. Vlastní
technické zdroje, čísla stran a katalogová vydání zůstávají dostupné v detailu
prvku a v technických výstupech.
""")

        hit_source = ""
        try:
            hit_source = str(owner.hit_source_var.get() or "").strip()
        except Exception:
            pass
        catalog_dir = str(getattr(owner, "catalog_dir", "—"))
        source_dir = str(getattr(owner, "source_dir", "—"))
        _tab(notebook, owner, "Data a zdroje", f"""
Katalogová složka:
{catalog_dir}

Složka zdrojových dokumentů:
{source_dir}

Aktuální informace návrhové vrstvy HIT:
{hit_source or "není uvedena / data zatím nebyla načtena"}

Tlačítko „Složka katalogů“ otevře katalogová data. „Kontrola katalogů“
provede kontrolu jejich struktury a návazností. Zdrojové PDF lze otevřít
příslušnou akcí v návrhu, pokud je pro daný katalog dostupné.

Online aktualizace stahuje pouze programové soubory uvedené v ověřeném
manifestu. Databáze AKCÍ actions.sqlite3 je chráněný soubor a běžná
aktualizace ji nesmí přepsat.
""")

        buttons = ttk.Frame(outer, style="App.TFrame")
        buttons.grid(row=2, column=0, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Zavřít", command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())


def show_help(owner: Any) -> None:
    existing = getattr(owner, "_help_dialog", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return
        except Exception:
            pass
    dialog = HelpDialog(owner)
    owner._help_dialog = dialog


def install(app_base: Any) -> None:
    cls = app_base.ThermalConnectorApp
    if getattr(cls, "_turto_help_223_installed", False):
        return
    original_header = cls._build_header

    def header(self) -> None:
        original_header(self)
        master = None
        for widget in _walk(self):
            try:
                if isinstance(widget, ttk.Button) and str(widget.cget("text")) in {"Kontrola katalogů", "Kontrola databáze"}:
                    master = widget.master
                    break
            except Exception:
                pass
        if master is None:
            for widget in _walk(self):
                try:
                    if isinstance(widget, ttk.Button) and str(widget.cget("style")) == "Header.TButton":
                        master = widget.master
                        break
                except Exception:
                    pass
        if master is not None and not hasattr(self, "help_button"):
            columns = []
            for child in master.winfo_children():
                try:
                    if child.winfo_manager() == "grid":
                        columns.append(int(child.grid_info().get("column", 0)))
                except Exception:
                    pass
            column = (max(columns) + 1) if columns else 5
            button = ttk.Button(master, text="Nápověda", style="Header.TButton", command=lambda: show_help(self))
            button.grid(row=0, column=column, rowspan=2, padx=(8, 0))
            self.help_button = button
        compact_inline_help(self)

    cls._build_header = header
    cls.show_help = lambda self: show_help(self)
    cls._turto_help_223_installed = True


def selftest() -> None:
    assert _is_inline_help("PDF je nadřazené produktovým oblastem a zahrnuje nosníky.")
    assert _is_inline_help("Jedna AKCE • více produktových oblastí")
    assert not _is_inline_help("AKCE dosud není uložena")


if __name__ == "__main__":
    selftest()
