from __future__ import annotations

"""TURTO 2.2.15 cleanup – backup hierarchy and compressed historical runtime."""

import os
import shutil
import time
import zipfile
from pathlib import Path

VERSION = "2.2.15"

LEGACY_UPDATE_BACKUP = ".update_backup"
LEGACY_RECOVERY_PREFIX = ".recovery_backup_"
HISTORICAL_RUNTIME_DIR = "Runtime_pred_2.2.13"


def _unique_dir(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if not target.exists():
        return target
    stamp = time.strftime("%Y%m%d_%H%M%S")
    index = 1
    while True:
        suffix = f"_{stamp}" if index == 1 else f"_{stamp}_{index}"
        candidate = folder / f"{name}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _move_dir(source: Path, destination_root: Path, name: str, actions: list[str], errors: list[str], root: Path) -> None:
    try:
        if not source.is_dir():
            return
        target = _unique_dir(destination_root, name)
        shutil.move(str(source), str(target))
        actions.append(f"Přesunuta záloha: {source.name} -> {target.relative_to(root)}")
    except Exception as exc:
        errors.append(f"{source}: {exc}")


def _migrate_update_backups(root: Path, actions: list[str], errors: list[str]) -> None:
    legacy = root / LEGACY_UPDATE_BACKUP
    destination = root / "Zaloha" / "Aktualizace"
    if not legacy.is_dir():
        return
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(legacy.iterdir(), key=lambda p: p.name):
            if child.is_dir():
                target = _unique_dir(destination, child.name)
                shutil.move(str(child), str(target))
                actions.append(
                    f"Přesunuta stará aktualizační záloha: {child.name} -> {target.relative_to(root)}"
                )
            elif child.is_file():
                misc = destination / "Ostatni"
                misc.mkdir(parents=True, exist_ok=True)
                target = misc / child.name
                if target.exists():
                    target = misc / f"{child.stem}_{time.strftime('%Y%m%d_%H%M%S')}{child.suffix}"
                shutil.move(str(child), str(target))
                actions.append(
                    f"Přesunut soubor staré aktualizační zálohy: {child.name} -> {target.relative_to(root)}"
                )
        try:
            legacy.rmdir()
            actions.append(f"Odstraněna prázdná stará složka: {LEGACY_UPDATE_BACKUP}")
        except OSError:
            pass
    except Exception as exc:
        errors.append(f"{legacy}: {exc}")


def _migrate_recovery_backups(root: Path, actions: list[str], errors: list[str]) -> None:
    destination = root / "Zaloha" / "Recovery"
    for source in sorted(root.glob(f"{LEGACY_RECOVERY_PREFIX}*"), key=lambda p: p.name):
        if not source.is_dir():
            continue
        clean_name = source.name[len(LEGACY_RECOVERY_PREFIX):] or source.name
        _move_dir(source, destination, clean_name, actions, errors, root)


def _verified_zip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(source))
        with zipfile.ZipFile(temporary, "r") as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Kontrola ZIP archivu selhala.")
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _compress_historical_runtime(root: Path, actions: list[str], errors: list[str]) -> None:
    source = root / "Archiv" / HISTORICAL_RUNTIME_DIR
    if not source.is_dir():
        return
    try:
        if not any(path.is_file() for path in source.rglob("*")):
            shutil.rmtree(source)
            actions.append(f"Odstraněn prázdný archiv: {source.relative_to(root)}")
            return
        archive_root = root / "Zaloha" / "Archiv"
        archive_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = archive_root / f"{HISTORICAL_RUNTIME_DIR}_{stamp}.zip"
        index = 2
        while target.exists():
            target = archive_root / f"{HISTORICAL_RUNTIME_DIR}_{stamp}_{index}.zip"
            index += 1
        _verified_zip(source, target)
        shutil.rmtree(source)
        actions.append(
            f"Zkomprimován historický runtime: {source.relative_to(root)} -> {target.relative_to(root)}"
        )
    except Exception as exc:
        errors.append(f"{source}: {exc}")


def _prune_dirs(folder: Path, pattern: str, keep: int, root: Path, actions: list[str], errors: list[str]) -> None:
    try:
        if not folder.is_dir():
            return
        items = [p for p in folder.glob(pattern) if p.is_dir()]
        items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in items[keep:]:
            try:
                shutil.rmtree(old)
                actions.append(f"Odstraněna stará záloha: {old.relative_to(root)}")
            except Exception as exc:
                errors.append(f"{old}: {exc}")
    except Exception as exc:
        errors.append(f"{folder}: {exc}")


def _prune_files(folder: Path, pattern: str, keep: int, root: Path, actions: list[str], errors: list[str]) -> None:
    try:
        if not folder.is_dir():
            return
        items = [p for p in folder.glob(pattern) if p.is_file()]
        items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in items[keep:]:
            try:
                old.unlink()
                actions.append(f"Odstraněna stará archivní záloha: {old.relative_to(root)}")
            except Exception as exc:
                errors.append(f"{old}: {exc}")
    except Exception as exc:
        errors.append(f"{folder}: {exc}")


def cleanup_stage4(root: Path, log_dir: Path, cleanup_log: Path) -> None:
    root = Path(root).resolve()
    actions: list[str] = []
    errors: list[str] = []

    _migrate_update_backups(root, actions, errors)
    _migrate_recovery_backups(root, actions, errors)
    _compress_historical_runtime(root, actions, errors)

    backup_root = root / "Zaloha"
    _prune_dirs(backup_root / "Aktualizace", "*", 3, root, actions, errors)
    _prune_dirs(backup_root / "Recovery", "*", 3, root, actions, errors)
    _prune_dirs(backup_root, "Program_pred_*", 2, root, actions, errors)
    _prune_files(backup_root / "Archiv", f"{HISTORICAL_RUNTIME_DIR}_*.zip", 2, root, actions, errors)

    if actions or errors:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with cleanup_log.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"TURTO {VERSION} – etapa 4 / zálohy a archiv\n"
                )
                for item in actions:
                    handle.write(f"OK  {item}\n")
                for item in errors:
                    handle.write(f"ERR {item}\n")
        except Exception:
            pass


def selftest() -> None:
    assert LEGACY_UPDATE_BACKUP == ".update_backup"
    assert LEGACY_RECOVERY_PREFIX == ".recovery_backup_"
    assert HISTORICAL_RUNTIME_DIR == "Runtime_pred_2.2.13"


if __name__ == "__main__":
    selftest()
