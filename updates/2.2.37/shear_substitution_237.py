from __future__ import annotations

"""TURTO 2.2.37 – transparent shear-dowel substitution modes.

Catalogue mode stays conservative: target VRd must reach the catalogue VRd of
source.  If no exact 1:1 replacement exists, the best geometry-compatible
catalogue candidate is shown as OVĚŘIT VEd instead of being hidden as NELZE.
VEd mode checks the actual design shear force against target VRd.

No resistance interpolation is performed. Existing catalogue helpers keep
their conservative table selection (height down, joint width up).
"""

import math
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

MODE_CATALOG = "catalog"
MODE_VED = "ved"
MODE_LABELS = {MODE_CATALOG: "Katalogová VRd", MODE_VED: "Podle VEd"}
LABEL_TO_MODE = {label: mode for mode, label in MODE_LABELS.items()}
LOGIC_VERSION = 237
_INSTALLED = False


def _number(value: Any) -> float | None:
    try:
        number = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _movement(result: dict[str, Any]) -> str:
    source = result.get("source") if isinstance(result.get("source"), dict) else {}
    return str(source.get("movement", result.get("movement", "axial")) or "axial")


def _catalog_candidates(result: dict[str, Any], target_manufacturer: str, required: float):
    """Use verified catalogue rows only; this function never interpolates."""
    from shear_dowels_catalog import design_ancon, design_schock

    movement = _movement(result)
    slab = float(result.get("slab_mm", 0) or 0)
    gap = float(result.get("gap_mm", 0) or 0)
    if "sch" in str(target_manufacturer or "").lower():
        return design_schock(
            required_vrd=required,
            slab_mm=slab,
            gap_mm=gap,
            movement=movement,
            cover_mm=int(result.get("cover_mm", 30) or 30),
        )
    return design_ancon(
        ved=required,
        slab_mm=slab,
        gap_mm=gap,
        concrete=str(result.get("concrete", "C25/30") or "C25/30"),
        movement=movement,
        application="new",
        low_sleeve=str(result.get("low_sleeve", "stainless") or "stainless"),
    )


def _best_geometry_candidate(result: dict[str, Any], target_manufacturer: str):
    # A tiny positive demand only passes the existing input guard. The returned
    # capacities are still exact catalogue table values.
    candidates, error = _catalog_candidates(result, target_manufacturer, 1e-6)
    if not candidates:
        return None, error
    return max(candidates, key=lambda candidate: float(candidate.vrd)), ""


def _append_note(target: dict[str, Any], text: str) -> None:
    current = str(target.get("note", "") or "").strip()
    target["note"] = (current + (" " if current else "") + text).strip()


def evaluate(values: dict[str, Any], target_manufacturer: str, base_substitution) -> dict[str, Any]:
    """Evaluate a substitution row in catalogue or VEd mode."""
    result = base_substitution(dict(values), target_manufacturer)
    if not isinstance(result, dict):
        result = dict(values)

    mode = str(values.get("verification_mode", result.get("verification_mode", MODE_CATALOG)) or MODE_CATALOG)
    if mode not in MODE_LABELS:
        mode = MODE_CATALOG
    result["verification_mode"] = mode
    result["substitution_logic_version"] = LOGIC_VERSION

    source = result.get("source") if isinstance(result.get("source"), dict) else {}
    source_vrd = _number(source.get("vrd"))
    if not source or source_vrd is None or source_vrd <= 0:
        return result

    if mode == MODE_VED:
        ved = _number(values.get("ved", result.get("ved")))
        result["ved"] = ved
        if ved is None or ved <= 0:
            result.update(target={}, status="CHYBÍ VEd", error="Pro režim Podle VEd zadejte VEd > 0 kN na jeden trn.")
            return result

        candidates, error = _catalog_candidates(result, target_manufacturer, ved)
        if candidates:
            target = candidates[0].as_dict()
            target["utilization"] = ved / float(target["vrd"])
            original_status = str(target.get("status", "") or "")
            result.update(
                target=target,
                status=original_status if original_status == "KONTROLA DESKY" else "VYHOVUJE dle VEd",
                error="",
                required_vrd=ved,
                capacity_ratio=float(target["vrd"]) / source_vrd,
            )
            _append_note(
                target,
                f"Návrh podle VEd = {ved:.1f} kN/trn; VRd cíle = {float(target['vrd']):.1f} kN. "
                "Shoda s katalogovou VRd původního prvku není v tomto režimu požadována. "
                "Únosnosti nejsou interpolovány.",
            )
            if ved > source_vrd + 1e-9:
                _append_note(target, f"Pozor: VEd je vyšší než katalogová VRd původního trnu {source_vrd:.1f} kN.")
            return result

        best, best_error = _best_geometry_candidate(result, target_manufacturer)
        if best is not None:
            target = best.as_dict()
            target["utilization"] = ved / float(target["vrd"])
            result.update(
                target=target,
                status="NELZE dle VEd",
                error="",
                required_vrd=ved,
                capacity_ratio=float(target["vrd"]) / source_vrd,
            )
            _append_note(
                target,
                f"Nejvyšší dostupná katalogová VRd při této geometrii je {float(target['vrd']):.1f} kN, "
                f"ale VEd = {ved:.1f} kN/trn. Únosnosti nejsou interpolovány.",
            )
        else:
            result.update(
                target={},
                status="NELZE dle VEd",
                error=error or best_error or "Pro zadané VEd nebyl nalezen použitelný cílový trn.",
            )
        return result

    result["ved"] = None
    result["required_vrd"] = source_vrd
    target = result.get("target") if isinstance(result.get("target"), dict) else {}
    if target:
        target_vrd = _number(target.get("vrd"))
        if target_vrd is not None:
            result["capacity_ratio"] = target_vrd / source_vrd
        return result

    best, _error = _best_geometry_candidate(result, target_manufacturer)
    if best is None:
        return result

    target = best.as_dict()
    target_vrd = float(target["vrd"])
    ratio = target_vrd / source_vrd
    result.update(target=target, capacity_ratio=ratio)
    if target_vrd + 1e-9 >= source_vrd:
        result.update(status=str(target.get("status", "VYHOVUJE") or "VYHOVUJE"), error="")
        return result

    result.update(status="OVĚŘIT VEd", error="", candidate_only=True)
    _append_note(
        target,
        f"Nejbližší katalogový kandidát: VRd {target_vrd:.1f} kN = {ratio * 100.0:.1f} % "
        f"původní VRd {source_vrd:.1f} kN. Nejde o záměnu 1:1 podle katalogové VRd; "
        f"použijte pouze po ověření skutečného VEd ≤ {target_vrd:.1f} kN/trn. "
        "Únosnosti nejsou interpolovány.",
    )
    return result


def _selected_indices(tree: Any) -> list[int]:
    if tree is None:
        return []
    output: list[int] = []
    for iid in tree.selection():
        try:
            output.append(int(iid))
        except (TypeError, ValueError):
            pass
    return sorted(set(output))


def _recalc_selected(owner: Any, *, mode: str, ved: float | None = None) -> None:
    tree = getattr(owner, "shear_substitution_tree", None)
    indices = _selected_indices(tree)
    if not indices:
        messagebox.showinfo("Záměny smykových trnů", "Vyberte jeden nebo více řádků.", parent=owner)
        return
    target = owner.shear_target_manufacturer_var.get()
    for index in indices:
        row = dict(owner.shear_substitution_rows[index])
        row["verification_mode"] = mode
        if mode == MODE_VED:
            row["ved"] = ved
        else:
            row.pop("ved", None)
        owner.shear_substitution_rows[index] = owner._turto_substitution_237(row, target)
    if hasattr(owner, "mark_project_dirty"):
        owner.mark_project_dirty()
    owner.refresh_shear_tables()


def _apply_selected_ved(owner: Any) -> None:
    tree = getattr(owner, "shear_substitution_tree", None)
    indices = _selected_indices(tree)
    if not indices:
        messagebox.showinfo("Záměny smykových trnů", "Vyberte jeden nebo více řádků.", parent=owner)
        return
    first = owner.shear_substitution_rows[indices[0]]
    initial = _number(first.get("ved"))
    kwargs = {"parent": owner, "minvalue": 0.000001}
    if initial is not None and initial > 0:
        kwargs["initialvalue"] = initial
    ved = simpledialog.askfloat("Ověřit podle VEd", "VEd [kN na jeden trn]:", **kwargs)
    if ved is not None:
        _recalc_selected(owner, mode=MODE_VED, ved=float(ved))


def _find_widget(root: Any, widget_type: type, text: str):
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass
        try:
            if isinstance(widget, widget_type) and str(widget.cget("text")) == text:
                return widget
        except Exception:
            pass
    return None


def _enhance_substitution_ui(owner: Any) -> None:
    if getattr(owner, "_turto_substitution_ui_237", False):
        return
    try:
        tab = owner.shear_notebook.nametowidget(owner.shear_notebook.tabs()[2])
    except Exception:
        return

    owner.shear_substitution_default_mode_var = tk.StringVar(owner, MODE_LABELS[MODE_CATALOG])
    owner.shear_substitution_default_ved_var = tk.StringVar(owner, "")

    target_label = _find_widget(tab, ttk.Label, "Cílový výrobce:")
    toolbar = target_label.master if target_label is not None else None
    if toolbar is not None:
        row = ttk.Frame(toolbar, style="Card.TFrame")
        row.grid(row=1, column=0, columnspan=10, sticky="ew", pady=(7, 0))
        ttk.Label(row, text="Výchozí režim:", style="Card.TLabel").pack(side="left")
        ttk.Combobox(
            row,
            textvariable=owner.shear_substitution_default_mode_var,
            values=tuple(MODE_LABELS.values()),
            state="readonly",
            width=19,
        ).pack(side="left", padx=(5, 12))
        ttk.Label(row, text="VEd [kN/trn]:", style="Card.TLabel").pack(side="left")
        ved_entry = ttk.Entry(row, textvariable=owner.shear_substitution_default_ved_var, width=10)
        ved_entry.pack(side="left", padx=(5, 12))
        ttk.Button(row, text="Ověřit vybrané dle VEd…", command=lambda: _apply_selected_ved(owner)).pack(side="left")
        ttk.Button(
            row,
            text="Vybrané zpět na katalogovou VRd",
            command=lambda: _recalc_selected(owner, mode=MODE_CATALOG),
        ).pack(side="left", padx=(6, 0))
        ttk.Label(row, text="Bez interpolace únosností.", style="MutedCard.TLabel").pack(side="right")

        def toggle(*_args):
            selected = LABEL_TO_MODE.get(owner.shear_substitution_default_mode_var.get(), MODE_CATALOG)
            ved_entry.configure(state="normal" if selected == MODE_VED else "disabled")

        owner.shear_substitution_default_mode_var.trace_add("write", toggle)
        toggle()

    tree = getattr(owner, "shear_substitution_tree", None)
    if tree is not None:
        columns = list(tree["columns"])
        if "mode237" not in columns:
            columns.extend(("mode237", "ved237"))
            tree.configure(columns=columns)
            tree.heading("mode237", text="Režim")
            tree.column("mode237", width=125, minwidth=105, anchor="center", stretch=False)
            tree.heading("ved237", text="VEd [kN]")
            tree.column("ved237", width=85, minwidth=75, anchor="center", stretch=False)
        tree.tag_configure("candidate237", foreground=owner.colors.get("warning_text", owner.colors.get("danger", "")))
        tree.tag_configure("ved_error237", foreground=owner.colors.get("danger", ""))

    owner._turto_substitution_ui_237 = True


def install(app_base: Any) -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    import shear_dowels_ui_214 as ui214
    import shear_dowels_ui_215 as ui215

    cls = app_base.ThermalConnectorApp
    base_substitution = ui215._substitution_from_values

    def substitution(values: dict[str, Any], target_manufacturer: str) -> dict[str, Any]:
        return evaluate(values, target_manufacturer, base_substitution)

    cls._turto_substitution_237 = staticmethod(substitution)
    ui215._substitution_from_values = substitution
    ui214._substitution_from_values = substitution

    original_sync = cls.sync_shear_substitutions_from_decoder
    original_refresh = cls.refresh_shear_tables
    original_body = cls._build_body

    def default_mode(owner: Any) -> tuple[str, float | None]:
        var = getattr(owner, "shear_substitution_default_mode_var", None)
        mode = LABEL_TO_MODE.get(var.get(), MODE_CATALOG) if var is not None else MODE_CATALOG
        ved_var = getattr(owner, "shear_substitution_default_ved_var", None)
        ved = _number(ved_var.get()) if ved_var is not None else None
        return mode, ved

    def add_substitution(owner: Any) -> None:
        values = owner.shear_substitution_vars
        mode, ved = default_mode(owner)
        try:
            if mode == MODE_VED and (ved is None or ved <= 0):
                raise ValueError("Pro režim Podle VEd zadejte VEd > 0 kN na jeden trn.")
            data = {
                "name": values["name"].get().strip() or ui214._next("Z", owner.shear_substitution_rows),
                "quantity": ui214._qty(values["qty"].get()),
                "source_designation": values["source"].get().strip(),
                "slab_mm": ui214._f(values["slab"].get()),
                "gap_mm": ui214._f(values["gap"].get()),
                "concrete": values["concrete"].get(),
                "cover_mm": int(values["cover"].get()),
                "low_sleeve": ui214._sleeve_code(values["sleeve"].get()),
                "origin": "manual",
                "verification_mode": mode,
            }
            if mode == MODE_VED:
                data["ved"] = ved
            computed = substitution(data, owner.shear_target_manufacturer_var.get())
            if not computed.get("target"):
                raise ValueError(computed.get("error") or "Záměnu nelze navrhnout.")
            owner.shear_substitution_rows.append(computed)
            ui214._mark(owner)
            owner.refresh_shear_tables()
            values["name"].set(ui214._next("Z", owner.shear_substitution_rows))
            values["source"].set("")
        except Exception as exc:
            messagebox.showerror("Záměna smykového trnu", str(exc), parent=owner)

    def sync(owner: Any) -> None:
        original_sync(owner)
        mode, ved = default_mode(owner)
        if mode == MODE_VED and (ved is None or ved <= 0):
            messagebox.showwarning(
                "Záměny smykových trnů",
                "Výchozí režim je Podle VEd, ale VEd není vyplněno. Řádky zůstaly v režimu Katalogová VRd.",
                parent=owner,
            )
            mode = MODE_CATALOG
        target = owner.shear_target_manufacturer_var.get()
        for index, existing in enumerate(owner.shear_substitution_rows):
            if existing.get("origin") != "decoder":
                continue
            row = dict(existing)
            row["verification_mode"] = mode
            if mode == MODE_VED:
                row["ved"] = ved
            else:
                row.pop("ved", None)
            owner.shear_substitution_rows[index] = substitution(row, target)
        owner.refresh_shear_tables()

    def recalc(owner: Any) -> None:
        target = owner.shear_target_manufacturer_var.get()
        owner.shear_substitution_rows = [substitution(dict(row), target) for row in owner.shear_substitution_rows]
        ui214._mark(owner)
        owner.refresh_shear_tables()

    def refresh(owner: Any) -> None:
        target = owner.shear_target_manufacturer_var.get() if hasattr(owner, "shear_target_manufacturer_var") else "Ancon"
        rows = getattr(owner, "shear_substitution_rows", [])
        for index, existing in enumerate(list(rows)):
            if not isinstance(existing, dict) or not existing.get("source_designation"):
                continue
            if int(existing.get("substitution_logic_version", 0) or 0) >= LOGIC_VERSION:
                continue
            rows[index] = substitution(dict(existing), target)

        original_refresh(owner)
        tree = getattr(owner, "shear_substitution_tree", None)
        if tree is None:
            return
        try:
            columns = tuple(tree["columns"])
        except Exception:
            return
        for index, row in enumerate(rows):
            iid = str(index)
            if not tree.exists(iid):
                continue
            mode = str(row.get("verification_mode", MODE_CATALOG) or MODE_CATALOG)
            ved = _number(row.get("ved"))
            if "mode237" in columns:
                tree.set(iid, "mode237", MODE_LABELS.get(mode, MODE_LABELS[MODE_CATALOG]))
            if "ved237" in columns:
                tree.set(iid, "ved237", f"{ved:.1f}".replace(".", ",") if ved is not None else "—")
            status = str(row.get("status", "") or "")
            if status == "OVĚŘIT VEd":
                tree.item(iid, tags=("candidate237",))
            elif status in {"NELZE dle VEd", "CHYBÍ VEd", "NELZE", "POUZE DEKODÉR"}:
                tree.item(iid, tags=("ved_error237",))

    def body(owner: Any) -> None:
        original_body(owner)
        _enhance_substitution_ui(owner)
        owner.refresh_shear_tables()

    cls.add_shear_substitution_row = add_substitution
    cls.sync_shear_substitutions_from_decoder = sync
    cls.recalculate_shear_substitutions = recalc
    cls.refresh_shear_tables = refresh
    cls._build_body = body
    ui215.recalculate_substitutions = recalc
    ui214.recalculate_substitutions = recalc

    cls._turto_shear_substitution_237 = True
    _INSTALLED = True


def selftest() -> None:
    assert MODE_LABELS[MODE_CATALOG] == "Katalogová VRd"
    assert MODE_LABELS[MODE_VED] == "Podle VEd"
    assert LOGIC_VERSION == 237


if __name__ == "__main__":
    selftest()
