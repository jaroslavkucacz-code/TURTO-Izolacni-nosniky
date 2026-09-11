from __future__ import annotations

"""Peikko EBEA / TEBEA decoding and functional-compatibility layer.

TURTO 2.2.30 intentionally does not contain Peikko resistance tables.
The module recognizes product families/models and their structural role, but
never reports a statically verified replacement or utilization without a
verified, country-specific resistance dataset.
"""

from dataclasses import dataclass, replace
from html import unescape
import re
from typing import Iterable

MODULE_VERSION = "2.2.30"
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

    variant: str = ""
    material: str = ""
    reinforcement: str = ""
    standard_d_mm: int | None = None
    ds_mm: int | None = None
    dt_mm: int | None = None
    sw_mm: int | None = None
    length_mm: int | None = None
    s11_mm: int | None = None
    cover_mm: int | None = None
    concrete: str = ""
    fire_rating: str = ""
    oq: bool = False
    position_reference: str = ""
    unknown_text: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def configuration_key(self) -> str:
        """Full normalized configuration, WITHOUT the drawing/position prefix."""
        return self.canonical

    @property
    def parameters(self) -> dict:
        return {key: getattr(self, key) for key in (
            "variant", "material", "reinforcement", "standard_d_mm", "ds_mm", "dt_mm", "sw_mm",
            "length_mm", "s11_mm", "cover_mm", "concrete", "fire_rating", "oq",
            "unknown_text",
        )}

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
    ModelSpec("EBEA", "ZS", ROLE_OTHER, "ebea_zs_unverified", (80, 120),
              "Doplňkový typ ZS z výkazu; nosná funkce a parametry vyžadují ověření.",
              "Označení z uživatelského výkazu; technické údaje ZS nejsou ověřeny."),
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
    value = unescape(str(text or "")).replace("\\_", "_").upper()
    value = value.replace("®", "").replace("–", "-").replace("—", "-").replace("−", "-")
    value = value.replace("×", "X").replace("✕", "X").replace("\u00a0", " ")
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


def is_peikko(text: str) -> bool:
    return re.search(r"\b(?:TEBEA|EBEA)(?:\b|®)", str(text or ""), re.I) is not None


def decode_peikko(text: str) -> DecodedPeikko | None:
    """Decode explicit tokens only. Missing values are NEVER filled by guesses.

    This is syntax recognition, not validation of a manufacturer's product or
    its resistance. Unfamiliar tokens remain part of the configuration key.
    Conflicting repeated parameters and malformed known parameters are errors.
    """
    raw = unescape(str(text or "")).replace("\\_", "_").strip()
    if not raw:
        return None
    normalized = _norm(raw)
    families = list(re.finditer(r"\b(?:TEBEA|EBEA)\b", normalized))
    if len(families) > 1:
        raise ValueError("Řádek obsahuje více prvků EBEA/TEBEA; použijte hromadné vložení.")
    found = _match_after_family(normalized, "TEBEA", _TEBEA_TOKENS)
    if found is None:
        found = _match_after_family(normalized, "EBEA", _EBEA_TOKENS)
    if found is None:
        return None
    spec, trailing = found
    prefix = raw[:re.search(r"\b(?:TEBEA|EBEA)\b", raw, re.I).start()].strip(" |;\t\r\n")
    work = trailing
    params: dict = {}
    def take(name: str, pattern: str, convert=str):
        nonlocal work
        matches = list(re.finditer(pattern, work, re.I))
        if not matches:
            return
        values = [convert(m.group(1)) for m in matches]
        if len(set(values)) != 1:
            raise ValueError(f"Rozporné hodnoty parametru {name}: " + ", ".join(map(str, values)))
        params[name] = values[0]
        work = re.sub(pattern, " ", work, flags=re.I)

    take("variant", r"(?<!\w)(B\d+)(?!\w)")
    take("material", r"(?<!\w)(RS|VE1|VE2)(?!\w)")
    take("reinforcement", r"(?<!\w)(\d+\s*X\s*\d+\s*-\s*\d+)(?!\w)",
         lambda x: re.sub(r"\s+", "", x).lower())
    for token, field in (("DS", "ds_mm"), ("DT", "dt_mm"), ("D", "standard_d_mm"), ("SW", "sw_mm"),
                         ("L", "length_mm"), ("S11", "s11_mm"), ("CV", "cover_mm")):
        take(field, rf"(?<!\w){token}\s*=?\s*([+-]?\d+)(?:\s*MM)?(?![\w.,])", int)
        if field in params and params[field] <= 0:
            raise ValueError(f"{token} musí být kladný rozměr v mm.")
        if re.search(rf"(?<!\w){token}(?=$|[\s=+\-0-9])", work):
            raise ValueError(f"Neplatný nebo neúplný parametr {token}.")
    take("fire_rating", r"(?<!\w)(REI\s*=?\s*\d+)(?!\w)",
         lambda x: re.sub(r"[\s=]", "", x))
    take("concrete", r"(?<!\w)(C\s*\d+\s*/\s*\d+)(?!\w)",
         lambda x: re.sub(r"\s+", "", x))
    if re.search(r"(?<!\w)OQ(?!\w)", work):
        params["oq"] = True
        work = re.sub(r"(?<!\w)OQ(?!\w)", " ", work)
    unknown = re.sub(r"\s+", " ", work).strip(" -:;,/()")
    if params.get("reinforcement") and any(int(x) <= 0 for x in re.split(r"[x-]", params["reinforcement"])):
        raise ValueError("Počty/průměry v kódu výztuže musí být kladné.")
    warnings = []
    if unknown:
        warnings.append("Nerozpoznané údaje zachovány beze změny: " + unknown)
    if not params.get("cover_mm") and spec.model != "ZS":
        warnings.append("Krytí nebylo uvedeno; z Ds/Dt ani S11 se nedopočítává.")
    if params.get("ds_mm") and params.get("dt_mm") and params["ds_mm"] != params["dt_mm"]:
        warnings.append("Ds a Dt se liší; geometrii spoje je nutné ověřit.")
    if params.get("sw_mm") and params["sw_mm"] not in spec.insulation_mm:
        warnings.append("SW je mimo standardní tloušťky této datové řady; ověřit konkrétní provedení.")
    if spec.model == "ZS":
        warnings.append("ZS: pouze rozpoznání označení, bez statického návrhu a bez automatické nosné záměny.")
    name = spec.canonical
    if spec.family == "EBEA" and spec.model.startswith("E-"):
        name = "EBEA-" + spec.model.replace("E-", "E")
    if params.get("variant"):
        name += "-" + params["variant"]
    tokens = [name]
    tokens.extend(params[key] for key in ("material", "reinforcement") if params.get(key))
    for token, key in (("Ds", "ds_mm"), ("Dt", "dt_mm"), ("D", "standard_d_mm"), ("SW", "sw_mm"),
                       ("L", "length_mm"), ("S11=", "s11_mm"), ("CV", "cover_mm")):
        if params.get(key) is not None:
            tokens.append(f"{token}{params[key]}")
    tokens.extend(params[key] for key in ("concrete", "fire_rating") if params.get(key))
    if params.get("oq"):
        tokens.append("OQ")
    if unknown:
        tokens.append(unknown)
    return DecodedPeikko(
        raw=raw, family=spec.family, model=spec.model, canonical=" ".join(tokens),
        role=spec.role, compatibility_group=spec.compatibility_group,
        insulation_mm=(params["sw_mm"],) if params.get("sw_mm") else spec.insulation_mm,
        description=spec.description, source=spec.source, trailing_text=trailing,
        position_reference=prefix, unknown_text=unknown, warnings=tuple(warnings), **params,
    )


def normalize_bulk_text(text: str) -> str:
    """Join multiline EBEA schedules; leave non-Peikko rows and quantities intact.

    Only dedicated continuation rows are joined. A new product, tabular row or
    position always starts a new record. No grouping or quantity summation.
    """
    if not is_peikko(text):
        return text
    lines = []
    for raw in unescape(str(text)).replace("\\_", "_").splitlines():
        line = raw.strip()
        if not line or re.fullmatch(r"[|\s:–-]+", line):
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            line = "\t".join(cells)
        lines.append(line)
    output: list[str] = []
    pending: list[str] = []
    current = ""
    position = ""
    def flush():
        nonlocal current, position
        if current:
            # Already-tabular rows retain the user's quantity and note columns.
            output.append((position + "\t" if position else "") + current)
        current, position = "", ""
    for line in lines:
        if is_peikko(line):
            flush()
            if pending:
                position = pending[0]
                reference = " ".join(pending[1:])
                if reference:
                    line = reference + " " + line
                pending.clear()
            # Same-line position prefix (e.g. e9 EBEA-700...), not drawing reference.
            m = re.match(r"^(e\d+|zs)\s+((?:EBEA|TEBEA)\b.*)$", line, re.I)
            if m and "\t" not in line:
                position, line = m.groups()
            current = line
        elif current and "\t" not in line and re.match(
                r"^(?:Ds|Dt|D(?=\d|\s*=)|SW|L(?=\d|\s*=)|S11|REI|OQ\b|CV|RS\b|VE[12]\b|C\d+/)", line, re.I):
            # Never append after tab-separated note/quantity columns.
            parts = current.split("\t")
            indices = [i for i, part in enumerate(parts) if is_peikko(part)]
            if len(indices) == 1:
                parts[indices[0]] += " " + line
                current = "\t".join(parts)
            else:
                current += " " + line
        elif re.fullmatch(r"e\d+|zs|[A-Za-z0-9]+_[A-Za-z0-9_]+", line, re.I):
            flush()
            pending.append(line)
        else:
            flush()
            output.extend(pending)
            pending.clear()
            output.append(line)
    flush()
    output.extend(pending)
    return "\n".join(output)


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

    if not (src.family == cand_family and src.compatibility_group == cand_group):
        return False
    if not isinstance(candidate, ModelSpec):
        # Functional compatibility must not conceal a known geometric conflict.
        for key in src.parameters:
            left, right = getattr(src, key), getattr(cand, key)
            if left not in (None, "", False) and right not in (None, "", False) and left != right:
                return False
        if src.variant != cand.variant or src.unknown_text != cand.unknown_text:
            return False
    return True


def compatible_models(source: str | DecodedPeikko, *, include_self: bool = False) -> tuple[ModelSpec, ...]:
    src = source if isinstance(source, DecodedPeikko) else decode_peikko(str(source))
    if src is None:
        return ()
    result = []
    for spec in MODEL_SPECS:
        if spec.family != src.family or spec.compatibility_group != src.compatibility_group:
            continue
        if src.trailing_text and spec.model != src.model:
            continue  # A configured source must not turn into generic alternate models.
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
    rows = [decoded.canonical, f"Výrobce: {decoded.manufacturer}",
            f"Funkce řady: {ROLE_LABELS.get(decoded.role, decoded.role)}",
            f"Stav: {decoded.status}"]
    labels = {"variant": "Varianta", "material": "Provedení výztuže",
              "reinforcement": "Kód výztuže (nikoli únosnost)", "ds_mm": "Ds [mm]",
              "standard_d_mm": "Výslovně zadané standardní D [mm]", "dt_mm": "Dt [mm]", "sw_mm": "Izolant SW [mm]", "length_mm": "Délka L [mm]",
              "s11_mm": "S11 [mm]", "cover_mm": "Zadané krytí CV [mm]", "concrete": "Zadaný beton",
              "fire_rating": "Požární označení z výkazu (neověřeno)", "oq": "OQ (kód z výkazu)",
              "unknown_text": "Další nerozpoznané údaje"}
    for key, value in decoded.parameters.items():
        if value not in (None, "", False):
            rows.append(f"{labels[key]}: {('ano' if value is True else value)}")
    if decoded.position_reference:
        rows.append("Reference výkresu / pozice: " + decoded.position_reference)
    rows.extend(decoded.warnings)
    rows.extend(("Dekódování samo nepotvrzuje únosnosti. Doložené tabulkové údaje jsou v technickém přehledu; prázdná hodnota není nula.",
                 "Zdroj popisu řady: " + decoded.source))
    return "\n".join(rows)


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
