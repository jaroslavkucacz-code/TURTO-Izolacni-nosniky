from __future__ import annotations

"""Peikko inside the SAME decoder, design and substitution workspace.

Adapters are installed before Tk widgets are built. Manufacturer changes hide
only the existing manufacturer's controls, not its data. Shared project rows
and platform selection use the existing central AKCE serialization.
"""
from dataclasses import replace
from functools import wraps
from typing import Any
import tkinter as tk
from tkinter import ttk, messagebox

from peikko_thermal_breaks import (
    decode_peikko, normalize_bulk_text, is_peikko, format_decode, proposal_models,
    compatible_models, ROLE_LABELS, ROLE_MOMENT_SHEAR, DESIGN_STATUS,
)
from peikko_catalog import catalog_class, CATALOG_ID, BLOCK_REASON, make_result

WORKSPACE_VERSION = "2.2.29"


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _is_source(row):
    return (row.get("selection", {}).get("catalog_id") == CATALOG_ID
            or is_peikko(row.get("snapshot", {}).get("designation", "")))


def _install_bulk():
    import bulk_import_engine as engine
    import bulk_import
    original = engine.analyze_bulk_text_progressive
    @wraps(original)
    def analyze(database, text, **kwargs):
        return original(database, normalize_bulk_text(text), **kwargs)
    engine.analyze_bulk_text_progressive = analyze
    bulk_import.analyze_bulk_text_progressive = analyze
    classify = engine._classify_bulk_item
    @wraps(classify)
    def classify_item(database, item, **kwargs):
        if not is_peikko(item.designation):
            return classify(database, item, **kwargs)
        try:
            item.result = database.resolve_designation(item.designation,
                preferred_concrete=kwargs.get("preferred_concrete"))
            d = decode_peikko(item.designation)
            item.status = "exact"  # exact syntax, NOT confirmed structural capacity
            item.message = DESIGN_STATUS
            if d.position_reference:
                item.note = " | ".join(x for x in (item.note, "Reference: " + d.position_reference) if x)
        except ValueError as exc:
            item.result = None
            item.status = "error"
            item.message = str(exc)
    engine._classify_bulk_item = classify_item
    # Avoid destructive Egcobox-specific suffix preprocessing for Peikko.
    preprocess = engine.preprocess_bulk_designation
    def peikko_preprocess(designation, note=""):
        return (str(designation).strip(), note) if is_peikko(designation) else preprocess(designation, note)
    engine.preprocess_bulk_designation = peikko_preprocess
    import project_ui_base
    project_ui_base.preprocess_bulk_designation = peikko_preprocess


def _install_guards():
    import substitution_workspace as sw
    original = sw.design_targets
    @wraps(original)
    def design_targets(database, *, row, metadata, **kwargs):
        if _is_source(row):
            return [], [BLOCK_REASON]
        return original(database, row=row, metadata=metadata, **kwargs)
    sw.design_targets = design_targets
    previous_meta = sw.source_metadata
    @wraps(previous_meta)
    def metadata(row):
        result = previous_meta(row)
        if _is_source(row):
            result["substitution_policy"] = "manual"
            result["substitution_note"] = BLOCK_REASON
            result["errors"] = [BLOCK_REASON]
            result["warnings"] = list(dict.fromkeys([*result.get("warnings", []),
                "Ds/Dt, S11, B2 a OQ jsou zachovány; nepředstavují ověřené návrhové parametry."]))
        return result
    sw.source_metadata = metadata


def _selected_source(owner):
    selected = list(owner.project_tree.selection()) if hasattr(owner, "project_tree") else []
    for row in getattr(getattr(owner, "project", None), "rows", []):
        if row.get("id") in selected:
            return row
    return None


def _set_text(widget, text):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")


def _build_panel(owner, parent, mode):
    panel = ttk.Frame(parent, style="App.TFrame", padding=12)
    panel.columnconfigure(1, weight=1)
    panel.rowconfigure(6, weight=1)
    values = {"family": tk.StringVar(master=owner, value="EBEA"),
              "role": tk.StringVar(master=owner, value=ROLE_LABELS[ROLE_MOMENT_SHEAR]),
              "sw": tk.StringVar(master=owner, value="80"),
              "designation": tk.StringVar(master=owner, value="")}
    ttk.Label(panel, text="Peikko EBEA / TEBEA – rozpoznání a předvýběr, nikoli statické posouzení",
              font=("Calibri", 11, "bold"), wraplength=1050).grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(panel, text="Řada / funkce / izolant:").grid(row=1, column=0, sticky="w", pady=10)
    selectors = ttk.Frame(panel)
    selectors.grid(row=1, column=1, columnspan=2, sticky="w")
    family = ttk.Combobox(selectors, textvariable=values["family"], values=("EBEA", "TEBEA"), state="readonly", width=10)
    family.pack(side="left", padx=(0, 8))
    ttk.Combobox(selectors, textvariable=values["role"], values=tuple(ROLE_LABELS.values()),
                 state="readonly", width=24).pack(side="left", padx=(0, 8))
    sw = ttk.Combobox(selectors, textvariable=values["sw"], values=("80", "120"), state="readonly", width=8)
    sw.pack(side="left")
    def family_changed(*_):
        sw.configure(values=("120",) if values["family"].get() == "TEBEA" else ("80", "120"))
        if values["family"].get() == "TEBEA":
            values["sw"].set("120")
    family.bind("<<ComboboxSelected>>", family_changed)
    ttk.Label(panel, text="Úplné označení (má přednost):").grid(row=2, column=0, sticky="w")
    entry = ttk.Entry(panel, textvariable=values["designation"], font=("Calibri", 10))
    entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)
    buttons = ttk.Frame(panel)
    buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
    output = tk.Text(panel, font=("Calibri", 10), wrap="word", height=14, relief="flat",
                     bg=owner.colors["panel"], fg=owner.colors["text"], padx=12, pady=10)
    output.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=8)
    scroll = ttk.Scrollbar(panel, command=output.yview)
    scroll.grid(row=6, column=2, sticky="ns")
    output.configure(yscrollcommand=scroll.set)
    _set_text(output, BLOCK_REASON + "\nZvolte funkci nebo převezměte označení z Dekodéru.")
    def show():
        try:
            text = values["designation"].get().strip()
            if text:
                d = decode_peikko(text)
                if d is None:
                    raise ValueError("Označení není podporovaný typ EBEA/TEBEA.")
                action_concrete = owner.project_concrete_var.get()
                make_result(text, action_concrete)  # enforce explicit concrete mismatch
                detail = format_decode(d)
                if mode == "substitution":
                    detail += "\n\n" + BLOCK_REASON + "\nShodná řada ani shodná funkce nejsou potvrzením záměny."
                _set_text(output, detail)
            elif mode == "substitution":
                _set_text(output, "Vyberte zdrojový řádek v Dekodéru a použijte Převzít z Dekodéru.\n" + BLOCK_REASON)
            else:
                role = next(k for k, label in ROLE_LABELS.items() if label == values["role"].get())
                candidates = proposal_models(family=values["family"].get(), role=role, insulation_mm=int(values["sw"].get()))
                _set_text(output, "Pouze modelové řady podle funkce a izolantu; beton, geometrie a únosnosti nejsou ověřeny.\n\n" +
                    "\n\n".join(f"{s.canonical} – {s.description}\n{DESIGN_STATUS}" for s in candidates)
                    if candidates else "Pro tyto filtry není žádná podporovaná modelová řada.")
        except (ValueError, StopIteration) as exc:
            _set_text(output, str(exc))
    def from_decoder():
        row = _selected_source(owner)
        if row is None:
            _set_text(output, "Nejdříve označte jeden řádek ve společném Dekodéru.")
            return
        text = row.get("snapshot", {}).get("designation", "")
        if not is_peikko(text):
            values["designation"].set("")
            _set_text(output, f"Zdroj: {text}\n" + BLOCK_REASON + "\nMezivýrobní záměna není automaticky potvrzena.")
            return
        values["designation"].set(text)
        show()
    def add_to_decoder():
        try:
            text = values["designation"].get().strip()
            if not text:
                raise ValueError("Zadejte konkrétní označení; samotný seznam modelových řad se do akce nevkládá.")
            from project_model import create_project_row
            result = owner.database.resolve_designation(text, preferred_concrete=owner.project_concrete_var.get())
            if result.catalog.get("id") != CATALOG_ID:
                raise ValueError("Tento formulář přijímá pouze EBEA/TEBEA.")
            row = create_project_row(result, position=owner.project.next_position(), source_text=text,
                                     note="Peikko – bez ověřených únosností")
            owner.project.add(row)
            owner.mark_project_dirty()
            owner.refresh_project_tree(select_ids=[row["id"]])
            owner.main_notebook.select(owner.project_tab)
        except ValueError as exc:
            messagebox.showwarning("Peikko", str(exc), parent=owner)
    for label, callback in (("Vyhodnotit označení / předvýběr", show),
                            ("Převzít z Dekodéru", from_decoder),
                            ("Uložit označení do Dekodéru", add_to_decoder)):
        ttk.Button(buttons, text=label, command=callback).pack(side="left", padx=(0, 8))
    entry.bind("<Return>", lambda _e: show())
    ttk.Label(panel, text="Bez statických tabulek se nezobrazují procenta využití, „vyhovuje“ ani schválená záměna.",
              wraplength=1050).grid(row=4, column=0, columnspan=3, sticky="w", pady=6)
    panel._peikko_values = values
    panel._peikko_output = output
    panel._peikko_show = show
    return panel


def _install_manufacturers(base):
    import platform_registry as registry
    import platform_workspace_200 as platform
    if not any(m.id == "peikko" for m in registry.domain("thermal_breaks").manufacturers):
        spec = registry.ManufacturerSpec(id="peikko", label="Peikko", product_line="EBEA / TEBEA",
            catalog_label="Označení a předvýběr – bez ověřených únosností",
            design_adapter="peikko_preselection", substitution_adapter="peikko_preselection", enabled=True)
        registry.DOMAINS = tuple(replace(d, manufacturers=d.manufacturers + (spec,))
            if d.id == "thermal_breaks" else d for d in registry.DOMAINS)
    previous = platform._manufacturer_changed
    def manufacturer_changed(owner, mode):
        variable = owner.design_manufacturer_var if mode == "design" else owner.substitution_manufacturer_var
        if variable.get() != "Peikko":
            previous(owner, mode)
        elif not getattr(owner, "_action_loading", False):
            owner.mark_project_dirty()
        _switch(owner, mode)
    platform._manufacturer_changed = manufacturer_changed


def _switch(owner, mode):
    state = getattr(owner, "_peikko_shared_panels", {}).get(mode)
    if not state:
        return
    parent, panel, original, controls = state
    variable = owner.design_manufacturer_var if mode == "design" else owner.substitution_manufacturer_var
    active = variable.get() == "Peikko"
    for child in original + controls:
        if active:
            child.grid_remove()
        else:
            child.grid()
    if active:
        panel.grid(row=1, column=0, rowspan=3, sticky="nsew")
    else:
        panel.grid_remove()
    if mode == "design":
        owner.design_catalog_var.set("Označení / předvýběr – staticky neověřeno" if active else "HALFEN / Leviat HIT 20.2-EN 2023")


def install(base_module: Any) -> None:
    cls = base_module.ThermalConnectorApp
    if getattr(cls, "_peikko_shared_229", False):
        return
    base_module.CatalogDatabase = catalog_class(base_module.CatalogDatabase)
    _install_bulk()
    _install_guards()
    _install_manufacturers(base_module)
    previous_payload = cls._row_payload
    def row_payload(self, row, order):
        payload, status = previous_payload(self, row, order)
        if _is_source(row):
            payload["status"] = "K ověření" if status == "ok" else payload["status"]
            payload["moment_class"] = "—"
            payload["shear_class"] = "—"
            payload["moment"] = "neověřeno"
            payload["shear"] = "neověřeno"
            payload["extra"] = DESIGN_STATUS
        return payload, status
    cls._row_payload = row_payload
    previous = cls._build_body
    def body(self):
        previous(self)
        self._peikko_shared_panels = {}
        for mode, parent in (("design", self.hit_tab), ("substitution", self.substitution_tab)):
            original, controls = [], []
            for child in parent.winfo_children():
                info = child.grid_info()
                if not info:
                    continue
                if int(info.get("row", 0)) > 0:
                    original.append(child)
                else:
                    for widget in child.winfo_children():
                        wi = widget.grid_info()
                        if wi and int(wi.get("column", 0)) >= (4 if mode == "design" else 2):
                            controls.append(widget)
            panel = _build_panel(self, parent, mode)
            self._peikko_shared_panels[mode] = (parent, panel, original, controls)
            var = self.design_manufacturer_var if mode == "design" else self.substitution_manufacturer_var
            var.trace_add("write", lambda *_args, m=mode: _switch(self, m))
            _switch(self, mode)
        # Row labels retain generic workflow names; NO additional notebook tab.
    cls._build_body = body
    cls.decode_peikko_product = lambda _self, text: decode_peikko(text)
    cls.peikko_substitution_candidates = lambda _self, text: compatible_models(text)
    cls.peikko_design_candidates = lambda _self, **kwargs: proposal_models(**kwargs)
    cls._peikko_shared_229 = True


def selftest():
    assert WORKSPACE_VERSION == "2.2.29"
    assert decode_peikko("EBEA-ZS Ds200 Dt200 SW80 L1000 REI120") is not None
