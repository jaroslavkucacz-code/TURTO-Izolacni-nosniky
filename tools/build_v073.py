from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.7.2"
OUT = ROOT / "updates" / "0.7.3"

UI_UTILS = '''from __future__ import annotations

from typing import Any


def place_dialog_on_parent(dialog: Any, parent: Any) -> None:
    """Umístí dialog nad rodičovské okno, tedy na stejný monitor.

    Zachová velikost nastavenou pomocí geometry()/minsize(). Souřadnice mohou být
    záporné, což je důležité pro monitory vlevo nebo nad primárním monitorem.
    Volání je odloženo přes after_idle, aby už Tk znal skutečnou velikost oken.
    """
    def _place() -> None:
        try:
            parent.update_idletasks()
            dialog.update_idletasks()

            width = int(dialog.winfo_width())
            height = int(dialog.winfo_height())
            if width <= 1:
                width = max(1, int(dialog.winfo_reqwidth()))
            if height <= 1:
                height = max(1, int(dialog.winfo_reqheight()))

            parent_x = int(parent.winfo_rootx())
            parent_y = int(parent.winfo_rooty())
            parent_w = max(1, int(parent.winfo_width()))
            parent_h = max(1, int(parent.winfo_height()))

            x = parent_x + (parent_w - width) // 2
            y = parent_y + (parent_h - height) // 2
            dialog.geometry(f"{width}x{height}{x:+d}{y:+d}")
            dialog.lift(parent)
        except Exception:
            # Umístění dialogu nesmí nikdy zablokovat jeho otevření.
            pass

    try:
        dialog.after_idle(_place)
    except Exception:
        pass
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_app(text: str) -> str:
    text = replace_once(text, 'APP_VERSION = "0.7.2"', 'APP_VERSION = "0.7.3"', "app version")
    text = replace_once(
        text,
        'from project_model import selection_from_result\n',
        'from project_model import selection_from_result\nfrom ui_utils import place_dialog_on_parent\n',
        "app ui_utils import",
    )
    text = replace_once(
        text,
        'self.geometry("980x600"); self.minsize(760,440); self.transient(parent); self.configure(background=parent.colors["bg"])',
        'self.geometry("980x600"); self.minsize(760,440); self.transient(parent); place_dialog_on_parent(self, parent); self.configure(background=parent.colors["bg"])',
        "height dialog monitor",
    )
    return text


def patch_project_ui(text: str) -> str:
    text = replace_once(
        text,
        'from xlsx_export import write_xlsx\n',
        'from xlsx_export import write_xlsx\nfrom ui_utils import place_dialog_on_parent\n',
        "project ui_utils import",
    )
    marker = '        self.transient(parent)\n        self.grab_set()\n'
    count = text.count(marker)
    if count != 3:
        raise RuntimeError(f"project dialogs: expected 3 transient/grab pairs, found {count}")
    text = text.replace(
        marker,
        '        self.transient(parent)\n        place_dialog_on_parent(self, parent)\n        self.grab_set()\n',
    )
    return text


def patch_bulk_import(text: str) -> str:
    text = replace_once(
        text,
        'from catalog_engine import CatalogDatabase, DesignationSuggestion, QueryResult, concrete_label\n',
        'from catalog_engine import CatalogDatabase, DesignationSuggestion, QueryResult, concrete_label\nfrom ui_utils import place_dialog_on_parent\n',
        "bulk ui_utils import",
    )
    text = replace_once(
        text,
        '        self.transient(parent)\n        self.grab_set()\n',
        '        self.transient(parent)\n        place_dialog_on_parent(self, parent)\n        self.grab_set()\n',
        "bulk dialog monitor",
    )
    return text


def patch_hit_workspace(text: str) -> str:
    text = replace_once(text, 'import os\nimport webbrowser\n', 'import hashlib\nimport os\nimport shutil\nimport webbrowser\n', "hit file imports")
    text = replace_once(
        text,
        'from hit_core import CONCRETES, COVERS, DATA_FILENAME, Candidate, HitDatabase, build_database_from_pdf, fmt\n',
        'from hit_core import CONCRETES, COVERS, DATA_FILENAME, Candidate, HitDatabase, build_database_from_pdf, fmt\nfrom ui_utils import place_dialog_on_parent\n',
        "hit ui_utils import",
    )
    text = replace_once(text, 'HIT_MODULE_VERSION = "0.3.0"', 'HIT_MODULE_VERSION = "0.3.1"', "hit module version")
    text = replace_once(
        text,
        '        self.transient(parent)\n        self.grab_set()\n',
        '        self.transient(parent)\n        place_dialog_on_parent(self, parent)\n        self.grab_set()\n',
        "hit variants monitor",
    )

    marker = '    def _integrated_hit_data_path(self) -> Path:\n        return Path(self.settings_path).resolve().parent / DATA_FILENAME\n'
    helpers = '''    def _managed_hit_source_directory(self) -> Path:\n        directory = Path(self.settings_path).resolve().parent / "sources" / "HIT"\n        directory.mkdir(parents=True, exist_ok=True)\n        return directory\n\n    @staticmethod\n    def _hit_file_sha256(path: Path) -> str:\n        digest = hashlib.sha256()\n        with Path(path).open("rb") as handle:\n            for chunk in iter(lambda: handle.read(1024 * 1024), b""):\n                digest.update(chunk)\n        return digest.hexdigest()\n\n    def _is_managed_hit_source(self, path: Path) -> bool:\n        try:\n            Path(path).resolve().relative_to(self._managed_hit_source_directory().resolve())\n            return True\n        except Exception:\n            return False\n\n    def _store_hit_source_pdf(self, source: Path, expected_sha256: str = "") -> Path:\n        source = Path(source).resolve()\n        if not source.exists() or not source.is_file():\n            raise FileNotFoundError(f"Zdrojové DoP nebylo nalezeno: {source}")\n        expected = str(expected_sha256 or "").strip().lower()\n        source_sha = self._hit_file_sha256(source)\n        if expected and source_sha != expected:\n            raise RuntimeError("Zdrojové DoP neodpovídá databázi HIT (nesouhlasí SHA-256).")\n\n        target = self._managed_hit_source_directory() / source.name\n        if source == target.resolve():\n            return target\n        if target.exists() and self._hit_file_sha256(target) == source_sha:\n            return target\n\n        temp = target.with_name(target.name + ".tmp")\n        try:\n            shutil.copy2(source, temp)\n            if self._hit_file_sha256(temp) != source_sha:\n                raise RuntimeError("Kontrola kopie zdrojového DoP selhala.")\n            temp.replace(target)\n        finally:\n            if temp.exists():\n                try:\n                    temp.unlink()\n                except Exception:\n                    pass\n        return target\n\n    def _discover_managed_hit_source(self, expected_sha256: str = "") -> Path | None:\n        expected = str(expected_sha256 or "").strip().lower()\n        for candidate in sorted(self._managed_hit_source_directory().glob("*.pdf")):\n            try:\n                if not expected or self._hit_file_sha256(candidate) == expected:\n                    return candidate\n            except Exception:\n                continue\n        return None\n\n''' + marker
    text = replace_once(text, marker, helpers, "managed HIT source helpers")

    old_source = '''        saved_pdf = str(state.get("source_pdf", "")).strip()\n        self.hit_source_pdf = Path(saved_pdf) if saved_pdf and Path(saved_pdf).exists() else None\n        if hasattr(self, "hit_open_source_button"):\n            self.hit_open_source_button.configure(state="normal" if self.hit_source_pdf else "disabled")\n'''
    new_source = '''        saved_pdf = str(state.get("source_pdf", "")).strip()\n        source_pdf = Path(saved_pdf) if saved_pdf and Path(saved_pdf).exists() else None\n        self.hit_source_pdf = None\n        if source_pdf is not None:\n            try:\n                self.hit_source_pdf = self._store_hit_source_pdf(source_pdf, database.source_sha256)\n            except Exception as exc:\n                # Databáze zůstává použitelná; pouze spravovaná kopie zdroje selhala.\n                self.hit_source_pdf = source_pdf\n                if not quiet:\n                    messagebox.showwarning(\n                        "Zdrojové DoP se nepodařilo uložit",\n                        f"Databáze HIT je načtená, ale zdrojové PDF se nepodařilo zkopírovat do spravované složky TURTO:\\n\\n{exc}",\n                        parent=self,\n                    )\n        if self.hit_source_pdf is None:\n            self.hit_source_pdf = self._discover_managed_hit_source(database.source_sha256)\n        if self.hit_source_pdf is not None:\n            state["source_pdf"] = str(self.hit_source_pdf)\n        if hasattr(self, "hit_open_source_button"):\n            self.hit_open_source_button.configure(state="normal" if self.hit_source_pdf else "disabled")\n'''
    text = replace_once(text, old_source, new_source, "managed source load/migration")

    old_status = '        self.hit_status_var.set("Data HIT byla obnovena z DoP.")\n'
    new_status = '''        if self.hit_source_pdf is not None and self._is_managed_hit_source(self.hit_source_pdf):\n            self.hit_status_var.set("Data HIT i zdrojové DoP byly uloženy do spravované složky TURTO.")\n        else:\n            self.hit_status_var.set("Data HIT byla obnovena z DoP; zdrojové PDF zůstává na původním umístění.")\n'''
    text = replace_once(text, old_status, new_status, "managed source rebuild status")
    return text


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    (OUT / "ui_utils.py").write_text(UI_UTILS, encoding="utf-8")
    patches = {
        "app.pyw": patch_app,
        "project_ui.py": patch_project_ui,
        "bulk_import.py": patch_bulk_import,
        "hit_workspace.py": patch_hit_workspace,
    }
    for rel, fn in patches.items():
        path = OUT / rel
        path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8")

    # Syntax checks for every Python module shipped in the update root.
    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    # Regression: managed HIT source survives removal of the original file and is SHA-checked.
    sys.path.insert(0, str(OUT))
    try:
        import hit_workspace  # type: ignore
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = tmp / "CONF-DOP_HIT-HP_SP_07-23-E.pdf"
            source.write_bytes(b"TURTO-HIT-source-regression")
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            dummy = object.__new__(hit_workspace.HitWorkspaceMixin)
            dummy.settings_path = tmp / "settings.json"
            managed = dummy._store_hit_source_pdf(source, expected)
            assert managed.exists() and managed != source
            assert managed.parent == tmp / "sources" / "HIT"
            assert dummy._hit_file_sha256(managed) == expected
            source.unlink()
            assert managed.exists() and dummy._discover_managed_hit_source(expected) == managed
            bad = tmp / "bad.pdf"
            bad.write_bytes(b"different")
            try:
                dummy._store_hit_source_pdf(bad, expected)
            except RuntimeError:
                pass
            else:
                raise AssertionError("SHA mismatch must reject wrong source PDF")
    finally:
        sys.path.pop(0)

    # Dialog placement must be wired into all custom modal dialogs, without touching tooltip popups.
    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    project_text = (OUT / "project_ui.py").read_text(encoding="utf-8")
    bulk_text = (OUT / "bulk_import.py").read_text(encoding="utf-8")
    hit_text = (OUT / "hit_workspace.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.7.3"' in app_text
    assert "place_dialog_on_parent(self, parent)" in app_text
    assert project_text.count("place_dialog_on_parent(self, parent)") == 3
    assert bulk_text.count("place_dialog_on_parent(self, parent)") == 1
    assert hit_text.count("place_dialog_on_parent(self, parent)") == 1
    assert 'HIT_MODULE_VERSION = "0.3.1"' in hit_text
    assert 'sources" / "HIT"' in hit_text

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.7.3\n"
        "- HIT: při načtení/obnovení DoP se originální PDF kopíruje do spravované složky TURTO sources/HIT.\n"
        "- Stávající externí cesta k DoP se při prvním načtení po aktualizaci automaticky migruje do spravované kopie, pokud SHA-256 odpovídá databázi.\n"
        "- Databáze HIT zůstává v uživatelských datech; zdrojové PDF a databáze tak přežijí přesun nebo smazání původního souboru.\n"
        "- Vlastní dialogy TURTO se otevírají nad rodičovským oknem, tedy na stejném monitoru jako hlavní program.\n"
        "- Zahrnuto: detail katalogových variant, metadata řádku, starší hromadný dialog, Excel export, kontrolovaný hromadný import a Varianty HIT.\n",
        encoding="utf-8",
    )

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_workspace.py", "ui_utils.py",
        "schoeck_archive_sources.json", "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.7.3/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.7.3",
        "notes": (
            "HIT nyní uchovává spravovanou kopii zdrojového DoP přímo v uživatelských datech TURTO a ověřuje ji SHA-256. "
            "Vlastní dialogová okna se současně otevírají nad rodičovským oknem na stejném monitoru jako hlavní program."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.7.3 OK; managed HIT source + parent-monitor dialogs")


if __name__ == "__main__":
    main()
