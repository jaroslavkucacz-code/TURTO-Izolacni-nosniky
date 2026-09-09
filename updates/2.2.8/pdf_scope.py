from __future__ import annotations

"""TURTO 2.2.8 – selectable PDF scope for AKCE reports."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import webbrowser
from typing import Any, Callable
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import action_report as _legacy
from hit_pdf import ensure_hit_pdf_backend, write_hit_proposal_pdf


@dataclass(frozen=True)
class ReportScope:
    id: str
    label: str
    domain: str | None = None
    tab: str | None = None


SCOPES = (
    ReportScope("all", "Celá AKCE"),
    ReportScope("iso.all", "Izolační nosníky – vše", "thermal_breaks"),
    ReportScope("iso.decoder", "Izolační nosníky → Dekodér", "thermal_breaks", "decoder"),
    ReportScope("iso.design", "Izolační nosníky → Návrh", "thermal_breaks", "design"),
    ReportScope("iso.substitution", "Izolační nosníky → Záměny", "thermal_breaks", "substitution"),
    ReportScope("shear.all", "Smykové trny – vše", "shear_dowels"),
    ReportScope("shear.decoder", "Smykové trny → Dekodér", "shear_dowels", "decoder"),
    ReportScope("shear.design", "Smykové trny → Návrh", "shear_dowels", "design"),
    ReportScope("shear.substitution", "Smykové trny → Záměny", "shear_dowels", "substitution"),
)
SCOPE_BY_ID = {scope.id: scope for scope in SCOPES}


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


def _tree_report_rows(
    owner: Any,
    tree_attr: str,
    *,
    domain_id: str,
    domain: str,
    group: str,
    dowel: bool,
    substitution: bool = False,
) -> list[dict[str, Any]]:
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
        data = {
            heading: str(raw_values[pos]) if pos < len(raw_values) else ""
            for pos, heading in enumerate(headings)
        }
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
        ("thermal_breaks", "decoder"): _tree_report_rows(
            owner, "project_tree", domain_id="thermal_breaks", domain="Izolační nosníky", group="Dekodér", dowel=False,
        ),
        ("thermal_breaks", "design"): _iso_design_rows(owner),
        ("thermal_breaks", "substitution"): _tree_report_rows(
            owner, "sub_tree", domain_id="thermal_breaks", domain="Izolační nosníky", group="Záměny", dowel=False, substitution=True,
        ),
        ("shear_dowels", "decoder"): _tree_report_rows(
            owner, "shear_decoder_tree", domain_id="shear_dowels", domain="Smykové trny", group="Dekodér", dowel=True,
        ),
        ("shear_dowels", "design"): _shear_design_rows(owner),
        ("shear_dowels", "substitution"): _tree_report_rows(
            owner, "shear_substitution_tree", domain_id="shear_dowels", domain="Smykové trny", group="Záměny", dowel=True, substitution=True,
        ),
    }


def rows_for_scope(owner: Any, scope_id: str) -> list[dict[str, Any]]:
    scope = SCOPE_BY_ID.get(scope_id, SCOPE_BY_ID["all"])
    sections = collect_report_sections(owner)
    rows: list[dict[str, Any]] = []
    for (domain_id, tab), section in sections.items():
        if scope.domain is not None and domain_id != scope.domain:
            continue
        if scope.tab is not None and tab != scope.tab:
            continue
        rows.extend(section)
    return rows


class ScopeDialog(tk.Toplevel):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.result: str | None = None
        self.variable = tk.StringVar(master=self, value="all")
        self.title("Rozsah PDF")
        self.geometry("620x550")
        self.minsize(540, 480)
        self.transient(owner)
        self.grab_set()
        try:
            self.configure(background=owner.colors["bg"])
        except Exception:
            pass
        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Co exportovat do PDF", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Vyberte celou AKCI, produktovou oblast nebo jednu pracovní záložku.", style="Muted.TLabel").pack(anchor="w", pady=(4, 12))
        card = ttk.Frame(outer, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True)
        for index, scope in enumerate(SCOPES):
            if index in {1, 5}:
                ttk.Separator(card, orient="horizontal").pack(fill="x", pady=(8, 8))
            ttk.Radiobutton(card, text=scope.label, value=scope.id, variable=self.variable).pack(anchor="w", pady=3)
        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Button(bottom, text="Zrušit", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Pokračovat", style="Accent.TButton", command=self._accept).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._accept())

    def _accept(self) -> None:
        self.result = self.variable.get() or "all"
        self.destroy()


def _open(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.resolve().as_uri())
    except Exception:
        pass


def export_pdf(owner: Any, scope_id: str) -> None:
    scope = SCOPE_BY_ID.get(scope_id, SCOPE_BY_ID["all"])
    try:
        rows = rows_for_scope(owner, scope.id)
    except Exception as exc:
        messagebox.showerror("Export PDF", f"Příprava podkladů se nezdařila.\n\n{exc}", parent=owner)
        return
    if not rows:
        messagebox.showinfo("Export PDF", f"V rozsahu „{scope.label}“ není žádný řádek k exportu.", parent=owner)
        return
    try:
        action = str(owner.project_name_var.get() or owner.project.name or "AKCE").strip()
    except Exception:
        action = "AKCE"
    safe_action = re.sub(r'[\\/:*?"<>|]+', "_", action).strip() or "AKCE"
    suffix = "Cela_AKCE" if scope.id == "all" else re.sub(r"[^A-Za-z0-9_-]+", "_", scope.id.replace(".", "_"))
    path = filedialog.asksaveasfilename(
        parent=owner,
        title=f"Uložit PDF – {scope.label}",
        defaultextension=".pdf",
        initialfile=f"TURTO_{safe_action}_{suffix}.pdf",
        filetypes=[("PDF", "*.pdf")],
    )
    if not path:
        return
    try:
        ensure_hit_pdf_backend()
        report_title = action if scope.id == "all" else f"{action} — {scope.label}"
        target = write_hit_proposal_pdf(Path(path), project_name=report_title, rows=rows, creator="Vytvořil Ing. Jaroslav Kučera")
    except Exception as exc:
        messagebox.showerror("Export PDF se nezdařil", str(exc), parent=owner)
        return
    try:
        owner.set_status(f"PDF exportováno: {scope.label} • {target.name} • {len(rows)} řádků")
    except Exception:
        pass
    _open(target)


def export_pdf_dialog(owner: Any) -> None:
    dialog = ScopeDialog(owner)
    owner.wait_window(dialog)
    if dialog.result:
        export_pdf(owner, dialog.result)


def selftest() -> None:
    assert len(SCOPES) == 9
    assert SCOPE_BY_ID["shear.substitution"].label == "Smykové trny → Záměny"
    assert SCOPE_BY_ID["iso.decoder"].tab == "decoder"


if __name__ == "__main__":
    selftest()
