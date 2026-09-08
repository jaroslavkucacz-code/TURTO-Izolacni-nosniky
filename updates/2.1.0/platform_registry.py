from __future__ import annotations
import platform_registry_200 as _prev
ManufacturerSpec=_prev.ManufacturerSpec
ProductDomainSpec=_prev.ProductDomainSpec
THERMAL_MANUFACTURERS=_prev.THERMAL_MANUFACTURERS
SHEAR_MANUFACTURERS=(
    ManufacturerSpec(id="ancon",label="Ancon / Leviat",product_line="ED / ESD / HLD / DSD",catalog_label="Ancon Querkraftdorne, Oktober 2018 (V1)",design_adapter="ancon_dowels",substitution_adapter="ancon_dowels",enabled=True),
    ManufacturerSpec(id="schoeck",label="Schöck",product_line="Stacon® LD / SLD",catalog_label="Schöck Stacon® – Technical Information",design_adapter=None,substitution_adapter="schoeck_stacon",enabled=True),
)
DOMAINS=(
    _prev.DOMAINS[0],
    ProductDomainSpec(id="shear_dowels",label="Smykové trny",short_label="Smykové trny",description="Smykové trny do dilatačních a pracovních spár; návrh Ancon a katalogové záměny Ancon ↔ Schöck Stacon.",enabled=True,manufacturers=SHEAR_MANUFACTURERS),
    _prev.DOMAINS[2],
)
DEFAULT_DOMAIN_ID=_prev.DEFAULT_DOMAIN_ID
DEFAULT_DESIGN_MANUFACTURER=dict(_prev.DEFAULT_DESIGN_MANUFACTURER,shear_dowels="ancon")
DEFAULT_SUBSTITUTION_MANUFACTURER=dict(_prev.DEFAULT_SUBSTITUTION_MANUFACTURER,shear_dowels="schoeck")
def domain(domain_id):
    for item in DOMAINS:
        if item.id==str(domain_id or "").strip():return item
    raise KeyError(f"Neznámá produktová oblast: {domain_id}")
def domains():return DOMAINS
def manufacturers(domain_id,*,enabled_only=False):
    vals=domain(domain_id).manufacturers;return tuple(x for x in vals if x.enabled) if enabled_only else vals
def manufacturer(domain_id,manufacturer_id):
    key=str(manufacturer_id or "").strip()
    for item in manufacturers(domain_id):
        if item.id==key:return item
    raise KeyError(f"Neznámý výrobce {manufacturer_id} pro oblast {domain_id}")
def manufacturer_labels(domain_id,*,enabled_only=True):return tuple(x.label for x in manufacturers(domain_id,enabled_only=enabled_only))
def manufacturer_id_from_label(domain_id,label):
    text=str(label or "").strip()
    for item in manufacturers(domain_id):
        if item.label==text or item.id==text:return item.id
    return ""
def manufacturer_label(domain_id,manufacturer_id):
    try:return manufacturer(domain_id,manufacturer_id).label
    except KeyError:return str(manufacturer_id or "")
def default_platform_state():
    return {"schema_version":2,"active_domain":DEFAULT_DOMAIN_ID,"domains":{item.id:{"design_manufacturer":DEFAULT_DESIGN_MANUFACTURER.get(item.id,""),"substitution_manufacturer":DEFAULT_SUBSTITUTION_MANUFACTURER.get(item.id,"")} for item in DOMAINS}}
def normalize_platform_state(raw):
    result=default_platform_state()
    if not isinstance(raw,dict):return result
    active=str(raw.get("active_domain","") or "").strip()
    if any(x.id==active for x in DOMAINS):result["active_domain"]=active
    src=raw.get("domains") if isinstance(raw.get("domains"),dict) else {}
    for spec in DOMAINS:
        part=src.get(spec.id) if isinstance(src,dict) else None
        if not isinstance(part,dict):continue
        for key in ("design_manufacturer","substitution_manufacturer"):
            cand=str(part.get(key,"") or "").strip()
            if cand and any(m.id==cand for m in spec.manufacturers):result["domains"][spec.id][key]=cand
    return result
