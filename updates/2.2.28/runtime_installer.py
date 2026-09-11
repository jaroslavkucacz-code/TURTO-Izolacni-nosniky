from __future__ import annotations

"""TURTO 2.2.28 – Peikko EBEA/TEBEA identification overlay; actions.sqlite3 is never modified."""

import hashlib
import json
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "8cc60a18a525558ae876ac68875dfb4f8d27fec9"
BASE_PATH = "updates/2.2.27/runtime_installer.py"
BASE_GIT_BLOB_SHA1 = "0bdc5bb6aab85559e8acf759258a5cdcc171780a"

PAYLOAD_COMMIT = "cb8784cf5e20845c607634ea538e683c2a5bd884"
PAYLOADS = {
    "app_runtime.pyw": (
        "updates/2.2.28/app_runtime.pyw",
        "a7920f4c0b1dd33f6ac9275b6f229a72fe5e28fe5ee21e5d6ae4be59b2796d4b",
    ),
    "peikko_connectors.py": (
        "updates/2.2.28/peikko_connectors.py",
        "f37361ed1ab3ea3467de70b7b6a67ecf6e72536c00b9c9713c73a0911fea4044",
    ),
}

RUNTIME_LAYOUT = "21"
PROGRAM_REVISION = ".turto_runtime_2_2_28.ok"
PEIKKO_CATALOG_NAME = "peikko_ebea_tebea_identification.json"

PREVIOUS_REQUIRED = (
    "app_runtime.pyw",
    "app_runtime_221.pyw",
    "substitution_workspace.py",
    "catalog_engine.py",
    "runtime_paths.py",
    "platform_workspace.py",
    "hit_workspace.py",
    "shear_dowels_current.py",
)
CURRENT_REQUIRED = PREVIOUS_REQUIRED + ("app_runtime_227.pyw", "peikko_connectors.py")


def _raw(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def _request_bytes(commit: str, path: str, agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                _raw(commit, path) + f"?turto={time.time_ns()}_{attempt}",
                headers={
                    "User-Agent": agent,
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if not data:
                raise RuntimeError(f"Stažen prázdný soubor: {path}")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout {path}\n{last}")


def _git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _download_base(temp: Path) -> Path:
    data = _request_bytes(BASE_COMMIT, BASE_PATH, "TURTO-2.2.28-base")
    actual = _git_blob_sha1(data)
    if actual.lower() != BASE_GIT_BLOB_SHA1.lower():
        raise RuntimeError(
            f"Kontrolní součet installeru 2.2.27 nesouhlasí.\n"
            f"Očekáváno: {BASE_GIT_BLOB_SHA1}\nStaženo: {actual}"
        )
    target = temp / "runtime_227.py"
    target.write_bytes(data)
    return target


def _download_payload(path: str, expected_sha256: str, temp: Path) -> Path:
    data = _request_bytes(PAYLOAD_COMMIT, path, "TURTO-2.2.28-runtime")
    actual = hashlib.sha256(data).hexdigest().lower()
    if actual != expected_sha256.lower():
        raise RuntimeError(
            f"Kontrolní součet nesouhlasí: {path}\n"
            f"Očekáváno: {expected_sha256}\nStaženo: {actual}"
        )
    target = temp / ("payload_" + Path(path).name)
    target.write_bytes(data)
    return target


def _complete(program: Path) -> bool:
    return program.is_dir() and all((program / name).is_file() for name in CURRENT_REQUIRED)


def _payloads_match(program: Path) -> bool:
    try:
        for local, (_remote, expected) in PAYLOADS.items():
            path = program / local
            if not path.is_file():
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest().lower() != expected.lower():
                return False
        return True
    except Exception:
        return False


def _catalog_valid(program: Path) -> bool:
    path = program / "catalogs" / PEIKKO_CATALOG_NAME
    try:
        if not path.is_file():
            return False
        package = json.loads(path.read_text(encoding="utf-8"))
        return (
            int(package.get("schema_version", 0)) == 2
            and str(package.get("catalog", {}).get("id", "")) == "peikko_ebea_tebea_identification_2026_09"
            and len(package.get("families", [])) == 33
            and all(f.get("verified_capacity") is False for f in package.get("families", []))
        )
    except Exception:
        return False


def _revision_ok(program: Path) -> bool:
    try:
        marker = program / PROGRAM_REVISION
        return (
            marker.is_file()
            and marker.read_text(encoding="utf-8").strip() == "2.2.28"
            and _complete(program)
            and _payloads_match(program)
            and _catalog_valid(program)
        )
    except Exception:
        return False


def _install_base(root: Path, temp: Path) -> None:
    installer = _download_base(temp)
    namespace = runpy.run_path(str(installer))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Installer 2.2.27 neobsahuje install_runtime().")
    install(root)
    program = root / "Program"
    if not program.is_dir() or not all((program / name).is_file() for name in PREVIOUS_REQUIRED):
        raise RuntimeError("Ověřený runtime 2.2.27 se nepodařilo obnovit kompletně.")


def _atomic_replace(source: Path, target: Path, temp: Path, backups: list[tuple[Path, Path | None]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if target.exists():
        backup = temp / ("backup_" + target.name + f"_{len(backups)}")
        shutil.copy2(target, backup)
    backups.append((target, backup))
    staged = target.with_name(target.name + ".turto_new")
    shutil.copy2(source, staged)
    os.replace(staged, target)


def _restore(backups: list[tuple[Path, Path | None]]) -> None:
    for target, backup in reversed(backups):
        try:
            if backup is None:
                target.unlink(missing_ok=True)
            elif backup.exists():
                staged = target.with_name(target.name + ".turto_restore")
                shutil.copy2(backup, staged)
                os.replace(staged, target)
        except Exception:
            pass


def _write_peikko_catalog(program: Path, temp: Path, backups: list[tuple[Path, Path | None]]) -> None:
    namespace = runpy.run_path(str(program / "peikko_connectors.py"))
    builder = namespace.get("build_catalog_package")
    selftest = namespace.get("selftest")
    if not callable(builder) or not callable(selftest):
        raise RuntimeError("Peikko dekodér neobsahuje očekávané rozhraní.")
    selftest()
    package = builder()
    if (
        int(package.get("schema_version", 0)) != 2
        or len(package.get("families", [])) != 33
        or any(f.get("verified_capacity") is not False for f in package.get("families", []))
    ):
        raise RuntimeError("Peikko katalog neprošel bezpečnostní kontrolou.")
    source = temp / PEIKKO_CATALOG_NAME
    source.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _atomic_replace(source, program / "catalogs" / PEIKKO_CATALOG_NAME, temp, backups)


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    program = root / "Program"
    if _revision_ok(program):
        return

    database = root / "actions.sqlite3"
    database_before = database.read_bytes() if database.is_file() else None

    with tempfile.TemporaryDirectory(prefix="turto_2228_") as temp_name:
        temp = Path(temp_name)
        _install_base(root, temp)
        program.mkdir(parents=True, exist_ok=True)

        backups: list[tuple[Path, Path | None]] = []
        try:
            base_runtime = program / "app_runtime.pyw"
            base_alias_source = temp / "app_runtime_227.pyw"
            shutil.copy2(base_runtime, base_alias_source)
            _atomic_replace(base_alias_source, program / "app_runtime_227.pyw", temp, backups)

            for local in ("peikko_connectors.py", "app_runtime.pyw"):
                remote, expected = PAYLOADS[local]
                source = _download_payload(remote, expected, temp)
                _atomic_replace(source, program / local, temp, backups)

            _write_peikko_catalog(program, temp, backups)

            if not _complete(program):
                raise RuntimeError("Runtime 2.2.28 není po aktualizaci kompletní.")
            if not _payloads_match(program):
                raise RuntimeError("Kontrola payloadů 2.2.28 po instalaci selhala.")
            if not _catalog_valid(program):
                raise RuntimeError("Peikko identifikační katalog po instalaci není platný.")

            marker = program / PROGRAM_REVISION
            marker.write_text("2.2.28", encoding="utf-8")
            for old in program.glob(".turto_runtime_*.ok"):
                if old != marker:
                    old.unlink(missing_ok=True)
        except Exception:
            _restore(backups)
            raise

    if database_before is not None:
        if not database.is_file() or database.read_bytes() != database_before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")


def selftest() -> None:
    assert RUNTIME_LAYOUT == "21"
    assert len(PAYLOADS) == 2
    assert len(BASE_GIT_BLOB_SHA1) == 40
    assert all(len(spec[1]) == 64 for spec in PAYLOADS.values())
    assert "app_runtime_227.pyw" in CURRENT_REQUIRED
    assert "peikko_connectors.py" in CURRENT_REQUIRED


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
