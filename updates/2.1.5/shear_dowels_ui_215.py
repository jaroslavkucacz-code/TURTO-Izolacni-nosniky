from __future__ import annotations

"""TURTO 2.1.5 – archivní Schöck Dorn v jednotném UI smykových trnů."""

from copy import deepcopy
from typing import Any
from tkinter import messagebox, ttk

import shear_dowels_ui as _base
import shear_dowels_ui_214 as _prev
from historical_schoeck_dorn import archive_capacity, is_archive_supported, reference_cover_mm
from shear_dowels_catalog import design_ancon, design_schock
from shear_dowels_schedule_215 import ShearScheduleDialog

TARGETS = _prev.TARGETS


def _info_for_designation(designation: str) -> dict[str, Any] | None:
    try:
        value = _base.decode_dowel(designation)
    except Exception:
        value = None
    return value if isinstance(value, dict) else None


def _archive_for_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    info = _info_for_designation(str(row.get("designation", "") or ""))
    if not info or not info.get("legacy"):
        return None, ""
    if not is_archive_supported(info):
        return None, str(info.get("legacy_detail", "") or "Historické komponentové označení nemá samostatnou únosnost.")
    capacity, error = archive_capacity(
        info,
        slab_mm=float(row.get("slab_mm", 0) or 0),
        gap_mm=float(row.get("gap_mm", 0) or 0),
        concrete=str(row.get("concrete", "C25/30") or "C25/30"),
    )
    return capacity, error


def _enrich_decoder_row(row: dict[str, Any]) -> None:
    info = _info_for_designation(str(row.get("designation", "") or ""))
    if not info:
        return
    if info.get("legacy"):
        row["manufacturer"] = "Schöck – historické"
        row["family"] = str(info.get("family", row.get("family", "")))
        row["size"] = str(info.get("size", row.get("size", "")))
        row["movement"] = str(info.get("movement", row.get("movement", "axial")))
        row["archive_reference_cover_mm"] = reference_cover_mm(info)
        capacity, error = _archive_for_row(row)
        if capacity:
            row["archive_vrd"] = capacity["vrd"]
            row["archive_source"] = capacity["source"]
            row["archive_note"] = capacity["note"]
            row["archive_table_height_mm"] = capacity["slab_table_mm"]
            row["archive_table_gap_mm"] = capacity["gap_table_mm"]
        else:
            row["archive_vrd"] = None
            row["archive_source"] = ""
            row["archive_note"] = error or str(info.get("legacy_detail", "") or "")


def _hide_decoder_cover(parent: ttk.Frame) -> None:
    stack = [parent]
    while stack:
        root = stack.pop()
        try:
            children = list(root.winfo_children())
        except Exception:
            continue
        stack.extend(children)
        for child in children:
            try:
                if not isinstance(child, ttk.Label) or str(child.cget("text")) != "cnom Schöck":
                    continue
                info = child.grid_info()
                row = int(info.get("row", 0))
                column = int(info.get("column", 0))
                master = child.master
                child.grid_remove()
                for sibling in master.winfo_children():
                    if sibling is child:
                        continue
                    try:
                        sinfo = sibling.grid_info()
                        if int(sinfo.get("row", -1)) == row and int(sinfo.get("column", -1)) == column + 1:
                            sibling.grid_remove()
                            break
                    except Exception:
                        pass
                # Posuň tlačítko doleva, pokud je ve stejném formuláři.
                for sibling in master.winfo_children():
                    try:
                        if isinstance(sibling, ttk.Button) and str(sibling.cget("text")) == "Dekódovat a přidat":
                            sinfo = sibling.grid_info()
                            sibling.grid_configure(column=max(0, int(sinfo.get("column", column + 2)) - 2))
                    except Exception:
                        pass
                return
            except Exception:
                pass


_ORIGINAL_BUILD_DECODER = _prev.build_decoder


def build_decoder(owner: Any, parent: ttk.Frame) -> None:
    _ORIGINAL_BUILD_DECODER(owner, parent)
    _hide_decoder_cover(parent)

    # Uprav vysvětlení: krytí není vstupem dekodéru, archivní tabulka nese
    # vlastní referenční cnom.
    for widget in _prev._walk(parent):
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text"))
                if text.startswith("Stejně jako u izolačních nosníků lze zadávat"):
                    widget.configure(
                        text=(
                            "Stejně jako u izolačních nosníků lze zadávat jednotlivě nebo hromadně z výkazu. "
                            "Historické Schöck Dorn SLD/SLD-Q a kompletní LD/LD-Q mají archivní VRd; "
                            "referenční krytí je vlastností zdrojové tabulky, ne vstupem Dekodéru."
                        )
                    )
        except Exception:
            pass

    # Původní tabulku nahradíme rozšířenou tabulkou s archivní únosností.
    old_tree = getattr(owner, "shear_decoder_tree", None)
    if old_tree is not None:
        try:
            old_tree.master.destroy()
        except Exception:
            pass

    columns = (
        "name", "qty", "manufacturer", "family", "size", "movement",
        "designation", "vrd", "slab", "gap", "concrete", "source",
    )
    owner.shear_decoder_tree = _prev._tree(
        parent,
        row=5,
        columns=columns,
        headings=(
            "Pozice", "Ks", "Výrobce", "Typ", "Velikost", "Pohyb",
            "Označení", "VRd archiv [kN]", "h [mm]", "Spára [mm]", "Beton", "Zdroj / kontrola",
        ),
        widths=(80, 50, 120, 100, 75, 150, 300, 110, 80, 90, 90, 520),
        anchors={"name": "w", "designation": "w", "source": "w"},
    )
    owner.shear_decoder_tree.bind(
        "<Double-1>",
        lambda _event: owner.after_idle(owner.shear_decoder_to_substitution),
    )


def add_decoder(self: Any) -> None:
    _prev.init_shear_workspace(self)
    values = self.shear_decoder_vars
    try:
        info = _base.decode_dowel(values["designation"].get())
        if not info:
            raise ValueError("Označení smykového trnu nebylo rozpoznáno.")
        row = {
            "name": values["name"].get().strip() or _prev._next("S", self.shear_decoder_rows),
            "quantity": _prev._qty(values["qty"].get()),
            "designation": values["designation"].get().strip(),
            "manufacturer": info.get("manufacturer", ""),
            "family": info.get("family", ""),
            "size": info.get("size", ""),
            "movement": info.get("movement", "axial"),
            "slab_mm": _prev._f(values["slab"].get()),
            "gap_mm": _prev._f(values["gap"].get()),
            "concrete": values["concrete"].get(),
        }
        _enrich_decoder_row(row)
        self.shear_decoder_rows.append(row)
        _prev._mark(self)
        self.refresh_shear_tables()
        values["name"].set(_prev._next("S", self.shear_decoder_rows))
        values["designation"].set("")
    except Exception as exc:
        messagebox.showerror("Dekodér smykových trnů", str(exc), parent=self)


def _historical_substitution(values: dict[str, Any], target_manufacturer: str) -> dict[str, Any] | None:
    source_designation = str(values.get("source_designation", "") or "").strip()
    info = _info_for_designation(source_designation)
    if not info or not info.get("legacy"):
        return None

    result = dict(values)
    result["target_manufacturer"] = target_manufacturer

    if not is_archive_supported(info):
        result.update({
            "source": {},
            "target": {},
            "status": "POUZE DEKODÉR",
            "error": (
                "Jde o historické označení samostatné komponenty Schöck Dorn. "
                "Bez jednoznačného kompletního typu nelze určit archivní VRd."
            ),
        })
        return result

    source, error = archive_capacity(
        info,
        slab_mm=float(result.get("slab_mm", 0) or 0),
        gap_mm=float(result.get("gap_mm", 0) or 0),
        concrete=str(result.get("concrete", "C25/30") or "C25/30"),
    )
    if source is None:
        result.update({
            "source": {},
            "target": {},
            "status": "NELZE",
            "error": error or "Archivní únosnost zdrojového Schöck Dorn nelze určit.",
        })
        return result

    required_vrd = float(source["vrd"])
    movement = str(source.get("movement", "axial"))
    target_text = str(target_manufacturer or "")
    try:
        if "sch" in target_text.lower():
            candidates, target_error = design_schock(
                required_vrd=required_vrd,
                slab_mm=float(result.get("slab_mm", 0) or 0),
                gap_mm=float(result.get("gap_mm", 0) or 0),
                movement=movement,
                cover_mm=int(result.get("cover_mm", 30) or 30),
            )
        else:
            candidates, target_error = design_ancon(
                ved=required_vrd,
                slab_mm=float(result.get("slab_mm", 0) or 0),
                gap_mm=float(result.get("gap_mm", 0) or 0),
                concrete=str(result.get("concrete", "C25/30") or "C25/30"),
                movement=movement,
                application="new",
                low_sleeve=str(result.get("low_sleeve", "stainless") or "stainless"),
            )
    except Exception as exc:
        candidates, target_error = [], str(exc)

    result["source"] = dict(source)
    if not candidates:
        result.update({
            "target": {},
            "status": "NELZE",
            "error": target_error or "Pro archivní únosnost původního Dorn nebyla nalezena záměna.",
        })
        return result

    target = candidates[0].as_dict()
    result["target"] = target
    result["status"] = target.get("status", "VYHOVUJE")
    result["error"] = ""
    result["archive_source"] = True
    return result


_ORIGINAL_SUBSTITUTION = _prev._substitution_from_values


def _substitution_from_values(values: dict[str, Any], target_manufacturer: str) -> dict[str, Any]:
    historical = _historical_substitution(values, target_manufacturer)
    if historical is not None:
        return historical
    return _ORIGINAL_SUBSTITUTION(values, target_manufacturer)


def decoder_to_substitution(self: Any) -> None:
    # Krytí v kartě Záměny patří cílovému Schöck. Nesmí se přepisovat
    # historickým referenčním krytím zdrojového Dorn.
    values = getattr(self, "shear_substitution_vars", {})
    cover_before = values.get("cover").get() if isinstance(values, dict) and values.get("cover") is not None else None
    _prev.decoder_to_substitution(self)
    if cover_before is not None:
        try:
            values["cover"].set(cover_before)
        except Exception:
            pass


def sync_substitutions_from_decoder(self: Any) -> None:
    _prev.init_shear_workspace(self)
    if not self.shear_decoder_rows:
        messagebox.showinfo("Záměny smykových trnů", "Dekodér zatím neobsahuje žádné řádky.", parent=self)
        return

    target = self.shear_target_manufacturer_var.get()
    manual = [deepcopy(row) for row in self.shear_substitution_rows if row.get("origin") != "decoder"]
    synced: list[dict[str, Any]] = []
    try:
        target_cover = int(self.shear_substitution_vars["cover"].get())
    except Exception:
        target_cover = 30

    for row in self.shear_decoder_rows:
        _enrich_decoder_row(row)
        data = {
            "name": str(row.get("name", "") or _prev._next("Z", manual + synced)),
            "quantity": int(row.get("quantity", 1) or 1),
            "source_designation": str(row.get("designation", "")),
            "slab_mm": float(row.get("slab_mm", 0) or 0),
            "gap_mm": float(row.get("gap_mm", 0) or 0),
            "concrete": str(row.get("concrete", "C25/30")),
            "cover_mm": target_cover,
            "low_sleeve": "stainless",
            "origin": "decoder",
        }
        synced.append(_substitution_from_values(data, target))

    self.shear_substitution_rows = manual + synced
    _prev._mark(self)
    self.refresh_shear_tables()
    self.shear_substitution_vars["name"].set(_prev._next("Z", self.shear_substitution_rows))
    try:
        self.shear_notebook.select(2)
    except Exception:
        pass


def recalculate_substitutions(self: Any) -> None:
    target = self.shear_target_manufacturer_var.get()
    self.shear_substitution_rows = [
        _substitution_from_values(dict(row), target)
        for row in self.shear_substitution_rows
    ]
    _prev._mark(self)
    self.refresh_shear_tables()


_ORIGINAL_REFRESH = _prev.refresh


def refresh(self: Any) -> None:
    for row in getattr(self, "shear_decoder_rows", []):
        if isinstance(row, dict):
            _enrich_decoder_row(row)

    _ORIGINAL_REFRESH(self)

    tree = getattr(self, "shear_decoder_tree", None)
    if tree is None:
        return

    try:
        columns = tuple(tree["columns"])
    except Exception:
        columns = ()
    if "vrd" not in columns or "source" not in columns:
        return

    tree.tag_configure("archive", foreground=self.colors.get("accent", self.colors.get("text", "")))
    tree.tag_configure("archive_error", foreground=self.colors.get("warning_text", self.colors.get("danger", "")))

    for iid in tree.get_children(""):
        try:
            row = self.shear_decoder_rows[int(iid)]
        except Exception:
            continue
        info = _info_for_designation(str(row.get("designation", "") or ""))
        historical = bool(info and info.get("legacy"))
        capacity, error = _archive_for_row(row) if historical else (None, "")
        if capacity:
            vrd_text = _prev._fmt(capacity["vrd"])
            source_text = (
                f"{capacity['source']} • cnom ref. {capacity['reference_cover_mm']} mm • "
                f"h tab. {capacity['slab_table_mm']} mm • spára tab. {capacity['gap_table_mm']} mm"
            )
            tag = "archive"
        elif historical:
            vrd_text = "—"
            source_text = error or str(info.get("legacy_detail", "") or "")
            tag = "archive_error"
        else:
            vrd_text = "—"
            source_text = ""
            tag = ""

        values = (
            row.get("name", ""),
            row.get("quantity", 1),
            row.get("manufacturer", ""),
            row.get("family", ""),
            row.get("size", ""),
            "axiální + příčný" if row.get("movement") == "transverse" else "axiální",
            row.get("designation", ""),
            vrd_text,
            _prev._fmt(row.get("slab_mm"), 0),
            _prev._fmt(row.get("gap_mm"), 0),
            row.get("concrete", ""),
            source_text,
        )
        tree.item(iid, values=values, tags=(tag,) if tag else ())


def open_decoder_schedule(self: Any) -> None:
    # Původní 2.1.4 metoda používá globální ShearScheduleDialog; ten je níže
    # přesměrován na 2.1.5 variantu bez cnom v Dekodéru.
    _prev.open_decoder_schedule(self)
    for row in getattr(self, "shear_decoder_rows", []):
        if isinstance(row, dict):
            _enrich_decoder_row(row)
    self.refresh_shear_tables()


def install_methods(cls: Any) -> None:
    _prev.install_methods(cls)
    cls.add_shear_decoder_row = add_decoder
    cls.shear_decoder_to_substitution = decoder_to_substitution
    cls.open_shear_decoder_schedule = open_decoder_schedule
    cls.sync_shear_substitutions_from_decoder = sync_substitutions_from_decoder
    cls.recalculate_shear_substitutions = recalculate_substitutions
    cls.refresh_shear_tables = refresh


# 2.1.4 build_shear_workspace a další metody vyhledávají tyto globály až
# za běhu. Přesměrováním zachováme jedno UI bez kopírování celé implementace.
_prev.build_decoder = build_decoder
_prev.add_decoder = add_decoder
_prev._substitution_from_values = _substitution_from_values
_prev.decoder_to_substitution = decoder_to_substitution
_prev.sync_substitutions_from_decoder = sync_substitutions_from_decoder
_prev.recalculate_substitutions = recalculate_substitutions
_prev.refresh = refresh
_prev.open_decoder_schedule = open_decoder_schedule
_prev.ShearScheduleDialog = ShearScheduleDialog

_base.refresh = refresh
_base.decoder_to_substitution = decoder_to_substitution

build_shear_workspace = _prev.build_shear_workspace
init_shear_workspace = _prev.init_shear_workspace
report_rows = _prev.report_rows
serialize = _prev.serialize
load = _prev.load
clear = _prev.clear
