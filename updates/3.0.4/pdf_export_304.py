from __future__ import annotations

"""TURTO 3.0.4 - live ISO substitution PDF data and corporate PDF logo."""

from functools import wraps
from typing import Any

VERSION = "3.0.4"
_INSTALLED = False



def _status_text(value: Any) -> str:
    text = str(value or "NEPOSOUZENO").strip().upper()
    return text or "NEPOSOUZENO"


def _live_iso_substitution_rows(owner: Any) -> list[dict[str, Any]]:
    import substitution_workspace as sub
    project = getattr(owner, "project", None)
    rows = getattr(project, "rows", []) if project is not None else []
    report: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
        live_meta = sub.source_metadata(row)
        meta = dict(live_meta)
        stored = mapping.get("source_meta") if isinstance(mapping.get("source_meta"), dict) else {}
        if stored:
            meta = {**live_meta, **stored}
            for key in ("geometry_target", "geometry_bx_mm", "geometry_display", "geometry_confirmed", "geometry_origin", "warnings", "errors"):
                meta[key] = live_meta.get(key)
        source_actions, action_warnings = sub.source_element_actions(row)
        actions = sub.action_values(source_actions)
        target = sub.selected_target(mapping)
        target = dict(target) if isinstance(target, dict) else {}
        payload, _ = owner._payload(row) if hasattr(owner, "_payload") else ({}, "not_run")
        reviewed = sub.review_state(row, live_meta, action_warnings)
        status = _status_text(payload.get("status") or reviewed.get("status"))
        candidate: dict[str, Any] = {}
        if target:
            candidate = {
                "designation": target.get("designation", ""),
                "connection_type": target.get("connection_type", ""),
                "manufacturer": "Leviat",
                "physical_length_mm": target.get("length_mm", 0),
                "height": target.get("height_mm", 0),
                "cover": target.get("cover_mm", 0),
                "concrete": target.get("concrete", meta.get("target_concrete", "")),
                "utilization": target.get("utilization"),
                "m1": target.get("m1", target.get("m_capacity", 0)),
                "v1": target.get("v1", target.get("v_capacity", 0)),
                "m2": target.get("m2", 0),
                "v2": target.get("v2", 0),
                "nrd": target.get("n_capacity", 0),
                "spacing_max": target.get("spacing_max_m", 0),
                "mode": target.get("mode", ""),
                "page": target.get("page", ""),
                "source_note": target.get("calculation", ""),
            }
        notes = []
        for value in [*reviewed.get("errors", []), *reviewed.get("warnings", []), *reviewed.get("audit_notes", [])]:
            if str(value).strip() and str(value).strip() not in notes:
                notes.append(str(value).strip())
        source_designation = str(meta.get("source_text") or row.get("source_text") or "").strip()
        report.append({
            "domain_id": "thermal_breaks",
            "domain": "Izolační nosníky",
            "group": "Záměny",
            "report_tab": "substitution",
            "name": str(row.get("position") or "—"),
            "quantity": int(row.get("quantity", 1) or 1),
            "series": str(payload.get("manufacturer") or "Schöck"),
            "connection_type": str((row.get("selection") or {}).get("type_name") or ""),
            "height_mm": meta.get("source_height_mm") or "",
            "cover_mm": meta.get("source_cover_mm") or "",
            "concrete": meta.get("source_concrete") or meta.get("target_concrete") or "",
            "required_length_mm": meta.get("source_length_mm") or "",
            "actions": actions,
            "custom_actions": [
                {"label": label, "value": actions.get(key, 0), "unit": unit}
                for key, label, unit in (
                    ("m_pos", "MEd+", "kNm/prvek"), ("m_neg", "MEd−", "kNm/prvek"),
                    ("n_pos", "NEd+", "kN/prvek"), ("n_neg", "NEd−", "kN/prvek"),
                    ("v_pos", "VEd+", "kN/prvek"), ("v_neg", "VEd−", "kN/prvek"),
                ) if abs(float(actions.get(key, 0) or 0)) > 1e-12
            ],
            "candidate": candidate,
            "status": status,
            "detail": " • ".join(notes),
            "notes": notes,
            "source_designation": source_designation,
            "source_compression": meta.get("source_compression_text", ""),
            "target_compression": target.get("compression_text", "") if target else "",
            "target_m_element": target.get("m_capacity_element", 0) if target else 0,
            "target_v_element": target.get("v_capacity_element", 0) if target else 0,
            "target_n_element": target.get("n_capacity_element", 0) if target else 0,
            "import_source_text": source_designation,
        })
    return report


def _pdf_input_summary_factory(old):
    def input_summary(row: dict[str, Any], *, with_actions: bool = True) -> str:
        if row.get("domain_id") == "thermal_breaks" and row.get("report_tab") == "substitution" and row.get("source_designation"):
            parts = [str(row["source_designation"])]
            concrete = str(row.get("concrete", "") or "").strip()
            if concrete:
                parts.append(concrete)
            if with_actions:
                import hit_pdf
                action_fn = getattr(hit_pdf, "_actions", None)
                acts = action_fn(row) if callable(action_fn) else []
                if acts:
                    parts.append(" • ".join(f"{a} {v} {u}" for a, v, u in acts))
                else:
                    parts.append("bez zadaných účinků")
            return " • ".join(parts)
        return old(row, with_actions=with_actions)
    return input_summary


def _install_input_summary_patch(hit_pdf) -> None:
    import sys
    modules = [hit_pdf, sys.modules.get("hit_pdf_127"), sys.modules.get("hit_pdf_prev")]
    for module in modules:
        if module is None:
            continue
        old = getattr(module, "_input_summary", None)
        if callable(old) and not getattr(old, "_turto_pdf_304", False):
            new = _pdf_input_summary_factory(old)
            new._turto_pdf_304 = True
            module._input_summary = new
    cls = getattr(hit_pdf, "_ProposalReport", None)
    if cls is not None:
        # The oldest methods resolve globals in their defining module.
        for name in ("summary_row", "card_flows"):
            fn = getattr(cls, name, None)
            if callable(fn):
                gl = getattr(fn, "__globals__", {})
                old = gl.get("_input_summary")
                if callable(old) and not getattr(old, "_turto_pdf_304", False):
                    new = _pdf_input_summary_factory(old)
                    new._turto_pdf_304 = True
                    gl["_input_summary"] = new



def install(app_base=None) -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    import pdf_scope
    import hit_pdf
    import substitution_pdf

    old_collect = pdf_scope.collect_report_sections

    @wraps(old_collect)
    def collect(owner):
        sections = old_collect(owner)
        # Unlike the historical Treeview adapter this reads the same row,
        # mapping, selected target and actions used by the live Záměny workspace.
        sections[("thermal_breaks", "substitution")] = _live_iso_substitution_rows(owner)
        return sections

    pdf_scope.collect_report_sections = collect
    _install_input_summary_patch(hit_pdf)

    report_cls = getattr(hit_pdf, "_ProposalReport", None)
    if report_cls is not None:
        old_header = report_cls.summary_header
        old_catalog = report_cls._catalog_table

        def summary_header(self):
            rows = list(getattr(self, "rows", []))
            if rows and all(r.get("domain_id") == "thermal_breaks" and r.get("report_tab") == "substitution" for r in rows):
                widths = [40.0, 170.0, 170.0, 62.0, self.width - 442.0]
                labels = ["Poz.", "Původní označení", "Navržený HIT", "Využití", "Výsledek"]
                base = hit_pdf._base
                return self.table([[self.p(v, size=10.0, bold=True, color=base.WHITE) for v in labels]], widths, background=base.NAVY), widths
            return old_header(self)

        def catalog_table(self, row, width):
            if row.get("domain_id") == "thermal_breaks" and row.get("report_tab") == "substitution":
                vals = [
                    ("MRd / prvek", row.get("target_m_element"), "kNm/prvek"),
                    ("VRd / prvek", row.get("target_v_element"), "kN/prvek"),
                    ("NRd / prvek", row.get("target_n_element"), "kN/prvek"),
                ]
                vals = [(a,b,c) for a,b,c in vals if abs(float(b or 0)) > 1e-12]
                if vals:
                    base = hit_pdf._base
                    widths = [160.0, 105.0, width - 265.0]
                    data = [[self.p("Katalogová hodnota", size=10.5, bold=True, color=base.NAVY),
                             self.p("Hodnota", size=10.5, bold=True, color=base.NAVY, align=2),
                             self.p("Jednotka", size=10.5, bold=True, color=base.NAVY)]]
                    for label, value, unit in vals:
                        data.append([self.p(label, bold=True), self.p(str(round(float(value), 3)).replace(".", ","), align=2), self.p(unit)])
                    table = self.table(data, widths, grid=True)
                    table.setStyle(self.b["TableStyle"]([("BACKGROUND", (0,0), (-1,0), self.b["colors"].HexColor(base.PANEL))]))
                    table.repeatRows = 1
                    return table
            return old_catalog(self, row, width)

        report_cls.summary_header = summary_header
        report_cls._catalog_table = catalog_table
        report_cls._turto_pdf_logo_304 = True  # standard vector TURTO logo inherited from report base
    sub_report = getattr(substitution_pdf, "_Report", None)
    if sub_report is not None:
        sub_report._turto_pdf_logo_304 = True  # standard vector TURTO logo already bundled in assets

    if app_base is not None:
        app_base.ThermalConnectorApp._turto_pdf_export_304 = True
    _INSTALLED = True


def selftest() -> None:
    assert VERSION == "3.0.4"


if __name__ == "__main__":
    selftest()
