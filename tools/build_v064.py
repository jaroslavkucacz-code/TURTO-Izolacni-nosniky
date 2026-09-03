from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.3"
OUT = ROOT / "updates" / "0.6.4"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(fn(text), encoding="utf-8")


def patch_app(s: str) -> str:
    return replace_once(s, 'APP_VERSION = "0.6.3"', 'APP_VERSION = "0.6.4"', "app version")


def patch_engine(s: str) -> str:
    # A-IP / A-IPQ / ... must be parsed even when the user omits the word ISOPRO.
    s = replace_once(
        s,
        '        if "ISOPRO" in n:\n',
        '        if "ISOPRO" in n or re.search(r"\\bA[\\s-]*IP", n):\n',
        "ISOPRO designation detection",
    )

    marker = '''    def _matrix_suggestions(self, text: str, preferred_catalog_id: str | None, limit: int, preferred_concrete: str | None = None) -> list[DesignationSuggestion]:\n'''
    helper = '''    def _structured_record_suggestions(self, text: str, preferred_catalog_id: str | None,\n                                       preferred_concrete: str | None, limit: int) -> list[DesignationSuggestion]:\n        """Strict partial matching for designations whose technical selectors are already recognizable.\n\n        Once type + moment are explicitly present, only parameters actually written by the user are\n        constrained. Missing parameters intentionally remain free so the popup offers only the real\n        alternatives for the missing selector (height, shear, cover, generation, ...).\n        """\n        parsed = self.parse_designation(text)\n        if not parsed.get("type") or not parsed.get("moment_class"):\n            return []\n\n        family_fields = ("manufacturer", "model", "type", "generation")\n        record_fields = ("moment_class", "shear_class", "concrete_min", "cover", "height_mm")\n        families = [f for f in self.families if f.get("backend") != "matrix"]\n        for key in family_fields:\n            value = parsed.get(key)\n            if value not in (None, ""):\n                families = [f for f in families if str(f.get(key, "")) == str(value)]\n\n        if preferred_catalog_id:\n            preferred = [f for f in families if str(f.get("catalog_id")) == str(preferred_catalog_id)]\n            if preferred:\n                families = preferred\n\n        matches: list[DesignationSuggestion] = []\n        selector_count = sum(1 for key in (*family_fields, *record_fields) if parsed.get(key) not in (None, ""))\n        for family in families:\n            for record in family.get("records", []):\n                if preferred_concrete and str(record.get("concrete_min", "")) != str(preferred_concrete):\n                    continue\n                if any(\n                    parsed.get(key) not in (None, "") and str(record.get(key, "")) != str(parsed[key])\n                    for key in record_fields\n                ):\n                    continue\n                matches.append(DesignationSuggestion(self.result_for_record(family, record), 350.0 + 15.0 * selector_count))\n\n        best: dict[str, DesignationSuggestion] = {}\n        for item in matches:\n            key = _normalise(item.designation)\n            if key not in best or item.score > best[key].score:\n                best[key] = item\n        return sorted(best.values(), key=lambda x: natural_key(x.designation))[:limit]\n\n''' + marker
    s = replace_once(s, marker, helper, "structured partial suggestion helper")

    old = '''            products = self.moment_classes(fam)\n            if not products: continue\n            product_rank=[]\n'''
    new = '''            products = self.moment_classes(fam)\n            if not products: continue\n            explicit_product_compacts = {\n                self._suggestion_compact(p) for p in products\n                if self._suggestion_compact(p) in q_tokens\n            }\n            if explicit_product_compacts:\n                products = [p for p in products if self._suggestion_compact(p) in explicit_product_compacts]\n                if not products:\n                    continue\n            product_rank=[]\n'''
    s = replace_once(s, old, new, "matrix explicit product restriction")

    old = '''            chosen_products=[p for ps,p in product_rank if ps>=48][:4]\n            if not chosen_products:\n                # For broad family query show a few representative product levels rather than every height.\n                chosen_products=products[:3]\n'''
    new = '''            if explicit_product_compacts:\n                chosen_products = products\n            else:\n                chosen_products=[p for ps,p in product_rank if ps>=48][:4]\n                if not chosen_products:\n                    # For broad family query show a few representative product levels rather than every height.\n                    chosen_products=products[:3]\n'''
    s = replace_once(s, old, new, "matrix exact product choice")

    old = '''                    # Match any typed shear token exactly/compactly; otherwise provide a few distinct options.\n                    matched_s=[sc for sc in shears if self._suggestion_compact(sc) in q_tokens or self._suggestion_compact(sc) in compact]\n                    use_s=matched_s[:3] if matched_s else shears[:3]\n'''
    new = '''                    # If shear is written explicitly, keep only that shear selector.\n                    n_no_space = re.sub(r"\\s+", "", n)\n                    strong_s = [sc for sc in shears if re.sub(r"\\s+", "", _normalise(sc)) in n_no_space]\n                    matched_s = strong_s or [sc for sc in shears if self._suggestion_compact(sc) in q_tokens]\n                    use_s=matched_s[:3] if matched_s else shears[:3]\n'''
    s = replace_once(s, old, new, "matrix explicit shear restriction")

    old = '''        raw = str(text or "").strip()\n        if not raw or len(self._suggestion_compact(raw)) < 2:\n            return []\n        q_tokens = self._suggestion_tokens(raw)\n'''
    new = '''        raw = str(text or "").strip()\n        if not raw or len(self._suggestion_compact(raw)) < 2:\n            return []\n\n        parsed = self.parse_designation(raw)\n        if preferred_concrete and parsed.get("concrete_min") and str(parsed.get("concrete_min")) != str(preferred_concrete):\n            return []\n\n        # Exact designation or alias: do not clutter the popup with merely similar products.\n        exact_pairs = list(self._designation_index.get(_normalise(raw), []))\n        if preferred_catalog_id:\n            preferred_pairs = [x for x in exact_pairs if str(x[0].get("catalog_id")) == str(preferred_catalog_id)]\n            if preferred_pairs:\n                exact_pairs = preferred_pairs\n        if preferred_concrete:\n            exact_pairs = [x for x in exact_pairs if str(x[1].get("concrete_min", "")) == str(preferred_concrete)]\n        if exact_pairs:\n            exact_out: list[DesignationSuggestion] = []\n            seen_exact: set[str] = set()\n            for family, record in exact_pairs:\n                item = DesignationSuggestion(self.result_for_record(family, record), 1000.0)\n                key = _normalise(item.designation)\n                if key not in seen_exact:\n                    seen_exact.add(key)\n                    exact_out.append(item)\n            if exact_out:\n                return exact_out[:limit]\n\n        # Recognizable partial designation: vary only selectors the user did NOT specify.\n        structured = self._structured_record_suggestions(raw, preferred_catalog_id, preferred_concrete, limit)\n        if structured:\n            return structured[:limit]\n\n        q_tokens = self._suggestion_tokens(raw)\n'''
    s = replace_once(s, old, new, "specificity-aware suggestion fast path")
    return s


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)
    patch_file(OUT / "catalog_engine.py", patch_engine)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.4\n"
        "- Našeptávač respektuje všechny parametry, které jsou už v názvu zadané.\n"
        "- Pokud typ + moment + smyk + krytí + výška určují konkrétní prvek, nezobrazuje jiné typy.\n"
        "- Pokud některý parametr chybí, nabízejí se pouze skutečné varianty tohoto chybějícího parametru.\n"
        "- Beton projektu zůstává striktním filtrem.\n",
        encoding="utf-8",
    )

    for name in ["app.pyw", "autocomplete.py", "catalog_engine.py", "project_model.py", "project_ui.py", "updater.py"]:
        py_compile.compile(str(OUT / name), doraise=True)

    import sys
    sys.path.insert(0, str(OUT))
    import catalog_engine as engine

    db = engine.CatalogDatabase(OUT / "catalogs")

    # Full Schöck designation must collapse to the specified technical combination only.
    full_schock = db.suggest_designations(
        "XT typ KL-M8-V2-CV1-H220-6.2", preferred_concrete="C25/30", limit=12
    )
    assert full_schock, "No Schöck suggestions"
    assert all(str(x.result.family.get("model")) == "XT" for x in full_schock)
    assert all(str(x.result.family.get("type")) == "KL" for x in full_schock)
    assert all(str(x.result.record.get("moment_class")) == "M8" for x in full_schock)
    assert all(str(x.result.record.get("shear_class")) == "V2" for x in full_schock)
    assert all(str(x.result.record.get("cover")) == "CV1" for x in full_schock)
    assert all(str(x.result.record.get("height_mm")) == "220" for x in full_schock)
    assert all(str(x.result.record.get("concrete_min")) == "C25/30" for x in full_schock)

    # Missing height may vary height, but not type/moment/shear/cover.
    partial_schock = db.suggest_designations(
        "XT typ KL-M8-V2-CV1-6.2", preferred_concrete="C25/30", limit=12
    )
    assert partial_schock, "No partial Schöck suggestions"
    assert all(str(x.result.family.get("type")) == "KL" for x in partial_schock)
    assert all(str(x.result.record.get("moment_class")) == "M8" for x in partial_schock)
    assert all(str(x.result.record.get("shear_class")) == "V2" for x in partial_schock)
    assert all(str(x.result.record.get("cover")) == "CV1" for x in partial_schock)

    # MAX FRANK: an explicit product level must never fall back to other product levels.
    full_mxl = db.suggest_designations(
        "MXL20 V6+- C30 h200", preferred_concrete="C25/30", limit=12
    )
    assert full_mxl, "No MXL20 suggestions"
    assert all(str(x.result.record.get("moment_class")) == "MXL20" for x in full_mxl)
    assert all(str(x.result.record.get("height_mm")) == "200" for x in full_mxl)
    assert all(str(x.result.record.get("concrete_min")) == "C25/30" for x in full_mxl)

    partial_mxl = db.suggest_designations(
        "MXL20 V6+- C30", preferred_concrete="C25/30", limit=12
    )
    assert partial_mxl, "No partial MXL20 suggestions"
    assert all(str(x.result.record.get("moment_class")) == "MXL20" for x in partial_mxl)
    assert all(str(x.result.record.get("concrete_min")) == "C25/30" for x in partial_mxl)

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.4/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.4",
        "notes": (
            "Přesnější našeptávač: zadané parametry (typ, moment, smyk, krytí, výška, generace) "
            "jsou nyní závazné a program nabízí pouze varianty parametrů, které v názvu skutečně chybí. "
            "Beton projektu zůstává striktním filtrem."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("v0.6.4 OK; specificity-aware designation filtering verified")


if __name__ == "__main__":
    main()
