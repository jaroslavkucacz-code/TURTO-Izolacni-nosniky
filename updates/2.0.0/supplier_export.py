from __future__ import annotations

"""Manufacturer-neutral supplier export for the active design adapter."""

import os
from pathlib import Path
import re
import webbrowser
from typing import Any
from tkinter import filedialog, messagebox

import hit_export_ui_127 as _hit_export
from xlsx_export import write_xlsx


def _actions_text(row: dict[str, Any]) -> str:
    custom = row.get("custom_actions")
    if isinstance(custom, list):
        parts = []
        for item in custom:
            if not isinstance(item, dict):
                continue
            value = str(item.get("value", "") or "").strip()
            if value and value not in {"0", "0,0", "0.0"}:
                parts.append(f"{item.get('label', '')} {value} {item.get('unit', '')}".strip())
        return " • ".join(parts)
    actions = row.get("actions") if isinstance(row.get("actions"), dict) else {}
    meta = {
        "m_pos": ("MEd+", "kNm/m"), "m_neg": ("MEd−", "kNm/m"),
        "n_pos": ("NEd+", "kN/m"), "n_neg": ("NEd−", "kN/m"),
        "v_pos": ("VEd+", "kN/m"), "v_neg": ("VEd−", "kN/m"),
        "h_parallel": ("HEd∥", "kN/prvek"), "h_perp": ("HEd⊥", "kN/prvek"),
    }
    parts = []
    for key, (label, unit) in meta.items():
        value = str(actions.get(key, "") or "").strip()
        if value and value not in {"0", "0,0", "0.0"}:
            parts.append(f"{label} {value} {unit}")
    return " • ".join(parts)


def _open(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.resolve().as_uri())
    except Exception:
        pass


def export_supplier_excel(owner: Any) -> None:
    try:
        if hasattr(owner, "recalculate_hit_all"):
            owner.recalculate_hit_all()
        if hasattr(owner, "recalculate_aux_all"):
            owner.recalculate_aux_all()
        if hasattr(owner, "recalculate_wt_all"):
            owner.recalculate_wt_all()
        rows = _hit_export.collect_all_hit_rows(owner)
    except Exception as exc:
        messagebox.showerror("Export Excel", f"Přepočet návrhu se nezdařil.\n\n{exc}", parent=owner)
        return

    valid = [row for row in rows if isinstance(row.get("candidate"), dict) and row.get("candidate")]
    if not valid:
        messagebox.showinfo("Export Excel", "Není navržen žádný výrobek k poptání.", parent=owner)
        return

    include_statics = messagebox.askyesnocancel(
        "Excel pro výrobce",
        "Přidat do stejného souboru také řádky s návrhovými účinky?\n\n"
        "Ano = soupis pro poptávku + detailní řádky se statikou.\n"
        "Ne = pouze Typ / Ks / Pozice.",
        parent=owner,
    )
    if include_statics is None:
        return

    grouped: dict[str, dict[str, Any]] = {}
    for row in valid:
        candidate = row["candidate"]
        designation = str(candidate.get("designation", "") or "").strip()
        if not designation:
            continue
        item = grouped.setdefault(designation, {"quantity": 0, "positions": [], "groups": set()})
        try:
            item["quantity"] += int(row.get("quantity", 1) or 1)
        except Exception:
            item["quantity"] += 1
        position = str(row.get("name", "") or "").strip()
        if position:
            item["positions"].append(position)
        item["groups"].add(str(row.get("group", "") or ""))

    output_rows: list[tuple[Any, ...]] = []
    for designation, info in sorted(grouped.items()):
        output_rows.append((
            "POPTÁVKA", designation, int(info["quantity"]), ", ".join(info["positions"]),
            ", ".join(sorted(x for x in info["groups"] if x)), "", "", "",
        ))
    if include_statics:
        for row in valid:
            candidate = row["candidate"]
            output_rows.append((
                "STATIKA",
                candidate.get("designation", ""),
                int(row.get("quantity", 1) or 1),
                row.get("name", ""),
                row.get("group", ""),
                _actions_text(row),
                row.get("status", ""),
                candidate.get("page", row.get("source", "")),
            ))

    try:
        action = str(owner.project_name_var.get() or owner.project.name or "AKCE").strip()
    except Exception:
        action = "AKCE"
    manufacturer = str(getattr(owner, "design_manufacturer_var", None).get() if hasattr(owner, "design_manufacturer_var") else "Leviat")
    safe = re.sub(r'[\\/:*?"<>|]+', "_", action).strip() or "AKCE"
    path = filedialog.asksaveasfilename(
        parent=owner,
        title="Uložit Excel pro poptávku výrobce",
        defaultextension=".xlsx",
        initialfile=f"Poptavka_{manufacturer}_{safe}.xlsx",
        filetypes=[("Excel", "*.xlsx")],
    )
    if not path:
        return
    try:
        target = write_xlsx(
            Path(path),
            headers=("Druh", "Typ výrobku", "Ks", "Pozice", "Skupina", "Návrhové účinky", "Výsledek", "Zdroj"),
            rows=output_rows,
            sheet_name="Poptávka a statika" if include_statics else "Poptávka",
            creator="TURTO",
        )
    except Exception as exc:
        messagebox.showerror("Export Excel", str(exc), parent=owner)
        return
    try:
        owner.set_status(f"Excel pro {manufacturer} exportován: {target.name}.")
    except Exception:
        pass
    _open(target)
