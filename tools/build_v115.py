from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.1.4"
OUT = ROOT / "updates" / "1.1.5"


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
        'SUBSTITUTION_MODULE_VERSION = "1.1.4"',
        'SUBSTITUTION_MODULE_VERSION = "1.1.5"',
        "substitution module version",
    )
    text = replace_once(
        text,
        '_TOL = 1e-9\n',
        '_TOL = 1e-9\n\n# Tabulka záměn musí sama prověřit všechny standardní délky HIT.\n# Zaškrtávače v kartě Návrh HIT jsou pouze filtrem ručního návrhu a nesmí\n# blokovat automatickou záměnu, zejména potřebný přechod 300 → 333 mm.\nSUBSTITUTION_LENGTH_CODES = frozenset({100, 50, 33, 25})\n',
        "substitution length constants",
    )
    text = replace_once(
        text,
        '        allowed_lengths = set(self.allowed_hit_lengths()) if hasattr(self, "allowed_hit_lengths") else {100, 50, 33, 25}\n',
        '        allowed_lengths = set(SUBSTITUTION_LENGTH_CODES)\n',
        "automatic substitution lengths",
    )
    text = replace_once(
        text,
        '            if not allowed_lengths:\n                fatal.append("v kartě Návrh HIT není povolena žádná délka")\n',
        '',
        "remove manual length blocker",
    )
    text = replace_once(
        text,
        '                "Standardně se navrhuje nejbližší shodná nebo kratší délka HIT; u zdroje 300 mm je přípustný také HIT 333 mm, pokud staticky vyhoví. "\n                "Délky aktuálních řad Egcobox MM/MXL a VM/VXL se určují přímo z katalogové třídy; neznámá délka návrh zastaví."',
        '                "Standardně se navrhuje nejbližší shodná nebo kratší délka HIT; u zdroje 300 mm je přípustný také HIT 333 mm, pokud staticky vyhoví. "\n                "Záměny automaticky prověřují všechny standardní délky HIT bez ohledu na zaškrtávače v kartě Návrh HIT. "\n                "Délky aktuálních řad Egcobox MM/MXL a VM/VXL se určují přímo z katalogové třídy; neznámá délka návrh zastaví."',
        "header automatic lengths",
    )
    text = replace_once(
        text,
        '                "HIT standardně nesmí být delší než zdroj; výjimkou je zdroj 300 mm, který lze nahradit HIT 333 mm. Jinak se upřednostní nejbližší shodná nebo kratší vyhovující délka. "\n                "Prvek s tlakovými ložisky se nahradí pouze HIT s tlakovými ložisky, prvek bez nich pouze provedením bez nich. "',
        '                "HIT standardně nesmí být delší než zdroj; výjimkou je zdroj 300 mm, který lze nahradit HIT 333 mm. Jinak se upřednostní nejbližší shodná nebo kratší vyhovující délka. "\n                "Pro automatickou záměnu se vždy prověří délky 1000, 500, 333 a 250 mm; volby délek v ručním návrhu HIT se zde nepoužívají. "\n                "Prvek s tlakovými ložisky se nahradí pouze HIT s tlakovými ložisky, prvek bez nich pouze provedením bez nich. "',
        "warning automatic lengths",
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
        replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "1.1.4"', 'APP_VERSION = "1.1.5"', "app version"),
        encoding="utf-8",
    )

    substitution = OUT / "substitution_workspace.py"
    substitution.write_text(patch_substitution(substitution.read_text(encoding="utf-8")), encoding="utf-8")

    compile_sources(OUT)

    sys.path.insert(0, str(OUT))
    from bulk_import_engine import preprocess_bulk_designation
    from catalog_engine import CatalogDatabase
    from hit_core import Candidate
    from project_model import create_project_row
    import substitution_workspace as sw

    assert sw.SUBSTITUTION_MODULE_VERSION == "1.1.5"
    assert sw.SUBSTITUTION_LENGTH_CODES == frozenset({100, 50, 33, 25})
    assert sw._target_length_options(300, set(sw.SUBSTITUTION_LENGTH_CODES)) == [(33, 333), (25, 250)]

    class FakeHitDatabase:
        def proposal_candidates(
            self, connection_type, series, height, cover, concrete, actions,
            lengths, include_offsets=False, load_distance_x=0.0,
        ):
            if connection_type != "ZVX" or 33 not in set(lengths):
                return [], f"{connection_type}: testovací databáze bez varianty", {}
            requirement = max(actions.v_pos, actions.v_neg)
            rows = []
            for code, vrd in (("0500", 163.9), ("0302", 172.1)):
                utilization = 0.0 if requirement <= 0 else requirement / vrd
                if utilization <= 1.0 + 1e-9:
                    rows.append(Candidate(
                        series, "ZVX", code, 33, "08", height, concrete,
                        0.0, vrd, 0.0, vrd, 99, cover, height,
                        utilization, "regresní test VXL48-K",
                    ))
            return rows, "", {}

    catalog = CatalogDatabase(OUT / "catalogs")
    cases = (
        (
            "EGCOBOX VXL Z 48-K-C30-h160-REI120-SW",
            "without",
            "HIT-SP ZVX-0500-16-033-30-08",
        ),
        (
            "EGCOBOX VXL48-K-C30-h160-REI120-SW",
            "bearing",
            "HIT-SP ZVX-0302-16-033-30-08",
        ),
    )
    for index, (raw, expected_compression, expected_target) in enumerate(cases, start=1):
        clean, note = preprocess_bulk_designation(raw)
        source = catalog.resolve_designation(clean, preferred_concrete="C25/30")
        row = create_project_row(source, position=f"P{index:03d}", quantity=1, note=note, source_text=raw)
        meta = sw.source_metadata(row)
        assert meta["source_length_mm"] == 300
        assert meta["target_series"] == "SP"
        assert meta["target_cover_mm"] == 30
        assert meta["target_height_mm"] == 160
        assert meta["source_compression_category"] == expected_compression
        assert not meta["errors"]
        targets, errors = sw.design_targets(
            FakeHitDatabase(),
            row=row,
            metadata=meta,
            allowed_length_codes=set(sw.SUBSTITUTION_LENGTH_CODES),
        )
        assert targets, (raw, errors)
        assert targets[0]["designation"] == expected_target, (raw, targets[0]["designation"])
        assert targets[0]["length_mm"] == 333
        assert targets[0]["compression_category"] == expected_compression
        assert float(targets[0]["v_capacity_element"]) + 1e-9 >= 48.6
        assert "povolená výjimka 300→333 mm" in targets[0]["calculation"]

    generated = substitution.read_text(encoding="utf-8")
    method = generated.split("    def design_substitutions", 1)[1].split("    def _output_rows", 1)[0]
    assert "allowed_lengths = set(SUBSTITUTION_LENGTH_CODES)" in method
    assert "self.allowed_hit_lengths" not in method
    assert "v kartě Návrh HIT není povolena žádná délka" not in generated
    assert "volby délek v ručním návrhu HIT se zde nepoužívají" in generated
    assert 'APP_VERSION = "1.1.5"' in app.read_text(encoding="utf-8")
    assert not any(OUT.rglob("*.pyc"))
    assert not any(path.name == "__pycache__" for path in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.1.5\n"
        "- Opravena záměna krátkých smykových prvků Egcobox, zejména VXL Z 48-K a VXL48-K délky 300 mm.\n"
        "- Automatická tabulka záměn nyní vždy prověřuje všechny standardní délky HIT 1000, 500, 333 a 250 mm.\n"
        "- Zaškrtávače Povolené délky v kartě Návrh HIT zůstávají filtrem pouze pro ruční návrh a již automatickou záměnu neblokují.\n"
        "- VXL Z 48-K bez tlakových ložisek se při h160, C25/30 a cnom 30 může převést na HIT-SP ZVX-0500-16-033-30-08, pokud vyhoví požadované únosnosti.\n"
        "- VXL48-K s tlakovými ložisky se za stejných podmínek může převést na HIT-SP ZVX-0302-16-033-30-08.\n"
        "- U obou případů zůstává plná kontrola únosnosti jednoho prvku, délková výjimka 300→333 mm a přesná vazba s tlakovými ložisky / bez nich.\n",
        encoding="utf-8",
    )

    previous_manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    paths = [str(item["path"]) for item in previous_manifest.get("files", [])]
    manifest_files = []
    for rel in paths:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.1.5/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.1.5",
        "notes": "TURTO ISO: oprava automatických záměn VXL Z 48-K / VXL48-K a nezávislé prověření všech standardních délek HIT.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.1.5")


if __name__ == "__main__":
    main()
