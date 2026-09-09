from __future__ import annotations

"""TURTO 2.2.17 cleanup – flatten HIT/runtime wrappers and finish one-shot housekeeping."""

import ast
import hashlib
import os
import shutil
import time
import zipfile
from pathlib import Path

VERSION = "2.2.17"
OBSOLETE_APP_WRAPPERS = (
    "app_runtime_202.pyw",
    "app_runtime_200.pyw",
    "app_runtime_127.pyw",
    "app_runtime_prev.pyw",
)
OBSOLETE_HIT_WRAPPERS = (
    "hit_workspace_201.py",
    "hit_workspace_200.py",
    "hit_workspace_127.py",
)
PROTECTED_NAMES = {
    "actions.sqlite3",
    "app.pyw",
    "updater.py",
    "version.txt",
    ".turto_runtime_current.ok",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _local_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            func = node.func
            dynamic = (
                isinstance(func, ast.Name) and func.id == "__import__"
            ) or (
                isinstance(func, ast.Attribute)
                and func.attr in {"import_module", "spec_from_file_location"}
            )
            if dynamic:
                for arg in node.args[:2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        names.add(arg.value.split(".", 1)[0])
    return names


def _safe_obsolete_wrappers(program: Path, names: tuple[str, ...]) -> list[Path]:
    candidates = [program / name for name in names if (program / name).is_file()]
    if not candidates:
        return []

    candidate_modules = {path.stem for path in candidates}
    referenced: set[str] = set()
    for path in sorted(program.glob("*.py*")):
        if not path.is_file() or path in candidates:
            continue
        try:
            referenced.update(_local_imports(path) & candidate_modules)
        except Exception:
            # Dependency analysis is deliberately fail-closed.
            return []
    return [path for path in candidates if path.stem not in referenced]


def _unique_zip(folder: Path, prefix: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = folder / f"{prefix}_{stamp}.zip"
    index = 2
    while target.exists():
        target = folder / f"{prefix}_{stamp}_{index}.zip"
        index += 1
    return target


def _archive_group(
    root: Path,
    program: Path,
    names: tuple[str, ...],
    prefix: str,
    label: str,
    actions: list[str],
    errors: list[str],
) -> None:
    safe = _safe_obsolete_wrappers(program, names)
    if not safe:
        return

    target = _unique_zip(root / "Zaloha" / "Archiv", prefix)
    temporary = target.with_name(target.name + ".part")
    expected = {path.name: _sha256(path.read_bytes()) for path in safe}
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in safe:
                archive.write(path, path.name)
        with zipfile.ZipFile(temporary, "r") as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"Kontrola ZIP archivu {label} selhala.")
            for name, digest in expected.items():
                if _sha256(archive.read(name)) != digest:
                    raise RuntimeError(f"Obsah archivu nesouhlasí pro {name}.")
        os.replace(temporary, target)
        for path in safe:
            path.unlink()
        actions.append(
            f"Archivovány nepoužívané {label}: "
            + ", ".join(path.name for path in safe)
            + f" -> {target.relative_to(root)}"
        )
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        errors.append(f"Archivace {label}: {exc}")


def _move_release_notes(root: Path, actions: list[str], errors: list[str]) -> None:
    source = root / "RELEASE_NOTES.txt"
    if not source.is_file():
        return
    destination = root / "Dokumentace" / "Interni" / "Vydani"
    try:
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / f"TURTO_{VERSION}.txt"
        if target.exists() and target.read_bytes() == source.read_bytes():
            source.unlink()
        elif target.exists():
            stamp = time.strftime("%Y%m%d_%H%M%S")
            target = destination / f"TURTO_{VERSION}_{stamp}.txt"
            shutil.move(str(source), str(target))
        else:
            shutil.move(str(source), str(target))
        actions.append(f"Přesunuty poznámky k vydání -> {target.relative_to(root)}")
    except Exception as exc:
        errors.append(f"RELEASE_NOTES.txt: {exc}")


def _remove_stale_internal_files(root: Path, program: Path, actions: list[str], errors: list[str]) -> None:
    cutoff = time.time() - 3600
    for folder in (root, program):
        for pattern in ("*.turto_new", "*.turto_restore"):
            for path in folder.glob(pattern):
                try:
                    if path.is_file() and path.name not in PROTECTED_NAMES and path.stat().st_mtime < cutoff:
                        path.unlink()
                        actions.append(f"Odstraněn starý interní dočasný soubor: {path.relative_to(root)}")
                except Exception as exc:
                    errors.append(f"{path}: {exc}")


def _clear_program_cache(program: Path, root: Path, actions: list[str], errors: list[str]) -> None:
    cache = program / "__pycache__"
    try:
        if cache.is_dir():
            shutil.rmtree(cache)
            actions.append(f"Odstraněna regenerovatelná Python cache: {cache.relative_to(root)}")
    except Exception as exc:
        errors.append(f"{cache}: {exc}")


def _prune_archives(root: Path, pattern: str, actions: list[str], errors: list[str], keep: int = 2) -> None:
    folder = root / "Zaloha" / "Archiv"
    try:
        if not folder.is_dir():
            return
        items = [p for p in folder.glob(pattern) if p.is_file()]
        items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in items[keep:]:
            old.unlink()
            actions.append(f"Odstraněna stará runtime archivní záloha: {old.relative_to(root)}")
    except Exception as exc:
        errors.append(f"Pruning archivů {pattern}: {exc}")


def _remove_empty_archive_dir(root: Path, actions: list[str]) -> None:
    archive = root / "Archiv"
    try:
        if archive.is_dir() and not any(archive.iterdir()):
            archive.rmdir()
            actions.append("Odstraněna prázdná složka Archiv")
    except Exception:
        pass


def cleanup_stage6(root: Path, program: Path, log_dir: Path, cleanup_log: Path) -> None:
    root = Path(root).resolve()
    program = Path(program).resolve()
    actions: list[str] = []
    errors: list[str] = []

    # actions.sqlite3 is intentionally outside every cleanup target.
    _archive_group(
        root,
        program,
        OBSOLETE_APP_WRAPPERS,
        "Program_legacy_runtime_2.2.17",
        "runtime wrappery",
        actions,
        errors,
    )
    _archive_group(
        root,
        program,
        OBSOLETE_HIT_WRAPPERS,
        "Program_legacy_HIT_2.2.17",
        "HIT wrappery",
        actions,
        errors,
    )
    _move_release_notes(root, actions, errors)
    _remove_stale_internal_files(root, program, actions, errors)
    _clear_program_cache(program, root, actions, errors)
    _prune_archives(root, "Program_legacy_runtime_2.2.17_*.zip", actions, errors, keep=2)
    _prune_archives(root, "Program_legacy_HIT_2.2.17_*.zip", actions, errors, keep=2)
    _remove_empty_archive_dir(root, actions)

    if actions or errors:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with cleanup_log.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"TURTO {VERSION} – etapa 6 / flatten HIT a runtime\n"
                )
                for item in actions:
                    handle.write(f"OK  {item}\n")
                for item in errors:
                    handle.write(f"ERR {item}\n")
        except Exception:
            pass


def selftest() -> None:
    assert "actions.sqlite3" in PROTECTED_NAMES
    assert "app_runtime_202.pyw" in OBSOLETE_APP_WRAPPERS
    assert "hit_workspace_201.py" in OBSOLETE_HIT_WRAPPERS
    assert "hit_workspace_125.py" not in OBSOLETE_HIT_WRAPPERS


if __name__ == "__main__":
    selftest()
