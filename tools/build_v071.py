from __future__ import annotations

import base64
import gzip
import hashlib
import importlib
import json
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.12"
OUT = ROOT / "updates" / "0.7.1"
HIT_WORKSPACE_TEMPLATE = ROOT / "tools" / "v071_hit_workspace.py"
HIT_LEGACY = ROOT / "hit" / "hit_design.pyw"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_app(text: str) -> str:
    text = replace_once(
        text,
        "from project_ui import ProjectWorkspaceMixin\n",
        "from project_ui import ProjectWorkspaceMixin\nfrom hit_workspace import HitWorkspaceMixin\n",
        "HIT workspace import",
    )
    text = replace_once(text, 'APP_VERSION = "0.6.12"', 'APP_VERSION = "0.7.1"', "app version")
    text = replace_once(
        text,
        "class ThermalConnectorApp(ProjectWorkspaceMixin, tk.Tk):",
        "class ThermalConnectorApp(HitWorkspaceMixin, ProjectWorkspaceMixin, tk.Tk):",
        "app mixins",
    )
    text = replace_once(
        text,
        "        self._init_project_workspace()\n",
        "        self._init_project_workspace()\n        self._init_hit_workspace()\n",
        "HIT workspace init",
    )

    old_notebook = '''        self.project_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
        self.lookup_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
        self.main_notebook.add(self.project_tab, text="Projektové řádky")
        self.main_notebook.add(self.lookup_tab, text="Databáze / detail nosníku")

        self._build_project_tab(self.project_tab)
        self._build_lookup_body(self.lookup_tab)
        self.main_notebook.select(self.project_tab)
'''
    new_notebook = '''        self.project_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
        self.lookup_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
        self.hit_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
        self.main_notebook.add(self.project_tab, text="Projektové řádky")
        self.main_notebook.add(self.lookup_tab, text="Databáze / detail nosníku")
        self.main_notebook.add(self.hit_tab, text="Návrh HIT")

        self._build_project_tab(self.project_tab)
        self._build_lookup_body(self.lookup_tab)
        self._build_hit_tab(self.hit_tab)
        self.main_notebook.select(self.project_tab)
'''
    text = replace_once(text, old_notebook, new_notebook, "HIT notebook tab")
    return text


def build_hit_core() -> str:
    """Use the exact standalone HIT calculation core as the integrated engine."""
    source = HIT_LEGACY.read_text(encoding="utf-8")
    marker = "\nclass CandidateDialog(tk.Toplevel):"
    if marker not in source:
        raise RuntimeError("HIT legacy source no longer contains the expected CandidateDialog marker")
    core = source.split(marker, 1)[0].rstrip() + "\n"
    core = replace_once(core, 'APP_VERSION = "0.2.0"', 'APP_VERSION = "0.3.0"', "HIT engine label")

    # Metadata access used by the integrated UI; calculation logic is unchanged.
    old = '        self.data = json.loads(raw.decode("utf-8"))\n        self.records = []\n'
    new = (
        '        self.data = json.loads(raw.decode("utf-8"))\n'
        '        self.source_document = str(self.data.get("source_document", "CONF-DOP HIT-HP/SP-07-23"))\n'
        '        self.source_sha256 = str(self.data.get("source_sha256", ""))\n'
        '        self.records = []\n'
    )
    core = replace_once(core, old, new, "HIT metadata properties")
    return core


def synthetic_hit_test(out: Path) -> None:
    sys.path.insert(0, str(out))
    try:
        module = importlib.import_module("hit_core")
        payload = {
            "schema_version": 1,
            "catalog_id": "test-hit",
            "source_document": "synthetic",
            "source_sha256": "abc123",
            "covers_mm": [30, 35, 50],
            "concretes": ["C20/25", "C25/30", "C30/37"],
            "ratio_min_m": 0.15,
            "sections": [
                [
                    ["HIT-HP MVX-1234-hh-100-cc"],
                    [[165, 10, 10, 20, 5, 12, 12, 24, 6, 14, 14, 28, 7]],
                    9,
                ],
                [
                    ["HIT-SP MVX-4321-hh-050-cc-WU"],
                    [[165, 10, 10, 20, 5, 12, 12, 24, 6, 14, 14, 28, 7]],
                    11,
                ],
            ],
        }
        temp = out / "_synthetic_hit.json.gz.b64"
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        temp.write_text(base64.b64encode(gzip.compress(raw, 9)).decode("ascii"), encoding="ascii")
        db = module.HitDatabase(temp)
        assert db.source_document == "synthetic" and db.source_sha256 == "abc123"

        candidates, error = db.candidates("HP", 200, 35, "C25/30", 5.0, 5.0, {100}, False)
        assert not error and candidates
        candidate = candidates[0]
        assert candidate.designation == "HIT-HP MVX-1234-200-100-35"
        assert candidate.h_table == 165 and candidate.height == 200 and candidate.cover == 35
        assert candidate.physical_length_mm == 1000
        assert 0 < candidate.utilization <= 1.0

        _none, ratio_error = db.candidates("HP", 200, 35, "C25/30", 1.0, 10.0, {100}, False)
        assert "0,150" in ratio_error

        offsets_hidden, offset_error = db.candidates("SP", 200, 35, "C25/30", 5.0, 5.0, {50}, False)
        assert not offset_error and offsets_hidden == []
        offsets, offset_error = db.candidates("SP", 200, 35, "C25/30", 5.0, 5.0, {50}, True)
        assert not offset_error and offsets and offsets[0].suffix == "WU"
        assert offsets[0].designation == "HIT-SP MVX-4321-200-050-35-WU"
    finally:
        try:
            (out / "_synthetic_hit.json.gz.b64").unlink()
        except FileNotFoundError:
            pass
        sys.path.remove(str(out))
        sys.modules.pop("hit_core", None)


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if not HIT_WORKSPACE_TEMPLATE.exists():
        raise SystemExit(f"Missing HIT workspace template: {HIT_WORKSPACE_TEMPLATE}")
    if not HIT_LEGACY.exists():
        raise SystemExit(f"Missing standalone HIT source: {HIT_LEGACY}")

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    app_path = OUT / "app.pyw"
    app_path.write_text(patch_app(app_path.read_text(encoding="utf-8")), encoding="utf-8")
    (OUT / "hit_core.py").write_text(build_hit_core(), encoding="utf-8")
    shutil.copy2(HIT_WORKSPACE_TEMPLATE, OUT / "hit_workspace.py")

    notes = (
        "TURTO v0.7.1\n"
        "- Samostatný návrhář HIT v0.3.0 je integrován do hlavního TURTO jako nová karta „Návrh HIT“.\n"
        "- Výpočet používá stejné jádro jako samostatný HIT: HP/SP MVX, tabulkovou výšku h−cnom, C20/25 až C30/37, podmínku |MEd|/|VEd| ≥ 0,15 m a lineární M–V obálku M1/V1–M2/V2.\n"
        "- Zachováno je přímé řádkové zadávání, automatický přepočet a ruční volba jiné vyhovující varianty.\n"
        "- Lze povolit délky 1000/500/250 mm a varianty OD/OU/WD/WU.\n"
        "- Integrovaný modul nejprve zkusí použít existující lokální databázi ze samostatného TURTO HIT; není-li dostupná, lze vybrat původní DoP a vytvořit data lokálně.\n"
        "- Projektové provazby jsou v této první integrované verzi záměrně vypnuté; připraven je interní strukturovaný výstup pro budoucí propojení s projektovými řádky a náhradami výrobců.\n"
    )
    (OUT / "RELEASE_NOTES.txt").write_text(notes, encoding="utf-8")

    compile_files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_workspace.py",
    ]
    for rel in compile_files:
        py_compile.compile(str(OUT / rel), doraise=True)

    synthetic_hit_test(OUT)

    app_text = app_path.read_text(encoding="utf-8")
    workspace_text = (OUT / "hit_workspace.py").read_text(encoding="utf-8")
    core_text = (OUT / "hit_core.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.7.1"' in app_text
    assert "from hit_workspace import HitWorkspaceMixin" in app_text
    assert "class ThermalConnectorApp(HitWorkspaceMixin, ProjectWorkspaceMixin, tk.Tk):" in app_text
    assert 'text="Návrh HIT"' in app_text
    assert "self._build_hit_tab(self.hit_tab)" in app_text
    assert "def hit_future_link_payloads" in workspace_text
    assert "def build_database_from_pdf" in core_text and "def utilization" in core_text

    shutil.rmtree(OUT / "__pycache__", ignore_errors=True)

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_workspace.py",
        "schoeck_archive_sources.json", "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.7.1/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.7.1",
        "notes": (
            "Integrovaný návrh Leviat HIT: hlavní TURTO má novou kartu Návrh HIT se stejnou výpočtovou logikou jako samostatný HIT v0.3.0. "
            "Lokální data z DoP se znovu použijí a nejsou součástí online aktualizace; projektové provazby jsou zatím záměrně vypnuté."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.7.1 OK; standalone HIT v0.3 engine integrated, synthetic M-V regression passed")


if __name__ == "__main__":
    main()
