from __future__ import annotations

"""TURTO 2.2.34 – Leviat/HALFEN HSD integration for the shared shear-dowel decoder.

Only reviewed catalogue data are added. Existing Ancon, Schöck, PohlCon and
MAX FRANK engines are not altered. HSD is a decoder/source adapter, not a new
target-manufacturer design engine.
"""

from typing import Any

from leviat_hsd import SOURCE, decode_hsd, hsd_capacity

VERSION = "2.2.34"


def _fmt(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value):.{decimals}f}".replace(".", ",")
    except Exception:
        return "—"


def install_catalog_hooks() -> None:
    import shear_catalogs_227 as catalog

    if getattr(catalog, "_leviat_hsd_234", False):
        return

    previous_decode = catalog.decode_dowel
    previous_capacity = catalog.capacity_from_designation
    previous_summary = catalog.catalog_summary

    def decode_dowel(text: str):
        parsed = decode_hsd(text)
        return parsed if parsed is not None else previous_decode(text)

    def capacity_from_designation(
        designation: str, *, slab_mm: float, gap_mm: float,
        concrete: str = "C25/30", cover_mm: int = 30,
    ):
        info = decode_hsd(designation)
        if info is None:
            return previous_capacity(
                designation, slab_mm=slab_mm, gap_mm=gap_mm,
                concrete=concrete, cover_mm=cover_mm,
            )
        payload, error = hsd_capacity(
            designation, slab_mm=slab_mm, gap_mm=gap_mm, concrete=concrete,
        )
        if payload is None:
            return None, error
        return catalog.DowelCandidate(**payload), ""

    def catalog_summary() -> str:
        base = previous_summary()
        tail = "Leviat/HALFEN: HSD-CRET/HSD-CRET V, HSD-D + HSD-S/HSD-SV/HSD-P, HSD-SET"
        return base if "HSD-CRET" in base else base + " • " + tail

    catalog.decode_dowel = decode_dowel
    catalog.capacity_from_designation = capacity_from_designation
    catalog.catalog_summary = catalog_summary
    catalog._leviat_hsd_234 = True

    try:
        catalog._base.decode_dowel = decode_dowel
    except Exception:
        pass
    for module_name in ("shear_dowels_ui", "shear_dowels_ui_215", "shear_ui_227"):
        try:
            module = __import__(module_name)
            if hasattr(module, "decode_dowel"):
                module.decode_dowel = decode_dowel
            if hasattr(module, "catalog_summary"):
                module.catalog_summary = catalog_summary
        except Exception:
            pass


def _extend_autocomplete() -> None:
    try:
        import shear_autocomplete as autocomplete
    except Exception:
        return
    if getattr(autocomplete, "_leviat_hsd_234", False):
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

        for size in (122, 124, 128, 134, 140, 145, 150, 155):
            suffix = " • VRd na vyžádání" if size >= 145 else ""
            add(
                f"HSD-CRET {size}",
                f"Leviat/HALFEN • HSD-CRET • podélný posun{suffix}",
                f"CRET {size}", f"HSD CRET {size}",
            )
            add(
                f"HSD-CRET {size} V",
                f"Leviat/HALFEN • HSD-CRET V • podélný + příčný posun{suffix}",
                f"CRET {size} V", f"HSD CRET {size} V",
            )
        for size in (20, 22, 25, 30):
            add(
                f"HSD-SET {size}-A4",
                "Leviat/HALFEN • HSD-D + HSD-S • podélný posun",
                f"HSD-D {size}-A4 + HSD-S {size}",
            )
            add(
                f"HSD-SET {size} V-A4",
                "Leviat/HALFEN • HSD-D + HSD-SV • podélný + příčný posun",
                f"HSD-D {size}-A4 + HSD-SV {size}",
            )
            add(
                f"HSD-D {size}-FV + HSD-P {size}",
                "Leviat/HALFEN • HSD-D FV + plastové HSD-P • podélný posun",
                f"HSD-P {size}",
            )
        return out

    autocomplete._build_catalog = build
    autocomplete._CACHE = None
    autocomplete._leviat_hsd_234 = True


def _decorate_decoder(owner: Any) -> None:
    tree = getattr(owner, "shear_decoder_tree", None)
    rows = getattr(owner, "shear_decoder_rows", [])
    if tree is None:
        return
    try:
        tree.heading("vrd", text="VRd [kN]")
        tree.heading("source", text="Zdroj / podmínky")
        tree.tag_configure("hsd_catalog", foreground=owner.colors.get("accent", owner.colors.get("text", "")))
        tree.tag_configure("hsd_warning", foreground=owner.colors.get("warning_text", owner.colors.get("danger", "")))
    except Exception:
        pass

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        designation = str(row.get("designation", "") or "")
        info = decode_hsd(designation)
        if info is None:
            continue

        row["manufacturer"] = "Leviat"
        row["family"] = info.get("family", "")
        row["size"] = info.get("size", "")
        row["movement"] = info.get("movement", "unknown")
        row["hsd_source"] = SOURCE
        row["hsd_decoder_only"] = bool(info.get("decoder_only"))

        capacity, error = hsd_capacity(
            designation,
            slab_mm=float(row.get("slab_mm", 0) or 0),
            gap_mm=float(row.get("gap_mm", 0) or 0),
            concrete=str(row.get("concrete", "C25/30") or "C25/30"),
        )
        if capacity:
            row["hsd_vrd"] = capacity["vrd"]
            row["hsd_table_height_mm"] = capacity["slab_table_mm"]
            row["hsd_table_gap_mm"] = capacity["gap_table_mm"]
            row["hsd_note"] = capacity["note"]
            vrd_text = _fmt(capacity["vrd"])
            source_text = (
                f"HSD EC 10-E p.{capacity['page']} • h tab. {capacity['slab_table_mm']} mm • "
                f"spára tab. {capacity['gap_table_mm']} mm • {capacity['concrete_table']} • {capacity['note']}"
            )
            tag = "hsd_catalog"
        else:
            row["hsd_vrd"] = None
            row["hsd_note"] = error or str(info.get("legacy_detail", "") or "")
            vrd_text = "—"
            source_text = row["hsd_note"] or SOURCE
            tag = "hsd_warning"

        iid = str(index)
        try:
            if tree.exists(iid):
                tree.set(iid, "manufacturer", "Leviat")
                tree.set(iid, "family", row["family"])
                tree.set(iid, "size", row["size"])
                tree.set(
                    iid, "movement",
                    "axiální + příčný" if row["movement"] == "transverse"
                    else ("axiální" if row["movement"] == "axial" else "neurčeno"),
                )
                tree.set(iid, "vrd", vrd_text)
                tree.set(iid, "source", source_text)
                old_tags = tuple(tree.item(iid, "tags") or ())
                kept = tuple(t for t in old_tags if t not in {"hsd_catalog", "hsd_warning"})
                tree.item(iid, tags=kept + (tag,))
        except Exception:
            pass


def install(base: Any) -> None:
    install_catalog_hooks()
    _extend_autocomplete()

    cls = base.ThermalConnectorApp
    if getattr(cls, "_leviat_hsd_decoder_234", False):
        return

    original_refresh = cls.refresh_shear_tables

    def refresh(self):
        original_refresh(self)
        _decorate_decoder(self)

    cls.refresh_shear_tables = refresh
    cls._leviat_hsd_decoder_234 = True

    try:
        import shear_ui_227 as ui227
        import shear_catalogs_227 as catalog
        ui227.decode_dowel = catalog.decode_dowel
        ui227.catalog_summary = catalog.catalog_summary
        ui227.propose_substitution = catalog.propose_substitution
    except Exception:
        pass


def selftest() -> None:
    from leviat_hsd import selftest as data_selftest
    data_selftest()
    assert VERSION == "2.2.34"
    assert callable(_decorate_decoder)
    assert callable(install_catalog_hooks)


if __name__ == "__main__":
    selftest()
