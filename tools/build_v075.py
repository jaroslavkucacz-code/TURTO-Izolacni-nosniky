from __future__ import annotations

import hashlib
import json
import math
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.7.4"
OUT = ROOT / "updates" / "0.7.5"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_app(text: str) -> str:
    return replace_once(text, 'APP_VERSION = "0.7.4"', 'APP_VERSION = "0.7.5"', "app version")


def patch_hit_workspace(text: str) -> str:
    return replace_once(text, 'HIT_MODULE_VERSION = "0.3.1"', 'HIT_MODULE_VERSION = "0.3.2"', "HIT module version")


def patch_hit_core(text: str) -> str:
    text = replace_once(text, 'APP_VERSION = "0.3.0"', 'APP_VERSION = "0.3.2"', "standalone HIT core version")

    old = '''def utilization(M: float, V: float, M1: float, V1: float, M2: float, V2: float):\n    if M < 1e-12 and V < 1e-12:\n        return 0.0, "nulové zatížení"\n\n    lambdas = []\n    if V > 1e-12:\n        lam = V1 / V\n        if lam * M <= M1 + 1e-9:\n            lambdas.append((lam, "V1"))\n\n    if M > 1e-12:\n        lam = M2 / M\n        if lam * V <= V2 + 1e-9:\n            lambdas.append((lam, "M2"))\n\n    dx = M2 - M1\n    dy = V2 - V1\n    den = M * dy - V * dx\n    if abs(den) > 1e-12:\n        lam = (M1 * dy - V1 * dx) / den\n        if lam >= 0:\n            if abs(dx) >= abs(dy):\n                t = (lam * M - M1) / dx if abs(dx) > 1e-12 else 0\n            else:\n                t = (lam * V - V1) / dy if abs(dy) > 1e-12 else 0\n            if -1e-9 <= t <= 1 + 1e-9:\n                lambdas.append((lam, "interpolace M–V"))\n\n    valid = [x for x in lambdas if x[0] >= 0]\n    if not valid:\n        return math.inf, "mimo obálku"\n\n    lam = max(valid, key=lambda x: x[0])\n    if lam[0] <= 1e-12:\n        return math.inf, lam[1]\n\n    return 1.0 / lam[0], lam[1]\n'''

    new = '''def _effective_balance_points(\n    M1: float, V1: float, M2: float, V2: float, *, tol: float = 1e-9\n) -> tuple[float, float, float, float, str]:\n    """Vrátí bilanční body v pořadí grafu DoP: M2 >= M1 a V1 >= V2.\n\n    DoP str. 3 definuje zjednodušenou únosnost vodorovnou hranou V1,\n    přímkou mezi (M1,V1) a (M2,V2) a svislou hranou M2.\n\n    Ve zdroji je právě jeden známý zaokrouhlovací nesoulad (SP MVX-0508,\n    h-cnom 270, C25/30): |MRd,1|=58,9 a |MRd,2|=58,8 při stejném\n    VRd=104,2. Aby kontrola nikdy nebyla nekonzervativní, sjednotíme v tomto\n    čistě vodorovném a <=0,11 kNm/m odlišném případě oba momenty na MENŠÍ\n    uvedenou hodnotu. Větší nebo jinak obrácené body se odmítnou.\n    """\n    m1 = abs(float(M1))\n    v1 = abs(float(V1))\n    m2 = abs(float(M2))\n    v2 = abs(float(V2))\n    note = ""\n\n    if m2 + tol < m1:\n        if abs(v2 - v1) <= 1e-6 and (m1 - m2) <= 0.11 + tol:\n            conservative_m = min(m1, m2)\n            m1 = conservative_m\n            m2 = conservative_m\n            note = "konzervativní normalizace zaokrouhlení DoP"\n        else:\n            raise ValueError(\n                f"Neplatné pořadí bilančních bodů: M2={m2:g} < M1={m1:g}."\n            )\n\n    if v2 > v1 + tol:\n        raise ValueError(\n            f"Neplatné pořadí bilančních bodů: V2={v2:g} > V1={v1:g}."\n        )\n\n    return m1, v1, m2, v2, note\n\n\ndef utilization(M: float, V: float, M1: float, V1: float, M2: float, V2: float):\n    """Využití z polygonální interakční obálky DoP, Annex 1, str. 3.\n\n    Pro absolutní hodnoty zatížení je bezpečná oblast průnikem:\n      V <= V1,\n      M <= M2,\n      (V1-V2)*M + (M2-M1)*V\n          <= (V1-V2)*M1 + (M2-M1)*V1.\n\n    Poslední nerovnost je přesná rovnice přímky mezi bilančními body\n    (M1,V1) a (M2,V2). Celkové eta je maximum využití těchto hranic.\n    Tím je výpočet přímo auditovatelný proti grafu a funguje i tehdy, když\n    se liší současně M1/M2 i V1/V2.\n    """\n    m = abs(float(M))\n    v = abs(float(V))\n    if m < 1e-12 and v < 1e-12:\n        return 0.0, "nulové zatížení"\n\n    try:\n        m1, v1, m2, v2, note = _effective_balance_points(M1, V1, M2, V2)\n    except ValueError as exc:\n        return math.inf, f"neplatné bilanční body • {exc}"\n\n    checks: list[tuple[float, str]] = []\n\n    if v1 > 1e-12:\n        checks.append((v / v1, "V1"))\n    elif v > 1e-12:\n        return math.inf, "V1 = 0"\n\n    if m2 > 1e-12:\n        checks.append((m / m2, "M2"))\n    elif m > 1e-12:\n        return math.inf, "M2 = 0"\n\n    dm = m2 - m1\n    dv = v1 - v2\n    if dm > 1e-12 or dv > 1e-12:\n        denominator = dv * m1 + dm * v1\n        if denominator > 1e-12:\n            eta_interaction = (dv * m + dm * v) / denominator\n            checks.append((eta_interaction, "interpolace M–V"))\n\n    if not checks:\n        return math.inf, "mimo obálku"\n\n    eta, mode = max(checks, key=lambda item: item[0])\n    if note:\n        mode += " • " + note\n    return eta, mode\n'''
    return replace_once(text, old, new, "explicit HIT interaction equation")


def legacy_utilization(M: float, V: float, M1: float, V1: float, M2: float, V2: float) -> float:
    """Původní geometrický výpočet pro regresní porovnání monotónních bodů."""
    if M < 1e-12 and V < 1e-12:
        return 0.0
    lambdas: list[float] = []
    if V > 1e-12:
        lam = V1 / V
        if lam * M <= M1 + 1e-9:
            lambdas.append(lam)
    if M > 1e-12:
        lam = M2 / M
        if lam * V <= V2 + 1e-9:
            lambdas.append(lam)
    dx = M2 - M1
    dy = V2 - V1
    den = M * dy - V * dx
    if abs(den) > 1e-12:
        lam = (M1 * dy - V1 * dx) / den
        if lam >= 0:
            if abs(dx) >= abs(dy):
                t = (lam * M - M1) / dx if abs(dx) > 1e-12 else 0.0
            else:
                t = (lam * V - V1) / dy if abs(dy) > 1e-12 else 0.0
            if -1e-9 <= t <= 1 + 1e-9:
                lambdas.append(lam)
    valid = [value for value in lambdas if value >= 0]
    if not valid:
        return math.inf
    lam = max(valid)
    return math.inf if lam <= 1e-12 else 1.0 / lam


def assert_close(actual: float, expected: float, tol: float = 1e-9) -> None:
    if not math.isclose(actual, expected, rel_tol=tol, abs_tol=tol):
        raise AssertionError(f"{actual!r} != {expected!r}")


def run_interaction_regressions(module) -> None:
    u = module.utilization

    # Skutečný typ tvaru z DoP: rozdílné M1/M2 i V1/V2.
    p = (20.0, 100.0, 40.0, 50.0)
    assert_close(u(20.0, 100.0, *p)[0], 1.0)       # bilanční bod 1
    assert_close(u(40.0, 50.0, *p)[0], 1.0)        # bilanční bod 2
    assert_close(u(30.0, 75.0, *p)[0], 1.0)        # střed šikmé hrany
    assert_close(u(15.0, 37.5, *p)[0], 0.5)        # polovina zatěžovacího paprsku
    assert_close(u(31.5, 78.75, *p)[0], 1.05)      # 5 % mimo obálku

    # Hraniční případy: pouze M rozdílné / pouze V rozdílné / oba body shodné.
    assert_close(u(30.0, 100.0, 20.0, 100.0, 40.0, 100.0)[0], 1.0)
    assert_close(u(20.0, 75.0, 20.0, 100.0, 20.0, 50.0)[0], 1.0)
    assert_close(u(10.0, 50.0, 20.0, 100.0, 20.0, 100.0)[0], 0.5)

    # Konkrétní extrém z tabulky DoP: M1=25, V1=32, M2=31, V2=0.
    assert_close(u(25.0, 32.0, 25.0, 32.0, 31.0, 0.0)[0], 1.0)
    assert_close(u(31.0, 0.0, 25.0, 32.0, 31.0, 0.0)[0], 1.0)
    assert_close(u(28.0, 16.0, 25.0, 32.0, 31.0, 0.0)[0], 1.0)
    if not u(28.0, 20.0, 25.0, 32.0, 31.0, 0.0)[0] > 1.0:
        raise AssertionError("Bod nad šikmou hranou musí nevyhovět.")

    # Známý jediný zaokrouhlovací nesoulad DoP, str. 41, C25/30, h-cnom=270.
    # Konzervativní efektivní moment je 58,8, ne 58,9 kNm/m.
    anomaly = u(58.8, 104.2, 58.9, 104.2, 58.8, 104.2)
    assert_close(anomaly[0], 1.0)
    if "konzervativní" not in anomaly[1]:
        raise AssertionError("Známý zdrojový rounding musí být v režimu explicitně označen.")
    if not u(58.85, 104.2, 58.9, 104.2, 58.8, 104.2)[0] > 1.0:
        raise AssertionError("Zaokrouhlovací anomálie nesmí vytvořit nekonzervativní klín.")

    # Větší nebo obrácená data se nesmí tiše opravovat.
    if not math.isinf(u(30.0, 60.0, 40.0, 100.0, 30.0, 70.0)[0]):
        raise AssertionError("Výrazně obrácené M body musí být odmítnuty.")
    if not math.isinf(u(30.0, 60.0, 20.0, 80.0, 40.0, 90.0)[0]):
        raise AssertionError("Obrácené V body musí být odmítnuty.")

    # Nová explicitní rovnice musí být pro běžné monotónní body numericky
    # ekvivalentní dosavadní geometrické metodě.
    point_sets = [
        (12.4, 32.0, 12.4, 32.0),
        (19.1, 32.0, 23.1, 13.1),
        (25.0, 32.0, 31.0, 0.0),
        (35.3, 111.5, 39.3, 103.9),
        (38.7, 144.0, 72.8, 68.7),
        (75.0, 107.3, 139.6, 40.1),
    ]
    fractions = (0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0, 1.05, 1.25)
    for m1, v1, m2, v2 in point_sets:
        for fm in fractions:
            for fv in fractions:
                m = max(m2, 1.0) * fm
                v = max(v1, 1.0) * fv
                old = legacy_utilization(m, v, m1, v1, m2, v2)
                new = u(m, v, m1, v1, m2, v2)[0]
                if math.isinf(old) and math.isinf(new):
                    continue
                assert_close(new, old, 2e-9)


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    app = OUT / "app.pyw"
    app.write_text(patch_app(app.read_text(encoding="utf-8")), encoding="utf-8")
    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_hit_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")
    core = OUT / "hit_core.py"
    core.write_text(patch_hit_core(core.read_text(encoding="utf-8")), encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    sys.path.insert(0, str(OUT))
    try:
        import hit_core  # type: ignore
        run_interaction_regressions(hit_core)
    finally:
        sys.path.pop(0)

    app_text = app.read_text(encoding="utf-8")
    hit_text = core.read_text(encoding="utf-8")
    workspace_text = workspace.read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.7.5"' in app_text
    assert 'APP_VERSION = "0.3.2"' in hit_text
    assert 'HIT_MODULE_VERSION = "0.3.2"' in workspace_text
    assert "eta_interaction" in hit_text
    assert "konzervativní normalizace zaokrouhlení DoP" in hit_text
    assert 'ratio_min_m", 0.15' in hit_text

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.7.5\n"
        "- HIT: interakce M/V je přepsána do explicitní rovnice obálky z DoP str. 3.\n"
        "- Správně se současně uplatní rozdílné MRd,1/VRd,1 a MRd,2/VRd,2; kontrolují se vodorovná, svislá i šikmá hrana.\n"
        "- Zachována podmínka |MEd|/|VEd| >= 0,150 m.\n"
        "- Známý zdrojový rounding na str. 41 (58,9/104,2 vs. 58,8/104,2) je ošetřen konzervativně hodnotou 58,8.\n"
        "- Výrazně nebo jinak obrácené bilanční body se nyní odmítnou jako neplatná data místo tichého výpočtu.\n"
        "- Regrese kontroluje bilanční body, šikmou hranu, body uvnitř/vně a numerickou shodu s dosavadní metodou pro standardní data.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.7.5/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.7.5",
        "notes": (
            "Statický audit HIT: interakce M1/V1–M2/V2 je nyní vyjádřena přímo rovnicí obálky z DoP; "
            "rozdílné bilanční body jsou kontrolovány přesně a jediný známý zaokrouhlovací nesoulad DoP je ošetřen konzervativně."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("v0.7.5 OK; HIT M/V interaction audited and explicit envelope regressions passed")


if __name__ == "__main__":
    main()
