from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "updates" / "1.1.2"))
from catalog_engine import CatalogDatabase

catalog_dir = ROOT / "updates" / "1.1.2" / "catalogs"
db = CatalogDatabase(catalog_dir)
print("FAMILIES", len(db.families))
for fam in db.families:
    manufacturer = str(fam.get("manufacturer", ""))
    if "FRANK" not in manufacturer.upper():
        continue
    print("\nFAMILY", {k: fam.get(k) for k in fam if any(x in k.lower() for x in ("manufacturer", "model", "type", "length", "width", "compress", "backend"))})
    for container_name in ("records", "moment_rows", "shear_rows"):
        rows = fam.get(container_name, [])
        print(container_name, "count", len(rows))
        for row in rows[:3]:
            interesting = {k: row.get(k) for k in row if any(x in k.lower() for x in ("designation", "moment_class", "shear_class", "length", "width", "compress", "cover", "height", "insulation", "result"))}
            print(interesting)
