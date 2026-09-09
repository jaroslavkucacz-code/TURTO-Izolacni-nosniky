from __future__ import annotations

"""Regression checks for TURTO 2.2.15 backup and root cleanup."""

import ast
import hashlib
import json
import os
import re
import runpy
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.15"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"{path}: chybí literální přiřazení {name}")


def _touch_dir(path: Path, age: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "data.txt").write_text(path.name, encoding="utf-8")
    stamp = 2_000_000_000 - age
    os.utime(path, (stamp, stamp))


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def main() -> int:
    required = (
        "app.pyw",
        "app_runtime.pyw",
        "runtime_installer.py",
        "cleanup_stage4.py",
        "updater.py",
        "RELEASE_NOTES.txt",
        "release_contract.json",
    )
    for name in required:
        path = RELEASE / name
        if not path.is_file():
            raise RuntimeError(f"Chybí {path.relative_to(ROOT)}")
        if path.suffix.lower() in {".py", ".pyw"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    app = (RELEASE / "app.pyw").read_text(encoding="utf-8")
    updater = (RELEASE / "updater.py").read_text(encoding="utf-8")
    cleanup = (RELEASE / "cleanup_stage4.py").read_text(encoding="utf-8")
    recovery = (ROOT / "OPRAVIT_TURTO.ps1").read_text(encoding="utf-8")

    for token in (
        'VERSION = "2.2.15"',
        'RUNTIME_LAYOUT = "8"',
        'PROGRAM_REVISION = PROGRAM / ".turto_runtime_2_2_15.ok"',
        '"cleanup_stage4.py"',
        "from cleanup_stage4 import cleanup_stage4",
    ):
        assert token in app, token

    for token in (
        'PROTECTED_TARGETS = {"actions.sqlite3"}',
        'LEGACY_UPDATE_BACKUP = ".update_backup"',
        'backup = dst / "Zaloha" / "Aktualizace" / stamp',
        'log_path = dst / "Logy" / "update_apply.log"',
        "rollback",
        "os.replace",
    ):
        assert token in updater, token

    for token in (
        'LEGACY_UPDATE_BACKUP = ".update_backup"',
        'LEGACY_RECOVERY_PREFIX = ".recovery_backup_"',
        '"Zaloha" / "Aktualizace"',
        '"Zaloha" / "Recovery"',
        '"Zaloha" / "Archiv"',
        '"Program_pred_*"',
        "archive.testzip()",
    ):
        assert token in cleanup, token

    recovery_match = re.search(r"^\$Version\s*=\s*'([^']+)'", recovery, flags=re.MULTILINE)
    assert recovery_match is not None
    assert _version_tuple(recovery_match.group(1)) >= (2, 2, 15)
    assert "'Zaloha') 'Recovery'" in recovery
    assert "$logDir = Join-Path $target 'Logy'" in recovery
    assert "$RecoveryLogName = 'recovery.log'" in recovery
    assert ".recovery_backup_" not in recovery

    base_hash = literal(RELEASE / "runtime_installer.py", "BASE_SHA256")
    assert sha256(ROOT / "updates" / "2.2.14" / "runtime_installer.py") == base_hash
    payloads = literal(RELEASE / "runtime_installer.py", "PAYLOADS")
    assert set(payloads) == {"app_runtime.pyw", "cleanup_stage4.py"}
    for _local, (_commit, source, expected) in payloads.items():
        source_path = ROOT / source
        assert source_path.is_file(), source
        assert sha256(source_path) == expected

    installer_hash = literal(RELEASE / "app.pyw", "INSTALLER_SHA256")
    assert sha256(RELEASE / "runtime_installer.py") == installer_hash

    module = runpy.run_path(str(RELEASE / "cleanup_stage4.py"), run_name="verify_cleanup_2215")
    with tempfile.TemporaryDirectory(prefix="turto_2215_cleanup_") as temp_name:
        root = Path(temp_name)
        log_dir = root / "Logy"
        database = root / "actions.sqlite3"
        database.write_bytes(b"database-must-stay-byte-identical")
        before = database.read_bytes()

        legacy_update = root / ".update_backup"
        for index in range(4):
            _touch_dir(legacy_update / f"update_{index}", age=index)

        for index in range(4):
            _touch_dir(root / f".recovery_backup_2026090{index}_120000", age=index)

        historical = root / "Archiv" / "Runtime_pred_2.2.13"
        historical.mkdir(parents=True)
        (historical / "old_module.py").write_text("OLD = True\n", encoding="utf-8")

        backup_root = root / "Zaloha"
        for index in range(3):
            _touch_dir(backup_root / f"Program_pred_2.2.13_2026090{index}", age=index)

        module["cleanup_stage4"](root, log_dir, log_dir / "cleanup.log")

        assert database.read_bytes() == before
        assert not (root / ".update_backup").exists()
        assert not any(root.glob(".recovery_backup_*"))
        assert len([p for p in (backup_root / "Aktualizace").iterdir() if p.is_dir()]) == 3
        assert len([p for p in (backup_root / "Recovery").iterdir() if p.is_dir()]) == 3
        assert len([p for p in backup_root.glob("Program_pred_*") if p.is_dir()]) == 2
        assert not historical.exists()

        archives = list((backup_root / "Archiv").glob("Runtime_pred_2.2.13_*.zip"))
        assert len(archives) == 1
        with zipfile.ZipFile(archives[0], "r") as archive:
            assert archive.testzip() is None
            assert "old_module.py" in archive.namelist()
            normalized = archive.read("old_module.py").replace(b"\r\n", b"\n")
            assert normalized == b"OLD = True\n"

    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    assert _version_tuple(str(manifest["version"])) >= (2, 2, 15)
    assert int(str(manifest["runtime_layout"])) >= 8
    assert all(item["path"] != "actions.sqlite3" for item in manifest["files"])

    print("OK: TURTO 2.2.15+ – backup hierarchy, archive compression and data protection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
