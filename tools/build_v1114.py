from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.1.13"
OUT = ROOT / "updates" / "1.1.14"
VERSION = "1.1.14"
REPO = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
EXPECTED_RENDERER = "2f186b0cfdd3e71ce0ccd0d4d060294185dde0d1cca77110c74ba3314142a615"
EXPECTED_TEST = "1502d36f54cdb081f862c9176f63dc278724f7a08a79cbd1765c42c8ca38b964"
EXPECTED_LOGO = "76d04bd62a127330fbc6d821caa2e5ffffb5aaeb592d404facbb2fedd302972f"

NOTES = """TURTO ISO v1.1.14
- Nová sazba vektorového PDF na A4 na výšku. Únosnosti, množství, rozměry a využití se vysazují písmem 11 pt bez zmenšování celé stránky. Běžný text má 11 pt, pomocné popisky 10,5 pt.
- Kompaktní souhrn obsahuje pozici, počet kusů, úplný původní prvek, úplný navržený HIT a rozhodující kontrolu se stavem. Duplicitní rozměrové údaje a tlakový přenos zůstávají v podrobné části.
- Počet řádků se počítá podle skutečné výšky textu; kontrolní vzorek 22 pozic se vejde na jednu stránku souhrnu.
- Detailní pozice se skládají podle skutečného obsahu, nejvýše čtyři na stránku. Kontrolní vzorek obsahuje stránky se třemi i čtyřmi pozicemi. Mimořádně dlouhé záznamy dostanou více místa, nikdy menší písmo.
- Originální firemní logo dodané uživatelem je v záhlaví překresleno vektorovými obrysy, včetně původního tvaru písmen TURTO.
- Všechny směrové kontroly M+/M−/N+/N−/V+/V− zůstávají ve výstupu. Potvrzená geometrie OU/OD zůstává viditelná u příslušné pozice.
- Delší poznámky a omezení jsou úplné v očíslované příloze s vazbou na pozice. Žádné označení ani poznámka se nekrátí výpustkou.
- Rozhodující údaj ve výstupu zohledňuje i uložené celkové využití a interakci M/V, ne pouze menší dílčí poměr.
- Stávající výpočtové jádro, katalogová data a pravidla návrhu/záměn zůstávají beze změny. Tato verze upravuje pouze výstup a označení verze aplikace.
- PDF se nejprve dokončí v dočasném souboru. Při selhání exportu zůstane dřívější soubor nedotčený.
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one version marker in {path.name}: {old}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    manifest_path = ROOT / "update_manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    if previous.get("version") not in {"1.1.13", VERSION}:
        raise RuntimeError("Newer/different release found; refusing to overwrite update manifest")
    renderer = (ROOT / "tools/v1114_substitution_pdf.py").read_bytes()
    tests = (ROOT / "tools/verify_v1114_pdf.py").read_bytes()
    encoded_logo = (ROOT / "tools/v1114_logo.json.gz.b64").read_text(encoding="ascii").strip()
    logo = gzip.decompress(base64.b64decode(encoded_logo, validate=True))
    for label, data, expected in (("renderer", renderer, EXPECTED_RENDERER), ("tests", tests, EXPECTED_TEST), ("logo", logo, EXPECTED_LOGO)):
        if sha(data) != expected:
            raise RuntimeError(f"Transport integrity check failed for {label}: {sha(data)}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (OUT / "substitution_pdf.py").write_bytes(renderer)
    (OUT / "assets").mkdir(exist_ok=True)
    (OUT / "assets/turto_logo_vector.json").write_bytes(logo)
    replace_once(OUT / "app.pyw", 'APP_VERSION = "1.1.13"', 'APP_VERSION = "1.1.14"')
    replace_once(OUT / "substitution_workspace.py", 'SUBSTITUTION_MODULE_VERSION = "1.1.13"', 'SUBSTITUTION_MODULE_VERSION = "1.1.14"')
    (OUT / "version.txt").write_text(VERSION + "\n", encoding="utf-8")
    (OUT / "RELEASE_NOTES.txt").write_text(NOTES, encoding="utf-8")
    for path in OUT.rglob("*"):
        if path.suffix in {".py", ".pyw"}:
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
    allowed = {"app.pyw", "substitution_workspace.py", "substitution_pdf.py", "version.txt", "RELEASE_NOTES.txt"}
    unchanged = 0
    for path in BASE.rglob("*"):
        if not path.is_file() or path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(BASE).as_posix()
        if rel not in allowed:
            assert path.read_bytes() == (OUT / rel).read_bytes(), f"Unintended change: {rel}"
            unchanged += 1
    sys.path.insert(0, str(OUT))
    import substitution_workspace
    import inspect
    assert "write_substitution_pdf" in inspect.getsource(substitution_workspace.export_substitution_pdf) if hasattr(substitution_workspace, "export_substitution_pdf") else hasattr(substitution_workspace.SubstitutionWorkspaceMixin, "export_substitution_pdf")
    spec = importlib.util.spec_from_file_location("verify_pdf", ROOT / "tools/verify_v1114_pdf.py")
    verify_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = verify_module
    spec.loader.exec_module(verify_module)
    result = verify_module.verify(OUT / "substitution_pdf.py", ROOT / "_diag_v1114")
    result.update(unchanged_catalog_and_support_files=unchanged,
                  structural_core_unchanged=True,
                  renderer_sha256=sha(renderer), logo_sha256=sha(logo),
                  runtime_dependency_added=False,
                  verification_environment="GitHub Actions; Python 3.12; Linux")
    verification = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    (OUT / "PDF_VERIFICATION.json").write_text(verification, encoding="utf-8")
    (ROOT / "_diag_v1114/verification.json").write_text(verification, encoding="utf-8")
    # Preserve all files delivered by the preceding updater, adding only report assets/diagnostics.
    paths = {str(item["path"]) for item in previous["files"]}
    paths.update({"assets/turto_logo_vector.json", "PDF_VERIFICATION.json", "version.txt", "RELEASE_NOTES.txt"})
    files = []
    for rel in sorted(paths):
        path = OUT / rel
        if not path.is_file():
            raise RuntimeError(f"Update payload is missing an existing file: {rel}")
        files.append(dict(path=rel, url=f"https://raw.githubusercontent.com/{REPO}/main/updates/{VERSION}/{rel}", sha256=sha(path.read_bytes())))
    new_manifest = dict(previous)
    new_manifest.update(version=VERSION, notes="TURTO ISO: čitelný vektorový PDF výstup A4 na výšku, hodnoty 11 pt, původní logo TURTO, kompaktní souhrn a 3–4 detailní pozice podle obsahu; úplné poznámky v příloze.", files=files)
    manifest_path.write_text(json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified release {VERSION}: {len(files)} update files; {unchanged} existing support/data files unchanged")


if __name__ == "__main__":
    main()
