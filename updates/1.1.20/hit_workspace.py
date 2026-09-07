from __future__ import annotations

"""Compatibility wrapper adding PDF export to the verified HIT workspace."""

import os
from pathlib import Path
import re
import webbrowser
from typing import Any

from tkinter import filedialog, messagebox, ttk

import hit_workspace_base as _base
from hit_workspace_base import *  # noqa: F401,F403 - preserve the original public module API
from hit_pdf import ensure_hit_pdf_backend, write_hit_proposal_pdf

HIT_MODULE_VERSION = "1.1.20"
_base.HIT_MODULE_VERSION = HIT_MODULE_VERSION

_ORIGINAL_BUILD_HIT_TAB = _base.HitWorkspaceMixin._build_hit_tab


def _find_button(root: Any, text: str):
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
                return widget
            stack.extend(widget.winfo_children())
        except Exception:
            continue
    return None


def _patched_build_hit_tab(self, parent: ttk.Frame) -> None:
    _ORIGINAL_BUILD_HIT_TAB(self, parent)
    anchor = _find_button(parent, "Kopírovat výsledky")
    if anchor is None:
        return
    toolbar = anchor.master
    button = ttk.Button(toolbar, text="Export PDF", style="Accent.TButton", command=self.export_hit_pdf)
    # Columns 10–19 are free in the current toolbar; status remains at column 20.
    button.grid(row=0, column=10, padx=(12, 0))
    self.hit_pdf_button = button


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


def _collect_hit_pdf_rows(self) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for row in self.hit_rows:
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
        notes = []
        if status != "VYHOVUJE" and detail:
            notes.append(detail)
        family_note = ""
        try:
            family_note = str(row._family_info.get("note", "") or "").strip()
        except Exception:
            family_note = ""
        if family_note:
            notes.append(family_note)
        report.append({
            "name": row.name.get().strip() or f"N{row.row_no}",
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


def export_hit_pdf(self) -> None:
    if not getattr(self, "hit_rows", None):
        messagebox.showinfo("Export PDF", "Není co exportovat.", parent=self)
        return
    # The issued document should always reflect current inputs, not a stale prior calculation.
    try:
        self.recalculate_hit_all()
    except Exception as exc:
        messagebox.showerror("Export PDF", f"Přepočet návrhu HIT se nezdařil.\n\n{exc}", parent=self)
        return
    rows = self._collect_hit_pdf_rows()
    if not rows:
        messagebox.showinfo("Export PDF", "Není co exportovat.", parent=self)
        return

    project = getattr(self, "project", None)
    project_name = str(getattr(project, "name", "Projekt") or "Projekt")
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", project_name).strip() or "projekt"
    path = filedialog.asksaveasfilename(
        parent=self,
        title="Uložit PDF návrhu HIT",
        defaultextension=".pdf",
        initialfile=f"Navrh_HIT_{safe_name}.pdf",
        filetypes=[("PDF", "*.pdf")],
    )
    if not path:
        return
    try:
        self.hit_status_var.set("Připravuji PDF návrhu HIT…")
        self.update_idletasks()
        ensure_hit_pdf_backend()
        target = write_hit_proposal_pdf(
            Path(path),
            project_name=project_name,
            rows=rows,
            creator="Vytvořil Ing. Jaroslav Kučera",
        )
    except Exception as exc:
        messagebox.showerror("Export PDF návrhu HIT se nezdařil", str(exc), parent=self)
        return
    self.hit_status_var.set(f"PDF návrhu HIT exportováno: {target.name}")
    try:
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            webbrowser.open(target.resolve().as_uri())
    except Exception:
        pass


_base.HitWorkspaceMixin._build_hit_tab = _patched_build_hit_tab
_base.HitWorkspaceMixin._collect_hit_pdf_rows = _collect_hit_pdf_rows
_base.HitWorkspaceMixin.export_hit_pdf = export_hit_pdf

# Keep the exported class name identical to the verified implementation object.
HitWorkspaceMixin = _base.HitWorkspaceMixin
