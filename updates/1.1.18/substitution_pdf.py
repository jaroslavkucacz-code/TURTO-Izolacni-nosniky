from __future__ import annotations

"""PDF compatibility layer for TURTO ISO 1.1.18.

Keeps the verified 1.1.17 vector PDF engine intact while changing only
presentation rules requested for issued reports:
- processing timestamp is displayed as date only,
- a valid user-confirmed substitution is shown as VYHOVUJE instead of KONTROLA.

The confirmation itself remains in the project/audit data and does not bypass
any failed or incomplete static check.
"""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import substitution_pdf_base as _base

PdfExportError = _base.PdfExportError
REPORT_VERSION = "1.1.18"


class _Report(_base._Report):
    def __init__(self, rows: list[dict[str, Any]], project_name: str, creator: str):
        super().__init__(rows, project_name, creator)
        self.generated = datetime.now().strftime("%d.%m.%Y")


def _presentation_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for source in rows:
        row = deepcopy(source)
        status = str(row.get("status", "") or "").strip().upper()
        confirmed = str(row.get("acceptance_text", "") or "").strip() == "Záměna potvrzena uživatelem"
        if confirmed and status == "KONTROLA":
            row["status"] = "VYHOVUJE"
        prepared.append(row)
    return prepared


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
