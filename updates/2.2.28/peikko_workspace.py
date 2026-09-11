from __future__ import annotations

"""TURTO 2.2.28 Peikko EBEA / TEBEA workspace integration."""

from typing import Any
import tkinter as tk
from tkinter import ttk

from peikko_thermal_breaks import (
    DESIGN_STATUS,
    MODEL_SPECS,
    ROLE_HORIZONTAL,
    ROLE_LABELS,
    ROLE_MOMENT_SHEAR,
    ROLE_NONLOAD,
    ROLE_OTHER,
    ROLE_SHEAR,
    compatible_models,
    decode_peikko,
    format_decode,
    proposal_models,
)

WORKSPACE_VERSION = "2.2.28"
_INSTALLED = False

ROLE_ORDER = (
    ROLE_MOMENT_SHEAR,
    ROLE_SHEAR,
    ROLE_HORIZONTAL,
    ROLE_OTHER,
    ROLE_NONLOAD,
)
ROLE_BY_LABEL = {ROLE_LABELS[role]: role for role in ROLE_ORDER}


def _safe_set_text(widget: tk.Text, text: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")


def _insulation_text(values: tuple[int, ...]) -> str:
    return " / ".join(str(v) for v in values) + " mm"


def _build_decoder(owner: Any, parent: ttk.Frame) -> None:
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(2, weight=1)

    card = ttk.Frame(parent, style="Card.TFrame", padding=12)
    card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    card.columnconfigure(1, weight=1)

    ttk.Label(
        card,
        text="Dekodér Peikko EBEA / TEBEA",
        style="Card.TLabel",
        font=("Calibri", 11, "bold"),
    ).grid(row=0, column=0, columnspan=3, sticky="w")

    ttk.Label(card, text="Označení:", style="Card.TLabel").grid(
        row=1, column=0, sticky="w", pady=(10, 0)
    )
    owner.peikko_decode_var = tk.StringVar(value="")
    entry = ttk.Entry(card, textvariable=owner.peikko_decode_var, font=("Calibri", 10))
    entry.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(10, 0))
    ttk.Button(
        card,
        text="Dekódovat",
        style="Accent.TButton",
        command=lambda: _decode_action(owner),
    ).grid(row=1, column=2, pady=(10, 0))
    entry.bind("<Return>", lambda _event: _decode_action(owner))

    examples = (
        "Příklady: EBEA-100 … · EBEA E-900 … · EBEA Type G · "
        "TEBEA CM-V … · TEBEA PVV-S … · TEBEA EA / EH / ES / N"
    )
    ttk.Label(
        card,
        text=examples,
        style="MutedCard.TLabel",
        wraplength=1000,
        justify="left",
    ).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    owner.peikko_decode_status_var = tk.StringVar(
        value="Zadejte označení EBEA nebo TEBEA."
    )
    ttk.Label(parent, textvariable=owner.peikko_decode_status_var).grid(
        row=1, column=0, sticky="ew", pady=(0, 6)
    )

    text = tk.Text(
        parent,
        height=14,
        wrap="word",
        font=("Calibri", 10),
        relief="flat",
        padx=12,
        pady=10,
    )
    text.grid(row=2, column=0, sticky="nsew")
    text.configure(state="disabled")
    owner.peikko_decode_text = text


def _decode_action(owner: Any) -> None:
    raw = str(owner.peikko_decode_var.get()).strip()
    decoded = decode_peikko(raw)
    if decoded is None:
        owner.peikko_decode_status_var.set(
            "Označení nebylo rozpoznáno jako podporovaný typ Peikko EBEA / TEBEA."
        )
        _safe_set_text(
            owner.peikko_decode_text,
            "Podporované jsou modelové řady EBEA 100–1200, E-100, E-900, Type G "
            "a aktuální modely TEBEA CM/PM/RM, PV/PVV/V, LM, EA/EH/ES/N.",
        )
        owner._peikko_last_decoded = None
        return
    owner._peikko_last_decoded = decoded
    owner.peikko_decode_status_var.set(
        f"{decoded.canonical} · {ROLE_LABELS.get(decoded.role, decoded.role)} · {decoded.status}"
    )
    _safe_set_text(owner.peikko_decode_text, format_decode(decoded))


def _build_substitution(owner: Any, parent: ttk.Frame) -> None:
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(2, weight=1)

    card = ttk.Frame(parent, style="Card.TFrame", padding=12)
    card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    card.columnconfigure(1, weight=1)
    ttk.Label(
        card,
        text="Funkční kandidáti záměny Peikko",
        style="Card.TLabel",
        font=("Calibri", 11, "bold"),
    ).grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(card, text="Výchozí označení:", style="Card.TLabel").grid(
        row=1, column=0, sticky="w", pady=(10, 0)
    )
    owner.peikko_sub_var = tk.StringVar(value="")
    entry = ttk.Entry(card, textvariable=owner.peikko_sub_var, font=("Calibri", 10))
    entry.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(10, 0))
    ttk.Button(
        card,
        text="Najít kandidáty",
        style="Accent.TButton",
        command=lambda: _substitution_action(owner),
    ).grid(row=1, column=2, pady=(10, 0))
    entry.bind("<Return>", lambda _event: _substitution_action(owner))

    owner.peikko_sub_status_var = tk.StringVar(
        value=(
            "Zobrazí se pouze stejná konzervativní funkční skupina ve stejné rodině. "
            "Nejde o staticky potvrzenou záměnu."
        )
    )
    ttk.Label(
        parent,
        textvariable=owner.peikko_sub_status_var,
        wraplength=1100,
        justify="left",
    ).grid(row=1, column=0, sticky="ew", pady=(0, 6))

    columns = ("model", "function", "insulation", "status")
    tree = ttk.Treeview(parent, columns=columns, show="headings", height=12)
    tree.heading("model", text="Kandidát")
    tree.heading("function", text="Funkce")
    tree.heading("insulation", text="Izolant")
    tree.heading("status", text="Stav")
    tree.column("model", width=190, anchor="w")
    tree.column("function", width=180, anchor="center")
    tree.column("insulation", width=120, anchor="center")
    tree.column("status", width=330, anchor="w")
    tree.grid(row=2, column=0, sticky="nsew")
    owner.peikko_sub_tree = tree


def _substitution_action(owner: Any) -> None:
    tree = owner.peikko_sub_tree
    for item in tree.get_children():
        tree.delete(item)

    raw = str(owner.peikko_sub_var.get()).strip()
    decoded = decode_peikko(raw)
    if decoded is None:
        owner.peikko_sub_status_var.set(
            "Výchozí označení nebylo rozpoznáno jako Peikko EBEA / TEBEA."
        )
        return

    candidates = compatible_models(decoded)
    if not candidates:
        owner.peikko_sub_status_var.set(
            f"{decoded.canonical}: v databázi není jiný typ se stejnou konzervativní "
            "funkční skupinou. Program proto žádnou automatickou záměnu nenabízí."
        )
        return

    for spec in candidates:
        tree.insert(
            "",
            "end",
            values=(
                spec.canonical,
                ROLE_LABELS.get(spec.role, spec.role),
                _insulation_text(spec.insulation_mm),
                "Funkčně kompatibilní kandidát – staticky ověřit",
            ),
        )
    owner.peikko_sub_status_var.set(
        f"{decoded.canonical}: nalezeno {len(candidates)} funkčně kompatibilních kandidátů. "
        "Únosnost, geometrii, krytí a národní podklady je nutné ověřit."
    )


def _build_design(owner: Any, parent: ttk.Frame) -> None:
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(2, weight=1)

    warning = ttk.Frame(parent, style="Card.TFrame", padding=12)
    warning.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    warning.columnconfigure(5, weight=1)

    ttk.Label(
        warning,
        text="Předvýběr návrhu EBEA / TEBEA",
        style="Card.TLabel",
        font=("Calibri", 11, "bold"),
    ).grid(row=0, column=0, columnspan=7, sticky="w")

    ttk.Label(warning, text="Rodina:", style="Card.TLabel").grid(
        row=1, column=0, sticky="w", pady=(10, 0)
    )
    owner.peikko_design_family_var = tk.StringVar(value="TEBEA")
    family = ttk.Combobox(
        warning,
        textvariable=owner.peikko_design_family_var,
        values=("EBEA", "TEBEA"),
        state="readonly",
        width=10,
        justify="center",
    )
    family.grid(row=1, column=1, sticky="w", padx=(6, 14), pady=(10, 0))

    ttk.Label(warning, text="Funkce:", style="Card.TLabel").grid(
        row=1, column=2, sticky="w", pady=(10, 0)
    )
    owner.peikko_design_role_var = tk.StringVar(value=ROLE_LABELS[ROLE_MOMENT_SHEAR])
    role = ttk.Combobox(
        warning,
        textvariable=owner.peikko_design_role_var,
        values=tuple(ROLE_LABELS[r] for r in ROLE_ORDER),
        state="readonly",
        width=22,
    )
    role.grid(row=1, column=3, sticky="w", padx=(6, 14), pady=(10, 0))

    ttk.Label(warning, text="Izolant:", style="Card.TLabel").grid(
        row=1, column=4, sticky="w", pady=(10, 0)
    )
    owner.peikko_design_insulation_var = tk.StringVar(value="120")
    insulation = ttk.Combobox(
        warning,
        textvariable=owner.peikko_design_insulation_var,
        values=("80", "120"),
        state="readonly",
        width=7,
        justify="center",
    )
    insulation.grid(row=1, column=5, sticky="w", padx=(6, 14), pady=(10, 0))

    ttk.Button(
        warning,
        text="Předvybrat typy",
        style="Accent.TButton",
        command=lambda: _design_action(owner),
    ).grid(row=1, column=6, sticky="e", pady=(10, 0))

    owner.peikko_design_status_var = tk.StringVar(
        value=(
            "Bez ověřené databáze únosností Peikko program nepočítá využití ani "
            "neoznačuje žádný typ jako staticky vyhovující."
        )
    )
    ttk.Label(
        parent,
        textvariable=owner.peikko_design_status_var,
        wraplength=1100,
        justify="left",
    ).grid(row=1, column=0, sticky="ew", pady=(0, 6))

    columns = ("model", "function", "insulation", "description", "status")
    tree = ttk.Treeview(parent, columns=columns, show="headings", height=12)
    for key, title in (
        ("model", "Typ"),
        ("function", "Funkce"),
        ("insulation", "Izolant"),
        ("description", "Použití"),
        ("status", "Výsledek / kontrola"),
    ):
        tree.heading(key, text=title)
    tree.column("model", width=150, anchor="w")
    tree.column("function", width=160, anchor="center")
    tree.column("insulation", width=95, anchor="center")
    tree.column("description", width=440, anchor="w")
    tree.column("status", width=280, anchor="w")
    tree.grid(row=2, column=0, sticky="nsew")
    owner.peikko_design_tree = tree

    family.bind("<<ComboboxSelected>>", lambda _e: _sync_design_insulation(owner))
    _sync_design_insulation(owner)


def _sync_design_insulation(owner: Any) -> None:
    family = str(owner.peikko_design_family_var.get()).strip().upper()
    if family == "TEBEA":
        owner.peikko_design_insulation_var.set("120")
    elif str(owner.peikko_design_insulation_var.get()) not in {"80", "120"}:
        owner.peikko_design_insulation_var.set("80")


def _design_action(owner: Any) -> None:
    tree = owner.peikko_design_tree
    for item in tree.get_children():
        tree.delete(item)

    family = str(owner.peikko_design_family_var.get()).strip().upper()
    role_label = str(owner.peikko_design_role_var.get()).strip()
    role = ROLE_BY_LABEL.get(role_label)
    if role is None:
        owner.peikko_design_status_var.set("Nebyla zvolena podporovaná funkce.")
        return
    try:
        insulation_mm = int(str(owner.peikko_design_insulation_var.get()).strip())
    except ValueError:
        owner.peikko_design_status_var.set("Neplatná tloušťka izolantu.")
        return

    candidates = proposal_models(
        family=family,
        role=role,
        insulation_mm=insulation_mm,
    )
    for spec in candidates:
        tree.insert(
            "",
            "end",
            values=(
                spec.canonical,
                ROLE_LABELS.get(spec.role, spec.role),
                _insulation_text(spec.insulation_mm),
                spec.description,
                DESIGN_STATUS,
            ),
        )

    if not candidates:
        owner.peikko_design_status_var.set(
            f"{family}: pro funkci „{role_label}“ a izolant {insulation_mm} mm "
            "není v této datové vrstvě žádný model."
        )
    else:
        owner.peikko_design_status_var.set(
            f"{family}: předvybráno {len(candidates)} modelů podle funkce a izolantu. "
            "Jde pouze o předvýběr; únosnost a geometrie nejsou v 2.2.28 vyhodnoceny."
        )


def _build_workspace(owner: Any) -> None:
    notebook = getattr(owner, "main_notebook", None)
    if notebook is None:
        return

    tab = ttk.Frame(notebook, style="App.TFrame", padding=(0, 12, 0, 0))
    owner.peikko_tab = tab
    notebook.add(tab, text="Peikko EBEA / TEBEA")
    tab.columnconfigure(0, weight=1)
    tab.rowconfigure(1, weight=1)

    banner = ttk.Frame(tab, style="Card.TFrame", padding=(12, 9))
    banner.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    banner.columnconfigure(1, weight=1)
    ttk.Label(
        banner,
        text="Peikko · EBEA / TEBEA",
        style="Card.TLabel",
        font=("Calibri", 11, "bold"),
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        banner,
        text=(
            "Dekódování a funkční předvýběr jsou aktivní. Statické únosnosti se "
            "záměrně nepředpokládají; každý výsledek vyžaduje ověření podle "
            "příslušných národních podkladů Peikko."
        ),
        style="MutedCard.TLabel",
        wraplength=940,
        justify="left",
    ).grid(row=0, column=1, sticky="ew", padx=(14, 0))

    sub = ttk.Notebook(tab, style="Workspace.TNotebook")
    sub.grid(row=1, column=0, sticky="nsew")
    owner.peikko_notebook = sub

    decoder = ttk.Frame(sub, style="App.TFrame", padding=(8, 8))
    substitution = ttk.Frame(sub, style="App.TFrame", padding=(8, 8))
    design = ttk.Frame(sub, style="App.TFrame", padding=(8, 8))
    sub.add(decoder, text="Dekodér")
    sub.add(substitution, text="Záměny")
    sub.add(design, text="Návrh / předvýběr")

    _build_decoder(owner, decoder)
    _build_substitution(owner, substitution)
    _build_design(owner, design)


def _append_header_info(owner: Any) -> None:
    stack = [owner]
    while stack:
        widget = stack.pop()
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            continue
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text"))
                if (
                    text.startswith("Jedna AKCE • Dekodér ISO")
                    and "Peikko EBEA/TEBEA" not in text
                ):
                    widget.configure(text=text + " • Peikko EBEA/TEBEA")
        except Exception:
            pass


def _api_decode(_owner: Any, text: str):
    return decode_peikko(text)


def _api_substitutions(_owner: Any, text: str):
    decoded = decode_peikko(text)
    return compatible_models(decoded) if decoded is not None else ()


def _api_design_candidates(
    _owner: Any,
    *,
    family: str,
    role: str,
    insulation_mm: int | None = None,
):
    return proposal_models(
        family=family,
        role=role,
        insulation_mm=insulation_mm,
    )


def install(base_module: Any) -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    app_cls = base_module.ThermalConnectorApp
    original_build_body = app_cls._build_body

    def _build_body_with_peikko(self) -> None:
        original_build_body(self)
        _build_workspace(self)
        _append_header_info(self)

    app_cls._build_body = _build_body_with_peikko
    app_cls.decode_peikko_product = _api_decode
    app_cls.peikko_substitution_candidates = _api_substitutions
    app_cls.peikko_design_candidates = _api_design_candidates
    _INSTALLED = True


def selftest() -> None:
    assert WORKSPACE_VERSION == "2.2.28"
    assert len(MODEL_SPECS) == 33
    assert decode_peikko("EBEA-100") is not None
    assert decode_peikko("TEBEA CM-V") is not None
    assert decode_peikko("HIT-HP MVX") is None


if __name__ == "__main__":
    selftest()
