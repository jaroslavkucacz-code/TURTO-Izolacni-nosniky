from __future__ import annotations

"""Regression checks for TURTO 2.2.28 Peikko EBEA / TEBEA support."""

import importlib.util
import py_compile
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.28"
MODULE = RELEASE / "peikko_thermal_breaks.py"
WORKSPACE = RELEASE / "peikko_workspace.py"
RUNTIME = RELEASE / "app_runtime.pyw"
INSTALLER = RELEASE / "runtime_installer.py"
BOOTSTRAP = RELEASE / "app.pyw"

EXPECTED_EBEA = {
    "100", "E-100", "200", "500", "600", "700", "800",
    "900", "E-900", "1000", "1100", "1200", "G",
}
EXPECTED_TEBEA = {
    "CM-V", "PM-V", "RM-V", "CM-VV", "PM-VV", "RM-VV", "RMC-V", "HM-W",
    "PV-S", "PVV-S", "V-S", "PV-W", "PVV-W", "V-W",
    "LM-V", "LM-VV", "EA", "EH", "ES", "N",
}


def load_module():
    spec = importlib.util.spec_from_file_location("peikko_thermal_breaks", MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Nelze načíst peikko_thermal_breaks.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["peikko_thermal_breaks"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    for path in (MODULE, WORKSPACE, RUNTIME, INSTALLER, BOOTSTRAP):
        if not path.is_file():
            raise AssertionError(f"Chybí {path.relative_to(ROOT)}")
        py_compile.compile(str(path), doraise=True)

    peikko = load_module()
    peikko.selftest()

    ebea = {spec.model for spec in peikko.MODEL_SPECS if spec.family == "EBEA"}
    tebea = {spec.model for spec in peikko.MODEL_SPECS if spec.family == "TEBEA"}
    assert ebea == EXPECTED_EBEA
    assert tebea == EXPECTED_TEBEA
    assert len(peikko.MODEL_SPECS) == 33
    assert all(spec.insulation_mm == (120,) for spec in peikko.MODEL_SPECS if spec.family == "TEBEA")

    # Representative decoding.
    assert peikko.decode_peikko("EBEA-100-VE1 200").model == "100"
    assert peikko.decode_peikko("EBEA E100").model == "E-100"
    assert peikko.decode_peikko("EBEA Type G").model == "G"
    assert peikko.decode_peikko("TEBEA CM-V 120").model == "CM-V"
    assert peikko.decode_peikko("TEBEA PVV-W").model == "PVV-W"
    assert peikko.decode_peikko("TEBEA N").role == peikko.ROLE_NONLOAD

    # Unsafe cross-family / cross-function substitutions must never pass.
    assert not peikko.functionally_compatible("EBEA-100", "TEBEA CM-V")
    assert not peikko.functionally_compatible("EBEA-500", "EBEA-100")
    assert not peikko.functionally_compatible("TEBEA EA", "TEBEA EH")
    assert not peikko.functionally_compatible("TEBEA N", "TEBEA CM-V")
    assert {s.model for s in peikko.compatible_models("TEBEA CM-V")} == {"PM-V", "RM-V"}
    assert {s.model for s in peikko.compatible_models("TEBEA CM-VV")} == {"PM-VV", "RM-VV"}

    assert peikko.DESIGN_STATUS == "Rozpoznáno – nutné statické ověření"

    installer = runpy.run_path(str(INSTALLER), run_name="turto_2228_installer_test")
    installer["selftest"]()
    assert installer["RUNTIME_LAYOUT"] == "21"
    assert set(installer["PAYLOADS"]) == {
        "app_runtime_227.pyw",
        "app_runtime.pyw",
        "peikko_thermal_breaks.py",
        "peikko_workspace.py",
    }

    bootstrap = runpy.run_path(str(BOOTSTRAP), run_name="turto_2228_bootstrap_test")
    bootstrap["selftest"]()
    assert bootstrap["VERSION"] == "2.2.28"
    assert bootstrap["RUNTIME_LAYOUT"] == "21"

    runtime_text = RUNTIME.read_text(encoding="utf-8")
    assert 'APP_VERSION = "2.2.28"' in runtime_text
    assert 'BASE_RUNTIME = PROGRAM / "app_runtime_227.pyw"' in runtime_text
    assert "peikko_workspace.install(_base)" in runtime_text

    workspace_text = WORKSPACE.read_text(encoding="utf-8")
    for token in ("Dekodér", "Záměny", "Návrh / předvýběr", "Peikko EBEA / TEBEA"):
        assert token in workspace_text
    assert "staticky vyhovující" in workspace_text

    print(
        "OK: TURTO 2.2.28 – EBEA/TEBEA modely, dekodér, bezpečné funkční záměny, "
        "předvýběr návrhu a runtime overlay jsou konzistentní."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
