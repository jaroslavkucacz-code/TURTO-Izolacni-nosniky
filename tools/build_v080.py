from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
import py_compile
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.7.5"
OUT = ROOT / "updates" / "0.8.0"
CORE = ROOT / "tools" / "hit_core_v080.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def patch_workspace(text: str) -> str:
    text = replace_once(
        text,
        "from hit_core import CONCRETES, COVERS, DATA_FILENAME, Candidate, HitDatabase, build_database_from_pdf, fmt",
        "from hit_core import CONCRETES, COVERS, CONNECTION_TYPES, DATA_FILENAME, Candidate, HitDatabase, build_database_from_pdf, fmt",
        "core import",
    )
    text = replace_once(text, 'HIT_MODULE_VERSION = "0.3.2"', 'HIT_MODULE_VERSION = "0.4.0"', "module version")
    text = replace_once(
        text,
        'f"{row.series.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "',
        'f"{row.series.get()} {row.connection_type.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "',
        "variant subtitle",
    )
    text = replace_once(
        text,
        '"m1": ("M1", 82, "center"),\n            "v1": ("V1", 82, "center"),\n            "m2": ("M2", 82, "center"),\n            "v2": ("V2", 82, "center"),\n            "page": ("DoP", 62, "center"),',
        '"m1": ("M1 / MRd", 88, "center"),\n            "v1": ("V1 / VRd", 88, "center"),\n            "m2": ("M2", 82, "center"),\n            "v2": ("V2", 82, "center"),\n            "page": ("Zdroj", 150, "center"),',
        "variant headings",
    )
    text = replace_once(
        text,
        'self.series = tk.StringVar(value=str(defaults.get("series", "HP")))\n        self.height =',
        'self.series = tk.StringVar(value=str(defaults.get("series", "HP")))\n        self.connection_type = tk.StringVar(value=str(defaults.get("connection_type", "MVX")))\n        self.height =',
        "type variable",
    )
    text = replace_once(
        text,
        'combo(self.series, ("HP", "SP"), 6)\n        entry(self.height, 8)',
        'combo(self.series, ("HP", "SP"), 6)\n        combo(self.connection_type, CONNECTION_TYPES, 7)\n        entry(self.height, 8)',
        "type combo",
    )
    text = replace_once(
        text,
        '''    def _read_values(self) -> tuple[int, int, float, float] | None:\n        if not self.med.get().strip() or not self.ved.get().strip():\n            return None\n        height = int(float(self.height.get().replace(",", ".")))\n        cover = int(self.cover.get())\n        med = float(self.med.get().replace(",", "."))\n        ved = float(self.ved.get().replace(",", "."))\n        return height, cover, med, ved\n''',
        '''    def _read_values(self) -> tuple[int, int, float, float] | None:\n        med_text = self.med.get().strip()\n        ved_text = self.ved.get().strip()\n        if not med_text and not ved_text:\n            return None\n        height = int(float(self.height.get().replace(",", ".")))\n        cover = int(self.cover.get())\n        med = float((med_text or "0").replace(",", "."))\n        ved = float((ved_text or "0").replace(",", "."))\n        return height, cover, med, ved\n''',
        "optional load fields",
    )
    text = replace_once(
        text,
        '''        candidates, error = database.candidates(\n            self.series.get(), height, cover, self.concrete.get(), med, ved, lengths, self.owner.hit_offsets_var.get()\n        )''',
        '''        candidates, error = database.candidates(\n            self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), med, ved, lengths,\n            self.owner.hit_offsets_var.get(),\n        )''',
        "candidate call",
    )
    text = replace_once(
        text,
        'self._set_error(f"bez vyhovující varianty (tabulková výška h−cnom = {height-cover} mm)")',
        'self._set_error(f"bez vyhovující varianty {self.connection_type.get()} pro zadané zatížení")',
        "generic no result",
    )
    text = replace_once(
        text,
        '''        text += f" • M1/V1 {fmt(candidate.m1)}/{fmt(candidate.v1)} • M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"\n        self.detail.set(text)''',
        '''        if candidate.connection_type == "MVX":\n            text += f" • M1/V1 {fmt(candidate.m1)}/{fmt(candidate.v1)} • M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"\n        else:\n            text += f" • MRd {fmt(candidate.m1)} • VRd {fmt(candidate.v1)}"\n        self.detail.set(text)''',
        "candidate detail",
    )
    text = replace_once(
        text,
        'return {"series": self.series.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med": "", "ved": ""}',
        'return {"series": self.series.get(), "connection_type": self.connection_type.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med": "", "ved": ""}',
        "defaults",
    )
    text = replace_once(
        text,
        '"name": self.name.get().strip(), "series": self.series.get(), "height_mm": candidate.height,',
        '"name": self.name.get().strip(), "series": self.series.get(), "connection_type": candidate.connection_type, "height_mm": candidate.height,',
        "future type",
    )
    text = replace_once(
        text,
        '"m1": candidate.m1, "v1": candidate.v1, "m2": candidate.m2, "v2": candidate.v2,',
        '"m1": candidate.m1, "v1": candidate.v1, "m2": candidate.m2, "v2": candidate.v2, "source_note": candidate.source_note,',
        "future source",
    )
    text = replace_once(
        text,
        'self.hit_l050_var = tk.BooleanVar(value=50 in lengths)\n        self.hit_l025_var =',
        'self.hit_l050_var = tk.BooleanVar(value=50 in lengths)\n        self.hit_l033_var = tk.BooleanVar(value=33 in lengths)\n        self.hit_l025_var =',
        "333 variable",
    )
    text = replace_once(
        text,
        'text=f"HIT-HP/SP MVX • integrovaný modul {HIT_MODULE_VERSION}"',
        'text=f"HIT-HP/SP • MVX / ZVX / ZDX / DD / DVL / DDL • modul {HIT_MODULE_VERSION}"',
        "subtitle",
    )
    text = replace_once(
        text,
        '''        for column, label, variable in ((6, "1000 mm", self.hit_l100_var), (7, "500 mm", self.hit_l050_var), (8, "250 mm", self.hit_l025_var)):\n            ttk.Checkbutton(toolbar, text=label, variable=variable, command=self._hit_options_changed).grid(row=0, column=column, padx=(7, 0))\n        ttk.Checkbutton(toolbar, text="zahrnout OD/OU/WD/WU", variable=self.hit_offsets_var, command=self._hit_options_changed).grid(row=0, column=9, padx=(16, 0))''',
        '''        for column, label, variable in ((6, "1000 mm", self.hit_l100_var), (7, "500 mm", self.hit_l050_var), (8, "333 mm", self.hit_l033_var), (9, "250 mm", self.hit_l025_var)):\n            ttk.Checkbutton(toolbar, text=label, variable=variable, command=self._hit_options_changed).grid(row=0, column=column, padx=(7, 0))\n        ttk.Checkbutton(toolbar, text="MVX: zahrnout OD/OU/WD/WU", variable=self.hit_offsets_var, command=self._hit_options_changed).grid(row=0, column=10, padx=(16, 0))''',
        "length toolbar",
    )
    text = replace_once(
        text,
        'headers = ("Označení", "Řada", "h [mm]", "cnom", "Beton", "MEd [kNm/m]", "VEd [kN/m]", "Navržený výrobek ▼", "Varianty", "Využití", "DoP", "Stav / interakce", "")',
        'headers = ("Označení", "Řada", "Typ", "h [mm]", "cnom", "Beton", "MEd [kNm/m]", "VEd [kN/m]", "Navržený výrobek ▼", "Varianty", "Využití", "Zdroj", "Stav / kontrola", "")',
        "headers",
    )
    text = replace_once(
        text,
        'anchor="w" if column in (0, 7, 11) else "center"',
        'anchor="w" if column in (0, 8, 12) else "center"',
        "header anchors",
    )
    text = replace_once(
        text,
        'weight=1 if column in (0, 7, 11) else 0',
        'weight=1 if column in (0, 8, 12) else 0',
        "header weights",
    )
    old_help = 'ttk.Label(parent, text=("Výpočet používá přímo data z CONF-DOP HIT-HP/SP-07-23. Tabulková výška je h − cnom; skutečné označení se sestaví zpět s plnou výškou a krytím. Kontroluje se |MEd|/|VEd| ≥ 0,15 m a lineární interakční obálka M1/V1–M2/V2. Tento modul je zatím záměrně oddělený od projektového soupisu; provazby doplníme následně."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'
    new_help = 'ttk.Label(parent, text=("MVX se kontroluje interakční obálkou M1/V1–M2/V2 a podmínkou |MEd|/|VEd| ≥ 0,15 m. ZVX/ZDX jsou smykové prvky; DD a DVL/DDL mají samostatnou momentovou a smykovou kontrolu podle příslušných tabulek. Výška v označení HIT je vždy v cm: 200 mm → 20. MVXL, AT, FT a OTX doplníme až s jejich dalšími návrhovými podmínkami."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'
    text = replace_once(text, old_help, new_help, "help")

    old_try = '''    def _try_load_hit_data(self) -> None:\n        path = self._discover_hit_data_path()\n        if path is None:\n            self.hit_db = None\n            self.hit_data_path = None\n            self.hit_source_var.set("Data HIT nejsou načtena. Vyberte originální CONF-DOP HIT-HP/SP-07-23.")\n            return\n        self._load_hit_data(path, quiet=True)\n'''
    new_try = '''    def _try_load_hit_data(self) -> None:\n        path = self._discover_hit_data_path()\n        if path is not None:\n            try:\n                probe = HitDatabase(path)\n                if probe.schema_version >= 2:\n                    self._load_hit_data(path, quiet=True)\n                    return\n            except Exception:\n                pass\n\n        state = self._hit_settings()\n        saved_pdf = str(state.get("source_pdf", "")).strip()\n        source = Path(saved_pdf) if saved_pdf and Path(saved_pdf).exists() else self._discover_managed_hit_source()\n        if source is not None and source.exists():\n            target = self._integrated_hit_data_path()\n            try:\n                self.hit_source_var.set("Aktualizuji databázi HIT pro další typy…")\n                self.update_idletasks()\n                build_database_from_pdf(source, target)\n                state["data_path"] = str(target)\n                state["source_pdf"] = str(source)\n                self._load_hit_data(target, quiet=True)\n                return\n            except Exception as exc:\n                self.hit_source_var.set(f"Automatická migrace HIT selhala: {exc}")\n\n        self.hit_db = None\n        self.hit_data_path = None\n        self.hit_source_var.set("Data HIT nejsou načtena. Vyberte originální CONF-DOP HIT-HP/SP-07-23.")\n'''
    text = replace_once(text, old_try, new_try, "database migration")

    text = replace_once(
        text,
        'self.hit_source_var.set(f"Načteno: {database.source_document} • {len(database.records)} záznamů • SHA {short_hash}…")',
        'total_records = len(database.records) + len(database.zvx_records) + len(database.dd_moment) + len(database.dvl_moment)\n        self.hit_source_var.set(f"Načteno: {database.source_document} • typy {\', \'.join(database.available_connection_types)} • {total_records} záznamů • SHA {short_hash}…")',
        "source status",
    )
    text = replace_once(
        text,
        'if self.hit_l050_var.get(): lengths.add(50)\n        if self.hit_l025_var.get():',
        'if self.hit_l050_var.get(): lengths.add(50)\n        if self.hit_l033_var.get(): lengths.add(33)\n        if self.hit_l025_var.get():',
        "allowed 333",
    )
    text = replace_once(
        text,
        'lines = ["Označení\\tŘada\\th [mm]\\tcnom [mm]\\tBeton\\tMEd [kNm/m]\\tVEd [kN/m]\\tNavržený výrobek\\tVyužití\\tDoP str.\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2"]',
        'lines = ["Označení\\tŘada\\tTyp\\th [mm]\\tcnom [mm]\\tBeton\\tMEd [kNm/m]\\tVEd [kN/m]\\tNavržený výrobek\\tVyužití\\tZdroj\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2"]',
        "copy header",
    )
    text = replace_once(
        text,
        'row.name.get(), row.series.get(), row.height.get(), row.cover.get(), row.concrete.get(), row.med.get(), row.ved.get(), candidate.designation,',
        'row.name.get(), row.series.get(), row.connection_type.get(), row.height.get(), row.cover.get(), row.concrete.get(), row.med.get(), row.ved.get(), candidate.designation,',
        "copy row",
    )
    return text


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)
    shutil.copy2(CORE, OUT / "hit_core.py")

    app = OUT / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    app_text = replace_once(app_text, 'APP_VERSION = "0.7.5"', 'APP_VERSION = "0.8.0"', "app version")
    app.write_text(app_text, encoding="utf-8")

    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    sys.path.insert(0, str(OUT))
    try:
        import hit_core as hc
        assert hc.height_code(200) == "20"
        assert hc.height_code(180) == "18"
        try:
            hc.height_code(205)
        except ValueError:
            pass
        else:
            raise AssertionError("205 mm must be rejected")

        mvx = hc.Candidate("HP", "MVX", "0707", 100, "", 165, "C25/30", 1, 1, 1, 1, 4, 35, 200, .5, "test")
        assert mvx.designation == "HIT-HP MVX-0707-20-100-35"

        payload = {
            "schema_version": 2,
            "source_document": "test",
            "source_sha256": "x",
            "concretes": list(hc.CONCRETES),
            "sections": [],
            "zvx_records": [{"series":"HP","code":"0404","length_code":100,"diameter":"08","h_min":160,"h_max":190,"concrete":"C25/30","vrd":112.0,"page":95}],
            "dd_moment": [{"h_eff":145,"xx":"10","concrete":"C20/25","mrd":50.7}],
            "dvl_moment": [{"h_eff":145,"xx":"16","concrete":"C25/30","mrd":94.3}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "db.b64"
            raw = json.dumps(payload).encode("utf-8")
            db_path.write_text(base64.b64encode(gzip.compress(raw)).decode("ascii"), encoding="ascii")
            db = hc.HitDatabase(db_path)
            z, err = db.candidates("ZDX", "HP", 180, 30, "C25/30", 0, 100, {100})
            assert not err and z and z[0].designation == "HIT-HP ZDX-0404-18-100-30-08"
            dd, err = db.candidates("DD", "HP", 180, 35, "C20/25", 50.7, 55.3, {100})
            assert not err and dd and dd[0].designation == "HIT-HP DD-1007-18-100-35-06"
            dvl, err = db.candidates("DVL", "HP", 180, 35, "C25/30", 94.3, 239.5, {100})
            assert not err and dvl and dvl[0].designation == "HIT-HP DVL-1608-18-100-35-12"

        u, _ = hc.utilization(28, 16, 25, 32, 31, 0)
        assert abs(u - 1.0) < 1e-9
    finally:
        sys.path.pop(0)

    ws_text = workspace.read_text(encoding="utf-8")
    assert 'combo(self.connection_type, CONNECTION_TYPES, 7)' in ws_text
    assert '"333 mm"' in ws_text
    assert 'HIT_MODULE_VERSION = "0.4.0"' in ws_text

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.8.0\n"
        "- HIT označení výšky opraveno globálně: výška se zapisuje v cm (200 mm -> 20), např. HIT-HP MVX-0707-20-100-35.\n"
        "- Návrh HIT rozšířen z MVX také na ZVX, ZDX, DD, DVL a DDL.\n"
        "- ZVX/ZDX používají přímé smykové únosnosti Annexu 3; ZDX má stejnou číselnou únosnost jako odpovídající ZVX v obou směrech.\n"
        "- DD kombinuje momentové hodnoty z Annexu 4 s oficiálními smykovými tabulkami HALFEN HIT 20.2-EN 2023.\n"
        "- DVL/DDL kombinuje momentové hodnoty Annexu 6 s oficiálními smykovými tabulkami HIT 20.2-EN; DVL je jednosměrný smyk, DDL ± smyk.\n"
        "- Přidána délka 333 mm pro ZVX/ZDX; DD a DVL/DDL jsou zatím automaticky ověřovány v úplné 1000mm variantě.\n"
        "- Starší lokální HIT databáze se při startu automaticky přegeneruje ze spravované kopie DoP na nové schéma.\n"
        "- MVXL, AT, FT a OTX zatím nejsou automaticky navrhovány, protože vyžadují další samostatné návrhové podmínky.\n",
        encoding="utf-8",
    )

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_workspace.py", "ui_utils.py",
        "assets/app_icon.png.b64", "schoeck_archive_sources.json", "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.8.0/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.8.0",
        "notes": "HIT rozšířen na MVX, ZVX, ZDX, DD, DVL a DDL. Současně je opraveno značení výšky HIT na centimetrový kód (200 mm = 20). Každá rodina používá vlastní ověřený statický model.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v0.8.0")


if __name__ == "__main__":
    main()
