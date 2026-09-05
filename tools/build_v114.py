from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.1.3"
OUT = ROOT / "updates" / "1.1.4"


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


def patch_substitution(text: str) -> str:
    text = replace_once(
        text,
        'SUBSTITUTION_MODULE_VERSION = "1.1.3"',
        'SUBSTITUTION_MODULE_VERSION = "1.1.4"',
        "substitution module version",
    )

    old_lengths = '''def _target_length_options(source_length_mm: int, allowed_codes: set[int] | None = None) -> list[tuple[int, int]]:
    allowed = set(allowed_codes or {code for code, _length in _STANDARD_LENGTHS})
    return [(code, length) for code, length in _STANDARD_LENGTHS if code in allowed and length <= int(source_length_mm)]
'''
    new_lengths = '''def _length_is_allowed(source_length_mm: int, target_length_mm: int) -> bool:
    """Délková kompatibilita jednoho zdrojového prvku a jednoho HIT.

    Standardně nesmí být HIT delší než původní prvek. Výslovně povolenou
    výjimkou je zdrojový prvek délky 300 mm, který lze nahradit standardním
    HIT délky 333 mm. Únosnost se i v tomto případě kontroluje na celý prvek.
    """
    source = int(source_length_mm)
    target = int(target_length_mm)
    return target <= source or (source == 300 and target == 333)


def _length_relation_text(source_length_mm: int, target_length_mm: int) -> str:
    source = int(source_length_mm)
    target = int(target_length_mm)
    if source == target:
        return "shodná délka"
    if source == 300 and target == 333:
        return "povolená výjimka 300→333 mm"
    if target < source:
        return "nejbližší kratší vyhovující délka"
    return "nepřípustná delší délka"


def _target_length_options(source_length_mm: int, allowed_codes: set[int] | None = None) -> list[tuple[int, int]]:
    allowed = set(allowed_codes or {code for code, _length in _STANDARD_LENGTHS})
    return [
        (code, length)
        for code, length in _STANDARD_LENGTHS
        if code in allowed and _length_is_allowed(int(source_length_mm), length)
    ]
'''
    text = replace_once(text, old_lengths, new_lengths, "length compatibility")

    text = replace_once(
        text,
        '    length_gap = max(0, int(source_length_mm) - int(candidate.physical_length_mm))',
        '    length_gap = abs(int(source_length_mm) - int(candidate.physical_length_mm))',
        "nearest length ranking",
    )
    text = replace_once(
        text,
        '                if candidate.physical_length_mm > source_length:\n                    continue',
        '                if not _length_is_allowed(source_length, candidate.physical_length_mm):\n                    continue',
        "candidate length filter",
    )
    text = replace_once(
        text,
        '        errors.append(f"pro délku zdroje {length_mm} mm neexistuje shodná ani kratší standardní délka HIT")',
        '        errors.append(f"pro délku zdroje {length_mm} mm neexistuje přípustná standardní délka HIT; u zdroje 300 mm je povolen také HIT 333 mm")',
        "metadata length error",
    )
    text = replace_once(
        text,
        '        return [], [f"není dostupná povolená délka HIT shodná nebo kratší než {source_length} mm (povoleno: {allowed_text or \'nic\'})"]',
        '        return [], [f"není dostupná přípustná délka HIT pro zdroj {source_length} mm (standardně shodná/kratší; u zdroje 300 mm také 333 mm; povoleno: {allowed_text or \'nic\'})"]',
        "design length error",
    )
    text = replace_once(
        text,
        '    relation = "shodná délka" if source_length == candidate.physical_length_mm else "nejbližší kratší vyhovující délka"',
        '    relation = _length_relation_text(source_length, candidate.physical_length_mm)',
        "calculation length relation",
    )
    text = replace_once(
        text,
        '                "Navrhuje se nejbližší shodná nebo kratší standardní délka HIT, která jako jeden prvek přenese stejnou únosnost. "',
        '                "Standardně se navrhuje nejbližší shodná nebo kratší délka HIT; u zdroje 300 mm je přípustný také HIT 333 mm, pokud staticky vyhoví. "',
        "header length explanation",
    )
    text = replace_once(
        text,
        '                "HIT nesmí být delší než zdroj; z povolených délek se upřednostní nejbližší kratší vyhovující prvek. "',
        '                "HIT standardně nesmí být delší než zdroj; výjimkou je zdroj 300 mm, který lze nahradit HIT 333 mm. Jinak se upřednostní nejbližší shodná nebo kratší vyhovující délka. "',
        "warning length explanation",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise RuntimeError(f"Base update not found: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    app = OUT / "app.pyw"
    app.write_text(
        replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "1.1.3"', 'APP_VERSION = "1.1.4"', "app version"),
        encoding="utf-8",
    )

    substitution = OUT / "substitution_workspace.py"
    substitution.write_text(patch_substitution(substitution.read_text(encoding="utf-8")), encoding="utf-8")

    compile_sources(OUT)

    sys.path.insert(0, str(OUT))
    import substitution_workspace as sw

    assert sw.SUBSTITUTION_MODULE_VERSION == "1.1.4"
    assert sw._length_is_allowed(300, 333)
    assert sw._length_is_allowed(300, 300)
    assert sw._length_is_allowed(300, 250)
    assert not sw._length_is_allowed(299, 333)
    assert not sw._length_is_allowed(300, 500)
    assert sw._target_length_options(300) == [(33, 333), (25, 250)]
    assert sw._target_length_options(300, {25}) == [(25, 250)]
    assert sw._target_length_options(299) == [(25, 250)]
    assert sw._length_relation_text(300, 333) == "povolená výjimka 300→333 mm"

    source_row = {
        "source_text": "Testovací smykový prvek - 0,3 m",
        "note": "",
        "selection": {},
        "mapping": {"source_overrides": {"source_length_mm": 300}},
        "snapshot": {
            "results": [
                {"kind": "shear", "value": 30.0, "unit": "kN/element"},
            ]
        },
    }
    source_total, warnings = sw.source_element_actions(source_row)
    assert not warnings and abs(source_total.v_pos - 30.0) < 1e-9
    target_actions, warnings = sw.source_actions(source_row, target_length_mm=333)
    assert not warnings and abs(target_actions.v_pos - 30.0 * 1000.0 / 333.0) < 1e-9

    generated = substitution.read_text(encoding="utf-8")
    assert "povolená výjimka 300→333 mm" in generated
    assert "výjimkou je zdroj 300 mm" in generated
    assert 'APP_VERSION = "1.1.4"' in app.read_text(encoding="utf-8")
    assert not any(OUT.rglob("*.pyc"))
    assert not any(path.name == "__pycache__" for path in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.1.4\n"
        "- U zdrojového prvku skutečné délky 300 mm je nově přípustná také standardní délka HIT 333 mm.\n"
        "- Výjimka platí pouze pro dvojici 300→333 mm; ostatní prvky se nadále nahrazují shodnou nebo kratší délkou.\n"
        "- Pro 300mm zdroj se nejprve zkouší 333mm HIT a potom 250mm HIT; vždy musí vyhovět celková únosnost jednoho prvku.\n"
        "- Přepočet hodnot /m i /prvek používá skutečnou cílovou délku 333 mm, takže se nemění bezpečnost statické kontroly.\n"
        "- Tabulka záměn a drobný výpočet označí tento případ textem „povolená výjimka 300→333 mm“.\n"
        "- Vazba tlakových ložisek zůstává beze změny a musí být shodná i u této délkové výjimky.\n",
        encoding="utf-8",
    )

    previous_manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    paths = [str(item["path"]) for item in previous_manifest.get("files", [])]
    manifest_files = []
    for rel in paths:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.1.4/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.1.4",
        "notes": "TURTO ISO: povolená délková výjimka 300 mm → HIT 333 mm při plné statické kontrole jednoho prvku.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.1.4")


if __name__ == "__main__":
    main()
