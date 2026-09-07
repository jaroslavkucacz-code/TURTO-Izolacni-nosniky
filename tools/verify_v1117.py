"""Regression checks for HIT-HT schedule import and catalog design."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk


def verify(directory: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(directory))
    import hit_schedule as hs
    import hit_ht
    import hit_core
    import hit_workspace as hw

    checks = 0

    def check(value, label):
        nonlocal checks
        assert value, label
        checks += 1

    def rejects(call, label, contains: str = ""):
        nonlocal checks
        try:
            call()
        except ValueError as exc:
            if contains:
                assert contains.lower() in str(exc).lower(), (label, str(exc))
            checks += 1
            return str(exc)
        raise AssertionError(label)

    # Existing 33-position schedule remains unchanged and does NOT silently become HT.
    regular = hs.parse_schedule(hs.EXAMPLE)
    check(len(regular) == 33, "existing 33-row schedule preserved")
    check(sum(r.kind == "Ohybový" for r in regular) == 28, "28 bending rows preserved")
    check(sum(r.kind == "Smykový" for r in regular) == 5, "5 vertical shear rows preserved")
    check(not any(r.errors for r in regular), "existing source still parses")
    short_vertical = regular[-2]
    check(short_vertical.kind == "Smykový" and short_vertical.length_mm == 100 and short_vertical.ved == 50,
          "100 mm VEd row remains vertical shear")
    short_payload = hs.row_defaults(short_vertical, hs.DEFAULTS, "S")
    check(short_payload["connection_type"] == "ZVX" and short_payload["hed_parallel"] == "" and short_payload["hed_perp"] == "",
          "100 mm VEd row never auto-mapped to HT")
    rejects(lambda: hs.required_length_codes("100", {100, 50}), "ordinary 100 mm length blocked", "HT")
    check(hs.required_length_codes("500", {100, 50}) == {50}, "existing 500 mm exact mapping preserved")
    check(hs.required_length_codes("1000", {100, 50}) == {100}, "existing 1000 mm exact mapping preserved")

    # Dedicated HEd parser: force-per-element only.
    ht_rows = hs.parse_schedule(hs.HT_EXAMPLE)
    check(len(ht_rows) == 3 and all(r.kind == "HT" for r in ht_rows), "HT example parses as HT")
    check(not any(r.errors for r in ht_rows), "HT example has no parser errors")
    check((ht_rows[0].h_parallel, ht_rows[0].h_perp, ht_rows[0].length_mm) == (8, None, 100),
          "parallel HT action and width")
    check((ht_rows[1].h_parallel, ht_rows[1].h_perp) == (None, 15), "perpendicular HT action")
    check((ht_rows[2].h_parallel, ht_rows[2].h_perp) == (8, 15), "combined HT actions")
    aliases = (
        ("HT HEd|| = 8 kN/prvek", 8, None),
        ("HT HEd parallelni = 8 kN/element", 8, None),
        ("HT HEd kolmo = 15 kN/ks", None, 15),
        ("HT HEd perpendicular = 15 kN/prvek", None, 15),
    )
    for text, hp, ht in aliases:
        row = hs.parse_schedule(text)[0]
        check(not row.errors and (row.h_parallel, row.h_perp) == (hp, ht), "HEd alias: " + text)
    for text in (
        "HT HEd∥ = 8 kN/m",
        "HT HEd⊥ = 15 kN",
        "HT HEd∥ = 8 kN/prvek VEd = 10 kN/m",
        "HT HEd∥ = 8 kN/prvek HEd∥ = 9 kN/prvek",
        "HT délky 0,1 m",
    ):
        row = hs.parse_schedule(text)[0]
        check(bool(row.errors), "unsafe HT input rejected: " + text)

    hp = hs.row_defaults(ht_rows[0], hs.DEFAULTS, "HT1")
    check(hp["connection_type"] == "HT" and hp["required_length"] == "100" and hp["hed_parallel"] == "8",
          "HP HT payload retains B=100 and H parallel")
    sp_no_width = hs.parse_schedule("HT HEd⊥ = 15 kN/prvek")[0]
    sp = hs.row_defaults(sp_no_width, {**hs.DEFAULTS, "series": "SP"}, "HTSP")
    check(sp["connection_type"] == "HT" and sp["required_length"] == "150" and sp["hed_perp"] == "15",
          "SP HT defaults to B=150")
    rejects(lambda: hs.row_defaults(ht_rows[0], {**hs.DEFAULTS, "series": "SP"}, "BAD"),
            "source B=100 cannot be SP HT", "150")
    check(hit_ht.validate_ht_width("100", "HP") == 100, "HP width 100 accepted")
    check(hit_ht.validate_ht_width("150", "SP") == 150, "SP width 150 accepted")
    rejects(lambda: hit_ht.validate_ht_width("150", "HP"), "HP wrong width rejected", "100")
    rejects(lambda: hit_ht.validate_ht_width("100", "SP"), "SP wrong width rejected", "150")

    # Catalog checks, HIT 20.2-EN pages 121-123.
    rows, error, info = hit_ht.design_ht_candidates("HP", 200, "C25/30", 8, 0, "100")
    check(not error and [r.code for r in rows] == ["HT1", "HT3"], "H parallel proposes HT1 then HT3")
    check(rows[0].designation == "HIT-HP HT1-20-010", "HP HT1 designation")
    check(rows[0].physical_length_mm == 100, "HP HT physical width is 100 mm")
    check(math.isclose(rows[0].m1, 11.5) and math.isclose(rows[0].v1, 0.0), "HT1 C25/30 capacity")
    check(math.isclose(rows[0].utilization, 8 / 11.5), "HT1 utilization")

    rows, error, _ = hit_ht.design_ht_candidates("HP", 200, "C25/30", 0, 15, "100")
    check(not error and [r.code for r in rows] == ["HT2", "HT3"], "H perpendicular proposes HT2 then HT3")
    check(rows[0].designation == "HIT-HP HT2-20-010", "HP HT2 designation")
    check(math.isclose(rows[0].v1, 21.2), "HT2 C25/30 capacity")

    rows, error, _ = hit_ht.design_ht_candidates("HP", 200, "C25/30", 8, 15, "100")
    check(not error and len(rows) == 1 and rows[0].code == "HT3", "combined H only proposes HT3")
    check(math.isclose(rows[0].m1, 11.5) and math.isclose(rows[0].v1, 21.2), "HT3 capacities")
    check(math.isclose(rows[0].utilization, max(8 / 11.5, 15 / 21.2)), "HT3 governing utilization")

    rows, error, _ = hit_ht.design_ht_candidates("SP", 250, "C20/25", 7, 0, "150")
    check(not error and rows[0].designation == "HIT-SP HT1-25-015", "SP designation B=150")
    check(rows[0].physical_length_mm == 150 and math.isclose(rows[0].m1, 9.9), "SP C20/25 capacity/width")
    rows30, error30, _ = hit_ht.design_ht_candidates("HP", 200, "C30/37", 8, 0, "100")
    check(not error30 and math.isclose(rows30[0].m1, 11.5), "C30/37 conservatively uses >=C25/30 table value")
    for height in (150, 360, 205):
        rows_bad, err_bad, _ = hit_ht.design_ht_candidates("HP", height, "C25/30", 8, 0, "100")
        check(not rows_bad and bool(err_bad), "HT height guard " + str(height))
    overload, overload_error, _ = hit_ht.design_ht_candidates("HP", 200, "C25/30", 50, 50, "100")
    check(not overload and "HT4/HT5" in overload_error and "MVX" in overload_error,
          "overload does not silently auto-select HT4/HT5")
    mismatch, mismatch_error, _ = hit_ht.design_ht_candidates("SP", 200, "C25/30", 8, 0, "100")
    check(not mismatch and "150" in mismatch_error, "SP width mismatch blocked")

    # Core/UI integration.
    check("HT" in hit_core.CONNECTION_TYPES, "HT is selectable connection type")
    ht_mask = hw.hit_action_field_mask("HT")
    check(ht_mask.get("h_parallel") and ht_mask.get("h_perp"), "HT H fields enabled")
    check(not any(ht_mask.get(k) for k in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg")),
          "HT M/N/V fields disabled")

    class App(hw.HitWorkspaceMixin, tk.Tk):
        def __init__(self):
            super().__init__()
            self.geometry("1360x900+0+0")
            self.colors = dict(
                bg="#F4F6F8", panel="#FFFFFF", panel_alt="#EEF2F5", text="#172B40",
                muted="#536779", border="#CCD5DF", danger="#A02020", warning_text="#926008"
            )
            self.theme_name = "light"
            self.style = ttk.Style(self)
            self.settings = {}
            self.settings_path = output / "settings.json"
            self.root_dir = directory
            self._init_hit_workspace()
            frame = ttk.Frame(self)
            frame.pack(fill="both", expand=True)
            self._build_hit_tab(frame)
        def _try_load_hit_data(self):
            self.hit_db = None
        def _save_settings(self):
            pass

    app = App()
    app.update()
    try:
        row = app.hit_rows[0]
        row.connection_type.set("HT")
        row.series.set("HP")
        row.height.set("200")
        row.required_length.set("100")
        row.concrete.set("C25/30")
        row.hed_parallel.set("8")
        row.hed_perp.set("")
        row._apply_type_constraints()
        row.recalculate()
        app.update()
        check(row.selected_candidate is not None and row.selected_candidate.code == "HT1",
              "real Tk row designs HT1 without ordinary HIT database")
        check(str(row.hed_parallel_entry.cget("state")) == "normal" and str(row.ved_pos_entry.cget("state")) == "disabled",
              "real Tk enables H and locks vertical V for HT")
        check(row.selected_candidate.designation == "HIT-HP HT1-20-010", "real Tk designation")
        check("kN/prvek" in row.action_summary(), "real Tk summary shows per-element unit")
        row.series.set("SP")
        row.recalculate()
        check(row.selected_candidate is None and "150" in row.detail.get(), "real Tk blocks HP-width value after switching to SP")
        row.required_length.set("150")
        row.recalculate()
        check(row.selected_candidate is not None and row.selected_candidate.physical_length_mm == 150,
              "real Tk SP HT accepts B=150")
        # The old vertical 100 mm line-load case remains blocked in real row logic.
        row.connection_type.set("ZVX")
        row.series.set("HP")
        row.required_length.set("100")
        row.hed_parallel.set("")
        row.ved_pos.set("50")
        row._apply_type_constraints()
        row.recalculate()
        check(row.selected_candidate is None and row.connection_type.get() == "ZVX" and not row.hed_parallel.get(), "real Tk never reinterprets VEd 100mm as HT")
    finally:
        app.destroy()

    result = dict(
        checks=checks,
        existing_schedule_positions=33,
        ht_examples=3,
        ht_auto_types=["HT1", "HT2", "HT3"],
        ht4_ht5_auto_selected=False,
        hp_width_mm=100,
        sp_width_mm=150,
        horizontal_units="kN/element only",
        vertical_line_load_auto_conversion=False,
        real_tk_integration=True,
        source="HALFEN HIT Insulated Connection ©2023, HIT 20.2-EN pages 121-123",
    )
    (output / "hit_ht_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS HIT HT:", checks, "checks")
    return result
