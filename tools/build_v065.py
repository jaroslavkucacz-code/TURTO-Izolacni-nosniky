from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.6.4"
OUT = ROOT / "updates" / "0.6.5"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, fn) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(fn(text), encoding="utf-8")


def patch_app(s: str) -> str:
    s = replace_once(s, 'APP_VERSION = "0.6.4"', 'APP_VERSION = "0.6.5"', "app version")

    s = replace_once(
        s,
        'CREATOR = "Vytvořil Ing. Jaroslav Kučera"\n',
        'CREATOR = "Vytvořil Ing. Jaroslav Kučera"\n\n'
        'MAX_FRANK_SOURCE_BASE_URL = "https://www.maxfrank.com/wAssets/docs/products/brochures/"\n'
        'MAX_FRANK_SOURCE_FALLBACK = {\n'
        '    "M": "egcobox-en-MM-thermal-break-balcony-connector-ETA-BR-INTGB.pdf",\n'
        '    "XL": "egcobox-en-MXL-thermal-break-balcony-connector-ETA-BR-INTGB.pdf",\n'
        '}\n',
        "MAX FRANK source constants",
    )

    s = replace_once(
        s,
        'self.open_pdf_button = ttk.Button(actions, text="Otevřít zdrojovou stranu PDF", command=self.open_current_source)',
        'self.open_pdf_button = ttk.Button(actions, text="Nahlédnout do katalogu", command=self.open_current_source)',
        "catalog button label",
    )

    old = '''    def source_path_for(self, result: QueryResult) -> Path:\n        return self.source_dir / str(result.catalog["source_filename"])\n\n    def open_current_source(self) -> None:\n        if self.current_result is None:\n            return\n        page = int(self.current_result.source_pages[0]) if self.current_result.source_pages else 1\n        path = self.source_path_for(self.current_result)\n        if not path.exists():\n            messagebox.showerror(\n                "Zdrojový soubor nebyl nalezen",\n                f"Program očekává zdrojový katalog zde:\\n{path}",\n                parent=self,\n            )\n            return\n        try:\n            uri = path.resolve().as_uri() + f"#page={page}"\n            opened = webbrowser.open(uri, new=2)\n            if not opened:\n                open_path(path)\n            self.set_status(f"Otevřen zdrojový katalog na straně {page}.")\n        except Exception as exc:\n            LOGGER.exception("Chyba při otevření PDF")\n            messagebox.showerror("PDF se nepodařilo otevřít", str(exc), parent=self)\n\n'''

    new = '''    def source_path_for(self, result: QueryResult) -> Path:\n        return self.source_dir / str(result.catalog["source_filename"])\n\n    def _remote_source_url_for(self, result: QueryResult) -> str | None:\n        """Oficiální online zdroj pro katalogy, které nejsou přibalené lokálně."""\n        if str(result.family.get("manufacturer", "")) != "MAX FRANK":\n            return None\n\n        source_filename = str(result.catalog.get("source_filename", "")).strip()\n        if source_filename.lower().endswith(".pdf") and source_filename.lower().startswith("egcobox-"):\n            return MAX_FRANK_SOURCE_BASE_URL + source_filename\n\n        model = str(result.family.get("model", "")).strip().upper()\n        fallback = MAX_FRANK_SOURCE_FALLBACK.get(model)\n        return MAX_FRANK_SOURCE_BASE_URL + fallback if fallback else None\n\n    def open_current_source(self) -> None:\n        if self.current_result is None:\n            return\n        page = int(self.current_result.source_pages[0]) if self.current_result.source_pages else 1\n        path = self.source_path_for(self.current_result)\n        try:\n            if path.exists():\n                uri = path.resolve().as_uri() + f"#page={page}"\n                opened = webbrowser.open(uri, new=2)\n                if not opened:\n                    open_path(path)\n                self.set_status(f"Otevřen zdrojový katalog na straně {page}.")\n                return\n\n            remote_url = self._remote_source_url_for(self.current_result)\n            if remote_url:\n                opened = webbrowser.open(remote_url + f"#page={page}", new=2)\n                if not opened:\n                    raise RuntimeError("Výchozí webový prohlížeč se nepodařilo otevřít.")\n                self.set_status(f"Otevřen online katalog MAX FRANK na straně {page}.")\n                return\n\n            messagebox.showerror(\n                "Zdrojový soubor nebyl nalezen",\n                f"Program očekává zdrojový katalog zde:\\n{path}",\n                parent=self,\n            )\n        except Exception as exc:\n            LOGGER.exception("Chyba při otevření PDF")\n            messagebox.showerror("PDF se nepodařilo otevřít", str(exc), parent=self)\n\n'''
    s = replace_once(s, old, new, "MAX FRANK online source fallback")
    return s


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    patch_file(OUT / "app.pyw", patch_app)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.6.5\n"
        "- MAX FRANK Egcobox nyní podporuje tlačítko Nahlédnout do katalogu stejně jako ostatní výrobci.\n"
        "- Pokud technický PDF katalog M / XL není lokálně ve složce sources, otevře se oficiální MAX FRANK PDF online.\n"
        "- Otevírá se přímo source_pages konkrétního zvoleného katalogového záznamu.\n"
        "- Lokální katalog má nadále přednost před online zdrojem.\n",
        encoding="utf-8",
    )

    for name in ["app.pyw", "autocomplete.py", "catalog_engine.py", "project_model.py", "project_ui.py", "updater.py"]:
        py_compile.compile(str(OUT / name), doraise=True)

    sys.path.insert(0, str(OUT))
    import catalog_engine as engine

    db = engine.CatalogDatabase(OUT / "catalogs")
    xl_id = "maxfrank-egcobox-xl-eta-19-0046-2022"
    result = db.query(
        catalog_id=xl_id,
        manufacturer="MAX FRANK",
        model="XL",
        type_name="MXL",
        generation="ETA-19/0046",
        moment_class="MXL20",
        concrete_min="C25/30",
        shear_class="V6±",
        cover="C30",
        height_mm="200",
    )
    assert result.source_pages, "MAX FRANK result has no source page"
    assert str(result.catalog.get("source_filename", "")).lower().endswith(".pdf")

    app_text = (OUT / "app.pyw").read_text(encoding="utf-8")
    assert 'text="Nahlédnout do katalogu"' in app_text
    assert "MAX_FRANK_SOURCE_BASE_URL" in app_text
    assert "_remote_source_url_for" in app_text
    assert 'remote_url + f"#page={page}"' in app_text

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.6.5/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.6.5",
        "notes": (
            "MAX FRANK Egcobox má nyní funkční Nahlédnout do katalogu. Program otevírá přímo zdrojovou stranu "
            "konkrétního typu v oficiálním technickém PDF M nebo XL; lokální PDF má přednost, online MAX FRANK je záloha."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"v0.6.5 OK; MAX FRANK source page {result.source_pages[0]} verified")


if __name__ == "__main__":
    main()
