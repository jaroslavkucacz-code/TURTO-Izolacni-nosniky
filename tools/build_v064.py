from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from collections import defaultdict
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
    marker = '''    def _matrix_suggestions(self, text: str, preferred_catalog_id: str | None, limit: int, preferred_concrete: str | None = None) -> list[DesignationSuggestion]:\n'''
    helper = '''    def _explicit_selector_constraints(self, text: str) -> dict[str, set[str]]:\n        """Catalog-driven selectors that are explicitly present in the typed designation."""\n        n = _normalise(text)\n        q_tokens = set(self._suggestion_tokens(text))\n        constraints: dict[str, set[str]] = {}\n\n        def find_values(values: Iterable[Any]) -> set[str]:\n            ranked: list[tuple[int, int, str]] = []\n            for raw in values:\n                value = str(raw or "").strip()\n                if not value or value == "—":\n                    continue\n                nv = _normalise(value)\n                compact = self._suggestion_compact(value)\n                score = 0\n                if nv and re.search(rf"(?<![A-Z0-9]){re.escape(nv)}(?![A-Z0-9])", n):\n                    score = 3\n                elif compact and compact in q_tokens:\n                    score = 2\n                if score:\n                    ranked.append((score, len(nv), value))\n            if not ranked:\n                return set()\n            best_score = max(x[0] for x in ranked)\n            best_len = max(x[1] for x in ranked if x[0] == best_score)\n            return {value for score, length, value in ranked if score == best_score and length == best_len}\n\n        non_matrix = [f for f in self.families if f.get("backend") != "matrix"]\n        for key in ("manufacturer", "model", "type", "generation"):\n            found = find_values(f.get(key) for f in non_matrix)\n            if found:\n                constraints[key] = found\n\n        records = [r for f in non_matrix for r in f.get("records", [])]\n        for key in ("moment_class", "shear_class", "cover"):\n            found = find_values(r.get(key) for r in records)\n            if found:\n                constraints[key] = found\n\n        concrete_match = re.search(r"C\\s*(\\d{2})\\s*/\\s*(\\d{2})", n)\n        if concrete_match:\n            constraints["concrete_min"] = {f"C{concrete_match.group(1)}/{concrete_match.group(2)}"}\n\n        height_match = re.search(r"\\bH\\s*(\\d{3,4})\\b", n)\n        if height_match:\n            constraints["height_mm"] = {height_match.group(1)}\n\n        insulation_match = re.search(r"\\b(80|120)\\s*MM\\b", n)\n        if insulation_match:\n            constraints["insulation_thickness_mm"] = {insulation_match.group(1)}\n\n        return constraints\n\n    def _structured_record_suggestions(self, text: str, preferred_catalog_id: str | None,\n                                       preferred_concrete: str | None, limit: int) -> list[DesignationSuggestion]:\n        """Vary only selectors that are not explicitly present in a recognizable partial designation."""\n        constraints = self._explicit_selector_constraints(text)\n        technical = {"model", "type", "moment_class", "shear_class", "cover", "height_mm", "generation"}\n        if not constraints.get("moment_class") or len(technical.intersection(constraints)) < 2:\n            return []\n\n        families = [f for f in self.families if f.get("backend") != "matrix"]\n        for key in ("manufacturer", "model", "type", "generation"):\n            allowed = constraints.get(key)\n            if allowed:\n                families = [f for f in families if str(f.get(key, "")) in allowed]\n\n        if preferred_catalog_id:\n            preferred = [f for f in families if str(f.get("catalog_id")) == str(preferred_catalog_id)]\n            if preferred:\n                families = preferred\n\n        matches: list[DesignationSuggestion] = []\n        for family in families:\n            for record in family.get("records", []):\n                if preferred_concrete and str(record.get("concrete_min", "")) != str(preferred_concrete):\n                    continue\n                ok = True\n                for key in ("moment_class", "shear_class", "concrete_min", "cover", "height_mm"):\n                    allowed = constraints.get(key)\n                    if allowed and str(record.get(key, "")) not in allowed:\n                        ok = False\n                        break\n                if not ok:\n                    continue\n                insulation = constraints.get("insulation_thickness_mm")\n                if insulation:\n                    actual = record.get("insulation_thickness_mm", family.get("insulation_thickness_mm"))\n                    if str(actual) not in insulation:\n                        continue\n                matches.append(DesignationSuggestion(self.result_for_record(family, record), 350.0 + 15.0 * len(constraints)))\n\n        best: dict[str, DesignationSuggestion] = {}\n        for item in matches:\n            key = _normalise(item.designation)\n            if key not in best or item.score > best[key].score:\n                best[key] = item\n        return sorted(best.values(), key=lambda x: natural_key(x.designation))[:limit]\n\n''' + marker
    s = replace_once(s, marker, helper, "structured partial suggestion helper")

    old = '''        if not height_match:\n            nums = [x for x in re.findall(r"\\b(\\d{3,4})\\b", n) if int(x) >= 100]\n            wanted_height = nums[-1] if nums else None\n        else:\n            wanted_height = height_match.group(1)\n\n        family_rank: list[tuple[float, dict[str, Any]]] = []\n        for fam in self.families:\n            if fam.get("backend") != "matrix": continue\n'''
    new = '''        if not height_match:\n            nums = [x for x in re.findall(r"\\b(\\d{3,4})\\b", n) if int(x) >= 100]\n            wanted_height = nums[-1] if nums else None\n        else:\n            wanted_height = height_match.group(1)\n\n        matrix_families = [f for f in self.families if f.get("backend") == "matrix"]\n\n        def explicit_matrix_values(values: Iterable[Any]) -> set[str]:\n            ranked: list[tuple[int, int, str]] = []\n            for raw_value in values:\n                value = str(raw_value or "").strip()\n                if not value or value == "—":\n                    continue\n                nv = _normalise(value)\n                cv = self._suggestion_compact(value)\n                score = 0\n                if nv and re.search(rf"(?<![A-Z0-9]){re.escape(nv)}(?![A-Z0-9])", n):\n                    score = 3\n                elif cv and cv in q_tokens:\n                    score = 2\n                if score:\n                    ranked.append((score, len(nv), value))\n            if not ranked:\n                return set()\n            best_score = max(item[0] for item in ranked)\n            best_len = max(item[1] for item in ranked if item[0] == best_score)\n            return {value for score, length, value in ranked if score == best_score and length == best_len}\n\n        explicit_products = explicit_matrix_values(\n            product for matrix_family in matrix_families for product in self.moment_classes(matrix_family)\n        )\n        explicit_shears = explicit_matrix_values(\n            row.get("shear_class") for matrix_family in matrix_families for row in matrix_family.get("shear_rows", [])\n        )\n        explicit_types = explicit_matrix_values(matrix_family.get("type") for matrix_family in matrix_families)\n        explicit_models = explicit_matrix_values(matrix_family.get("model") for matrix_family in matrix_families)\n\n        family_rank: list[tuple[float, dict[str, Any]]] = []\n        for fam in matrix_families:\n            if explicit_types and str(fam.get("type", "")) not in explicit_types:\n                continue\n            if explicit_models and str(fam.get("model", "")) not in explicit_models:\n                continue\n'''
    s = replace_once(s, old, new, "matrix global explicit selectors")

    old = '''            products = self.moment_classes(fam)\n            if not products: continue\n            product_rank=[]\n'''
    new = '''            products = self.moment_classes(fam)\n            if explicit_products:\n                products = [p for p in products if str(p) in explicit_products]\n            if not products: continue\n            product_rank=[]\n'''
    s = replace_once(s, old, new, "matrix explicit product restriction")

    old = '''            chosen_products=[p for ps,p in product_rank if ps>=48][:4]\n            if not chosen_products:\n                # For broad family query show a few representative product levels rather than every height.\n                chosen_products=products[:3]\n'''
    new = '''            if explicit_products:\n                chosen_products = products\n            else:\n                chosen_products=[p for ps,p in product_rank if ps>=48][:4]\n                if not chosen_products:\n                    # For broad family query show a few representative product levels rather than every height.\n                    chosen_products=products[:3]\n'''
    s = replace_once(s, old, new, "matrix exact product choice")

    old = '''                    # Match any typed shear token exactly/compactly; otherwise provide a few distinct options.\n                    matched_s=[sc for sc in shears if self._suggestion_compact(sc) in q_tokens or self._suggestion_compact(sc) in compact]\n                    use_s=matched_s[:3] if matched_s else shears[:3]\n'''
    new = '''                    if explicit_shears:\n                        matched_s = [sc for sc in shears if str(sc) in explicit_shears]\n                        if not matched_s:\n                            continue\n                        use_s = matched_s[:3]\n                    else:\n                        # Broad/incomplete shear text keeps the existing tolerant behaviour.\n                        matched_s=[sc for sc in shears if self._suggestion_compact(sc) in q_tokens or self._suggestion_compact(sc) in compact]\n                        use_s=matched_s[:3] if matched_s else shears[:3]\n'''
    s = replace_once(s, old, new, "matrix explicit shear restriction")

    old = '''        raw = str(text or "").strip()\n        if not raw or len(self._suggestion_compact(raw)) < 2:\n            return []\n        q_tokens = self._suggestion_tokens(raw)\n'''
    new = '''        raw = str(text or "").strip()\n        if not raw or len(self._suggestion_compact(raw)) < 2:\n            return []\n\n        constraints = self._explicit_selector_constraints(raw)\n        if preferred_concrete and constraints.get("concrete_min") and str(preferred_concrete) not in constraints["concrete_min"]:\n            return []\n\n        # Exact designation or alias: do not clutter the popup with merely similar products.\n        exact_pairs = list(self._designation_index.get(_normalise(raw), []))\n        if preferred_catalog_id:\n            preferred_pairs = [x for x in exact_pairs if str(x[0].get("catalog_id")) == str(preferred_catalog_id)]\n            if preferred_pairs:\n                exact_pairs = preferred_pairs\n        if preferred_concrete:\n            exact_pairs = [x for x in exact_pairs if str(x[1].get("concrete_min", "")) == str(preferred_concrete)]\n        if exact_pairs:\n            exact_out: list[DesignationSuggestion] = []\n            seen_exact: set[str] = set()\n            for family, record in exact_pairs:\n                item = DesignationSuggestion(self.result_for_record(family, record), 1000.0)\n                key = _normalise(item.designation)\n                if key not in seen_exact:\n                    seen_exact.add(key)\n                    exact_out.append(item)\n            if exact_out:\n                return exact_out[:limit]\n\n        # Recognizable standard partial designation: vary only selectors the user did NOT specify.\n        structured = self._structured_record_suggestions(raw, preferred_catalog_id, preferred_concrete, limit)\n        if structured:\n            return structured[:limit]\n\n        # Recognizable matrix designation: stay inside the matrix family instead of mixing fuzzy standard products.\n        matrix_specific = self._matrix_suggestions(raw, preferred_catalog_id, limit, preferred_concrete=preferred_concrete)\n        if matrix_specific:\n            return matrix_specific[:limit]\n\n        q_tokens = self._suggestion_tokens(raw)\n'''
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
        "- Pokud zadané parametry určují konkrétní prvek, nezobrazuje jiné typy.\n"
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

    # Pick a real non-matrix group with at least two heights so the test reflects actual catalog data.
    groups: dict[tuple[int, str, str, str, str], list[tuple[dict, dict]]] = defaultdict(list)
    for family in db.families:
        if family.get("backend") == "matrix":
            continue
        for record in family.get("records", []):
            required = [record.get("moment_class"), record.get("shear_class"), record.get("concrete_min"), record.get("cover"), record.get("height_mm")]
            if any(x in (None, "", "—") for x in required):
                continue
            key = (id(family), str(record["moment_class"]), str(record["shear_class"]), str(record["concrete_min"]), str(record["cover"]))
            groups[key].append((family, record))

    standard_group = None
    for items in groups.values():
        heights = {str(record.get("height_mm")) for _family, record in items}
        family = items[0][0]
        if len(heights) >= 2 and str(family.get("type", "")) not in ("", "—") and str(family.get("model", "")) not in ("", "—"):
            standard_group = items
            break
    assert standard_group, "No suitable standard catalog group for v0.6.4 regression test"

    family, record = standard_group[0]
    generation = str(family.get("generation", ""))
    common_parts = [
        str(family.get("model", "")), str(family.get("type", "")),
        str(record.get("moment_class", "")), str(record.get("shear_class", "")), str(record.get("cover", "")),
    ]
    if generation not in ("", "—"):
        common_parts.append(generation)
    full_text = " ".join(common_parts + [f"H{record.get('height_mm')}"])
    concrete = str(record.get("concrete_min"))

    full_standard = db.suggest_designations(full_text, preferred_concrete=concrete, limit=12)
    assert full_standard, f"No full standard suggestions for {full_text!r}"
    assert all(str(x.result.family.get("model")) == str(family.get("model")) for x in full_standard)
    assert all(str(x.result.family.get("type")) == str(family.get("type")) for x in full_standard)
    assert all(str(x.result.record.get("moment_class")) == str(record.get("moment_class")) for x in full_standard)
    assert all(str(x.result.record.get("shear_class")) == str(record.get("shear_class")) for x in full_standard)
    assert all(str(x.result.record.get("cover")) == str(record.get("cover")) for x in full_standard)
    assert all(str(x.result.record.get("height_mm")) == str(record.get("height_mm")) for x in full_standard)
    assert all(str(x.result.record.get("concrete_min")) == concrete for x in full_standard)

    partial_text = " ".join(common_parts)
    partial_standard = db.suggest_designations(partial_text, preferred_concrete=concrete, limit=12)
    assert partial_standard, f"No partial standard suggestions for {partial_text!r}"
    assert all(str(x.result.family.get("model")) == str(family.get("model")) for x in partial_standard)
    assert all(str(x.result.family.get("type")) == str(family.get("type")) for x in partial_standard)
    assert all(str(x.result.record.get("moment_class")) == str(record.get("moment_class")) for x in partial_standard)
    assert all(str(x.result.record.get("shear_class")) == str(record.get("shear_class")) for x in partial_standard)
    assert all(str(x.result.record.get("cover")) == str(record.get("cover")) for x in partial_standard)
    assert all(str(x.result.record.get("concrete_min")) == concrete for x in partial_standard)
    assert len({str(x.result.record.get("height_mm")) for x in partial_standard}) >= 2, "Missing height should offer height variants"

    # MAX FRANK: explicit product level, shear, cover and height remain binding across all matrix families.
    full_mxl = db.suggest_designations("MXL20 V6+- C30 h200", preferred_concrete="C25/30", limit=12)
    assert full_mxl, "No MXL20 suggestions"
    assert all(str(x.result.record.get("moment_class")) == "MXL20" for x in full_mxl)
    assert all(str(x.result.record.get("shear_class")) == "V6±" for x in full_mxl)
    assert all(str(x.result.record.get("cover", "")).startswith("C30") for x in full_mxl)
    assert all(str(x.result.record.get("height_mm")) == "200" for x in full_mxl)
    assert all(str(x.result.record.get("concrete_min")) == "C25/30" for x in full_mxl)

    partial_mxl = db.suggest_designations("MXL20 V6+- C30", preferred_concrete="C25/30", limit=12)
    assert partial_mxl, "No partial MXL20 suggestions"
    assert all(str(x.result.record.get("moment_class")) == "MXL20" for x in partial_mxl)
    assert all(str(x.result.record.get("shear_class")) == "V6±" for x in partial_mxl)
    assert all(str(x.result.record.get("cover", "")).startswith("C30") for x in partial_mxl)
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
            "Přesnější našeptávač: zadané parametry (typ, moment, smyk, krytí, výška, generace i explicitní tloušťka izolantu) "
            "jsou nyní závazné a program nabízí pouze varianty parametrů, které v názvu skutečně chybí. "
            "Beton projektu zůstává striktním filtrem."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.6.4 OK; specificity-aware designation filtering verified")


if __name__ == "__main__":
    main()
