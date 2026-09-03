from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.2"
OUT = ROOT / "updates" / "0.6.3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(fn(text), encoding="utf-8")


def patch_app(s: str) -> str:
    s = replace_once(s, 'APP_VERSION = "0.6.2"', 'APP_VERSION = "0.6.3"', "app version")

    marker = '''    def current_family(self) -> dict[str, Any]:\n        return self.database.get_family(\n            self.current_catalog_id(),\n            self.manufacturer_var.get(),\n            self.model_var.get(),\n            self.type_var.get(),\n            self.generation_var.get(),\n        )\n\n'''
    insert = marker + '''    def _project_concrete_class(self) -> str:\n        if hasattr(self, "project_concrete_var"):\n            value = self.project_concrete_var.get().strip()\n            if value:\n                return value\n        return "C25/30"\n\n    @staticmethod\n    def _family_supports_concrete(family: dict[str, Any], concrete: str) -> bool:\n        rows = family.get("moment_rows", []) if family.get("backend") == "matrix" else family.get("records", [])\n        return any(str(row.get("concrete_min", "")) == str(concrete) for row in rows)\n\n    def _filtered_families(self, *, catalog_id: str | None = None, manufacturer: str | None = None,\n                           model: str | None = None, type_name: str | None = None) -> list[dict[str, Any]]:\n        target = self._project_concrete_class()\n        out: list[dict[str, Any]] = []\n        for family in self.database.families:\n            if catalog_id is not None and str(family.get("catalog_id")) != str(catalog_id):\n                continue\n            if manufacturer is not None and str(family.get("manufacturer")) != str(manufacturer):\n                continue\n            if model is not None and str(family.get("model")) != str(model):\n                continue\n            if type_name is not None and str(family.get("type")) != str(type_name):\n                continue\n            if self._family_supports_concrete(family, target):\n                out.append(family)\n        return out\n\n    def refresh_project_concrete_filter(self) -> None:\n        previous = self._updating\n        self._updating = True\n        try:\n            families = self._filtered_families()\n            manufacturers = sorted({str(f["manufacturer"]) for f in families}, key=natural_key)\n            preferred = self.manufacturer_var.get() or ("Schöck" if "Schöck" in manufacturers else None)\n            self._set_combo_values(self.combos["manufacturer"], self.manufacturer_var, manufacturers, preferred)\n            self._cascade_from_manufacturer()\n        finally:\n            self._updating = previous\n        self.refresh_result()\n\n'''
    s = replace_once(s, marker, insert, "strict concrete helper methods")

    old = '''    def _populate_initial_data(self) -> None:\n        self._updating = True\n        try:\n            self._set_combo_values(\n                self.combos["manufacturer"],\n                self.manufacturer_var,\n                self.database.manufacturers(),\n                "Schöck",\n            )\n            self._cascade_from_manufacturer()\n        finally:\n            self._updating = False\n'''
    new = '''    def _populate_initial_data(self) -> None:\n        self._updating = True\n        try:\n            families = self._filtered_families()\n            manufacturers = sorted({str(f["manufacturer"]) for f in families}, key=natural_key)\n            preferred = "Schöck" if "Schöck" in manufacturers else (manufacturers[0] if manufacturers else None)\n            self._set_combo_values(self.combos["manufacturer"], self.manufacturer_var, manufacturers, preferred)\n            self._cascade_from_manufacturer()\n        finally:\n            self._updating = False\n'''
    s = replace_once(s, old, new, "initial manufacturer strict filter")

    old = '''    def _cascade_from_manufacturer(self, preferred_catalog_id: str | None = None) -> None:\n        manufacturer = self.manufacturer_var.get()\n        catalogs = self.database.catalogs_for(manufacturer)\n        self.catalog_display_to_id.clear()\n        self.catalog_id_to_display.clear()\n        displays: list[str] = []\n        newest_id = self.database.newest_catalog_id(manufacturer)\n'''
    new = '''    def _cascade_from_manufacturer(self, preferred_catalog_id: str | None = None) -> None:\n        manufacturer = self.manufacturer_var.get()\n        supported_ids = {str(f["catalog_id"]) for f in self._filtered_families(manufacturer=manufacturer)}\n        catalogs = [c for c in self.database.catalogs_for(manufacturer) if str(c["id"]) in supported_ids]\n        self.catalog_display_to_id.clear()\n        self.catalog_id_to_display.clear()\n        displays: list[str] = []\n        newest_id = str(catalogs[0]["id"]) if catalogs else None\n'''
    s = replace_once(s, old, new, "catalog strict filter")

    old = '''    def _cascade_from_catalog(self, preferred_model: str | None = None) -> None:\n        catalog_id = self.current_catalog_id() if self.catalog_var.get() else ""\n        values = self.database.models(catalog_id, self.manufacturer_var.get()) if catalog_id else []\n        self._set_combo_values(self.combos["model"], self.model_var, values, preferred_model)\n        self._cascade_from_model()\n'''
    new = '''    def _cascade_from_catalog(self, preferred_model: str | None = None) -> None:\n        catalog_id = self.current_catalog_id() if self.catalog_var.get() else ""\n        families = self._filtered_families(catalog_id=catalog_id, manufacturer=self.manufacturer_var.get()) if catalog_id else []\n        values = sorted({str(f["model"]) for f in families}, key=natural_key)\n        self._set_combo_values(self.combos["model"], self.model_var, values, preferred_model)\n        self._cascade_from_model()\n'''
    s = replace_once(s, old, new, "model strict filter")

    old = '''    def _cascade_from_model(self, preferred_type: str | None = None) -> None:\n        try:\n            values = self.database.types(self.current_catalog_id(), self.manufacturer_var.get(), self.model_var.get())\n        except SelectionError:\n            values = []\n        self._set_combo_values(self.combos["type"], self.type_var, values, preferred_type)\n        self._cascade_from_type()\n'''
    new = '''    def _cascade_from_model(self, preferred_type: str | None = None) -> None:\n        try:\n            families = self._filtered_families(catalog_id=self.current_catalog_id(), manufacturer=self.manufacturer_var.get(), model=self.model_var.get())\n            values = sorted({str(f["type"]) for f in families}, key=natural_key)\n        except SelectionError:\n            values = []\n        self._set_combo_values(self.combos["type"], self.type_var, values, preferred_type)\n        self._cascade_from_type()\n'''
    s = replace_once(s, old, new, "type strict filter")

    old = '''    def _cascade_from_type(self, preferred_generation: str | None = None) -> None:\n        try:\n            values = self.database.generations(\n                self.current_catalog_id(),\n                self.manufacturer_var.get(),\n                self.model_var.get(),\n                self.type_var.get(),\n            )\n        except SelectionError:\n            values = []\n        self._set_combo_values(self.combos["generation"], self.generation_var, values, preferred_generation)\n        self._cascade_from_generation()\n'''
    new = '''    def _cascade_from_type(self, preferred_generation: str | None = None) -> None:\n        try:\n            families = self._filtered_families(\n                catalog_id=self.current_catalog_id(), manufacturer=self.manufacturer_var.get(),\n                model=self.model_var.get(), type_name=self.type_var.get(),\n            )\n            values = sorted({str(f["generation"]) for f in families}, key=natural_key, reverse=True)\n        except SelectionError:\n            values = []\n        self._set_combo_values(self.combos["generation"], self.generation_var, values, preferred_generation)\n        self._cascade_from_generation()\n'''
    s = replace_once(s, old, new, "generation strict filter")

    old = '''    def _cascade_from_generation(self, preferred_moment: str | None = None) -> None:\n        try:\n            family = self.current_family()\n            values = self.database.moment_classes(family)\n        except (SelectionError, KeyError):\n            values = []\n        self._set_combo_values(self.combos["moment"], self.moment_var, values, preferred_moment)\n        self._cascade_from_moment()\n'''
    new = '''    def _cascade_from_generation(self, preferred_moment: str | None = None) -> None:\n        try:\n            family = self.current_family()\n            target = self._project_concrete_class()\n            values = [m for m in self.database.moment_classes(family) if target in self.database.concrete_classes(family, m)]\n        except (SelectionError, KeyError):\n            values = []\n        self._set_combo_values(self.combos["moment"], self.moment_var, values, preferred_moment)\n        self._cascade_from_moment()\n'''
    s = replace_once(s, old, new, "moment strict filter")

    old = '''    def _cascade_from_moment(self, preferred_concrete: str | None = None, preferred_shear: str | None = None) -> None:\n        try:\n            family = self.current_family()\n            concrete_values = self.database.concrete_classes(family, self.moment_var.get())\n        except (SelectionError, KeyError):\n            concrete_values = []\n        concrete_texts = [str(value) for value in concrete_values]\n        target_concrete = preferred_concrete\n        if target_concrete is None and hasattr(self, "project_concrete_var"):\n            candidate = self.project_concrete_var.get().strip()\n            if candidate in concrete_texts:\n                target_concrete = candidate\n        if target_concrete is None and "C25/30" in concrete_texts:\n            target_concrete = "C25/30"\n        self._set_combo_values(self.combos["concrete"], self.concrete_var, concrete_values, target_concrete)\n        self._cascade_from_concrete(preferred_shear=preferred_shear)\n'''
    new = '''    def _cascade_from_moment(self, preferred_concrete: str | None = None, preferred_shear: str | None = None) -> None:\n        target_concrete = self._project_concrete_class()\n        try:\n            family = self.current_family()\n            available = [str(value) for value in self.database.concrete_classes(family, self.moment_var.get())]\n            concrete_values = [target_concrete] if target_concrete in available else []\n        except (SelectionError, KeyError):\n            concrete_values = []\n        self._set_combo_values(self.combos["concrete"], self.concrete_var, concrete_values, target_concrete)\n        self._cascade_from_concrete(preferred_shear=preferred_shear)\n'''
    s = replace_once(s, old, new, "concrete combo strict filter")
    return s


def patch_engine(s: str) -> str:
    old = '''        concrete_match = re.search(r"C\\s*(20|25)\\s*/\\s*(25|30)", n)\n        wanted_concrete = f"C{concrete_match.group(1)}/{concrete_match.group(2)}" if concrete_match else None\n        height_match = re.search(r"\\bH\\s*(\\d{3,4})\\b", n)\n'''
    new = '''        concrete_match = re.search(r"C\\s*(20|25)\\s*/\\s*(25|30)", n)\n        wanted_concrete = f"C{concrete_match.group(1)}/{concrete_match.group(2)}" if concrete_match else None\n        if preferred_concrete:\n            preferred_concrete = str(preferred_concrete)\n            if wanted_concrete and wanted_concrete != preferred_concrete:\n                return []\n            wanted_concrete = preferred_concrete\n        height_match = re.search(r"\\bH\\s*(\\d{3,4})\\b", n)\n'''
    s = replace_once(s, old, new, "matrix strict concrete")

    old = '''        for idx, base in scores.items():\n            entry = self._suggestion_entries[idx]\n            fam = entry["family"]\n            if preferred_catalog_id and str(fam.get("catalog_id")) != str(preferred_catalog_id):\n'''
    new = '''        for idx, base in scores.items():\n            entry = self._suggestion_entries[idx]\n            fam = entry["family"]\n            if preferred_concrete and str(entry.get("record", {}).get("concrete_min", "")) != str(preferred_concrete):\n                continue\n            if preferred_catalog_id and str(fam.get("catalog_id")) != str(preferred_catalog_id):\n'''
    s = replace_once(s, old, new, "record suggestion strict concrete")

    old = '''    def suggestion_hint(self, text: str, preferred_catalog_id: str | None = None, limit: int = 4) -> str:\n        suggestions = self.suggest_designations(text, preferred_catalog_id=preferred_catalog_id, limit=limit)\n'''
    new = '''    def suggestion_hint(self, text: str, preferred_catalog_id: str | None = None, preferred_concrete: str | None = None, limit: int = 4) -> str:\n        suggestions = self.suggest_designations(text, preferred_catalog_id=preferred_catalog_id, preferred_concrete=preferred_concrete, limit=limit)\n'''
    s = replace_once(s, old, new, "strict concrete suggestion hint")

    old = '''        exact = list(self._designation_index.get(key, []))\n        if preferred_catalog_id:\n            exact_pref=[x for x in exact if str(x[0]["catalog_id"])==str(preferred_catalog_id)]\n            if exact_pref: exact=exact_pref\n        if preferred_concrete:\n            concrete_pref=[x for x in exact if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n            if concrete_pref: exact=concrete_pref\n'''
    new = '''        exact = list(self._designation_index.get(key, []))\n        if preferred_catalog_id:\n            exact_pref=[x for x in exact if str(x[0]["catalog_id"])==str(preferred_catalog_id)]\n            if exact_pref: exact=exact_pref\n        if preferred_concrete:\n            concrete_pref=[x for x in exact if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n            if exact and not concrete_pref:\n                found = sorted({str(x[1].get("concrete_min", "")) for x in exact if x[1].get("concrete_min")})\n                raise SelectionError(f"Označení je v databázi pro beton {', '.join(found) or 'jiné třídy'}, ale projekt je nastaven na {preferred_concrete}.")\n            exact=concrete_pref\n'''
    s = replace_once(s, old, new, "exact strict concrete")

    old = '''        if preferred_concrete:\n            p=[x for x in embedded if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n            if p: embedded=p\n        unique={(id(f), id(r)):(f,r) for f,r in embedded}\n'''
    new = '''        if preferred_concrete:\n            embedded=[x for x in embedded if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n        unique={(id(f), id(r)):(f,r) for f,r in embedded}\n'''
    s = replace_once(s, old, new, "embedded strict concrete")

    old = '''        parsed=self.parse_designation(text)\n        if parsed.get("type") and parsed.get("moment_class"):\n'''
    new = '''        parsed=self.parse_designation(text)\n        if preferred_concrete and parsed.get("concrete_min") and str(parsed.get("concrete_min")) != str(preferred_concrete):\n            raise SelectionError(f"V označení je beton {parsed.get('concrete_min')}, ale projekt je nastaven na {preferred_concrete}.")\n        if parsed.get("type") and parsed.get("moment_class"):\n'''
    s = replace_once(s, old, new, "parsed concrete mismatch")

    old = '''            if preferred_concrete and not parsed.get("concrete_min"):\n                concrete_recs=[x for x in recs if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n                if concrete_recs: recs=concrete_recs\n'''
    new = '''            if preferred_concrete:\n                recs=[x for x in recs if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n'''
    s = replace_once(s, old, new, "parsed records strict concrete")

    old_call = "self.suggestion_hint(text, preferred_catalog_id)"
    count = s.count(old_call)
    if count < 3:
        raise RuntimeError(f"suggestion_hint strict forwarding: expected >=3 matches, found {count}")
    s = s.replace(old_call, "self.suggestion_hint(text, preferred_catalog_id, preferred_concrete)")
    return s


def patch_project_ui(s: str) -> str:
    old = '''        try:\n            values = tuple(self.combos["concrete"].cget("values")) if hasattr(self, "combos") else ()\n            if target in values:\n                self.concrete_var.set(target)\n                self._run_cascade(self._cascade_from_concrete)\n        except Exception:\n            pass\n        self.set_status(f"Beton projektu nastaven na {target}. Nové výběry jej budou preferovat.")\n'''
    new = '''        try:\n            if hasattr(self, "refresh_project_concrete_filter"):\n                self.refresh_project_concrete_filter()\n        except Exception:\n            pass\n        self.set_status(f"Beton projektu nastaven na {target}. Databáze i našeptávač zobrazují pouze tento beton.")\n'''
    s = replace_once(s, old, new, "project concrete change full refresh")

    old = '''    def _apply_project_selection_to_lookup(self, selection: dict[str, Any]) -> None:\n        self._updating = True\n'''
    new = '''    def _apply_project_selection_to_lookup(self, selection: dict[str, Any]) -> None:\n        target = self.project_concrete_var.get().strip() or "C25/30"\n        row_concrete = str(selection.get("concrete_min", ""))\n        if row_concrete and row_concrete != target:\n            raise ValueError(f"Řádek používá beton {row_concrete}, ale projekt je nastaven na {target}. Nejprve změňte beton projektu nebo použijte „Použít na řádky“.")\n        self._updating = True\n'''
    s = replace_once(s, old, new, "load row concrete guard")

    old = '''        self.cancel_project_row_edit()\n        self.refresh_project_tree()\n        self._update_project_title()\n'''
    new = '''        self.cancel_project_row_edit()\n        self.refresh_project_tree()\n        if hasattr(self, "refresh_project_concrete_filter"):\n            self.refresh_project_concrete_filter()\n        self._update_project_title()\n'''
    s = replace_once(s, old, new, "project open concrete refresh")
    return s


def patch_updater(s: str) -> str:
    # Keep current updater implementation; only the manifest drives this release.
    return s


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)
    patch_file(OUT / "catalog_engine.py", patch_engine)
    patch_file(OUT / "project_ui.py", patch_project_ui)
    patch_file(OUT / "updater.py", patch_updater)

    for name in ["app.pyw", "autocomplete.py", "catalog_engine.py", "project_model.py", "project_ui.py", "updater.py"]:
        py_compile.compile(str(OUT / name), doraise=True)

    # Regression tests with the corrected MAX FRANK v0.6.2 catalogs.
    import sys
    sys.path.insert(0, str(OUT))
    import catalog_engine as engine

    db = engine.CatalogDatabase(OUT / "catalogs")
    xl_id = "maxfrank-egcobox-xl-eta-19-0046-2022"
    exact = db.query(
        catalog_id=xl_id, manufacturer="MAX FRANK", model="XL", type_name="MXL", generation="ETA-19/0046",
        moment_class="MXL20", concrete_min="C25/30", shear_class="V6±", cover="C30", height_mm="200",
    )
    assert "MXL20" in exact.designation and "V6±" in exact.designation and "C30" in exact.designation and "h200" in exact.designation

    for concrete in ("C25/30", "C20/25"):
        suggestions = db.suggest_designations("MXL20 V6+- C30 h200", preferred_concrete=concrete, limit=12)
        assert suggestions, f"No suggestions for {concrete}"
        assert all(str(x.result.record.get("concrete_min")) == concrete for x in suggestions), concrete
        resolved = db.resolve_designation("MXL20-V6+-C30-h200", preferred_concrete=concrete)
        assert str(resolved.record.get("concrete_min")) == concrete

    try:
        db.resolve_designation("MXL20-V6±-C30-h200 C20/25", preferred_concrete="C25/30")
    except engine.SelectionError:
        pass
    else:
        raise AssertionError("Explicit different concrete must be rejected")

    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    ui_text = (OUT / "project_ui.py").read_text(encoding="utf-8")
    assert 'concrete_values = [target_concrete] if target_concrete in available else []' in app_text
    assert 'Databáze i našeptávač zobrazují pouze tento beton.' in ui_text

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.3/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.3",
        "notes": "Beton projektu je nyní striktní filtr. Našeptávač, rychlé a hromadné vložení i detailní výběr nezobrazují ani nepřijmou varianty jiného betonu. Zachována oprava MAX FRANK MXL20-V6±-C30-h200 a zápis ± také jako +- nebo +/-.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.6.3 OK; strict project concrete filter verified")


if __name__ == "__main__":
    main()
