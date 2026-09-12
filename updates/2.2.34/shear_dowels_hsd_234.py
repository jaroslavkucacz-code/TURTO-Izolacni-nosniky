from __future__ import annotations

"""TURTO 2.2.34 – HALFEN / Leviat HSD EC 10-E (03/2026) decoder overlay."""

from typing import Any

import halfen_hsd_2026 as _hsd

_INSTALLED = False


def _is_hsd(info: Any) -> bool:
    return isinstance(info, dict) and bool(info.get("halfen_hsd_2026"))


def install(app_base: Any) -> None:
    """Install the overlay without replacing the verified 2.2.33 runtime."""
    global _INSTALLED
    if _INSTALLED:
        return

    import shear_dowels_ui as decoder_base
    import shear_dowels_ui_215 as ui215

    original_decode = decoder_base.decode_dowel
    original_enrich = ui215._enrich_decoder_row
    original_build_decoder = ui215.build_decoder
    original_substitution = ui215._substitution_from_values
    original_refresh = ui215.refresh

    def decode_dowel(designation: str):
        # HSD must be decoded by the 03/2026 catalogue overlay first. This prevents
        # a broad older pattern from silently classifying the same marking elsewhere.
        value = _hsd.decode_designation(designation)
        if value is not None:
            return value
        return original_decode(designation)

    def enrich_decoder_row(row: dict[str, Any]) -> None:
        original_enrich(row)
        try:
            info = decode_dowel(str(row.get("designation", "") or ""))
        except Exception:
            info = None
        if not _is_hsd(info):
            return

        row["manufacturer"] = str(info.get("manufacturer", "Leviat / HALFEN"))
        row["family"] = str(info.get("family", row.get("family", "")))
        row["size"] = str(info.get("size", row.get("size", "")))
        row["movement"] = str(info.get("movement", row.get("movement", "axial")))
        row["hsd_catalog"] = _hsd.CATALOG_ID
        row["hsd_catalog_edition"] = _hsd.CATALOG_EDITION
        row["hsd_hmin_mm"] = info.get("hmin_mm")
        row["hsd_max_joint_mm"] = info.get("max_joint_mm")

        capacity, error = _hsd.capacity_for(
            info,
            slab_mm=float(row.get("slab_mm", 0) or 0),
            gap_mm=float(row.get("gap_mm", 0) or 0),
            concrete=str(row.get("concrete", "C25/30") or "C25/30"),
        )
        if capacity:
            # 2.1.5 already has a generic VRd/source display path under archive_*
            # keys. Re-use it to remain backwards compatible with saved actions.
            row["archive_vrd"] = capacity["vrd"]
            row["archive_source"] = capacity["source"]
            row["archive_note"] = capacity["note"]
            row["archive_table_height_mm"] = capacity["slab_table_mm"]
            row["archive_table_gap_mm"] = capacity["gap_table_mm"]
            row["hsd_capacity"] = dict(capacity)
        else:
            row["archive_vrd"] = None
            row["archive_source"] = _hsd.CATALOG_SOURCE
            row["archive_note"] = error
            row.pop("archive_table_height_mm", None)
            row.pop("archive_table_gap_mm", None)
            row.pop("hsd_capacity", None)

    def build_decoder(owner: Any, parent: Any) -> None:
        original_build_decoder(owner, parent)
        tree = getattr(owner, "shear_decoder_tree", None)
        if tree is not None:
            try:
                tree.heading("vrd", text="VRd katalog [kN]")
                tree.heading("source", text="Zdroj / kontrola")
            except Exception:
                pass
        # Extend the explanatory sentence without changing layout.
        try:
            for widget in ui215._prev._walk(parent):
                if widget.__class__.__name__.endswith("Label"):
                    text = str(widget.cget("text"))
                    if "Historické Schöck Dorn" in text and "HSD-CRET" not in text:
                        widget.configure(
                            text=text + " Leviat/HALFEN HSD-CRET a HSD-SET se vyhodnocují z HSD EC 10-E (03/2026)."
                        )
                        break
        except Exception:
            pass

    def refresh(self: Any) -> None:
        # The 2.1.5 refresh path only renders VRd for historical Schöck rows.
        # Let it do its normal work first, then fill the same generic columns for HSD.
        original_refresh(self)
        tree = getattr(self, "shear_decoder_tree", None)
        if tree is None:
            return
        try:
            columns = tuple(tree["columns"])
            vrd_index = columns.index("vrd")
            source_index = columns.index("source")
        except Exception:
            return

        try:
            tree.tag_configure("hsd_catalog", foreground=self.colors.get("accent", self.colors.get("text", "")))
            tree.tag_configure("hsd_error", foreground=self.colors.get("warning_text", self.colors.get("danger", "")))
        except Exception:
            pass

        for iid in tree.get_children(""):
            try:
                row = self.shear_decoder_rows[int(iid)]
                info = decode_dowel(str(row.get("designation", "") or ""))
            except Exception:
                continue
            if not _is_hsd(info):
                continue

            enrich_decoder_row(row)
            capacity = row.get("hsd_capacity")
            if isinstance(capacity, dict):
                vrd_text = ui215._prev._fmt(capacity.get("vrd"))
                source_text = (
                    f"{capacity.get('source', _hsd.CATALOG_SOURCE)} • "
                    f"h tab. {capacity.get('slab_table_mm')} mm • "
                    f"spára tab. {capacity.get('gap_table_mm')} mm • "
                    f"{capacity.get('note', '')}"
                ).strip(" •")
                tag = "hsd_catalog"
            else:
                vrd_text = "—"
                source_text = (
                    f"{row.get('archive_source', _hsd.CATALOG_SOURCE)} • "
                    f"{row.get('archive_note', '')}"
                ).strip(" •")
                tag = "hsd_error"

            try:
                values = list(tree.item(iid, "values"))
                while len(values) < len(columns):
                    values.append("")
                values[vrd_index] = vrd_text
                values[source_index] = source_text
                tree.item(iid, values=values, tags=(tag,))
            except Exception:
                pass

    def hsd_substitution(values: dict[str, Any], target_manufacturer: str) -> dict[str, Any] | None:
        source_designation = str(values.get("source_designation", "") or "").strip()
        info = _hsd.decode_designation(source_designation)
        if info is None:
            return None

        result = dict(values)
        result["target_manufacturer"] = target_manufacturer
        source, error = _hsd.capacity_for(
            info,
            slab_mm=float(result.get("slab_mm", 0) or 0),
            gap_mm=float(result.get("gap_mm", 0) or 0),
            concrete=str(result.get("concrete", "C25/30") or "C25/30"),
        )
        if source is None:
            result.update({
                "source": {},
                "target": {},
                "status": "POUZE DEKODÉR" if info.get("component_only") else "NELZE",
                "error": error or "Katalogovou únosnost HSD nelze určit.",
            })
            return result

        source = dict(source)
        source.update({
            "manufacturer": "Leviat / HALFEN",
            "designation": info.get("designation", source_designation),
            "family": info.get("family", "HSD"),
            "size": info.get("size", ""),
        })

        try:
            from shear_dowels_catalog import design_ancon, design_schock
            required_vrd = float(source["vrd"])
            movement = str(source.get("movement", info.get("movement", "axial")))
            if "sch" in str(target_manufacturer or "").lower():
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

        result["source"] = source
        if not candidates:
            result.update({
                "target": {},
                "status": "NELZE",
                "error": target_error or "Pro katalogovou únosnost HSD nebyla nalezena záměna.",
            })
            return result

        target = candidates[0].as_dict()
        result["target"] = target
        result["status"] = target.get("status", "VYHOVUJE")
        result["error"] = ""
        result["hsd_catalog_source"] = True
        return result

    def substitution(values: dict[str, Any], target_manufacturer: str) -> dict[str, Any]:
        value = hsd_substitution(values, target_manufacturer)
        if value is not None:
            return value
        return original_substitution(values, target_manufacturer)

    # Patch the decoder and the exact globals used by the 2.1.4/2.1.5 UI chain.
    decoder_base.decode_dowel = decode_dowel
    ui215._enrich_decoder_row = enrich_decoder_row
    ui215.build_decoder = build_decoder
    ui215._substitution_from_values = substitution
    ui215.refresh = refresh

    # ui215 intentionally redirects the 2.1.4 workspace to its own functions.
    # Keep those redirections current so build_shear_workspace sees this overlay.
    ui215._prev.build_decoder = build_decoder
    ui215._prev._substitution_from_values = substitution
    ui215._base.decode_dowel = decode_dowel
    ui215._base.refresh = refresh

    cls = app_base.ThermalConnectorApp
    cls.refresh_shear_tables = refresh
    setattr(cls, "_turto_hsd_234_installed", True)
    _INSTALLED = True


def selftest() -> None:
    _hsd.selftest()
    assert _hsd.decode_designation("HSD-CRET 124 V")["movement"] == "transverse"
    assert _hsd.decode_designation("HSD-D 25-A4")["component_only"] is True


if __name__ == "__main__":
    selftest()
