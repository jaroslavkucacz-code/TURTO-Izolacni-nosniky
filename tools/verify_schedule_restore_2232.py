from __future__ import annotations

"""Regression checks for TURTO 2.2.32 schedule-import restoration."""

import hashlib
import json
import py_compile
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / "updates" / "2.2.32"
REQUIRED = (
    "schedule_restore.py",
    "app_runtime.pyw",
    "runtime_installer.py",
    "app.pyw",
    "RELEASE_NOTES.txt",
    "release_contract.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def main() -> None:
    for name in REQUIRED:
        assert (UPDATE / name).is_file(), f"missing 2.2.32 payload: {name}"

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
        actual = sha(UPDATE / local)
        assert actual == str(expected).lower(), f"payload hash mismatch: {local}: {actual}"

    app_ns = runpy.run_path(str(UPDATE / "app.pyw"), run_name="verify_app_2232")
    app_ns["selftest"]()
    assert app_ns["VERSION"] == "2.2.32"
    assert app_ns["INSTALLER_COMMIT"] == "4481100bdbb2dc0bd96d993c8c5042c25fe5d6fa"
    assert app_ns["INSTALLER_SHA256"] == sha(UPDATE / "runtime_installer.py")

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2.2.32"
    app_item = next(item for item in manifest["files"] if item["path"] == "app.pyw")
    notes_item = next(item for item in manifest["files"] if item["path"] == "RELEASE_NOTES.txt")
    assert app_item["sha256"].lower() == sha(UPDATE / "app.pyw")
    assert notes_item["sha256"].lower() == sha(UPDATE / "RELEASE_NOTES.txt")

    contract = json.loads((UPDATE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["version"] == "2.2.32"
    assert contract["base_version"] == "2.2.31"
    assert contract["manifest_root_only"] is True
    assert contract["runtime_directory"] == "Program"
    assert "actions.sqlite3" in contract["preserve"]
    assert contract["runtime_strategy"] == "schedule-import-regression-overlay"
    assert contract["schedule_import_restored"] is True
    assert contract["peikko_bulk_static_design_added"] is False

    notes = (UPDATE / "RELEASE_NOTES.txt").read_text(encoding="utf-8")
    assert notes.startswith("TURTO 2.2.32")
    assert "Vložit výkaz…" in notes
    assert "unified_schedule.py" in notes

    print("TURTO 2.2.32 schedule-import regression checks: OK")


if __name__ == "__main__":
    main()
