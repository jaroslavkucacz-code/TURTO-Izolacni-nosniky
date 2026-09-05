from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.1.2"
OUT = ROOT / "updates" / "1.1.3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def compile_sources(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.suffix not in {".py", ".pyw"}:
            continue
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


LENGTH_INFERENCE = r'''_VM_K_LENGTHS = {
    "VM": {24: 200, 43: 250, 65: 250, 86: 300, 108: 400, 130: 400, 151: 500, 200: 500},
    "VXL": {18: 200, 32: 250, 48: 300, 65: 300, 75: 400, 97: 400, 113: 500, 152: 510},
}
_VM_K_BIDIRECTIONAL_LENGTHS = {
    "VM": {24: 200, 43: 250, 65: 250, 86: 310, 108: 400, 130: 400, 151: 500, 200: 520},
    "VXL": {18: 200, 32: 250, 48: 300, 65: 310, 75: 400, 97: 400, 113: 500, 152: 530},
}


def _maxfrank_catalog_length_mm(selection: dict[str, Any], source_text: str) -> int | None:
    """Délka jednoho aktuálního prvku Egcobox podle katalogové řady.

    Používá přesné délkové řady z katalogů Egcobox M a XL. Složené rohové
    prvky CO se záměrně neodhadují, protože jejich dílčí prvky mají rozdílné
    délky a jeden společný převod by byl zavádějící.
    """
    manufacturer = _ascii_upper(selection.get("manufacturer", ""))
    model = _ascii_upper(selection.get("model", ""))
    type_name = _ascii_upper(selection.get("type_name", ""))
    moment_class = _ascii_upper(selection.get("moment_class", ""))
    shear_class = _ascii_upper(selection.get("shear_class", ""))
    source = _ascii_upper(source_text)
    joined = " ".join((model, type_name, moment_class, shear_class, source))
    if "MAX FRANK" not in manufacturer and "EGCOBOX" not in source:
        return None
    if re.search(r"(?:MM|MXL)\s*-?\s*CO\b", joined) or "-CO-" in joined:
        return None

    # Momentové prvky MM/MXL: běžné typy mají 1000 mm; všechny katalogové
    # K-prvky (např. MXL10-K, MXL80-K, MXL110-K) mají 500 mm.
    moment = re.search(r"\b(MXL|MM)\s*(\d{1,3})(?:\s*[±+/-]+)?(?:\s*-\s*K)?\b", joined)
    if moment:
        token_start, token_end = moment.span()
        nearby = joined[token_start : min(len(joined), token_end + 6)]
        number = int(moment.group(2))
        has_k = bool(re.search(r"-\s*K\b", nearby))
        if has_k or number == 10:
            return 500
        if 20 <= number <= 80:
            return 1000

    # Smykové řady VM/VXL bez K mají vždy délku 1000 mm. Krátké K-prvky
    # používají samostatné délkové tabulky; obousměrné ± mají u několika
    # stupňů odlišnou fyzickou délku, proto se rozlišují zvlášť.
    shear = re.search(r"\b(VXL|VM)\s*(?:Z\s*)?(\d{2,3})(?:\s*-\s*K)?\s*(?:±|\+/-|\+-)?", joined)
    if shear:
        family = shear.group(1)
        number = int(shear.group(2))
        token_start, token_end = shear.span()
        nearby = joined[max(0, token_start - 8) : min(len(joined), token_end + 8)]
        has_k = bool(re.search(r"-\s*K\b", nearby))
        if not has_k:
            return 1000
        bidirectional = "±" in nearby or "+/-" in nearby or "+-" in nearby or "±" in type_name
        table = _VM_K_BIDIRECTIONAL_LENGTHS if bidirectional else _VM_K_LENGTHS
        return table.get(family, {}).get(number)
    return None


'''


def patch_substitution(text: str) -> str:
    text = replace_once(text, 'SUBSTITUTION_MODULE_VERSION = "1.1.2"', 'SUBSTITUTION_MODULE_VERSION = "1.1.3"', "substitution version")
    marker = "def _source_element_length_info(row: dict[str, Any]) -> tuple[int | None, str, list[str]]:\n"
    text = replace_once(text, marker, LENGTH_INFERENCE + marker, "catalog length inference")

    old_fallback = '''    manufacturer = _ascii_upper(selection.get("manufacturer", ""))
    model = _ascii_upper(selection.get("model", ""))
    type_name = _ascii_upper(selection.get("type_name", ""))
    source = _ascii_upper(source_text)
    if (
        "MAX FRANK" in manufacturer
        and (model in {"M", "XL", "MM", "MXL"} or type_name.startswith(("MM", "MXL")))
    ) or ("EGCOBOX" in source and re.search(r"\\b(?:MM|MXL)\\d", source)):
        warning = (
            "délka zdrojového prvku nebyla v datech jednoznačná; použit předpoklad 1000 mm pro katalogovou matici "
            "Egcobox. Délku lze potvrdit přes Upravit zdroj / délku / tlak"
        )
        return 1000, "odhad 1000 mm", [warning]
    return None, "", []
'''
    new_fallback = '''    catalog_length = _maxfrank_catalog_length_mm(selection, source_text)
    if catalog_length:
        return catalog_length, "délka z katalogové řady Egcobox", []
    return None, "", []
'''
    text = replace_once(text, old_fallback, new_fallback, "remove generic 1000 mm assumption")

    old_category = '''def _compression_category(value: Any) -> str:
    text = _ascii_upper(value)
    if not text or text in {"-", "—"} or "NEUVEDENO" in text or "DLE TYPU" in text:
        return "unknown"
    without_patterns = (
'''
    new_category = '''def _compression_category(value: Any) -> str:
    text = _ascii_upper(value)
    if not text or text in {"-", "—"} or "NEUVEDENO" in text or "DLE TYPU" in text:
        return "unknown"
    # Smíšený rohový nebo sestavný prvek může obsahovat současně ložiska i
    # tlačené pruty. Takový celek nelze bezpečně převést jednou binární volbou.
    bearing_hint = "COMPRESSION BEARING" in text or "PRESSURE BEARING" in text or ("TLAKOV" in text and "LOZISK" in text)
    bar_hint = any(pattern in text for pattern in ("TLACENE OCEL", "TLACENE PRUTY", "COMPRESSION BARS", "TENSION/COMPRESSION BARS"))
    if bearing_hint and bar_hint:
        return "unknown"
    without_patterns = (
'''
    text = replace_once(text, old_category, new_category, "mixed compression transfer")

    old_error = '        errors.append("délka původního prvku není jednoznačná")\n'
    new_error = '        errors.append("délka původního prvku není jednoznačná; potvrďte ji přes Upravit zdroj / délku / tlak")\n'
    text = replace_once(text, old_error, new_error, "length error guidance")

    text = replace_once(
        text,
        '                "Navrhuje se nejbližší shodná nebo kratší standardní délka HIT, která jako jeden prvek přenese stejnou únosnost."',
        '                "Navrhuje se nejbližší shodná nebo kratší standardní délka HIT, která jako jeden prvek přenese stejnou únosnost. "\n                "Délky aktuálních řad Egcobox MM/MXL a VM/VXL se určují přímo z katalogové třídy; neznámá délka návrh zastaví."',
        "subtitle catalog length",
    )
    text = replace_once(
        text,
        '                "Požární odolnost REI se zatím neposuzuje."',
        '                "Nejednoznačná délka ani smíšený tlakový přenos se neodhadují a návrh se zastaví. Požární odolnost REI se zatím neposuzuje."',
        "warning safe ambiguity",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise RuntimeError(f"Base update not found: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    substitution = OUT / "substitution_workspace.py"
    substitution.write_text(patch_substitution(substitution.read_text(encoding="utf-8")), encoding="utf-8")

    app = OUT / "app.pyw"
    app.write_text(
        replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "1.1.2"', 'APP_VERSION = "1.1.3"', "app version"),
        encoding="utf-8",
    )

    compile_sources(OUT)

    sys.path.insert(0, str(OUT))
    import substitution_workspace as sw

    def selection(moment_class: str, type_name: str = "", model: str = "XL") -> dict[str, str]:
        return {
            "manufacturer": "MAX FRANK", "model": model, "type_name": type_name,
            "moment_class": moment_class, "shear_class": "", "cover": "C30",
            "height_mm": "200", "concrete_min": "C25/30",
        }

    cases = {
        "MXL10-K": 500, "MXL20": 1000, "MXL80": 1000, "MXL80-K": 500, "MXL110-K": 500,
        "MM10-K": 500, "MM25": 1000, "MM150-K": 500,
        "VM48": 1000, "VM24-K": 200, "VM43-K": 250, "VM86-K": 300,
        "VM108-K": 400, "VM151-K": 500, "VM200-K": 500,
        "VXL36": 1000, "VXL18-K": 200, "VXL32-K": 250, "VXL48-K": 300,
        "VXL65-K": 300, "VXL75-K": 400, "VXL113-K": 500, "VXL152-K": 510,
        "VM Z 86-K": 300, "VXL Z 152-K": 510,
    }
    for product, expected in cases.items():
        actual = sw._maxfrank_catalog_length_mm(selection(product), f"EGCOBOX {product}-C30-h200")
        assert actual == expected, (product, actual, expected)

    bidirectional = {
        "VM24-K±": 200, "VM86-K±": 310, "VM200-K±": 520,
        "VXL18-K±": 200, "VXL65-K±": 310, "VXL152-K±": 530,
        "VM48±": 1000, "VXL36±": 1000,
    }
    for product, expected in bidirectional.items():
        actual = sw._maxfrank_catalog_length_mm(selection(product, type_name=product), f"EGCOBOX {product}-C30-h200")
        assert actual == expected, (product, actual, expected)

    # Exact text length always wins over catalog standard.
    row = {
        "source_text": "EGCOBOX MXL20-VS-C30-h200 - 0,93m",
        "selection": selection("MXL20", type_name="MXL"),
        "snapshot": {}, "mapping": {"source_overrides": {}}, "note": "",
    }
    length, origin, warnings = sw._source_element_length_info(row)
    assert (length, origin, warnings) == (930, "délka z označení / poznámky", [])

    # Standard matrix type is now exact, not a generic 1000 mm guess.
    row["source_text"] = "EGCOBOX MXL20-VS-C30-h200"
    length, origin, warnings = sw._source_element_length_info(row)
    assert length == 1000 and origin == "délka z katalogové řady Egcobox" and not warnings

    # Corner assemblies and unknown products are never guessed.
    assert sw._maxfrank_catalog_length_mm(selection("MXL20-CO-L", type_name="MXL-CO"), "EGCOBOX MXL20-CO-L") is None
    unknown_row = {
        "source_text": "EGCOBOX SPECIAL-X",
        "selection": selection("SPECIAL-X", type_name="SPECIAL"),
        "snapshot": {}, "mapping": {"source_overrides": {}}, "note": "",
    }
    assert sw._source_element_length_info(unknown_row)[0] is None

    assert sw._compression_category("betonová tlaková ložiska") == "bearing"
    assert sw._compression_category("tlačené ocelové pruty") == "without"
    assert sw._compression_category("tlaková ložiska / tlačené ocelové pruty dle dílčího prvku") == "unknown"

    generated = substitution.read_text(encoding="utf-8")
    assert 'SUBSTITUTION_MODULE_VERSION = "1.1.3"' in generated
    assert "_maxfrank_catalog_length_mm" in generated
    assert "odhad 1000 mm" not in generated
    assert "neznámá délka návrh zastaví" in generated
    assert 'APP_VERSION = "1.1.3"' in app.read_text(encoding="utf-8")
    assert not any(OUT.rglob("*.pyc"))
    assert not any(p.name == "__pycache__" for p in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.1.3\n"
        "- Záměna jeden prvek za jeden nadále vybírá nejbližší shodný nebo kratší HIT, který přenese celkovou únosnost původního prvku.\n"
        "- Délky aktuálních řad MAX FRANK Egcobox MM/MXL, jejich výškových variant a smykových řad VM/VXL se nyní určují přímo z katalogové třídy.\n"
        "- Zohledněny jsou rozdílné délky krátkých K-prvků i rozdíly mezi jednosměrnými a obousměrnými VM-K/VXL-K±, např. VM86-K 300 mm versus VM86-K± 310 mm.\n"
        "- Explicitní délka v označení nebo poznámce, např. 0,93 m, má před katalogovou standardní délkou přednost.\n"
        "- Neznámá délka se již nikdy nenahrazuje obecným odhadem 1000 mm; automatický návrh se zastaví a vyžádá ruční potvrzení délky.\n"
        "- Složené rohové prvky CO s rozdílnými dílčími délkami a smíšeným tlakovým přenosem se automaticky nepřevádějí jako jeden prvek.\n"
        "- Zachována je přísná vazba tlakových ložisek: s ložisky pouze za HIT s CSB, bez ložisek pouze za HIT bez CSB nebo s tlačenými pruty.\n",
        encoding="utf-8",
    )

    previous_manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    paths = [str(item["path"]) for item in previous_manifest.get("files", [])]
    manifest_files = []
    for rel in paths:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.1.3/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.1.3",
        "notes": "TURTO ISO: katalogově přesné délky Egcobox, nejbližší kratší HIT a bezpečné zachování tlakových ložisek.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.1.3")


if __name__ == "__main__":
    main()
