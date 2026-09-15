from __future__ import annotations

"""TURTO 3.0.1: verified incremental ISO/logo delivery; customer data is read-only."""
import hashlib
import os
from pathlib import Path
import runpy
import tempfile
import time
import urllib.request

VERSION = "3.0.1"
RUNTIME_LAYOUT = "32"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "00fce83b4abd9912dbf26c113b798c6670fa9241"
BASE_PATH = "updates/2.2.46/runtime_installer.py"
BASE_SHA256 = "9c9a435923c0cb4514dedeaaf06a10fb743c3b4201ed999d36b63ee617b2bad2"
MARKER = ".turto_runtime_3_0_1.ok"

PAYLOADS = {
    "app_runtime.pyw": ("e2a04fb52d2f344942e00686206bd4faad7d66be", "updates/3.0.1/app_runtime.pyw", "c47e68e78fc3a4a8397fdb652e54f8e235e17804eea9e109784694cb01003304"),
    "branding_301.py": ("e2a04fb52d2f344942e00686206bd4faad7d66be", "updates/3.0.1/branding_301.py", "c811082110b17c3ad817c10ae583d70695b22520a0fff9051ab494ebae95e4ce"),
    "iso_bulk_301.py": ("e2a04fb52d2f344942e00686206bd4faad7d66be", "updates/3.0.1/iso_bulk_301.py", "eff6e5b0b6c7cfbed756ca4b2109d895f8cb565b7f39e1935a252627b3f1d192"),
    "turto_icon_301.png.b64": ("0f7e5c11bd09c843ff105eb10a9b1b64fd168117", "updates/3.0.1/turto_icon_301.png.b64", "d98c9ae427a9837b038bc3b9352fd13c3e563a98d4e85ff4529fdc7f7d7ed11d"),
    "app_runtime_246.pyw": ("1c1427a1695f529db0d720d576cbd3c0556a12a7", "updates/2.2.46/app_runtime.pyw", "f9b7647b35b6d33d1aad7222eda0dd6573cb6ce882f942a71645f90a8ae3a5b9"),
    "bulk_import_engine.py": ("d20446e502a87aed46326d810ca000ce1d69cd5c", "updates/1.1.17/bulk_import_engine.py", "6b30a9ee4d1e3533799c079d94313cccdf9a067b40bd069e222da170140150f7"),
    "bulk_import.py": ("d20446e502a87aed46326d810ca000ce1d69cd5c", "updates/1.1.17/bulk_import.py", "db5977f431867ca2871abf59e538d68b8059000f880d11cae1b6af9bb6e7ad16"),
    "catalog_engine.py": ("d20446e502a87aed46326d810ca000ce1d69cd5c", "updates/1.1.17/catalog_engine.py", "6ef19641918d507791e3e50ce6abf7394769c8ce0c97be3c63239ca9ed5f5b1c"),
    "runtime_paths.py": ("d20446e502a87aed46326d810ca000ce1d69cd5c", "updates/2.2.13/runtime_paths.py", "d25f98aeed24d866cf6b9f8ed63833d45e65252cf070f06600a91e61ec0e025a"),
    "isokorb_xt_parser_243.py": ("d20446e502a87aed46326d810ca000ce1d69cd5c", "updates/2.2.43/isokorb_xt_parser_243.py", "680f6853fbb62234a440c2a43e8d1b4f0b03e0df2b4d69c4b84b6b52a2a28352"),
    "isokorb_xt_resolver_245.py": ("e7eaa0dbe2b258f4e2f6d59b635ecc7393679bb5", "updates/2.2.45/isokorb_xt_resolver_245.py", "e0a633936c4d901aa9fa88f89b50fa85e55e6eea80a43b2235a743117144dda7"),
    "isokorb_xt_resolver_246.py": ("da091c489678cf8da745190785a9988757072d7a", "updates/2.2.46/isokorb_xt_resolver_246.py", "3b7407cfc3affd947fd9995a48278e3e97b194d6073111b44eb192e375941218"),
}
BASE_REQUIRED = (
    "app_base.py", "app_runtime_244.pyw", "app_runtime_243.pyw", "app_runtime_242.pyw",
    "project_ui.py", "project_model.py", "hit_workspace.py", "platform_workspace.py",
    "action_workspace.py", "action_store.py", "action_payload.py", "updater.py",
)


def _digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def _revision_ok(program: Path) -> bool:
    try:
        return (all((program / n).is_file() for n in BASE_REQUIRED)
                and (program / MARKER).read_text(encoding="utf-8").strip() == VERSION
                and all(_digest(program / n) == v[2] for n, v in PAYLOADS.items()))
    except (OSError, ValueError):
        return False


def _download(commit: str, path: str, expected: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url + f"?turto={time.time_ns()}", headers={
                "User-Agent": "TURTO-3.0.1-runtime", "Cache-Control": "no-cache, no-store"})
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError(f"Nesouhlasí SHA-256 souboru {path}.")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(attempt + 1)
    raise RuntimeError(f"Nelze stáhnout ověřený soubor {path}: {last}")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".turto_301_", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def install_runtime(root: Path | str) -> Path:
    root = Path(root).resolve()
    program = root / "Program"
    if _revision_ok(program):
        return program / "app_runtime.pyw"
    database = root / "actions.sqlite3"
    before = _digest(database)
    # Stage and verify every payload before changing the existing application.
    payload = {name: _download(*pin) for name, pin in PAYLOADS.items()
               if _digest(program / name) != pin[2]}
    if not all((program / n).is_file() for n in BASE_REQUIRED):
        with tempfile.TemporaryDirectory(prefix="turto_301_base_") as folder:
            path = Path(folder) / "installer.py"
            path.write_bytes(_download(BASE_COMMIT, BASE_PATH, BASE_SHA256))
            runpy.run_path(str(path))["install_runtime"](root)
        # The base installer may have replaced files staged as already current.
        payload.update({n: _download(*p) for n, p in PAYLOADS.items()
                        if n not in payload and _digest(program / n) != p[2]})
    if not all((program / n).is_file() for n in BASE_REQUIRED):
        raise RuntimeError("Nepodařilo se obnovit úplný runtime základ TURTO.")
    targets = [program / n for n in payload] + [program / MARKER]
    backups = {p: p.read_bytes() if p.is_file() else None for p in targets}
    try:
        for name, data in payload.items():
            _atomic_write(program / name, data)
        # Fail visibly for a corrupted logo instead of silently ignoring it.
        ns = runpy.run_path(str(program / "branding_301.py"))
        ns["logo_bytes"]()
        if _digest(database) != before:
            raise RuntimeError("actions.sqlite3 se během instalace změnila.")
        _atomic_write(program / MARKER, VERSION.encode("utf-8"))
        if not _revision_ok(program):
            raise RuntimeError("Runtime TURTO 3.0.1 neprošel závěrečnou kontrolou.")
    except Exception:
        for target in reversed(targets):
            data = backups[target]
            if data is None:
                target.unlink(missing_ok=True)
            else:
                _atomic_write(target, data)
        raise
    return program / "app_runtime.pyw"


def selftest() -> None:
    assert VERSION == "3.0.1" and RUNTIME_LAYOUT == "32"
    assert len(BASE_COMMIT) == 40 and len(BASE_SHA256) == 64
    assert "actions.sqlite3" not in PAYLOADS
    assert all(Path(n).name == n and len(p[0]) == 40 and len(p[2]) == 64 for n, p in PAYLOADS.items())


if __name__ == "__main__":
    selftest()
