from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.8"
OUT = ROOT / "updates" / "0.6.9"

ARCHIVE_SOURCES = {
    "schema_version": 1,
    "manufacturer": "Schöck",
    "archive_url": "https://www.schoeck.com/cs/downloads-archiv",
    "policy": "Pokud zadaná generace není v aktivní databázi, použij pouze oficiální zdroj Schöck; nikdy ji nenahrazuj jinou generací.",
    "sources": [
        {
            "id": "schoeck-t-zl-5.3",
            "required_compact": ["TZL", "53"],
            "model": "T",
            "type": "ZL",
            "generation": "5.3",
            "edition": "Technische Information Schöck Isokorb T / CH-de / 2026.1",
            "source_url": "https://www.schoeck.com/viewfile/10776/Teildokument_Technische_Information_Schoeck_Isokorb_T_Typ_ZL__10776__.pdf",
            "source_pages": [1, 3],
            "status": "source_only",
            "note": "T typ ZL je nenosný tepelně izolační mezikus; nepřenáší síly. Výška 160–300 mm, délka 1000 mm, generace 5.3."
        },
        {
            "id": "schoeck-cxt-ap-1.0",
            "required_compact": ["CXTAP", "10"],
            "model": "CXT",
            "type": "AP",
            "generation": "1.0",
            "edition": "Technické informace Schöck Isokorb pro atiky a parapety / CZ / 2024.1",
            "source_url": "https://www.schoeck.com/viewfile/8304/Technicke_informace_Schoeck_Isokorb_CXT_typ_AP__8304__.pdf",
            "source_pages": [3, 6, 7],
            "status": "special_design",
            "note": "Dimenzování CXT AP 1.0 používá interakční postup KF a grafy Ft/Fc; nesmí se redukovat na jeden moment a smyk."
        },
        {
            "id": "schoeck-sconnex-w-1.0",
            "required_compact": ["SCONNEXW", "10"],
            "model": "Sconnex",
            "type": "W",
            "generation": "1.0",
            "edition": "Technické informace Schöck Sconnex / CZ / 2023.1",
            "source_url": "https://www.schoeck.com/viewfile/6195/Technicke_informace_Schoeck_Sconnex_typ_W__6195__.pdf",
            "source_pages": [6, 14, 31],
            "status": "loaded",
            "catalog_id": "schoeck-sconnex-w-cz-2023-1",
            "note": "Archivní generace 1.0 je součástí doplňkového katalogu TURTO."
        }
    ]
}


def sconnex_catalog() -> dict:
    widths = {150: 250.0, 180: 450.0, 200: 500.0, 250: 500.0, 300: 500.0}
    records = []
    for width, normal in widths.items():
        designation = f"Schöck Sconnex® W-N1-V1H1-B{width}-1.0"
        records.append({
            "moment_class": "N1",
            "shear_class": "V1H1",
            "concrete_min": "C25/30",
            "cover": f"B{width}",
            "height_mm": "80",
            "designation": designation,
            "aliases": [
                designation.replace("®", ""),
                designation.replace("Schöck ", "").replace("®", ""),
                f"Schöck Sconnex typ W-N1-V1H1-B{width}-1.0",
                f"Sconnex W-N1-V1H1-B{width}-1.0",
            ],
            "results": [
                {"key": "n_rd_z_wall", "label": "NRd,z,stěna", "kind": "normal", "value": normal, "unit": "kN/prvek"},
                {"key": "v_rd_x_b", "label": "VRd,x varianta B", "kind": "shear", "positive": 46.3, "negative": -46.3, "unit": "kN/prvek"},
                {"key": "v_rd_y", "label": "VRd,y", "kind": "horizontal", "positive": 59.0, "negative": -59.0, "unit": "kN/prvek"},
                {"key": "v_rd_x_a", "label": "VRd,x varianta A", "kind": "horizontal", "positive": 88.0, "negative": -88.0, "unit": "kN/prvek"},
            ],
            "source_pages": [6, 14, 31],
            "insulation_thickness_mm": 80,
            "compression_transfer": "tlakový přenos N1",
            "notes": [
                "VRd,x závisí na provedení napojovací stavební výztuže: varianta A ±88,0 kN/prvek; varianta B ±46,3 kN/prvek.",
                "Pro V1H1 platí interakce VEd,y/VRd,y + VEd,x/VRd,x ≤ 1.",
                "Hodnoty převzaty z českých Technických informací Schöck Sconnex CZ/2023.1."
            ]
        })
    return {
        "schema_version": 2,
        "catalog": {
            "id": "schoeck-sconnex-w-cz-2023-1",
            "edition": "Sconnex CZ/2023.1",
            "publication_label": "leden 2023 – archivní generace W 1.0",
            "publication_date": "2023-01-01",
            "source_filename": "Technicke_informace_Schoeck_Sconnex_typ_W__6195__.pdf",
            "source_url": "https://www.schoeck.com/viewfile/6195/Technicke_informace_Schoeck_Sconnex_typ_W__6195__.pdf"
        },
        "families": [{
            "manufacturer": "Schöck",
            "model": "Sconnex",
            "type": "W",
            "generation": "1.0",
            "basis": "Technické informace Schöck Sconnex/CZ/2023.1/leden",
            "insulation_thickness_mm": 80,
            "compression_transfer": "tlakový přenos N1",
            "selector_labels": {
                "moment": "Hlavní třída",
                "shear": "Vedlejší třída",
                "concrete": "Beton",
                "cover": "Šířka stěny",
                "height": "Tloušťka prvku"
            },
            "notes": ["Archivní dokument Schöck. Generace se nesmí zaměnit za novější W 1.1."],
            "records": records
        }]
    }


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_app(text: str) -> str:
    text = replace_once(text, 'APP_VERSION = "0.6.8"', 'APP_VERSION = "0.6.9"', "app version")
    old = '''    def _remote_source_url_for(self, result: QueryResult) -> str | None:\n        """Oficiální online zdroj pro katalogy, které nejsou přibalené lokálně."""\n        if str(result.family.get("manufacturer", "")) != "MAX FRANK":\n            return None\n'''
    new = '''    def _remote_source_url_for(self, result: QueryResult) -> str | None:\n        """Oficiální online zdroj pro katalogy, které nejsou přibalené lokálně."""\n        explicit = str(result.catalog.get("source_url", "")).strip()\n        if explicit.startswith(("https://", "http://")):\n            return explicit\n        if str(result.family.get("manufacturer", "")) != "MAX FRANK":\n            return None\n'''
    return replace_once(text, old, new, "generic source_url")


def patch_bulk_engine(text: str) -> str:
    text = replace_once(text, "import re\n", "import json\nimport re\nfrom pathlib import Path\n", "bulk imports")
    text = replace_once(text, '    varying_keys: tuple[str, ...] = ()\n', '    varying_keys: tuple[str, ...] = ()\n    archive_source: dict[str, Any] | None = None\n', "archive field")
    text = replace_once(text, '            "review": "Doplnit",\n            "error": "Chyba",\n', '            "review": "Doplnit",\n            "archive": "Archivní zdroj",\n            "error": "Chyba",\n', "archive status text")
    text = replace_once(text, '    error: int\n', '    archive: int\n    error: int\n', "summary archive field")
    helper_marker = '\n\ndef split_bulk_line(line: str) -> list[str]:\n'
    helper = '''\n\ndef _archive_registry_path() -> Path:\n    return Path(__file__).resolve().with_name("schoeck_archive_sources.json")\n\n\ndef load_schoeck_archive_sources() -> list[dict[str, Any]]:\n    path = _archive_registry_path()\n    if not path.exists():\n        return []\n    try:\n        payload = json.loads(path.read_text(encoding="utf-8"))\n    except Exception:\n        return []\n    sources = payload.get("sources", []) if isinstance(payload, dict) else []\n    return [dict(item) for item in sources if isinstance(item, dict)]\n\n\ndef find_schoeck_archive_source(text: str) -> dict[str, Any] | None:\n    normalized = normalize_designation_text(text)\n    if "SCHOCK" not in normalized and "SCONNEX" not in normalized and "CXT" not in normalized and "TZL" not in normalized:\n        return None\n    for source in load_schoeck_archive_sources():\n        required = [str(value).upper() for value in source.get("required_compact", []) if str(value).strip()]\n        if required and all(token in normalized for token in required):\n            return source\n    return None\n'''
    text = replace_once(text, helper_marker, helper + helper_marker, "archive helpers")

    exact_block = '''        exact_candidates = [candidate for candidate in candidates if is_exact_designation(designation, candidate.result)]\n        if len(exact_candidates) == 1:\n            item.result = exact_candidates[0].result\n            item.candidates = exact_candidates\n            item.status = "exact"\n            item.message = "Úplné označení odpovídá právě jednomu katalogovému prvku."\n            items.append(item)\n            continue\n\n        if len(candidates) == 1:\n'''
    exact_new = '''        exact_candidates = [candidate for candidate in candidates if is_exact_designation(designation, candidate.result)]\n        if len(exact_candidates) == 1:\n            item.result = exact_candidates[0].result\n            item.candidates = exact_candidates\n            item.status = "exact"\n            item.message = "Úplné označení odpovídá právě jednomu katalogovému prvku."\n            items.append(item)\n            continue\n\n        archive_source = find_schoeck_archive_source(designation)\n        if archive_source is not None:\n            item.archive_source = archive_source\n            item.status = "archive"\n            edition = str(archive_source.get("edition", "oficiální archiv Schöck"))\n            note = str(archive_source.get("note", "")).strip()\n            item.message = f"Generace není v aktivních katalogových datech. Ověřený zdroj: {edition}."\n            if note:\n                item.message += " " + note\n            items.append(item)\n            continue\n\n        if len(candidates) == 1:\n'''
    text = replace_once(text, exact_block, exact_new, "archive before fuzzy candidate")
    text = replace_once(text, '    counts = {"exact": 0, "unique": 0, "confirmed": 0, "review": 0, "error": 0}\n', '    counts = {"exact": 0, "unique": 0, "confirmed": 0, "review": 0, "archive": 0, "error": 0}\n', "summary counts")
    return text


def patch_bulk_ui(text: str) -> str:
    text = replace_once(text, "from typing import Any, Iterable\n\nimport tkinter as tk\n", "from typing import Any, Iterable\n\nimport webbrowser\nimport tkinter as tk\n", "webbrowser import")
    old = '''        ttk.Button(\n            candidate_actions,\n            text="Použít na označené kompatibilní řádky",\n            command=lambda: self._apply_candidate(True),\n        ).pack(side="left", padx=(7, 0))\n'''
    new = old + '''        self.archive_button = ttk.Button(\n            candidate_actions,\n            text="Otevřít archivní katalog",\n            command=self._open_archive_source,\n            state="disabled",\n        )\n        self.archive_button.pack(side="left", padx=(7, 0))\n'''
    text = replace_once(text, old, new, "archive button")
    text = replace_once(text, '        self.review_tree.tag_configure("error", foreground=colors["danger"])\n', '        self.review_tree.tag_configure("archive", foreground=colors["warning_text"])\n        self.review_tree.tag_configure("error", foreground=colors["danger"])\n', "archive tag")
    text = replace_once(text, '            tag = "ready" if item.ready else ("review" if item.status == "review" else "error")\n', '            tag = "ready" if item.ready else ("archive" if item.status == "archive" else ("review" if item.status == "review" else "error"))\n', "archive row tag")
    text = replace_once(text, '            f"{summary.review} k doplnění",\n            f"{summary.error} nerozpoznáno",\n', '            f"{summary.review} k doplnění",\n            f"{summary.archive} archivní zdroj",\n            f"{summary.error} nerozpoznáno",\n', "archive summary")
    text = replace_once(text, '            unresolved = summary.review + summary.error\n', '            unresolved = summary.review + summary.archive + summary.error\n', "unresolved archive")
    text = replace_once(text, '                "Zelené řádky jsou bezpečně připravené. Žluté vyžadují výběr varianty. "\n                "Červené nejsou podle vloženého textu rozpoznatelné."\n', '                "Zelené řádky jsou bezpečně připravené. Žluté vyžadují výběr varianty nebo mají dohledaný archivní zdroj. "\n                "Archivní typ se nevloží, dokud nejsou jeho statická data bezpečně převedena. Červené nejsou rozpoznatelné."\n', "legend")

    show_marker = '''        self.candidate_title_var.set(f"Řádek {item.line_number} • {item.position or 'bez pozice'}")\n        if item.status == "review":\n'''
    show_new = '''        self.candidate_title_var.set(f"Řádek {item.line_number} • {item.position or 'bez pozice'}")\n        self.archive_button.configure(state="normal" if item.archive_source and item.archive_source.get("source_url") else "disabled")\n        if item.status == "review":\n'''
    text = replace_once(text, show_marker, show_new, "archive button state")

    insert_marker = '''    def _active_review_iid(self) -> str | None:\n'''
    archive_method = '''    def _open_archive_source(self) -> None:\n        iid = self._active_review_iid()\n        item = self._item_by_iid.get(iid or "")\n        source = item.archive_source if item is not None else None\n        if not source:\n            return\n        url = str(source.get("source_url", "")).strip()\n        if not url:\n            return\n        pages = source.get("source_pages") or []\n        if pages:\n            try:\n                url += f"#page={int(pages[0])}"\n            except Exception:\n                pass\n        try:\n            webbrowser.open(url, new=2)\n        except Exception as exc:\n            messagebox.showerror("Archivní katalog se nepodařilo otevřít", str(exc), parent=self)\n\n'''
    text = replace_once(text, insert_marker, archive_method + insert_marker, "archive open method")
    return text


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    for name, fn in (("app.pyw", patch_app), ("bulk_import_engine.py", patch_bulk_engine), ("bulk_import.py", patch_bulk_ui)):
        path = OUT / name
        path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8")

    (OUT / "schoeck_archive_sources.json").write_text(json.dumps(ARCHIVE_SOURCES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "catalogs" / "schoeck_sconnex_w_2023.json").write_text(json.dumps(sconnex_catalog(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.9\n"
        "- Schöck: chybějící generace se už nesmí nahrazovat jinou generací; hromadný import umí zobrazit ověřený oficiální archivní zdroj.\n"
        "- Přidán registr zdrojů Schöck pro T-ZL 5.3, CXT AP 1.0 a Sconnex W 1.0.\n"
        "- Sconnex W 1.0 (CZ/2023.1) je doplněn jako plnohodnotný katalog pro B150/B180/B200/B250/B300, beton C25/30.\n"
        "- T-ZL 5.3 je evidován jako nenosný mezikus bez přenosu sil.\n"
        "- CXT AP 1.0 zůstává bezpečně blokovaný pro automatické vložení, protože vyžaduje interakční dimenzování KF-Ft/Fc.\n"
        "- Tlačítko Otevřít archivní katalog vede přímo na oficiální PDF Schöck.\n",
        encoding="utf-8",
    )

    for name in ["app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py", "bulk_import_engine.py", "bulk_import.py"]:
        py_compile.compile(str(OUT / name), doraise=True)

    sys.path.insert(0, str(OUT))
    import catalog_engine as engine
    import bulk_import_engine as bulk

    db = engine.CatalogDatabase(OUT / "catalogs")
    sconnex = "Schöck Sconnex W-N1-V1H1-B180-1.0"
    items, _ = bulk.analyze_bulk_text(db, sconnex + "\t2", preferred_concrete="C25/30")
    assert len(items) == 1 and items[0].ready and items[0].result is not None, (items[0].status, items[0].message)
    assert items[0].quantity == 2
    assert items[0].result.designation.startswith("Schöck Sconnex® W-N1-V1H1-B180-1.0")
    normal = next(r for r in items[0].result.results if r.get("key") == "n_rd_z_wall")
    assert float(normal["value"]) == 450.0

    tzl, _ = bulk.analyze_bulk_text(db, "Schöck Isokorb T-ZL-EI120-H180-5.3\t86", preferred_concrete="C25/30")
    assert len(tzl) == 1 and tzl[0].status == "archive" and tzl[0].archive_source
    assert tzl[0].archive_source["generation"] == "5.3"

    cxt, _ = bulk.analyze_bulk_text(db, "Schöck Isokorb CXT-AP-MM1-VV1-REI30-LR200-B200-L300-1.0\t7", preferred_concrete="C25/30")
    assert len(cxt) == 1 and cxt[0].status == "archive" and cxt[0].archive_source
    assert cxt[0].archive_source["status"] == "special_design"

    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.6.9"' in app_text
    assert 'result.catalog.get("source_url"' in app_text

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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.9/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.6.9",
        "notes": "Schöck archivní workflow: chybějící generace se nenahrazuje novější, ale zobrazí ověřený oficiální zdroj. Doplněn katalog Sconnex W 1.0 CZ/2023.1; T-ZL 5.3 a CXT AP 1.0 mají ověřené zdroje, CXT AP je do implementace interakčního modelu blokován pro automatické statické vložení.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.6.9 OK; Schock archive workflow and Sconnex W 1.0 verified")


if __name__ == "__main__":
    main()
