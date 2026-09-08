from __future__ import annotations

"""TURTO 2.2.7 – four-manufacturer shear-dowel workflow.

Adds PohlCon and MAX FRANK without changing the historical Ancon/Schöck data
layer. Decoder / Design / Substitution keep the same three-step workflow.
"""

from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

import shear_dowels_ui_215 as _ui
from historical_schoeck_dorn import archive_capacity, is_archive_supported
from shear_catalogs_227 import (
    TARGET_MANUFACTURERS,
    catalog_summary,
    decode_dowel,
    design_for_manufacturer,
    install_catalog_hooks,
    propose_substitution,
)


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _movement_text(value: Any) -> str:
    value = str(value or "")
    if value == "transverse":
        return "axiální + příčný"
    if value == "axial":
        return "axiální"
    return "neurčeno"


def init_shear_workspace(owner: Any) -> None:
    _ui.init_shear_workspace(owner)
    if not hasattr(owner, "shear_design_manufacturer_var"):
        owner.shear_design_manufacturer_var = tk.StringVar(master=owner, value="Ancon")
    if not hasattr(owner, "shear_target_manufacturer_var"):
        owner.shear_target_manufacturer_var = tk.StringVar(master=owner, value="Schöck")
    if owner.shear_design_manufacturer_var.get() not in TARGET_MANUFACTURERS:
        owner.shear_design_manufacturer_var.set("Ancon")
    if owner.shear_target_manufacturer_var.get() not in TARGET_MANUFACTURERS:
        owner.shear_target_manufacturer_var.set("Schöck")


def _find_button(root: Any, *texts: str) -> ttk.Button | None:
    wanted = set(texts)
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) in wanted:
                return widget
        except Exception:
            pass
    return None


def _update_target_combos(owner: Any, root: Any) -> None:
    target_var = str(owner.shear_target_manufacturer_var)
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Combobox) and str(widget.cget("textvariable")) == target_var:
                widget.configure(values=TARGET_MANUFACTURERS, width=14)
        except Exception:
            pass


def _install_design_selector(owner: Any, root: Any) -> None:
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return
    try:
        tabs = notebook.tabs()
        design_tab = notebook.nametowidget(tabs[1])
    except Exception:
        return

    anchor = _find_button(design_tab, "Vložit výkaz…", "Hromadný návrh z výkazu…")
    if anchor is None:
        return
    toolbar = anchor.master

    for widget in list(toolbar.winfo_children()):
        try:
            if isinstance(widget, ttk.Label) and "Výrobce návrhu" in str(widget.cget("text")):
                widget.grid_remove()
        except Exception:
            pass

    if getattr(owner, "_shear_design_manufacturer_combo_227", None) is not None:
        return
    try:
        toolbar.columnconfigure(18, weight=1)
    except Exception:
        pass
    ttk.Label(toolbar, text="Výrobce:", style="Card.TLabel", font=("Calibri", 10, "bold")).grid(
        row=0, column=19, sticky="e", padx=(16, 5)
    )
    combo = ttk.Combobox(
        toolbar,
        textvariable=owner.shear_design_manufacturer_var,
        values=TARGET_MANUFACTURERS,
        state="readonly",
        width=14,
    )
    combo.grid(row=0, column=20, sticky="e")
    owner._shear_design_manufacturer_combo_227 = combo

    tree = getattr(owner, "shear_design_tree", None)
    if tree is not None:
        try:
            tree.heading("designation", text="Navržený trn")
        except Exception:
            pass


def build_shear_workspace(owner: Any, parent: ttk.Frame) -> None:
    init_shear_workspace(owner)
    _ui.build_shear_workspace(owner, parent)
    _update_target_combos(owner, parent)
    _install_design_selector(owner, parent)

    for widget in _walk(parent):
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text"))
                if ("Ancon:" in text or "Ancon/Leviat:" in text) and "Schöck" in text:
                    widget.configure(text=catalog_summary())
        except Exception:
            pass


def _design_data(self: Any) -> dict[str, Any]:
    values = self.shear_design_vars
    return {
        "name": values["name"].get().strip() or _ui._prev._next("N", self.shear_design_rows),
        "quantity": _ui._prev._qty(values["qty"].get()),
        "ved": abs(_ui._prev._f(values["ved"].get())),
        "slab_mm": _ui._prev._f(values["slab"].get()),
        "gap_mm": _ui._prev._f(values["gap"].get()),
        "concrete": values["concrete"].get(),
        "movement": _ui._prev._movement_code(values["movement"].get()),
        "application": _ui._prev._application_code(values["application"].get()),
        "low_sleeve": _ui._prev._sleeve_code(values["sleeve"].get()),
        "manufacturer": self.shear_design_manufacturer_var.get(),
    }


def _design_row(row: dict[str, Any], fallback_manufacturer: str = "Ancon") -> tuple[dict[str, Any] | None, str]:
    manufacturer = str(row.get("manufacturer") or fallback_manufacturer or "Ancon")
    candidates, error = design_for_manufacturer(
        manufacturer,
        ved=abs(float(row.get("ved", 0) or 0)),
        slab_mm=float(row.get("slab_mm", 0) or 0),
        gap_mm=float(row.get("gap_mm", 0) or 0),
        concrete=str(row.get("concrete", "C25/30") or "C25/30"),
        movement=str(row.get("movement", "axial") or "axial"),
        application=str(row.get("application", "new") or "new"),
        low_sleeve=str(row.get("low_sleeve", "stainless") or "stainless"),
        cover_mm=int(row.get("cover_mm", 30) or 30),
    )
    if not candidates:
        return None, error or f"Nenalezen vyhovující {manufacturer}."
    return candidates[0].as_dict(), ""


def add_design(self: Any) -> None:
    init_shear_workspace(self)
    try:
        data = _design_data(self)
        candidate, error = _design_row(data, self.shear_design_manufacturer_var.get())
        if candidate is None:
            raise ValueError(error)
        data["candidate"] = candidate
        data["error"] = ""
        self.shear_design_rows.append(data)
        _ui._prev._mark(self)
        self.refresh_shear_tables()
        self.shear_design_vars["name"].set(_ui._prev._next("N", self.shear_design_rows))
        self.shear_design_vars["ved"].set("")
    except Exception as exc:
        messagebox.showerror("Návrh smykového trnu", str(exc), parent=self)


def recalculate_design_all(self: Any) -> None:
    failed = 0
    current = self.shear_design_manufacturer_var.get()
    for row in self.shear_design_rows:
        candidate, error = _design_row(row, current)
        if candidate is None:
            row["candidate"] = {}
            row["error"] = error
            failed += 1
        else:
            row["candidate"] = candidate
            row["error"] = ""
    _ui._prev._mark(self)
    self.refresh_shear_tables()
    if failed:
        messagebox.showwarning(
            "Návrh smykových trnů",
            f"Přepočet dokončen. {failed} řádků nyní nelze navrhnout.",
            parent=self,
        )


def open_design_schedule(self: Any) -> None:
    values = self.shear_design_vars
    manufacturer = self.shear_design_manufacturer_var.get()

    def design_adapter(**kwargs: Any):
        return design_for_manufacturer(manufacturer, **kwargs)

    dialog = _ui.ShearScheduleDialog(
        self,
        mode="design",
        design=design_adapter,
        defaults={
            "slab": values["slab"].get(),
            "gap": values["gap"].get(),
            "concrete": values["concrete"].get(),
            "cover": "30",
            "movement": values["movement"].get(),
            "application": values["application"].get(),
            "sleeve": values["sleeve"].get(),
        },
        existing_names={str(row.get("name", "")) for row in self.shear_design_rows},
    )
    self.wait_window(dialog)
    if not dialog.result:
        return
    if bool(dialog.replace_existing.get()):
        self.shear_design_rows = []
    for payload in dialog.result:
        row = dict(payload)
        row["manufacturer"] = manufacturer
        source = row.pop("import_source_text", "")
        if source:
            row["import_source_text"] = source
        self.shear_design_rows.append(row)
    _ui._prev._mark(self)
    self.refresh_shear_tables()
    values["name"].set(_ui._prev._next("N", self.shear_design_rows))


def _historical_substitution(values: dict[str, Any], target_manufacturer: str) -> dict[str, Any] | None:
    source_designation = str(values.get("source_designation", "") or "").strip()
    info = _ui._info_for_designation(source_designation)
    if not info or not info.get("legacy"):
        return None

    result = dict(values)
    result["target_manufacturer"] = target_manufacturer
    if not is_archive_supported(info):
        result.update({
            "source": {}, "target": {}, "status": "POUZE DEKODÉR",
            "error": str(info.get("legacy_detail") or "Historické komponentové označení nemá samostatnou únosnost."),
        })
        return result

    source, error = archive_capacity(
        info,
        slab_mm=float(result.get("slab_mm", 0) or 0),
        gap_mm=float(result.get("gap_mm", 0) or 0),
        concrete=str(result.get("concrete", "C25/30") or "C25/30"),
    )
    if source is None:
        result.update({"source": {}, "target": {}, "status": "NELZE", "error": error or "Archivní VRd nelze určit."})
        return result

    candidates, target_error = design_for_manufacturer(
        target_manufacturer,
        ved=float(source["vrd"]),
        slab_mm=float(result.get("slab_mm", 0) or 0),
        gap_mm=float(result.get("gap_mm", 0) or 0),
        concrete=str(result.get("concrete", "C25/30") or "C25/30"),
        movement=str(source.get("movement", "axial") or "axial"),
        application="new",
        low_sleeve=str(result.get("low_sleeve", "stainless") or "stainless"),
        cover_mm=int(result.get("cover_mm", 30) or 30),
    )
    result["source"] = dict(source)
    if not candidates:
        result.update({
            "target": {}, "status": "NELZE",
            "error": target_error or "Pro archivní únosnost původního Dorn nebyla nalezena záměna.",
        })
        return result
    target = candidates[0].as_dict()
    result["target"] = target
    result["status"] = target.get("status", "VYHOVUJE")
    result["error"] = ""
    result["archive_source"] = True
    return result


def substitution_from_values(values: dict[str, Any], target_manufacturer: str) -> dict[str, Any]:
    historical = _historical_substitution(values, target_manufacturer)
    if historical is not None:
        return historical

    result = dict(values)
    source_designation = str(result.get("source_designation", "") or "").strip()
    try:
        source, target, error = propose_substitution(
            source_designation=source_designation,
            target_manufacturer=target_manufacturer,
            slab_mm=float(result.get("slab_mm", 0) or 0),
            gap_mm=float(result.get("gap_mm", 0) or 0),
            concrete=str(result.get("concrete", "C25/30") or "C25/30"),
            cover_mm=int(result.get("cover_mm", 30) or 30),
            low_sleeve=str(result.get("low_sleeve", "stainless") or "stainless"),
        )
    except Exception as exc:
        source, target, error = None, None, str(exc)

    result["source"] = source.as_dict() if source is not None else {}
    result["target"] = target.as_dict() if target is not None else {}
    result["target_manufacturer"] = target_manufacturer
    if source is None or target is None:
        result["status"] = "NELZE"
        result["error"] = error or "Záměnu nelze navrhnout."
    else:
        result["status"] = target.status
        result["error"] = ""
    return result


def refresh(self: Any) -> None:
    _ui.refresh(self)

    decoder_tree = getattr(self, "shear_decoder_tree", None)
    if decoder_tree is not None:
        for index, row in enumerate(getattr(self, "shear_decoder_rows", [])):
            iid = str(index)
            if decoder_tree.exists(iid):
                try:
                    decoder_tree.set(iid, "movement", _movement_text(row.get("movement")))
                except Exception:
                    pass

    design_tree = getattr(self, "shear_design_tree", None)
    if design_tree is not None:
        try:
            design_tree.heading("designation", text="Navržený trn")
        except Exception:
            pass
        for index, row in enumerate(getattr(self, "shear_design_rows", [])):
            iid = str(index)
            if not design_tree.exists(iid):
                continue
            candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
            if candidate:
                manufacturer = str(candidate.get("manufacturer") or row.get("manufacturer") or "")
                page = str(candidate.get("page", "") or "")
                try:
                    design_tree.set(iid, "source", f"{manufacturer}" + (f" p.{page}" if page else ""))
                except Exception:
                    pass


def serialize(self: Any) -> dict[str, Any]:
    data = _ui.serialize(self)
    data["schema_version"] = max(3, int(data.get("schema_version", 0) or 0))
    data["design_manufacturer"] = self.shear_design_manufacturer_var.get() if hasattr(self, "shear_design_manufacturer_var") else "Ancon"
    data["target_manufacturer"] = self.shear_target_manufacturer_var.get() if hasattr(self, "shear_target_manufacturer_var") else "Schöck"
    return data


def load(self: Any, payload: Any) -> None:
    _ui.load(self, payload)
    init_shear_workspace(self)
    data = payload if isinstance(payload, dict) else {}
    design = str(data.get("design_manufacturer", "") or "")
    target = str(data.get("target_manufacturer", "") or "")
    if design in TARGET_MANUFACTURERS:
        self.shear_design_manufacturer_var.set(design)
    if target in TARGET_MANUFACTURERS:
        self.shear_target_manufacturer_var.set(target)
    self.refresh_shear_tables()


def _extend_autocomplete() -> None:
    import shear_autocomplete as autocomplete
    if getattr(autocomplete, "_turto_extended_227", False):
        return
    original = autocomplete._build_catalog

    def build():
        out = list(original())
        seen = {autocomplete._compact(item.designation) for item in out}

        def add(designation: str, details: str, *aliases: str) -> None:
            key = autocomplete._compact(designation)
            if key in seen:
                return
            seen.add(key)
            out.append(autocomplete.ShearSuggestion(designation, details, tuple(aliases)))

        for size, length, sleeve, sleeve_q in (
            (20, 300, 160, 180), (22, 300, 160, 180),
            (25, 300, 160, 180), (30, 350, 185, 205),
        ):
            add(
                f"PohlCon HED-S {size}/{length} + GS {size}/{sleeve}",
                "PohlCon • HED-S + GS • Jednosměrný",
                f"HED {size}", f"HED-S {size}",
            )
            add(
                f"PohlCon HED-S {size}/{length} + GSQ {size}/{sleeve_q}",
                "PohlCon • HED-S + GSQ • Obousměrný",
                f"HEDQ {size}", f"HED-S {size} GSQ",
            )
        for size in ("20 HF", "25 HF", "30 HF", "45 HF", "60 HF", "90 HF", "120 HF", "130", "150", "400", "450"):
            add(f"PohlCon JDSD {size}", "PohlCon • JDSD • Jednosměrný", f"JDSD {size}")
            if not size.startswith("20"):
                add(f"PohlCon JDSDQ {size}", "PohlCon • JDSDQ • Obousměrný", f"JDSDQ {size}")

        for size in (40, 50, 70, 95, 100, 120, 150, 210, 300, 350):
            add(f"MAX FRANK Egcodorn® WN{size}", "MAX FRANK • Egcodorn WN • Jednosměrný", f"WN {size}")
            add(f"MAX FRANK Egcodorn® WQ{size}", "MAX FRANK • Egcodorn WQ • Obousměrný", f"WQ {size}")
            add(f"MAX FRANK Egcodorn® SWN{size}", "MAX FRANK • Egcodorn SWN • Jednosměrný • stěna", f"SWN {size}")
            add(f"MAX FRANK Egcodorn® SWQ{size}", "MAX FRANK • Egcodorn SWQ • Obousměrný • stěna", f"SWQ {size}")
        add("MAX FRANK Egcodorn® N400", "MAX FRANK • Egcodorn N • Jednosměrný", "Egcodorn N 400")
        add("MAX FRANK Egcodorn® Q400", "MAX FRANK • Egcodorn Q • Obousměrný", "Egcodorn Q 400")
        for size in (20, 22, 27, 30, 37):
            add(f"MAX FRANK Egcodubel EDM {size} HF HI", "MAX FRANK • Egcodubel EDM HF • Jednosměrný", f"EDM {size} HI")
            add(f"MAX FRANK Egcodubel EDM {size} HF HQI", "MAX FRANK • Egcodubel EDM HF • Obousměrný", f"EDM {size} HQI")
        add("MAX FRANK Egcodorn® DND", "MAX FRANK • Egcodorn DND • dynamické zatížení • pouze Dekodér", "DND")
        return out

    autocomplete._build_catalog = build
    autocomplete._CACHE = None
    autocomplete._turto_extended_227 = True


def install_methods(cls: Any) -> None:
    install_catalog_hooks()
    _extend_autocomplete()

    _ui._substitution_from_values = substitution_from_values
    _ui._prev._substitution_from_values = substitution_from_values
    _ui._base.decode_dowel = decode_dowel

    cls.add_shear_design_row = add_design
    cls.open_shear_design_schedule = open_design_schedule
    cls.recalculate_shear_design_all = recalculate_design_all
    cls.refresh_shear_tables = refresh
    cls.serialize_shear_dowels = serialize
    cls.load_shear_dowels = load


def selftest() -> None:
    assert "PohlCon" in TARGET_MANUFACTURERS and "MAX FRANK" in TARGET_MANUFACTURERS
    assert callable(substitution_from_values)
    assert _movement_text("unknown") == "neurčeno"


if __name__ == "__main__":
    selftest()
