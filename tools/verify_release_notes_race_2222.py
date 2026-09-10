from __future__ import annotations

"""Regression checks for TURTO 2.2.22 release-note ownership and repair."""

import ast
import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.22"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for name in ("app.pyw", "app_runtime.pyw", "runtime_installer.py", "RELEASE_NOTES.txt", "release_contract.json"):
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    app = RELEASE / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    assert 'VERSION = "2.2.22"' in app_text
    assert 'RUNTIME_LAYOUT = "15"' in app_text
    assert "_disk_bootstrap_version() != VERSION" in app_text
    assert "_repair_misfiled_release_notes()" in app_text
    assert "_notes_version(source) != VERSION" in app_text

    runtime = RELEASE / "app_runtime.pyw"
    runtime_text = runtime.read_text(encoding="utf-8")
    assert 'APP_VERSION = "2.2.22"' in runtime_text
    assert 'BASE_RUNTIME = Path(__file__).with_name("app_runtime_221.pyw")' in runtime_text

    installer = RELEASE / "runtime_installer.py"
    ns = runpy.run_path(str(installer), run_name="verify_installer_2222")
    assert ns["RUNTIME_LAYOUT"] == "15"
    assert ns["BASE_PATH"] == "updates/2.2.21/runtime_installer.py"
    assert sha256(ROOT / ns["BASE_PATH"]) == ns["BASE_SHA256"]
    assert ns["PREVIOUS_REVISION"] == ".turto_runtime_2_2_21.ok"
    assert ns["PROGRAM_REVISION"] == ".turto_runtime_2_2_22.ok"
    assert set(ns["PAYLOADS"]) == {"app_runtime_221.pyw", "app_runtime.pyw"}
    for _local, (_commit, source, expected) in ns["PAYLOADS"].items():
        assert sha256(ROOT / source) == expected, source

    # A complete 2.2.21 installation must use only the small overlay and keep
    # the user's action database byte-identical.
    payload_bytes = {
        source: (ROOT / source).read_bytes()
        for _local, (_commit, source, _expected) in ns["PAYLOADS"].items()
    }
    with tempfile.TemporaryDirectory(prefix="turto_2222_installer_") as temp_name:
        root = Path(temp_name)
        program = root / "Program"
        program.mkdir()
        database = root / "actions.sqlite3"
        database.write_bytes(b"actions-db-must-not-change-2222")
        before = database.read_bytes()
        for name in ns["PREVIOUS_REQUIRED"]:
            target = program / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("VALUE = 2221\n", encoding="utf-8")
        (program / ".turto_runtime_2_2_21.ok").write_text("2.2.21", encoding="utf-8")

        calls: list[str] = []

        def fake_download(_commit: str, source: str, _expected: str, _agent: str) -> bytes:
            calls.append(source)
            if source == ns["BASE_PATH"]:
                raise AssertionError("Kompletní 2.2.21 Program nesmí spustit plnou obnovu.")
            return payload_bytes[source]

        install = ns["install_runtime"]
        install.__globals__["_download"] = fake_download
        install(root)
        assert database.read_bytes() == before
        assert ns["BASE_PATH"] not in calls
        assert set(calls) == {value[1] for value in ns["PAYLOADS"].values()}
        assert (program / ".turto_runtime_2_2_22.ok").read_text(encoding="utf-8") == "2.2.22"
        assert not (program / ".turto_runtime_2_2_21.ok").exists()
        assert (program / "app_runtime.pyw").read_bytes() == runtime.read_bytes()
        assert (program / "app_runtime_221.pyw").read_bytes() == (ROOT / "updates" / "2.2.21" / "app_runtime.pyw").read_bytes()

    app_ns = runpy.run_path(str(app), run_name="verify_app_2222")

    def patch_app_globals(root: Path) -> dict:
        globals_dict = app_ns["_post_run_cleanup"].__globals__
        globals_dict["ROOT"] = root
        globals_dict["PROGRAM"] = root / "Program"
        globals_dict["MARKER"] = root / ".turto_runtime_current.ok"
        globals_dict["PROGRAM_REVISION"] = root / "Program" / ".turto_runtime_2_2_22.ok"
        globals_dict["CLEANUP_REVISION"] = root / ".turto_cleanup_2_2_22.ok"
        globals_dict["LOG_DIR"] = root / "Logy"
        globals_dict["CLEANUP_LOG"] = root / "Logy" / "cleanup.log"
        return globals_dict

    # Reproduce the user's observed 2.2.20 -> 2.2.21 misfiling: file name says
    # 2.2.20, but the first line proves the contents are 2.2.21 release notes.
    with tempfile.TemporaryDirectory(prefix="turto_2222_repair_") as temp_name:
        root = Path(temp_name)
        patch_app_globals(root)
        folder = root / "Dokumentace" / "Interni" / "Vydani"
        folder.mkdir(parents=True)
        wrong = folder / "TURTO_2.2.20_20260910_140705.txt"
        expected = b"TURTO 2.2.21\n\nSmykove trny\n"
        wrong.write_bytes(expected)
        database = root / "actions.sqlite3"
        database.write_bytes(b"repair-does-not-touch-db")
        before = database.read_bytes()
        app_ns["_repair_misfiled_release_notes"]()
        assert not wrong.exists()
        assert (folder / "TURTO_2.2.21.txt").read_bytes() == expected
        assert database.read_bytes() == before

    # Stale-process guard: once disk app.pyw belongs to a newer version, this
    # old process may not consume that newer version's RELEASE_NOTES.txt.
    with tempfile.TemporaryDirectory(prefix="turto_2222_stale_") as temp_name:
        root = Path(temp_name)
        patch_app_globals(root)
        (root / "app.pyw").write_text('VERSION = "2.2.23"\n', encoding="utf-8")
        notes = root / "RELEASE_NOTES.txt"
        notes.write_text("TURTO 2.2.23\n\nFuture release\n", encoding="utf-8")
        database = root / "actions.sqlite3"
        database.write_bytes(b"stale-process-db")
        before = database.read_bytes()
        app_ns["_post_run_cleanup"]()
        assert notes.is_file()
        assert notes.read_text(encoding="utf-8").startswith("TURTO 2.2.23")
        assert not (root / ".turto_cleanup_2_2_22.ok").exists()
        assert database.read_bytes() == before

    # Current release notes still archive normally when ownership matches.
    with tempfile.TemporaryDirectory(prefix="turto_2222_current_") as temp_name:
        root = Path(temp_name)
        patch_app_globals(root)
        (root / "app.pyw").write_text('VERSION = "2.2.22"\n', encoding="utf-8")
        notes = root / "RELEASE_NOTES.txt"
        expected = b"TURTO 2.2.22\n\nCurrent release\n"
        notes.write_bytes(expected)
        database = root / "actions.sqlite3"
        database.write_bytes(b"current-notes-db")
        before = database.read_bytes()
        app_ns["_post_run_cleanup"]()
        target = root / "Dokumentace" / "Interni" / "Vydani" / "TURTO_2.2.22.txt"
        assert not notes.exists()
        assert target.read_bytes() == expected
        assert (root / ".turto_cleanup_2_2_22.ok").read_text(encoding="utf-8") == "2.2.22"
        assert database.read_bytes() == before

    contract = json.loads((RELEASE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["version"] == "2.2.22"
    assert str(contract["runtime_layout"]) == "15"
    assert contract["release_notes_race_guard"] is True
    assert contract["release_notes_repair"] is True
    assert "actions.sqlite3" in contract["preserve"]

    print("OK: TURTO 2.2.22 – release-note race guarded, misfiled notes repaired, actions.sqlite3 unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
