from __future__ import annotations
"""TURTO 2.2.39 - Aschwanden CRET 05/2026 engineering overlay.

Bare CRET markings are handled as Aschwanden CRET, never as HALFEN HSD-CRET.
Explicit HSD-CRET continues through the verified HSD EC 10-E 03/2026 path.
"""
import math
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

import cret_series_100_239 as cret

_INSTALLED = False


def _cret_info(value: Any):
    try:
        info = cret.decode_designation(value)
    except Exception:
        info = None
    return info if isinstance(info, dict) else None


def _selected_manufacturer(owner: Any) -> str:
    var = getattr(owner, "shear_design_manufacturer_var", None)
    return str(var.get() if var is not None else "Ancon / Leviat")


def _design(values: dict[str, Any], manufacturer: str):
    if "cret" in manufacturer.lower() or "aschwanden" in manufacturer.lower():
        candidates, error = cret.design_cret(
            ved=abs(float(values["ved"])),
            slab_mm=float(values["slab_mm"]),
            gap_mm=float(values["gap_mm"]),
            concrete=str(values["concrete"]),
            movement=str(values.get("movement", "axial")),
            application=str(values.get("application", "new")),
            low_sleeve=str(values.get("low_sleeve", "stainless")),
        )
        return (candidates[0].as_dict(), "") if candidates else (None, error)
    import shear_dowels_ui_214 as ui214
    return ui214._design_from_values(values)


def _enrich(row: dict[str, Any], original_enrich) -> None:
    original_enrich(row)
    info = _cret_info(str(row.get("designation", "") or ""))
    if not info:
        return
    row["manufacturer"] = info.get("manufacturer", "Leviat / Aschwanden")
    row["family"] = info.get("family", "")
    row["size"] = info.get("size", "")
    row["movement"] = info.get("movement", "axial")
    row["canonical_designation"] = info.get("designation", row.get("designation", ""))
    row["cret_catalog"] = cret.CATALOG_ID
    row["cret_catalog_edition"] = cret.CATALOG_EDITION
    row["cret_hmin_mm"] = info.get("hmin_mm")
    row["cret_corrosion_class"] = info.get("corrosion_class")
    row["cret_lateral_movement_mm"] = info.get("lateral_movement_mm")
    row.pop("hsd_capacity", None)

    if row.get("geometry_confirmed") is False:
        row["archive_vrd"] = None
        row["archive_source"] = cret.CATALOG_SOURCE
        row["archive_note"] = "Pouze typ a počet. Doplňte h, návrhovou spáru a beton."
        row.pop("cret_capacity", None)
        return

    cap, error = cret.capacity_for(
        info,
        float(row.get("slab_mm", 0) or 0),
        float(row.get("gap_mm", 0) or 0),
        str(row.get("concrete", "C25/30") or "C25/30"),
    )
    if cap:
        row["archive_vrd"] = cap["vrd"]
        row["archive_source"] = cap["source"]
        row["archive_note"] = cap["note"]
        row["archive_table_height_mm"] = cap["slab_table_mm"]
        row["archive_table_gap_mm"] = cap["gap_table_mm"]
        row["cret_capacity"] = dict(cap)
    else:
        row["archive_vrd"] = None
        row["archive_source"] = cret.CATALOG_SOURCE
        row["archive_note"] = error
        row.pop("archive_table_height_mm", None)
        row.pop("archive_table_gap_mm", None)
        row.pop("cret_capacity", None)


def _cret_base_substitution(values: dict[str, Any], target_manufacturer: str):
    result = dict(values)
    info = _cret_info(str(result.get("source_designation", "") or ""))
    if not info:
        return result
    result["target_manufacturer"] = target_manufacturer
    source, error = cret.capacity_for(
        info,
        float(result.get("slab_mm", 0) or 0),
        float(result.get("gap_mm", 0) or 0),
        str(result.get("concrete", "C25/30") or "C25/30"),
    )
    if source is None:
        result.update(source={}, target={}, status="POUZE DEKODÉR" if info.get("decoder_only") else "NELZE", error=error)
        return result
    source = dict(source)
    source.update({
        "manufacturer": "Leviat / Aschwanden",
        "designation": info.get("designation", result.get("source_designation", "")),
        "family": info.get("family", "CRET"),
        "size": info.get("size", ""),
    })
    result["source"] = source
    try:
        import shear_substitution_237 as ss237
        candidates, target_error = ss237._catalog_candidates(result, target_manufacturer, float(source["vrd"]))
    except Exception as exc:
        candidates, target_error = [], str(exc)
    if candidates:
        target = candidates[0].as_dict()
        result.update(target=target, status=target.get("status", "VYHOVUJE"), error="")
    else:
        result.update(target={}, status="NELZE", error=target_error or "Pro CRET nebyla nalezena katalogová záměna.")
    result["cret_catalog_source"] = True
    return result


def _enhance_ui(owner: Any) -> None:
    if getattr(owner, "_turto_cret_ui_239", False):
        return
    if not hasattr(owner, "shear_design_manufacturer_var"):
        owner.shear_design_manufacturer_var = tk.StringVar(owner, "Ancon / Leviat")
    try:
        tab = owner.shear_notebook.nametowidget(owner.shear_notebook.tabs()[1])
        for widget in _walk(tab):
            if isinstance(widget, ttk.Label) and str(widget.cget("text")) == "Výrobce návrhu: Ancon / Leviat":
                info = widget.grid_info()
                master = widget.master
                widget.grid_remove()
                frame = ttk.Frame(master, style="App.TFrame")
                frame.grid(row=info.get("row", 0), column=info.get("column", 7), sticky="e")
                ttk.Label(frame, text="Výrobce návrhu:", style="Muted.TLabel").pack(side="left", padx=(0, 5))
                ttk.Combobox(
                    frame,
                    textvariable=owner.shear_design_manufacturer_var,
                    values=("Ancon / Leviat", "Aschwanden CRET"),
                    state="readonly",
                    width=20,
                ).pack(side="left")
                break
        tree = getattr(owner, "shear_design_tree", None)
        if tree is not None and "designation" in tuple(tree["columns"]):
            tree.heading("designation", text="Navržený smykový trn")
    except Exception:
        pass

    try:
        import shear_autocomplete as ac
        choice = getattr(owner, "hsd_catalog_choice", None)
        if choice is not None:
            options = [
                s.designation for s in ac.all_suggestions()
                if s.designation.startswith("HSD-") or s.designation.startswith("CRET")
            ]
            choice.configure(values=list(dict.fromkeys(options)))
            choice.set("Leviat: CRET / HALFEN HSD…")
    except Exception:
        pass
    owner._turto_cret_ui_239 = True


def _walk(root: Any):
    yield root
    try:
        children = root.winfo_children()
    except Exception:
        children = ()
    for child in children:
        yield from _walk(child)


def install(app_base: Any) -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    import shear_dowels_ui as decoder_base
    import shear_dowels_ui_214 as ui214
    import shear_dowels_ui_215 as ui215
    import shear_autocomplete as ac
    import shear_substitution_237 as ss237

    cls = app_base.ThermalConnectorApp

    original_decode = decoder_base.decode_dowel
    def decode_dowel(text: str):
        info = _cret_info(text)
        return info if info is not None else original_decode(text)
    decoder_base.decode_dowel = decode_dowel
    ui214._base.decode_dowel = decode_dowel
    ui215._base.decode_dowel = decode_dowel

    original_enrich = ui215._enrich_decoder_row
    def enrich(row: dict[str, Any]):
        _enrich(row, original_enrich)
    ui215._enrich_decoder_row = enrich

    original_catalog = ac._build_catalog
    def catalog():
        rows = list(original_catalog())
        for designation, subtitle, aliases in cret.suggestions():
            rows.append(ac.ShearSuggestion(designation, subtitle, aliases))
        return rows
    ac._build_catalog = catalog
    ac._CACHE = None
    original_suggest = ac.suggest_values
    def suggest(text: str, limit: int = 10):
        q = ac._compact(text)
        exact = [
            r for r in ac.all_suggestions()
            if r.designation.startswith("CRET")
            and any(ac._compact(v) == q for v in (r.designation, *r.aliases))
        ]
        return exact[:limit] or original_suggest(text, limit)
    ac.suggest_values = suggest

    original_catalog_candidates = ss237._catalog_candidates
    def catalog_candidates(result: dict[str, Any], target_manufacturer: str, required: float):
        target = str(target_manufacturer or "").lower()
        if "cret" in target or "aschwanden" in target:
            return cret.design_cret(
                ved=required,
                slab_mm=float(result.get("slab_mm", 0) or 0),
                gap_mm=float(result.get("gap_mm", 0) or 0),
                concrete=str(result.get("concrete", "C25/30") or "C25/30"),
                movement=ss237._movement(result),
                application="new",
                low_sleeve="stainless",
            )
        return original_catalog_candidates(result, target_manufacturer, required)
    ss237._catalog_candidates = catalog_candidates

    current_substitution = ui215._substitution_from_values
    def substitution(values: dict[str, Any], target_manufacturer: str):
        if _cret_info(str(values.get("source_designation", "") or "")):
            return ss237.evaluate(values, target_manufacturer, _cret_base_substitution)
        return current_substitution(values, target_manufacturer)
    ui215._substitution_from_values = substitution
    ui214._substitution_from_values = substitution
    cls._turto_substitution_237 = staticmethod(substitution)

    new_targets = tuple(dict.fromkeys(tuple(getattr(ui214, "TARGETS", ())) + ("Aschwanden CRET",)))
    ui214.TARGETS = new_targets
    ui215.TARGETS = new_targets

    def add_design(owner: Any):
        ui214.init_shear_workspace(owner)
        values = owner.shear_design_vars
        try:
            data = {
                "name": values["name"].get().strip() or ui214._next("N", owner.shear_design_rows),
                "quantity": ui214._qty(values["qty"].get()),
                "ved": abs(ui214._f(values["ved"].get())),
                "slab_mm": ui214._f(values["slab"].get()),
                "gap_mm": ui214._f(values["gap"].get()),
                "concrete": values["concrete"].get(),
                "movement": ui214._movement_code(values["movement"].get()),
                "application": ui214._application_code(values["application"].get()),
                "low_sleeve": ui214._sleeve_code(values["sleeve"].get()),
                "design_manufacturer": _selected_manufacturer(owner),
            }
            candidate, error = _design(data, data["design_manufacturer"])
            if candidate is None:
                raise ValueError(error)
            data["candidate"] = candidate
            owner.shear_design_rows.append(data)
            ui214._mark(owner)
            owner.refresh_shear_tables()
            values["name"].set(ui214._next("N", owner.shear_design_rows))
            values["ved"].set("")
        except Exception as exc:
            messagebox.showerror("Návrh smykového trnu", str(exc), parent=owner)

    def recalc_design(owner: Any):
        failed = 0
        default_manufacturer = _selected_manufacturer(owner)
        for row in owner.shear_design_rows:
            manufacturer = str(row.get("design_manufacturer", default_manufacturer) or default_manufacturer)
            candidate, error = _design(row, manufacturer)
            row["design_manufacturer"] = manufacturer
            if candidate is None:
                row["candidate"] = {}
                row["error"] = error
                failed += 1
            else:
                row["candidate"] = candidate
                row["error"] = ""
        ui214._mark(owner)
        owner.refresh_shear_tables()
        if failed:
            messagebox.showwarning("Přepočet návrhu", f"{failed} řádků nemá vyhovující návrh.", parent=owner)

    original_open_design = cls.open_shear_design_schedule
    def open_design(owner: Any):
        if "cret" not in _selected_manufacturer(owner).lower():
            return original_open_design(owner)
        from shear_dowels_schedule_215 import ShearScheduleDialog
        values = owner.shear_design_vars
        dialog = ShearScheduleDialog(
            owner,
            mode="design",
            design=cret.design_cret,
            defaults={
                "slab": values["slab"].get(), "gap": values["gap"].get(),
                "concrete": values["concrete"].get(), "cover": "30",
                "movement": values["movement"].get(),
                "application": values["application"].get(),
                "sleeve": values["sleeve"].get(),
            },
            existing_names={str(row.get("name", "")) for row in owner.shear_design_rows},
        )
        owner.wait_window(dialog)
        if not dialog.result:
            return
        if bool(dialog.replace_existing.get()):
            owner.shear_design_rows = []
        for payload in dialog.result:
            row = dict(payload)
            row["design_manufacturer"] = "Aschwanden CRET"
            row.pop("import_source_text", None)
            owner.shear_design_rows.append(row)
        ui214._mark(owner)
        owner.refresh_shear_tables()
        values["name"].set(ui214._next("N", owner.shear_design_rows))

    cls.add_shear_design_row = add_design
    cls.recalculate_shear_design_all = recalc_design
    cls.open_shear_design_schedule = open_design

    original_refresh = cls.refresh_shear_tables
    def refresh(owner: Any):
        for row in getattr(owner, "shear_decoder_rows", []):
            if isinstance(row, dict) and _cret_info(str(row.get("designation", "") or "")):
                enrich(row)
        original_refresh(owner)
        tree = getattr(owner, "shear_decoder_tree", None)
        if tree is None:
            return
        try:
            columns = tuple(tree["columns"])
            tree.tag_configure("cret239", foreground=owner.colors.get("accent", owner.colors.get("text", "")))
            tree.tag_configure("cret239_error", foreground=owner.colors.get("warning_text", owner.colors.get("danger", "")))
        except Exception:
            return
        for iid in tree.get_children(""):
            try:
                row = owner.shear_decoder_rows[int(iid)]
            except Exception:
                continue
            info = _cret_info(str(row.get("designation", "") or ""))
            if not info:
                continue
            enrich(row)
            cap = row.get("cret_capacity")
            tag = "cret239" if isinstance(cap, dict) else "cret239_error"
            try:
                if "manufacturer" in columns: tree.set(iid, "manufacturer", row.get("manufacturer", ""))
                if "family" in columns: tree.set(iid, "family", row.get("family", ""))
                if "size" in columns: tree.set(iid, "size", row.get("size", ""))
                if "movement" in columns:
                    movement = "Podélný + příčný" if row.get("movement") == "transverse" else "Podélný"
                    if row.get("movement") == "seismic": movement = "Seismic"
                    tree.set(iid, "movement", movement)
                if "vrd" in columns:
                    tree.set(iid, "vrd", ui214._fmt(cap.get("vrd")) if isinstance(cap, dict) else "—")
                if "source" in columns:
                    if isinstance(cap, dict):
                        extra = (
                            f"h tab. {cap['slab_table_mm']} mm • spára tab. {cap['gap_table_mm']} mm • "
                            f"aD,min ρ 0,2/0,5/1,0 % = {cap['aD_min_rho_02_mm']}/"
                            f"{cap['aD_min_rho_05_mm']}/{cap['aD_min_rho_10_mm']} mm"
                        )
                        if cap.get("constructive_min_mm"):
                            extra += f" • konstr. min {cap['constructive_min_mm']} mm"
                        tree.set(iid, "source", f"{cret.CATALOG_SOURCE} • {extra}")
                    else:
                        tree.set(iid, "source", row.get("archive_note", ""))
                tree.item(iid, tags=(tag,))
            except Exception:
                pass

    cls.refresh_shear_tables = refresh

    original_body = cls._build_body
    def body(owner: Any):
        original_body(owner)
        _enhance_ui(owner)
    cls._build_body = body

    cls._turto_cret_239 = True
    _INSTALLED = True


def selftest() -> None:
    cret.selftest()
    assert _cret_info("CRET-145 V42")["manufacturer"] == "Leviat / Aschwanden"
    assert _cret_info("HSD-CRET 145") is None

if __name__ == "__main__":
    selftest()
