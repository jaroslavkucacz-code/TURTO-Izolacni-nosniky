from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from catalog_engine import CatalogDatabase, DesignationSuggestion, QueryResult
from project_model import safe_quantity


READY_STATUSES = {"exact", "unique", "confirmed"}

SELECTOR_FIELDS: tuple[tuple[str, str], ...] = (
    ("manufacturer", "výrobce"),
    ("model", "řada"),
    ("type", "typ"),
    ("generation", "generace"),
    ("moment_class", "moment / třída 1"),
    ("shear_class", "smyk / třída 2"),
    ("concrete_min", "beton"),
    ("cover", "krytí / varianta"),
    ("height_mm", "výška / rozměr"),
    ("insulation", "tloušťka izolantu"),
    ("compression", "tlakový přenos"),
)

SELECTOR_LABELS = dict(SELECTOR_FIELDS)


@dataclass
class BulkImportItem:
    line_number: int
    raw: str
    position: str
    quantity: int
    designation: str
    note: str = ""
    status: str = "error"
    message: str = ""
    result: QueryResult | None = None
    candidates: list[DesignationSuggestion] = field(default_factory=list)
    varying_keys: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status in READY_STATUSES and self.result is not None

    @property
    def status_text(self) -> str:
        return {
            "exact": "Připraveno",
            "unique": "Připraveno",
            "confirmed": "Potvrzeno",
            "review": "Doplnit",
            "error": "Chyba",
        }.get(self.status, self.status)


@dataclass(frozen=True)
class BulkAnalysisSummary:
    skipped_headers: int
    exact: int
    unique: int
    confirmed: int
    review: int
    error: int

    @property
    def ready(self) -> int:
        return self.exact + self.unique + self.confirmed


def split_bulk_line(line: str) -> list[str]:
    if "\t" in line:
        return [part.strip() for part in line.split("\t")]
    if line.count(";") >= 1:
        return [part.strip() for part in line.split(";")]
    return [line.strip()]


def looks_like_bulk_header(parts: list[str]) -> bool:
    values = [str(part).strip().casefold() for part in parts if str(part).strip()]
    if not values:
        return False
    if len(values) == 1 and values[0] in {"typ", "označení", "oznaceni", "designation", "nosník", "nosnik"}:
        return True
    normalized = " ".join(values)
    has_designation = any(word in normalized for word in ("označení", "oznaceni", "designation", "typ", "nosník", "nosnik"))
    has_meta = any(word in normalized for word in ("pozice", "position", "ks", "počet", "pocet", "quantity"))
    return has_designation and has_meta


def _quantity_or_none(value: str) -> int | None:
    try:
        return safe_quantity(value)
    except ValueError:
        return None


def interpret_bulk_parts(parts: list[str]) -> tuple[str | None, int, str, str]:
    values = list(parts)
    while values and not values[-1]:
        values.pop()
    if not values:
        raise ValueError("Prázdný řádek.")

    if len(values) == 1:
        return None, 1, values[0], ""

    if len(values) == 2:
        quantity = _quantity_or_none(values[1])
        if quantity is not None:
            # Typ [TAB] ks – nejběžnější výstup jednoduchého excelového výkazu.
            return None, quantity, values[0], ""
        # Pozice [TAB] typ.
        return values[0] or None, 1, values[1], ""

    if len(values) == 3:
        quantity = _quantity_or_none(values[1])
        if quantity is not None:
            # Pozice [TAB] ks [TAB] typ.
            return values[0] or None, quantity, values[2], ""
        # Pozice [TAB] typ [TAB] poznámka.
        return values[0] or None, 1, values[1], values[2]

    quantity = safe_quantity(values[1] or 1)
    return values[0] or None, quantity, values[2], " | ".join(values[3:]).strip()


def normalize_designation_text(value: str) -> str:
    text = str(value).upper().replace("SCHÖCK", "SCHOCK").replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace("+/-", "±").replace("+-", "±").replace("-+", "±")
    return re.sub(r"[^A-Z0-9±]+", "", text)


def selector_value(result: QueryResult, key: str) -> str:
    if key == "manufacturer":
        return str(result.family.get("manufacturer", ""))
    if key == "model":
        return str(result.family.get("model", ""))
    if key == "type":
        return str(result.family.get("type", ""))
    if key == "generation":
        return str(result.family.get("generation", ""))
    if key == "insulation":
        return result.insulation_text
    if key == "compression":
        return result.compression_transfer
    return str(result.record.get(key, ""))


def result_identity(result: QueryResult) -> tuple[str, ...]:
    return (
        str(result.catalog.get("id", "")),
        selector_value(result, "manufacturer"),
        selector_value(result, "model"),
        selector_value(result, "type"),
        selector_value(result, "generation"),
        selector_value(result, "moment_class"),
        selector_value(result, "concrete_min"),
        selector_value(result, "shear_class"),
        selector_value(result, "cover"),
        selector_value(result, "height_mm"),
    )


def dedupe_suggestions(values: Iterable[DesignationSuggestion]) -> list[DesignationSuggestion]:
    result: list[DesignationSuggestion] = []
    seen: set[tuple[str, ...]] = set()
    for item in values:
        key = result_identity(item.result)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def varying_selector_keys(candidates: list[DesignationSuggestion]) -> tuple[str, ...]:
    if len(candidates) < 2:
        return ()
    varying: list[str] = []
    for key, _label in SELECTOR_FIELDS:
        values = {selector_value(item.result, key) for item in candidates}
        if len(values) > 1:
            varying.append(key)
    return tuple(varying)


def is_exact_designation(text: str, result: QueryResult) -> bool:
    wanted = normalize_designation_text(text)
    if not wanted:
        return False
    options = [result.designation]
    aliases = result.record.get("aliases", [])
    if isinstance(aliases, list):
        options.extend(str(value) for value in aliases)
    return any(normalize_designation_text(value) == wanted for value in options if value)


def _existing_p_number(positions: Iterable[str]) -> int:
    highest = 0
    for value in positions:
        match = re.fullmatch(r"P\s*0*(\d+)", str(value).strip(), flags=re.I)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def _start_p_number(start_position: str, existing_positions: Iterable[str]) -> int:
    match = re.fullmatch(r"P\s*0*(\d+)", str(start_position).strip(), flags=re.I)
    if match:
        return max(1, int(match.group(1)))
    return _existing_p_number(existing_positions) + 1


def analyze_bulk_text(
    database: CatalogDatabase,
    text: str,
    *,
    preferred_concrete: str | None,
    existing_positions: Iterable[str] = (),
    start_position: str = "P001",
    suggestion_limit: int = 80,
) -> tuple[list[BulkImportItem], int]:
    existing = {str(value).strip() for value in existing_positions if str(value).strip()}
    reserved = set(existing)
    next_number = _start_p_number(start_position, existing)
    skipped_headers = 0
    items: list[BulkImportItem] = []

    def allocate_position() -> str:
        nonlocal next_number
        while True:
            candidate = f"P{next_number:03d}"
            next_number += 1
            if candidate not in reserved:
                reserved.add(candidate)
                return candidate

    for line_number, raw_line in enumerate(str(text).splitlines(), start=1):
        if not raw_line.strip():
            continue
        parts = split_bulk_line(raw_line)
        if looks_like_bulk_header(parts):
            skipped_headers += 1
            continue

        try:
            position, quantity, designation, note = interpret_bulk_parts(parts)
            designation = designation.strip()
            if not designation:
                raise ValueError("Chybí označení nosníku.")
            if not position:
                position = allocate_position()
            else:
                position = str(position).strip()
                reserved.add(position)
        except Exception as exc:
            items.append(
                BulkImportItem(
                    line_number=line_number,
                    raw=raw_line,
                    position="",
                    quantity=1,
                    designation="",
                    status="error",
                    message=str(exc),
                )
            )
            continue

        item = BulkImportItem(
            line_number=line_number,
            raw=raw_line,
            position=position,
            quantity=quantity,
            designation=designation,
            note=note,
        )

        try:
            candidates = dedupe_suggestions(
                database.suggest_designations(
                    designation,
                    preferred_concrete=preferred_concrete,
                    limit=max(12, int(suggestion_limit)),
                )
            )
        except Exception:
            candidates = []

        if len(candidates) == 1:
            item.result = candidates[0].result
            item.candidates = candidates
            if is_exact_designation(designation, item.result):
                item.status = "exact"
                item.message = "Úplné označení odpovídá právě jednomu katalogovému prvku."
            else:
                item.status = "unique"
                item.message = "Chybějící údaj byl jednoznačně doplněn z katalogu; neexistuje jiná platná varianta."
            items.append(item)
            continue

        if len(candidates) > 1:
            item.candidates = candidates
            item.varying_keys = varying_selector_keys(candidates)
            item.status = "review"
            if item.varying_keys:
                labels = ", ".join(SELECTOR_LABELS[key] for key in item.varying_keys)
                item.message = f"Nutno upřesnit: {labels}."
            else:
                item.message = "Nalezeno více katalogových možností; zvolte správnou variantu."
            items.append(item)
            continue

        # Poslední záchrana pro zápisy, které resolver umí jednoznačně vyhodnotit,
        # ale nevejdou se do heuristik našeptávače.
        try:
            resolved = database.resolve_designation(
                designation,
                preferred_concrete=preferred_concrete,
            )
        except Exception as exc:
            item.status = "error"
            detail = str(exc).strip()
            item.message = detail or f"Označení nebylo nalezeno pro beton {preferred_concrete or 'projektu'}."
        else:
            item.result = resolved
            item.status = "unique"
            item.message = "Označení bylo jednoznačně vyhodnoceno resolverem katalogu."
        items.append(item)

    return items, skipped_headers


def summarize_items(items: Iterable[BulkImportItem], skipped_headers: int = 0) -> BulkAnalysisSummary:
    counts = {"exact": 0, "unique": 0, "confirmed": 0, "review": 0, "error": 0}
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
    return BulkAnalysisSummary(skipped_headers=skipped_headers, **counts)
