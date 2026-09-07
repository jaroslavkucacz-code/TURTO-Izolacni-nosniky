from __future__ import annotations

"""PDF presentation layer for TURTO ISO 1.1.19.

Separates a completed static capacity check from a remaining geometry/Bx review:
- date is shown without processing time,
- a statically complete, passing row with confirmed automatic OU/OD geometry is
  shown as VYHOVUJE in the PDF,
- the PDF still explicitly flags Bx for verification in the project,
- internal review/audit data are not changed,
- failed, incomplete or over-utilized checks remain unchanged.
"""

from copy import deepcopy
from datetime import datetime
import math
from pathlib import Path
from typing import Any, Iterable

import substitution_pdf_base as _base

PdfExportError = _base.PdfExportError
REPORT_VERSION = "1.1.19"
_TOL = 1e-9


def _static_passes(row: dict[str, Any]) -> bool:
    target = _base._target(row)
    if not target:
        return False

    checks = _base._checks(row)
    if not checks:
        return False
    for check in checks:
        eta = _base._float(check.get("eta"))
        if not math.isfinite(eta) or eta > 1.0 + _TOL:
            return False
        result = str(check.get("result", "") or "").strip().upper()
        if result and result != "VYHOVUJE":
            return False

    overall = _base._float(target.get("utilization"))
    if not math.isfinite(overall) or overall > 1.0 + _TOL:
        return False

    if _base._interaction_applies(row):
        interaction = _base._float(target.get("interaction_utilization"))
        if not math.isfinite(interaction) or interaction > 1.0 + _TOL:
            return False

    _label, governing = _base._governing_check(row)
    return math.isfinite(governing) and governing <= 1.0 + _TOL


def _confirmed_auto_geometry(row: dict[str, Any]) -> tuple[bool, int]:
    meta = row.get("source_meta") if isinstance(row.get("source_meta"), dict) else {}
    target = str(meta.get("geometry_target", "") or "").strip().upper()
    origin = str(meta.get("geometry_origin", "") or "").strip().lower()
    try:
        bx = int(meta.get("geometry_bx_mm") or 0)
    except (TypeError, ValueError):
        bx = 0
    return target in {"OU", "OD"} and origin == "confirmed_auto" and bx > 0, bx


def _presentation_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for source in rows:
        row = deepcopy(source)
        status = str(row.get("status", "") or "").strip().upper()
        accepted = str(row.get("acceptance_text", "") or "").strip() == "Záměna potvrzena uživatelem"
        geometry_review, bx = _confirmed_auto_geometry(row)

        # Previous 1.1.18 behavior: a valid explicit user acceptance is presented
        # as VYHOVUJE instead of KONTROLA.
        if status == "KONTROLA" and accepted:
            row["status"] = "VYHOVUJE"

        # New 1.1.19 behavior: the static result and geometry review are separated.
        # This does not mutate project state; it changes only the issued PDF.
        if status == "KONTROLA" and geometry_review and _static_passes(row):
            row["status"] = "VYHOVUJE"
            row["_geometry_bx_review_mm"] = bx

        prepared.append(row)
    return prepared


class _Report(_base._Report):
    def __init__(self, rows: list[dict[str, Any]], project_name: str, creator: str):
        super().__init__(rows, project_name, creator)
        self.generated = datetime.now().strftime("%d.%m.%Y")

    def summary_row(self, row, index, widths):
        table = super().summary_row(row, index, widths)
        bx = int(row.get("_geometry_bx_review_mm") or 0)
        if not bx:
            return table

        # Rebuild only this compact summary row so the remaining geometry check
        # is visible directly below the green static result.
        target = _base._target(row)
        label, eta = _base._governing_check(row)
        status = _base._status(row)
        control = (f"{label} {_base._percent(eta)}<br/>" if not math.isnan(eta) else "")
        control += f"{status}<br/><font color=\"{_base.WARNING}\">Bx {bx} mm ověřit</font>"
        background = _base.WHITE if index % 2 == 0 else _base.PANEL
        return self.table(
            [[
                self.p(row.get("position"), bold=True),
                self.p(row.get("quantity"), align=1),
                self.p(row.get("source")),
                self.p(target.get("designation") if target else "—", bold=True),
                self.p(control, color=_base._status_color(status), markup=True),
            ]],
            widths,
            background=background,
            grid=True,
        )

    def card_flows(self, row, refs):
        flows = super().card_flows(row, refs)
        bx = int(row.get("_geometry_bx_review_mm") or 0)
        if not bx:
            return flows

        warning = self.p(
            f"Geometrie Bx = {bx} mm: nutno ověřit podle skutečné geometrie konstrukce.",
            size=10.5,
            bold=True,
            color=_base.WARNING,
        )
        meta = _base._meta(row)
        insert_at = 5 if meta.get("geometry_display") else 4
        flows.insert(min(insert_at, len(flows)), warning)
        return flows


def ensure_vector_pdf_backend() -> None:
    _base.ensure_vector_pdf_backend()


def write_substitution_pdf(
    path: Path | str,
    *,
    project_name: str,
    rows: Iterable[dict[str, Any]],
    creator: str = "Vytvořil Ing. Jaroslav Kučera",
) -> Path:
    data = _presentation_rows(rows)
    original_report = _base._Report
    original_version = _base.REPORT_VERSION
    _base._Report = _Report
    _base.REPORT_VERSION = REPORT_VERSION
    try:
        return _base.write_substitution_pdf(
            path,
            project_name=project_name,
            rows=data,
            creator=creator,
        )
    finally:
        _base._Report = original_report
        _base.REPORT_VERSION = original_version
