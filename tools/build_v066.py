from __future__ import annotations

import hashlib
import json
import py_compile
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.5"
OUT = ROOT / "updates" / "0.6.6"
TEMPLATE_ENGINE = ROOT / "tools" / "v066_bulk_import_engine.py"
TEMPLATE_UI = ROOT / "tools" / "v066_bulk_import.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(fn(text), encoding="utf-8")


def patch_app(s: str) -> str:
    return replace_once(s, 'APP_VERSION = "0.6.5"', 'APP_VERSION = "0.6.6"', "app version")


def patch_project_ui(s: str) -> str:
    s = replace_once(
        s,
        "from autocomplete import DesignationAutocomplete\n",
        "from autocomplete import DesignationAutocomplete\nfrom bulk_import import BulkImportDialog\n",
        "bulk import dialog import",
    )
    s = replace_once(
        s,
        'ttk.Button(filebar, text="Hromadné vložení", command=self.bulk_paste_project_rows).grid(row=0, column=5)',
        'ttk.Button(filebar, text="Hromadné vložení z výkazu", command=self.bulk_paste_project_rows).grid(row=0, column=5)',
        "bulk import button label",
    )

    start_marker = "    def bulk_paste_project_rows(self) -> None:\n"
    end_marker = "    # ---------- přenos mezi tabulkou a detailním editorem ----------\n"
    start = s.find(start_marker)
    end = s.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("bulk paste method markers not found")

    method = '''    def bulk_paste_project_rows(self) -> None:\n        dialog = BulkImportDialog(\n            self,\n            database=self.database,\n            colors=self.colors,\n            preferred_concrete=self.project_concrete_var.get(),\n            existing_positions=[str(row.get("position", "")) for row in self.project.rows],\n            start_position=self.project.next_position(),\n        )\n        self.wait_window(dialog)\n        if not dialog.result:\n            return\n\n        added_ids: list[str] = []\n        for imported in dialog.result:\n            result = imported.get("result")\n            if not isinstance(result, QueryResult):\n                continue\n            row = create_project_row(\n                result,\n                position=str(imported.get("position", "")) or self.project.next_position(),\n                quantity=safe_quantity(imported.get("quantity", 1)),\n                note=str(imported.get("note", "")),\n            )\n            self.project.add(row)\n            added_ids.append(str(row["id"]))\n\n        if not added_ids:\n            self.set_status("Z hromadného výkazu nebyl vložen žádný řádek.")\n            return\n        self.mark_project_dirty()\n        self.refresh_project_tree(select_ids=added_ids[-1:])\n        self.set_status(f"Hromadně vloženo {len(added_ids)} zkontrolovaných řádků.")\n\n'''
    return s[:start] + method + s[end:]


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if not TEMPLATE_ENGINE.exists() or not TEMPLATE_UI.exists():
        raise SystemExit("Missing v0.6.6 bulk import templates")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)
    patch_file(OUT / "project_ui.py", patch_project_ui)
    shutil.copy2(TEMPLATE_ENGINE, OUT / "bulk_import_engine.py")
    shutil.copy2(TEMPLATE_UI, OUT / "bulk_import.py")

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.6\n"
        "- Hromadné vložení z Excelu nově používá kontrolní mezikrok před zápisem do projektu.\n"
        "- Úplné nebo jednoznačně doplnitelné typy jsou označeny jako připravené.\n"
        "- Neúplné názvy zobrazí jen skutečně možné katalogové varianty a údaj, který je nutné upřesnit.\n"
        "- Nejednoznačná varianta se nikdy nevloží bez ručního potvrzení.\n"
        "- Vybranou volbu lze hromadně aplikovat na označené kompatibilní řádky.\n"
        "- Podporováno je vložení jednoho sloupce typů i tabulek typ+ks / pozice+typ / pozice+ks+typ+poznámka.\n",
        encoding="utf-8",
    )

    compile_files = [
        "app.pyw", "autocomplete.py", "catalog_engine.py", "project_model.py", "project_ui.py",
        "updater.py", "bulk_import_engine.py", "bulk_import.py",
    ]
    for name in compile_files:
        py_compile.compile(str(OUT / name), doraise=True)

    sys.path.insert(0, str(OUT))
    import catalog_engine as engine
    import bulk_import_engine as bulk

    db = engine.CatalogDatabase(OUT / "catalogs")
    xl_id = "maxfrank-egcobox-xl-eta-19-0046-2022"
    exact_result = db.query(
        catalog_id=xl_id,
        manufacturer="MAX FRANK",
        model="XL",
        type_name="MXL",
        generation="ETA-19/0046",
        moment_class="MXL20",
        concrete_min="C25/30",
        shear_class="V6±",
        cover="C30",
        height_mm="200",
    )

    items, skipped = bulk.analyze_bulk_text(
        db,
        exact_result.designation,
        preferred_concrete="C25/30",
        existing_positions=[],
        start_position="P001",
    )
    assert skipped == 0 and len(items) == 1
    assert items[0].ready and items[0].result is not None
    assert items[0].position == "P001"
    assert str(items[0].result.record.get("concrete_min")) == "C25/30"

    two_col, _ = bulk.analyze_bulk_text(
        db,
        exact_result.designation + "\t3",
        preferred_concrete="C25/30",
        existing_positions=["P001"],
        start_position="P002",
    )
    assert len(two_col) == 1 and two_col[0].ready
    assert two_col[0].quantity == 3 and two_col[0].position == "P002"

    # Najdi reálnou maticovou kombinaci s více výškami a ověř, že bez výšky zůstane žlutá.
    found_partial = False
    for family in db.families:
        if family.get("backend") != "matrix" or str(family.get("manufacturer")) != "MAX FRANK":
            continue
        for moment in db.moment_classes(family):
            concretes = db.concrete_classes(family, moment)
            if "C25/30" not in concretes:
                continue
            for shear in db.shear_classes(family, moment, "C25/30"):
                for cover in db.covers(family, moment, "C25/30", shear):
                    heights = db.heights(family, moment, "C25/30", cover, shear)
                    if len(heights) < 2:
                        continue
                    result = db.query(
                        catalog_id=str(family["catalog_id"]),
                        manufacturer=str(family["manufacturer"]),
                        model=str(family["model"]),
                        type_name=str(family["type"]),
                        generation=str(family["generation"]),
                        moment_class=str(moment),
                        concrete_min="C25/30",
                        shear_class=str(shear),
                        cover=str(cover),
                        height_mm=str(heights[0]),
                    )
                    aliases = result.record.get("aliases", [])
                    if not aliases:
                        continue
                    partial = re.sub(r"-h\\d+", "", str(aliases[0]), flags=re.I)
                    suggestions = bulk.dedupe_suggestions(
                        db.suggest_designations(partial, preferred_concrete="C25/30", limit=80)
                    )
                    if len(suggestions) < 2:
                        continue
                    partial_items, _ = bulk.analyze_bulk_text(
                        db,
                        partial,
                        preferred_concrete="C25/30",
                        existing_positions=[],
                        start_position="P001",
                    )
                    assert len(partial_items) == 1
                    assert partial_items[0].status == "review"
                    assert "height_mm" in partial_items[0].varying_keys
                    assert all(str(x.result.record.get("concrete_min")) == "C25/30" for x in partial_items[0].candidates)
                    found_partial = True
                    break
                if found_partial:
                    break
            if found_partial:
                break
        if found_partial:
            break
    assert found_partial, "No real MAX FRANK partial-height bulk-import test case found"

    project_ui_text = (OUT / "project_ui.py").read_text(encoding="utf-8")
    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    assert "from bulk_import import BulkImportDialog" in project_ui_text
    assert 'text="Hromadné vložení z výkazu"' in project_ui_text
    assert "dialog = BulkImportDialog(" in project_ui_text
    assert 'APP_VERSION = "0.6.6"' in app_text

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.6/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.6",
        "notes": (
            "Hromadné vložení z výkazu nyní nejprve analyzuje všechny řádky. Jednoznačné typy připraví automaticky, "
            "neúplné označí k doplnění a nabídne pouze kompatibilní katalogové varianty. Nejednoznačný řádek se bez "
            "potvrzení nevloží; stejnou volbu lze použít na více označených kompatibilních řádků."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("v0.6.6 OK; reviewed bulk import and strict concrete filtering verified")


if __name__ == "__main__":
    main()
