from __future__ import annotations

"""TURTO 2.2.13 stage-3 cleanup: move duplicated root runtime into Archiv."""

import hashlib
import shutil
import time
from pathlib import Path

VERSION = "2.2.13"

PROTECTED_ROOT_FILES = {
    "app.pyw",
    "updater.py",
    "actions.sqlite3",
    "version.txt",
    ".turto_runtime_current.ok",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _unique_target(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if not target.exists():
        return target
    src = Path(name)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = folder / f"{src.stem}_{stamp}{src.suffix}"
    index = 2
    while target.exists():
        target = folder / f"{src.stem}_{stamp}_{index}{src.suffix}"
        index += 1
    return target


def _program_complete(program: Path, required_program_files: tuple[str, ...]) -> bool:
    return program.is_dir() and all((program / rel).is_file() for rel in required_program_files)


def cleanup_stage3(
    root: Path,
    program: Path,
    required_program_files: tuple[str, ...],
    log_dir: Path,
    cleanup_log: Path,
) -> None:
    """Archive only root code that has a verified replacement in Program\."""
    root = Path(root).resolve()
    program = Path(program).resolve()
    actions: list[str] = []
    errors: list[str] = []

    if not _program_complete(program, required_program_files):
        return

    archive = root / "Archiv" / "Runtime_pred_2.2.13"
    for pattern in ("*.py", "*.pyw"):
        for source in root.glob(pattern):
            if not source.is_file() or source.name in PROTECTED_ROOT_FILES:
                continue
            replacement = program / source.name
            if not replacement.is_file():
                continue
            try:
                target = _unique_target(archive, source.name)
                shutil.move(str(source), str(target))
                actions.append(
                    f"Přesunuto duplicitní runtime: {source.name} -> {target.relative_to(root)}"
                )
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")

    # Bytecode caches are generated files and can safely be rebuilt in Program.
    for cache in (root / "__pycache__",):
        try:
            if cache.is_dir():
                shutil.rmtree(cache)
                actions.append(f"Odstraněna cache: {cache.relative_to(root)}")
        except Exception as exc:
            errors.append(f"{cache}: {exc}")

    # Keep only three update backup generations, same policy as previous cleanup.
    update_backup = root / ".update_backup"
    try:
        if update_backup.is_dir():
            backups = [p for p in update_backup.iterdir() if p.is_dir()]
            backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for old in backups[3:]:
                shutil.rmtree(old)
                actions.append(f"Odstraněna stará záloha aktualizace: {old.name}")
    except Exception as exc:
        errors.append(f".update_backup: {exc}")

    if actions or errors:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with cleanup_log.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"TURTO {VERSION} – etapa 3 / Program layout\n"
                )
                for item in actions:
                    handle.write(f"OK  {item}\n")
                for item in errors:
                    handle.write(f"ERR {item}\n")
        except Exception:
            pass


def selftest() -> None:
    assert "app.pyw" in PROTECTED_ROOT_FILES
    assert "updater.py" in PROTECTED_ROOT_FILES
    assert "actions.sqlite3" in PROTECTED_ROOT_FILES


if __name__ == "__main__":
    selftest()
