from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.7"
OUT = ROOT / "updates" / "0.6.8"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(fn(text), encoding="utf-8")


def patch_app(s: str) -> str:
    return replace_once(s, 'APP_VERSION = "0.6.7"', 'APP_VERSION = "0.6.8"', "app version")


def patch_bulk_engine(s: str) -> str:
    old_header = '''    normalized = " ".join(values)\n    has_designation = any(word in normalized for word in ("označení", "oznaceni", "designation", "typ", "nosník", "nosnik"))\n    has_meta = any(word in normalized for word in ("pozice", "position", "ks", "počet", "pocet", "quantity"))\n    return has_designation and has_meta\n\n\ndef _quantity_or_none(value: str) -> int | None:\n    try:\n        return safe_quantity(value)\n    except ValueError:\n        return None\n'''
    new_header = '''    normalized = " ".join(values)\n    has_designation = any(\n        word in normalized\n        for word in ("označení", "oznaceni", "designation", "typ", "nosník", "nosnik", "popis", "položka", "polozka", "název", "nazev")\n    )\n    has_meta = any(\n        word in normalized\n        for word in ("pozice", "position", "ks", "počet", "pocet", "quantity", "jednotka", "mj", "množství", "mnozstvi")\n    )\n    return has_designation and has_meta\n\n\nPIECE_UNITS = {"kus", "ks", "pc", "pcs", "piece", "pieces"}\n\n\ndef parse_bulk_quantity(value: str) -> int:\n    """Počet kusů z Excelu, včetně českého formátu 86,000 = 86 ks.\n\n    Desetinný zápis je přijat pouze tehdy, pokud má nulovou desetinnou část.\n    Tím se nepovolí zlomkové počty výrobků.\n    """\n    text = str(value or "").strip().replace("\\u00a0", "")\n    text = "".join(text.split())\n    if not text:\n        raise ValueError("Počet kusů není zadán.")\n    match = re.fullmatch(r"([+-]?\\d+)[,.](0+)", text)\n    if match:\n        text = match.group(1)\n    return safe_quantity(text)\n\n\ndef _quantity_or_none(value: str) -> int | None:\n    try:\n        return parse_bulk_quantity(value)\n    except ValueError:\n        return None\n\n\ndef _is_piece_unit(value: str) -> bool:\n    unit = str(value or "").strip().casefold().rstrip(".")\n    return unit in PIECE_UNITS\n'''
    s = replace_once(s, old_header, new_header, "headers and Excel quantities")

    old_three = '''    if len(values) == 3:\n        quantity = _quantity_or_none(values[1])\n        if quantity is not None:\n            # Pozice [TAB] ks [TAB] typ.\n            return values[0] or None, quantity, values[2], ""\n        # Pozice [TAB] typ [TAB] poznámka.\n        return values[0] or None, 1, values[1], values[2]\n\n    quantity = safe_quantity(values[1] or 1)\n    return values[0] or None, quantity, values[2], " | ".join(values[3:]).strip()\n'''
    new_three = '''    if len(values) == 3:\n        # Popis [TAB] jednotka [TAB] množství – typický export rozpočtu / výkazu výměr.\n        if _is_piece_unit(values[1]):\n            quantity = _quantity_or_none(values[2])\n            if quantity is None:\n                raise ValueError(f"Množství '{values[2]}' není platný celý počet kusů.")\n            return None, quantity, values[0], ""\n        quantity = _quantity_or_none(values[1])\n        if quantity is not None:\n            # Pozice [TAB] ks [TAB] typ.\n            return values[0] or None, quantity, values[2], ""\n        # Pozice [TAB] typ [TAB] poznámka.\n        return values[0] or None, 1, values[1], values[2]\n\n    # Popis [TAB] jednotka [TAB] množství [TAB] poznámka ...\n    if len(values) >= 4 and _is_piece_unit(values[1]):\n        quantity = _quantity_or_none(values[2])\n        if quantity is None:\n            raise ValueError(f"Množství '{values[2]}' není platný celý počet kusů.")\n        return None, quantity, values[0], " | ".join(values[3:]).strip()\n\n    quantity = parse_bulk_quantity(values[1] or 1)\n    return values[0] or None, quantity, values[2], " | ".join(values[3:]).strip()\n'''
    s = replace_once(s, old_three, new_three, "three-column BOQ parsing")

    old_pre = '''    text = str(designation or "").strip()\n    result_note = str(note or "").strip()\n\n    length_match = re.search'''
    new_pre = '''    text = str(designation or "").strip()\n    result_note = str(note or "").strip()\n\n    # Rozpočtové prefixy nejsou součástí označení výrobku. Zachováme však celý\n    # původní řádek v BulkImportItem.raw, takže se nic auditně neztrácí.\n    text = re.sub(r"^\\s*M\\s*\\+\\s*D\\s*", "", text, flags=re.I)\n    text = re.sub(\n        r"^\\s*Nosn[ýy]\\s+tepeln[ěe]\\s+izola[čc]n[íi]\\s+prvek\\s*",\n        "",\n        text,\n        flags=re.I,\n    ).strip()\n\n    length_match = re.search'''
    s = replace_once(s, old_pre, new_pre, "BOQ description prefix")
    return s


def patch_bulk_ui(s: str) -> str:
    old = '''                "Formáty:  typ  |  typ [TAB] ks  |  pozice [TAB] typ  |  "\n                "pozice [TAB] ks [TAB] typ [TAB] poznámka"\n'''
    new = '''                "Formáty: typ | typ [TAB] ks | popis [TAB] jednotka [TAB] množství | "\n                "pozice [TAB] typ | pozice [TAB] ks [TAB] typ [TAB] poznámka"\n'''
    return replace_once(s, old, new, "bulk UI format help")


SCHOCK_ROWS = [
    ("M+D   Nosný tepelně izolační prvek Schöck Isokorb T-ZL-EI120-H180-5.3", "kus", "86,000", 86, "Schöck Isokorb T-ZL-EI120-H180-5.3"),
    ("M+D   Nosný tepelně izolační prvek Schöck Sconnex W-N1-V1H1-B180-1.0", "kus", "2,000", 2, "Schöck Sconnex W-N1-V1H1-B180-1.0"),
    ("M+D   Nosný tepelně izolační prvek Schöck Isokorb T-QP-VV1-REI120-H200-L300-5.0", "kus", "2,000", 2, "Schöck Isokorb T-QP-VV1-REI120-H200-L300-5.0"),
    ("M+D   Nosný tepelně izolační prvekSchöck Isokorb   CXT-AP-MM1-VV1-REI30-LR200-B200-L300-1.0", "kus", "7,000", 7, "Schöck Isokorb   CXT-AP-MM1-VV1-REI30-LR200-B200-L300-1.0"),
    ("M+D   Nosný tepelně izolační prvek Schöck Isokorb XT-KL-O-M3-V1-REI120-CV1-H250-7.2", "kus", "8,000", 8, "Schöck Isokorb XT-KL-O-M3-V1-REI120-CV1-H250-7.2"),
    ("M+D   Nosný tepelně izolační prvek Schöck Isokorb XT-KL-M6-V3-REI120-CV1-H250-6.2", "kus", "8,000", 8, "Schöck Isokorb XT-KL-M6-V3-REI120-CV1-H250-6.2"),
]


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)
    patch_file(OUT / "bulk_import_engine.py", patch_bulk_engine)
    patch_file(OUT / "bulk_import.py", patch_bulk_ui)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.8\n"
        "- Hromadné vložení umí přímo formát Popis | jednotka | množství z rozpočtů a výkazů výměr.\n"
        "- Množství jako 86,000 / 2,000 se bezpečně převede na 86 / 2 ks; nenulové zlomkové množství se odmítne.\n"
        "- Prefix 'M+D Nosný tepelně izolační prvek' se při vyhledání ignoruje.\n"
        "- Technické označení Schöck zůstává celé: generace 5.3, 5.0, 7.2, 6.2 a 1.0 se nikdy neodřezává.\n"
        "- Přidány regresní testy přesně pro šest skutečných řádků Schöck dodaných z výkazu.\n",
        encoding="utf-8",
    )

    for name in [
        "app.pyw", "autocomplete.py", "catalog_engine.py", "project_model.py", "project_ui.py",
        "updater.py", "bulk_import_engine.py", "bulk_import.py",
    ]:
        py_compile.compile(str(OUT / name), doraise=True)

    sys.path.insert(0, str(OUT))
    import bulk_import_engine as bulk
    import catalog_engine as engine

    # 1) Přesný formát skutečného Schöck výkazu – testujeme parser nezávisle na tom,
    # které velké Schöck katalogové soubory jsou zachované jen v lokální instalaci.
    for description, unit, quantity_text, expected_qty, expected_designation in SCHOCK_ROWS:
        position, quantity, designation, note = bulk.interpret_bulk_parts([description, unit, quantity_text])
        assert position is None
        assert quantity == expected_qty, (description, quantity, expected_qty)
        designation, note = bulk.preprocess_bulk_designation(designation, note)
        assert designation == expected_designation, (designation, expected_designation)
        assert note == "", (description, note)
        # Desetinná koncovka je generace výrobku a musí zůstat součástí označení.
        assert designation.rsplit("-", 1)[-1] in {"5.3", "1.0", "5.0", "7.2", "6.2"}

    assert bulk.parse_bulk_quantity("86,000") == 86
    assert bulk.parse_bulk_quantity("8.000") == 8
    assert bulk.parse_bulk_quantity("2") == 2
    try:
        bulk.parse_bulk_quantity("2,500")
    except ValueError:
        pass
    else:
        raise AssertionError("Fractional product quantity 2,500 must not be accepted")

    # 2) Hlavička běžného výkazu se přeskočí.
    assert bulk.looks_like_bulk_header(["Popis", "MJ", "Množství"])
    assert bulk.looks_like_bulk_header(["Název", "Jednotka", "Počet"])

    # 3) Předchozí Egcobox chování nesmí regressovat.
    db = engine.CatalogDatabase(OUT / "catalogs")
    egcobox_text = "\n".join([
        "EGCOBOX   MXL20-VS-C50-h200-REI120-SW - 0,93m\t4",
        "EGCOBOX   MXL25-WU280-VS-C30-h200-REI120-SW\t2",
        "EGCOBOX VXL Z   48-K-C30-h160-REI120-SW\t8",
        "EGCOBOX   VXL48-K-C30-h160-REI120-SW\t26",
    ])
    items, skipped = bulk.analyze_bulk_text(
        db, egcobox_text, preferred_concrete="C25/30", existing_positions=[], start_position="P001", suggestion_limit=100
    )
    assert skipped == 0 and len(items) == 4
    assert all(item.ready and item.result is not None for item in items), [(x.status, x.message) for x in items]
    assert "Délka prvku: 0,93 m" in items[0].note
    assert str(items[1].result.family.get("type")) == "MXL-WU"
    assert "Geometrie WU: 280 mm" in items[1].note
    assert str(items[2].result.family.get("type")) == "VXL Z-K"
    assert str(items[3].result.family.get("type")) == "VXL-K"

    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.6.8"' in app_text

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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.8/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.8",
        "notes": (
            "Hromadný import nyní přijímá i skutečné třísloupcové výkazy Popis | jednotka | množství. "
            "České celočíselné množství ve formátu 86,000 se načte jako 86 ks, rozpočtový prefix M+D se ignoruje "
            "a technické generace Schöck (např. 5.0, 6.2, 7.2) zůstávají nedílnou součástí označení."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("v0.6.8 OK; Schock BOQ parsing and Egcobox regression verified")


if __name__ == "__main__":
    main()
