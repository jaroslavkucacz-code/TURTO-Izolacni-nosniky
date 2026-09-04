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
BASE = ROOT / "updates" / "0.8.3"
OUT = ROOT / "updates" / "0.9.0"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


MVXL_PARSER = r'''

_MVXL_RE = re.compile(
    r"HIT-(HP|SP)\s+MVXL-(\d{4})-hh-(100|050)-cc-(\d{4})"
)
_MVXL_BLOCKS = ((75.0, 220.0), (223.0, 370.0), (372.0, 520.0))


def _parse_number_token(token: str) -> float | None:
    value = str(token).strip().replace("−", "-").replace(",", ".")
    if value in {"", "-", "–", "—"}:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _parse_mvxl_pages(pdf) -> list[dict[str, Any]]:
    """Parse Annex 5 MVXL tables (DoP pages 104-121).

    Each visual block contains one 1000 mm product and, where available, its
    equivalent 500 mm product. The +VRd ranges and -MRd rows are common to both
    because the tables are given per metre. Bond conditions are not a user
    choice: Annex 5 switches from good to poor bond after h-cnom = 300 mm.
    """
    records: list[dict[str, Any]] = []
    width_code = {"100": 100, "050": 50}
    concretes = ("C20/25", "C25/30", "C30/37")

    # PDF indices 103..120 correspond to printed DoP pages 104..121.
    for page_index in range(103, 121):
        page = pdf.pages[page_index]
        all_words = page.extract_words(x_tolerance=1, y_tolerance=1) or []
        for x0, x1 in _MVXL_BLOCKS:
            header_text = page.crop((x0, 0, x1, 105)).extract_text(x_tolerance=1, y_tolerance=2) or ""
            products: list[dict[str, Any]] = []
            seen_product: set[tuple[str, str, int, str]] = set()
            for match in _MVXL_RE.finditer(header_text):
                series, code, width, tail = match.groups()
                key = (series, code, width_code[width], tail)
                if key in seen_product:
                    continue
                seen_product.add(key)
                products.append({
                    "series": series,
                    "code": code,
                    "length_code": width_code[width],
                    "tail": tail,
                })
            if not products:
                continue

            # +VRd range table is located in the upper part of each block.
            top_text = page.crop((x0, 95, x1, 195)).extract_text(x_tolerance=1, y_tolerance=2) or ""
            v_ranges: list[dict[str, Any]] = []
            for raw_line in top_text.splitlines():
                line = " ".join(raw_line.split())
                m = re.match(r"^(\d{3})\s*-\s*(\d{3})\s+(.+)$", line)
                if m:
                    h_min, h_max = int(m.group(1)), int(m.group(2))
                    nums = [_parse_number_token(tok) for tok in m.group(3).split()]
                else:
                    m = re.match(r"^>\s*(\d{3})\s+(.+)$", line)
                    if not m:
                        continue
                    h_min, h_max = int(m.group(1)) + 1, 10000
                    nums = [_parse_number_token(tok) for tok in m.group(2).split()]
                nums = [v for v in nums if v is not None]
                if len(nums) < 3:
                    continue
                v_ranges.append({
                    "h_min": h_min,
                    "h_max": h_max,
                    "values": {concretes[i]: float(nums[i]) for i in range(3)},
                })

            # -MRd rows: group words by their vertical coordinate so extraction
            # is stable even where the PDF inserts the 'Verbundbereich' labels.
            block_words = [
                w for w in all_words
                if x0 <= float(w.get("x0", 0)) < x1 and float(w.get("top", 0)) >= 190
            ]
            groups: list[dict[str, Any]] = []
            for word in sorted(block_words, key=lambda z: (float(z["top"]), float(z["x0"]))):
                target = None
                for group in groups[-4:]:
                    if abs(float(group["top"]) - float(word["top"])) <= 0.9:
                        target = group
                        break
                if target is None:
                    target = {"top": float(word["top"]), "words": []}
                    groups.append(target)
                target["words"].append(word)

            m_rows: list[dict[str, Any]] = []
            for group in groups:
                toks = [str(w["text"]).strip() for w in sorted(group["words"], key=lambda z: float(z["x0"]))]
                if not toks or not re.fullmatch(r"\d{3}", toks[0]):
                    continue
                h_eff = int(toks[0])
                if not 120 <= h_eff <= 500:
                    continue
                values: list[float | None] = []
                for tok in toks[1:]:
                    parsed = _parse_number_token(tok)
                    if parsed is not None or tok in {"-", "–", "—"}:
                        values.append(parsed)
                    if len(values) == 3:
                        break
                if len(values) != 3 or not any(v is not None for v in values):
                    continue
                m_rows.append({
                    "h_eff": h_eff,
                    "bond": "good" if h_eff <= 300 else "poor",
                    "values": {concretes[i]: values[i] for i in range(3)},
                })

            if not v_ranges or not m_rows:
                continue
            for product in products:
                records.append({
                    **product,
                    "page": page_index + 1,
                    "vrd_pos_ranges": v_ranges,
                    "mrd_rows": m_rows,
                })

    # Deduplicate defensively; each designation template must map to one table.
    unique: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for row in records:
        unique[(row["series"], row["code"], int(row["length_code"]), row["tail"])] = row
    return list(unique.values())
'''

MVXL_METHODS = r'''
    def _equivalent_mvx_record(self, series: str, code: str, length_code: int, h_eff: int, concrete: str):
        for row in self.records:
            s, rcode, length, suffix, h, conc, m1, v1, m2, v2, page = row
            if (
                s == series and str(rcode) == str(code) and int(length) == int(length_code)
                and not suffix and int(h) == int(h_eff) and conc == concrete
            ):
                return row
        return None

    @staticmethod
    def _mvxl_value_for_height(record: dict[str, Any], h_eff: int, concrete: str):
        mrd = None
        bond = ""
        for row in record.get("mrd_rows", []):
            if int(row.get("h_eff", -1)) == int(h_eff):
                value = (row.get("values") or {}).get(concrete)
                if value is not None:
                    mrd = abs(float(value))
                    bond = str(row.get("bond") or ("good" if h_eff <= 300 else "poor"))
                break
        vrd_pos = None
        for span in record.get("vrd_pos_ranges", []):
            if int(span.get("h_min", -1)) <= int(h_eff) <= int(span.get("h_max", -1)):
                value = (span.get("values") or {}).get(concrete)
                if value is not None:
                    vrd_pos = abs(float(value))
                break
        return mrd, vrd_pos, bond

    def _mvxl_candidates(
        self, series: str, height: int, cover: int, concrete: str,
        m_neg: float, v_pos: float, v_neg: float, lengths: set[int],
    ):
        if self.schema_version < 3 or not self.mvxl_records:
            return [], "Databáze HIT neobsahuje Annex 5 MVXL. Obnovte ji ze spravovaného DoP."
        if not ({100, 50} & set(lengths)):
            return [], "MVXL je v Annexu 5 veden v délkách 1000 a 500 mm; povolte alespoň jednu z nich."
        h_eff = int(height) - int(cover)
        if h_eff < 0:
            return [], f"Výška h − krytí = {h_eff} mm není platná."

        m_neg = abs(float(m_neg)); v_pos = abs(float(v_pos)); v_neg = abs(float(v_neg))
        out: list[Candidate] = []
        missing_negative_source = False
        for record in self.mvxl_records:
            if record.get("series") != series or int(record.get("length_code", 0)) not in lengths:
                continue
            mrd, vrd_pos, bond = self._mvxl_value_for_height(record, h_eff, concrete)
            if not mrd or not vrd_pos:
                continue
            mu = 0.0 if m_neg <= TOL else m_neg / mrd
            up = max(mu, 0.0 if v_pos <= TOL else v_pos / vrd_pos)
            if up > 1.0 + 1e-9:
                continue

            mvx = self._equivalent_mvx_record(
                series, str(record["code"]), int(record["length_code"]), h_eff, concrete
            )
            m2_eff = 0.0
            v2_eff = 0.0
            un = mu
            neg_mode = ""
            mvx_page = None
            if v_neg > TOL:
                if mvx is None:
                    missing_negative_source = True
                    continue
                _s, _code, _L, _suffix, _h, _conc, mm1, vv1, mm2, vv2, mvx_page = mvx
                mm1 = abs(float(mm1)); vv1 = abs(float(vv1)); mm2 = abs(float(mm2)); vv2 = abs(float(vv2))
                m2_eff, v2_eff = mm2, vv2
                ratio = 0.0 if v_neg <= TOL else m_neg / v_neg
                if ratio <= RATIO_MIN_M + 1e-12:
                    if vv2 <= TOL:
                        continue
                    un = max(mu, v_neg / vv2)
                    neg_mode = f"V− přímá větev MVX V2 ({fmt(vv2)} kN/m; M/V={fmt(ratio,3)} m)"
                else:
                    un, mv_mode = utilization(m_neg, v_neg, mm1, vv1, mm2, vv2)
                    neg_mode = f"V− interakce MVX M1/V1–M2/V2 ({mv_mode})"
                if un > 1.0 + 1e-9:
                    continue
            elif mvx is not None:
                _s, _code, _L, _suffix, _h, _conc, _mm1, _vv1, mm2, vv2, mvx_page = mvx
                m2_eff, v2_eff = abs(float(mm2)), abs(float(vv2))

            u = max(up, un)
            parts = [
                f"MVXL Annex 5 • bond {bond} automaticky",
                f"M− {fmt(mu*100)} %",
            ]
            if v_pos > TOL:
                parts.append(f"V+ {fmt((v_pos/vrd_pos)*100)} %")
            if neg_mode:
                parts.append(neg_mode + f" = {fmt(un*100)} %")
            mode = " • ".join(parts)
            page = f"DoP {record['page']}" + (f" / MVX {mvx_page}" if mvx_page else "")
            note = (
                "MVXL: -MRd a +VRd z Annexu 5; good/poor bond se volí automaticky podle h-cnom. "
                "Zvedající V− se kontroluje proti odpovídajícímu MVX se stejným počtem tahových prutů a CSB."
            )
            out.append(Candidate(
                series, "MVXL", str(record["code"]), int(record["length_code"]), str(record["tail"]),
                h_eff, concrete, mrd, vrd_pos, m2_eff, v2_eff, page, cover, height, u, mode, note,
            ))

        if not out and v_neg > TOL and missing_negative_source:
            return [], "Pro zadané MVXL se nepodařilo dohledat odpovídající MVX pro kontrolu zvedajícího smyku."
        out = list({candidate.designation: candidate for candidate in out}.values())
        out.sort(key=lambda x: (-x.utilization, x.length_code != 100, x.code, x.suffix))
        return out, ""

'''


def patch_core(text: str) -> str:
    text = replace_once(text, 'DATA_FILENAME = "hit_all_2023_v2.json.gz.b64"', 'DATA_FILENAME = "hit_all_2023_v3.json.gz.b64"', "data filename")
    text = replace_once(
        text,
        'CONNECTION_TYPES = ("MVX", "ZVX", "ZDX", "DD", "DVL", "DDL")',
        'CONNECTION_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL")',
        "connection types",
    )
    text = replace_once(
        text,
        '''        if typ == "MVX":\n            tail = f"-{self.suffix}" if self.suffix else ""\n            return f"HIT-{self.series} MVX-{self.code}-{hcode}-{width}-{self.cover:02d}{tail}"\n''',
        '''        if typ == "MVX":\n            tail = f"-{self.suffix}" if self.suffix else ""\n            return f"HIT-{self.series} MVX-{self.code}-{hcode}-{width}-{self.cover:02d}{tail}"\n        if typ == "MVXL":\n            tail = f"-{self.suffix}" if self.suffix else ""\n            return f"HIT-{self.series} MVXL-{self.code}-{hcode}-{width}-{self.cover:02d}{tail}"\n''',
        "MVXL designation",
    )
    text = replace_once(text, '\ndef _parse_moment_page(', MVXL_PARSER + '\n\ndef _parse_moment_page(', "MVXL parser insertion")

    text = replace_once(
        text,
        '''        dvl_moment = _parse_moment_page(pdf.pages[122], ("11", "12", "13", "14", "16"), 10)\n        if len(dvl_moment) < 300:\n            raise RuntimeError("Nepodařilo se bezpečně načíst momentové tabulky DVL/DDL z Annexu 6.")\n''',
        '''        dvl_moment = _parse_moment_page(pdf.pages[122], ("11", "12", "13", "14", "16"), 10)\n        if len(dvl_moment) < 300:\n            raise RuntimeError("Nepodařilo se bezpečně načíst momentové tabulky DVL/DDL z Annexu 6.")\n\n        mvxl_records = _parse_mvxl_pages(pdf)\n        if len(mvxl_records) < 90:\n            raise RuntimeError(f"Z Annexu 5 se podařilo načíst jen {len(mvxl_records)} tabulek MVXL; očekáváno přibližně 96.")\n''',
        "MVXL parse build",
    )
    text = replace_once(text, '"schema_version": 2,', '"schema_version": 3,', "schema v3")
    text = replace_once(text, '"catalog_id": "leviat_hit_hp_sp_07_23_all",', '"catalog_id": "leviat_hit_hp_sp_07_23_all_v3",', "catalog id")
    text = replace_once(
        text,
        '        "dvl_moment": dvl_moment,\n',
        '        "dvl_moment": dvl_moment,\n        "mvxl_records": mvxl_records,\n',
        "payload mvxl",
    )
    text = replace_once(
        text,
        '        self.dvl_moment = list(self.data.get("dvl_moment", []))\n',
        '        self.dvl_moment = list(self.data.get("dvl_moment", []))\n        self.mvxl_records = list(self.data.get("mvxl_records", []))\n',
        "load mvxl",
    )
    text = replace_once(
        text,
        '''        values = ["MVX"]\n        if self.zvx_records:\n''',
        '''        values = ["MVX"]\n        if self.schema_version >= 3 and self.mvxl_records:\n            values.append("MVXL")\n        if self.zvx_records:\n''',
        "available MVXL",
    )

    marker = '        if typ in {"ZVX", "ZDX"}:\n'
    branch = '''        if typ == "MVXL":\n            if a.m_pos > TOL:\n                return [], "MVXL je v Annexu 5 navržen pro záporný moment; MEd+ musí být 0."\n            return self._mvxl_candidates(series, height, cover, concrete, a.m_neg, a.v_pos, a.v_neg, lengths)\n\n'''
    text = replace_once(text, marker, branch + marker, "directional MVXL")

    old = '''        if typ == "MVX":\n            return self._mvx_candidates(series, height, cover, concrete, med, ved, lengths, include_offsets)\n        if self.schema_version < 2:\n'''
    new = '''        if typ == "MVX":\n            return self._mvx_candidates(series, height, cover, concrete, med, ved, lengths, include_offsets)\n        if typ == "MVXL":\n            return self._mvxl_candidates(series, height, cover, concrete, med, ved, 0.0, lengths)\n        if self.schema_version < 2:\n'''
    text = replace_once(text, old, new, "generic MVXL")

    text = replace_once(text, '\n    def _zvx_candidates(', '\n' + MVXL_METHODS + '    def _zvx_candidates(', "MVXL methods")
    return text


def patch_workspace(text: str) -> str:
    text = replace_once(text, 'HIT_MODULE_VERSION = "0.4.3"', 'HIT_MODULE_VERSION = "0.5.0"', "module version")
    text = replace_once(
        text,
        '    "MVX": {"m_pos": False, "m_neg": True,  "v_pos": True, "v_neg": True},\n',
        '    "MVX":  {"m_pos": False, "m_neg": True,  "v_pos": True, "v_neg": True},\n    "MVXL": {"m_pos": False, "m_neg": True,  "v_pos": True, "v_neg": True},\n',
        "MVXL action mask",
    )
    text = replace_once(
        text,
        'text=f"HIT-HP/SP • MVX / ZVX / ZDX / DD / DVL / DDL • modul {HIT_MODULE_VERSION}"',
        'text=f"HIT-HP/SP • MVX / MVXL / ZVX / ZDX / DD / DVL / DDL • modul {HIT_MODULE_VERSION}"',
        "workspace subtitle",
    )
    old_help = (
        'ttk.Label(parent, text=("Vstupy zatížení se automaticky zamykají podle zvoleného typu: '
        'MVX = M−, V±; ZVX = pouze V+; ZDX = V±; DD = M±, V±; DVL = M±, V+; DDL = M±, V±. '
        'Uzamčená pole jsou při výpočtu ignorována, ale jejich dříve zadaná hodnota se zachová pro případné přepnutí zpět. '
        'Do aktivních polí stačí zadat velikost; směr určuje záhlaví. Výška v označení HIT je v cm: 200 mm → 20."), '
        'style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'
    )
    new_help = (
        'ttk.Label(parent, text=("Vstupy se zamykají podle typu: MVX/MVXL = M−, V±; ZVX = pouze V+; ZDX = V±; '
        'DD = M±, V±; DVL = M±, V+; DDL = M±, V±. MVXL používá -MRd/+VRd z Annexu 5; pro zvedající V− '
        'se podle DoP kontroluje odpovídající MVX. Good/poor bond se volí automaticky podle h−cnom, není to ruční volba. '
        'Uzamčená pole jsou ignorována, ale hodnota se zachová pro přepnutí zpět. Výška v označení HIT je v cm: 200 mm → 20."), '
        'style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'
    )
    text = replace_once(text, old_help, new_help, "help text")
    text = replace_once(text, 'if probe.schema_version >= 2:', 'if probe.schema_version >= 3:', "schema migration")
    text = replace_once(
        text,
        'total_records = len(database.records) + len(database.zvx_records) + len(database.dd_moment) + len(database.dvl_moment)',
        'total_records = len(database.records) + len(database.mvxl_records) + len(database.zvx_records) + len(database.dd_moment) + len(database.dvl_moment)',
        "record count",
    )
    text = replace_once(
        text,
        '''        if candidate.connection_type == "MVX":\n            text += f" • M1/V1 {fmt(candidate.m1)}/{fmt(candidate.v1)} • M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"\n        else:\n''',
        '''        if candidate.connection_type == "MVX":\n            text += f" • M1/V1 {fmt(candidate.m1)}/{fmt(candidate.v1)} • M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"\n        elif candidate.connection_type == "MVXL":\n            text += f" • -MRd {fmt(candidate.m1)} • +VRd {fmt(candidate.v1)} • MVX M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"\n        else:\n''',
        "MVXL detail",
    )
    return text


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    core = OUT / "hit_core.py"
    core.write_text(patch_core(core.read_text(encoding="utf-8")), encoding="utf-8")

    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    app = OUT / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    app_text = replace_once(app_text, 'APP_VERSION = "0.8.3"', 'APP_VERSION = "0.9.0"', "app version")
    app.write_text(app_text, encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    sys.path.insert(0, str(OUT))
    try:
        spec = importlib.util.spec_from_file_location("hit_core_v090_test", core)
        hc = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = hc
        spec.loader.exec_module(hc)
        assert "MVXL" in hc.CONNECTION_TYPES
        assert hc.DATA_FILENAME.endswith("v3.json.gz.b64")

        sample = hc.Candidate("HP", "MVXL", "0806", 100, "0810", 165, "C25/30", 100, 200, 80, 90, 104, 35, 200, .5, "test")
        assert sample.designation == "HIT-HP MVXL-0806-20-100-35-0810"

        mvx_row = ["HP", "0806", 100, "", 165, "C25/30", -70.0, 96.0, -100.0, 60.0, 11]
        mvxl = {
            "series":"HP", "code":"0806", "length_code":100, "tail":"0810", "page":104,
            "vrd_pos_ranges":[{"h_min":165,"h_max":210,"values":{"C20/25":190.0,"C25/30":200.0,"C30/37":205.0}}],
            "mrd_rows":[{"h_eff":165,"bond":"good","values":{"C20/25":90.0,"C25/30":100.0,"C30/37":105.0}}],
        }
        payload = {
            "schema_version":3, "source_document":"test", "source_sha256":"x", "concretes":list(hc.CONCRETES),
            "sections":[], "zvx_records":[], "dd_moment":[], "dvl_moment":[], "mvxl_records":[mvxl],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "db.b64"
            raw = json.dumps(payload).encode("utf-8")
            db_path.write_text(base64.b64encode(gzip.compress(raw)).decode("ascii"), encoding="ascii")
            db = hc.HitDatabase(db_path)
            db.records.append(mvx_row)
            assert "MVXL" in db.available_connection_types

            rows, err = db.directional_candidates(
                "MVXL", "HP", 200, 35, "C25/30",
                hc.DirectionalActions(m_neg=50, v_pos=100), {100}, False,
            )
            assert not err and rows
            assert rows[0].designation == "HIT-HP MVXL-0806-20-100-35-0810"
            assert abs(rows[0].utilization - 0.5) < 1e-9

            rows, err = db.directional_candidates(
                "MVXL", "HP", 200, 35, "C25/30",
                hc.DirectionalActions(m_neg=6, v_neg=50), {100}, False,
            )
            assert not err and rows and abs(rows[0].utilization - (50/60)) < 1e-9
            assert "přímá větev" in rows[0].mode

            rows, err = db.directional_candidates(
                "MVXL", "HP", 200, 35, "C25/30",
                hc.DirectionalActions(m_neg=60, v_neg=40), {100}, False,
            )
            assert not err and rows and "interakce MVX" in rows[0].mode

        ws_text = workspace.read_text(encoding="utf-8")
        assert '"MVXL": {"m_pos": False, "m_neg": True' in ws_text
        assert 'HIT_MODULE_VERSION = "0.5.0"' in ws_text
        assert 'probe.schema_version >= 3' in ws_text
        assert 'bond se volí automaticky' in ws_text
    finally:
        sys.path.pop(0)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.9.0\n"
        "- HIT: přidán plnohodnotný typ MVXL pro HP i SP z Annexu 5 CONF-DOP HIT-HP/SP-07-23.\n"
        "- MVXL používá délky 1000 a 500 mm a zachovává úplný koncový kód (např. 0810/1012).\n"
        "- Aktivní směry MVXL jsou MEd−, VEd+ a VEd−; MEd+ je uzamčený.\n"
        "- -MRd a +VRd se berou přímo z tabulek Annexu 5. Good/poor bond se vybere automaticky podle h−cnom (do 300 / od 305 mm).\n"
        "- Zvedající VEd− se podle Annexu 5 váže na odpovídající MVX se stejným počtem tahových prutů a CSB: pro nízký poměr M/V se používá přímá V2 větev, jinak přesná interakce M1/V1–M2/V2.\n"
        "- Databáze HIT je povýšena na schéma 3 a při prvním spuštění se automaticky znovu vytvoří ze spravované kopie DoP.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.9.0/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.9.0",
        "notes": "HIT MVXL doplněn z Annexu 5 včetně směrového návrhu, automatické good/poor bond větve a vazby zvedajícího smyku na odpovídající MVX.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v0.9.0")


if __name__ == "__main__":
    main()
