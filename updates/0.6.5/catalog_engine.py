from __future__ import annotations

import json
import re
import gzip
import base64
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


class CatalogError(RuntimeError):
    """Chyba při načítání nebo dotazu do katalogových dat."""


class SelectionError(CatalogError):
    """Neúplný nebo neplatný výběr prvku."""


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", str(value))]


def format_number_cs(value: float, decimals: int = 1, force_plus: bool = False) -> str:
    sign = ""
    number = float(value)
    if number < 0:
        sign = "−"
        number = abs(number)
    elif force_plus and number > 0:
        sign = "+"
    return f"{sign}{number:.{decimals}f}".replace(".", ",")


def format_moment(value: float, unit: str = "kNm/m") -> str:
    suffix = f" {unit}" if unit else ""
    return f"{format_number_cs(value)}{suffix}"


def concrete_label(value: str) -> str:
    value = str(value)
    if value in {"", "—", "-"}:
        return value or "—"
    return value if value.startswith("≥") else f"≥ {value}"


def _normalise(text: str) -> str:
    text = str(text)
    text = re.sub(r"\+/\-(?=[A-Za-z0-9])", "±-", text)
    text = re.sub(r"\+\-(?=[A-Za-z0-9])", "±-", text)
    text = re.sub(r"\-\+(?=[A-Za-z0-9])", "±-", text)
    text = text.replace("+/-", "±").replace("+-", "±").replace("-+", "±")
    text = text.upper().replace("SCHÖCK", "SCHOCK").replace("ISOKORB®", "ISOKORB").replace("ISOPRO®", "ISOPRO")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def format_result(record: dict[str, Any]) -> str:
    label = str(record.get("label") or record.get("key") or "Hodnota")
    unit = str(record.get("unit") or "")
    suffix = f" {unit}" if unit else ""
    if "text" in record:
        return f"{label} = {record['text']}{suffix}"
    if "positive" in record or "negative" in record:
        pos = float(record.get("positive", 0.0))
        neg = float(record.get("negative", -pos))
        if abs(pos + neg) < 1e-9:
            value = f"±{format_number_cs(abs(pos))}"
        else:
            value = f"{format_number_cs(pos, force_plus=True)} / {format_number_cs(neg)}"
        return f"{label} = {value}{suffix}"
    if "value" in record:
        return f"{label} = {format_number_cs(float(record['value']))}{suffix}"
    return f"{label} = —"


def format_result_value(record: dict[str, Any]) -> str:
    text = format_result(record)
    return text.split(" = ", 1)[1] if " = " in text else text


def format_shear(record: dict[str, Any]) -> str:
    """Zpětně kompatibilní formátování legacy i generického záznamu."""
    if "v_rd_z_positive" in record:
        positive = float(record["v_rd_z_positive"])
        negative = record.get("v_rd_z_negative")
        unit = record.get("unit", "kN/m")
        if negative is None:
            return f"{format_number_cs(positive)} {unit}"
        negative = float(negative)
        if abs(positive + negative) < 1e-9:
            return f"±{format_number_cs(abs(positive))} {unit}"
        return f"{format_number_cs(positive, force_plus=True)} / {format_number_cs(negative)} {unit}"
    return format_result_value(record)


@dataclass(frozen=True)
class QueryResult:
    catalog: dict[str, Any]
    family: dict[str, Any]
    record: dict[str, Any]

    @property
    def designation(self) -> str:
        return str(self.record.get("designation") or "—")

    @property
    def results(self) -> list[dict[str, Any]]:
        return list(self.record.get("results", []))

    @property
    def source_pages(self) -> list[int]:
        pages = self.record.get("source_pages") or self.family.get("source_pages") or []
        return sorted({int(p) for p in pages})

    @property
    def insulation_thickness_mm(self) -> int | None:
        value = self.record.get("insulation_thickness_mm", self.family.get("insulation_thickness_mm"))
        if value not in (None, "", "—"):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                pass
        manufacturer = str(self.family.get("manufacturer", ""))
        model = str(self.family.get("model", ""))
        if manufacturer == "Schöck":
            if model == "T": return 80
            if model == "XT": return 120
        if manufacturer == "ISOPRO":
            return 80
        return None

    @property
    def insulation_text(self) -> str:
        value = self.insulation_thickness_mm
        return f"{value} mm" if value is not None else "—"

    @property
    def compression_transfer(self) -> str:
        explicit = self.record.get("compression_transfer", self.family.get("compression_transfer"))
        if explicit not in (None, "", "—", "dle typu – viz katalog"):
            return str(explicit)
        manufacturer = str(self.family.get("manufacturer", ""))
        typ = str(self.family.get("type", ""))
        if manufacturer == "Schöck":
            if typ == "QP-Z": return "bez tlakových ložisek"
            if typ in {"QL", "QP"}: return "betonová tlaková ložiska"
            if typ in {"SKP", "SQP"}: return "tlaková ložiska / tlačená výztuž"
        if manufacturer == "ISOPRO":
            if typ in {"A-IP", "A-IPQ", "A-IPQS"}: return "betonová tlaková ložiska"
            if typ in {"A-IPZQ", "A-IPQZ"}: return "bez tlakových ložisek"
            if typ in {"A-IPT", "A-IPTQQ", "A-IPTQQS", "A-IPTD", "A-IPTS", "A-IPTW"}:
                return "tlačené ocelové pruty"
        return str(explicit) if explicit not in (None, "", "—") else "neuvedeno / dle typu"

    def _first(self, kinds: Iterable[str]) -> dict[str, Any] | None:
        wanted = set(kinds)
        return next((r for r in self.results if str(r.get("kind")) in wanted), None)

    @property
    def moment_result(self) -> dict[str, Any] | None:
        return self._first(["moment"])

    @property
    def force_result(self) -> dict[str, Any] | None:
        return self._first(["shear", "horizontal", "normal"])

    @property
    def moment_text(self) -> str:
        r = self.moment_result
        return format_result_value(r) if r else "—"

    @property
    def shear_text(self) -> str:
        r = self._first(["shear"])
        if r is None:
            r = self._first(["horizontal", "normal"])
        return format_result_value(r) if r else "—"

    @property
    def other_text(self) -> str:
        first_m = self.moment_result
        first_f = self.force_result
        extra = [r for r in self.results if r is not first_m and r is not first_f]
        return "\n".join(format_result(r) for r in extra) if extra else "—"

    @property
    def all_results_text(self) -> str:
        return "\n".join(format_result(r) for r in self.results) or "—"

    # Compatibility for older UI/project code while it is being migrated.
    @property
    def moment(self) -> dict[str, Any]:
        r = self.moment_result
        value = 0.0
        unit = ""
        convention = None
        if r:
            if "value" in r:
                value = float(r["value"])
            elif "negative" in r:
                value = float(r["negative"])
            elif "positive" in r:
                value = float(r["positive"])
            unit = str(r.get("unit") or "")
            convention = r.get("note")
        return {"m_rd_y": value, "unit": unit, "source_page": self.source_pages[0] if self.source_pages else 1, "value_convention": convention}

    @property
    def shear(self) -> dict[str, Any]:
        r = self._first(["shear", "horizontal", "normal"])
        if not r:
            return {"v_rd_z_positive": 0.0, "unit": "", "source_page": self.source_pages[0] if self.source_pages else 1}
        if "positive" in r or "negative" in r:
            pos = float(r.get("positive", 0.0)); neg = r.get("negative")
        elif "value" in r:
            pos = float(r["value"]); neg = None
        else:
            pos = 0.0; neg = None
        return {"v_rd_z_positive": pos, "v_rd_z_negative": neg, "unit": r.get("unit", ""), "source_page": self.source_pages[0] if self.source_pages else 1}

    def clipboard_text(self) -> str:
        pages = ", ".join(str(p) for p in self.source_pages)
        return (
            f"{self.designation}\n"
            f"{self.all_results_text}\n"
            f"Izolant: {self.insulation_text}\n"
            f"Tlakový přenos: {self.compression_transfer}\n"
            f"Katalog: {self.catalog.get('edition','—')}, {self.catalog.get('publication_label','—')}, str. {pages or '—'}"
        )


@dataclass(frozen=True)
class DesignationSuggestion:
    """Jeden návrh našeptávače označení."""

    result: QueryResult
    score: float
    matched_tokens: tuple[str, ...] = ()

    @property
    def designation(self) -> str:
        return self.result.designation

    @property
    def values_text(self) -> str:
        parts = [self.result.insulation_text]
        pressure = self.result.compression_transfer
        if pressure and pressure != "neuvedeno / dle typu":
            short = pressure.replace("betonová tlaková ložiska", "tlak. ložiska").replace("tlačené ocelové pruty", "ocel. tlak. pruty").replace("bez tlakových ložisek", "bez tlak. ložisek")
            parts.append(short)
        parts.extend(x for x in (self.result.moment_text, self.result.shear_text) if x and x != "—")
        if len(parts) <= 2:
            other = self.result.other_text
            if other and other != "—":
                parts.append(other.split("\n", 1)[0].split(" = ", 1)[-1])
        return "  |  ".join(x for x in parts if x and x != "—") or "—"

    @property
    def context_text(self) -> str:
        f = self.result.family
        bits = [str(f.get("manufacturer", "")), str(f.get("model", "")), str(f.get("type", ""))]
        gen = str(f.get("generation", ""))
        if gen and gen != "—":
            bits.append(f"gen. {gen}")
        return " • ".join(x for x in bits if x)


class CatalogDatabase:
    """Databáze více výrobců a více historických vydání katalogů."""

    def __init__(self, catalog_directory: Path | str):
        self.catalog_directory = Path(catalog_directory)
        self.catalogs: dict[str, dict[str, Any]] = {}
        self.families: list[dict[str, Any]] = []
        self.load_errors: list[str] = []
        self._designation_index: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
        self._suggestion_entries: list[dict[str, Any]] = []
        self._suggestion_token_index: dict[str, set[int]] = defaultdict(set)
        self._suggestion_vocabulary: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.catalog_directory.exists():
            raise CatalogError(f"Adresář katalogů neexistuje: {self.catalog_directory}")
        files = sorted(list(self.catalog_directory.glob("*.json")) + list(self.catalog_directory.glob("*.json.gz.b64")))
        chunk_groups: dict[str, list[Path]] = defaultdict(list)
        for part in self.catalog_directory.glob("*.json.gz.b64.part*"):
            chunk_groups[part.name.split(".part", 1)[0]].append(part)
        if not files and not chunk_groups:
            raise CatalogError(f"V adresáři nejsou žádná katalogová data: {self.catalog_directory}")
        for path in files:
            try:
                if path.name.endswith(".json.gz.b64"):
                    raw = base64.b64decode(path.read_text(encoding="ascii"))
                    package = json.loads(gzip.decompress(raw).decode("utf-8"))
                else:
                    package = json.loads(path.read_text(encoding="utf-8"))
                self._load_package(path, package)
            except Exception as exc:
                self.load_errors.append(f"{path.name}: {exc}")
        for base_name, parts in sorted(chunk_groups.items()):
            try:
                text = "".join(p.read_text(encoding="ascii").strip() for p in sorted(parts, key=lambda x: natural_key(x.name)))
                raw = base64.b64decode(text)
                package = json.loads(gzip.decompress(raw).decode("utf-8"))
                self._load_package(self.catalog_directory / base_name, package)
            except Exception as exc:
                self.load_errors.append(f"{base_name} (části): {exc}")
        if not self.catalogs or not self.families:
            raise CatalogError("Nepodařilo se načíst žádná použitelná data.\n" + "\n".join(self.load_errors))
        for fam in self.families:
            for r in fam.get("records", []):
                for text in [r.get("designation"), *(r.get("aliases") or [])]:
                    if text:
                        self._designation_index.setdefault(_normalise(str(text)), []).append((fam, r))
        self._build_suggestion_index()

    def _load_package(self, path: Path, package: dict[str, Any]) -> None:
        version = int(package.get("schema_version", 0))
        if version not in {2, 3}:
            raise CatalogError(f"Nepodporovaná verze datového schématu {version}; očekáváno 2 nebo 3.")
        catalog = dict(package["catalog"])
        catalog_id = str(catalog["id"])
        if catalog_id in self.catalogs:
            raise CatalogError(f"Duplicitní ID katalogu {catalog_id!r}.")
        catalog["_data_file"] = str(path)
        self.catalogs[catalog_id] = catalog
        shared = package.get("shared_matrices", {}) if version >= 3 else {}
        for source in package.get("families", []):
            fam = dict(source); fam["catalog_id"] = catalog_id; fam["catalog"] = catalog
            if fam.get("backend") == "matrix" and fam.get("matrix_ref"):
                matrix = shared.get(str(fam.get("matrix_ref")))
                if not isinstance(matrix, dict):
                    raise CatalogError(f"Chybí sdílená matice {fam.get('matrix_ref')!r} pro {fam.get('type')!r}.")
                fam["moment_rows"] = matrix.get("moment_rows", [])
                fam["shear_rows"] = matrix.get("shear_rows", [])
            fam.setdefault("selector_labels", {})
            self.families.append(fam)

    def manufacturers(self) -> list[str]:
        return sorted({str(f["manufacturer"]) for f in self.families}, key=natural_key)

    def catalogs_for(self, manufacturer: str) -> list[dict[str, Any]]:
        ids = {f["catalog_id"] for f in self.families if f["manufacturer"] == manufacturer}
        return sorted((self.catalogs[i] for i in ids), key=lambda x: x.get("publication_date", ""), reverse=True)

    def newest_catalog_id(self, manufacturer: str) -> str | None:
        c = self.catalogs_for(manufacturer)
        return str(c[0]["id"]) if c else None

    def models(self, catalog_id: str, manufacturer: str) -> list[str]:
        return sorted({str(f["model"]) for f in self.families if f["catalog_id"] == catalog_id and f["manufacturer"] == manufacturer}, key=natural_key)

    def types(self, catalog_id: str, manufacturer: str, model: str) -> list[str]:
        return sorted({str(f["type"]) for f in self.families if f["catalog_id"] == catalog_id and f["manufacturer"] == manufacturer and f["model"] == model}, key=natural_key)

    def generations(self, catalog_id: str, manufacturer: str, model: str, type_name: str) -> list[str]:
        return sorted({str(f["generation"]) for f in self.families if f["catalog_id"] == catalog_id and f["manufacturer"] == manufacturer and f["model"] == model and f["type"] == type_name}, key=natural_key, reverse=True)

    def get_family(self, catalog_id: str, manufacturer: str, model: str, type_name: str, generation: str) -> dict[str, Any]:
        m = [f for f in self.families if f["catalog_id"] == catalog_id and f["manufacturer"] == manufacturer and f["model"] == model and f["type"] == type_name and f["generation"] == generation]
        if len(m) != 1:
            raise SelectionError("Vybranou produktovou řadu se nepodařilo jednoznačně nalézt.")
        return m[0]

    @staticmethod
    def _records(family: dict[str, Any], **filters: str) -> list[dict[str, Any]]:
        out = list(family.get("records", []))
        for key, val in filters.items():
            if val not in (None, ""):
                out = [r for r in out if str(r.get(key, "")) == str(val)]
        return out

    @staticmethod
    def _height_matches_range(row: dict[str, Any], height: Any) -> bool:
        h = str(height)
        if "height_mm" in row:
            return str(row.get("height_mm")) == h
        lo = str(row.get("height_min", "")); hi = str(row.get("height_max", lo))
        if h.isdigit() and lo.isdigit() and hi.isdigit():
            return int(lo) <= int(h) <= int(hi)
        return h == lo or h == hi

    @classmethod
    def moment_classes(cls, family: dict[str, Any]) -> list[str]:
        source = family.get("moment_rows", []) if family.get("backend") == "matrix" else family.get("records", [])
        return sorted({str(r["moment_class"]) for r in source}, key=natural_key)

    @classmethod
    def concrete_classes(cls, family: dict[str, Any], moment_class: str) -> list[str]:
        if family.get("backend") == "matrix":
            rows = [r for r in family.get("moment_rows", []) if str(r.get("moment_class")) == str(moment_class)]
            return sorted({str(r["concrete_min"]) for r in rows}, key=natural_key)
        return sorted({str(r["concrete_min"]) for r in cls._records(family, moment_class=moment_class)}, key=natural_key)

    @classmethod
    def shear_classes(cls, family: dict[str, Any], moment_class: str, concrete_min: str) -> list[str]:
        if family.get("backend") == "matrix":
            rows = [r for r in family.get("shear_rows", [])
                    if str(r.get("moment_class")) == str(moment_class) and str(r.get("concrete_min")) == str(concrete_min)]
            return sorted({str(r["shear_class"]) for r in rows}, key=natural_key)
        return sorted({str(r["shear_class"]) for r in cls._records(family, moment_class=moment_class, concrete_min=concrete_min)}, key=natural_key)

    @classmethod
    def covers(cls, family: dict[str, Any], moment_class: str, concrete_min: str, shear_class: str | None = None) -> list[str]:
        if family.get("backend") == "matrix":
            moment_rows = [r for r in family.get("moment_rows", [])
                           if str(r.get("moment_class")) == str(moment_class) and str(r.get("concrete_min")) == str(concrete_min)]
            covers = {str(r.get("cover")) for r in moment_rows}
            if shear_class is not None:
                shear_covers = {str(r.get("cover")) for r in family.get("shear_rows", [])
                                if str(r.get("moment_class")) == str(moment_class)
                                and str(r.get("concrete_min")) == str(concrete_min)
                                and str(r.get("shear_class")) == str(shear_class)}
                # CO shear rows use the same full cover label because they originate from source records.
                covers &= shear_covers
            return sorted(covers, key=natural_key)
        kw = {"moment_class": moment_class, "concrete_min": concrete_min}
        if shear_class is not None: kw["shear_class"] = shear_class
        return sorted({str(r["cover"]) for r in cls._records(family, **kw)}, key=natural_key)

    @classmethod
    def heights(cls, family: dict[str, Any], moment_class: str, concrete_min: str, cover: str, shear_class: str | None = None) -> list[str]:
        if family.get("backend") == "matrix":
            heights = {str(r.get("height_mm")) for r in family.get("moment_rows", [])
                       if str(r.get("moment_class")) == str(moment_class)
                       and str(r.get("concrete_min")) == str(concrete_min)
                       and str(r.get("cover")) == str(cover)}
            if shear_class is not None:
                shear_rows = [r for r in family.get("shear_rows", [])
                              if str(r.get("moment_class")) == str(moment_class)
                              and str(r.get("concrete_min")) == str(concrete_min)
                              and str(r.get("shear_class")) == str(shear_class)
                              and str(r.get("cover")) == str(cover)]
                heights = {h for h in heights if any(cls._height_matches_range(r, h) for r in shear_rows)}
            return sorted(heights, key=natural_key)
        kw = {"moment_class": moment_class, "concrete_min": concrete_min, "cover": cover}
        if shear_class is not None: kw["shear_class"] = shear_class
        return sorted({str(r["height_mm"]) for r in cls._records(family, **kw)}, key=natural_key)

    @staticmethod
    def _maxfrank_matrix_designation(family: dict[str, Any], moment_class: str, shear_class: str, concrete_min: str, cover: str, height_mm: str) -> tuple[str, list[str]]:
        typ = str(family.get("type", ""))
        product = str(moment_class)
        cover_code = str(cover).split(" ", 1)[0]
        variant = ""
        # CO already carries -CO-L/-CO-R in the product selector; ± product names in source do not need a suffix.
        if "-CO-" not in product and not typ.endswith("±"):
            alpha = re.match(r"^[A-Z]+", product)
            base = alpha.group(0) if alpha else str(family.get("model", ""))
            if typ.startswith(base + "-"):
                variant = typ[len(base):]  # includes leading hyphen
        source = f"{product}{variant}-{shear_class}-{cover_code}-h{height_mm}"
        full = f"Egcobox® {source} [{concrete_min}]"
        aliases = [source, f"MAX FRANK {source}", f"Egcobox {source}"]
        return full, aliases

    def query(self, *, catalog_id: str, manufacturer: str, model: str, type_name: str, generation: str,
              moment_class: str, concrete_min: str, shear_class: str, cover: str, height_mm: Any) -> QueryResult:
        fam = self.get_family(catalog_id, manufacturer, model, type_name, generation)
        if fam.get("backend") == "matrix":
            h = str(height_mm)
            mm = [r for r in fam.get("moment_rows", [])
                  if str(r.get("moment_class")) == str(moment_class)
                  and str(r.get("concrete_min")) == str(concrete_min)
                  and str(r.get("cover")) == str(cover)
                  and str(r.get("height_mm")) == h]
            ss = [r for r in fam.get("shear_rows", [])
                  if str(r.get("moment_class")) == str(moment_class)
                  and str(r.get("shear_class")) == str(shear_class)
                  and str(r.get("concrete_min")) == str(concrete_min)
                  and str(r.get("cover")) == str(cover)
                  and self._height_matches_range(r, h)]
            if len(mm) != 1 or len(ss) != 1:
                raise SelectionError("Pro zvolenou kombinaci nebyl nalezen jednoznačný katalogový záznam.")
            designation, aliases = self._maxfrank_matrix_designation(fam, str(moment_class), str(shear_class), str(concrete_min), str(cover), h)
            pages = sorted({int(p) for row in (mm[0], ss[0]) for p in (row.get("source_pages") or fam.get("source_pages") or [])})
            notes = list(mm[0].get("notes") or []) + [n for n in (ss[0].get("notes") or []) if n not in (mm[0].get("notes") or [])]
            rec = {
                "moment_class": str(moment_class), "shear_class": str(shear_class), "concrete_min": str(concrete_min),
                "cover": str(cover), "height_mm": h, "designation": designation, "aliases": aliases,
                "results": list(mm[0].get("results", [])) + list(ss[0].get("results", [])),
                "source_pages": pages,
                "insulation_thickness_mm": mm[0].get("insulation_thickness_mm", fam.get("insulation_thickness_mm")),
                "compression_transfer": mm[0].get("compression_transfer") or ss[0].get("compression_transfer") or fam.get("compression_transfer"),
            }
            if notes: rec["notes"] = notes
            return QueryResult(self.catalogs[catalog_id], fam, rec)
        matches = self._records(fam, moment_class=str(moment_class), concrete_min=str(concrete_min), shear_class=str(shear_class), cover=str(cover), height_mm=str(height_mm))
        if len(matches) != 1:
            raise SelectionError("Pro zvolenou kombinaci nebyl nalezen jednoznačný katalogový záznam.")
        return QueryResult(self.catalogs[catalog_id], fam, matches[0])

    def result_for_record(self, family: dict[str, Any], record: dict[str, Any]) -> QueryResult:
        return QueryResult(self.catalogs[str(family["catalog_id"])], family, record)

    @staticmethod
    def _suggestion_tokens(text: str) -> list[str]:
        n = _normalise(text)
        # Slova, která nenesou pro vyhledání konkrétního typu téměř žádnou informaci.
        n = re.sub(r"\b(TYP|TYPE|ISOKORB|ISOPRO|PRVEK|ELEMENT)\b", " ", n)
        tokens = re.findall(r"[A-Z]+\d+[A-Z]*|\d+\.\d+|\d+|[A-Z]{1,12}", n)
        # Běžný neúplný zápis bývá rozdělen mezerou (např. ``VM 130`` nebo ``AIPQ 60``).
        # Přidáme proto i složený token, aniž bychom původní tokeny zahodili.
        combined = [a + b for a, b in re.findall(r"\b([A-Z]{1,12})\s+(\d{2,4})\b", n)]
        return [t for t in tokens + combined if t]

    @staticmethod
    def _suggestion_compact(text: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", _normalise(text))

    def _build_suggestion_index(self) -> None:
        self._suggestion_entries.clear()
        self._suggestion_token_index = defaultdict(set)
        self._suggestion_vocabulary = set()
        for fam in self.families:
            for record in fam.get("records", []):
                designation = str(record.get("designation") or "")
                aliases = [str(a) for a in (record.get("aliases") or []) if a]
                searchable = " ".join([
                    designation,
                    *aliases,
                    str(fam.get("manufacturer", "")), str(fam.get("model", "")), str(fam.get("type", "")),
                    str(fam.get("generation", "")), str(record.get("moment_class", "")),
                    str(record.get("shear_class", "")), str(record.get("concrete_min", "")),
                    str(record.get("cover", "")), str(record.get("height_mm", "")),
                    str(record.get("insulation_thickness_mm", fam.get("insulation_thickness_mm", ""))),
                    str(record.get("compression_transfer", fam.get("compression_transfer", ""))),
                ])
                tokens = set(self._suggestion_tokens(searchable))
                # Přidáme i kompaktní značky: A-IPQ -> AIPQ, KL-U -> KLU, H 220 -> H220.
                for value in (fam.get("type"), record.get("moment_class"), record.get("shear_class"), record.get("cover")):
                    if value not in (None, "", "—"):
                        compact_value = self._suggestion_compact(str(value))
                        if compact_value:
                            tokens.add(compact_value)
                h = str(record.get("height_mm", ""))
                if h.isdigit():
                    tokens.add("H" + h)
                idx = len(self._suggestion_entries)
                self._suggestion_entries.append({
                    "family": fam,
                    "record": record,
                    "designation": designation,
                    "compact": self._suggestion_compact(searchable),
                    "tokens": tokens,
                })
                for token in tokens:
                    self._suggestion_token_index[token].add(idx)
                    self._suggestion_vocabulary.add(token)

    def _explicit_selector_constraints(self, text: str) -> dict[str, set[str]]:
        """Catalog-driven selectors that are explicitly present in the typed designation."""
        n = _normalise(text)
        q_tokens = set(self._suggestion_tokens(text))
        constraints: dict[str, set[str]] = {}

        def find_values(values: Iterable[Any]) -> set[str]:
            ranked: list[tuple[int, int, str]] = []
            for raw in values:
                value = str(raw or "").strip()
                if not value or value == "—":
                    continue
                nv = _normalise(value)
                compact = self._suggestion_compact(value)
                score = 0
                if nv and re.search(rf"(?<![A-Z0-9]){re.escape(nv)}(?![A-Z0-9])", n):
                    score = 3
                elif compact and compact in q_tokens:
                    score = 2
                if score:
                    ranked.append((score, len(nv), value))
            if not ranked:
                return set()
            best_score = max(x[0] for x in ranked)
            best_len = max(x[1] for x in ranked if x[0] == best_score)
            return {value for score, length, value in ranked if score == best_score and length == best_len}

        non_matrix = [f for f in self.families if f.get("backend") != "matrix"]
        for key in ("manufacturer", "model", "type", "generation"):
            found = find_values(f.get(key) for f in non_matrix)
            if found:
                constraints[key] = found

        records = [r for f in non_matrix for r in f.get("records", [])]
        for key in ("moment_class", "shear_class", "cover"):
            found = find_values(r.get(key) for r in records)
            if found:
                constraints[key] = found

        concrete_match = re.search(r"C\s*(\d{2})\s*/\s*(\d{2})", n)
        if concrete_match:
            constraints["concrete_min"] = {f"C{concrete_match.group(1)}/{concrete_match.group(2)}"}

        height_match = re.search(r"\bH\s*(\d{3,4})\b", n)
        if height_match:
            constraints["height_mm"] = {height_match.group(1)}

        insulation_match = re.search(r"\b(80|120)\s*MM\b", n)
        if insulation_match:
            constraints["insulation_thickness_mm"] = {insulation_match.group(1)}

        return constraints

    def _structured_record_suggestions(self, text: str, preferred_catalog_id: str | None,
                                       preferred_concrete: str | None, limit: int) -> list[DesignationSuggestion]:
        """Vary only selectors that are not explicitly present in a recognizable partial designation."""
        constraints = self._explicit_selector_constraints(text)
        technical = {"model", "type", "moment_class", "shear_class", "cover", "height_mm", "generation"}
        if not constraints.get("moment_class") or len(technical.intersection(constraints)) < 2:
            return []

        families = [f for f in self.families if f.get("backend") != "matrix"]
        for key in ("manufacturer", "model", "type", "generation"):
            allowed = constraints.get(key)
            if allowed:
                families = [f for f in families if str(f.get(key, "")) in allowed]

        if preferred_catalog_id:
            preferred = [f for f in families if str(f.get("catalog_id")) == str(preferred_catalog_id)]
            if preferred:
                families = preferred

        matches: list[DesignationSuggestion] = []
        for family in families:
            for record in family.get("records", []):
                if preferred_concrete and str(record.get("concrete_min", "")) != str(preferred_concrete):
                    continue
                ok = True
                for key in ("moment_class", "shear_class", "concrete_min", "cover", "height_mm"):
                    allowed = constraints.get(key)
                    if allowed and str(record.get(key, "")) not in allowed:
                        ok = False
                        break
                if not ok:
                    continue
                insulation = constraints.get("insulation_thickness_mm")
                if insulation:
                    actual = record.get("insulation_thickness_mm", family.get("insulation_thickness_mm"))
                    if str(actual) not in insulation:
                        continue
                matches.append(DesignationSuggestion(self.result_for_record(family, record), 350.0 + 15.0 * len(constraints)))

        best: dict[str, DesignationSuggestion] = {}
        for item in matches:
            key = _normalise(item.designation)
            if key not in best or item.score > best[key].score:
                best[key] = item
        return sorted(best.values(), key=lambda x: natural_key(x.designation))[:limit]

    def _matrix_suggestions(self, text: str, preferred_catalog_id: str | None, limit: int, preferred_concrete: str | None = None) -> list[DesignationSuggestion]:
        raw = str(text or "").strip(); n = _normalise(raw); compact = self._suggestion_compact(raw)
        q_tokens = set(self._suggestion_tokens(raw))
        out: list[DesignationSuggestion] = []
        if "SCHOCK" in n or "ISOPRO" in n:
            return []
        matrix_trigger = (
            "MAXFRANK" in compact or "EGCOBOX" in compact or
            bool(re.search(r"\b(?:MM|MXL)\s*\d", n)) or
            any(token in q_tokens for token in {"MM", "MXL", "HVS", "WOS", "BH", "WU", "BHS", "WUS"})
        )
        if not matrix_trigger:
            return []
        # Optional explicit selectors from the typed text.
        cover_match = re.search(r"\bC(30|35|50)\b", n)
        wanted_cover = f"C{cover_match.group(1)}" if cover_match else None
        concrete_match = re.search(r"C\s*(20|25)\s*/\s*(25|30)", n)
        wanted_concrete = f"C{concrete_match.group(1)}/{concrete_match.group(2)}" if concrete_match else None
        if preferred_concrete:
            preferred_concrete = str(preferred_concrete)
            if wanted_concrete and wanted_concrete != preferred_concrete:
                return []
            wanted_concrete = preferred_concrete
        height_match = re.search(r"\bH\s*(\d{3,4})\b", n)
        if not height_match:
            nums = [x for x in re.findall(r"\b(\d{3,4})\b", n) if int(x) >= 100]
            wanted_height = nums[-1] if nums else None
        else:
            wanted_height = height_match.group(1)

        matrix_families = [f for f in self.families if f.get("backend") == "matrix"]

        def explicit_matrix_values(values: Iterable[Any]) -> set[str]:
            ranked: list[tuple[int, int, str]] = []
            for raw_value in values:
                value = str(raw_value or "").strip()
                if not value or value == "—":
                    continue
                nv = _normalise(value)
                cv = self._suggestion_compact(value)
                score = 0
                if nv and re.search(rf"(?<![A-Z0-9]){re.escape(nv)}(?![A-Z0-9])", n):
                    score = 3
                elif cv and cv in q_tokens:
                    score = 2
                if score:
                    ranked.append((score, len(nv), value))
            if not ranked:
                return set()
            best_score = max(item[0] for item in ranked)
            best_len = max(item[1] for item in ranked if item[0] == best_score)
            return {value for score, length, value in ranked if score == best_score and length == best_len}

        explicit_products = explicit_matrix_values(
            product for matrix_family in matrix_families for product in self.moment_classes(matrix_family)
        )
        explicit_shears = explicit_matrix_values(
            row.get("shear_class") for matrix_family in matrix_families for row in matrix_family.get("shear_rows", [])
        )
        explicit_types = explicit_matrix_values(matrix_family.get("type") for matrix_family in matrix_families)
        explicit_models = explicit_matrix_values(matrix_family.get("model") for matrix_family in matrix_families)

        family_rank: list[tuple[float, dict[str, Any]]] = []
        for fam in matrix_families:
            if explicit_types and str(fam.get("type", "")) not in explicit_types:
                continue
            if explicit_models and str(fam.get("model", "")) not in explicit_models:
                continue
            if preferred_catalog_id and str(fam.get("catalog_id")) != str(preferred_catalog_id):
                preferred_factor = 0.93
            else: preferred_factor = 1.0
            ftext = f"{fam.get('manufacturer','')} {fam.get('model','')} {fam.get('type','')}"
            fcompact = self._suggestion_compact(ftext)
            typcompact = self._suggestion_compact(str(fam.get('type','')))
            score = 10.0
            if typcompact and typcompact in compact: score += 55
            elif self._suggestion_compact(str(fam.get('model',''))) in compact: score += 32
            else:
                # A short fuzzy comparison keeps common misspellings usable without indexing tens of thousands of combinations.
                ratio = SequenceMatcher(None, compact[:max(4,len(typcompact))], typcompact).ratio() if compact else 0
                score += 25*ratio
            if "MAXFRANK" in compact or "EGCOBOX" in compact or "EGCOBOX" in compact: score += 8
            family_rank.append((score*preferred_factor, fam))
        family_rank.sort(key=lambda x: -x[0])

        for fscore, fam in family_rank[:8]:
            products = self.moment_classes(fam)
            if explicit_products:
                products = [p for p in products if str(p) in explicit_products]
            if not products: continue
            product_rank=[]
            for product in products:
                pc=self._suggestion_compact(product)
                if pc in compact: ps=100.0
                elif any(pc == t for t in q_tokens): ps=95.0
                else:
                    token_ratios=[SequenceMatcher(None, t, pc).ratio() for t in q_tokens if len(t)>=2]
                    ps=(max(token_ratios) if token_ratios else 0.0)*70.0
                product_rank.append((ps,product))
            product_rank.sort(key=lambda x:(-x[0],natural_key(x[1])))
            if explicit_products:
                chosen_products = products
            else:
                chosen_products=[p for ps,p in product_rank if ps>=48][:4]
                if not chosen_products:
                    # For broad family query show a few representative product levels rather than every height.
                    chosen_products=products[:3]
            for product in chosen_products:
                concretes=self.concrete_classes(fam, product)
                if wanted_concrete:
                    concretes=[c for c in concretes if c==wanted_concrete]
                else:
                    concretes=sorted(concretes,key=lambda c:(0 if preferred_concrete and c==preferred_concrete else 1, 0 if c=="C25/30" else 1, natural_key(c)))[:2]
                for concrete in concretes:
                    shears=self.shear_classes(fam, product, concrete)
                    if explicit_shears:
                        matched_s = [sc for sc in shears if str(sc) in explicit_shears]
                        if not matched_s:
                            continue
                        use_s = matched_s[:3]
                    else:
                        # Broad/incomplete shear text keeps the existing tolerant behaviour.
                        matched_s=[sc for sc in shears if self._suggestion_compact(sc) in q_tokens or self._suggestion_compact(sc) in compact]
                        use_s=matched_s[:3] if matched_s else shears[:3]
                    for sc in use_s:
                        covers=self.covers(fam, product, concrete, sc)
                        if wanted_cover:
                            covers=[c for c in covers if str(c).startswith(wanted_cover)]
                        else: covers=covers[:2]
                        for cover in covers:
                            heights=self.heights(fam, product, concrete, cover, sc)
                            if wanted_height:
                                heights=[h for h in heights if h==wanted_height]
                            else:
                                # use the lowest and one central option; enough to guide completion without flooding the popup
                                if len(heights)>1: heights=[heights[0], heights[len(heights)//2]]
                                else: heights=heights[:1]
                            for h in heights:
                                try: result=self.query(catalog_id=str(fam['catalog_id']),manufacturer=str(fam['manufacturer']),model=str(fam['model']),type_name=str(fam['type']),generation=str(fam['generation']),moment_class=product,concrete_min=concrete,shear_class=sc,cover=cover,height_mm=h)
                                except SelectionError: continue
                                score=fscore + next((ps for ps,p in product_rank if p==product),0)
                                if wanted_height: score+=35
                                if wanted_cover: score+=15
                                if matched_s: score+=20
                                out.append(DesignationSuggestion(result,score,tuple(sorted(q_tokens,key=natural_key))))
                                if len(out)>=limit*4: break
                            if len(out)>=limit*4: break
                        if len(out)>=limit*4: break
                    if len(out)>=limit*4: break
                if len(out)>=limit*4: break
            if len(out)>=limit*4: break
        # Exact duplicate designations can occur only in pathological source overlap; dedupe and keep highest score.
        best={}
        for item in out:
            key=_normalise(item.designation)
            if key not in best or item.score>best[key].score: best[key]=item
        return sorted(best.values(), key=lambda x:(-x.score,natural_key(x.designation)))[:limit]

    def suggest_designations(self, text: str, preferred_catalog_id: str | None = None,
                             preferred_concrete: str | None = None, limit: int = 12) -> list[DesignationSuggestion]:
        """Vrátí nejlepší doplnění i pro neúplný nebo lehce chybně napsaný název.

        Vyhledávání je záměrně tolerantní k mezerám, pomlčkám, diakritice výrobce,
        vynechanému slovu ``typ`` i drobným překlepům. Výsledek se nikdy sám
        nepovažuje za statický návrh – uživatel si konkrétní katalogový záznam zvolí.
        """
        raw = str(text or "").strip()
        if not raw or len(self._suggestion_compact(raw)) < 2:
            return []

        constraints = self._explicit_selector_constraints(raw)
        if preferred_concrete and constraints.get("concrete_min") and str(preferred_concrete) not in constraints["concrete_min"]:
            return []

        # Exact designation or alias: do not clutter the popup with merely similar products.
        exact_pairs = list(self._designation_index.get(_normalise(raw), []))
        if preferred_catalog_id:
            preferred_pairs = [x for x in exact_pairs if str(x[0].get("catalog_id")) == str(preferred_catalog_id)]
            if preferred_pairs:
                exact_pairs = preferred_pairs
        if preferred_concrete:
            exact_pairs = [x for x in exact_pairs if str(x[1].get("concrete_min", "")) == str(preferred_concrete)]
        if exact_pairs:
            exact_out: list[DesignationSuggestion] = []
            seen_exact: set[str] = set()
            for family, record in exact_pairs:
                item = DesignationSuggestion(self.result_for_record(family, record), 1000.0)
                key = _normalise(item.designation)
                if key not in seen_exact:
                    seen_exact.add(key)
                    exact_out.append(item)
            if exact_out:
                return exact_out[:limit]

        # Recognizable standard partial designation: vary only selectors the user did NOT specify.
        structured = self._structured_record_suggestions(raw, preferred_catalog_id, preferred_concrete, limit)
        if structured:
            return structured[:limit]

        # Recognizable matrix designation: stay inside the matrix family instead of mixing fuzzy standard products.
        matrix_specific = self._matrix_suggestions(raw, preferred_catalog_id, limit, preferred_concrete=preferred_concrete)
        if matrix_specific:
            return matrix_specific[:limit]

        q_tokens = self._suggestion_tokens(raw)
        q_compact = self._suggestion_compact(raw)
        # Stop-slova po odstranění mohou zanechat prázdný dotaz.
        if not q_tokens and not q_compact:
            return []

        # Pro každý token najdeme přesné, prefixové a teprve poté fuzzy ekvivalenty
        # ve slovníku. Fuzzy porovnání tedy neběží proti všem 14k+ záznamům.
        token_matches: list[list[tuple[str, float]]] = []
        vocab = self._suggestion_vocabulary
        for qt in q_tokens:
            matches: list[tuple[str, float]] = []
            if qt in vocab:
                matches.append((qt, 1.0))
            if len(qt) >= 2:
                # Prefix je vhodný pro rozepsané označení, např. "K"/"KL" nebo "AIP".
                prefix = [(v, 0.88) for v in vocab if v != qt and (v.startswith(qt) or (len(v) >= 3 and qt.startswith(v)))]
                prefix.sort(key=lambda x: (abs(len(x[0]) - len(qt)), natural_key(x[0])))
                matches.extend(prefix[:18])
            if len(qt) >= 3 and not any(w >= 0.99 for _v, w in matches):
                fuzzy: list[tuple[str, float]] = []
                for v in vocab:
                    if abs(len(v) - len(qt)) > max(3, len(qt) // 2):
                        continue
                    ratio = SequenceMatcher(None, qt, v).ratio()
                    if ratio >= 0.72:
                        fuzzy.append((v, 0.62 + 0.28 * ratio))
                fuzzy.sort(key=lambda x: (-x[1], abs(len(x[0]) - len(qt)), natural_key(x[0])))
                matches.extend(fuzzy[:12])
            # Deduplikace tokenu s ponecháním nejlepší váhy.
            best: dict[str, float] = {}
            for v, w in matches:
                best[v] = max(w, best.get(v, 0.0))
            token_matches.append(sorted(best.items(), key=lambda x: -x[1]))

        scores: Counter[int] = Counter()
        matched_count: Counter[int] = Counter()
        matched_tokens: dict[int, set[str]] = defaultdict(set)
        for qt, matches in zip(q_tokens, token_matches):
            seen_for_query: set[int] = set()
            for candidate_token, weight in matches:
                for idx in self._suggestion_token_index.get(candidate_token, ()):
                    scores[idx] += weight
                    matched_tokens[idx].add(qt)
                    seen_for_query.add(idx)
            for idx in seen_for_query:
                matched_count[idx] += 1

        # Dotazy bez použitelných tokenů (např. kompaktní AIPQ60) dostanou kandidáty
        # přes kompaktní řetězec; současně je to bonus pro běžné zápisy bez pomlček.
        compact_hits: set[int] = set()
        if len(q_compact) >= 3 and not scores:
            for idx, entry in enumerate(self._suggestion_entries):
                c = entry["compact"]
                if q_compact in c:
                    compact_hits.add(idx)
                    scores[idx] += 0.8

        if not scores:
            # Poslední záchrana pro velmi zkomolený krátký text: fuzzy podobnost
            # proti kompaktnímu typu/označení, ale jen nad produktovými rodinami.
            family_scores: list[tuple[float, dict[str, Any]]] = []
            seen_fam: set[int] = set()
            for entry in self._suggestion_entries:
                fam = entry["family"]
                if id(fam) in seen_fam:
                    continue
                seen_fam.add(id(fam))
                family_text = self._suggestion_compact(
                    f"{fam.get('manufacturer','')} {fam.get('model','')} {fam.get('type','')} {fam.get('generation','')}"
                )
                ratio = SequenceMatcher(None, q_compact, family_text).ratio()
                family_scores.append((ratio, fam))
            family_scores.sort(key=lambda x: -x[0])
            good_families = {id(f) for ratio, f in family_scores[:5] if ratio >= 0.35}
            for idx, entry in enumerate(self._suggestion_entries):
                if id(entry["family"]) in good_families:
                    scores[idx] = 0.25

        q_count = max(1, len(q_tokens))
        ranked: list[tuple[float, int]] = []
        for idx, base in scores.items():
            entry = self._suggestion_entries[idx]
            fam = entry["family"]
            if preferred_concrete and str(entry.get("record", {}).get("concrete_min", "")) != str(preferred_concrete):
                continue
            if preferred_catalog_id and str(fam.get("catalog_id")) != str(preferred_catalog_id):
                catalog_factor = 0.90
            else:
                catalog_factor = 1.0
            coverage = matched_count[idx] / q_count if q_tokens else 0.0
            # Kandidáti, kteří ignorují většinu zadaných tokenů, mají výraznou penalizaci.
            if len(q_tokens) >= 3 and coverage < 0.5 and idx not in compact_hits:
                continue
            score = (base / q_count) * 70.0 + coverage * 25.0
            if idx in compact_hits:
                score += 8.0
            # Mírná preference aktuálního katalogu a kratšího doplnění při shodném skóre.
            if preferred_concrete:
                record_concrete = str(entry.get("record", {}).get("concrete_min", ""))
                score += 12.0 if record_concrete == str(preferred_concrete) else -3.0
            score *= catalog_factor
            ranked.append((score, idx))
        ranked.sort(key=lambda x: (-x[0], natural_key(self._suggestion_entries[x[1]]["designation"])))

        # Nejprve nabídneme různorodé varianty (jiná rodina/třída/krytí), aby široký
        # dotaz neskončil dvanácti výškami téhož prvku. Poté doplníme zbytek pořadí.
        selected: list[int] = []
        used_groups: set[tuple[str, ...]] = set()
        for _score, idx in ranked:
            e = self._suggestion_entries[idx]; f = e["family"]; r = e["record"]
            group = (str(f.get("catalog_id")), str(f.get("model")), str(f.get("type")),
                     str(r.get("moment_class")), str(r.get("shear_class")), str(r.get("cover")))
            if group in used_groups:
                continue
            used_groups.add(group); selected.append(idx)
            if len(selected) >= limit:
                break
        if len(selected) < limit:
            for _score, idx in ranked:
                if idx not in selected:
                    selected.append(idx)
                    if len(selected) >= limit:
                        break
        score_map = {idx: score for score, idx in ranked}
        out: list[DesignationSuggestion] = []
        for idx in selected:
            e = self._suggestion_entries[idx]
            out.append(DesignationSuggestion(
                self.result_for_record(e["family"], e["record"]),
                score_map.get(idx, 0.0),
                tuple(sorted(matched_tokens.get(idx, set()), key=natural_key)),
            ))
        matrix = self._matrix_suggestions(raw, preferred_catalog_id, limit, preferred_concrete=preferred_concrete)
        combined = out + matrix
        best: dict[str, DesignationSuggestion] = {}
        for item in combined:
            key = _normalise(item.designation)
            if key not in best or item.score > best[key].score:
                best[key] = item
        return sorted(best.values(), key=lambda x: (-x.score, natural_key(x.designation)))[:limit]

    def suggestion_hint(self, text: str, preferred_catalog_id: str | None = None, preferred_concrete: str | None = None, limit: int = 4) -> str:
        suggestions = self.suggest_designations(text, preferred_catalog_id=preferred_catalog_id, preferred_concrete=preferred_concrete, limit=limit)
        if not suggestions:
            return ""
        return "\nNejbližší možnosti:\n" + "\n".join(f"• {s.designation}" for s in suggestions)

    def parse_designation(self, text: str) -> dict[str, Any]:
        """Lehký parser pro starší běžné zápisy. Přesné nové označení řeší index v resolve_designation."""
        n = _normalise(text)
        d: dict[str, Any] = {}
        if "ISOPRO" in n:
            d["manufacturer"] = "ISOPRO"; d["model"] = "ISOPRO 80"; d["generation"] = "—"
            m = re.search(r"A-IPT\s*(120|150|160)\b", n)
            if m: d["type"]="A-IPT"; d["moment_class"]=m.group(1)
            else:
                m = re.search(r"A-IP\s*(10|15|20|30|40|50|60|70|75|80|85|90|100)\b", n)
                if m: d["type"]="A-IP"; d["moment_class"]=m.group(1)
            q = re.search(r"\b(STANDARD|Q(?:8|10|12|14)(?:X)?)\b", n)
            if q: d["shear_class"] = "Standard" if q.group(1)=="STANDARD" else q.group(1)
            cv = re.search(r"\bCV(30|35|50)\b", n)
            if cv: d["cover"]="cv"+cv.group(1)
            h = re.search(r"\bH\s*(\d{3})\b", n)
            if h: d["height_mm"]=h.group(1)
        else:
            if "SCHOCK" in n: d["manufacturer"]="Schöck"
            if re.search(r"\bXT\b",n): d["model"]="XT"
            elif re.search(r"\bT\b",n): d["model"]="T"
            if re.search(r"\bKL\b",n): d["type"]="KL"
            m=re.search(r"\bM(\d+)\b",n)
            if m: d["moment_class"]="M"+str(int(m.group(1)))
            v=re.search(r"\b(VV?\d+)\b",n)
            if v: d["shear_class"]=v.group(1)
            cv=re.search(r"\bCV(\d+)\b",n)
            if cv: d["cover"]="CV"+str(int(cv.group(1)))
            h=re.search(r"\bH\s*(\d{3})\b",n)
            if h: d["height_mm"]=h.group(1)
            g=re.search(r"(?:-|\s)(\d+\.\d+)\s*$",n)
            if g: d["generation"]=g.group(1)
        c=re.search(r"C\s*(\d{2})\s*/\s*(\d{2})", n)
        if c: d["concrete_min"]=f"C{c.group(1)}/{c.group(2)}"
        return d

    def resolve_designation(self, text: str, preferred_catalog_id: str | None = None, preferred_concrete: str | None = None) -> QueryResult:
        key = _normalise(text)
        exact = list(self._designation_index.get(key, []))
        if preferred_catalog_id:
            exact_pref=[x for x in exact if str(x[0]["catalog_id"])==str(preferred_catalog_id)]
            if exact_pref: exact=exact_pref
        if preferred_concrete:
            concrete_pref=[x for x in exact if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]
            if exact and not concrete_pref:
                found = sorted({str(x[1].get("concrete_min", "")) for x in exact if x[1].get("concrete_min")})
                raise SelectionError(f"Označení je v databázi pro beton {', '.join(found) or 'jiné třídy'}, ale projekt je nastaven na {preferred_concrete}.")
            exact=concrete_pref
        if len(exact)==1:
            return self.result_for_record(*exact[0])
        if len(exact)>1:
            raise SelectionError("Označení odpovídá více katalogovým záznamům. Upřesněte vydání nebo variantu." + self.suggestion_hint(text, preferred_catalog_id, preferred_concrete))

        for suggestion in self._matrix_suggestions(text, preferred_catalog_id, 20, preferred_concrete=preferred_concrete):
            if _normalise(suggestion.designation) == key or any(_normalise(a) == key for a in (suggestion.result.record.get("aliases") or [])):
                return suggestion.result

        # Accept an exact designation embedded in a longer clipboard line.
        embedded=[]
        for des, pairs in self._designation_index.items():
            if des and des in key:
                embedded.extend(pairs)
        if preferred_catalog_id:
            p=[x for x in embedded if str(x[0]["catalog_id"])==str(preferred_catalog_id)]
            if p: embedded=p
        if preferred_concrete:
            embedded=[x for x in embedded if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]
        unique={(id(f), id(r)):(f,r) for f,r in embedded}
        if len(unique)==1:
            f,r=next(iter(unique.values())); return self.result_for_record(f,r)

        parsed=self.parse_designation(text)
        if preferred_concrete and parsed.get("concrete_min") and str(parsed.get("concrete_min")) != str(preferred_concrete):
            raise SelectionError(f"V označení je beton {parsed.get('concrete_min')}, ale projekt je nastaven na {preferred_concrete}.")
        if parsed.get("type") and parsed.get("moment_class"):
            manufacturer=parsed.get("manufacturer") or ("Schöck" if parsed.get("model") in {"T","XT"} else None)
            candidates=[f for f in self.families if (not manufacturer or f["manufacturer"]==manufacturer)
                        and (not parsed.get("model") or f["model"]==parsed["model"])
                        and f["type"]==parsed["type"]
                        and (not parsed.get("generation") or f["generation"]==parsed["generation"])]
            if preferred_catalog_id:
                pref=[f for f in candidates if str(f["catalog_id"])==str(preferred_catalog_id)]
                if pref: candidates=pref
            recs=[]
            for f in candidates:
                for r in f.get("records",[]):
                    ok=True
                    for k in ("moment_class","shear_class","concrete_min","cover","height_mm"):
                        if parsed.get(k) not in (None,"") and str(r.get(k))!=str(parsed[k]): ok=False; break
                    if ok: recs.append((f,r))
            if preferred_concrete:
                recs=[x for x in recs if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]
            if len(recs)==1: return self.result_for_record(*recs[0])
            if len(recs)>1:
                raise SelectionError("Označení je nejednoznačné. Doplňte chybějící třídu, krytí/variantu nebo rozměr." + self.suggestion_hint(text, preferred_catalog_id, preferred_concrete))
        raise SelectionError("Označení se nepodařilo jednoznačně přiřadit. Vyberte některou z nabízených možností nebo použijte detailní výběr." + self.suggestion_hint(text, preferred_catalog_id, preferred_concrete))

    def validation_report(self) -> tuple[list[str], list[str], dict[str, int]]:
        errors=list(self.load_errors); warnings=[]; family_keys=set(); record_count=0; moment_count=0; shear_count=0; other_count=0
        for fam in self.families:
            fk=(fam["catalog_id"],fam["manufacturer"],fam["model"],fam["type"],fam["generation"])
            if fk in family_keys: errors.append(f"Duplicitní produktová řada: {fk}")
            family_keys.add(fk)
            if fam.get("backend") == "matrix":
                mseen=set(); sseen=set()
                sgroups=defaultdict(list)
                for r in fam.get("shear_rows",[]):
                    rk=(r.get("moment_class"),r.get("shear_class"),r.get("concrete_min"),r.get("cover"),str(r.get("height_min")),str(r.get("height_max")))
                    if rk in sseen: errors.append(f"Duplicitní maticový smyk: {fk} {rk}")
                    sseen.add(rk)
                    if not r.get("results"): warnings.append(f"Maticový smyk bez výsledku: {fk} {rk}")
                    sgroups[(str(r.get('moment_class')),str(r.get('concrete_min')),str(r.get('cover')))].append(r)
                for r in fam.get("moment_rows",[]):
                    rk=(r.get("moment_class"),r.get("concrete_min"),r.get("cover"),str(r.get("height_mm")))
                    if rk in mseen: errors.append(f"Duplicitní maticový moment: {fk} {rk}")
                    mseen.add(rk)
                    candidates=sgroups.get((str(r.get('moment_class')),str(r.get('concrete_min')),str(r.get('cover'))),[])
                    matches=[sr for sr in candidates if self._height_matches_range(sr,r.get('height_mm'))]
                    record_count += len(matches)
                    for _sr in matches:
                        moment_count += sum(1 for v in r.get('results',[]) if str(v.get('kind'))=='moment')
                        shear_count += sum(1 for v in _sr.get('results',[]) if str(v.get('kind'))=='shear')
                        other_count += sum(1 for v in r.get('results',[]) + _sr.get('results',[]) if str(v.get('kind')) not in {'moment','shear'})
                continue
            seen=set()
            for r in fam.get("records",[]):
                record_count+=1
                rk=(r.get("moment_class"),r.get("shear_class"),r.get("concrete_min"),r.get("cover"),str(r.get("height_mm")))
                if rk in seen: errors.append(f"Duplicitní kombinace: {fk} {rk}")
                seen.add(rk)
                if not r.get("results"): warnings.append(f"Záznam bez statické hodnoty: {fk} {rk}")
                for v in r.get("results",[]):
                    kind=str(v.get("kind","other"))
                    if kind=="moment": moment_count+=1
                    elif kind=="shear": shear_count+=1
                    else: other_count+=1
                    if not any(k in v for k in ("value","positive","negative","text")):
                        errors.append(f"Výsledek bez hodnoty: {fk} {rk} {v.get('key')}")
        stats={"catalogs":len(self.catalogs),"families":len(self.families),"records":record_count,
               "moment_records":moment_count,"shear_records":shear_count,"other_records":other_count}
        return errors,warnings,stats

    @staticmethod
    def catalog_date(catalog: dict[str, Any]) -> date | None:
        raw=catalog.get("publication_date")
        if not raw: return None
        try: return datetime.strptime(str(raw),"%Y-%m-%d").date()
        except ValueError: return None
