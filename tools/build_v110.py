from __future__ import annotations

import base64
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.0.4"
OUT = ROOT / "updates" / "1.1.0"
PARTS = ROOT / "tools" / "v110_parts"
MODULE_SHA256 = "9703ce931e437586011079811f066b54713686301ecad96746352dddbe8a4f14"


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


def assemble_module() -> bytes:
    files = sorted(PARTS.glob("substitution_workspace.b64.part*"), key=lambda p: p.name)
    if len(files) != 5:
        raise RuntimeError(f"Expected 5 substitution module parts, got {len(files)}")
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in files)
    data = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(data).hexdigest()
    if digest != MODULE_SHA256:
        raise RuntimeError(f"Substitution module SHA mismatch: {digest}")
    return data


def patch_app(text: str) -> str:
    text = replace_once(text, 'from hit_workspace import HitWorkspaceMixin\n', 'from hit_workspace import HitWorkspaceMixin\nfrom substitution_workspace import SubstitutionWorkspaceMixin\n', "substitution import")
    text = replace_once(text, 'APP_VERSION = "1.0.4"', 'APP_VERSION = "1.1.0"', "app version")
    text = replace_once(
        text,
        'class ThermalConnectorApp(HitWorkspaceMixin, ProjectWorkspaceMixin, tk.Tk):',
        'class ThermalConnectorApp(SubstitutionWorkspaceMixin, HitWorkspaceMixin, ProjectWorkspaceMixin, tk.Tk):',
        "application mixins",
    )
    text = replace_once(
        text,
        '        self._init_project_workspace()\n        self._init_hit_workspace()\n',
        '        self._init_project_workspace()\n        self._init_hit_workspace()\n        self._init_substitution_workspace()\n',
        "substitution initialization",
    )
    text = replace_once(
        text,
        '        self.hit_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))\n'
        '        self.main_notebook.add(self.project_tab, text="Projektové řádky")\n'
        '        self.main_notebook.add(self.lookup_tab, text="Databáze / detail nosníku")\n'
        '        self.main_notebook.add(self.hit_tab, text="Návrh HIT")\n\n'
        '        self._build_project_tab(self.project_tab)\n'
        '        self._build_lookup_body(self.lookup_tab)\n'
        '        self._build_hit_tab(self.hit_tab)\n'
        '        self.main_notebook.select(self.project_tab)\n',
        '        self.hit_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))\n'
        '        self.substitution_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))\n'
        '        self.main_notebook.add(self.project_tab, text="Projektové řádky")\n'
        '        self.main_notebook.add(self.lookup_tab, text="Databáze / detail nosníku")\n'
        '        self.main_notebook.add(self.hit_tab, text="Návrh HIT")\n'
        '        self.main_notebook.add(self.substitution_tab, text="Záměny za HIT")\n\n'
        '        self._build_project_tab(self.project_tab)\n'
        '        self._build_lookup_body(self.lookup_tab)\n'
        '        self._build_hit_tab(self.hit_tab)\n'
        '        self._build_substitution_tab(self.substitution_tab)\n'
        '        self.main_notebook.bind("<<NotebookTabChanged>>", self._on_substitution_tab_selected, add="+")\n'
        '        self.main_notebook.select(self.project_tab)\n',
        "substitution tab",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise RuntimeError(f"Base update not found: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    module_data = assemble_module()
    module_path = OUT / "substitution_workspace.py"
    module_path.write_bytes(module_data)

    app = OUT / "app.pyw"
    app_text = patch_app(app.read_text(encoding="utf-8"))
    app.write_text(app_text, encoding="utf-8")

    project_model = OUT / "project_model.py"
    model_text = project_model.read_text(encoding="utf-8")
    model_text = model_text.replace('"application":"TURTO – Databáze izolačních nosníků"', '"application":"TURTO ISO"')
    project_model.write_text(model_text, encoding="utf-8")

    compile_sources(OUT)

    # Static integration checks.
    generated_app = app.read_text(encoding="utf-8")
    generated_module = module_path.read_text(encoding="utf-8")
    assert 'APP_VERSION = "1.1.0"' in generated_app
    assert 'from substitution_workspace import SubstitutionWorkspaceMixin' in generated_app
    assert 'class ThermalConnectorApp(SubstitutionWorkspaceMixin, HitWorkspaceMixin, ProjectWorkspaceMixin, tk.Tk):' in generated_app
    assert 'text="Záměny za HIT"' in generated_app
    assert 'self._build_substitution_tab(self.substitution_tab)' in generated_app
    assert 'SUBSTITUTION_MODULE_VERSION = "1.1.0"' in generated_module
    assert 'Drobný statický výpočet' in generated_module
    assert 'Jde o předběžnou statickou záměnu M/N/V.' in generated_module

    # Pure logic regressions without starting Tk.
    sys.path.insert(0, str(OUT))
    import substitution_workspace as sw

    mock = {
        "snapshot": {
            "results": [
                {"kind": "moment", "label": "mRd,y", "negative": -30.0, "unit": "kNm/m"},
                {"kind": "shear", "label": "vRd,z", "positive": 50.0, "negative": -40.0, "unit": "kN/m"},
            ]
        }
    }
    actions, warnings = sw.source_actions(mock)
    assert not warnings
    assert actions.m_neg == 30.0 and actions.v_pos == 50.0 and actions.v_neg == 40.0
    assert sw.hit_type_order(actions)[0] == "MVX"
    assert sw.hit_concrete("C35/45") == "C30/37"
    assert sw.hit_concrete("C25/30") == "C25/30"
    assert sw.hit_concrete("C16/20") is None

    unsupported = {"snapshot": {"results": [{"kind": "shear", "value": 25, "unit": "kN"}]}}
    unsupported_actions, unsupported_warnings = sw.source_actions(unsupported)
    assert not unsupported_actions.has_any() and unsupported_warnings

    # Existing project mapping schema must retain the richer target dictionaries.
    import project_model as pm
    raw_row = {
        "id": "x",
        "position": "P001",
        "quantity": 1,
        "note": "",
        "selection": {
            "catalog_id": "c", "manufacturer": "Other", "model": "M", "type_name": "T", "generation": "1",
            "moment_class": "M1", "concrete_min": "C25/30", "shear_class": "V1", "cover": "C35", "height_mm": "200",
        },
        "snapshot": {"designation": "SOURCE", "results": [], "moment_text": "—", "shear_text": "—"},
        "mapping": {"status": "ok", "targets": [{"id": "HIT-X", "designation": "HIT-X", "calculation": "test"}], "selected_target_id": "HIT-X"},
    }
    normalized = pm.normalize_project_row(raw_row)
    assert normalized["mapping"]["targets"][0]["calculation"] == "test"
    assert normalized["mapping"]["selected_target_id"] == "HIT-X"

    assert not any(OUT.rglob("*.pyc"))
    assert not any(p.name == "__pycache__" for p in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.1.0\n"
        "- Přidána samostatná karta Záměny za HIT, která přebírá typy jiných výrobců z Projektových řádků.\n"
        "- Z katalogových výsledků původního prvku se automaticky sestaví směrové požadavky M+, M−, N+, N−, V+ a V− v jednotkách na metr.\n"
        "- Původní katalogové únosnosti se v první verzi používají konzervativně jako současně působící požadavek; nejde o přenos skutečných zatěžovacích kombinací.\n"
        "- Návrh používá stávající statické jádro HIT a hledá technicky přípustné typy podle směru účinků, výšky, betonu, krytí a povolených délek.\n"
        "- Tabulka záměn obsahuje původní typ, účinky, navržený HIT, využití, počet variant, rozhodující kontrolu a drobný statický výpočet.\n"
        "- Výsledek se ukládá přímo do projektového souboru .tinp a zobrazuje se také ve sloupci Převod v Projektových řádcích.\n"
        "- Přidáno kopírování tabulky a nativní Excel export.\n"
        "- Záměna je výslovně označena jako předběžná: neověřuje tuhost, deformace, požár, izolant, tlakový přenos, geometrii, kotvení, spáry ani montáž.\n",
        encoding="utf-8",
    )

    previous_manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    paths = [str(item["path"]) for item in previous_manifest.get("files", [])]
    if "substitution_workspace.py" not in paths:
        paths.append("substitution_workspace.py")
    manifest_files = []
    for rel in paths:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.1.0/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.1.0",
        "notes": "TURTO ISO: nová karta Záměny za HIT s konzervativním statickým převodem, tabulkou a Excel exportem.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.1.0")


if __name__ == "__main__":
    main()
