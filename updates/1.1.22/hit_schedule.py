from __future__ import annotations

"""TURTO ISO 1.1.22 schedule import compatibility layer.

Adds quantities from a second table/Excel column and explicit ± directions
without changing the verified 1.1.17 schedule dialog and proposal engine.
"""

import copy
import re
from typing import Any

import hit_schedule_base as _base
from hit_schedule_base import *  # noqa: F401,F403 - preserve public API

_IMPORT_VERSION = "1.1.22"
_QTY_RE = re.compile(r"^\s*(\d+)\s*(?:ks|kus(?:y|ů)?)?\s*$", re.I)
_SEPARATOR_RE = re.compile(r"^[\s:=-]+$")
_PM_FIELD_RE = re.compile(
    r"(?i)(?<![a-z])(?P<field>[mv])\s*_?\s*e\s*_?\s*d\s*(?P<sign>[+-]?)\s*[=:]\s*±\s*(?=\d)"
)


def _split_source_quantity(line: str) -> tuple[str, int] | None:
    """Return (source, quantity); ignore Markdown separator rows."""
    raw = str(line or "").strip()
    if not raw:
        return None

    # Markdown table: | description | 39 |
    if "|" in raw:
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if cells and _SEPARATOR_RE.fullmatch(cells[0] or ""):
            return None
        if len(cells) >= 2:
            match = _QTY_RE.fullmatch(cells[1])
            if match:
                quantity = int(match.group(1))
                if not 1 <= quantity <= 1_000_000:
                    raise ValueError("Počet kusů musí být v rozsahu 1 až 1 000 000.")
                return cells[0], quantity

    # Excel / clipboard: description<TAB>39
    if "\t" in raw:
        cells = [cell.strip() for cell in raw.split("\t")]
        if len(cells) >= 2:
            match = _QTY_RE.fullmatch(cells[-1])
            if match:
                quantity = int(match.group(1))
                if not 1 <= quantity <= 1_000_000:
                    raise ValueError("Počet kusů musí být v rozsahu 1 až 1 000 000.")
                return "\t".join(cells[:-1]).strip(), quantity

    return raw.strip("|").strip(), 1


def _strip_plusminus(source: str) -> tuple[str, set[str]]:
    directions: set[str] = set()

    def repl(match: re.Match[str]) -> str:
        field = match.group("field").lower()
        directions.add(field)
        # Keep any explicit field sign before "="; only remove the ± in value.
        sign = match.group("sign") or ""
        return f"{field}ed{sign} = "

    return _PM_FIELD_RE.sub(repl, source), directions


def parse_schedule(text: str):
    if len(text) > 1_000_000:
        raise ValueError("Výkaz je příliš dlouhý; vložte nejvýše 1 MB textu.")

    result = []
    for original_line, raw in enumerate(str(text).splitlines(), 1):
        parsed = _split_source_quantity(raw)
        if parsed is None:
            continue
        source, quantity = parsed
        cleaned, plusminus = _strip_plusminus(source)
        records = _base.parse_schedule(cleaned)
        for row in records:
            row.line = original_line
            row.source = source
            row.quantity = quantity
            if "v" in plusminus:
                row.v_sign = "both"
            if "m" in plusminus:
                row.m_sign = "both"
            result.append(row)
            if len(result) > 500:
                raise ValueError("Najednou lze vložit nejvýše 500 pozic; výkaz rozdělte na části.")
    return result


def row_defaults(row, options: dict[str, str], name: str) -> dict[str, str]:
    opts = dict(options)
    both_v = str(getattr(row, "v_sign", "")) == "both"
    both_m = str(getattr(row, "m_sign", "")) == "both"

    # ± shear has an unambiguous two-direction counterpart in the shear family.
    if both_v and str(getattr(row, "kind", "")) == "Smykový" and opts.get("shear") == "ZVX":
        opts["shear"] = "ZDX"

    work = copy.copy(row)
    if both_v:
        work.v_sign = ""
    if both_m:
        work.m_sign = ""

    payload = _base.row_defaults(work, opts, name)
    quantity = int(getattr(row, "quantity", 1) or 1)
    if not 1 <= quantity <= 1_000_000:
        raise ValueError("Počet kusů musí být v rozsahu 1 až 1 000 000.")
    payload["quantity"] = str(quantity)

    typ = str(payload.get("connection_type", "")).upper()
    directions = _base.DIRECTIONS.get(typ, set())

    if both_v:
        if not {"ved_pos", "ved_neg"}.issubset(directions):
            raise ValueError(
                f"{typ} nepřijímá VEd±; zvolte typ, který přenáší smyk v obou směrech."
            )
        value = _base.text_number(abs(float(getattr(row, "ved", 0.0) or 0.0)))
        payload["ved_pos"] = value
        payload["ved_neg"] = value

    if both_m:
        if not {"med_pos", "med_neg"}.issubset(directions):
            raise ValueError(
                f"{typ} nepřijímá MEd±; zvolte typ, který přenáší moment v obou směrech."
            )
        value = _base.text_number(abs(float(getattr(row, "med", 0.0) or 0.0)))
        payload["med_pos"] = value
        payload["med_neg"] = value

    return payload


# The dialog class was defined in hit_schedule_base, so its methods resolve
# module globals there. Patch those globals before the dialog is used.
_base.parse_schedule = parse_schedule
_base.row_defaults = row_defaults

_ORIGINAL_DIALOG_INIT = _base.HitScheduleDialog.__init__
_ORIGINAL_RENDER = _base.HitScheduleDialog.render


def _dialog_init(self, owner) -> None:
    _ORIGINAL_DIALOG_INIT(self, owner)
    columns = list(self.tree.cget("columns"))
    if "qty" not in columns:
        self.tree.configure(columns=tuple([*columns, "qty"]))
        self.tree.heading("qty", text="Ks")
        self.tree.column("qty", width=54, minwidth=45, anchor="center", stretch=False)


def _render(self) -> None:
    _ORIGINAL_RENDER(self)

    total_quantity = 0
    for iid in self.tree.get_children(""):
        try:
            index = int(iid)
        except (TypeError, ValueError):
            continue
        record = self.records[index] if 0 <= index < len(self.records) else None
        payload = self.payloads.get(index, {})
        quantity = int(payload.get("quantity") or getattr(record, "quantity", 1) or 1)
        self.tree.set(iid, "qty", str(quantity))

        if payload.get("ved_pos") and payload.get("ved_neg"):
            if payload["ved_pos"] == payload["ved_neg"]:
                self.tree.set(iid, "v", "±" + str(payload["ved_pos"]))
        if payload.get("med_pos") and payload.get("med_neg"):
            if payload["med_pos"] == payload["med_neg"]:
                self.tree.set(iid, "m", "±" + str(payload["med_pos"]))

        if index in self.included and index in self.payloads:
            total_quantity += quantity

    if self.records:
        text = self.summary.get()
        if " ks" not in text:
            self.summary.set(text + f" • {total_quantity} ks")


_base.HitScheduleDialog.__init__ = _dialog_init
_base.HitScheduleDialog.render = _render

HitScheduleDialog = _base.HitScheduleDialog
ScheduleRecord = _base.ScheduleRecord
required_length_codes = _base.required_length_codes
