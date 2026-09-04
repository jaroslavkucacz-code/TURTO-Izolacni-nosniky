from __future__ import annotations

import base64
import gzip
import hashlib
import json
import py_compile
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.8.0"
OUT = ROOT / "updates" / "0.8.1"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def patch_core(text: str) -> str:
    text = replace_once(text, "from dataclasses import dataclass", "from dataclasses import dataclass, replace", "dataclasses import")

    marker = '''\n\n@dataclass(frozen=True)\nclass Candidate:\n'''
    insertion = '''\n\n@dataclass(frozen=True)\nclass DirectionalActions:\n    \"\"\"Obálkové návrhové účinky rozdělené podle znaménka.\n\n    Hodnoty jsou velikosti; směr určuje příslušné pole. Uživatel tedy může\n    současně zadat např. V+ i V-. To je důležité i pro budoucí výrobce,\n    jejichž únosnost nemusí být v obou směrech shodná.\n    \"\"\"\n    m_pos: float = 0.0\n    m_neg: float = 0.0\n    v_pos: float = 0.0\n    v_neg: float = 0.0\n\n    def normalized(self) -> \"DirectionalActions\":\n        return DirectionalActions(\n            abs(float(self.m_pos)), abs(float(self.m_neg)),\n            abs(float(self.v_pos)), abs(float(self.v_neg)),\n        )\n\n    def has_any(self) -> bool:\n        a = self.normalized()\n        return max(a.m_pos, a.m_neg, a.v_pos, a.v_neg) > TOL\n\n\n@dataclass(frozen=True)\nclass Candidate:\n'''
    text = replace_once(text, marker, insertion, "directional actions")

    marker = '''        return tuple(values)\n\n    def candidates(self, connection_type: str, series: str, height: int, cover: int, concrete: str, med: float, ved: float, lengths: set[int], include_offsets: bool = False):\n'''
    method = '''        return tuple(values)\n\n    @staticmethod\n    def _governing_direction(pos: float, neg: float, symbol: str) -> str:\n        pos = abs(float(pos)); neg = abs(float(neg))\n        if pos <= TOL and neg <= TOL:\n            return symbol + "0"\n        if pos > TOL and neg > TOL and abs(pos - neg) <= TOL:\n            return symbol + "±"\n        return symbol + ("+" if pos >= neg else "−")\n\n    @staticmethod\n    def _decorate_directional(rows: list[Candidate], prefix: str) -> list[Candidate]:\n        return [replace(row, mode=f"{prefix} • {row.mode}") for row in rows]\n\n    def directional_candidates(\n        self, connection_type: str, series: str, height: int, cover: int, concrete: str,\n        actions: DirectionalActions, lengths: set[int], include_offsets: bool = False,\n    ):\n        \"\"\"Návrh z obálky M+/M-/V+/V-.\n\n        Pro současné HIT se směrovost aplikuje přesně podle charakteru typu:\n        MVX: pouze záporný moment, smyk ±; ZVX/DVL: jednosměrný smyk;\n        ZDX/DD/DDL: oba směry. API je záměrně směrové, aby pozdější katalogy\n        mohly mít rozdílné kladné a záporné únosnosti bez ztráty informace.\n        \"\"\"\n        a = actions.normalized()\n        typ = str(connection_type or "MVX").upper()\n        series = str(series).upper()\n\n        # Výslovně zadané samé nuly zachovají historické chování a nabídnou varianty s 0% využitím.\n        if not a.has_any():\n            return self.candidates(typ, series, height, cover, concrete, 0.0, 0.0, lengths, include_offsets)\n\n        if typ == "MVX":\n            if a.m_pos > TOL:\n                return [], "MVX je v tomto DoP určen pro záporný moment; MEd+ musí být 0. Pro obousměrný moment zvolte odpovídající jiný typ."\n            load_cases: list[tuple[str, float, float]] = []\n            if a.v_pos > TOL:\n                load_cases.append(("M−/V+", a.m_neg, a.v_pos))\n            if a.v_neg > TOL:\n                load_cases.append(("M−/V−", a.m_neg, a.v_neg))\n            if not load_cases:\n                load_cases.append(("M−", a.m_neg, 0.0))\n\n            case_maps: list[tuple[str, dict[str, Candidate]]] = []\n            for label, med, ved in load_cases:\n                rows, error = self._mvx_candidates(series, height, cover, concrete, med, ved, lengths, include_offsets)\n                if error:\n                    return [], f"{label}: {error}"\n                case_maps.append((label, {row.designation: row for row in rows}))\n\n            common = set(case_maps[0][1])\n            for _label, mapping in case_maps[1:]:\n                common &= set(mapping)\n            out: list[Candidate] = []\n            for designation in common:\n                checked = [(label, mapping[designation]) for label, mapping in case_maps]\n                governing_label, governing = max(checked, key=lambda item: item[1].utilization)\n                summary = ", ".join(f"{label} {fmt(row.utilization * 100.0)} %" for label, row in checked)\n                out.append(replace(\n                    governing,\n                    utilization=max(row.utilization for _label, row in checked),\n                    mode=f"obálka směrů • {summary} • rozhoduje {governing_label}: {governing.mode}",\n                ))\n            out.sort(key=lambda x: (-x.utilization, 0 if not x.suffix else 1, -x.length_code, x.code))\n            return out, ""\n\n        if typ in {"ZVX", "ZDX"}:\n            if a.m_pos > TOL or a.m_neg > TOL:\n                return [], f"{typ} je smykový prvek; MEd+ i MEd− musí být 0."\n            if typ == "ZVX" and a.v_pos > TOL and a.v_neg > TOL:\n                return [], "ZVX přenáší smyk jedním směrem. Pro současné VEd+ i VEd− použijte ZDX nebo dva samostatně orientované prvky."\n            ved = max(a.v_pos, a.v_neg)\n            rows, error = self._zvx_candidates(typ, series, height, cover, concrete, 0.0, ved, lengths)\n            if error:\n                return rows, error\n            vdir = self._governing_direction(a.v_pos, a.v_neg, "V")\n            prefix = f"směrová kontrola • {'orientace ' if typ == 'ZVX' else 'rozhoduje '}{vdir}"\n            return self._decorate_directional(rows, prefix), ""\n\n        if typ == "DD":\n            med = max(a.m_pos, a.m_neg)\n            ved = max(a.v_pos, a.v_neg)\n            rows, error = self._dd_candidates(series, height, cover, concrete, med, ved, lengths)\n            if error:\n                return rows, error\n            mdir = self._governing_direction(a.m_pos, a.m_neg, "M")\n            vdir = self._governing_direction(a.v_pos, a.v_neg, "V")\n            return self._decorate_directional(rows, f"obálka ± • maxima {mdir}/{vdir}"), ""\n\n        if typ in {"DVL", "DDL"}:\n            if typ == "DVL" and a.v_pos > TOL and a.v_neg > TOL:\n                return [], "DVL přenáší smyk jedním směrem. Pro současné VEd+ i VEd− použijte DDL."\n            med = max(a.m_pos, a.m_neg)\n            ved = max(a.v_pos, a.v_neg)\n            rows, error = self._dvl_candidates(typ, series, height, cover, concrete, med, ved, lengths)\n            if error:\n                return rows, error\n            mdir = self._governing_direction(a.m_pos, a.m_neg, "M")\n            vdir = self._governing_direction(a.v_pos, a.v_neg, "V")\n            orientation = "orientace" if typ == "DVL" else "maxima"\n            return self._decorate_directional(rows, f"obálka směrů • {mdir} • {orientation} {vdir}"), ""\n\n        return [], f"Typ HIT {typ} zatím není implementován."\n\n    def candidates(self, connection_type: str, series: str, height: int, cover: int, concrete: str, med: float, ved: float, lengths: set[int], include_offsets: bool = False):\n'''
    text = replace_once(text, marker, method, "directional candidates")
    return text


def patch_workspace(text: str) -> str:
    text = replace_once(
        text,
        "from hit_core import CONCRETES, COVERS, CONNECTION_TYPES, DATA_FILENAME, Candidate, HitDatabase, build_database_from_pdf, fmt",
        "from hit_core import CONCRETES, COVERS, CONNECTION_TYPES, DATA_FILENAME, Candidate, DirectionalActions, HitDatabase, build_database_from_pdf, fmt",
        "workspace import",
    )
    text = replace_once(text, 'HIT_MODULE_VERSION = "0.4.0"', 'HIT_MODULE_VERSION = "0.4.1"', "module version")

    text = replace_once(
        text,
        '''                f"{row.series.get()} {row.connection_type.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "\n                f"MEd {row.med.get()} kNm/m • VEd {row.ved.get()} kN/m"''',
        '''                f"{row.series.get()} {row.connection_type.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "\n                f"MEd+ {row.med_pos.get()} / MEd− {row.med_neg.get()} kNm/m • VEd+ {row.ved_pos.get()} / VEd− {row.ved_neg.get()} kN/m"''',
        "variant subtitle",
    )

    text = replace_once(
        text,
        '''        self.med = tk.StringVar(value=str(defaults.get("med", "")))\n        self.ved = tk.StringVar(value=str(defaults.get("ved", "")))''',
        '''        legacy_med = str(defaults.get("med", ""))\n        legacy_ved = str(defaults.get("ved", ""))\n        self.med_pos = tk.StringVar(value=str(defaults.get("med_pos", "")))\n        self.med_neg = tk.StringVar(value=str(defaults.get("med_neg", legacy_med)))\n        self.ved_pos = tk.StringVar(value=str(defaults.get("ved_pos", legacy_ved)))\n        self.ved_neg = tk.StringVar(value=str(defaults.get("ved_neg", "")))\n        # Dočasné aliasy pro případ návazností vytvořených před v0.8.1.\n        self.med = self.med_neg\n        self.ved = self.ved_pos''',
        "directional variables",
    )

    text = replace_once(
        text,
        '''        entry(self.med, 11)\n        entry(self.ved, 11)''',
        '''        entry(self.med_pos, 9)\n        entry(self.med_neg, 9)\n        entry(self.ved_pos, 9)\n        entry(self.ved_neg, 9)''',
        "directional entries",
    )

    old_read = '''    def _read_values(self) -> tuple[int, int, float, float] | None:\n        med_text = self.med.get().strip()\n        ved_text = self.ved.get().strip()\n        if not med_text and not ved_text:\n            return None\n        height = int(float(self.height.get().replace(",", ".")))\n        cover = int(self.cover.get())\n        med = float((med_text or "0").replace(",", "."))\n        ved = float((ved_text or "0").replace(",", "."))\n        return height, cover, med, ved\n'''
    new_read = '''    def _read_values(self) -> tuple[int, int, DirectionalActions] | None:\n        texts = [self.med_pos.get().strip(), self.med_neg.get().strip(), self.ved_pos.get().strip(), self.ved_neg.get().strip()]\n        if not any(texts):\n            return None\n        height = int(float(self.height.get().replace(",", ".")))\n        cover = int(self.cover.get())\n\n        def load_value(text: str) -> float:\n            return abs(float((text or "0").replace(",", ".")))\n\n        actions = DirectionalActions(\n            m_pos=load_value(texts[0]), m_neg=load_value(texts[1]),\n            v_pos=load_value(texts[2]), v_neg=load_value(texts[3]),\n        )\n        return height, cover, actions\n'''
    text = replace_once(text, old_read, new_read, "read directional values")

    text = replace_once(
        text,
        '''        height, cover, med, ved = values\n        lengths = self.owner.allowed_hit_lengths()''',
        '''        height, cover, actions = values\n        lengths = self.owner.allowed_hit_lengths()''',
        "recalc unpack",
    )
    text = replace_once(
        text,
        '''        candidates, error = database.candidates(\n            self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), med, ved, lengths,\n            self.owner.hit_offsets_var.get(),\n        )''',
        '''        candidates, error = database.directional_candidates(\n            self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), actions, lengths,\n            self.owner.hit_offsets_var.get(),\n        )''',
        "directional candidate call",
    )

    text = replace_once(
        text,
        'return {"series": self.series.get(), "connection_type": self.connection_type.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med": "", "ved": ""}',
        'return {"series": self.series.get(), "connection_type": self.connection_type.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med_pos": "", "med_neg": "", "ved_pos": "", "ved_neg": ""}',
        "defaults",
    )

    text = replace_once(
        text,
        '''            "cover_mm": candidate.cover, "concrete": candidate.concrete, "med": self.med.get().strip(),\n            "ved": self.ved.get().strip(), "designation": candidate.designation, "utilization": candidate.utilization,''',
        '''            "cover_mm": candidate.cover, "concrete": candidate.concrete,\n            "med_pos": self.med_pos.get().strip(), "med_neg": self.med_neg.get().strip(),\n            "ved_pos": self.ved_pos.get().strip(), "ved_neg": self.ved_neg.get().strip(),\n            "med": self.med_neg.get().strip(), "ved": self.ved_pos.get().strip(),\n            "designation": candidate.designation, "utilization": candidate.utilization,''',
        "future payload directions",
    )

    text = replace_once(
        text,
        'headers = ("Označení", "Řada", "Typ", "h [mm]", "cnom", "Beton", "MEd [kNm/m]", "VEd [kN/m]", "Navržený výrobek ▼", "Varianty", "Využití", "Zdroj", "Stav / kontrola", "")',
        'headers = ("Označení", "Řada", "Typ", "h [mm]", "cnom", "Beton", "MEd+", "MEd−", "VEd+", "VEd−", "Navržený výrobek ▼", "Varianty", "Využití", "Zdroj", "Stav / kontrola", "")',
        "headers",
    )
    text = replace_once(text, 'anchor="w" if column in (0, 8, 12) else "center"', 'anchor="w" if column in (0, 10, 14) else "center"', "header anchors")
    text = replace_once(text, 'weight=1 if column in (0, 8, 12) else 0', 'weight=1 if column in (0, 10, 14) else 0', "header weights")

    old_help = 'ttk.Label(parent, text=("MVX se kontroluje interakční obálkou M1/V1–M2/V2 a podmínkou |MEd|/|VEd| ≥ 0,15 m. ZVX/ZDX jsou smykové prvky; DD a DVL/DDL mají samostatnou momentovou a smykovou kontrolu podle příslušných tabulek. Výška v označení HIT je vždy v cm: 200 mm → 20. MVXL, AT, FT a OTX doplníme až s jejich dalšími návrhovými podmínkami."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'
    new_help = 'ttk.Label(parent, text=("Zatížení lze zadat současně ve směrech +/−; do polí stačí zadat velikost a směr určuje záhlaví. Program pracuje s obálkou směrových maxim. MVX používá záporný moment a kontroluje oba směry smyku; ZVX a DVL jsou jednosměrné ve smyku, zatímco ZDX, DD a DDL kontrolují oba směry. Toto směrové rozhraní je připravené i pro další výrobce s rozdílnou únosností V+ a V−. Výška v označení HIT je v cm: 200 mm → 20."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'
    text = replace_once(text, old_help, new_help, "help")

    text = replace_once(
        text,
        'lines = ["Označení\\tŘada\\tTyp\\th [mm]\\tcnom [mm]\\tBeton\\tMEd [kNm/m]\\tVEd [kN/m]\\tNavržený výrobek\\tVyužití\\tZdroj\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2"]',
        'lines = ["Označení\\tŘada\\tTyp\\th [mm]\\tcnom [mm]\\tBeton\\tMEd+ [kNm/m]\\tMEd− [kNm/m]\\tVEd+ [kN/m]\\tVEd− [kN/m]\\tNavržený výrobek\\tVyužití\\tZdroj\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2"]',
        "copy header",
    )
    text = replace_once(
        text,
        'row.name.get(), row.series.get(), row.connection_type.get(), row.height.get(), row.cover.get(), row.concrete.get(), row.med.get(), row.ved.get(), candidate.designation,',
        'row.name.get(), row.series.get(), row.connection_type.get(), row.height.get(), row.cover.get(), row.concrete.get(), row.med_pos.get(), row.med_neg.get(), row.ved_pos.get(), row.ved_neg.get(), candidate.designation,',
        "copy row",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    app = OUT / "app.pyw"
    app_text = replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "0.8.0"', 'APP_VERSION = "0.8.1"', "app version")
    app.write_text(app_text, encoding="utf-8")

    core = OUT / "hit_core.py"
    core.write_text(patch_core(core.read_text(encoding="utf-8")), encoding="utf-8")
    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    sys.path.insert(0, str(OUT))
    try:
        import hit_core as hc
        a = hc.DirectionalActions(m_pos=-10, m_neg=-20, v_pos=30, v_neg=-40).normalized()
        assert (a.m_pos, a.m_neg, a.v_pos, a.v_neg) == (10.0, 20.0, 30.0, 40.0)

        payload = {
            "schema_version": 2,
            "source_document": "test",
            "source_sha256": "x",
            "concretes": list(hc.CONCRETES),
            "ratio_min_m": 0.15,
            "sections": [[
                ["HIT-HP MVX-0707-hh-100-cc"],
                [[165, -50.0, 100.0, -80.0, 50.0, -50.0, 100.0, -80.0, 50.0, -50.0, 100.0, -80.0, 50.0]],
                4,
            ]],
            "zvx_records": [{"series":"HP","code":"0404","length_code":100,"diameter":"08","h_min":160,"h_max":190,"concrete":"C25/30","vrd":112.0,"page":95}],
            "dd_moment": [{"h_eff":145,"xx":"10","concrete":"C20/25","mrd":50.7}],
            "dvl_moment": [{"h_eff":145,"xx":"16","concrete":"C25/30","mrd":94.3}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "db.b64"
            raw = json.dumps(payload).encode("utf-8")
            db_path.write_text(base64.b64encode(gzip.compress(raw)).decode("ascii"), encoding="ascii")
            db = hc.HitDatabase(db_path)

            mvx, err = db.directional_candidates("MVX", "HP", 200, 35, "C25/30", hc.DirectionalActions(m_neg=30, v_pos=40, v_neg=20), {100})
            assert not err and mvx and mvx[0].designation == "HIT-HP MVX-0707-20-100-35"
            assert "M−/V+" in mvx[0].mode and "M−/V−" in mvx[0].mode
            mvx_bad, err = db.directional_candidates("MVX", "HP", 200, 35, "C25/30", hc.DirectionalActions(m_pos=5, m_neg=30, v_pos=20), {100})
            assert not mvx_bad and "MEd+" in err

            zvx_bad, err = db.directional_candidates("ZVX", "HP", 180, 30, "C25/30", hc.DirectionalActions(v_pos=50, v_neg=40), {100})
            assert not zvx_bad and "ZVX přenáší smyk jedním směrem" in err
            zdx, err = db.directional_candidates("ZDX", "HP", 180, 30, "C25/30", hc.DirectionalActions(v_pos=80, v_neg=100), {100})
            assert not err and zdx and "V−" in zdx[0].mode

            dd, err = db.directional_candidates("DD", "HP", 180, 35, "C20/25", hc.DirectionalActions(m_pos=40, m_neg=50.7, v_pos=50, v_neg=55.3), {100})
            assert not err and dd and dd[0].designation == "HIT-HP DD-1007-18-100-35-06"
            assert "M−/V−" in dd[0].mode

            dvl_bad, err = db.directional_candidates("DVL", "HP", 180, 35, "C25/30", hc.DirectionalActions(m_pos=90, m_neg=94.3, v_pos=100, v_neg=239.5), {100})
            assert not dvl_bad and "DVL přenáší smyk jedním směrem" in err
            ddl, err = db.directional_candidates("DDL", "HP", 180, 35, "C25/30", hc.DirectionalActions(m_pos=90, m_neg=94.3, v_pos=100, v_neg=239.5), {100})
            assert not err and ddl and ddl[0].designation == "HIT-HP DDL-1608-18-100-35-12"

            # Legacy API remains usable for older integrations.
            legacy, err = db.candidates("ZDX", "HP", 180, 30, "C25/30", 0, 100, {100})
            assert not err and legacy
    finally:
        sys.path.pop(0)

    ws_text = workspace.read_text(encoding="utf-8")
    assert 'HIT_MODULE_VERSION = "0.4.1"' in ws_text
    assert '"MEd+", "MEd−", "VEd+", "VEd−"' in ws_text
    assert "database.directional_candidates(" in ws_text
    assert "row.med_pos.get()" in ws_text and "row.ved_neg.get()" in ws_text

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.8.1\n"
        "- Návrh HIT má samostatné vstupy MEd+, MEd−, VEd+ a VEd−; oba směry lze zadat současně.\n"
        "- Směr určuje sloupec, takže lze zadávat velikosti bez znaménka; případné napsané znaménko se bezpečně převede na velikost.\n"
        "- MVX kontroluje záporný moment proti V+ i V− přes interakční obálku; kladný moment u MVX se výslovně odmítne.\n"
        "- ZVX a DVL jsou jednosměrné ve smyku: při současném V+ a V− program upozorní na ZDX/DDL.\n"
        "- ZDX, DD a DDL kontrolují obě smyková znaménka; DD/DDL současně kontrolují oba směry momentu.\n"
        "- Směrové API je připravené pro budoucí výrobce s rozdílnými únosnostmi v kladném a záporném směru.\n"
        "- Kopírování výsledků a budoucí provazby předávají všechny čtyři směrové vstupy samostatně.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.8.1/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.8.1",
        "notes": "HIT nyní přijímá současně kladné i záporné návrhové účinky MEd+/MEd−/VEd+/VEd− a zachovává směrovost pro budoucí výrobce s asymetrickými únosnostmi.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v0.8.1")


if __name__ == "__main__":
    main()
