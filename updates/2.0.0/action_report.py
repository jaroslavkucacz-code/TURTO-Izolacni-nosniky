from __future__ import annotations

"""AKCE-level report dispatcher for TURTO 2.0.

Today only the thermal-break provider is active. Future product domains add a
provider here without moving the report button or changing the AKCE workflow.
"""

import os
from pathlib import Path
import re
import webbrowser
from typing import Any, Callable
from tkinter import filedialog, messagebox

import hit_export_ui_127 as _thermal
from hit_pdf_127 import ensure_hit_pdf_backend, write_hit_proposal_pdf


def _thermal_rows(owner: Any) -> list[dict[str, Any]]:
    if hasattr(owner, "recalculate_hit_all"):
        owner.recalculate_hit_all()
    if hasattr(owner, "recalculate_aux_all"):
        owner.recalculate_aux_all()
    if hasattr(owner, "recalculate_wt_all"):
        owner.recalculate_wt_all()
    rows = _thermal.collect_all_hit_rows(owner)
    for row in rows:
        row["domain_id"] = "thermal_breaks"
        row["domain"] = "Izolační nosníky"
    return rows


REPORT_PROVIDERS: dict[str, Callable[[Any], list[dict[str, Any]]]] = {
    "thermal_breaks": _thermal_rows,
}


def collect_action_report_rows(owner: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for domain_id, provider in REPORT_PROVIDERS.items():
        try:
            rows.extend(provider(owner))
        except Exception as exc:
            raise RuntimeError(f"{domain_id}: {exc}") from exc
    return rows


def _open(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.resolve().as_uri())
    except Exception:
        pass


def export_action_pdf(owner: Any) -> None:
    try:
        rows = collect_action_report_rows(owner)
    except Exception as exc:
        messagebox.showerror("Export PDF AKCE", f"Přepočet podkladů se nezdařil.\n\n{exc}", parent=owner)
        return
    if not rows:
        messagebox.showinfo("Export PDF AKCE", "AKCE zatím neobsahuje žádný navržený prvek k exportu.", parent=owner)
        return
    try:
        action = str(owner.project_name_var.get() or owner.project.name or "AKCE").strip()
    except Exception:
        action = "AKCE"
    safe = re.sub(r'[\\/:*?"<>|]+', "_", action).strip() or "AKCE"
    path = filedialog.asksaveasfilename(
        parent=owner,
        title="Uložit PDF výstup celé AKCE",
        defaultextension=".pdf",
        initialfile=f"TURTO_AKCE_{safe}.pdf",
        filetypes=[("PDF", "*.pdf")],
    )
    if not path:
        return
    try:
        ensure_hit_pdf_backend()
        target = write_hit_proposal_pdf(
            Path(path), project_name=action, rows=rows,
            creator="Vytvořil Ing. Jaroslav Kučera",
        )
    except Exception as exc:
        messagebox.showerror("Export PDF AKCE se nezdařil", str(exc), parent=owner)
        return
    try:
        domains = sorted({str(row.get("domain", "") or "") for row in rows if row.get("domain")})
        owner.set_status(f"PDF celé AKCE exportováno: {target.name} • " + ", ".join(domains))
    except Exception:
        pass
    _open(target)
