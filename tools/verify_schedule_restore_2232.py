from __future__ import annotations

"""Regression checks for TURTO 2.2.32 schedule-import restoration."""

import hashlib
import json
import py_compile
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / "updates" / "2.2.32"

EXPECTED = {
    "schedule_restore.py": "9eda896646371cef4bda70ba6eea8c787c9c5c48046be5d5f6636a5f2bf20f01",
    "app_runtime.pyw": "56540f96213666734a527ddc208ac1ff6150cb78a114be05646ffdf8d6bcdb3f",
    "runtime_installer.py": "3c74eb26ea0b545ea2db760419bca9f4c795a43a7d40a727feed8aacfe9756af",
    "app.pyw": "db3181a5a41ebc43cbd415efeff474b4c70d63ce8accbbd765ddbfbd04f7f9a3",
    "RELEASE_NOTES.txt": "beca2b3f602d48ad8954a59f09af0d47c1241b4f90fd7180bd201d74f8bd0b52",
    "release_contract.json": "83bb5fa06e58186115355cbacb02912bdd3876f0764194a6f18a44946f5d62b2",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def main() -> None:
    for name, expected in EXPECTED.items():
        path = UPDATE / name
        assert path.is_file(), f"missing 2.2.32 payload: {name}"
        actual = sha(path)
        assert actual == expected, f"unexpected hash for {name}: {actual}"

    for name in ("schedule_restore.py", "app_runtime.pyw", "runtime_installer.py", "app.pyw"):
        py_compile.compile(str(UPDATE / name), doraise=True)

    restore = (UPDATE / "schedule_restore.py").read_text(encoding="utf-8")
    assert 'text="Vložit výkaz…"' in restore
    assert "from unified_schedule import open_unified_schedule" in restore
    assert "open_unified_schedule(self.owner)" in restore
    assert "self.show_legacy()" in restore
    assert "design_manufacturer_var.set(\"Leviat\")" in restore
    # This hotfix must reuse the verified parser, not introduce another parser.
    assert "import re" not in restore
    assert "def route_schedule" not in restore

    historical = (ROOT / "updates" / "2.0.0" / "unified_schedule.py").read_text(encoding="utf-8")
    assert "def route_schedule(" in historical
    assert "def open_unified_schedule(" in historical
    assert "Výkaz → návrh izolačních nosníků" in historical
    assert "Přidat do návrhu" in historical

    runtime = (UPDATE / "app_runtime.pyw").read_text(encoding="utf-8")
    assert 'APP_VERSION = "2.2.32"' in runtime
    assert 'BASE_RUNTIME = PROGRAM / "app_runtime_231.pyw"' in runtime
    assert "schedule_restore.install(_base)" in runtime

    installer_ns = runpy.run_path(str(UPDATE / "runtime_installer.py"), run_name="verify_installer_2232")
    installer_ns["selftest"]()
    assert installer_ns["BASE_PATH"] == "updates/2.2.31/runtime_installer.py"
    assert installer_ns["BASE_APP_RUNTIME_SHA256"] == "186a327b161b03cac8b612a097cf480e1e650df3b3b04c67bef8a0ddaa60c4e2"
    payloads = installer_ns["PAYLOADS"]
    assert set(payloads) == {"app_runtime.pyw", "schedule_restore.py"}
    for local, (_commit, _remote, expected) in payloads.items():
        assert sha(UPDATE / local) == expected.lower()

    app_ns = runpy.run_path(str(UPDATE / "app.pyw"), run_name="verify_app_2232")
    app_ns["selftest"]()
    assert app_ns["VERSION"] == "2.2.32"
    assert app_ns["INSTALLER_COMMIT"] == "4481100bdbb2dc0bd96d993c8c5042c25fe5d6fa"
    assert app_ns["INSTALLER_SHA256"] == sha(UPDATE / "runtime_installer.py")

    contract = json.loads((UPDATE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["version"] == "2.2.32"
    assert contract["base_version"] == "2.2.31"
    assert "actions.sqlite3" in contract["preserve"]
    assert contract["strategy"] == "schedule-import-regression-overlay"

    notes = (UPDATE / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    assert notes.startswith("TURTO 2.2.32")
    assert "Vložit výkaz…" in notes
    assert "unified_schedule.py" in notes

    print("TURTO 2.2.32 schedule-import regression checks: OK")


if __name__ == "__main__":
    main()
