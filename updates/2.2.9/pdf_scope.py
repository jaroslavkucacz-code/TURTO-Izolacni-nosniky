from __future__ import annotations

"""TURTO 2.2.9 – multi-select PDF export for AKCE reports."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import webbrowser
from typing import Any, Iterable
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import action_report as _legacy
from hit_pdf import ensure_hit_pdf_backend, write_hit_proposal_pdf


@dataclass(frozen=True)
class ReportScope:
    id: str
    label: str
    domain: str
    tab: str


SCOPES = (
    ReportScope("iso.decoder", "Izolační nosníky → Dekodér", "thermal_breaks", "decoder"),
    ReportScope("iso.design", "Izolační nosníky → Návrh", "thermal_breaks", "design"),
    ReportScope("iso.substitution", "Izolační nosníky → Záměny", "thermal_breaks", "substitution"),
    ReportScope("shear.decoder", "Smykové trny → Dekodér", "shear_dowels", "decoder"),
    ReportScope("shear.design", "Smykové trny → Návrh", "shear_dowels", "design"),
    ReportScope("shear.substitution", "Smykové trny → Záměny", "shear_dowels", "substitution"),
)
SCOPE_BY_ID = {scope.id: scope for scope in SCOPES}
ALL_SCOPE_IDS = tuple(scope.id for scope in SCOPES)


def _heading(tree: ttk.Treeview, column: str) -> str:
    try:
        return str(tree.heading(column, "text") or column).rstrip(" ▲▼")
    except Exception:
        return str(column)


def _first_value(values: dict[str, str], *tokens: str) -> str:
    for heading, value in values.items():
        low = heading.lower()
        if any(token in low for token in tokens) and str(value).strip():
            return str(value).strip()
    return ""


def _number(value: Any, default: float = 0.0) -> float:
    try:
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value or ""))
        return float(match.group(0).replace(",", ".")) if match else default
    except Exception:
        return default


def _tree_report_rows(owner: Any, tree_attr: str, *, domain_id: str, domain: str, group: str, dowel: bool, substitution: bool = False) -> list[dict[str, Any]]:
    tree = getattr(owner, tree_attr, None)
    if tree is None:
        return []
    try:
        columns = [str(value) for value in tree["columns"]]
    except Exception:
        return []
    headings = [_heading(tree, column) for column in columns]
    report: list[dict[str, Any]] = []
    try:
        iids = list(tree.get_children(""))
    except Exception:
        iids = []
    for index, iid in enumerate(iids, 1):
        try:
            raw_values = list(tree.item(iid, "values"))
        except Exception:
            continue
        data = {heading: str(raw_values[pos]) if pos < len(raw_values) else "" for pos, heading in enumerate(headings)}
        name = _first_value(data, "pozice") or f"P{index:03d}"
        qty = int(max(1, _number(_first_value(data, "ks"), 1)))
        source = _first_value(data, "původní", "označení", "název")
        target = _first_value(data, "navržený ekvivalent", "navržený trn", "záměna", "náhrada")
        designation = target if substitution and target else source
        if not designation:
            designation = _first_value(data, "typ", "řada") or "—"
        concrete = _first_value(data, "beton")
        height = _number(_first_value(data, "výška", "h [mm]", "h[mm]"), 0)
        gap = _number(_first_value(data, "spára"), 0)
        status = _first_value(data, "výsledek", "stav") or ("ZÁMĚNA" if substitution else "DEKÓDOVÁNO")
        vrd = _number(_first_value(data, "vrd cíle", "vrd", "vrd archiv", "vrd / síla"), 0)
        details = [f"{heading}: {value}" for heading, value in data.items() if str(value).strip()]
        if substitution and source:
            details.insert(0, f"Původní prvek: {source}")
        candidate = {
            "designation": designation,
            "connection_type": "DOWEL" if dowel else "DECODED",
            "manufacturer": _first_value(data, "výrobce"),
            "physical_length_mm": 0,
            "height": height,
            "concrete": concrete,
            "utilization": 0,
            "m1": 0,
            "v1": vrd,
            "m2": 0,
            "v2": 0,
            "mode": group,
            "page": "",
            "source_note": "",
        }
        report.append({
            "domain_id": domain_id,
            "domain": domain,
            "group": group,
            "name": name,
            "quantity": qty,
            "series": candidate.get("manufacturer", ""),
            "connection_type": "DOWEL" if dowel else "DECODED",
            "height_mm": height or "",
            "cover_mm": "",
            "concrete": concrete,
            "required_length_mm": gap or "",
            "custom_actions": [],
            "candidate": candidate,
            "status": status,
            "detail": " • ".join(details),
            "notes": [],
            "report_tab": "substitution" if substitution else "decoder",
        })
    return report


def _iso_design_rows(owner: Any) -> list[dict[str, Any]]:
    rows = _legacy._thermal_rows(owner)
    for row in rows:
        row["report_tab"] = "design"
    return rows


def _shear_design_rows(owner: Any) -> list[dict[str, Any]]:
    rows = owner.collect_shear_report_rows() if hasattr(owner, "collect_shear_report_rows") else []
    for row in rows:
        row["domain_id"] = "shear_dowels"
        row["domain"] = "Smykové trny"
        row["group"] = "Návrh"
        row["report_tab"] = "design"
    return rows


def collect_report_sections(owner: Any) -> dict[tuple[str, str], list[dict[str, Any]]]:
    return {
        ("thermal_breaks", "decoder"): _tree_report_rows(owner, "project_tree", domain_id="thermal_breaks", domain="Izolační nosníky", group="Dekodér", dowel=False),
        ("thermal_breaks", "design"): _iso_design_rows(owner),
        ("thermal_breaks", "substitution"): _tree_report_rows(owner, "sub_tree", domain_id="thermal_breaks", domain="Izolační nosníky", group="Záměny", dowel=False, substitution=True),
        ("shear_dowels", "decoder"): _tree_report_rows(owner, "shear_decoder_tree", domain_id="shear_dowels", domain="Smykové trny", group="Dekodér", dowel=True),
        ("shear_dowels", "design"): _shear_design_rows(owner),
        ("shear_dowels", "substitution"): _tree_report_rows(owner, "shear_substitution_tree", domain_id="shear_dowels", domain="Smykové trny", group="Záměny", dowel=True, substitution=True),
    }


def normalize_scope_ids(scope_ids: Iterable[str] | str | None) -> tuple[str, ...]:
    if scope_ids is None:
        return ALL_SCOPE_IDS
    if isinstance(scope_ids, str):
        if scope_ids in {"all", "*"}:
            return ALL_SCOPE_IDS
        scope_ids = (scope_ids,)
    wanted = {str(value) for value in scope_ids if str(value) in SCOPE_BY_ID}
    return tuple(scope.id for scope in SCOPES if scope.id in wanted)


def rows_for_scopes(owner: Any, scope_ids: Iterable[str] | str | None) -> list[dict[str, Any]]:
    selected = normalize_scope_ids(scope_ids)
    sections = collect_report_sections(owner)
    rows: list[dict[str, Any]] = []
    for scope_id in selected:
        scope = SCOPE_BY_ID[scope_id]
        rows.extend(sections.get((scope.domain, scope.tab), ()))
    return rows


def rows_for_scope(owner: Any, scope_id: str) -> list[dict[str, Any]]:
    return rows_for_scopes(owner, scope_id)


class ScopeDialog(tk.Toplevel):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.result: tuple[str, ...] | None = None
        self.variables = {scope.id: tk.BooleanVar(master=self, value=True) for scope in SCOPES}
        self.title("Rozsah PDF")
        self.geometry("650x560")
        self.minsize(570, 500)
        self.transient(owner)
        self.grab_set()
        try:
            self.configure(background=owner.colors["bg"])
        except Exception:
            pass

        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Co exportovat do PDF", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Zaškrtněte libovolnou kombinaci částí AKCE. Můžete exportovat jednu, několik i všechny položky.", style="Muted.TLabel", wraplength=590, justify="left").pack(anchor="w", pady=(4, 12))

        presets = ttk.Frame(outer, style="App.TFrame")
        presets.pack(fill="x", pady=(0, 8))
        ttk.Button(presets, text="Vybrat vše", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(presets, text="Zrušit výběr", command=lambda: self._set_all(False)).pack(side="left", padx=(7, 0))
        ttk.Button(presets, text="Jen izolační nosníky", command=lambda: self._set_domain("thermal_breaks")).pack(side="left", padx=(7, 0))
        ttk.Button(presets, text="Jen smykové trny", command=lambda: self._set_domain("shear_dowels")).pack(side="left", padx=(7, 0))

        card = ttk.Frame(outer, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True)
        for domain, title in (("thermal_breaks", "Izolační nosníky"), ("shear_dowels", "Smykové trny")):
            ttk.Label(card, text=title, style="Card.TLabel", font=("Calibri", 10, "bold")).pack(anchor="w", pady=(4, 3))
            for scope in (item for item in SCOPES if item.domain == domain):
                ttk.Checkbutton(card, text=scope.label.split("→", 1)[-1].strip(), variable=self.variables[scope.id]).pack(anchor="w", padx=(16, 0), pady=2)
            if domain == "thermal_breaks":
                ttk.Separator(card, orient="horizontal").pack(fill="x", pady=(10, 8))

        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Button(bottom, text="Zrušit", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Pokračovat", style="Accent.TButton", command=self._accept).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._accept())

    def _set_all(self, value: bool) -> None:
        for variable in self.variables.values():
            variable.set(value)

    def _set_domain(self, domain: str) -> None:
        for scope in SCOPES:
            self.variables[scope.id].set(scope.domain == domain)

    def _accept(self) -> None:
        selected = tuple(scope.id for scope in SCOPES if self.variables[scope.id].get())
        if not selected:
            messagebox.showinfo("Rozsah PDF", "Vyberte alespoň jednu položku.", parent=self)
            return
        self.result = selected
        self.destroy()


def _open(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.resolve().as_uri())
    except Exception:
        pass


def _selection_label(scope_ids: tuple[str, ...]) -> str:
    thermal = tuple(scope.id for scope in SCOPES if scope.domain == "thermal_breaks")
    shear = tuple(scope.id for scope in SCOPES if scope.domain == "shear_dowels")
    if scope_ids == ALL_SCOPE_IDS:
        return "Celá AKCE"
    if scope_ids == thermal:
        return "Izolační nosníky – vše"
    if scope_ids == shear:
        return "Smykové trny – vše"
    if len(scope_ids) == 1:
        return SCOPE_BY_ID[scope_ids[0]].label
    return f"Vybrané části ({len(scope_ids)})"


def export_pdf(owner: Any, scope_ids: Iterable[str] | str | None) -> None:
    selected = normalize_scope_ids(scope_ids)
    if not selected:
        messagebox.showinfo("Export PDF", "Není vybrána žádná část k exportu.", parent=owner)
        return
    label = _selection_label(selected)
    try:
        rows = rows_for_scopes(owner, selected)
    except Exception as exc:
        messagebox.showerror("Export PDF", f"Příprava podkladů se nezdařila.\n\n{exc}", parent=owner)
        return
    if not rows:
        messagebox.showinfo("Export PDF", f"Ve výběru „{label}“ není žádný řádek k exportu.", parent=owner)
        return
    try:
        action = str(owner.project_name_var.get() or owner.project.name or "AKCE").strip()
    except Exception:
        action = "AKCE"
    safe_action = re.sub(r'[\\/:*?"<>|]+', "_", action).strip() or "AKCE"
    if selected == ALL_SCOPE_IDS:
        suffix = "Cela_AKCE"
    elif len(selected) == 1:
        suffix = selected[0].replace(".", "_")
    else:
        suffix = f"Vyber_{len(selected)}_casti"
    path = filedialog.asksaveasfilename(parent=owner, title=f"Uložit PDF – {label}", defaultextension=".pdf", initialfile=f"TURTO_{safe_action}_{suffix}.pdf", filetypes=[("PDF", "*.pdf")])
    if not path:
        return
    try:
        ensure_hit_pdf_backend()
        report_title = action if selected == ALL_SCOPE_IDS else f"{action} — {label}"
        target = write_hit_proposal_pdf(Path(path), project_name=report_title, rows=rows, creator="Vytvořil Ing. Jaroslav Kučera")
    except Exception as exc:
        messagebox.showerror("Export PDF se nezdařil", str(exc), parent=owner)
        return
    try:
        owner.set_status(f"PDF exportováno: {label} • {target.name} • {len(rows)} řádků")
    except Exception:
        pass
    _open(target)


def export_pdf_dialog(owner: Any) -> None:
    dialog = ScopeDialog(owner)
    owner.wait_window(dialog)
    if dialog.result:
        export_pdf(owner, dialog.result)


def selftest() -> None:
    assert len(SCOPES) == 6
    assert normalize_scope_ids("all") == ALL_SCOPE_IDS
    assert normalize_scope_ids(("iso.design", "shear.design")) == ("iso.design", "shear.design")


if __name__ == "__main__":
    selftest()
