from __future__ import annotations

"""TURTO 2.0 product/manufacturer registry.

The UI and persisted AKCE refer to stable IDs from this registry instead of
hard-coding HIT or one manufacturer into the whole application. Calculation
engines remain separate adapters; the registry only describes capabilities.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ManufacturerSpec:
    id: str
    label: str
    product_line: str
    catalog_label: str
    design_adapter: str | None = None
    substitution_adapter: str | None = None
    enabled: bool = True


@dataclass(frozen=True)
class ProductDomainSpec:
    id: str
    label: str
    short_label: str
    description: str
    operations: tuple[str, ...] = ("decoder", "design", "substitution")
    enabled: bool = False
    manufacturers: tuple[ManufacturerSpec, ...] = ()


THERMAL_MANUFACTURERS = (
    ManufacturerSpec(
        id="leviat",
        label="Leviat",
        product_line="HIT",
        catalog_label="HALFEN / Leviat HIT 20.2-EN 2023",
        design_adapter="leviat_hit",
        substitution_adapter="leviat_hit",
        enabled=True,
    ),
)

DOMAINS = (
    ProductDomainSpec(
        id="thermal_breaks",
        label="Izolační nosníky",
        short_label="Izolační nosníky",
        description="Tepelně oddělené nosné prvky balkonů, stěn a souvisejících detailů.",
        enabled=True,
        manufacturers=THERMAL_MANUFACTURERS,
    ),
    ProductDomainSpec(
        id="shear_dowels",
        label="Smykové trny",
        short_label="Smykové trny",
        description="Dekodér, návrh a záměny smykových trnů – připraveno pro katalogové adaptéry.",
        enabled=False,
        manufacturers=(),
    ),
    ProductDomainSpec(
        id="stair_acoustics",
        label="Akustika schodiště",
        short_label="Akustika schodiště",
        description="Akustické prvky schodišť a podest – připraveno pro budoucí katalogy.",
        enabled=False,
        manufacturers=(),
    ),
)

DEFAULT_DOMAIN_ID = "thermal_breaks"
DEFAULT_DESIGN_MANUFACTURER = {"thermal_breaks": "leviat"}
DEFAULT_SUBSTITUTION_MANUFACTURER = {"thermal_breaks": "leviat"}


def domain(domain_id: str) -> ProductDomainSpec:
    key = str(domain_id or "").strip()
    for item in DOMAINS:
        if item.id == key:
            return item
    raise KeyError(f"Neznámá produktová oblast: {domain_id}")


def domains() -> tuple[ProductDomainSpec, ...]:
    return DOMAINS


def manufacturers(domain_id: str, *, enabled_only: bool = False) -> tuple[ManufacturerSpec, ...]:
    values = domain(domain_id).manufacturers
    if enabled_only:
        return tuple(item for item in values if item.enabled)
    return values


def manufacturer(domain_id: str, manufacturer_id: str) -> ManufacturerSpec:
    key = str(manufacturer_id or "").strip()
    for item in manufacturers(domain_id):
        if item.id == key:
            return item
    raise KeyError(f"Neznámý výrobce {manufacturer_id} pro oblast {domain_id}")


def manufacturer_labels(domain_id: str, *, enabled_only: bool = True) -> tuple[str, ...]:
    return tuple(item.label for item in manufacturers(domain_id, enabled_only=enabled_only))


def manufacturer_id_from_label(domain_id: str, label: str) -> str:
    text = str(label or "").strip()
    for item in manufacturers(domain_id):
        if item.label == text or item.id == text:
            return item.id
    return ""


def manufacturer_label(domain_id: str, manufacturer_id: str) -> str:
    try:
        return manufacturer(domain_id, manufacturer_id).label
    except KeyError:
        return str(manufacturer_id or "")


def default_platform_state() -> dict:
    return {
        "schema_version": 1,
        "active_domain": DEFAULT_DOMAIN_ID,
        "domains": {
            item.id: {
                "design_manufacturer": DEFAULT_DESIGN_MANUFACTURER.get(item.id, ""),
                "substitution_manufacturer": DEFAULT_SUBSTITUTION_MANUFACTURER.get(item.id, ""),
            }
            for item in DOMAINS
        },
    }


def normalize_platform_state(raw: object) -> dict:
    result = default_platform_state()
    if not isinstance(raw, dict):
        return result
    active = str(raw.get("active_domain", "") or "").strip()
    if any(item.id == active for item in DOMAINS):
        result["active_domain"] = active
    source_domains = raw.get("domains") if isinstance(raw.get("domains"), dict) else {}
    for spec in DOMAINS:
        source = source_domains.get(spec.id) if isinstance(source_domains, dict) else None
        if not isinstance(source, dict):
            continue
        dst = result["domains"][spec.id]
        for key in ("design_manufacturer", "substitution_manufacturer"):
            candidate = str(source.get(key, "") or "").strip()
            if not candidate:
                continue
            if any(item.id == candidate for item in spec.manufacturers):
                dst[key] = candidate
    return result
