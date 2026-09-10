from __future__ import annotations

"""TURTO 2.2.24 runtime installer.

Repairs the verified shear-dowel chain even when an older installation carries
valid-looking version markers. Critical payload contents are verified by
SHA-256 before the installer accepts the runtime as current.

actions.sqlite3 is never modified.
"""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "f03e8f4284aeb575f4f47597b3f1e051c0e885a1"
BASE_PATH = "updates/2.2.23/runtime_installer.py"
BASE_SHA256 = "f46925d999d12db432bf44206ec16fc5eff79e03b567b0c75ae912efd258679b"

RUNTIME_LAYOUT = "17"
PROGRAM_REVISION = ".turto_runtime_2_2_24.ok"

PAYLOADS = {
    "app_runtime.pyw": (
        "bc740be50979563f86f1f9863fbde358a43b2e8a",
        "updates/2.2.24/app_runtime.pyw",
        "ed0dcb300ed07d12d70dc7775964d1ab38c1035e4ececd7ee379189004b2c23b",
    ),
    "shear_dowels_current.py": (
        "35d37bece6b17d1899ba96bf0f19d09dadceadf9",
        "updates/2.2.24/shear_dowels_current.py",
        "3643b6efec0e0e0109c5567cfea4f365ae52a12082134d228a6a13d1ee21aa60",
    ),
    "shear_dowels_current_221.py": (
        "3c4ebb0720f6db8e40bb59d697523b77fd3d53ca",
        "updates/2.2.21/shear_dowels_current.py",
        "de150f895f7be451a6f0dc46d05918ef75254604c3eb2557d4211ac7e4a01318",
    ),
    "shear_ui_227.py": (
        "5b5510e856198d20b02110a0666105d81c386f02",
        "updates/2.2.7/shear_ui_227.py",
        "c73e459a7ad8340d54d0fdc6990c5be936bcf55d3896fb4bd719d7c7180bd94d",
    ),
    "shear_catalogs_227.py": (
        "5c82c249d7ef2634df31a9f656c3cfc35eb61bfb",
        "updates/2.2.7/shear_catalogs_227.py",
        "b1e59c850451ae662e2bfc065db04ac8038f1dc3d2137776e9fcb314324ab44f",
    ),
    "shear_dowels_ui_215.py": (
        "58f5bcd6b322b85446672270c5881630e89cd172",
        "updates/2.1.5/shear_dowels_ui_215.py",
        "e510f974ac9f98320e563424da924a00c5dd9868fa5c836338ea2fac136ae265",
    ),
    "shear_dowels_ui_214.py": (
        "b198cbb7bf0720d694dfda5e9baf66c07d9bc23e",
        "updates/2.1.4/shear_dowels_ui_214.py",
        "ece048d76888dbdb398ea9b6c67ef4bcb2765a0904987ae358cc59765a069813",
    ),
}


def _url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def _download(commit: str, path: str, expected: str, agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                _url(commit, path) + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={
                    "User-Agent": agent,
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != expected.lower():
                raise RuntimeError(f"SHA-256 nesouhlasí pro {path}: {actual}")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout {path}: {last}")


def _revision(program: Path) -> bool:
    try:
        marker = program / PROGRAM_REVISION
        return marker.is_file() and marker.read_text(encoding="utf-8").strip() == "2.2.24"
    except Exception:
        return False


def _payloads_match(program: Path) -> bool:
    try:
        if not program.is_dir():
            return False
        for local, (_commit, _remote, expected) in PAYLOADS.items():
            path = program / local
            if not path.is_file():
                return False
            actual = hashlib.sha256(path.read_bytes()).hexdigest().lower()
            if actual != expected.lower():
                return False
        return True
    except Exception:
        return False


def _ensure_223_base(root: Path, temp: Path) -> None:
    base = temp / "base_installer.py"
    base.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.24-base"))
    namespace = runpy.run_path(str(base))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Ověřený installer 2.2.23 neobsahuje install_runtime().")
    install(root)


def _apply_overlay(program: Path, temp: Path) -> None:
    staged: dict[str, Path] = {}
    backups: dict[str, Path | None] = {}

    for local, (commit, remote, expected) in PAYLOADS.items():
        source = temp / f"payload_{Path(local).name}"
        source.write_bytes(_download(commit, remote, expected, "TURTO-2.2.24-runtime"))
        staged[local] = source

    try:
        for local, source in staged.items():
            target = program / local
            target.parent.mkdir(parents=True, exist_ok=True)
            saved = None
            if target.exists():
                saved = temp / f"backup_{Path(local).name}"
                shutil.copy2(target, saved)
            backups[local] = saved

            replacement = target.with_name(target.name + ".turto_new")
            shutil.copy2(source, replacement)
            os.replace(replacement, target)
    except Exception:
        for local in reversed(tuple(staged)):
            target = program / local
            saved = backups.get(local)
            try:
                if saved is not None and saved.exists():
                    restore = target.with_name(target.name + ".turto_restore")
                    shutil.copy2(saved, restore)
                    os.replace(restore, target)
                elif local in backups and target.exists():
                    target.unlink()
            except Exception:
                pass
        raise


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    program = root / "Program"

    # A marker alone is no longer sufficient. The critical runtime payloads
    # must also match their verified SHA-256 values.
    if _revision(program) and _payloads_match(program):
        return

    database = root / "actions.sqlite3"
    database_before = database.read_bytes() if database.is_file() else None

    with tempfile.TemporaryDirectory(prefix="turto_2224_") as temp_name:
        temp = Path(temp_name)

        # Ensures the complete historical runtime exists. Even if 2.2.23
        # itself considers its markers valid, the critical shear chain below
        # is overlaid again from pinned, hash-checked sources.
        _ensure_223_base(root, temp)
        program.mkdir(parents=True, exist_ok=True)
        _apply_overlay(program, temp)

        if not _payloads_match(program):
            raise RuntimeError(
                "Runtime 2.2.24 neodpovídá ověřeným kontrolním součtům."
            )

        current_marker = program / PROGRAM_REVISION
        current_marker.write_text("2.2.24", encoding="utf-8")
        for old_marker in program.glob(".turto_runtime_*.ok"):
            if old_marker != current_marker:
                old_marker.unlink(missing_ok=True)

    if database_before is not None and (
        not database.is_file() or database.read_bytes() != database_before
    ):
        raise RuntimeError("actions.sqlite3 se během instalace změnila.")


def selftest() -> None:
    assert RUNTIME_LAYOUT == "17"
    assert len(PAYLOADS) >= 7
    assert all(len(item[2]) == 64 for item in PAYLOADS.values())


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
