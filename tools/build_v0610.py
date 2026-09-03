from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.9"
OUT = ROOT / "updates" / "0.6.10"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(fn(text), encoding="utf-8")


def patch_app(text: str) -> str:
    return replace_once(text, 'APP_VERSION = "0.6.9"', 'APP_VERSION = "0.6.10"', "app version")


def patch_bulk_engine(text: str) -> str:
    text = replace_once(
        text,
        '    archive_source: dict[str, Any] | None = None\n',
        '    archive_source: dict[str, Any] | None = None\n'
        '    manual_previous_status: str | None = None\n'
        '    manual_previous_message: str = ""\n',
        "manual state fields",
    )
    text = replace_once(
        text,
        '            "archive": "Archivní zdroj",\n            "error": "Chyba",\n',
        '            "archive": "Archivní zdroj",\n'
        '            "manual": "Neřešit (ručně)",\n'
        '            "error": "Chyba",\n',
        "manual status text",
    )
    text = replace_once(
        text,
        '    archive: int\n    error: int\n',
        '    archive: int\n    manual: int\n    error: int\n',
        "manual summary field",
    )
    text = replace_once(
        text,
        '    counts = {"exact": 0, "unique": 0, "confirmed": 0, "review": 0, "archive": 0, "error": 0}\n',
        '    counts = {"exact": 0, "unique": 0, "confirmed": 0, "review": 0, "archive": 0, "manual": 0, "error": 0}\n',
        "manual summary count",
    )
    return text


def patch_bulk_ui(text: str) -> str:
    text = replace_once(
        text,
        '        self.skipped_headers = 0\n',
        '        self.skipped_headers = 0\n        self.manual_skipped_count = 0\n',
        "manual skipped count",
    )

    archive_button = '''        self.archive_button = ttk.Button(\n            candidate_actions,\n            text="Otevřít archivní katalog",\n            command=self._open_archive_source,\n            state="disabled",\n        )\n        self.archive_button.pack(side="left", padx=(7, 0))\n'''
    archive_plus_manual = archive_button + '''        self.manual_button = ttk.Button(\n            candidate_actions,\n            text="Neřešit – zadám ručně",\n            command=self._toggle_manual,\n            state="disabled",\n        )\n        self.manual_button.pack(side="left", padx=(7, 0))\n'''
    text = replace_once(text, archive_button, archive_plus_manual, "manual button")

    text = replace_once(
        text,
        '        self.review_tree.tag_configure("archive", foreground=colors["warning_text"])\n'
        '        self.review_tree.tag_configure("error", foreground=colors["danger"])\n',
        '        self.review_tree.tag_configure("archive", foreground=colors["warning_text"])\n'
        '        self.review_tree.tag_configure("manual", foreground=colors["muted"])\n'
        '        self.review_tree.tag_configure("error", foreground=colors["danger"])\n',
        "manual row tag style",
    )

    old_tag = '            tag = "ready" if item.ready else ("archive" if item.status == "archive" else ("review" if item.status == "review" else "error"))\n'
    new_tag = '            tag = "ready" if item.ready else ("manual" if item.status == "manual" else ("archive" if item.status == "archive" else ("review" if item.status == "review" else "error")))\n'
    text = replace_once(text, old_tag, new_tag, "manual row tag")

    text = replace_once(
        text,
        '            f"{summary.archive} archivní zdroj",\n            f"{summary.error} nerozpoznáno",\n',
        '            f"{summary.archive} archivní zdroj",\n'
        '            f"{summary.manual} neřešit / ručně",\n'
        '            f"{summary.error} nerozpoznáno",\n',
        "manual summary text",
    )

    old_button_logic = '''        if summary.ready:\n            unresolved = summary.review + summary.archive + summary.error\n            self.insert_button_var.set(\n                f"Vložit vše ({summary.ready})" if unresolved == 0 else f"Vložit připravené ({summary.ready})"\n            )\n            self.insert_button.configure(state="normal")\n        else:\n            self.insert_button_var.set("Vložit připravené")\n            self.insert_button.configure(state="disabled")\n'''
    new_button_logic = '''        unresolved = summary.review + summary.archive + summary.error\n        if summary.ready:\n            if unresolved == 0 and summary.manual == 0:\n                self.insert_button_var.set(f"Vložit vše ({summary.ready})")\n            elif unresolved == 0:\n                self.insert_button_var.set(f"Vložit {summary.ready} • {summary.manual} ručně")\n            else:\n                self.insert_button_var.set(f"Vložit připravené ({summary.ready})")\n            self.insert_button.configure(state="normal")\n        elif summary.manual and unresolved == 0:\n            self.insert_button_var.set(f"Dokončit • {summary.manual} ručně")\n            self.insert_button.configure(state="normal")\n        else:\n            self.insert_button_var.set("Vložit připravené")\n            self.insert_button.configure(state="disabled")\n'''
    text = replace_once(text, old_button_logic, new_button_logic, "manual insert button logic")

    text = replace_once(
        text,
        '        self.archive_button.configure(state="normal" if item.archive_source and item.archive_source.get("source_url") else "disabled")\n'
        '        if item.status == "review":\n',
        '        self.archive_button.configure(state="normal" if item.archive_source and item.archive_source.get("source_url") else "disabled")\n'
        '        if item.status == "manual":\n'
        '            self.manual_button.configure(text="Vrátit k řešení", state="normal")\n'
        '        elif item.ready:\n'
        '            self.manual_button.configure(text="Neřešit – zadám ručně", state="disabled")\n'
        '        else:\n'
        '            self.manual_button.configure(text="Neřešit – zadám ručně", state="normal")\n'
        '        if item.status == "review":\n',
        "manual button state",
    )

    text = replace_once(
        text,
        '        elif item.ready:\n            self.candidate_hint_var.set(item.message)\n        else:\n            self.candidate_hint_var.set(item.message or "Řádek nebylo možné rozpoznat.")\n',
        '        elif item.status == "manual":\n'
        '            self.candidate_hint_var.set("Řádek je vědomě přeskočený a nebude hromadně vložen. Zadáte jej později ručně. Volbou „Vrátit k řešení“ obnovíte původní stav bez nové analýzy celého výkazu.")\n'
        '        elif item.ready:\n'
        '            self.candidate_hint_var.set(item.message)\n'
        '        else:\n'
        '            self.candidate_hint_var.set(item.message or "Řádek nebylo možné rozpoznat.")\n',
        "manual candidate hint",
    )

    chosen_marker = '''    def _chosen_candidate(self) -> DesignationSuggestion | None:\n'''
    manual_method = '''    def _toggle_manual(self) -> None:\n        iid = self._active_review_iid()\n        item = self._item_by_iid.get(iid or "")\n        if item is None or item.ready:\n            return\n\n        if item.status == "manual":\n            previous = item.manual_previous_status\n            if previous not in {"review", "archive", "error"}:\n                previous = "archive" if item.archive_source else ("review" if item.candidates else "error")\n            item.status = previous\n            if item.manual_previous_message:\n                item.message = item.manual_previous_message\n            elif previous == "archive":\n                item.message = "Archivní typ byl vrácen k řešení."\n            elif previous == "review":\n                item.message = "Řádek byl vrácen k výběru katalogové varianty."\n            else:\n                item.message = "Řádek byl vrácen k řešení."\n            item.manual_previous_status = None\n            item.manual_previous_message = ""\n        else:\n            item.manual_previous_status = item.status\n            item.manual_previous_message = item.message\n            item.status = "manual"\n            item.message = "Neřešit – označeno uživatelem pro následné ruční zadání; hromadný import tento řádek přeskočí."\n\n        self._refresh_review_tree(preserve_selection=True)\n        if iid and iid in self._item_by_iid:\n            self._show_candidates_for(iid)\n\n'''
    text = replace_once(text, chosen_marker, manual_method + chosen_marker, "manual toggle method")

    old_insert = '''    def _insert_ready(self) -> None:\n        ready = [item for item in self.items if item.ready and item.result is not None]\n        unresolved = [item for item in self.items if not item.ready]\n        if not ready:\n            return\n        if unresolved:\n            if not messagebox.askyesno(\n                "Nevyřešené řádky",\n                f"Zbývá {len(unresolved)} nevyřešených řádků. Vložit nyní pouze {len(ready)} připravených řádků?",\n                parent=self,\n            ):\n                return\n        self.result = [\n'''
    new_insert = '''    def _insert_ready(self) -> None:\n        ready = [item for item in self.items if item.ready and item.result is not None]\n        manual = [item for item in self.items if item.status == "manual"]\n        unresolved = [item for item in self.items if not item.ready and item.status != "manual"]\n        if not ready and not manual:\n            return\n        if unresolved:\n            if not messagebox.askyesno(\n                "Nevyřešené řádky",\n                f"Zbývá {len(unresolved)} skutečně nevyřešených řádků. Vložit nyní pouze {len(ready)} připravených řádků?",\n                parent=self,\n            ):\n                return\n        self.manual_skipped_count = len(manual)\n        self.result = [\n'''
    text = replace_once(text, old_insert, new_insert, "manual insert filtering")

    old_help = '''                "Zelené řádky jsou bezpečně připravené. Žluté vyžadují výběr varianty nebo mají dohledaný archivní zdroj. "\n                "Archivní typ se nevloží, dokud nejsou jeho statická data bezpečně převedena. Červené nejsou rozpoznatelné."\n'''
    new_help = '''                "Zelené řádky jsou bezpečně připravené. Žluté vyžadují výběr varianty nebo mají dohledaný archivní zdroj. "\n                "Červené nejsou rozpoznatelné. Volbou „Neřešit – zadám ručně“ lze libovolný nevyřešený řádek vědomě přeskočit; "\n                "šedý řádek se hromadně nevloží a zůstává určen pro následné ruční zadání."\n'''
    text = replace_once(text, old_help, new_help, "manual help text")
    return text


def patch_project_ui(text: str) -> str:
    old = '''        self.wait_window(dialog)\n        if not dialog.result:\n            return\n\n        added_ids: list[str] = []\n'''
    new = '''        self.wait_window(dialog)\n        if dialog.result is None:\n            return\n        manual_count = int(getattr(dialog, "manual_skipped_count", 0) or 0)\n        if not dialog.result:\n            if manual_count:\n                self.set_status(f"{manual_count} řádků ponecháno pro ruční zadání; hromadně nebylo nic vloženo.")\n            return\n\n        added_ids: list[str] = []\n'''
    text = replace_once(text, old, new, "dialog result handling")
    text = replace_once(
        text,
        '        self.set_status(f"Hromadně vloženo {len(added_ids)} zkontrolovaných řádků.")\n',
        '        status = f"Hromadně vloženo {len(added_ids)} zkontrolovaných řádků."\n'
        '        if manual_count:\n'
        '            status += f" • {manual_count} ponecháno pro ruční zadání."\n'
        '        self.set_status(status)\n',
        "manual project status",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)
    patch_file(OUT / "bulk_import_engine.py", patch_bulk_engine)
    patch_file(OUT / "bulk_import.py", patch_bulk_ui)
    patch_file(OUT / "project_ui.py", patch_project_ui)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.10\n"
        "- Hromadné vložení: každý nevyřešený řádek lze ručně označit „Neřešit – zadám ručně“.\n"
        "- Tento stav program nikdy nenastavuje automaticky a řádek se hromadně nevloží.\n"
        "- Ručně přeskočený řádek je šedý, nepočítá se mezi chyby a lze jej tlačítkem „Vrátit k řešení“ obnovit bez nové analýzy výkazu.\n"
        "- Při dokončení se ve stavovém řádku zobrazí počet položek ponechaných pro ruční zadání.\n",
        encoding="utf-8",
    )

    compile_files = [
        "app.pyw", "autocomplete.py", "catalog_engine.py", "project_model.py", "project_ui.py",
        "updater.py", "bulk_import_engine.py", "bulk_import.py",
    ]
    for name in compile_files:
        py_compile.compile(str(OUT / name), doraise=True)

    # Regresní kontrola datového stavu „manual“ bez spouštění Tk GUI.
    import sys
    sys.path.insert(0, str(OUT))
    import bulk_import_engine as bulk

    item = bulk.BulkImportItem(
        line_number=1,
        raw="NEZNÁMÝ TYP\t2",
        position="P001",
        quantity=2,
        designation="NEZNÁMÝ TYP",
        status="manual",
        message="Neřešit – zadám ručně",
        manual_previous_status="error",
        manual_previous_message="Původní chyba",
    )
    summary = bulk.summarize_items([item])
    assert summary.manual == 1 and summary.error == 0 and summary.ready == 0
    assert item.status_text == "Neřešit (ručně)"
    assert not item.ready

    ui_text = (OUT / "bulk_import.py").read_text(encoding="utf-8")
    project_text = (OUT / "project_ui.py").read_text(encoding="utf-8")
    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    assert "Neřešit – zadám ručně" in ui_text
    assert "Vrátit k řešení" in ui_text
    assert "def _toggle_manual" in ui_text
    assert 'item.status == "manual"' in ui_text
    assert 'item.status != "manual"' in ui_text
    assert "manual_skipped_count" in ui_text and "manual_skipped_count" in project_text
    assert 'APP_VERSION = "0.6.10"' in app_text

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "schoeck_archive_sources.json",
        "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.10/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.10",
        "notes": (
            "Hromadné vložení má nový čistě ruční stav „Neřešit – zadám ručně“. Nevyřešený typ lze vědomě přeskočit bez "
            "falešného katalogového přiřazení; nepočítá se pak mezi chyby, hromadně se nevloží a lze jej vrátit k řešení."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("v0.6.10 OK; manual skip is explicit, reversible and never auto-inserted")


if __name__ == "__main__":
    main()
