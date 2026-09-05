from __future__ import annotations

import base64
import lzma
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parts = sorted((ROOT / "tools").glob("build_v118_payload.part*"))
if not parts:
    raise RuntimeError("Chybí build payload pro v1.1.8")
payload = "".join(path.read_text(encoding="ascii").strip() for path in parts)
code = lzma.decompress(base64.b85decode(payload.encode("ascii"))).decode("utf-8")

# WU musí být rozpoznáno před obecným tokenem WD, jinak zápis „WU WD280“
# zachytí pouze WD280 a ztratí se vazba na HIT MVX-OU280.
old = '''    new_geometry = \'\'\'    if not match:
        match = re.search(r"(?:^|[-\\\\s])(WU|OU|OD|WD|WO|HVS|WOS|BHS|WUS|BH)\\\\s*(\\\\d{2,4})(?=[-\\\\s]|$)", combined, flags=re.I)
    if not match:
        # ISOPRO 120 zapisuje např. ``WU WD 220``; pro HIT jde o OU s bx = WD.
        match = re.search(r"(?:^|[-\\\\s])(WU)\\\\s+(?:WD\\\\s*)?(\\\\d{2,4})(?=[-\\\\s]|$)", combined, flags=re.I)
    if not match:
        return "", None, "", []
\'\'\'
'''
new = '''    new_geometry = \'\'\'    if not match:
        # ISOPRO 120 zapisuje např. ``WU WD 220``; pro HIT jde o OU s bx = WD.
        match = re.search(r"(?:^|[-\\\\s])(WU)\\\\s+(?:WD\\\\s*)?(\\\\d{2,4})(?=[-\\\\s]|$)", combined, flags=re.I)
    if not match:
        match = re.search(r"(?:^|[-\\\\s])(WU|OU|OD|WD|WO|HVS|WOS|BHS|WUS|BH)\\\\s*(\\\\d{2,4})(?=[-\\\\s]|$)", combined, flags=re.I)
    if not match:
        return "", None, "", []
\'\'\'
'''
if code.count(old) != 1:
    raise RuntimeError(f"Neočekávaný počet WU patchů: {code.count(old)}")
code = code.replace(old, new, 1)

# Oficiální označení A a Z ISO se ve výkazech běžně uvádí i s R90 / FP1.
alias_patches = (
    (
        'extra_aliases=[f"IP120 A{level} b{b} h{h}",f"IP120 A {level} b{b}"],notes=',
        'extra_aliases=[f"IP120 A{level} b{b} h{h}",f"IP120 A{level} b{b} h{h} R90",f"IP120 A {level} b{b}"],notes=',
    ),
    (
        'extra_aliases=[f"IP120 Z ISO h{h}",des+" FP1"]))',
        'extra_aliases=[f"IP120 Z ISO h{h}",f"IP120 Z ISO h{h} FP1",des+" FP1"]))',
    ),
)
for alias_old, alias_new in alias_patches:
    if code.count(alias_old) != 1:
        raise RuntimeError(f"Neočekávaný počet alias patchů: {code.count(alias_old)}")
    code = code.replace(alias_old, alias_new, 1)

# Více textových aliasů stejného záznamu se po normalizaci může slít do
# stejného klíče. Před vyhodnocením přesné shody je proto deduplikujeme podle
# skutečného katalogového záznamu; nejde o slučování odlišných výrobků.
main_old = '''    substitution = OUT / "substitution_workspace.py"
    substitution.write_text(patch_substitution(substitution.read_text(encoding="utf-8")), encoding="utf-8")

    package = build_package()
'''
main_new = '''    substitution = OUT / "substitution_workspace.py"
    substitution.write_text(patch_substitution(substitution.read_text(encoding="utf-8")), encoding="utf-8")

    catalog_engine = OUT / "catalog_engine.py"
    catalog_source = catalog_engine.read_text(encoding="utf-8")
    catalog_source = replace_once(
        catalog_source,
        "        exact = list(self._designation_index.get(key, []))\\n",
        "        exact = list({(id(f), id(r)): (f, r) for f, r in self._designation_index.get(key, [])}.values())\\n",
        "deduplicate exact designation aliases",
    )
    catalog_engine.write_text(catalog_source, encoding="utf-8")

    package = build_package()
'''
if code.count(main_old) != 1:
    raise RuntimeError(f"Neočekávaný počet main patchů: {code.count(main_old)}")
code = code.replace(main_old, main_new, 1)

exec(compile(code, __file__ + "<payload>", "exec"), {"__name__": __name__, "__file__": __file__})
