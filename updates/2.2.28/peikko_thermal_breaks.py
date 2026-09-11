from __future__ import annotations

"""Peikko EBEA / TEBEA decoding and functional-compatibility layer.

TURTO 2.2.28 intentionally does not contain Peikko resistance tables.
The module recognizes product families/models and their structural role, but
never reports a statically verified replacement or utilization without a
verified, country-specific resistance dataset.
"""

from dataclasses import dataclass
import re
from typing import Iterable

MODULE_VERSION = "2.2.28"
MANUFACTURER = "Peikko"
DESIGN_STATUS = "Rozpoznáno – nutné statické ověření"
SOURCE_EBEA = "Peikko EBEA Technical Manual 08/2023"
SOURCE_TEBEA = "Peikko TEBEA Technical Manual 08/2025"

ROLE_MOMENT_SHEAR = "moment + smyk"
ROLE_SHEAR = "smyk"
ROLE_HORIZONTAL = "vodorovné síly"
ROLE_NONLOAD = "nenosný / výplňový"
ROLE_OTHER = "speciální nosný"

ROLE_LABELS = {
    ROLE_MOMENT_SHEAR: "Moment + smyk",
    ROLE_SHEAR: "Smyk",
    ROLE_HORIZONTAL: "Vodorovné síly",
    ROLE_NONLOAD: "Nenosný / výplňový",
    ROLE_OTHER: "Speciální nosný",
}


@dataclass(frozen=True)
class ModelSpec:
    family: str
    model: str
    role: str
    compatibility_group: str
    insulation_mm: tuple[int, ...]
    description: str
    source: str
    aliases: tuple[str, ...] = ()

    @property
    def canonical(self) -> str:
        if self.family == "EBEA":
            if self.model.startswith("E-"):
                return f"EBEA {self.model}"
            if self.model == "G":
                return "EBEA Type G"
            return f"EBEA-{self.model}"
        return f"TEBEA {self.model}"


@dataclass(frozen=True)
class DecodedPeikko:
    raw: str
    family: str
    model: str
    canonical: str
    role: str
    compatibility_group: str
    insulation_mm: tuple[int, ...]
    description: str
    source: str
    trailing_text: str
    status: str = DESIGN_STATUS
    manufacturer: str = MANUFACTURER

    @property
    def is_load_bearing(self) -> bool:
        return self.role != ROLE_NONLOAD


# Functional groups are deliberately conservative. A shared role alone is not
# enough for an automatic substitution: geometry, movement behaviour and
# country-specific resistances still have to be checked.
_EBEA = (
    ModelSpec("EBEA", "100", ROLE_MOMENT_SHEAR, "ebea_cantilever_mneg_vbidir", (80, 120),
              "Konzolový spoj: záporný moment a smyk v obou směrech.", SOURCE_EBEA),
    ModelSpec("EBEA", "E-100", ROLE_MOMENT_SHEAR, "ebea_cantilever_mneg_vbidir_corner", (80, 120),
              "Rohový prvek k EBEA-100: záporný moment a smyk v obou směrech.", SOURCE_EBEA,
              aliases=("E100",)),
    ModelSpec("EBEA", "200", ROLE_MOMENT_SHEAR, "ebea_continuous_mbidir_vbidir", (80, 120),
              "Průběžná deska: moment a smyk v obou směrech.", SOURCE_EBEA),
    ModelSpec("EBEA", "500", ROLE_SHEAR, "ebea_shear_bidir", (80, 120),
              "Smykový prvek pro smyk v obou směrech.", SOURCE_EBEA),
    ModelSpec("EBEA", "600", ROLE_SHEAR, "ebea_shear_positive", (80, 120),
              "Smykový prvek pro smyk v jednom směru.", SOURCE_EBEA),
    ModelSpec("EBEA", "700", ROLE_OTHER, "ebea_moment_shear_axial", (80, 120),
              "Speciální konzolový/parapetní prvek: moment, smyk a osová síla.", SOURCE_EBEA),
    ModelSpec("EBEA", "800", ROLE_SHEAR, "ebea_offset_shear_bidir", (80,),
              "Výškově odsazené desky: smyk v obou směrech.", SOURCE_EBEA),
    ModelSpec("EBEA", "900", ROLE_MOMENT_SHEAR, "ebea_mbidir_vbidir_site_rebar", (80,),
              "Moment a smyk v obou směrech; ohybová výztuž se doplňuje na stavbě.", SOURCE_EBEA),
    ModelSpec("EBEA", "E-900", ROLE_MOMENT_SHEAR, "ebea_mbidir_vbidir_site_rebar_corner", (80, 120),
              "Rohový prvek k EBEA-900; moment a smyk v obou směrech.", SOURCE_EBEA,
              aliases=("E900",)),
    ModelSpec("EBEA", "1000", ROLE_MOMENT_SHEAR, "ebea_offset_mbidir_vbidir", (80,),
              "Výškově odsazené balkony: moment a smyk v obou směrech.", SOURCE_EBEA),
    ModelSpec("EBEA", "1100", ROLE_MOMENT_SHEAR, "ebea_cantilever_mneg_vpositive", (80, 120),
              "Konzolový spoj: záporný moment a smyk v jednom směru.", SOURCE_EBEA),
    ModelSpec("EBEA", "1200", ROLE_MOMENT_SHEAR, "ebea_continuous_mbidir_vbidir_acoustic", (80, 120),
              "Průběžná deska: moment a smyk v obou směrech, akusticky výhodné provedení.", SOURCE_EBEA),
    ModelSpec("EBEA", "G", ROLE_HORIZONTAL, "ebea_horizontal_parallel", (80,),
              "Seismický prvek pro vodorovné síly rovnoběžně se spárou.", SOURCE_EBEA,
              aliases=("TYPE G", "TYPE-G")),
)

_TEBEA_MODELS = (
    ("CM-V", ROLE_MOMENT_SHEAR, "tebea_cantilever_v", "Konzolový balkon; momentový/smykový prvek CM."),
    ("PM-V", ROLE_MOMENT_SHEAR, "tebea_cantilever_v", "Konzolový balkon; momentový/smykový prvek PM."),
    ("RM-V", ROLE_MOMENT_SHEAR, "tebea_cantilever_v", "Konzolový balkon; momentový/smykový prvek RM."),
    ("CM-VV", ROLE_MOMENT_SHEAR, "tebea_cantilever_vv", "Konzolový balkon; momentový/smykový prvek CM-VV."),
    ("PM-VV", ROLE_MOMENT_SHEAR, "tebea_cantilever_vv", "Konzolový balkon; momentový/smykový prvek PM-VV."),
    ("RM-VV", ROLE_MOMENT_SHEAR, "tebea_cantilever_vv", "Konzolový balkon; momentový/smykový prvek RM-VV."),
    ("RMC-V", ROLE_MOMENT_SHEAR, "tebea_rmc_v", "Konzolový balkon; momentový/smykový prvek RMC."),
    ("HM-W", ROLE_MOMENT_SHEAR, "tebea_hm_w", "Výškově odsazený balkon / stěna; moment a smyk."),
    ("PV-S", ROLE_SHEAR, "tebea_pv_s", "Podepřený balkon; smykový prvek PV-S."),
    ("PVV-S", ROLE_SHEAR, "tebea_pvv_s", "Podepřený balkon; smykový prvek PVV-S pro oba směry smyku."),
    ("V-S", ROLE_SHEAR, "tebea_v_s", "Podepřený balkon; smyk, podélný posun je umožněn."),
    ("PV-W", ROLE_SHEAR, "tebea_pv_w", "Výškově odsazený podepřený balkon / stěna; smykový prvek PV-W."),
    ("PVV-W", ROLE_SHEAR, "tebea_pvv_w", "Výškově odsazený podepřený balkon / stěna; smykový prvek PVV-W."),
    ("V-W", ROLE_SHEAR, "tebea_v_w", "Výškově odsazený podepřený balkon / stěna; smyk, podélný posun je umožněn."),
    ("LM-V", ROLE_MOMENT_SHEAR, "tebea_lm_v", "Římsa/parapet/krátká konzola; moment a smyk."),
    ("LM-VV", ROLE_OTHER, "tebea_lm_vv", "Atika a podobné prvky; tlak, moment a smyk."),
    ("EA", ROLE_HORIZONTAL, "tebea_horizontal_perpendicular", "Vodorovné síly kolmo na spáru."),
    ("EH", ROLE_HORIZONTAL, "tebea_horizontal_parallel", "Vodorovné síly rovnoběžně se spárou."),
    ("ES", ROLE_HORIZONTAL, "tebea_horizontal_both", "Vodorovné síly rovnoběžně i kolmo na spáru."),
    ("N", ROLE_NONLOAD, "tebea_nonload", "Nenosný výplňový/distanční prvek bez přenosu sil."),
)
_TEBEA = tuple(
    ModelSpec("TEBEA", model, role, group, (120,), description, SOURCE_TEBEA)
    for model, role, group, description in _TEBEA_MODELS
)

MODEL_SPECS: tuple[ModelSpec, ...] = _EBEA + _TEBEA
BY_KEY = {(spec.family, spec.model): spec for spec in MODEL_SPECS}

# Longest tokens first prevents "N" or "-V" style fragments from stealing a match.
_TEBEA_TOKENS = sorted((spec.model for spec in _TEBEA), key=len, reverse=True)
_EBEA_TOKENS = sorted(
    {spec.model for spec in _EBEA} | {alias for spec in _EBEA for alias in spec.aliases},
    key=len,
    reverse=True,
)


def _norm(text: str) -> str:
    value = str(text or "").upper()
    value = value.replace("®", "").replace("–", "-").replace("—", "-").replace("_", "-")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _lookup_alias(family: str, token: str) -> ModelSpec | None:
    token = _norm(token)
    for spec in MODEL_SPECS:
        if spec.family != family:
            continue
        if _norm(spec.model) == token:
            return spec
        if any(_norm(alias) == token for alias in spec.aliases):
            return spec
    return None


def _match_after_family(normalized: str, family: str, tokens: Iterable[str]) -> tuple[ModelSpec, str] | None:
    match = re.search(rf"\b{family}\b", normalized)
    if not match:
        return None
    tail = normalized[match.end():].lstrip(" -:/")
    # EBEA Type G is common wording and should resolve before generic token logic.
    if family == "EBEA":
        g = re.match(r"(?:TYPE\s*[- ]?\s*)?G(?:\b|$)", tail)
        if g:
            spec = BY_KEY[("EBEA", "G")]
            return spec, tail[g.end():].lstrip(" -:/")
    for token in tokens:
        pattern = re.escape(_norm(token)).replace(r"\ ", r"\s*")
        m = re.match(pattern + r"(?=$|[\s:/;,()\-])", tail)
        if m:
            spec = _lookup_alias(family, token)
            if spec is not None:
                return spec, tail[m.end():].lstrip(" -:/")
    return None


def decode_peikko(text: str) -> DecodedPeikko | None:
    """Decode EBEA/TEBEA family and model from an arbitrary product string.

    Extra dimensions/reinforcement tokens are intentionally preserved in
    ``trailing_text`` rather than interpreted as resistance data.
    """
    raw = str(text or "").strip()
    if not raw:
        return None
    normalized = _norm(raw)

    found = _match_after_family(normalized, "TEBEA", _TEBEA_TOKENS)
    if found is None:
        found = _match_after_family(normalized, "EBEA", _EBEA_TOKENS)
    if found is None:
        return None

    spec, trailing = found
    return DecodedPeikko(
        raw=raw,
        family=spec.family,
        model=spec.model,
        canonical=spec.canonical,
        role=spec.role,
        compatibility_group=spec.compatibility_group,
        insulation_mm=spec.insulation_mm,
        description=spec.description,
        source=spec.source,
        trailing_text=trailing,
    )


def specs_for_family(family: str) -> tuple[ModelSpec, ...]:
    family = _norm(family)
    return tuple(spec for spec in MODEL_SPECS if spec.family == family)


def specs_for_role(role: str, *, family: str | None = None) -> tuple[ModelSpec, ...]:
    fam = _norm(family) if family else None
    return tuple(
        spec
        for spec in MODEL_SPECS
        if spec.role == role and (fam is None or spec.family == fam)
    )


def functionally_compatible(source: str | DecodedPeikko, candidate: str | ModelSpec | DecodedPeikko) -> bool:
    """Strict functional compatibility, never a resistance verification.

    For safety, automatic compatibility is limited to the *same Peikko family*
    and the same conservative compatibility group.
    """
    src = source if isinstance(source, DecodedPeikko) else decode_peikko(str(source))
    if src is None:
        return False

    if isinstance(candidate, ModelSpec):
        cand_family = candidate.family
        cand_group = candidate.compatibility_group
    else:
        cand = candidate if isinstance(candidate, DecodedPeikko) else decode_peikko(str(candidate))
        if cand is None:
            return False
        cand_family = cand.family
        cand_group = cand.compatibility_group

    return src.family == cand_family and src.compatibility_group == cand_group


def compatible_models(source: str | DecodedPeikko, *, include_self: bool = False) -> tuple[ModelSpec, ...]:
    src = source if isinstance(source, DecodedPeikko) else decode_peikko(str(source))
    if src is None:
        return ()
    result = []
    for spec in MODEL_SPECS:
        if spec.family != src.family or spec.compatibility_group != src.compatibility_group:
            continue
        if not include_self and spec.model == src.model:
            continue
        result.append(spec)
    return tuple(result)


def proposal_models(
    *,
    family: str,
    role: str,
    insulation_mm: int | None = None,
) -> tuple[ModelSpec, ...]:
    """Return only functionally matching candidates.

    This is a preselection for manual/static verification, not a structural
    design result.
    """
    result = []
    for spec in specs_for_role(role, family=family):
        if insulation_mm is not None and int(insulation_mm) not in spec.insulation_mm:
            continue
        result.append(spec)
    return tuple(result)


def format_decode(decoded: DecodedPeikko) -> str:
    insulation = " / ".join(str(x) for x in decoded.insulation_mm) + " mm"
    extra = decoded.trailing_text or "—"
    return (
        f"{decoded.canonical}\n"
        f"Výrobce: {decoded.manufacturer}\n"
        f"Funkce: {ROLE_LABELS.get(decoded.role, decoded.role)}\n"
        f"Standardní izolant: {insulation}\n"
        f"Popis: {decoded.description}\n"
        f"Zbytek označení: {extra}\n"
        f"Stav: {decoded.status}\n"
        f"Zdrojová řada: {decoded.source}"
    )


def selftest() -> None:
    cases = {
        "EBEA-100-VE1 200": ("EBEA", "100"),
        "EBEA E-100 / 120": ("EBEA", "E-100"),
        "EBEA E100": ("EBEA", "E-100"),
        "EBEA Type G 200": ("EBEA", "G"),
        "TEBEA CM-V 120": ("TEBEA", "CM-V"),
        "TEBEA PVV-W": ("TEBEA", "PVV-W"),
        "TEBEA N": ("TEBEA", "N"),
    }
    for raw, expected in cases.items():
        decoded = decode_peikko(raw)
        assert decoded is not None, raw
        assert (decoded.family, decoded.model) == expected, (raw, decoded)
        assert decoded.status == DESIGN_STATUS

    assert decode_peikko("HIT-HP MVX") is None
    assert BY_KEY[("EBEA", "900")].insulation_mm == (80,)
    assert BY_KEY[("TEBEA", "CM-V")].insulation_mm == (120,)
    assert BY_KEY[("TEBEA", "N")].role == ROLE_NONLOAD

    assert functionally_compatible("EBEA-100", "EBEA E-100") is False  # corner vs standard
    assert functionally_compatible("EBEA-500", "EBEA-800") is False   # offset geometry differs
    assert functionally_compatible("TEBEA EA", "TEBEA EH") is False
    assert not functionally_compatible("EBEA-100", "TEBEA CM-V")
    assert {s.model for s in compatible_models("TEBEA CM-V")} == {"PM-V", "RM-V"}
    assert {s.model for s in compatible_models("TEBEA CM-VV")} == {"PM-VV", "RM-VV"}
    assert compatible_models("TEBEA N") == ()


if __name__ == "__main__":
    selftest()
