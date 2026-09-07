from __future__ import annotations

"""PDF and supplier Excel UI for direct HIT proposals."""

import os
from pathlib import Path
import re
import webbrowser
from typing import Any
from tkinter import filedialog, messagebox

from hit_design_ui import current_action_name
from hit_excel import write_hit_request_xlsx
from hit_pdf import ensure_hit_pdf_backend, write_hit_proposal_pdf
from hit_row_extension import quantity_int


def _candidate_dict(candidate: Any) -> dict[str, Any]:
    if candidate is None:
        return {}
    return {
        "designation": candidate.designation,
        "series": candidate.series,
        "connection_type": candidate.connection_type,
        "code": candidate.code,
        "physical_length_mm": candidate.physical_length_mm,
        "height": candidate.height,
        "cover": candidate.cover,
        "concrete": candidate.concrete,
        "utilization": candidate.utilization,
        "spacing_max": candidate.spacing_max,
        "load_distance_x": candidate.load_distance_x,
        "page": candidate.page,
        "nrd": candidate.nrd,
        "m1": candidate.m1,
        "v1": candidate.v1,
        "m2": candidate.m2,
        "v2": candidate.v2,
        "mode": candidate.mode,
        "source_note": candidate.source_note,
    }


def collect_hit_rows(owner: Any) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for row in owner.hit_rows:
        candidate = row.selected_candidate
        product = str(row.product.get() or "").strip()
        if candidate is not None:
            status = "VYHOVUJE"
        elif product == "NELZE NAVRHNOUT":
            status = "NELZE"
        else:
            status = "NEPOSOUZENO"
        effective = row.effective_action_texts()
        detail = str(row.detail.get() or "").strip() if hasattr(row, "detail") else ""
        notes: list[str] = []
        if status != "VYHOVUJE" and detail:
            notes.append(detail)
        try:
            family_note = str(row._family_info.get("note", "") or "").strip()
        except Exception:
            family_note = ""
        if family_note:
            notes.append(family_note)
        report.append({
            "name": row.name.get().strip() or f"N{row.row_no}",
            "quantity": quantity_int(row),
            "series": row.series.get().strip(),
            "connection_type": row.connection_type.get().strip(),
            "mvx_variant": row.mvx_variant.get().strip(),
            "bx_mm": row.mvx_bx.get().strip(),
            "height_mm": row.height.get().strip(),
            "cover_mm": row.cover.get().strip(),
            "concrete": row.concrete.get().strip(),
            "required_length_mm": row.required_length.get().strip(),
            "actions": dict(effective),
            "import_source_text": str(getattr(row, "import_source_text", "") or "").strip(),
            "candidate": _candidate_dict(candidate),
            "status": status,
            "detail": detail,
            "notes": list(dict.fromkeys(notes)),
        })
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
    if not getattr(owner, "hit_rows", None):
        messagebox.showinfo("Export PDF", "Není co exportovat.", parent=owner)
        return
    try:
        owner.recalculate_hit_all()
        rows = collect_hit_rows(owner)
    except Exception as exc:
        messagebox.showerror("Export PDF", f"Přepočet návrhu HIT se nezdařil.\n\n{exc}", parent=owner)
        return
    action = current_action_name(owner)
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", action).strip() or "projekt"
    path = filedialog.asksaveasfilename(
        parent=owner, title="Uložit PDF návrhu HIT", defaultextension=".pdf",
        initialfile=f"Navrh_HIT_{safe_name}.pdf", filetypes=[("PDF", "*.pdf")],
    )
    if not path:
        return
    try:
        owner.hit_status_var.set("Připravuji PDF návrhu HIT…")
        owner.update_idletasks()
        ensure_hit_pdf_backend()
        target = write_hit_proposal_pdf(
            Path(path), project_name=action, rows=rows,
            creator="Vytvořil Ing. Jaroslav Kučera",
        )
    except Exception as exc:
        messagebox.showerror("Export PDF návrhu HIT se nezdařil", str(exc), parent=owner)
        return
    owner.hit_status_var.set(f"PDF návrhu HIT exportováno: {target.name}")
    _open_export(target)


def export_hit_excel(owner: Any) -> None:
    if not getattr(owner, "hit_rows", None):
        messagebox.showinfo("Export Excel", "Není co exportovat.", parent=owner)
        return
    try:
        owner.recalculate_hit_all()
        rows = collect_hit_rows(owner)
    except Exception as exc:
        messagebox.showerror("Export Excel", f"Přepočet návrhu HIT se nezdařil.\n\n{exc}", parent=owner)
        return
    valid = [row for row in rows if isinstance(row.get("candidate"), dict) and row.get("candidate")]
    skipped = len(rows) - len(valid)
    if not valid:
        messagebox.showinfo("Export Excel", "Není navržen žádný vyhovující HIT.", parent=owner)
        return
    if skipped and not messagebox.askyesno(
        "Export Excel",
        f"{skipped} řádků nemá vyhovující navržený HIT a nebude zahrnuto do poptávky. Pokračovat?",
        parent=owner,
    ):
        return
    include_statics = messagebox.askyesnocancel(
        "Excel návrhu HIT",
        "Přidat i list „Statická data“?\n\n"
        "Ano = první list Typ HIT + Ks + Pozice a druhý list s jednotlivými statickými daty.\n"
        "Ne = pouze jednoduchá poptávka pro výrobce.",
        parent=owner,
    )
    if include_statics is None:
        return
    action = current_action_name(owner)
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", action).strip() or "akce"
    path = filedialog.asksaveasfilename(
        parent=owner, title="Uložit Excel pro poptávku HIT", defaultextension=".xlsx",
        initialfile=f"Poptavka_HIT_{safe_name}.xlsx", filetypes=[("Excel", "*.xlsx")],
    )
    if not path:
        return
    try:
        target = write_hit_request_xlsx(
            Path(path), action_name=action, rows=valid,
            include_statics=bool(include_statics), creator="TURTO",
        )
    except Exception as exc:
        messagebox.showerror("Export Excel se nezdařil", str(exc), parent=owner)
        return
    owner.hit_status_var.set(
        f"Excel pro poptávku exportován: {target.name} • {len(valid)} pozic"
        + (" • včetně statiky" if include_statics else "")
    )
    _open_export(target)


def install(base: Any) -> None:
    def collect(self) -> list[dict[str, Any]]:
        return collect_hit_rows(self)
    def pdf(self) -> None:
        export_hit_pdf(self)
    def excel(self) -> None:
        export_hit_excel(self)
    base.HitWorkspaceMixin._collect_hit_pdf_rows = collect
    base.HitWorkspaceMixin.export_hit_pdf = pdf
    base.HitWorkspaceMixin.export_hit_excel = excel
