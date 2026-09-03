from __future__ import annotations

import hashlib
import json
import py_compile
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.0"
OUT = ROOT / "updates" / "0.6.1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    text = fn(text)
    path.write_text(text, encoding="utf-8")


def patch_app(s: str) -> str:
    s = replace_once(s, 'APP_VERSION = "0.6.0"', 'APP_VERSION = "0.6.1"', "app version")

    s = replace_once(
        s,
        "            preferred_catalog_getter=self._autocomplete_preferred_catalog,\n            limit=10,",
        "            preferred_catalog_getter=self._autocomplete_preferred_catalog,\n            preferred_concrete_getter=self._autocomplete_preferred_concrete,\n            limit=10,",
        "lookup autocomplete concrete getter",
    )

    old = '''    def _cascade_from_moment(self, preferred_concrete: str | None = None, preferred_shear: str | None = None) -> None:\n        try:\n            family = self.current_family()\n            concrete_values = self.database.concrete_classes(family, self.moment_var.get())\n        except (SelectionError, KeyError):\n            concrete_values = []\n        self._set_combo_values(self.combos["concrete"], self.concrete_var, concrete_values, preferred_concrete)\n        self._cascade_from_concrete(preferred_shear=preferred_shear)\n'''
    new = '''    def _cascade_from_moment(self, preferred_concrete: str | None = None, preferred_shear: str | None = None) -> None:\n        try:\n            family = self.current_family()\n            concrete_values = self.database.concrete_classes(family, self.moment_var.get())\n        except (SelectionError, KeyError):\n            concrete_values = []\n        concrete_texts = [str(value) for value in concrete_values]\n        target_concrete = preferred_concrete\n        if target_concrete is None and hasattr(self, "project_concrete_var"):\n            candidate = self.project_concrete_var.get().strip()\n            if candidate in concrete_texts:\n                target_concrete = candidate\n        if target_concrete is None and "C25/30" in concrete_texts:\n            target_concrete = "C25/30"\n        self._set_combo_values(self.combos["concrete"], self.concrete_var, concrete_values, target_concrete)\n        self._cascade_from_concrete(preferred_shear=preferred_shear)\n'''
    s = replace_once(s, old, new, "default project concrete cascade")

    old = '''    def _autocomplete_preferred_catalog(self) -> str | None:\n        try:\n            return self.current_catalog_id()\n        except Exception:\n            return None\n\n    def _on_lookup_suggestion_chosen(self, result: QueryResult) -> None:\n'''
    new = '''    def _autocomplete_preferred_catalog(self) -> str | None:\n        try:\n            return self.current_catalog_id()\n        except Exception:\n            return None\n\n    def _autocomplete_preferred_concrete(self) -> str | None:\n        if hasattr(self, "project_concrete_var"):\n            value = self.project_concrete_var.get().strip()\n            if value:\n                return value\n        return "C25/30"\n\n    def _on_lookup_suggestion_chosen(self, result: QueryResult) -> None:\n'''
    s = replace_once(s, old, new, "preferred concrete helper")

    s = replace_once(
        s,
        "            result=self.database.resolve_designation(text,preferred_catalog_id=preferred)\n",
        "            result=self.database.resolve_designation(text, preferred_catalog_id=preferred, preferred_concrete=self._autocomplete_preferred_concrete())\n",
        "quick resolve preferred concrete",
    )
    return s


def patch_autocomplete(s: str) -> str:
    s = replace_once(
        s,
        "        preferred_catalog_getter: Callable[[], str | None] | None = None,\n        limit: int = 10,",
        "        preferred_catalog_getter: Callable[[], str | None] | None = None,\n        preferred_concrete_getter: Callable[[], str | None] | None = None,\n        limit: int = 10,",
        "autocomplete signature",
    )
    s = replace_once(
        s,
        "        self.preferred_catalog_getter = preferred_catalog_getter\n        self.limit = max(4, int(limit))",
        "        self.preferred_catalog_getter = preferred_catalog_getter\n        self.preferred_concrete_getter = preferred_concrete_getter\n        self.limit = max(4, int(limit))",
        "autocomplete assignment",
    )
    old = '''    def _preferred_catalog(self) -> str | None:\n        if self.preferred_catalog_getter is None:\n            return None\n        try:\n            return self.preferred_catalog_getter()\n        except Exception:\n            return None\n\n    def refresh(self) -> None:\n'''
    new = '''    def _preferred_catalog(self) -> str | None:\n        if self.preferred_catalog_getter is None:\n            return None\n        try:\n            return self.preferred_catalog_getter()\n        except Exception:\n            return None\n\n    def _preferred_concrete(self) -> str | None:\n        if self.preferred_concrete_getter is None:\n            return None\n        try:\n            value = self.preferred_concrete_getter()\n            return str(value).strip() if value else None\n        except Exception:\n            return None\n\n    def refresh(self) -> None:\n'''
    s = replace_once(s, old, new, "autocomplete preferred concrete method")
    s = replace_once(
        s,
        "        preferred = self._preferred_catalog()\n",
        "        preferred = self._preferred_catalog()\n        preferred_concrete = self._preferred_concrete()\n",
        "autocomplete refresh preferred concrete",
    )
    s = replace_once(
        s,
        "            exact = self.database.resolve_designation(text, preferred_catalog_id=preferred)\n",
        "            exact = self.database.resolve_designation(text, preferred_catalog_id=preferred, preferred_concrete=preferred_concrete)\n",
        "autocomplete exact resolve",
    )
    s = replace_once(
        s,
        "            text, preferred_catalog_id=preferred, limit=self.limit\n",
        "            text, preferred_catalog_id=preferred, preferred_concrete=preferred_concrete, limit=self.limit\n",
        "autocomplete suggestions",
    )
    return s


def patch_engine(s: str) -> str:
    s = replace_once(
        s,
        '    text = str(text).upper().replace("SCHÖCK", "SCHOCK").replace("ISOKORB®", "ISOKORB").replace("ISOPRO®", "ISOPRO")\n',
        '    text = str(text).replace("+/-", "±").replace("+-", "±").replace("-+", "±")\n    text = text.upper().replace("SCHÖCK", "SCHOCK").replace("ISOKORB®", "ISOKORB").replace("ISOPRO®", "ISOPRO")\n',
        "plus-minus normalization",
    )
    s = replace_once(
        s,
        "    def _matrix_suggestions(self, text: str, preferred_catalog_id: str | None, limit: int) -> list[DesignationSuggestion]:",
        "    def _matrix_suggestions(self, text: str, preferred_catalog_id: str | None, limit: int, preferred_concrete: str | None = None) -> list[DesignationSuggestion]:",
        "matrix suggestions signature",
    )
    s = replace_once(
        s,
        '                    concretes=sorted(concretes,key=lambda c:(0 if c=="C25/30" else 1,natural_key(c)))[:2]\n',
        '                    concretes=sorted(concretes,key=lambda c:(0 if preferred_concrete and c==preferred_concrete else 1, 0 if c=="C25/30" else 1, natural_key(c)))[:2]\n',
        "matrix concrete priority",
    )
    s = replace_once(
        s,
        "    def suggest_designations(self, text: str, preferred_catalog_id: str | None = None,\n                             limit: int = 12) -> list[DesignationSuggestion]:",
        "    def suggest_designations(self, text: str, preferred_catalog_id: str | None = None,\n                             preferred_concrete: str | None = None, limit: int = 12) -> list[DesignationSuggestion]:",
        "suggestions signature",
    )
    s = replace_once(
        s,
        "            score *= catalog_factor\n            ranked.append((score, idx))",
        "            if preferred_concrete:\n                record_concrete = str(entry.get(\"record\", {}).get(\"concrete_min\", \"\"))\n                score += 12.0 if record_concrete == str(preferred_concrete) else -3.0\n            score *= catalog_factor\n            ranked.append((score, idx))",
        "suggestion concrete score",
    )
    s = replace_once(
        s,
        "        matrix = self._matrix_suggestions(raw, preferred_catalog_id, limit)\n",
        "        matrix = self._matrix_suggestions(raw, preferred_catalog_id, limit, preferred_concrete=preferred_concrete)\n",
        "matrix suggestions call",
    )
    s = replace_once(
        s,
        "    def resolve_designation(self, text: str, preferred_catalog_id: str | None = None) -> QueryResult:\n",
        "    def resolve_designation(self, text: str, preferred_catalog_id: str | None = None, preferred_concrete: str | None = None) -> QueryResult:\n",
        "resolve signature",
    )
    s = replace_once(
        s,
        '''        if preferred_catalog_id:\n            exact_pref=[x for x in exact if str(x[0]["catalog_id"])==str(preferred_catalog_id)]\n            if exact_pref: exact=exact_pref\n        if len(exact)==1:\n''',
        '''        if preferred_catalog_id:\n            exact_pref=[x for x in exact if str(x[0]["catalog_id"])==str(preferred_catalog_id)]\n            if exact_pref: exact=exact_pref\n        if preferred_concrete:\n            concrete_pref=[x for x in exact if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n            if concrete_pref: exact=concrete_pref\n        if len(exact)==1:\n''',
        "resolve exact concrete filter",
    )
    s = replace_once(
        s,
        "        for suggestion in self._matrix_suggestions(text, preferred_catalog_id, 20):\n",
        "        for suggestion in self._matrix_suggestions(text, preferred_catalog_id, 20, preferred_concrete=preferred_concrete):\n",
        "resolve matrix concrete",
    )
    s = replace_once(
        s,
        '''        if preferred_catalog_id:\n            p=[x for x in embedded if str(x[0]["catalog_id"])==str(preferred_catalog_id)]\n            if p: embedded=p\n        unique={(id(f), id(r)):(f,r) for f,r in embedded}\n''',
        '''        if preferred_catalog_id:\n            p=[x for x in embedded if str(x[0]["catalog_id"])==str(preferred_catalog_id)]\n            if p: embedded=p\n        if preferred_concrete:\n            p=[x for x in embedded if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n            if p: embedded=p\n        unique={(id(f), id(r)):(f,r) for f,r in embedded}\n''',
        "embedded concrete filter",
    )
    s = replace_once(
        s,
        '''            if len(recs)==1: return self.result_for_record(*recs[0])\n            if len(recs)>1:\n''',
        '''            if preferred_concrete and not parsed.get("concrete_min"):\n                concrete_recs=[x for x in recs if str(x[1].get("concrete_min", ""))==str(preferred_concrete)]\n                if concrete_recs: recs=concrete_recs\n            if len(recs)==1: return self.result_for_record(*recs[0])\n            if len(recs)>1:\n''',
        "parsed concrete filter",
    )
    return s


def patch_project_model(s: str) -> str:
    s = replace_once(s, "PROJECT_SCHEMA_VERSION = 2", "PROJECT_SCHEMA_VERSION = 3", "project schema version")
    s = replace_once(
        s,
        '    name:str="Nový objekt"; note:str=""; rows:list[dict[str,Any]]=field(default_factory=list)\n',
        '    name:str="Nový objekt"; note:str=""; concrete_class:str="C25/30"; rows:list[dict[str,Any]]=field(default_factory=list)\n',
        "project concrete field",
    )
    s = replace_once(
        s,
        '                             "project":{"id":self.project_id,"name":self.name,"note":self.note,"created_at":self.created_at,"updated_at":self.updated_at},\n',
        '                             "project":{"id":self.project_id,"name":self.name,"note":self.note,"concrete_class":self.concrete_class,"created_at":self.created_at,"updated_at":self.updated_at},\n',
        "project concrete serialization",
    )
    s = replace_once(s, '        if version not in {1,2}:', '        if version not in {1,2,3}:', "project supported schema")
    s = replace_once(
        s,
        '        return cls(name=str(project.get("name","Nový objekt")),note=str(project.get("note","")),rows=[normalize_project_row(r) for r in rows],\n',
        '        return cls(name=str(project.get("name","Nový objekt")),note=str(project.get("note","")),concrete_class=str(project.get("concrete_class","C25/30") or "C25/30"),rows=[normalize_project_row(r) for r in rows],\n',
        "project concrete deserialization",
    )
    return s


def patch_project_ui(s: str) -> str:
    s = replace_once(
        s,
        '        self.project_edit_info_var = tk.StringVar(value="")\n',
        '        self.project_edit_info_var = tk.StringVar(value="")\n        self.project_concrete_var = tk.StringVar(value=getattr(self.project, "concrete_class", "C25/30") or "C25/30")\n',
        "project concrete variable",
    )

    marker = '''    # ---------- sestavení projektové karty ----------\n\n    def _build_project_tab(self, parent: ttk.Frame) -> None:\n'''
    insert = '''    def _available_project_concretes(self) -> list[str]:\n        values: set[str] = set()\n        for family in self.database.families:\n            rows = family.get("moment_rows", []) if family.get("backend") == "matrix" else family.get("records", [])\n            for row in rows:\n                value = str(row.get("concrete_min", "")).strip()\n                if value:\n                    values.add(value)\n        ordered = sorted(values, key=natural_key)\n        if "C25/30" in ordered:\n            ordered.remove("C25/30")\n            ordered.insert(0, "C25/30")\n        return ordered\n\n    # ---------- sestavení projektové karty ----------\n\n    def _build_project_tab(self, parent: ttk.Frame) -> None:\n'''
    s = replace_once(s, marker, insert, "project concrete choices helper")

    old = '''        ttk.Label(project_card, textvariable=self.project_path_var, style="ProjectPath.TLabel").grid(\n            row=1, column=0, columnspan=3, sticky="w", pady=(5, 0)\n        )\n'''
    new = '''        ttk.Label(project_card, textvariable=self.project_path_var, style="ProjectPath.TLabel").grid(\n            row=1, column=0, columnspan=2, sticky="w", pady=(5, 0)\n        )\n        concrete_bar = ttk.Frame(project_card, style="Card.TFrame")\n        concrete_bar.grid(row=1, column=2, sticky="e", pady=(5, 0))\n        ttk.Label(concrete_bar, text="Beton projektu", style="Card.TLabel").pack(side="left", padx=(0, 6))\n        concrete_values = self._available_project_concretes()\n        if self.project_concrete_var.get() not in concrete_values:\n            self.project_concrete_var.set("C25/30" if "C25/30" in concrete_values else (concrete_values[0] if concrete_values else "C25/30"))\n        self.project_concrete_combo = ttk.Combobox(concrete_bar, textvariable=self.project_concrete_var, values=concrete_values, state="readonly", width=10)\n        self.project_concrete_combo.pack(side="left")\n        self.project_concrete_combo.bind("<<ComboboxSelected>>", self._on_project_concrete_changed)\n        ttk.Button(concrete_bar, text="Použít na řádky", command=self.apply_project_concrete_to_rows).pack(side="left", padx=(7, 0))\n'''
    s = replace_once(s, old, new, "project concrete controls")

    s = replace_once(
        s,
        "            preferred_catalog_getter=None,\n            limit=12,",
        "            preferred_catalog_getter=None,\n            preferred_concrete_getter=lambda: self.project_concrete_var.get(),\n            limit=12,",
        "project autocomplete concrete getter",
    )

    marker = '''        self.refresh_project_tree()\n\n    def _build_project_context_menu(self) -> None:\n'''
    insert = '''        self.refresh_project_tree()\n\n    def _on_project_concrete_changed(self, _event: tk.Event[Any] | None = None) -> None:\n        target = self.project_concrete_var.get().strip() or "C25/30"\n        self.project.concrete_class = target\n        self.project.touch()\n        self.mark_project_dirty()\n        try:\n            values = tuple(self.combos["concrete"].cget("values")) if hasattr(self, "combos") else ()\n            if target in values:\n                self.concrete_var.set(target)\n                self._run_cascade(self._cascade_from_concrete)\n        except Exception:\n            pass\n        self.set_status(f"Beton projektu nastaven na {target}. Nové výběry jej budou preferovat.")\n\n    def apply_project_concrete_to_rows(self) -> None:\n        target = self.project_concrete_var.get().strip() or "C25/30"\n        self.project.concrete_class = target\n        if not self.project.rows:\n            self.mark_project_dirty()\n            self.set_status(f"Beton projektu nastaven na {target}.")\n            return\n        if not messagebox.askyesno(\n            "Použít beton na projekt",\n            f"Přepočítat všechny řádky projektu na beton {target}, pokud je pro daný typ v katalogu dostupný?",\n            parent=self,\n        ):\n            return\n        updated = 0\n        skipped: list[str] = []\n        for row in list(self.project.rows):\n            selection = dict(row.get("selection", {}))\n            if str(selection.get("concrete_min", "")) == target:\n                continue\n            selection["concrete_min"] = target\n            try:\n                result = query_from_selection(self.database, selection)\n            except Exception:\n                skipped.append(str(row.get("position", "")) or str(row.get("id", ""))[:8])\n                continue\n            replacement = create_project_row(\n                result,\n                row_id=str(row["id"]),\n                position=str(row.get("position", "")),\n                quantity=int(row.get("quantity", 1)),\n                note=str(row.get("note", "")),\n            )\n            self.project.replace(str(row["id"]), replacement)\n            updated += 1\n        self.mark_project_dirty()\n        self.refresh_project_tree()\n        message = f"Beton projektu: {target}. Přepočítáno {updated} řádků."\n        if skipped:\n            message += f" Beze změny zůstalo {len(skipped)} řádků, kde tato třída není dostupná."\n        self.set_status(message)\n        if skipped:\n            messagebox.showwarning(\n                "Beton projektu",\n                message + "\\n\\nŘádky beze změny: " + ", ".join(skipped[:20]),\n                parent=self,\n            )\n\n    def _build_project_context_menu(self) -> None:\n'''
    s = replace_once(s, marker, insert, "project concrete handlers")

    s = s.replace("result = self.database.resolve_designation(designation)\n", "result = self.database.resolve_designation(designation, preferred_concrete=self.project_concrete_var.get())\n")
    if s.count("preferred_concrete=self.project_concrete_var.get()") < 2:
        raise RuntimeError("Expected quick and bulk project resolve calls to be patched")

    old = '''        try:\n            self.project_name_var.set(document.name)\n            self.project_filter_var.set("")\n        finally:\n'''
    new = '''        try:\n            self.project_name_var.set(document.name)\n            self.project_concrete_var.set(getattr(document, "concrete_class", "C25/30") or "C25/30")\n            self.project_filter_var.set("")\n        finally:\n'''
    s = replace_once(s, old, new, "restore project concrete")
    return s


def patch_updater(s: str) -> str:
    s = s.replace(
        'req = urllib.request.Request(url, headers={"User-Agent": "TURTO-Updater"})',
        'req = urllib.request.Request(url, headers={"User-Agent": "TURTO-Updater", "Cache-Control": "no-cache", "Pragma": "no-cache"})',
    )
    return s


def main() -> None:
    if not BASE.exists():
        raise RuntimeError(f"Base release does not exist: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)
    patch_file(OUT / "autocomplete.py", patch_autocomplete)
    patch_file(OUT / "catalog_engine.py", patch_engine)
    patch_file(OUT / "project_model.py", patch_project_model)
    patch_file(OUT / "project_ui.py", patch_project_ui)
    patch_file(OUT / "updater.py", patch_updater)

    for name in ["app.pyw", "autocomplete.py", "catalog_engine.py", "project_model.py", "project_ui.py", "updater.py"]:
        py_compile.compile(str(OUT / name), doraise=True)

    # Focused regression checks that do not require loading catalog files.
    import importlib.util
    spec = importlib.util.spec_from_file_location("turto_engine_061", OUT / "catalog_engine.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module._normalise("V6+-") == module._normalise("V6±")
    assert module._normalise("V6+/-") == module._normalise("V6±")

    files = [
        "app.pyw",
        "catalog_engine.py",
        "project_model.py",
        "project_ui.py",
        "autocomplete.py",
        "updater.py",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64",
        "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        path = OUT / rel
        data = path.read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.1/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.1",
        "notes": "Beton projektu s výchozí preferencí C25/30 pro všechny výrobce; možnost přepočítat existující řádky na zvolený beton; zápis ± lze zadávat také jako +- nebo +/-. Obsah MAX FRANK z v0.6.0 zůstává zachován.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.1\n"
        "- C25/30 je výchozí beton, pokud je pro zvolený typ dostupný.\n"
        "- Projekt má vlastní volbu Beton projektu.\n"
        "- Tlačítko Použít na řádky bezpečně přepočítá jen dostupné kombinace.\n"
        "- Zápis ± lze psát jako +-, -+ nebo +/-.\n",
        encoding="utf-8",
    )
    print("Built TURTO v0.6.1")
    for item in manifest_files:
        print(item["path"], item["sha256"])


if __name__ == "__main__":
    main()
