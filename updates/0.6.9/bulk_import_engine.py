from __future__ import annotations

import json
import re
from pathlib import Path
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
    archive_source: dict[str, Any] | None = None

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
            "archive": "Archivní zdroj",
            "error": "Chyba",
        }.get(self.status, self.status)


@dataclass(frozen=True)
class BulkAnalysisSummary:
    skipped_headers: int
    exact: int
    unique: int
    confirmed: int
    review: int
    archive: int
    error: int

    @property
    def ready(self) -> int:
        return self.exact + self.unique + self.confirmed


def _archive_registry_path() -> Path:
    return Path(__file__).resolve().with_name("schoeck_archive_sources.json")


def load_schoeck_archive_sources() -> list[dict[str, Any]]:
    path = _archive_registry_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return [dict(item) for item in sources if isinstance(item, dict)]


def find_schoeck_archive_source(text: str) -> dict[str, Any] | None:
    normalized = normalize_designation_text(text)
    if "SCHOCK" not in normalized and "SCONNEX" not in normalized and "CXT" not in normalized and "TZL" not in normalized:
        return None
    for source in load_schoeck_archive_sources():
        required = [str(value).upper() for value in source.get("required_compact", []) if str(value).strip()]
        if required and all(token in normalized for token in required):
            return source
    return None


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
    has_designation = any(
        word in normalized
        for word in ("označení", "oznaceni", "designation", "typ", "nosník", "nosnik", "popis", "položka", "polozka", "název", "nazev")
    )
    has_meta = any(
        word in normalized
        for word in ("pozice", "position", "ks", "počet", "pocet", "quantity", "jednotka", "mj", "množství", "mnozstvi")
    )
    return has_designation and has_meta


PIECE_UNITS = {"kus", "ks", "pc", "pcs", "piece", "pieces"}


def parse_bulk_quantity(value: str) -> int:
    """Počet kusů z Excelu, včetně českého formátu 86,000 = 86 ks.

    Desetinný zápis je přijat pouze tehdy, pokud má nulovou desetinnou část.
    Tím se nepovolí zlomkové počty výrobků.
    """
    text = str(value or "").strip().replace("\u00a0", "")
    text = "".join(text.split())
    if not text:
        raise ValueError("Počet kusů není zadán.")
    match = re.fullmatch(r"([+-]?\d+)[,.](0+)", text)
    if match:
        text = match.group(1)
    return safe_quantity(text)


def _quantity_or_none(value: str) -> int | None:
    try:
        return parse_bulk_quantity(value)
    except ValueError:
        return None


def _is_piece_unit(value: str) -> bool:
    unit = str(value or "").strip().casefold().rstrip(".")
    return unit in PIECE_UNITS


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
        # Popis [TAB] jednotka [TAB] množství – typický export rozpočtu / výkazu výměr.
        if _is_piece_unit(values[1]):
            quantity = _quantity_or_none(values[2])
            if quantity is None:
                raise ValueError(f"Množství '{values[2]}' není platný celý počet kusů.")
            return None, quantity, values[0], ""
        quantity = _quantity_or_none(values[1])
        if quantity is not None:
            # Pozice [TAB] ks [TAB] typ.
            return values[0] or None, quantity, values[2], ""
        # Pozice [TAB] typ [TAB] poznámka.
        return values[0] or None, 1, values[1], values[2]

    # Popis [TAB] jednotka [TAB] množství [TAB] poznámka ...
    if len(values) >= 4 and _is_piece_unit(values[1]):
        quantity = _quantity_or_none(values[2])
        if quantity is None:
            raise ValueError(f"Množství '{values[2]}' není platný celý počet kusů.")
        return None, quantity, values[0], " | ".join(values[3:]).strip()

    quantity = parse_bulk_quantity(values[1] or 1)
    return values[0] or None, quantity, values[2], " | ".join(values[3:]).strip()


def _append_bulk_note(note: str, value: str) -> str:
    note = str(note or "").strip()
    value = str(value or "").strip()
    if not value:
        return note
    return f"{note} | {value}" if note else value


def preprocess_bulk_designation(designation: str, note: str = "") -> tuple[str, str]:
    """Oddělí projektové doplňky, které nejsou součástí statického katalogového klíče.

    Reálné výkazy Egcobox obsahují navíc obchodní prefix EGCOBOX, požární/izolační
    příponu (např. REI120-SW), zkrácenou délku a někdy geometrický rozměr varianty
    přímo v jejím kódu (WU280). Pro vyhledání se tyto části normalizují, ale údaje
    se neztratí: vše podstatné se uloží do poznámky projektového řádku.
    """
    text = str(designation or "").strip()
    result_note = str(note or "").strip()

    # Rozpočtové prefixy nejsou součástí označení výrobku. Zachováme však celý
    # původní řádek v BulkImportItem.raw, takže se nic auditně neztrácí.
    text = re.sub(r"^\s*M\s*\+\s*D\s*", "", text, flags=re.I)
    text = re.sub(
        r"^\s*Nosn[ýy]\s+tepeln[ěe]\s+izola[čc]n[íi]\s+prvek\s*",
        "",
        text,
        flags=re.I,
    ).strip()

    length_match = re.search(r"\s*-\s*(\d+(?:[.,]\d+)?)\s*m\s*$", text, flags=re.I)
    if length_match:
        length = length_match.group(1).replace(".", ",")
        result_note = _append_bulk_note(result_note, f"Délka prvku: {length} m")
        text = text[: length_match.start()].rstrip()

    specification_match = re.search(r"-(REI\d+)(?:-([A-Z]{2,4}))?\s*$", text, flags=re.I)
    if specification_match:
        fire = specification_match.group(1).upper()
        insulation = (specification_match.group(2) or "").upper()
        suffix = f"-{insulation}" if insulation else ""
        result_note = _append_bulk_note(result_note, f"Specifikace: {fire}{suffix}")
        text = text[: specification_match.start()].rstrip()

    text = re.sub(r"^\s*EGCOBOX(?:®)?\s+", "", text, flags=re.I).strip()

    geometry_match = re.search(
        r"\b(MXL\s*\d+(?:-K)?)-(HVS|WOS|BHS|WUS|BH|WU)(\d{2,4})(?=-)",
        text,
        flags=re.I,
    )
    if geometry_match:
        product = geometry_match.group(1)
        variant = geometry_match.group(2).upper()
        dimension = geometry_match.group(3)
        canonical = f"{product}-{variant}"
        text = text[: geometry_match.start()] + canonical + text[geometry_match.end() :]
        result_note = _append_bulk_note(result_note, f"Geometrie {variant}: {dimension} mm")

    return text.strip(), result_note


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
            designation, note = preprocess_bulk_designation(designation, note)
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

        exact_candidates = [candidate for candidate in candidates if is_exact_designation(designation, candidate.result)]
        if len(exact_candidates) == 1:
            item.result = exact_candidates[0].result
            item.candidates = exact_candidates
            item.status = "exact"
            item.message = "Úplné označení odpovídá právě jednomu katalogovému prvku."
            items.append(item)
            continue

        archive_source = find_schoeck_archive_source(designation)
        if archive_source is not None:
            item.archive_source = archive_source
            item.status = "archive"
            edition = str(archive_source.get("edition", "oficiální archiv Schöck"))
            note = str(archive_source.get("note", "")).strip()
            item.message = f"Generace není v aktivních katalogových datech. Ověřený zdroj: {edition}."
            if note:
                item.message += " " + note
            items.append(item)
            continue

        if len(candidates) == 1:
            item.result = candidates[0].result
            item.candidates = candidates
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
    counts = {"exact": 0, "unique": 0, "confirmed": 0, "review": 0, "archive": 0, "error": 0}
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
    return BulkAnalysisSummary(skipped_headers=skipped_headers, **counts)
