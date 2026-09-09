from __future__ import annotations

"""TURTO 2.2.17 cleanup – archive obsolete HIT compatibility wrappers safely."""

import ast
import hashlib
import os
import shutil
import time
import zipfile
from pathlib import Path

VERSION = "2.2.17"
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


def _safe_obsolete_wrappers(program: Path) -> list[Path]:
    candidates = [program / name for name in OBSOLETE_HIT_WRAPPERS if (program / name).is_file()]
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


def _archive_hit_wrappers(root: Path, program: Path, actions: list[str], errors: list[str]) -> None:
    safe = _safe_obsolete_wrappers(program)
    if not safe:
        return

    target = _unique_zip(root / "Zaloha" / "Archiv", "Program_legacy_HIT_2.2.17")
    temporary = target.with_name(target.name + ".part")
    expected = {path.name: _sha256(path.read_bytes()) for path in safe}
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in safe:
                archive.write(path, path.name)
        with zipfile.ZipFile(temporary, "r") as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Kontrola ZIP archivu HIT wrapperů selhala.")
            for name, digest in expected.items():
                if _sha256(archive.read(name)) != digest:
                    raise RuntimeError(f"Obsah archivu nesouhlasí pro {name}.")
        os.replace(temporary, target)
        for path in safe:
            path.unlink()
        actions.append(
            "Archivovány nepoužívané HIT wrappery: "
            + ", ".join(path.name for path in safe)
            + f" -> {target.relative_to(root)}"
        )
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        errors.append(f"Archivace HIT wrapperů: {exc}")


def _clear_program_cache(program: Path, root: Path, actions: list[str], errors: list[str]) -> None:
    cache = program / "__pycache__"
    try:
        if cache.is_dir():
            shutil.rmtree(cache)
            actions.append(f"Odstraněna regenerovatelná Python cache: {cache.relative_to(root)}")
    except Exception as exc:
        errors.append(f"{cache}: {exc}")


def _prune_archives(root: Path, actions: list[str], errors: list[str], keep: int = 2) -> None:
    folder = root / "Zaloha" / "Archiv"
    try:
        if not folder.is_dir():
            return
        items = [p for p in folder.glob("Program_legacy_HIT_2.2.17_*.zip") if p.is_file()]
        items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in items[keep:]:
            old.unlink()
            actions.append(f"Odstraněna stará HIT archivní záloha: {old.relative_to(root)}")
    except Exception as exc:
        errors.append(f"Pruning HIT archivů: {exc}")


def cleanup_stage6(root: Path, program: Path, log_dir: Path, cleanup_log: Path) -> None:
    root = Path(root).resolve()
    program = Path(program).resolve()
    actions: list[str] = []
    errors: list[str] = []

    # actions.sqlite3 is intentionally outside every cleanup target.
    _archive_hit_wrappers(root, program, actions, errors)
    _clear_program_cache(program, root, actions, errors)
    _prune_archives(root, actions, errors, keep=2)

    if actions or errors:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with cleanup_log.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"TURTO {VERSION} – etapa 6 / flatten HIT workspace\n"
                )
                for item in actions:
                    handle.write(f"OK  {item}\n")
                for item in errors:
                    handle.write(f"ERR {item}\n")
        except Exception:
            pass


def selftest() -> None:
    assert "actions.sqlite3" in PROTECTED_NAMES
    assert "hit_workspace_201.py" in OBSOLETE_HIT_WRAPPERS
    assert "hit_workspace_125.py" not in OBSOLETE_HIT_WRAPPERS


if __name__ == "__main__":
    selftest()
