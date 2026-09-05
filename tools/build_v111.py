from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.1.0"
OUT = ROOT / "updates" / "1.1.1"
TEMPLATE = ROOT / "tools" / "v111_substitution_workspace.py"


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


def patch_project_model(text: str) -> str:
    text = replace_once(text, "PROJECT_SCHEMA_VERSION = 3", "PROJECT_SCHEMA_VERSION = 4", "project schema")
    old_create = '''def create_project_row(result: QueryResult, *, position: str, quantity: int=1, note: str="", row_id: str|None=None) -> dict[str,Any]:
    return {"id":row_id or uuid.uuid4().hex,"position":str(position).strip(),"quantity":safe_quantity(quantity),"note":str(note).strip(),
            "selection":selection_from_result(result),"snapshot":snapshot_from_result(result),
            "mapping":{"status":"not_run","targets":[],"selected_target_id":None}}
'''
    new_create = '''def create_project_row(result: QueryResult, *, position: str, quantity: int=1, note: str="", source_text: str="", row_id: str|None=None) -> dict[str,Any]:
    return {"id":row_id or uuid.uuid4().hex,"position":str(position).strip(),"quantity":safe_quantity(quantity),"note":str(note).strip(),
            "source_text":str(source_text or result.designation).strip(),
            "selection":selection_from_result(result),"snapshot":snapshot_from_result(result),
            "mapping":{"status":"not_run","targets":[],"selected_target_id":None,"source_meta":{},"warnings":[],"errors":[],"estimated_type":""}}
'''
    text = replace_once(text, old_create, new_create, "project row source text")
    old_mapping = '''    mapping=raw.get("mapping") if isinstance(raw.get("mapping"),dict) else {}
    mapping={"status":str(mapping.get("status","not_run")),"targets":list(mapping.get("targets",[])) if isinstance(mapping.get("targets",[]),list) else [],"selected_target_id":mapping.get("selected_target_id")}
    return {"id":str(raw.get("id") or uuid.uuid4().hex),"position":str(raw.get("position","")).strip(),"quantity":safe_quantity(raw.get("quantity",1)),"note":str(raw.get("note","")).strip(),
            "selection":{"catalog_id":str(selection["catalog_id"]),"manufacturer":str(selection["manufacturer"]),"model":str(selection["model"]),"type_name":str(selection["type_name"]),"generation":str(selection["generation"]),"moment_class":str(selection["moment_class"]),"concrete_min":str(selection["concrete_min"]),"shear_class":str(selection["shear_class"]),"cover":str(selection["cover"]),"height_mm":str(selection["height_mm"])},
            "snapshot":snap,"mapping":mapping}
'''
    new_mapping = '''    raw_mapping=raw.get("mapping") if isinstance(raw.get("mapping"),dict) else {}
    mapping={
        "status":str(raw_mapping.get("status","not_run")),
        "targets":list(raw_mapping.get("targets",[])) if isinstance(raw_mapping.get("targets",[]),list) else [],
        "selected_target_id":raw_mapping.get("selected_target_id"),
        "source_meta":dict(raw_mapping.get("source_meta",{})) if isinstance(raw_mapping.get("source_meta",{}),dict) else {},
        "warnings":list(raw_mapping.get("warnings",[])) if isinstance(raw_mapping.get("warnings",[]),list) else [],
        "errors":list(raw_mapping.get("errors",[])) if isinstance(raw_mapping.get("errors",[]),list) else [],
        "estimated_type":str(raw_mapping.get("estimated_type","")),
    }
    return {"id":str(raw.get("id") or uuid.uuid4().hex),"position":str(raw.get("position","")).strip(),"quantity":safe_quantity(raw.get("quantity",1)),"note":str(raw.get("note","")).strip(),
            "source_text":str(raw.get("source_text") or snap.get("designation","")).strip(),
            "selection":{"catalog_id":str(selection["catalog_id"]),"manufacturer":str(selection["manufacturer"]),"model":str(selection["model"]),"type_name":str(selection["type_name"]),"generation":str(selection["generation"]),"moment_class":str(selection["moment_class"]),"concrete_min":str(selection["concrete_min"]),"shear_class":str(selection["shear_class"]),"cover":str(selection["cover"]),"height_mm":str(selection["height_mm"])},
            "snapshot":snap,"mapping":mapping}
'''
    text = replace_once(text, old_mapping, new_mapping, "mapping metadata")
    text = replace_once(text, "if version not in {1,2,3}:", "if version not in {1,2,3,4}:", "project schema reader")
    return text


def patch_bulk_engine(text: str) -> str:
    text = replace_once(
        text,
        '    designation: str\n    note: str = ""\n',
        '    designation: str\n    source_designation: str = ""\n    note: str = ""\n',
        "bulk source designation field",
    )
    text = replace_once(
        text,
        '            position, quantity, designation, note = interpret_bulk_parts(parts)\n            designation, note = preprocess_bulk_designation(designation, note)\n',
        '            position, quantity, designation, note = interpret_bulk_parts(parts)\n'
        '            source_designation = designation\n'
        '            designation, note = preprocess_bulk_designation(designation, note)\n',
        "capture raw designation",
    )
    text = replace_once(
        text,
        '            designation=designation,\n            note=note,\n',
        '            designation=designation,\n            source_designation=source_designation,\n            note=note,\n',
        "store raw designation",
    )
    return text


def patch_bulk_dialog(text: str) -> str:
    return replace_once(
        text,
        '                "source_text": item.raw,\n',
        '                "source_text": item.source_designation or item.raw,\n',
        "bulk result source text",
    )


def patch_project_ui(text: str) -> str:
    text = replace_once(
        text,
        'from bulk_import import BulkImportDialog\n',
        'from bulk_import import BulkImportDialog\nfrom bulk_import_engine import preprocess_bulk_designation\n',
        "preprocess import",
    )
    old_quick = '''            quantity = safe_quantity(self.project_quick_quantity_var.get())
            result = self.database.resolve_designation(designation, preferred_concrete=self.project_concrete_var.get())
            position = self.project_quick_position_var.get().strip() or self.project.next_position()
            row = create_project_row(
                result,
                position=position,
                quantity=quantity,
                note=self.project_quick_note_var.get(),
            )
'''
    new_quick = '''            quantity = safe_quantity(self.project_quick_quantity_var.get())
            lookup_designation, normalized_note = preprocess_bulk_designation(designation, self.project_quick_note_var.get())
            result = self.database.resolve_designation(lookup_designation, preferred_concrete=self.project_concrete_var.get())
            position = self.project_quick_position_var.get().strip() or self.project.next_position()
            row = create_project_row(
                result,
                position=position,
                quantity=quantity,
                note=normalized_note,
                source_text=designation,
            )
'''
    text = replace_once(text, old_quick, new_quick, "quick source preservation")
    text = replace_once(
        text,
        '                note=str(row.get("note", "")),\n            )\n            self.project.replace(str(row["id"]), replacement)\n',
        '                note=str(row.get("note", "")),\n'
        '                source_text=str(row.get("source_text", "")),\n'
        '            )\n'
        '            self.project.replace(str(row["id"]), replacement)\n',
        "preserve source on concrete update",
    )
    text = replace_once(
        text,
        '                note=str(imported.get("note", "")),\n            )\n            self.project.add(row)\n',
        '                note=str(imported.get("note", "")),\n'
        '                source_text=str(imported.get("source_text", "")) or result.designation,\n'
        '            )\n'
        '            self.project.add(row)\n',
        "bulk source preservation",
    )
    text = replace_once(
        text,
        '            replacement = create_project_row(result, row_id=row_id, **dialog.result)\n',
        '            replacement = create_project_row(result, row_id=row_id, source_text=str(existing.get("source_text", "")) or result.designation, **dialog.result)\n',
        "editor preserve source",
    )
    text = replace_once(
        text,
        '            replacement = create_project_row(result, **dialog.result)\n',
        '            replacement = create_project_row(result, source_text=result.designation, **dialog.result)\n',
        "editor new source",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise RuntimeError(f"Base update not found: {BASE}")
    if not TEMPLATE.exists():
        raise RuntimeError(f"Template not found: {TEMPLATE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    (OUT / "substitution_workspace.py").write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")

    app = OUT / "app.pyw"
    app.write_text(replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "1.1.0"', 'APP_VERSION = "1.1.1"', "app version"), encoding="utf-8")

    model = OUT / "project_model.py"
    model.write_text(patch_project_model(model.read_text(encoding="utf-8")), encoding="utf-8")

    project_ui = OUT / "project_ui.py"
    project_ui.write_text(patch_project_ui(project_ui.read_text(encoding="utf-8")), encoding="utf-8")

    bulk_engine = OUT / "bulk_import_engine.py"
    bulk_engine.write_text(patch_bulk_engine(bulk_engine.read_text(encoding="utf-8")), encoding="utf-8")

    bulk_dialog = OUT / "bulk_import.py"
    bulk_dialog.write_text(patch_bulk_dialog(bulk_dialog.read_text(encoding="utf-8")), encoding="utf-8")

    compile_sources(OUT)

    sys.path.insert(0, str(OUT))
    import substitution_workspace as sw
    import project_model as pm
    from hit_core import Candidate

    source_row = {
        "source_text": "EGCOBOX MXL35-VS-C30-h200-REI120-SW",
        "note": "Geometrie WU: 280 mm | Specifikace: REI120-SW",
        "selection": {"manufacturer": "MAX FRANK", "model": "XL", "type_name": "MXL", "cover": "C30", "height_mm": "200", "concrete_min": "C25/30"},
        "snapshot": {"designation": "Egcobox MXL35-VS-C30-h200", "insulation_thickness_mm": 120, "results": [
            {"kind": "moment", "value": -38.1, "unit": "kNm/element"},
            {"kind": "shear", "value": 48.7, "unit": "kN/element"},
        ]},
    }
    actions, warnings = sw.source_actions(source_row)
    assert not warnings
    assert actions.m_neg == 38.1 and actions.v_pos == 48.7
    meta = sw.source_metadata(source_row)
    assert meta["target_series"] == "SP" and meta["target_cover_mm"] == 30 and meta["target_height_mm"] == 200
    assert meta["geometry_target"] == "OU" and meta["geometry_bx_mm"] == 280

    plain_meta = dict(meta, geometry_target="", geometry_bx_mm=None, geometry_display="", warnings=[])
    c0605 = Candidate("SP", "MVX", "0605", 100, "", 170, "C25/30", -38.2, 80.0, -40.0, 0.0, 1, 30, 200, 0.989, "test")
    c0704 = Candidate("SP", "MVX", "0704", 100, "", 170, "C25/30", -38.2, 64.0, -45.0, 0.0, 1, 30, 200, 0.907, "test")
    order = sw.hit_type_order(actions, 30)
    assert sw._component_ok(c0605, actions) and sw._component_ok(c0704, actions)
    assert sw._candidate_rank(c0704, actions, order) < sw._candidate_rank(c0605, actions, order)
    assert sw.target_dict(c0704, actions, plain_meta)["calculation"].startswith("M−")

    class Dummy:
        catalog = {"id": "c", "edition": "e", "publication_label": "p", "publication_date": "", "source_filename": ""}
        family = {"manufacturer": "MAX FRANK", "model": "XL", "type": "MXL", "generation": "g"}
        record = {"moment_class": "MXL35", "concrete_min": "C25/30", "shear_class": "VS", "cover": "C30", "height_mm": "200"}
        designation = "Egcobox MXL35-VS-C30-h200"
        results = source_row["snapshot"]["results"]
        all_results_text = ""
        moment_text = ""
        shear_text = ""
        other_text = ""
        insulation_thickness_mm = 120
        insulation_text = "120 mm"
        compression_transfer = ""
        source_pages = []

    project_row = pm.create_project_row(Dummy(), position="P001", source_text=source_row["source_text"])
    normalized = pm.normalize_project_row(project_row)
    assert normalized["source_text"] == source_row["source_text"]
    assert pm.PROJECT_SCHEMA_VERSION == 4

    import bulk_import_engine as bie
    clean, note = bie.preprocess_bulk_designation("EGCOBOX MXL25-WU280-VS-C30-h200-REI120-SW - 0,93m")
    assert "WU" in clean and "280" not in clean
    assert "Geometrie WU: 280 mm" in note and "Délka prvku: 0,93 m" in note

    generated = (OUT / "substitution_workspace.py").read_text(encoding="utf-8")
    assert 'SUBSTITUTION_MODULE_VERSION = "1.1.1"' in generated
    assert "kNm/element" in generated and "HIT-SP odpovídá izolantu 120 mm" in generated
    assert 'APP_VERSION = "1.1.1"' in app.read_text(encoding="utf-8")
    assert not any(OUT.rglob("*.pyc"))
    assert not any(p.name == "__pycache__" for p in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.1.1\n"
        "- Opravena nefunkční záměna Egcobox: hodnoty kNm/element a kN/element se u známého jedno-metrového prvku MAX FRANK správně převádějí na srovnávací hodnoty na metr.\n"
        "- Řada HIT se určuje automaticky podle izolantu: 80 mm = HIT-HP, 120 mm = HIT-SP. Krytí, výška a beton se přebírají z původního prvku.\n"
        "- Kandidát musí samostatně splnit momentovou, smykovou a normálovou únosnost. U MVX/MVXL se navíc informativně zobrazuje interakční využití M-V.\n"
        "- Výběr MVX je řazen podle minimální potřebné výzbroje, nikoli podle náhodně nejvyššího využití; při shodném součtu se upřednostní menší smykový kód.\n"
        "- Bez geometrického požadavku se nenabízejí OD/OU/WD/WU. Geometrie Egcobox WU280 se převádí na HIT MVX-OU280 a kontroluje rozsah bx.\n"
        "- Původní text označení se nově uchovává v projektu; lze jej upravit přímo v kartě Záměny za HIT.\n"
        "- Tabulka záměn nově zobrazuje izolant, řadu HIT, zdrojové/cílové krytí a výšku, geometrii, cílové kapacity a drobný výpočet poměrů.\n"
        "- Požární odolnost REI se v této fázi vědomě neposuzuje a návrh neblokuje.\n",
        encoding="utf-8",
    )

    previous_manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    paths = [str(item["path"]) for item in previous_manifest.get("files", [])]
    manifest_files = []
    for rel in paths:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.1.1/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.1.1",
        "notes": "TURTO ISO: opravený převod Egcobox /element, automatické přenesení izolantu, cnom a výšky a kapacitně řazená tabulka záměn.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.1.1")


if __name__ == "__main__":
    main()
