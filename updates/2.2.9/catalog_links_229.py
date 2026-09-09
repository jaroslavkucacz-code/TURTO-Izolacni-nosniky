from __future__ import annotations

"""Stable catalogue access registry for TURTO 2.2.9.

URLs point to official manufacturer product/download pages rather than
third-party mirrors so that the application always leads users to the current
technical documents offered by the manufacturer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogResource:
    id: str
    domain: str
    manufacturer: str
    label: str
    source: str
    url: str


CATALOG_RESOURCES = (
    CatalogResource(
        "thermal.leviat.hit",
        "thermal_breaks",
        "Leviat",
        "Leviat / HALFEN HIT",
        "HIT-HP / HIT-SP – evropské podklady a prohlášení o vlastnostech",
        "https://www.leviat.com/en-be/hit.html",
    ),
    CatalogResource(
        "thermal.schoeck.isokorb",
        "thermal_breaks",
        "Schöck",
        "Schöck Isokorb® T / XT",
        "Technické informace, dimenzační tabulky, ETA a DoP",
        "https://www.schoeck.com/cs/isokorb-t",
    ),
    CatalogResource(
        "thermal.pohlcon.isopro",
        "thermal_breaks",
        "PohlCon",
        "PohlCon ISOPRO® 80 / 120",
        "ISOPRO® – technické informace, ETA, DoP a návrhové podklady",
        "https://pohlcon.com/en-de/construction-support/thermal-insulation/balcony-insulation-elements",
    ),
    CatalogResource(
        "thermal.maxfrank.egcobox",
        "thermal_breaks",
        "MAX FRANK",
        "MAX FRANK Egcobox® M / XL",
        "Egcobox® – technické informace, ETA a produktové podklady",
        "https://www.maxfrank.com/intl-en/products/reinforcement-technologies/04-thermal-break-balcony-connector-egcobox/",
    ),
    CatalogResource(
        "shear.ancon.dsd",
        "shear_dowels",
        "Ancon",
        "Ancon DSD / DSDQ",
        "Shear Load Connectors – technické podklady výrobce",
        "https://www.leviat.com/en-au/products/structural-connections/dsd.html",
    ),
    CatalogResource(
        "shear.schoeck.stacon-ld",
        "shear_dowels",
        "Schöck",
        "Schöck Stacon® LD",
        "Technické informace, DoP a ETA 16/0545",
        "https://www.schoeck.com/cs/dorn-ld",
    ),
    CatalogResource(
        "shear.pohlcon.hed",
        "shear_dowels",
        "PohlCon",
        "PohlCon HED",
        "Shear Dowels HED – Technical Information",
        "https://pohlcon.com/en-de/construction-support/connection/dowels/shear-dowel-hed",
    ),
    CatalogResource(
        "shear.pohlcon.jdsd",
        "shear_dowels",
        "PohlCon",
        "PohlCon JDSD / JDSDQ",
        "Double Shear Dowels JDSD – Technical Information",
        "https://pohlcon.com/en-de/downloads",
    ),
    CatalogResource(
        "shear.maxfrank.egcodorn",
        "shear_dowels",
        "MAX FRANK",
        "MAX FRANK Egcodorn® / Egcodubel",
        "Shear force dowel Egcodorn® – product downloads and approvals",
        "https://www.maxfrank.com/intl-en/products/reinforcement-technologies/03-shear-force-dowel-egcodorn/",
    ),
)

EXPECTED_THERMAL_MANUFACTURERS = ("Leviat", "Schöck", "PohlCon", "MAX FRANK")
EXPECTED_SHEAR_MANUFACTURERS = ("Ancon", "Schöck", "PohlCon", "MAX FRANK")


def catalogs_for_domain(domain: str | None = None) -> tuple[CatalogResource, ...]:
    if not domain:
        return CATALOG_RESOURCES
    key = str(domain).strip()
    return tuple(item for item in CATALOG_RESOURCES if item.domain == key)


def selftest() -> None:
    assert len(CATALOG_RESOURCES) == 9
    assert {item.manufacturer for item in catalogs_for_domain("thermal_breaks")} == set(EXPECTED_THERMAL_MANUFACTURERS)
    assert {item.manufacturer for item in catalogs_for_domain("shear_dowels")} == set(EXPECTED_SHEAR_MANUFACTURERS)
    assert all(item.url.startswith("https://") for item in CATALOG_RESOURCES)
    assert len({item.id for item in CATALOG_RESOURCES}) == len(CATALOG_RESOURCES)


if __name__ == "__main__":
    selftest()
