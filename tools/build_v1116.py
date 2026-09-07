"""Build a verified, atomic updater payload on top of the deployed 1.1.15."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
VERSION="1.1.16"
BASE=ROOT/"updates/1.1.15"
OUT=ROOT/"updates"/VERSION
REPO="jaroslavkucacz-code/TURTO-Izolacni-nosniky"
sys.dont_write_bytecode=True

NOTES='''TURTO ISO v1.1.16 – hromadné zadání HIT z výkazu
- Návrh HIT → Vložit výkaz…: vložení textu nebo sloupce z Excelu, načtení MEd/VEd, ohybových a smykových pozic a délek v m/cm/mm.
- Kontrolní náhled, společná výška/krytí/beton/řada, výslovné přiřazení typů a směru nepodepsaného MEd. Parametry lze změnit také jen označeným pozicím.
- Chybný nebo nejednoznačný řádek se nikdy tiše nezahodí. Import vybraných pozic vyžaduje kontrolu typů a směrů. Lze vynechat označené řádky, připojit je nebo po potvrzení nahradit dosavadní zadání.
- Hodnoty kN/m a kNm/m se nepřepočítávají délkou. Jiné nebo chybějící jednotky se musí před importem vyřešit. Explicitní znaménka se zachovávají a nepodporované směry jsou blokovány.
- Nové pole L požad. [mm] v každém řádku: prázdné používá společné povolené délky, uvedená délka vyžaduje přesnou shodu. 0,1 m se nikdy nezamění za kód 100 = 1000 mm. Nepodporovaná délka se zobrazí jako nelze navrhnout, ne jako vyhovující náhrada.
- ZVX/ZDX si zachovávají katalogově pevné krytí 30 mm. Další úpravy po importu probíhají přímo ve stávajících řádcích Návrhu HIT.
- Původní text a požadovaná délka se přidávají na konec kopírovaných výsledků. Pořadí a opakované pozice zůstávají zachované.
- Ukázkový výkaz obsahuje 33 pozic (28 ohybových, 5 smykových).
- Výpočtové jádro, katalogová data a modul záměn/potvrzení/PDF zůstávají beze změny. Nová funkce nepřidává žádné runtime závislosti.
'''

def change(text,old,new,count=1):
    if text.count(old)!=count:
        raise RuntimeError(f"Expected {count} patch anchors, found {text.count(old)}: {old[:100]}")
    return text.replace(old,new)


def patch_workspace(text):
    text=change(text,'HIT_MODULE_VERSION = "1.0.3"','HIT_MODULE_VERSION = "1.1.16"')
    text=change(text,'from ui_utils import place_dialog_on_parent',
        'from ui_utils import place_dialog_on_parent\nfrom hit_schedule import HitScheduleDialog, required_length_codes')
    anchor='        self.height = tk.StringVar(value=str(defaults.get("height", "200")))'
    text=change(text,anchor,anchor+'\n        self.required_length = tk.StringVar(value=str(defaults.get("required_length", "")))\n        self.import_source_text = str(defaults.get("import_source_text", ""))\n        self.import_source_line = str(defaults.get("import_source_line", ""))')
    text=change(text,'        entry(self.height, 8)','        entry(self.height, 8)\n        self.required_length_entry = entry(self.required_length, 8)')
    text=change(text,'''        lengths = self.owner.allowed_hit_lengths()
        if not lengths:
            self._set_error("není povolena žádná délka")
            return''','''        try:
            lengths = required_length_codes(self.required_length.get(), self.owner.allowed_hit_lengths())
        except ValueError as exc:
            self._set_error(str(exc))
            return''')
    text=change(text,'''        self._family_info = family_info
        self.candidates = candidates''','''        self._family_info = family_info
        required_mm = self.required_length.get().strip()
        if required_mm:
            candidates = [candidate for candidate in candidates if candidate.physical_length_mm == int(required_mm)]
        self.candidates = candidates''')
    text=change(text,'        self.detail.set(text)\n\n    def _set_error',
        '        if self.required_length.get().strip():\n            text += " • požadované L " + self.required_length.get().strip() + " mm"\n        self.detail.set(text)\n\n    def _set_error')
    text=change(text,'        return {"series": self.series.get(), "connection_type":',
        '        return {"required_length": self.required_length.get(), "series": self.series.get(), "connection_type":')
    text=change(text,'            "name": self.name.get().strip(), "series": self.series.get(),',
        '            "import_source_text": self.import_source_text, "required_length_mm": self.required_length.get().strip(),\n            "name": self.name.get().strip(), "series": self.series.get(),')
    text=change(text,'        toolbar.columnconfigure(20, weight=1)', '''        toolbar.columnconfigure(20, weight=1)
        import_bar = ttk.Frame(toolbar, style="App.TFrame")
        import_bar.grid(row=1, column=0, columnspan=21, sticky="ew", pady=(8, 0))
        ttk.Button(import_bar, text="Vložit výkaz…", style="Accent.TButton", command=self.open_hit_schedule).pack(side="left")
        ttk.Label(import_bar, text="MEd / VEd z textu či Excelu → společné parametry → kontrola → návrh. L požadované [mm] je závazné; prázdné pole použije horní volbu délek.", style="Muted.TLabel").pack(side="left", padx=(10, 0))''')
    text=change(text,'"bx [mm]", "h [mm]", "cnom",','"bx [mm]", "h [mm]", "L požad. [mm]", "cnom",')
    text=change(text,'column in (0, 15, 20)','column in (0, 16, 21)',2)
    text=change(text,'    def add_hit_row(self) -> None:', '''    def open_hit_schedule(self) -> None:
        dialog = HitScheduleDialog(self)
        self.wait_window(dialog)

    def add_hit_row(self) -> None:''')
    text=change(text,r'MRd,2\tVRd,2"]',r'MRd,2\tVRd,2\tL požadované [mm]\tVýkaz – původní text"]')
    text=change(text,'fmt(candidate.m2), fmt(candidate.v2)]))',
        'fmt(candidate.m2), fmt(candidate.v2), row.required_length.get(), row.import_source_text.replace("\\t", " ").replace("\\n", " ")]))')
    return text


def load_test(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod


def build():
    manifest=ROOT/"update_manifest.json"
    old=json.loads(manifest.read_text(encoding="utf-8"))
    if old["version"] not in {"1.1.15",VERSION}:raise RuntimeError("Another release is current; refusing to overwrite it")
    if OUT.exists():shutil.rmtree(OUT)
    shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    path=OUT/"hit_workspace.py"
    path.write_text(patch_workspace(path.read_text(encoding="utf-8")),encoding="utf-8")
    shutil.copyfile(ROOT/"tools/v1116_hit_schedule.py",OUT/"hit_schedule.py")
    app=OUT/"app.pyw"
    app.write_text(change(app.read_text(encoding="utf-8"),'APP_VERSION = "1.1.15"','APP_VERSION = "1.1.16"'),encoding="utf-8")
    (OUT/"version.txt").write_text(VERSION+"\n",encoding="utf-8")
    (OUT/"RELEASE_NOTES.txt").write_text(NOTES,encoding="utf-8")
    for path in OUT.rglob("*"):
        if path.suffix in {".py",".pyw"}:compile(path.read_text(encoding="utf-8-sig"),str(path),"exec")
    changed={"hit_workspace.py","app.pyw","version.txt","RELEASE_NOTES.txt"}
    same=0
    for path in BASE.rglob("*"):
        rel=path.relative_to(BASE).as_posix()
        if path.is_file() and path.suffix!=".pyc" and "__pycache__" not in path.parts and rel not in changed:
            assert path.read_bytes()==(OUT/rel).read_bytes(),rel
            same+=1
    result=load_test("verify_hit_import",ROOT/"tools/verify_v1116.py").verify(OUT,ROOT/"_diag_v1116")
    result["prior_release_regression"]=load_test("verify_prior_release",ROOT/"tools/verify_v1115.py").verify(OUT,ROOT/"_diag_v1116/previous_release")
    result.update(version=VERSION,structural_core_unchanged=True,unchanged_support_files=same,new_runtime_dependencies=[])
    data=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    (OUT/"HIT_IMPORT_VERIFICATION.json").write_text(data,encoding="utf-8")
    (ROOT/"_diag_v1116/verification.json").write_text(data,encoding="utf-8")
    paths={entry["path"] for entry in old["files"]}|{"hit_schedule.py","HIT_IMPORT_VERIFICATION.json"}
    files=[]
    for rel in sorted(paths):
        path=OUT/rel
        if not path.is_file():raise RuntimeError("Missing updater file: "+rel)
        files.append(dict(path=rel,url=f"https://raw.githubusercontent.com/{REPO}/main/updates/{VERSION}/{rel}",sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    old.update(version=VERSION,files=files,notes="Návrh HIT: vložení výkazu MEd/VEd, společné i individuální parametry, kontrola znamének/jednotek a přesné délky. Výpočtové jádro beze změny.")
    # The updater manifest is changed only after every verification has passed.
    manifest.write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS",VERSION,len(files),"updater files;",same,"support files unchanged")

if __name__=="__main__":build()
