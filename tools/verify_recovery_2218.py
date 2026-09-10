from __future__ import annotations

"""Regression checks for TURTO 2.2.18 recovery from the broken 2.2.17 update."""

import ast
import hashlib
import json
import re
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.18"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"{path}: chybí literální přiřazení {name}")


def version_tuple(value: str) -> tuple[int, ...]:
    parts = str(value).strip().split(".")
    try:
        return tuple(int(part) for part in parts)
    except ValueError as exc:
        raise RuntimeError(f"Neplatná verze: {value!r}") from exc


def main() -> int:
    required = (
        "app.pyw",
        "app_runtime.pyw",
        "runtime_installer.py",
        "RELEASE_NOTES.txt",
        "release_contract.json",
    )
    for name in required:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    app = RELEASE / "app.pyw"
    installer = RELEASE / "runtime_installer.py"
    runtime = RELEASE / "app_runtime.pyw"

    app_text = app.read_text(encoding="utf-8")
    installer_text = installer.read_text(encoding="utf-8")
    runtime_text = runtime.read_text(encoding="utf-8")

    # The historical 2.2.18 release itself stays pinned exactly. These checks
    # must never be relaxed when CURRENT_VERSION advances.
    for token in (
        'VERSION = "2.2.18"',
        'RUNTIME_LAYOUT = "11"',
        'PROGRAM_REVISION = PROGRAM / ".turto_runtime_2_2_18.ok"',
        "_activate_program_imports",
        "runpy.run_path(str(PROGRAM / \"app_runtime.pyw\"), run_name=\"__main__\")",
    ):
        assert token in app_text, token

    for token in (
        'RUNTIME_LAYOUT = "11"',
        'PREVIOUS_REVISION = ".turto_runtime_2_2_16.ok"',
        'PROGRAM_REVISION = ".turto_runtime_2_2_18.ok"',
        "_ensure_previous_runtime",
        "_apply_incremental_overlay",
        "actions.sqlite3 is never modified",
    ):
        assert token in installer_text, token

    assert 'APP_VERSION = "2.2.18"' in runtime_text
    assert "import hit_workspace" in runtime_text

    assert literal(app, "INSTALLER_COMMIT") == "635b61efb6a28103b1e2a05084ea53aaa3b2da36"
    assert literal(app, "INSTALLER_SHA256") == sha256(installer)

    assert literal(installer, "BASE_COMMIT") == "c17ab156e01d84f71ff70f1cdcb4c5f50ee49517"
    assert literal(installer, "BASE_PATH") == "updates/2.2.16/runtime_installer.py"
    assert sha256(ROOT / "updates" / "2.2.16" / "runtime_installer.py") == literal(installer, "BASE_SHA256")

    payloads = literal(installer, "PAYLOADS")
    assert set(payloads) == {"app_runtime.pyw", "hit_workspace.py"}
    assert payloads["app_runtime.pyw"][0] == "e6d26c38a6c23ea82b554ceb8e68b7ca79a6e603"
    assert payloads["app_runtime.pyw"][1] == "updates/2.2.18/app_runtime.pyw"
    assert payloads["hit_workspace.py"][0] == "abfdd5389ed8067a44876247583188c5c0c1069a"
    assert payloads["hit_workspace.py"][1] == "updates/2.2.17/hit_workspace.py"
    for local, (_commit, source, expected) in payloads.items():
        source_path = ROOT / source
        assert source_path.is_file(), source
        actual = sha256(source_path)
        if actual != expected:
            raise RuntimeError(f"PAYLOAD {local}: očekáváno {expected}, skutečně {actual}")

    contract = json.loads((RELEASE / "release_contract.json").read_text(encoding="utf-8"))
    assert contract["version"] == "2.2.18"
    assert str(contract["runtime_layout"]) == "11"
    assert contract["manifest_root_only"] is True
    assert contract["pinned_runtime_sources_verified"] is True
    assert "actions.sqlite3" in contract["preserve"]

    # CURRENT_VERSION and the root manifest may move forward. Require them to
    # retain the structural guarantees introduced by 2.2.18 instead of pinning
    # this historical regression test to one production version forever.
    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    current_version = (ROOT / "CURRENT_VERSION").read_text(encoding="utf-8").strip()
    assert version_tuple(current_version) >= (2, 2, 18)
    assert version_tuple(str(manifest["version"])) >= (2, 2, 18)
    assert manifest["version"] == current_version
    assert int(str(manifest["runtime_layout"])) >= 11
    assert {item["path"] for item in manifest["files"]} == {
        "app.pyw",
        "updater.py",
        "RELEASE_NOTES.txt",
    }
    assert all(item["path"] != "actions.sqlite3" for item in manifest["files"])

    # The root recovery tool is intentionally updated with the current release.
    # Keep checking that it is not older than 2.2.18 and still restores the
    # pinned root app/updater rather than mutating Program or the actions DB.
    recovery = (ROOT / "OPRAVIT_TURTO.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$Version = '([^']+)'", recovery)
    assert match is not None
    recovery_version = match.group(1)
    assert version_tuple(recovery_version) >= (2, 2, 18)
    assert recovery_version == current_version
    assert f"updates/{current_version}/app.pyw" in recovery
    assert "actions.sqlite3 ani složka Program nebyly měněny" in recovery

    # Exact historical recovery scenario: 2.2.17 failed while staging downloads,
    # so Program remains a valid 2.2.16 runtime. The 2.2.18 installer must use
    # only its two payloads and must not touch actions.sqlite3.
    ns = runpy.run_path(str(installer), run_name="verify_recovery_2218")
    install_runtime = ns["install_runtime"]
    payload_bytes = {
        source: (ROOT / source).read_bytes()
        for _local, (_commit, source, _expected) in payloads.items()
    }

    with tempfile.TemporaryDirectory(prefix="turto_2218_recovery_") as temp_name:
        root = Path(temp_name)
        program = root / "Program"
        program.mkdir()
        database = root / "actions.sqlite3"
        database.write_bytes(b"actions-database-must-remain-byte-identical")
        before = database.read_bytes()

        for name in ns["PREVIOUS_REQUIRED"]:
            path = program / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("VALUE = 2216\n", encoding="utf-8")
        (program / ".turto_runtime_2_2_16.ok").write_text("2.2.16", encoding="utf-8")

        calls: list[str] = []

        def fake_download(_commit: str, path: str, _expected: str, _agent: str) -> bytes:
            calls.append(path)
            if path == ns["BASE_PATH"]:
                raise AssertionError("Platný 2.2.16 Program nesmí spouštět plnou obnovu.")
            return payload_bytes[path]

        install_runtime.__globals__["_download"] = fake_download
        install_runtime(root)

        assert database.read_bytes() == before
        assert (program / ".turto_runtime_2_2_18.ok").read_text(encoding="utf-8") == "2.2.18"
        assert not (program / ".turto_runtime_2_2_16.ok").exists()
        assert all((program / name).is_file() for name in ns["CURRENT_REQUIRED"])
        assert (program / "app_runtime.pyw").read_bytes() == runtime.read_bytes()
        assert (program / "hit_workspace.py").read_bytes() == (ROOT / payloads["hit_workspace.py"][1]).read_bytes()
        assert ns["BASE_PATH"] not in calls
        assert set(calls) == {value[1] for value in payloads.values()}

    print(
        "OK: TURTO 2.2.18 – historical recovery remains reproducible; current "
        "release retains root-only manifest and data-protection guarantees."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
