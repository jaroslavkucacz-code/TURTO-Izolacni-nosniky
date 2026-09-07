from __future__ import annotations

"""TURTO ISO 1.1.27 unified PDF export across all HIT proposal sub-tabs."""

import os
from pathlib import Path
import re
import webbrowser
from typing import Any
from tkinter import filedialog, messagebox

import hit_export_ui_prev as _prev
from hit_export_ui_prev import *  # noqa: F401,F403
from hit_pdf import ensure_hit_pdf_backend, write_hit_proposal_pdf
from hit_wt import candidate_dict as wt_candidate_dict

_ORIGINAL_INSTALL = _prev.install


def _meaningful(row: dict[str, Any]) -> bool:
    if isinstance(row.get("candidate"), dict) and row.get("candidate"):
        return True
    if str(row.get("status", "")).upper() not in {"", "NEPOSOUZENO"}:
        return True
    actions = row.get("actions")
    if isinstance(actions, dict) and any(str(v or "").strip() not in {"", "0", "0,0"} for v in actions.values()):
        return True
    custom = row.get("custom_actions")
    if isinstance(custom, list):
        for item in custom:
            if isinstance(item, dict) and str(item.get("value", "") or "").strip() not in {"", "0", "0,0"}:
                return True
    return bool(str(row.get("import_source_text", "") or "").strip())


def collect_all_hit_rows(owner: Any) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []

    for row in _prev.collect_hit_rows(owner):
        item = dict(row)
        item["group"] = "Desky / balkony"
        if _meaningful(item):
            report.append(item)

    if hasattr(owner, "_collect_aux_pdf_rows"):
        for row in owner._collect_aux_pdf_rows():
            item = dict(row)
            item["group"] = "Doplňkové prvky"
            if _meaningful(item):
                report.append(item)

    for index, row in enumerate(getattr(owner, "wt_rows", []), 1):
        candidate = getattr(row, "selected_candidate", None)
        try:
            quantity = int(str(row.quantity.get() or "1").strip())
        except Exception:
            quantity = 1
        med = str(row.med_neg.get() or "").strip()
        vv = str(row.ved_vertical.get() or "").strip()
        vh = str(row.ved_horizontal.get() or "").strip()
        active = sum(
            1
            for raw in (med, vv, vh)
            if str(raw).strip().replace(",", ".") not in {"", "0", "0.0"}
        )
        status_text = str(row.status.get() or "").strip()
        if candidate is not None:
            status = "KONTROLA" if active > 1 else "VYHOVUJE"
            cdict = wt_candidate_dict(candidate)
            cdict.update({
                "connection_type": "WT",
                "physical_length_mm": candidate.width_mm,
                "height": candidate.wall_height_mm,
                "cover": 0,
            })
        else:
            status = "NEPOSOUZENO" if active == 0 else "NELZE"
            cdict = {}

        item = {
            "group": "Stěny WT",
            "name": row.name.get().strip() or f"W{index:03d}",
            "quantity": quantity,
            "series": row.series.get().strip(),
            "connection_type": "WT",
            "height_mm": row.wall_height.get().strip(),
            "cover_mm": "",
            "concrete": row.concrete.get().strip(),
            "required_length_mm": row.width.get().strip(),
            "custom_actions": [
                {"label": "MEd−", "value": med, "unit": "kNm/prvek"},
                {"label": "VEd,v+", "value": vv, "unit": "kN/prvek"},
                {"label": "VEd,h±", "value": vh, "unit": "kN/prvek"},
            ],
            "candidate": cdict,
            "status": status,
            "detail": status_text,
            "notes": (
                ["WT: při současném působení více účinků je nutná kontrola jejich kombinace."]
                if candidate is not None and active > 1
                else ([status_text] if candidate is None and status_text else [])
            ),
        }
        if _meaningful(item):
            report.append(item)

    return report


def _open_export(target: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            webbrowser.open(target.resolve().as_uri())
    except Exception:
        pass


def export_hit_pdf(owner: Any) -> None:
    try:
        if hasattr(owner, "recalculate_hit_all"):
            owner.recalculate_hit_all()
        if hasattr(owner, "recalculate_aux_all"):
            owner.recalculate_aux_all()
        if hasattr(owner, "recalculate_wt_all"):
            owner.recalculate_wt_all()
        rows = collect_all_hit_rows(owner)
    except Exception as exc:
        messagebox.showerror(
            "Export PDF",
            f"Přepočet celé AKCE před exportem se nezdařil.\n\n{exc}",
            parent=owner,
        )
        return

    if not rows:
        messagebox.showinfo(
            "Export PDF",
            "V Návrhu HIT není žádný vyplněný prvek k exportu.",
            parent=owner,
        )
        return

    try:
        action = str(owner.project_name_var.get() or owner.project.name or "AKCE").strip()
    except Exception:
        action = _prev.current_action_name(owner)
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", action).strip() or "akce"
    path = filedialog.asksaveasfilename(
        parent=owner,
        title="Uložit PDF návrhu HIT – všechny prvky",
        defaultextension=".pdf",
        initialfile=f"Navrh_HIT_{safe_name}.pdf",
        filetypes=[("PDF", "*.pdf")],
    )
    if not path:
        return

    try:
        if hasattr(owner, "hit_status_var"):
            owner.hit_status_var.set("Připravuji PDF celé AKCE…")
        owner.update_idletasks()
        ensure_hit_pdf_backend()
        target = write_hit_proposal_pdf(
            Path(path),
            project_name=action,
            rows=rows,
            creator="Vytvořil Ing. Jaroslav Kučera",
        )
    except Exception as exc:
        messagebox.showerror("Export PDF návrhu HIT se nezdařil", str(exc), parent=owner)
        return

    standard = sum(1 for row in rows if row.get("group") == "Desky / balkony")
    aux = sum(1 for row in rows if row.get("group") == "Doplňkové prvky")
    wt = sum(1 for row in rows if row.get("group") == "Stěny WT")
    try:
        owner.hit_status_var.set(
            f"PDF celé AKCE exportováno: {target.name} • desky {standard} • doplňky {aux} • WT {wt}"
        )
        owner.set_status(
            f"PDF Návrhu HIT obsahuje všechny skupiny: {standard} desky/balkony, {aux} doplňkové, {wt} WT."
        )
    except Exception:
        pass
    _open_export(target)


def install(base: Any) -> None:
    _ORIGINAL_INSTALL(base)

    def collect(self) -> list[dict[str, Any]]:
        return collect_all_hit_rows(self)

    def pdf(self) -> None:
        export_hit_pdf(self)

    base.HitWorkspaceMixin._collect_hit_pdf_rows = collect
    base.HitWorkspaceMixin.export_hit_pdf = pdf
