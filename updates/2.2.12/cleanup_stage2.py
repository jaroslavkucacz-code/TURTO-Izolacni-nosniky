from __future__ import annotations

"""Second-stage safe cleanup for TURTO installation root."""

import ast
import re
import shutil
import time
from pathlib import Path

VERSION = "2.2.12"

LEGACY_CODE_PATTERNS = (
    "app_central*.pyw",
    "app_old*.pyw",
    "app_legacy*.pyw",
    "action_*.py",
    "platform_*.py",
)
DIAGNOSTIC_PATTERNS = (
    "*DIAGNOST*.bat",
    "*DIAGNOST*.vbs",
    "*DIAGNOST*.cmd",
    "*TEST*.bat",
    "*TEST*.vbs",
    "fix*.bat",
    "fix*.vbs",
    "recovery*.bat",
    "recovery*.vbs",
)
SOURCE_FILES = (
    "schoeck_archive_sources.json",
)

PROTECTED_NAMES = {
    "app.pyw",
    "app_runtime.pyw",
    "app_runtime_202.pyw",
    "Spustit_program.vbs",
    "actions.sqlite3",
    "version.txt",
    ".turto_runtime_current.ok",
}


def _unique_target(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if not target.exists():
        return target
    source = Path(name)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = folder / f"{source.stem}_{stamp}{source.suffix}"
    index = 2
    while target.exists():
        target = folder / f"{source.stem}_{stamp}_{index}{source.suffix}"
        index += 1
    return target


def _root_python_files(root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for pattern in ("*.py", "*.pyw"):
        for path in root.glob(pattern):
            if path.is_file():
                modules.setdefault(path.stem, path)
    return modules


def _import_names(text: str) -> set[str]:
    names: set[str] = set()
    try:
        tree = ast.parse(text)
    except Exception:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".", 1)[0])

    for match in re.finditer(r'''['"]([A-Za-z_][A-Za-z0-9_]*)['"]''', text):
        names.add(match.group(1))
    return names


def _active_runtime_files(root: Path, required_runtime_files: tuple[str, ...]) -> set[Path]:
    modules = _root_python_files(root)
    active: set[Path] = set()
    queue: list[Path] = []

    seed_names = {
        "app.pyw",
        "app_runtime.pyw",
        "app_runtime_202.pyw",
        *required_runtime_files,
    }
    for name in seed_names:
        path = root / name
        if path.is_file() and path.suffix.lower() in {".py", ".pyw"}:
            queue.append(path)

    while queue:
        path = queue.pop()
        try:
            path = path.resolve()
        except Exception:
            continue
        if path in active or not path.is_file():
            continue
        active.add(path)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for module_name in _import_names(text):
            dep = modules.get(module_name)
            if dep is not None:
                try:
                    resolved = dep.resolve()
                except Exception:
                    continue
                if resolved not in active:
                    queue.append(dep)

        for stem, dep in modules.items():
            try:
                resolved = dep.resolve()
            except Exception:
                continue
            if resolved in active:
                continue
            if re.search(rf"\b{re.escape(stem)}\b", text):
                queue.append(dep)

    return active


def _referenced_by_launcher(root: Path, candidate: Path) -> bool:
    needle_name = candidate.name.lower()
    needle_stem = candidate.stem.lower()
    for pattern in ("*.vbs", "*.bat", "*.cmd", "*.ps1"):
        for launcher in root.glob(pattern):
            if not launcher.is_file():
                continue
            try:
                text = launcher.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            if needle_name in text or needle_stem in text:
                return True
    return False


def _move(source: Path, folder: Path, actions: list[str], errors: list[str], root: Path) -> None:
    try:
        if not source.is_file():
            return
        target = _unique_target(folder, source.name)
        shutil.move(str(source), str(target))
        actions.append(f"Přesunuto: {source.name} -> {target.relative_to(root)}")
    except Exception as exc:
        errors.append(f"{source.name}: {exc}")


def cleanup_stage2(
    root: Path,
    required_runtime_files: tuple[str, ...],
    log_dir: Path,
    cleanup_log: Path,
) -> None:
    root = Path(root).resolve()
    archive_modules = root / "Archiv" / "Stare_moduly"
    diagnostics = root / "Nastroje" / "Diagnostika"
    source_docs = root / "Dokumentace" / "Zdroje"

    actions: list[str] = []
    errors: list[str] = []

    try:
        active = _active_runtime_files(root, required_runtime_files)
    except Exception as exc:
        active = set()
        errors.append(f"Analýza aktivních modulů selhala; moduly se nearchivují: {exc}")

    if active:
        seen: set[Path] = set()
        for pattern in LEGACY_CODE_PATTERNS:
            for candidate in root.glob(pattern):
                if candidate in seen or not candidate.is_file():
                    continue
                seen.add(candidate)
                if candidate.name in PROTECTED_NAMES:
                    continue
                if candidate.name in required_runtime_files:
                    continue
                try:
                    if candidate.resolve() in active:
                        continue
                except Exception:
                    continue
                if _referenced_by_launcher(root, candidate):
                    continue
                _move(candidate, archive_modules, actions, errors, root)

    seen = set()
    for pattern in DIAGNOSTIC_PATTERNS:
        for candidate in root.glob(pattern):
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            if candidate.name in PROTECTED_NAMES:
                continue
            _move(candidate, diagnostics, actions, errors, root)

    for name in SOURCE_FILES:
        _move(root / name, source_docs, actions, errors, root)

    if actions or errors:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with cleanup_log.open("a", encoding="utf-8") as handle:
                handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] TURTO {VERSION} – etapa 2\n")
                for item in actions:
                    handle.write(f"OK  {item}\n")
                for item in errors:
                    handle.write(f"ERR {item}\n")
        except Exception:
            pass


def selftest() -> None:
    assert "app.pyw" in PROTECTED_NAMES
    assert "actions.sqlite3" in PROTECTED_NAMES
    assert any("action_" in p for p in LEGACY_CODE_PATTERNS)
