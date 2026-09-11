from __future__ import annotations

"""Peikko EBEA / TEBEA identification layer for TURTO 2.2.28.

This module intentionally contains no structural resistance values.
Recognised products remain blocked for automatic design/substitution until
verified Peikko resistance data are added to a later data package.
"""

import re
from typing import Any

MANUFACTURER = "Peikko"
MODULE_VERSION = "2.2.28"
UNVERIFIED_STATUS = "rozpoznáno – nutné statické ověření"

EBEA_TYPES = (
    "E-100", "E-900", "100", "200", "500", "600", "700", "800",
    "900", "1000", "1100", "1200", "TYPE G",
)
TEBEA_TYPES = (
    "CM-VV", "PM-VV", "RM-VV", "RMC-V", "PVV-S", "PVV-W", "LM-VV",
    "CM-V", "PM-V", "RM-V", "HM-W", "PV-S", "V-S", "PV-W", "V-W",
    "LM-V", "EA", "EH", "ES", "N",
)

_TEBEA_FUNCTION = {
    **{key: "moment_shear" for key in ("CM-V", "PM-V", "RM-V", "CM-VV", "PM-VV", "RM-VV", "RMC-V", "LM-V", "LM-VV")},
    **{key: "shear" for key in ("HM-W", "PV-S", "PVV-S", "V-S", "PV-W", "PVV-W", "V-W")},
    **{key: "horizontal" for key in ("EA", "EH", "ES")},
    "N": "non_loadbearing",
}
_EBEA_FUNCTION = {key: ("special" if key == "TYPE G" else "loadbearing") for key in EBEA_TYPES}

_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‑": "-", "‐": "-"})


def normalize_designation(text: Any) -> str:
    value = str(text or "").translate(_DASHES).upper()
    value = value.replace("PEIKKO®", "PEIKKO").replace("EBEA®", "EBEA").replace("TEBEA®", "TEBEA")
    value = re.sub(r"\s*-\s*", "-", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _extract_insulation(tail: str) -> int | None:
    matches = re.findall(r"(?<!\d)(60|80|100|120)\s*MM\b", tail)
    if matches:
        return int(matches[-1])
    match = re.search(r"(?:^|[\s/-])(60|80|100|120)(?=$|[\s/-])", tail)
    return int(match.group(1)) if match else None


def _match_type(text: str, family: str) -> tuple[str | None, str]:
    if family == "TEBEA":
        for code in sorted(TEBEA_TYPES, key=len, reverse=True):
            match = re.search(rf"\b{re.escape(code)}\b", text)
            if match:
                return code, text[match.end():]
        return None, ""
    type_g = re.search(r"\bTYPE\s*G\b", text)
    if type_g:
        return "TYPE G", text[type_g.end():]
    for code in ("E-100", "E-900", "1200", "1100", "1000", "100", "200", "500", "600", "700", "800", "900"):
        match = re.search(rf"(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])", text)
        if match:
            return code, text[match.end():]
    return None, ""


def decode_peikko_designation(text: Any) -> dict[str, Any]:
    raw = str(text or "")
    normalized = normalize_designation(raw)
    family = "TEBEA" if re.search(r"\bTEBEA\b", normalized) else ("EBEA" if re.search(r"\bEBEA\b", normalized) else None)
    if not family:
        return {
            "recognized": False, "manufacturer": None, "family": None, "type_code": None,
            "normalized_designation": normalized, "insulation_mm": None, "standard_insulation_mm": None,
            "function_class": None, "verified_capacity": False, "automatic_substitution_allowed": False,
            "design_status": None, "warnings": [],
        }

    type_code, tail = _match_type(normalized, family)
    if not type_code:
        return {
            "recognized": False, "manufacturer": MANUFACTURER, "family": family, "type_code": None,
            "normalized_designation": normalized, "insulation_mm": None,
            "standard_insulation_mm": [80, 120] if family == "EBEA" else [120],
            "function_class": None, "verified_capacity": False, "automatic_substitution_allowed": False,
            "design_status": UNVERIFIED_STATUS, "warnings": [f"Neznámý nebo neúplný typ {family}."],
        }

    insulation = _extract_insulation(tail)
    warnings: list[str] = []
    if family == "EBEA":
        standard = [80, 120]
        function_class = _EBEA_FUNCTION[type_code]
        if insulation in {60, 100}:
            warnings.append("Tloušťka izolantu je nestandardní / na vyžádání; automatický návrh je zakázán.")
        elif insulation is not None and insulation not in standard:
            warnings.append("Tloušťka izolantu není v podporovaném standardním rozsahu EBEA.")
    else:
        standard = [120]
        function_class = _TEBEA_FUNCTION[type_code]
        if insulation is not None and insulation != 120:
            warnings.append("TEBEA je v této vrstvě vedena se standardním izolantem 120 mm; zadanou variantu je nutné ověřit.")

    warnings.append("Statické únosnosti Peikko nejsou v této verzi ověřeně přiřazeny.")
    return {
        "recognized": True, "manufacturer": MANUFACTURER, "family": family, "type_code": type_code,
        "normalized_designation": normalized, "insulation_mm": insulation, "standard_insulation_mm": standard,
        "function_class": function_class, "verified_capacity": False, "automatic_substitution_allowed": False,
        "design_status": UNVERIFIED_STATUS, "warnings": warnings,
    }


def is_peikko_text(text: Any) -> bool:
    return bool(decode_peikko_designation(text).get("recognized"))


def functionally_compatible(left: Any, right: Any) -> bool:
    a = left if isinstance(left, dict) else decode_peikko_designation(left)
    b = right if isinstance(right, dict) else decode_peikko_designation(right)
    if not a.get("recognized") or not b.get("recognized"):
        return False
    return bool(a.get("function_class") and a.get("function_class") == b.get("function_class"))


def automatic_design_allowed(value: Any) -> bool:
    decoded = value if isinstance(value, dict) else decode_peikko_designation(value)
    return bool(decoded.get("recognized") and decoded.get("verified_capacity") and decoded.get("automatic_substitution_allowed"))


def substitution_block_reason(value: Any) -> str | None:
    decoded = value if isinstance(value, dict) else decode_peikko_designation(value)
    if not decoded.get("recognized"):
        return None
    if automatic_design_allowed(decoded):
        return None
    return (
        f"Peikko {decoded.get('family')} {decoded.get('type_code')}: {UNVERIFIED_STATUS}. "
        "Automatický návrh/záměna je z bezpečnostních důvodů zablokována."
    )


def selftest() -> None:
    cases = {
        "EBEA 100 80": ("EBEA", "100", 80, "loadbearing"),
        "Peikko EBEA E-100 120 mm": ("EBEA", "E-100", 120, "loadbearing"),
        "EBEA Type G 80": ("EBEA", "TYPE G", 80, "special"),
        "TEBEA CM-V 120": ("TEBEA", "CM-V", 120, "moment_shear"),
        "TEBEA PVV-S": ("TEBEA", "PVV-S", None, "shear"),
        "Peikko TEBEA EA": ("TEBEA", "EA", None, "horizontal"),
        "TEBEA N": ("TEBEA", "N", None, "non_loadbearing"),
    }
    for text, expected in cases.items():
        d = decode_peikko_designation(text)
        got = (d["family"], d["type_code"], d["insulation_mm"], d["function_class"])
        assert d["recognized"], text
        assert got == expected, (text, got, expected)
        assert d["verified_capacity"] is False
        assert d["automatic_substitution_allowed"] is False
        assert automatic_design_allowed(d) is False
        assert substitution_block_reason(d)
    assert not decode_peikko_designation("HIT HP SP MVX")["recognized"]
    assert not decode_peikko_designation("TEBEA UNKNOWN")["recognized"]
    assert functionally_compatible("TEBEA CM-V", "TEBEA LM-V")
    assert not functionally_compatible("TEBEA CM-V", "TEBEA PV-S")
