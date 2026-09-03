from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.6"
OUT = ROOT / "updates" / "0.6.7"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(fn(text), encoding="utf-8")


def patch_app(s: str) -> str:
    return replace_once(s, 'APP_VERSION = "0.6.6"', 'APP_VERSION = "0.6.7"', "app version")


def patch_bulk_engine(s: str) -> str:
    marker = '''    quantity = safe_quantity(values[1] or 1)\n    return values[0] or None, quantity, values[2], " | ".join(values[3:]).strip()\n\n\ndef normalize_designation_text(value: str) -> str:\n'''
    replacement = '''    quantity = safe_quantity(values[1] or 1)\n    return values[0] or None, quantity, values[2], " | ".join(values[3:]).strip()\n\n\ndef _append_bulk_note(note: str, value: str) -> str:\n    note = str(note or "").strip()\n    value = str(value or "").strip()\n    if not value:\n        return note\n    return f"{note} | {value}" if note else value\n\n\ndef preprocess_bulk_designation(designation: str, note: str = "") -> tuple[str, str]:\n    """Oddělí projektové doplňky, které nejsou součástí statického katalogového klíče.\n\n    Reálné výkazy Egcobox obsahují navíc obchodní prefix EGCOBOX, požární/izolační\n    příponu (např. REI120-SW), zkrácenou délku a někdy geometrický rozměr varianty\n    přímo v jejím kódu (WU280). Pro vyhledání se tyto části normalizují, ale údaje\n    se neztratí: vše podstatné se uloží do poznámky projektového řádku.\n    """\n    text = str(designation or "").strip()\n    result_note = str(note or "").strip()\n\n    length_match = re.search(r"\\s*-\\s*(\\d+(?:[.,]\\d+)?)\\s*m\\s*$", text, flags=re.I)\n    if length_match:\n        length = length_match.group(1).replace(".", ",")\n        result_note = _append_bulk_note(result_note, f"Délka prvku: {length} m")\n        text = text[: length_match.start()].rstrip()\n\n    specification_match = re.search(r"-(REI\\d+)(?:-([A-Z]{2,4}))?\\s*$", text, flags=re.I)\n    if specification_match:\n        fire = specification_match.group(1).upper()\n        insulation = (specification_match.group(2) or "").upper()\n        suffix = f"-{insulation}" if insulation else ""\n        result_note = _append_bulk_note(result_note, f"Specifikace: {fire}{suffix}")\n        text = text[: specification_match.start()].rstrip()\n\n    text = re.sub(r"^\\s*EGCOBOX(?:®)?\\s+", "", text, flags=re.I).strip()\n\n    geometry_match = re.search(\n        r"\\b(MXL\\s*\\d+(?:-K)?)-(HVS|WOS|BHS|WUS|BH|WU)(\\d{2,4})(?=-)",\n        text,\n        flags=re.I,\n    )\n    if geometry_match:\n        product = geometry_match.group(1)\n        variant = geometry_match.group(2).upper()\n        dimension = geometry_match.group(3)\n        canonical = f"{product}-{variant}"\n        text = text[: geometry_match.start()] + canonical + text[geometry_match.end() :]\n        result_note = _append_bulk_note(result_note, f"Geometrie {variant}: {dimension} mm")\n\n    return text.strip(), result_note\n\n\ndef normalize_designation_text(value: str) -> str:\n'''
    s = replace_once(s, marker, replacement, "bulk metadata preprocessing helper")

    old = '''            position, quantity, designation, note = interpret_bulk_parts(parts)\n            designation = designation.strip()\n            if not designation:\n                raise ValueError("Chybí označení nosníku.")\n'''
    new = '''            position, quantity, designation, note = interpret_bulk_parts(parts)\n            designation, note = preprocess_bulk_designation(designation, note)\n            if not designation:\n                raise ValueError("Chybí označení nosníku.")\n'''
    s = replace_once(s, old, new, "bulk preprocessing call")

    old = '''        if len(candidates) == 1:\n            item.result = candidates[0].result\n            item.candidates = candidates\n            if is_exact_designation(designation, item.result):\n                item.status = "exact"\n                item.message = "Úplné označení odpovídá právě jednomu katalogovému prvku."\n            else:\n                item.status = "unique"\n                item.message = "Chybějící údaj byl jednoznačně doplněn z katalogu; neexistuje jiná platná varianta."\n            items.append(item)\n            continue\n\n        if len(candidates) > 1:\n'''
    new = '''        exact_candidates = [candidate for candidate in candidates if is_exact_designation(designation, candidate.result)]\n        if len(exact_candidates) == 1:\n            item.result = exact_candidates[0].result\n            item.candidates = exact_candidates\n            item.status = "exact"\n            item.message = "Úplné označení odpovídá právě jednomu katalogovému prvku."\n            items.append(item)\n            continue\n\n        if len(candidates) == 1:\n            item.result = candidates[0].result\n            item.candidates = candidates\n            item.status = "unique"\n            item.message = "Chybějící údaj byl jednoznačně doplněn z katalogu; neexistuje jiná platná varianta."\n            items.append(item)\n            continue\n\n        if len(candidates) > 1:\n'''
    return replace_once(s, old, new, "prefer exact candidate in bulk review")


def patch_catalog_engine(s: str) -> str:
    old = '''        matrix_trigger = (\n            "MAXFRANK" in compact or "EGCOBOX" in compact or\n            bool(re.search(r"\\b(?:MM|MXL)\\s*\\d", n)) or\n            any(token in q_tokens for token in {"MM", "MXL", "HVS", "WOS", "BH", "WU", "BHS", "WUS"})\n        )\n'''
    new = '''        matrix_trigger = (\n            bool(re.search(r"\\b(?:MM|MXL)\\s*\\d", n)) or\n            any(token in q_tokens for token in {"MM", "MXL", "HVS", "WOS", "BH", "WU", "BHS", "WUS"})\n        )\n'''
    s = replace_once(s, old, new, "matrix trigger scope")

    old = '''        explicit_types = explicit_matrix_values(matrix_family.get("type") for matrix_family in matrix_families)\n        explicit_models = explicit_matrix_values(matrix_family.get("model") for matrix_family in matrix_families)\n\n        family_rank: list[tuple[float, dict[str, Any]]] = []\n'''
    new = '''        explicit_types = explicit_matrix_values(matrix_family.get("type") for matrix_family in matrix_families)\n        explicit_models = explicit_matrix_values(matrix_family.get("model") for matrix_family in matrix_families)\n\n        variant_match = re.search(\n            r"\\b(?:MM|MXL)\\s*\\d+(?:-K)?-(HVS|WOS|BHS|WUS|BH|WU)(?=-|\\b)",\n            n,\n        )\n        if variant_match:\n            suffix = "-" + variant_match.group(1)\n            variant_types = {\n                str(matrix_family.get("type", ""))\n                for matrix_family in matrix_families\n                if str(matrix_family.get("type", "")).endswith(suffix)\n            }\n            if variant_types:\n                explicit_types = variant_types\n\n        family_rank: list[tuple[float, dict[str, Any]]] = []\n'''
    return replace_once(s, old, new, "explicit matrix variant lock")


REAL_ROWS = [
    ("EGCOBOX   MXL20-V1-C50-h200-REI120-SW", 16),
    ("EGCOBOX   MXL20-V6±-C30-h200-REI120-SW", 10),
    ("EGCOBOX   MXL20-V6±-C50-h200-REI120-SW", 24),
    ("EGCOBOX   MXL20-VS-C30-h200-REI120-SW", 10),
    ("EGCOBOX   MXL20-VS-C50-h200-REI120-SW", 8),
    ("EGCOBOX   MXL20-VS-C50-h200-REI120-SW - 0,93m", 4),
    ("EGCOBOX   MXL25-V1-C50-h200-REI120-SW", 4),
    ("EGCOBOX   MXL25-VS-C30-h200-REI120-SW", 16),
    ("EGCOBOX   MXL25-VS-C50-h200-REI120-SW", 40),
    ("EGCOBOX   MXL25-VS-C50-h200-REI120-SW - 1m", 8),
    ("EGCOBOX   MXL25-WU280-VS-C30-h200-REI120-SW", 2),
    ("EGCOBOX   MXL35-VS-C30-h200-REI120-SW", 16),
    ("EGCOBOX   MXL50-V1-C30-h200-REI120-SW", 8),
    ("EGCOBOX   MXL50-V2-C50-h200-REI120-SW", 4),
    ("EGCOBOX   MXL50-V2-C50-h200-REI120-SW - 1m", 4),
    ("EGCOBOX VXL Z   48-K-C30-h160-REI120-SW", 8),
    ("EGCOBOX   VXL48-K-C30-h160-REI120-SW", 26),
]


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)
    patch_file(OUT / "bulk_import_engine.py", patch_bulk_engine)
    patch_file(OUT / "catalog_engine.py", patch_catalog_engine)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.7\n"
        "- Ověřeno na reálném 17řádkovém výkazu Egcobox dodaném uživatelem.\n"
        "- Délky '- 0,93m' a '- 1m' se uloží do poznámky a neovlivní vyhledávání.\n"
        "- MXL25-WU280 je bezpečně rodina MXL-WU; geometrie 280 mm se zachová v poznámce.\n"
        "- Prefix EGCOBOX a specifikace REI120-SW se oddělí od statického klíče; specifikace zůstane v poznámce.\n"
        "- VXL Z 48-K se již neplete s maticovými MXL typy.\n",
        encoding="utf-8",
    )

    compile_files = ["app.pyw", "autocomplete.py", "catalog_engine.py", "project_model.py", "project_ui.py", "updater.py", "bulk_import_engine.py", "bulk_import.py"]
    for name in compile_files:
        py_compile.compile(str(OUT / name), doraise=True)

    sys.path.insert(0, str(OUT))
    import catalog_engine as engine
    import bulk_import_engine as bulk

    db = engine.CatalogDatabase(OUT / "catalogs")
    text = "\n".join(f"{designation}\t{quantity}" for designation, quantity in REAL_ROWS)
    items, skipped = bulk.analyze_bulk_text(db, text, preferred_concrete="C25/30", existing_positions=[], start_position="P001", suggestion_limit=100)
    assert skipped == 0 and len(items) == len(REAL_ROWS)
    failures = [item for item in items if not item.ready or item.result is None]
    assert not failures, [(x.line_number, x.status, x.message, x.designation) for x in failures]
    for index, item in enumerate(items):
        assert item.quantity == REAL_ROWS[index][1]
        assert str(item.result.record.get("concrete_min", "")) == "C25/30"
        assert "Specifikace: REI120-SW" in item.note, (index + 1, item.note)

    assert items[5].result.designation.startswith("Egcobox® MXL20-VS-C50-h200")
    assert "Délka prvku: 0,93 m" in items[5].note
    assert items[9].result.designation.startswith("Egcobox® MXL25-VS-C50-h200")
    assert "Délka prvku: 1 m" in items[9].note
    assert items[14].result.designation.startswith("Egcobox® MXL50-V2-C50-h200")
    assert "Délka prvku: 1 m" in items[14].note

    wu = items[10]
    assert str(wu.result.family.get("type")) == "MXL-WU", (wu.result.family.get("type"), wu.result.designation)
    assert wu.result.designation.startswith("Egcobox® MXL25-WU-VS-C30-h200"), wu.result.designation
    assert "Geometrie WU: 280 mm" in wu.note

    vz = items[15]
    assert str(vz.result.family.get("type")) == "VXL Z-K", (vz.result.family.get("type"), vz.result.designation)
    assert vz.result.designation.startswith("Egcobox® VXL Z 48-K-C30-h160"), vz.result.designation
    vxl = items[16]
    assert str(vxl.result.family.get("type")) == "VXL-K", (vxl.result.family.get("type"), vxl.result.designation)
    assert vxl.result.designation.startswith("Egcobox® VXL48-K-C30-h160"), vxl.result.designation

    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    bulk_text = (OUT / "bulk_import_engine.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.6.7"' in app_text
    assert "preprocess_bulk_designation" in bulk_text and "exact_candidates" in bulk_text

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({"path": rel, "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.7/{rel}", "sha256": hashlib.sha256(data).hexdigest()})

    manifest = {
        "version": "0.6.7",
        "notes": "Hromadný import byl doladěn podle reálného výkazu Egcobox. Prefix a REI/SW specifikace se oddělí od statického klíče, délky se uchovají v poznámce, WU rozměr zůstane svázán s MXL-WU a VXL/VXL Z nejsou přebíjeny MXL našeptávačem. Všech 17 dodaných řádků je regresně ověřeno.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.6.7 OK; all 17 real Egcobox bulk rows verified")


if __name__ == "__main__":
    main()
