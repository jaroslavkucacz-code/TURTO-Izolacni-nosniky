from __future__ import annotations

"""TURTO 2.2.43 – exact Schöck Isokorb XT designation normalization for bulk analysis."""

from dataclasses import dataclass
import re
from typing import Mapping

_DASH_TRANSLATION = str.maketrans({
    "\u2212": "-",  # minus
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
})

_PREFIX_RE = re.compile(
    r"""^\s*
        (?:
            (?:SCH[ÖO]CK\s+)?ISOKORB(?:\s*[®R])?\s+
        )?
        XT\s+TYP(?:E)?
        \s*(?::|=)?\s*
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "QP-Z",
        re.compile(
            r"^QP-Z-(?P<shear>V\d+)-REI(?P<fire>\d+)-H(?P<height>\d+)-L(?P<length>\d+)-(?P<generation>\d+(?:[.,]\d+)?)$",
            re.IGNORECASE,
        ),
    ),
    (
        "KL",
        re.compile(
            r"^KL-M(?P<moment>\d+)-(?P<shear>V{1,2}\d+)-REI(?P<fire>\d+)-CV(?P<cover>\d+)-H(?P<height>\d+)-(?P<generation>\d+(?:[.,]\d+)?)$",
            re.IGNORECASE,
        ),
    ),
    (
        "QL",
        re.compile(
            r"^QL-(?P<shear>V{1,2}\d+)-REI(?P<fire>\d+)-H(?P<height>\d+)-(?P<generation>\d+(?:[.,]\d+)?)$",
            re.IGNORECASE,
        ),
    ),
    (
        "QP",
        re.compile(
            r"^QP-(?P<shear>V\d+)-REI(?P<fire>\d+)-H(?P<height>\d+)-L(?P<length>\d+)-(?P<generation>\d+(?:[.,]\d+)?)$",
            re.IGNORECASE,
        ),
    ),
    (
        "ZL",
        re.compile(
            r"^ZL-EI(?P<fire>\d+)-H(?P<height>\d+)-(?P<generation>\d+(?:[.,]\d+)?)$",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class XTDesignation:
    family: str
    canonical: str
    fields: Mapping[str, str]


def _normalize_surface(value: str) -> str:
    text = str(value or "").translate(_DASH_TRANSLATION).replace("\u00a0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text


def _remove_xt_prefix(value: str) -> tuple[str, bool]:
    text = _normalize_surface(value)
    match = _PREFIX_RE.match(text)
    if not match:
        return text, False
    return text[match.end():].strip(), True


def parse_xt_designation(value: str) -> XTDesignation | None:
    """Parse only a complete, known XT designation. Never accepts partial/fuzzy matches."""
    core, _had_prefix = _remove_xt_prefix(value)
    core = core.strip().upper().replace(",", ".")
    for family, pattern in _PATTERNS:
        match = pattern.fullmatch(core)
        if not match:
            continue
        fields = {key: str(val).upper().replace(",", ".") for key, val in match.groupdict().items() if val is not None}
        return XTDesignation(family=family, canonical=core, fields=fields)
    return None


def canonicalize_xt_input(value: str) -> str:
    """Strip the harmless 'XT Typ' wrapper only when the remaining designation is fully valid."""
    parsed = parse_xt_designation(value)
    if parsed is None:
        return _normalize_surface(value)
    return parsed.canonical


def install(_base=None) -> None:
    """Patch bulk preprocessing without changing catalogue/statical data."""
    import bulk_import_engine

    if getattr(bulk_import_engine, "_turto_isokorb_xt_243", False):
        return

    original = bulk_import_engine.preprocess_bulk_designation

    def preprocess_bulk_designation(designation: str, note: str = "") -> tuple[str, str]:
        text, result_note = original(designation, note)
        parsed = parse_xt_designation(text)
        if parsed is not None:
            text = parsed.canonical
        return text, result_note

    bulk_import_engine.preprocess_bulk_designation = preprocess_bulk_designation
    bulk_import_engine._turto_isokorb_xt_243 = True


_SAMPLE_ROWS: tuple[tuple[str, int, str], ...] = (
    ("XT Typ KL-M3-V2-REI120-CV1-H240-6.2", 81, "KL"),
    ("XT Typ KL-M3-V2-REI120-CV1-H250-6.2", 7, "KL"),
    ("XT Typ KL-M3-VV1-REI120-CV1-H240-6.2", 2, "KL"),
    ("XT Typ KL-M4-V2-REI120-CV1-H240-6.2", 142, "KL"),
    ("XT Typ KL-M4-V2-REI120-CV1-H250-6.2", 1, "KL"),
    ("XT Typ KL-M5-V2-REI120-CV1-H240-6.2", 12, "KL"),
    ("XT Typ KL-M5-V2-REI120-CV1-H250-6.2", 4, "KL"),
    ("XT Typ KL-M6-V2-REI120-CV1-H240-6.2", 71, "KL"),
    ("XT Typ KL-M7-V1-REI120-CV1-H240-6.2", 5, "KL"),
    ("XT Typ KL-M7-V2-REI120-CV1-H240-6.2", 2, "KL"),
    ("XT Typ KL-M8-V1-REI120-CV1-H240-6.2", 3, "KL"),
    ("XT Typ KL-M8-V1-REI120-CV1-H250-6.2", 1, "KL"),
    ("XT Typ KL-M8-VV1-REI120-CV1-H240-6.2", 2, "KL"),
    ("XT Typ QL-VV1-REI120-H240-6.0", 2, "QL"),
    ("XT Typ QL-VV3-REI120-H240-6.0", 2, "QL"),
    ("XT Typ QL-VV4-REI120-H240-6.0", 7, "QL"),
    ("XT Typ QL-VV5-REI120-H240-6.0", 19, "QL"),
    ("XT Typ QL-VV5-REI120-H250-6.0", 1, "QL"),
    ("XT Typ QL-VV6-REI120-H240-6.0", 3, "QL"),
    ("XT Typ QL-VV7-REI120-H240-6.0", 6, "QL"),
    ("XT Typ QP-V10-REI120-H240-L500-5.0", 2, "QP"),
    ("XT Typ QP-V1-REI120-H240-L300-5.0", 12, "QP"),
    ("XT Typ QP-V2-REI120-H240-L400-5.0", 4, "QP"),
    ("XT Typ QP-V3-REI120-H240-L500-5.0", 3, "QP"),
    ("XT Typ QP-V5-REI120-H240-L400-5.0", 7, "QP"),
    ("XT Typ QP-V7-REI120-H240-L400-5.0", 19, "QP"),
    ("XT Typ QP-V7-REI120-H250-L400-5.0", 1, "QP"),
    ("XT Typ QP-Z-V7-REI120-H240-L400-5.0", 9, "QP-Z"),
    ("XT Typ ZL-EI120-H240-5.3", 164, "ZL"),
    ("XT Typ ZL-EI120-H250-5.3", 7, "ZL"),
)


def selftest() -> None:
    family_totals: dict[str, int] = {}
    parsed_rows: list[XTDesignation] = []
    for text, quantity, expected_family in _SAMPLE_ROWS:
        parsed = parse_xt_designation(text)
        assert parsed is not None, text
        assert parsed.family == expected_family, (text, parsed.family)
        assert canonicalize_xt_input(text) == parsed.canonical
        family_totals[parsed.family] = family_totals.get(parsed.family, 0) + quantity
        parsed_rows.append(parsed)

    assert len(parsed_rows) == 30
    assert len({item.canonical for item in parsed_rows}) == 30
    assert sum(quantity for _text, quantity, _family in _SAMPLE_ROWS) == 601
    assert family_totals == {"KL": 333, "QL": 40, "QP": 48, "QP-Z": 9, "ZL": 171}

    v10 = parse_xt_designation("XT Typ QP-V10-REI120-H240-L500-5.0")
    vv1 = parse_xt_designation("XT Typ KL-M3-VV1-REI120-CV1-H240-6.2")
    qpz = parse_xt_designation("XT Typ QP-Z-V7-REI120-H240-L400-5.0")
    assert v10 and v10.fields["shear"] == "V10"
    assert vv1 and vv1.fields["shear"] == "VV1"
    assert qpz and qpz.family == "QP-Z"

    # Refuse partial/unknown structures rather than guessing.
    assert parse_xt_designation("XT Typ QP-V1-REI120-H240-5.0") is None
    assert parse_xt_designation("XT Typ ZL-REI120-H240-5.3") is None


if __name__ == "__main__":
    selftest()
