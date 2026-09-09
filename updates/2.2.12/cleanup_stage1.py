from __future__ import annotations

"""First-stage conservative cleanup for TURTO installation root."""

import shutil
import time
from pathlib import Path

VERSION = "2.2.12"

LEGACY_LOG_PATTERNS = (
    "fix*.log",
    "startup*.log",
    "recovery*.log",
    "update_apply.log",
)
BACKUP_PATTERNS = (
    "*.bak",
    "*.bak_*",
    "*.py.bak_*",
    "*.pyw.bak_*",
)
VERIFICATION_FILES = (
    "REVIEW_VERIFICATION.json",
    "PDF_VERIFICATION.json",
    "HIT_WORKSPACE_VERIFICATION.json",
    "HIT_IMPORT_VERIFICATION.json",
    "HIT_HT_VERIFICATION.json",
)
DOCUMENTATION_FILES = (
    "GITHUB_REPO.txt",
    "README.txt",
    "DATA_VALIDATION.txt",
    "FORMAT_KATALOGU.md",
    "FORMAT_PROJEKTU.md",
    "CHANGELOG.txt",
)


def _unique_target(folder: Path, name: str) -> Path:
    target = folder / name
    if not target.exists():
        return target
    source = Path(name)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = folder / f"{source.stem}_{stamp}{source.suffix}"
    index = 2
    while candidate.exists():
        candidate = folder / f"{source.stem}_{stamp}_{index}{source.suffix}"
        index += 1
    return candidate


def _move_file(root: Path, source: Path, folder: Path, actions: list[str], errors: list[str]) -> None:
    try:
        if not source.is_file():
            return
        folder.mkdir(parents=True, exist_ok=True)
        target = _unique_target(folder, source.name)
        shutil.move(str(source), str(target))
        actions.append(f"Přesunuto: {source.name} -> {target.relative_to(root)}")
    except Exception as exc:
        errors.append(f"{source.name}: {exc}")


def _prune_files(root: Path, folder: Path, limit: int, cleanup_log: Path, actions: list[str], errors: list[str]) -> None:
    try:
        if not folder.is_dir():
            return
        files = [p for p in folder.iterdir() if p.is_file() and p.name != cleanup_log.name]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[limit:]:
            try:
                old.unlink()
                actions.append(f"Odstraněn starý soubor: {old.relative_to(root)}")
            except Exception as exc:
                errors.append(f"{old}: {exc}")
    except Exception as exc:
        errors.append(f"Čištění {folder.name}: {exc}")


def _prune_update_backups(root: Path, actions: list[str], errors: list[str], keep: int = 3) -> None:
    folder = root / ".update_backup"
    try:
        if not folder.is_dir():
            return
        backups = [p for p in folder.iterdir() if p.is_dir()]
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[keep:]:
            try:
                shutil.rmtree(old)
                actions.append(f"Odstraněna stará záloha aktualizace: {old.name}")
            except Exception as exc:
                errors.append(f"{old}: {exc}")
    except Exception as exc:
        errors.append(f"Čištění .update_backup: {exc}")


def cleanup_stage1(root: Path, marker: Path, log_dir: Path, backup_dir: Path, docs_dir: Path, cleanup_log: Path) -> None:
    root = Path(root).resolve()
    internal_docs = docs_dir / "Interni"
    actions: list[str] = []
    errors: list[str] = []

    seen: set[Path] = set()
    for pattern in LEGACY_LOG_PATTERNS:
        for source in root.glob(pattern):
            if source in seen:
                continue
            seen.add(source)
            _move_file(root, source, log_dir, actions, errors)

    seen.clear()
    for pattern in BACKUP_PATTERNS:
        for source in root.glob(pattern):
            if source in seen:
                continue
            seen.add(source)
            _move_file(root, source, backup_dir, actions, errors)

    for old_marker in root.glob(".turto_runtime_*.ok"):
        if old_marker == marker:
            continue
        try:
            old_marker.unlink()
            actions.append(f"Odstraněn starý runtime marker: {old_marker.name}")
        except Exception as exc:
            errors.append(f"{old_marker.name}: {exc}")

    for name in VERIFICATION_FILES:
        _move_file(root, root / name, internal_docs, actions, errors)

    for name in DOCUMENTATION_FILES:
        _move_file(root, root / name, docs_dir, actions, errors)

    _prune_files(root, log_dir, 20, cleanup_log, actions, errors)
    _prune_files(root, backup_dir, 10, cleanup_log, actions, errors)
    _prune_update_backups(root, actions, errors, keep=3)

    if actions or errors:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with cleanup_log.open("a", encoding="utf-8") as handle:
                handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] TURTO {VERSION} – etapa 1\n")
                for item in actions:
                    handle.write(f"OK  {item}\n")
                for item in errors:
                    handle.write(f"ERR {item}\n")
        except Exception:
            pass
