"""Build verified TURTO ISO v1.1.17 with HIT-HT horizontal-force design."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.17"
BASE = ROOT / "updates/1.1.16"
OUT = ROOT / "updates" / VERSION
REPO = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
sys.dont_write_bytecode = True

NOTES = '''TURTO ISO v1.1.17 – HIT-HT a bezpečné oddělení vodorovných sil
- Návrh HIT rozlišuje běžné MEd/VEd [na metr] od vodorovných HEd∥/HEd⊥ [kN/prvek]. Lineární zatížení se na sílu HT nikdy nepřevádí automaticky.
- Hromadný výkaz umí načíst HEd∥ a HEd⊥ v kN/prvek (také kN/element nebo kN/ks), zobrazit je v kontrolním náhledu a vložit jako typ HT.
- HIT-HP HT má katalogovou šířku B = 100 mm, HIT-SP HT B = 150 mm. Výkaz i ruční řádek musí této šířce přesně odpovídat.
- Automaticky se navrhují HIT-HT1, HT2 a HT3 podle katalogových HRd a výšky h = 160–350 mm. HT1 = H∥, HT2 = H⊥, HT3 = oba směry.
- HT4/HT5 se z bezpečnostních důvodů automaticky nevybírají: katalog je pro odpor proti zvedacímu momentu váže na kombinaci s HIT-MVX. Pokud HT1–HT3 nestačí, program na toto omezení výslovně upozorní.
- Původní řádek „Smykový isonosník délky 0,1 m · VEd = … kN/m“ se nepřevádí na HT jen podle délky. Zůstává svislým smykovým zadáním a požaduje vyřešení typu/zatížení.
- Stávající délky 1000/500/333/250 mm a návrhy MVX/MVXL/ZVX/ZDX/DD/DVL/DDL/AT/FT/OTX zůstávají beze změny; předchozí regresní sada se spouští znovu.
- Zdroj HT: HALFEN HIT Insulated Connection ©2023, HIT 20.2-EN, katalogové tabulky HT1–HT3 na stranách 121–123.
'''

def change(text, old, new, count=1):
    if text.count(old) != count:
        raise RuntimeError(f"Expected {count} patch anchors, found {text.count(old)}: {old[:100]}")
    return text.replace(old, new)


def load_test(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

SCHEDULE_PREFIX = '"""Clipboard schedule import for regular HIT and horizontal HIT-HT actions."""\nfrom __future__ import annotations\n\nfrom dataclasses import dataclass, field\nimport math\nimport re\nimport unicodedata\nimport tkinter as tk\nfrom tkinter import messagebox, ttk\n\nfrom hit_ht import HT_WIDTH_MM, validate_ht_width\n\nLENGTH_CODES = {1000: 100, 500: 50, 333: 33, 250: 25}\nDEFAULTS = dict(height="200", cover="35", concrete="C25/30", series="HP",\n                bending="MVX", shear="ZVX", moment="MEd− (konzola)")\nPARAMS = (\n    ("height", "Výška h [mm]", tuple(str(n) for n in range(160, 401, 10))),\n    ("cover", "Krytí cnom [mm]", ("30", "35", "50")),\n    ("concrete", "Beton", ("C20/25", "C25/30", "C30/37")),\n    ("series", "Řada", ("HP", "SP")),\n    ("bending", "Ohybové prvky →", ("MVX", "MVXL", "DD", "DVL", "DDL")),\n    ("shear", "Smykové prvky →", ("ZVX", "ZDX")),\n    ("moment", "MEd bez znaménka →", ("MEd− (konzola)", "MEd+")),\n)\nDIRECTIONS = {\n    "MVX": {"med_neg", "ved_pos", "ved_neg"},\n    "MVXL": {"med_neg", "ved_pos", "ved_neg"},\n    "DD": {"med_pos", "med_neg", "ved_pos", "ved_neg"},\n    "DVL": {"med_pos", "med_neg", "ved_pos"},\n    "DDL": {"med_pos", "med_neg", "ved_pos", "ved_neg"},\n    "ZVX": {"ved_pos"}, "ZDX": {"ved_pos", "ved_neg"},\n}\nNUMBER = r"[+-]?\\s*(?:\\d{1,3}(?:[ ]\\d{3})+|\\d+)(?:[.,]\\d+)?"\nFIELD = re.compile(r"(?<![a-z])([mv])\\s*_?\\s*e\\s*_?\\s*d\\s*([+-]?)\\s*[=:]")\nHFIELD = re.compile(\n    r"(?<![a-z])h\\s*_?\\s*e\\s*_?\\s*d\\s*"\n    r"(?P<dir>\\|\\||∥|⊥|parallel(?:ni)?|paralel(?:ni)?|kolmo|perp(?:endicular)?)\\s*[=:]"\n)\nLENGTH = re.compile(r"\\b(?:delky|delka|l)\\s*[=:]?\\s*(" + NUMBER + r")\\s*(mm|cm|m)\\b")\n\ndef normalized(text: str) -> str:\n    text = unicodedata.normalize("NFKC", text).replace("−", "-").replace("–", "-")\n    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()\n\ndef number(text: str) -> float:\n    value = float(text.replace(" ", "").replace(",", "."))\n    if not math.isfinite(value) or abs(value) > 1e9:\n        raise ValueError("Číslo je mimo podporovaný rozsah.")\n    return value\n\ndef text_number(value: float) -> str:\n    return format(value, ".12g").replace(".", ",")\n\ndef _h_direction(token: str) -> str:\n    token = str(token).lower()\n    return "perp" if token in {"⊥", "kolmo", "perp", "perpendicular"} else "parallel"\n\n@dataclass\nclass ScheduleRecord:\n    line: int\n    source: str\n    kind: str\n    med: float | None = None\n    ved: float | None = None\n    h_parallel: float | None = None\n    h_perp: float | None = None\n    m_sign: str = ""\n    v_sign: str = ""\n    length_mm: int | None = None\n    errors: list[str] = field(default_factory=list)\n\ndef parse_schedule(text: str) -> list[ScheduleRecord]:\n    if len(text) > 1_000_000:\n        raise ValueError("Výkaz je příliš dlouhý; vložte nejvýše 1 MB textu.")\n    result = []\n    for lineno, original in enumerate(text.splitlines(), 1):\n        source = original.strip().strip("|").strip()\n        if not source or re.fullmatch(r"[\\s|:\\-–]+", source):\n            continue\n        value = normalized(source)\n        if re.fullmatch(r"(?:popis|nazev|polozka|oznaceni)(?:\\s+(?:prvku|polozky))?", value):\n            continue\n        matches = list(FIELD.finditer(value))\n        hmatches = list(HFIELD.finditer(value))\n        if hmatches:\n            kind = "HT"\n        else:\n            kind = "Smykový" if "smykov" in value else "Ohybový" if "ohybov" in value else (\n                "Ohybový" if any(m[1] == "m" for m in matches) else "Smykový")\n        row = ScheduleRecord(lineno, source, kind)\n        if matches and hmatches:\n            row.errors.append("MEd/VEd a HEd jsou v jednom řádku smíchané. HT zadávejte samostatně v kN/prvek.")\n        if not matches and not hmatches:\n            row.errors.append("Nerozpoznané zadání: očekáváno MEd/VEd nebo HEd∥/HEd⊥.")\n        if re.search(r"\\bn\\s*_?e\\s*_?d\\s*[+-]?\\s*[=:]", value):\n            row.errors.append("Import NEd není podporován; tento řádek zadejte ručně.")\n\n        seen = set()\n        for index, match in enumerate(matches):\n            key = match[1]\n            label = "MEd" if key == "m" else "VEd"\n            if key in seen:\n                row.errors.append(f"{label} je uvedeno vícekrát; řádek musí obsahovat jednu hodnotu pro každý účinek.")\n                continue\n            seen.add(key)\n            tail = value[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(value)]\n            numeric = re.match(r"\\s*(" + NUMBER + r")", tail)\n            if not numeric:\n                row.errors.append(f"{label}: chybí platné číslo.")\n                continue\n            try:\n                amount = number(numeric[1])\n            except ValueError:\n                row.errors.append(f"{label}: neplatné číslo.")\n                continue\n            unit_match = re.match(r"\\s*(kn\\s*(?:[*.·]\\s*)?m?\\s*(?:/\\s*(?:m|ks|prvek|element))?)(?![a-z0-9/])", tail[numeric.end():])\n            unit = re.sub(r"[\\s*.·]", "", unit_match[1]) if unit_match else ""\n            expected = "knm/m" if key == "m" else "kn/m"\n            if unit != expected:\n                row.errors.append(f"{label}: očekávány {\'kNm/m\' if key == \'m\' else \'kN/m\'}; hodnoty se nepřevádějí automaticky.")\n            raw_sign = numeric[1].strip()[:1]\n            explicit = raw_sign if raw_sign in {"+", "-"} else ""\n            if match[2] and explicit and match[2] != explicit:\n                row.errors.append(f"{label}: rozporná znaménka názvu pole a hodnoty.")\n            sign = match[2] or explicit\n            if key == "m":\n                row.med, row.m_sign = abs(amount), sign\n            else:\n                row.ved, row.v_sign = abs(amount), sign\n\n        seen_h = set()\n        for index, match in enumerate(hmatches):\n            direction = _h_direction(match.group("dir"))\n            label = "HEd∥" if direction == "parallel" else "HEd⊥"\n            if direction in seen_h:\n                row.errors.append(f"{label} je uvedeno vícekrát.")\n                continue\n            seen_h.add(direction)\n            tail = value[match.end():hmatches[index + 1].start() if index + 1 < len(hmatches) else len(value)]\n            numeric = re.match(r"\\s*(" + NUMBER + r")", tail)\n            if not numeric:\n                row.errors.append(f"{label}: chybí platné číslo.")\n                continue\n            try:\n                amount = abs(number(numeric[1]))\n            except ValueError:\n                row.errors.append(f"{label}: neplatné číslo.")\n                continue\n            unit_match = re.match(r"\\s*(kn\\s*/\\s*(?:ks|prvek|element))(?![a-z0-9/])", tail[numeric.end():])\n            if not unit_match:\n                row.errors.append(\n                    f"{label}: pro HIT-HT použijte kN/prvek (ne kN/m). "\n                    "Program lineární zatížení na sílu jednoho HT automaticky nepřevádí."\n                )\n            if direction == "parallel":\n                row.h_parallel = amount\n            else:\n                row.h_perp = amount\n\n        lengths = list(LENGTH.finditer(value))\n        if len(lengths) > 1:\n            row.errors.append("Délka je uvedena vícekrát; ponechte jednu jednoznačnou délku.")\n        if lengths:\n            try:\n                millimetres = number(lengths[0][1]) * {"m": 1000, "cm": 10, "mm": 1}[lengths[0][2]]\n                if not 0 < millimetres <= 100_000 or not math.isclose(millimetres, round(millimetres), abs_tol=1e-6):\n                    raise ValueError()\n                row.length_mm = round(millimetres)\n            except ValueError:\n                row.errors.append("Délka musí být kladná a vyjádřitelná v celých mm.")\n        elif re.search(r"\\b(?:delky|delka)\\b|\\bl\\s*[=:]", value):\n            row.errors.append("Délka nebyla rozpoznána; použijte např. délky 0,5 m nebo L = 500 mm.")\n\n        if kind == "HT":\n            if (row.h_parallel or 0) == 0 and (row.h_perp or 0) == 0:\n                row.errors.append("U HT chybí nenulové HEd∥ nebo HEd⊥.")\n        else:\n            if row.ved is None:\n                row.errors.append("Chybí VEd.")\n            if kind == "Ohybový" and row.med is None:\n                row.errors.append("U ohybového prvku chybí MEd.")\n            if kind == "Smykový" and row.med:\n                row.errors.append("Smykový prvek obsahuje nenulový MEd; opravte druh prvku.")\n            if row.ved is not None and row.ved == 0 and (row.med or 0) == 0:\n                row.errors.append("Všechny návrhové účinky jsou nulové.")\n        result.append(row)\n        if len(result) > 500:\n            raise ValueError("Najednou lze vložit nejvýše 500 pozic; výkaz rozdělte na části.")\n    return result\n\ndef row_defaults(row: ScheduleRecord, options: dict[str, str], name: str) -> dict[str, str]:\n    if row.errors:\n        raise ValueError(" • ".join(row.errors))\n    options = {**DEFAULTS, **options}\n    try:\n        height = int(options["height"].strip())\n        if height <= 0 or height > 1000 or height % 10:\n            raise ValueError()\n    except (ValueError, TypeError):\n        raise ValueError("Výška musí být kladné celé číslo v mm po 10 mm (např. 200).") from None\n    for key, _label, choices in PARAMS[1:]:\n        if options[key] not in choices:\n            raise ValueError("Neplatná hodnota: " + _label)\n\n    common = dict(\n        name=name, height=str(height), concrete=options["concrete"], series=options["series"],\n        required_length=str(row.length_mm or ""), import_source_text=row.source,\n        import_source_line=str(row.line), mvx_variant="Bez", mvx_bx="",\n        med_pos="", med_neg="", ved_pos="", ved_neg="", ned_pos="", ned_neg="",\n        hed_parallel="", hed_perp="", load_x=""\n    )\n    if row.kind == "HT":\n        expected = HT_WIDTH_MM[options["series"]]\n        width = row.length_mm or expected\n        validate_ht_width(str(width), options["series"])\n        common.update(\n            connection_type="HT", cover=options["cover"], required_length=str(width),\n            hed_parallel=text_number(row.h_parallel or 0) if (row.h_parallel or 0) else "",\n            hed_perp=text_number(row.h_perp or 0) if (row.h_perp or 0) else "",\n        )\n        return common\n\n    typ = options["bending"] if row.kind == "Ohybový" else options["shear"]\n    common.update(connection_type=typ, cover="30" if typ in {"ZVX", "ZDX"} else options["cover"])\n    if row.med is not None:\n        sign = row.m_sign or ("-" if options["moment"] == "MEd− (konzola)" else "+")\n        key = "med_neg" if sign == "-" else "med_pos"\n        if row.med and key not in DIRECTIONS[typ]:\n            raise ValueError(f"{typ} nepřijímá MEd{sign}; změňte přiřazení typu nebo směr podle skutečného zadání.")\n        common[key] = text_number(row.med)\n    key = "ved_neg" if row.v_sign == "-" else "ved_pos"\n    if row.ved and key not in DIRECTIONS[typ]:\n        raise ValueError(f"{typ} nepřijímá VEd−; pro oba směry lze v přiřazení zvolit ZDX.")\n    common[key] = text_number(row.ved or 0)\n    return common\n\ndef required_length_codes(text: str, allowed: set[int]) -> set[int]:\n    text = str(text).strip()\n    if not text:\n        if not allowed:\n            raise ValueError("Není povolena žádná délka HIT.")\n        return set(allowed)\n    try:\n        length = int(text)\n        if str(length) != text or length <= 0:\n            raise ValueError()\n    except ValueError:\n        raise ValueError("L požadované: zadejte kladné celé mm, nebo nechte pole prázdné.") from None\n    if length not in LENGTH_CODES:\n        if length in {100, 150}:\n            raise ValueError(\n                f"L = {length} mm není standardní délka běžného M/V HIT. "\n                "Krátký HIT-HT se vybírá podle HEd∥/HEd⊥ v kN/prvek "\n                "(HP: B 100 mm, SP: B 150 mm), nikoli podle svislého VEd v kN/m."\n            )\n        raise ValueError(f"L = {length} mm: v tomto návrháři není shodná katalogová délka běžného HIT.")\n    code = LENGTH_CODES[length]\n    if code not in allowed:\n        raise ValueError(f"Pro tento řádek je nutné nahoře povolit délku {length} mm.")\n    return {code}\n\n'

def patch_schedule(text: str) -> str:
    marker = "SAMPLE_PAIRS ="
    i = text.find(marker)
    if i < 0:
        raise RuntimeError("Schedule sample marker missing")
    text = SCHEDULE_PREFIX + text[i:]
    old_example = 'EXAMPLE = "\\n".join([f"Ohybový isonosník · Ved = {v} kN/m, Med = {m} kNm/m" for v,m in SAMPLE_PAIRS] +\n                    [f"Smykový isonosník · Ved = {v} kN/m" for v in (30,65,90)] +\n                    ["Smykový isonosník délky 0.1m · Ved = 50 kN/m", "Smykový isonosník délky 0.5m · Ved = 70 kN/m"])'
    new_example = old_example + '\nHT_EXAMPLE = "\\n".join((\n    "HT vodorovně ∥ · délky 0,1 m · HEd∥ = 8 kN/prvek",\n    "HT vodorovně ⊥ · délky 0,1 m · HEd⊥ = 15 kN/prvek",\n    "HT oba směry · délky 0,1 m · HEd∥ = 8 kN/prvek, HEd⊥ = 15 kN/prvek",\n))'
    text = change(text, old_example, new_example)
    text = change(
        text,
        '("med_pos", "med_neg", "ved_pos", "ved_neg", "ned_pos", "ned_neg", "load_x", "required_length")))',
        '("med_pos", "med_neg", "ved_pos", "ved_neg", "ned_pos", "ned_neg", "hed_parallel", "hed_perp", "load_x", "required_length")))'
    )
    text = change(
        text,
        'ttk.Button(bar,text="Ukázkový výkaz (33 pozic)",command=self.example).pack(side="left")',
        'ttk.Button(bar,text="Ukázkový výkaz (33 pozic)",command=self.example).pack(side="left")\n        ttk.Button(bar,text="Ukázka HT",command=self.example_ht).pack(side="left",padx=(6,0))'
    )
    text = change(
        text,
        'columns=("use","name","kind","m","v","length","height","cover","concrete","series","type","check")',
        'columns=("use","name","kind","m","v","hpar","hperp","length","height","cover","concrete","series","type","check")'
    )
    text = change(
        text,
        'labels=("✓","Pozice","Druh","MEd [kNm/m]","VEd [kN/m]","L [mm]","h [mm]","cnom","Beton","Řada","Typ HIT","Kontrola")\n        widths=(34,64,78,108,100,65,60,55,85,50,65,285)',
        'labels=("✓","Pozice","Druh","MEd [kNm/m]","VEd [kN/m]","HEd∥ [kN/prv.]","HEd⊥ [kN/prv.]","L/B [mm]","h [mm]","cnom","Beton","Řada","Typ HIT","Kontrola")\n        widths=(34,64,78,108,100,108,108,70,60,55,85,50,65,285)'
    )
    text = change(
        text,
        'ttk.Label(outer,text="ZVX/ZDX mají v návrháři pevné cnom 30 mm. Uvedená délka je závazný požadavek, prázdná používá horní volbu délek. Síly zůstávají na metr. Nejde o schválení statického řešení.",wraplength=1090,style="Muted.TLabel").grid(row=8,column=0,sticky="ew",pady=6)',
        'ttk.Label(outer,text="MEd/VEd zůstávají na metr. HIT-HT používá výhradně HEd∥/HEd⊥ v kN/prvek; program kN/m na sílu prvku nepřevádí. HP HT má B=100 mm, SP HT B=150 mm. ZVX/ZDX mají pevné cnom 30 mm. Nejde o schválení statického řešení.",wraplength=1090,style="Muted.TLabel").grid(row=8,column=0,sticky="ew",pady=6)'
    )
    text = change(
        text,
        'ttk.Checkbutton(outer,text="Potvrzuji přiřazení typů a směrů MEd/VEd podle skutečného zadání (viz náhled).",variable=self.ack,command=self.render).grid(row=9,column=0,sticky="w")',
        'ttk.Checkbutton(outer,text="Potvrzuji přiřazení MEd/VEd/HEd a jejich jednotek podle skutečného zadání (viz náhled).",variable=self.ack,command=self.render).grid(row=9,column=0,sticky="w")'
    )
    text = change(
        text,
        '    def analyze(self):',
        '    def example_ht(self):\n        self.text.delete("1.0","end");self.text.insert("1.0",HT_EXAMPLE);self.analyze()\n\n    def analyze(self):'
    )
    old_render = """            try:
                payload=row_defaults(row,opt,name);self.payloads[i]=payload
                check="Připraveno";tag=()
                try:required_length_codes(payload["required_length"],self.owner.allowed_hit_lengths())
                except ValueError as exc:
                    check=str(exc);tag=("warning",)
                    if i in self.included:warnings+=1
                m=("−" if payload["med_neg"] else "+")+(payload["med_neg"] or payload["med_pos"] or "0")
                v=("−" if payload["ved_neg"] else "+")+(payload["ved_neg"] or payload["ved_pos"] or "0")
                typ=payload["connection_type"];cover=payload["cover"]
            except ValueError as exc:
                check=str(exc);tag=("error",);m="—" if row.med is None else text_number(row.med);v="—" if row.ved is None else text_number(row.ved)
                typ=opt["bending"] if row.kind=="Ohybový" else opt["shear"];cover=opt["cover"]
                if i in self.included:errors+=1
            self.tree.insert("","end",iid=str(i),tags=tag,values=("✓" if i in self.included else "—",name,row.kind,m,v,row.length_mm or "—",opt["height"],cover,opt["concrete"],opt["series"],typ,check))"""
    new_render = """            try:
                payload=row_defaults(row,opt,name);self.payloads[i]=payload
                check="Připraveno";tag=()
                if payload["connection_type"] == "HT":
                    validate_ht_width(payload["required_length"], payload["series"])
                else:
                    try:required_length_codes(payload["required_length"],self.owner.allowed_hit_lengths())
                    except ValueError as exc:
                        check=str(exc);tag=("warning",)
                        if i in self.included:warnings+=1
                if payload["connection_type"] == "HT":
                    m=v="—"
                    hpar=payload["hed_parallel"] or "—";hperp=payload["hed_perp"] or "—"
                else:
                    m=("−" if payload["med_neg"] else "+")+(payload["med_neg"] or payload["med_pos"] or "0")
                    v=("−" if payload["ved_neg"] else "+")+(payload["ved_neg"] or payload["ved_pos"] or "0")
                    hpar=hperp="—"
                typ=payload["connection_type"];cover=payload["cover"]
            except ValueError as exc:
                check=str(exc);tag=("error",)
                m="—" if row.med is None else text_number(row.med);v="—" if row.ved is None else text_number(row.ved)
                hpar="—" if row.h_parallel is None else text_number(row.h_parallel)
                hperp="—" if row.h_perp is None else text_number(row.h_perp)
                typ="HT" if row.kind=="HT" else (opt["bending"] if row.kind=="Ohybový" else opt["shear"]);cover=opt["cover"]
                if i in self.included:errors+=1
            self.tree.insert("","end",iid=str(i),tags=tag,values=("✓" if i in self.included else "—",name,row.kind,m,v,hpar,hperp,row.length_mm or "—",opt["height"],cover,opt["concrete"],opt["series"],typ,check))"""
    text = change(text, old_render, new_render)
    return text


def patch_core(text: str) -> str:
    text = change(
        text,
        'CONNECTION_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL", "AT", "FT", "OTX")',
        'CONNECTION_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL", "HT", "AT", "FT", "OTX")'
    )
    text = change(
        text,
        '        if typ in {"AT", "FT"}:\n            return f"HIT-{self.series} {self.code}-{hcode}-025"',
        '        if typ == "HT":\n            width = "010" if self.series.upper() == "HP" else "015"\n            return f"HIT-{self.series} {self.code}-{hcode}-{width}"\n        if typ in {"AT", "FT"}:\n            return f"HIT-{self.series} {self.code}-{hcode}-025"'
    )
    text = change(
        text,
        '    def physical_length_mm(self) -> int:\n        return {100: 1000, 50: 500, 33: 333, 25: 250}.get(self.length_code, self.length_code)',
        '    def physical_length_mm(self) -> int:\n        if self.connection_type.upper() == "HT":\n            return 100 if self.series.upper() == "HP" else 150\n        return {100: 1000, 50: 500, 33: 333, 25: 250}.get(self.length_code, self.length_code)'
    )
    return text


def patch_workspace(text: str) -> str:
    text = change(text, 'HIT_MODULE_VERSION = "1.1.16"', 'HIT_MODULE_VERSION = "1.1.17"')
    text = change(
        text,
        'from hit_schedule import HitScheduleDialog, required_length_codes',
        'from hit_schedule import HitScheduleDialog, required_length_codes\nfrom hit_ht import design_ht_candidates'
    )
    text = change(
        text,
        '    "OTX":  {"m_pos": False, "m_neg": False, "n_pos": True,  "n_neg": True,  "v_pos": True, "v_neg": False},',
        '    "OTX":  {"m_pos": False, "m_neg": False, "n_pos": True,  "n_neg": True,  "v_pos": True, "v_neg": False},\n'
        '    "HT":   {"m_pos": False, "m_neg": False, "n_pos": False, "n_neg": False, "v_pos": False, "v_neg": False, "h_parallel": True, "h_perp": True},'
    )
    text = change(
        text,
        '    "v_neg": ("VEd−", "kN/m"),\n}',
        '    "v_neg": ("VEd−", "kN/m"),\n    "h_parallel": ("HEd∥", "kN/prvek"),\n    "h_perp": ("HEd⊥", "kN/prvek"),\n}'
    )
    text = change(
        text,
        '        self.ned_neg = tk.StringVar(value=str(defaults.get("ned_neg", "")))\n        self.load_x = tk.StringVar(value=str(defaults.get("load_x", "")))',
        '        self.ned_neg = tk.StringVar(value=str(defaults.get("ned_neg", "")))\n'
        '        self.hed_parallel = tk.StringVar(value=str(defaults.get("hed_parallel", "")))\n'
        '        self.hed_perp = tk.StringVar(value=str(defaults.get("hed_perp", "")))\n'
        '        self.load_x = tk.StringVar(value=str(defaults.get("load_x", "")))'
    )
    text = change(text, '        self.detail = tk.StringVar(value="čeká na MEd / VEd")', '        self.detail = tk.StringVar(value="čeká na zatížení")')
    text = change(
        text,
        '        self.ved_neg_entry = entry(self.ved_neg, 9)\n        self.load_x_entry = entry(self.load_x, 8)',
        '        self.ved_neg_entry = entry(self.ved_neg, 9)\n'
        '        self.hed_parallel_entry = entry(self.hed_parallel, 9)\n'
        '        self.hed_perp_entry = entry(self.hed_perp, 9)\n'
        '        self.load_x_entry = entry(self.load_x, 8)'
    )
    text = change(
        text,
        '            "v_pos": self.ved_pos_entry,\n            "v_neg": self.ved_neg_entry,\n        }',
        '            "v_pos": self.ved_pos_entry,\n            "v_neg": self.ved_neg_entry,\n'
        '            "h_parallel": self.hed_parallel_entry,\n'
        '            "h_perp": self.hed_perp_entry,\n        }'
    )
    text = change(
        text,
        '        fixed_cover = HIT_FIXED_COVER_TYPES.get(typ)\n        if fixed_cover is not None:',
        '        if typ == "HT":\n            self.cover_combo.configure(state="disabled", style="HitLocked.TCombobox")\n            self._cover_forced = False\n            return\n        fixed_cover = HIT_FIXED_COVER_TYPES.get(typ)\n        if fixed_cover is not None:'
    )
    text = change(
        text,
        '            "v_pos": self.ved_pos.get().strip(),\n            "v_neg": self.ved_neg.get().strip(),\n        }',
        '            "v_pos": self.ved_pos.get().strip(),\n            "v_neg": self.ved_neg.get().strip(),\n'
        '            "h_parallel": self.hed_parallel.get().strip(),\n'
        '            "h_perp": self.hed_perp.get().strip(),\n        }'
    )
    text = change(
        text,
        '        for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg"):',
        '        for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg", "h_parallel", "h_perp"):'
    )
    text = change(
        text,
        '    def _mvx_candidates_for_row(self, database: HitDatabase, height: int, cover: int, actions: DirectionalActions, lengths: set[int], x_mm: float):',
        '    def _read_ht_values(self) -> tuple[int, float, float] | None:\n'
        '        effective = self.effective_action_texts()\n'
        '        if not (effective.get("h_parallel") or effective.get("h_perp")):\n'
        '            return None\n'
        '        height = int(float(self.height.get().replace(",", ".")))\n'
        '        def force(value: str) -> float:\n'
        '            return abs(float((value or "0").replace(",", ".")))\n'
        '        return height, force(effective.get("h_parallel", "")), force(effective.get("h_perp", ""))\n\n'
        '    def _mvx_candidates_for_row(self, database: HitDatabase, height: int, cover: int, actions: DirectionalActions, lengths: set[int], x_mm: float):'
    )
    start = '    def recalculate(self, preserve_product: str | None = None) -> None:\n'
    end = '    def open_variants(self) -> None:\n'
    new_recalc = """    def recalculate(self, preserve_product: str | None = None) -> None:
        self._after_id = None
        self._family_info = {}
        typ = self.connection_type.get().strip().upper()
        candidates: list[Candidate] = []
        error = ""
        family_info: dict[str, Any] = {}

        if typ == "HT":
            try:
                values = self._read_ht_values()
            except ValueError:
                self._set_error("neplatný číselný vstup HEd")
                return
            if values is None:
                self.candidates = []
                self.product_combo.configure(values=())
                self.variants_button.configure(text="Varianty…", state="disabled")
                self.product.set("—"); self.util.set("—"); self.page.set("—"); self.spacing.set("—")
                self.detail_label.configure(style="MutedCard.TLabel")
                self.detail.set("čeká na HEd∥ / HEd⊥ [kN/prvek]")
                self.owner.update_hit_status()
                return
            height, h_parallel, h_perp = values
            candidates, error, family_info = design_ht_candidates(
                self.series.get(), height, self.concrete.get(),
                h_parallel, h_perp, self.required_length.get(),
            )
        else:
            database = self.owner.hit_db
            if database is None:
                self._set_error("nejprve načtěte data HIT z DoP")
                return
            try:
                values = self._read_values()
            except ValueError:
                self._set_error("neplatný číselný vstup")
                return
            if values is None:
                self.candidates = []
                self.product_combo.configure(values=())
                self.variants_button.configure(text="Varianty…", state="disabled")
                self.product.set("—"); self.util.set("—"); self.page.set("—"); self.spacing.set("—")
                self.detail_label.configure(style="MutedCard.TLabel")
                self.detail.set("čeká na MEd / VEd")
                self.owner.update_hit_status()
                return
            height, cover, actions, x_mm = values
            try:
                lengths = required_length_codes(self.required_length.get(), self.owner.allowed_hit_lengths())
            except ValueError as exc:
                self._set_error(str(exc))
                return
            if typ == "MVX":
                candidates, error, family_info = self._mvx_candidates_for_row(database, height, cover, actions, lengths, x_mm)
            else:
                candidates, error, family_info = database.proposal_candidates(
                    self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), actions, lengths,
                    False, load_distance_x=x_mm,
                )
            required_mm = self.required_length.get().strip()
            if required_mm:
                candidates = [candidate for candidate in candidates if candidate.physical_length_mm == int(required_mm)]

        self._family_info = family_info
        self.candidates = candidates
        if error:
            self._set_error(error)
            return
        if not candidates:
            self._set_error(f"bez vyhovující varianty {self.connection_type.get()} pro zadané zatížení")
            return
        names = [candidate.designation for candidate in candidates]
        self.product_combo.configure(values=names)
        alt_type = str(self._family_info.get("alternative_type", ""))
        alt_count = int(self._family_info.get("alternative_count", 0) or 0)
        economy_attention = (
            self.connection_type.get().strip().upper() == "MVXL"
            and alt_type == "MVX"
            and alt_count > 0
            and bool(self._family_info.get("primary_available"))
        )
        button_text = "⚠ Varianty… +MVX" if economy_attention else (f"Varianty… +{alt_type}" if alt_count and alt_type else "Varianty…")
        self.variants_button.configure(text=button_text, width=16 if economy_attention else 14, state="normal" if len(candidates) > 1 else "disabled")
        chosen = candidates[0]
        if preserve_product and preserve_product in names:
            chosen = candidates[names.index(preserve_product)]
        self.product.set(chosen.designation)
        self._manual_product = chosen is not candidates[0]
        self._show_candidate(chosen)
        self.owner.update_hit_status()

"""
    i = text.find(start)
    j = text.find(end, i)
    if i < 0 or j < 0:
        raise RuntimeError("recalculate patch anchors missing")
    text = text[:i] + new_recalc + text[j:]
    text = change(
        text,
        '        if candidate.connection_type in {"AT", "FT", "OTX"}:',
        '        if candidate.connection_type == "HT":\n'
        '            text += f" • HRd∥ {fmt(candidate.m1)} kN/prvek • HRd⊥ {fmt(candidate.v1)} kN/prvek"\n'
        '        elif candidate.connection_type in {"AT", "FT", "OTX"}:'
    )
    text = change(
        text,
        '        if self.required_length.get().strip():\n            text += " • požadované L " + self.required_length.get().strip() + " mm"',
        '        if self.required_length.get().strip():\n            text += (" • požadované B " if candidate.connection_type == "HT" else " • požadované L ") + self.required_length.get().strip() + " mm"'
    )
    text = change(
        text,
        'return {"required_length": self.required_length.get(), "series": self.series.get(), "connection_type": self.connection_type.get(), "mvx_variant": self.mvx_variant.get(), "mvx_bx": self.mvx_bx.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med_pos": "", "med_neg": "", "ned_pos": "", "ned_neg": "", "ved_pos": "", "ved_neg": "", "load_x": ""}',
        'return {"required_length": self.required_length.get(), "series": self.series.get(), "connection_type": self.connection_type.get(), "mvx_variant": self.mvx_variant.get(), "mvx_bx": self.mvx_bx.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med_pos": "", "med_neg": "", "ned_pos": "", "ned_neg": "", "ved_pos": "", "ved_neg": "", "hed_parallel": "", "hed_perp": "", "load_x": ""}'
    )
    text = change(
        text,
        '            "ved_pos": effective["v_pos"], "ved_neg": effective["v_neg"],',
        '            "ved_pos": effective["v_pos"], "ved_neg": effective["v_neg"],\n'
        '            "hed_parallel": effective.get("h_parallel", ""), "hed_perp": effective.get("h_perp", ""),'
    )
    text = change(
        text,
        'ttk.Label(import_bar, text="MEd / VEd z textu či Excelu → společné parametry → kontrola → návrh. L požadované [mm] je závazné; prázdné pole použije horní volbu délek.", style="Muted.TLabel").pack(side="left", padx=(10, 0))',
        'ttk.Label(import_bar, text="MEd/VEd [na metr] nebo HEd∥/HEd⊥ [kN/prvek] → společné parametry → kontrola → návrh. Pro HT platí B: HP 100 mm / SP 150 mm.", style="Muted.TLabel").pack(side="left", padx=(10, 0))'
    )
    text = change(
        text,
        '("Označení", "Řada", "Typ", "MVX prov.", "bx [mm]", "h [mm]", "L požad. [mm]", "cnom", "Beton", "MEd+", "MEd−", "NEd+", "NEd−", "VEd+", "VEd−", "x [mm]", "Navržený výrobek ▼", "Varianty", "Využití", "a max", "Zdroj", "Stav / kontrola", "")',
        '("Označení", "Řada", "Typ", "MVX prov.", "bx [mm]", "h [mm]", "L/B požad. [mm]", "cnom", "Beton", "MEd+", "MEd−", "NEd+", "NEd−", "VEd+", "VEd−", "HEd∥", "HEd⊥", "x [mm]", "Navržený výrobek ▼", "Varianty", "Využití", "a max", "Zdroj", "Stav / kontrola", "")'
    )
    text = change(text, 'column in (0, 16, 21)', 'column in (0, 18, 23)', 2)
    old_help_start = '        ttk.Label(parent, text=("Vstupy zatížení se automaticky zamykají podle zvoleného typu:'
    hi = text.find(old_help_start)
    if hi < 0:
        raise RuntimeError("help label anchor missing")
    hj = text.find(').grid(row=3, column=0, sticky="ew", pady=(8, 0))', hi)
    if hj < 0:
        raise RuntimeError("help label end missing")
    hj += len(').grid(row=3, column=0, sticky="ew", pady=(8, 0))')
    new_help = '''        ttk.Label(parent, text=("Vstupy se zamykají podle typu. HIT-HT používá pouze HEd∥/HEd⊥ v kN/prvek; MEd/NEd/VEd jsou u HT uzamčené. "
                "HP HT má B=100 mm, SP HT B=150 mm a h=160–350 mm. HT1 přenáší H∥, HT2 H⊥, HT3 oba směry. HT4/HT5 se bez samostatné kontroly vazby na MVX automaticky nevybírají. "
                "MEd/VEd ostatních typů zůstávají na metr a nikdy se nepřevádějí na HEd. ZVX/ZDX mají pevné cnom=30 mm. Ostatní pravidla MVX/MVXL/DD/DVL/DDL/AT/FT/OTX zůstávají beze změny."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'''
    text = text[:hi] + new_help + text[hj:]
    old_copy_header = 'lines = ["Označení\\tŘada\\tTyp\\tMVX prov.\\tbx [mm]\\th [mm]\\tcnom [mm]\\tBeton\\tMEd+ [kNm/m]\\tMEd− [kNm/m]\\tNEd+ [kN/m]\\tNEd− [kN/m]\\tVEd+ [kN/m]\\tVEd− [kN/m]\\tx [mm]\\tNavržený výrobek\\tVyužití\\ta max [m]\\tZdroj\\tNRd\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2\\tL požadované [mm]\\tVýkaz – původní text"]'
    new_copy_header = 'lines = ["Označení\\tŘada\\tTyp\\tMVX prov.\\tbx [mm]\\th [mm]\\tcnom [mm]\\tBeton\\tMEd+ [kNm/m]\\tMEd− [kNm/m]\\tNEd+ [kN/m]\\tNEd− [kN/m]\\tVEd+ [kN/m]\\tVEd− [kN/m]\\tHEd∥ [kN/prvek]\\tHEd⊥ [kN/prvek]\\tx [mm]\\tNavržený výrobek\\tVyužití\\ta max [m]\\tZdroj\\tNRd\\tMRd/HRd∥,1\\tVRd/HRd⊥,1\\tMRd,2\\tVRd,2\\tL/B požadované [mm]\\tVýkaz – původní text"]'
    text = change(text, old_copy_header, new_copy_header)
    old_copy_row = 'effective["m_pos"], effective["m_neg"], effective["n_pos"], effective["n_neg"], effective["v_pos"], effective["v_neg"], (fmt(candidate.load_distance_x,0) if candidate.load_distance_x else ""), candidate.designation'
    new_copy_row = 'effective["m_pos"], effective["m_neg"], effective["n_pos"], effective["n_neg"], effective["v_pos"], effective["v_neg"], effective.get("h_parallel", ""), effective.get("h_perp", ""), (fmt(candidate.load_distance_x,0) if candidate.load_distance_x else ""), candidate.designation'
    text = change(text, old_copy_row, new_copy_row)
    return text


def build():
    manifest = ROOT / "update_manifest.json"
    old = json.loads(manifest.read_text(encoding="utf-8"))
    if old["version"] not in {"1.1.16", VERSION}:
        raise RuntimeError("Another release is current; refusing to overwrite it")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    (OUT / "hit_ht.py").write_text((ROOT / "tools/v1117_hit_ht.py").read_text(encoding="utf-8"), encoding="utf-8")
    path = OUT / "hit_schedule.py"
    path.write_text(patch_schedule(path.read_text(encoding="utf-8")), encoding="utf-8")
    path = OUT / "hit_core.py"
    path.write_text(patch_core(path.read_text(encoding="utf-8")), encoding="utf-8")
    path = OUT / "hit_workspace.py"
    path.write_text(patch_workspace(path.read_text(encoding="utf-8")), encoding="utf-8")
    app = OUT / "app.pyw"
    app.write_text(change(app.read_text(encoding="utf-8"), 'APP_VERSION = "1.1.16"', 'APP_VERSION = "1.1.17"'), encoding="utf-8")
    (OUT / "version.txt").write_text(VERSION + "\n", encoding="utf-8")
    (OUT / "RELEASE_NOTES.txt").write_text(NOTES, encoding="utf-8")

    for path in OUT.rglob("*"):
        if path.suffix in {".py", ".pyw"}:
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")

    changed = {"hit_ht.py", "hit_schedule.py", "hit_core.py", "hit_workspace.py", "app.pyw", "version.txt", "RELEASE_NOTES.txt"}
    same = 0
    for path in BASE.rglob("*"):
        rel = path.relative_to(BASE).as_posix()
        if path.is_file() and path.suffix != ".pyc" and "__pycache__" not in path.parts and rel not in changed:
            assert path.read_bytes() == (OUT / rel).read_bytes(), rel
            same += 1

    result = load_test("verify_hit_ht", ROOT / "tools/verify_v1117.py").verify(OUT, ROOT / "_diag_v1117")
    result["prior_release_regression"] = load_test("verify_prior_release", ROOT / "tools/verify_v1115.py").verify(
        OUT, ROOT / "_diag_v1117/previous_release"
    )
    result.update(
        version=VERSION,
        ht_catalog_source="HIT 20.2-EN 2023 pages 121-123",
        ht4_ht5_auto_selected=False,
        unchanged_support_files=same,
        new_runtime_dependencies=[],
    )
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    (OUT / "HIT_HT_VERIFICATION.json").write_text(data, encoding="utf-8")
    (ROOT / "_diag_v1117").mkdir(parents=True, exist_ok=True)
    (ROOT / "_diag_v1117/verification.json").write_text(data, encoding="utf-8")

    paths = {entry["path"] for entry in old["files"]} | {"hit_ht.py", "HIT_HT_VERIFICATION.json"}
    files = []
    for rel in sorted(paths):
        path = OUT / rel
        if not path.is_file():
            raise RuntimeError("Missing updater file: " + rel)
        files.append(dict(
            path=rel,
            url=f"https://raw.githubusercontent.com/{REPO}/main/updates/{VERSION}/{rel}",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        ))
    old.update(
        version=VERSION,
        files=files,
        notes="Návrh HIT: bezpečné rozlišení VEd a HEd, nový HIT-HT1/HT2/HT3 návrh, HP B=100 mm / SP B=150 mm a přísné jednotky kN/prvek.",
    )
    manifest.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS", VERSION, len(files), "updater files;", same, "support files unchanged")

if __name__ == "__main__":
    build()
