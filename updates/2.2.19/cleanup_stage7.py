from __future__ import annotations

"""TURTO 2.2.19 cleanup – archive dead compatibility layers after a successful app run."""

import ast
import hashlib
import os
import shutil
import time
import zipfile
from pathlib import Path

VERSION = "2.2.19"

OBSOLETE_PROGRAM_FILES = (
    "app_runtime_202.pyw",
    "app_runtime_200.pyw",
    "app_runtime_127.pyw",
    "app_runtime_prev.pyw",
    "hit_workspace_201.py",
    "hit_workspace_200.py",
    "hit_workspace_127.py",
    "hit_workspace_125.py",
    "hit_workspace_prev.py",
    "cleanup_stage3.py",
    "cleanup_stage4.py",
    "cleanup_stage5.py",
    "cleanup_stage6.py",
)

PROTECTED_NAMES = {
    "actions.sqlite3",
    "app.pyw",
    "updater.py",
    "version.txt",
    ".turto_runtime_current.ok",
    "app_runtime.pyw",
    "app_central_prev.pyw",
    "app_base.py",
    "hit_workspace.py",
    "hit_workspace_base.py",
    "cleanup_stage7.py",
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
                and func.attr in {"import_module", "spec_from_file_location", "run_path"}
            )
            if dynamic:
                for arg in node.args[:2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        value = arg.value.replace("\\", "/").rsplit("/", 1)[-1]
                        names.add(value.rsplit(".", 1)[0])
    return names


def _safe_obsolete_files(program: Path) -> list[Path]:
    candidates = [
        program / name
        for name in OBSOLETE_PROGRAM_FILES
        if (program / name).is_file()
    ]
    if not candidates:
        return []

    candidate_modules = {path.stem for path in candidates}
    externally_referenced: set[str] = set()

    for path in sorted(program.glob("*.py*")):
        if not path.is_file() or path in candidates:
            continue
        try:
            externally_referenced.update(_local_imports(path) & candidate_modules)
        except Exception:
            # Any uncertainty keeps every candidate in place.
            return []

    return [path for path in candidates if path.stem not in externally_referenced]


def _unique_archive(root: Path) -> Path:
    folder = root / "Zaloha" / "Archiv"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = folder / f"Program_legacy_layers_2.2.19_{stamp}.zip"
    index = 2
    while target.exists():
        target = folder / f"Program_legacy_layers_2.2.19_{stamp}_{index}.zip"
        index += 1
    return target


def _archive_obsolete(
    root: Path,
    program: Path,
    actions: list[str],
    errors: list[str],
) -> set[str]:
    safe = _safe_obsolete_files(program)
    if not safe:
        return set()

    target = _unique_archive(root)
    temporary = target.with_name(target.name + ".part")
    expected = {path.name: _sha256(path.read_bytes()) for path in safe}
    total_bytes = sum(path.stat().st_size for path in safe)

    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for path in safe:
                archive.write(path, path.name)

        with zipfile.ZipFile(temporary, "r") as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Kontrola ZIP archivu historických vrstev selhala.")
            archived_names = set(archive.namelist())
            if archived_names != set(expected):
                raise RuntimeError("ZIP archiv neobsahuje přesně očekávanou sadu souborů.")
            for name, digest in expected.items():
                if _sha256(archive.read(name)) != digest:
                    raise RuntimeError(f"Obsah archivu nesouhlasí pro {name}.")

        os.replace(temporary, target)

        removed: set[str] = set()
        for path in safe:
            if path.name in PROTECTED_NAMES:
                raise RuntimeError(f"Interní ochrana zabránila odstranění {path.name}.")
            path.unlink()
            removed.add(path.stem)

        actions.append(
            "Archivovány nepoužívané vrstvy: "
            + ", ".join(path.name for path in safe)
            + f" -> {target.relative_to(root)} "
            + f"({total_bytes / 1024:.1f} KiB před kompresí)"
        )
        return removed
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        errors.append(f"Archivace historických vrstev: {exc}")
        return set()


def _prune_stale_bytecode(
    root: Path,
    program: Path,
    removed_modules: set[str],
    actions: list[str],
    errors: list[str],
) -> None:
    if not removed_modules:
        return
    cache = program / "__pycache__"
    if not cache.is_dir():
        return

    removed_count = 0
    try:
        for module in sorted(removed_modules):
            for path in cache.glob(f"{module}.*.pyc"):
                if path.is_file():
                    path.unlink()
                    removed_count += 1
        if removed_count:
            actions.append(
                f"Odstraněno {removed_count} zastaralých .pyc souborů; "
                "cache aktivních modulů byla zachována pro rychlejší start."
            )
    except Exception as exc:
        errors.append(f"Úklid zastaralé Python cache: {exc}")


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


def _remove_stale_internal_files(
    root: Path,
    program: Path,
    actions: list[str],
    errors: list[str],
) -> None:
    cutoff = time.time() - 3600
    for folder in (root, program):
        for pattern in ("*.turto_new", "*.turto_restore", "*.part"):
            for path in folder.glob(pattern):
                try:
                    if (
                        path.is_file()
                        and path.name not in PROTECTED_NAMES
                        and path.stat().st_mtime < cutoff
                    ):
                        path.unlink()
                        actions.append(
                            f"Odstraněn starý interní dočasný soubor: {path.relative_to(root)}"
                        )
                except Exception as exc:
                    errors.append(f"{path}: {exc}")


def _prune_archives(
    root: Path,
    actions: list[str],
    errors: list[str],
    keep: int = 2,
) -> None:
    folder = root / "Zaloha" / "Archiv"
    try:
        if not folder.is_dir():
            return
        items = [
            path
            for path in folder.glob("Program_legacy_layers_2.2.19_*.zip")
            if path.is_file()
        ]
        items.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for old in items[keep:]:
            old.unlink()
            actions.append(f"Odstraněna stará archivní záloha: {old.relative_to(root)}")
    except Exception as exc:
        errors.append(f"Pruning archivů 2.2.19: {exc}")


def cleanup_stage7(
    root: Path,
    program: Path,
    log_dir: Path,
    cleanup_log: Path,
) -> None:
    root = Path(root).resolve()
    program = Path(program).resolve()
    actions: list[str] = []
    errors: list[str] = []

    database = root / "actions.sqlite3"
    database_before = database.read_bytes() if database.is_file() else None

    removed_modules = _archive_obsolete(root, program, actions, errors)
    _prune_stale_bytecode(root, program, removed_modules, actions, errors)
    _move_release_notes(root, actions, errors)
    _remove_stale_internal_files(root, program, actions, errors)
    _prune_archives(root, actions, errors, keep=2)

    if database_before is not None:
        try:
            if not database.is_file() or database.read_bytes() != database_before:
                raise RuntimeError("actions.sqlite3 se během úklidu změnila.")
        except Exception as exc:
            errors.append(f"Kontrola databáze: {exc}")

    if actions or errors:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with cleanup_log.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"TURTO {VERSION} – etapa 7 / deep HIT flatten\n"
                )
                for item in actions:
                    handle.write(f"OK  {item}\n")
                for item in errors:
                    handle.write(f"ERR {item}\n")
        except Exception:
            pass


def selftest() -> None:
    assert "actions.sqlite3" in PROTECTED_NAMES
    assert "hit_workspace_125.py" in OBSOLETE_PROGRAM_FILES
    assert "hit_workspace_prev.py" in OBSOLETE_PROGRAM_FILES
    assert "hit_workspace_base.py" not in OBSOLETE_PROGRAM_FILES
    assert "cleanup_stage7.py" not in OBSOLETE_PROGRAM_FILES


if __name__ == "__main__":
    selftest()
