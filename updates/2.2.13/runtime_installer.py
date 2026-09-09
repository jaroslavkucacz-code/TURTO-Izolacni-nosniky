from __future__ import annotations

"""TURTO 2.2.13 verified Program\ runtime installer; actions.sqlite3 is never modified."""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_COMMIT = "b74b8f31bd327da72120f3087ff3066b629846c9"
BASE_PATH = "updates/2.2.12/runtime_installer.py"
BASE_SHA256 = "929ae15466c136ee2da503df257a76f01edd52332164bde107f17770c0a70cf6"
RUNTIME_LAYOUT = "6"

PAYLOADS = {
    "runtime_paths.py": (
        "6fa3dca596112b71f77c7b45da1380beca9b259f",
        "updates/2.2.13/runtime_paths.py",
        "d25f98aeed24d866cf6b9f8ed63833d45e65252cf070f06600a91e61ec0e025a",
    ),
    "updater.py": (
        "ecea6f3954b9fc61701e118840472d3841434b65",
        "updates/2.2.13/updater.py",
        "66f92731447afd2ce0dca0970838e7e194ecfbbe40af0be6bd18e3b7f36c87ed",
    ),
    "catalog_browser.py": (
        "045395211a8984d17ac582fe8b7d9b7be639712e",
        "updates/2.2.13/catalog_browser.py",
        "ecb8df57d2f8e1e52f32d15605a920ac13a6506d04dce694b0715ab43690aa0f",
    ),
    "cleanup_stage3.py": (
        "8fc73a226ba001b3bfdde716ea6d4a24ca003bc1",
        "updates/2.2.13/cleanup_stage3.py",
        "12457a142f4a6421eef08e9e4f67ab2c7cec72f290ead57d16f25047be15a84c",
    ),
    "app_runtime.pyw": (
        "43d9acb1b5db4b89aa757fbf52773cbc4d810f0e",
        "updates/2.2.13/app_runtime.pyw",
        "c22ae956c3691a3b15bebf69f97f2f65d8489aadc0f4fa1f028739d43eacc159",
    ),
}

REQUIRED_PROGRAM_FILES = (
    "app_runtime.pyw",
    "app_runtime_202.pyw",
    "app_runtime_200.pyw",
    "app_runtime_127.pyw",
    "app_base.py",
    "platform_workspace.py",
    "action_store.py",
    "catalog_browser.py",
    "catalog_browser_2210.py",
    "runtime_paths.py",
    "updater.py",
    "cleanup_stage3.py",
    "hit_workspace.py",
    "hit_pdf.py",
    "shear_movement.py",
    "shear_dowels_current.py",
)


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


def _verify_program(program: Path) -> None:
    missing = [name for name in REQUIRED_PROGRAM_FILES if not (program / name).is_file()]
    if missing:
        raise RuntimeError("Program runtime není kompletní: " + ", ".join(missing))


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    program = root / "Program"
    work = Path(tempfile.mkdtemp(prefix=".turto_2213_", dir=str(root)))
    staging = work / "Program"
    staging.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None

    try:
        base = work / "base_installer.py"
        base.write_bytes(
            _download(BASE_COMMIT, BASE_PATH, BASE_SHA256, "TURTO-2.2.13-base")
        )
        namespace = runpy.run_path(str(base))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Předchozí ověřený installer neobsahuje install_runtime().")

        # Rebuild the full historical dependency chain inside Program, never in the root.
        install(staging)

        # Preserve the verified 2.2.10 implementation behind the 2.2.13 root-path shim.
        legacy_catalog = staging / "catalog_browser.py"
        if not legacy_catalog.is_file():
            raise RuntimeError("Základ runtime neobsahuje catalog_browser.py.")
        shutil.copy2(legacy_catalog, staging / "catalog_browser_2210.py")

        for local, (commit, remote, expected) in PAYLOADS.items():
            destination = staging / local
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(
                _download(commit, remote, expected, "TURTO-2.2.13-runtime")
            )

        _verify_program(staging)

        # Only after the complete staging tree is verified do we replace Program.
        if program.exists():
            backup_root = root / "Zaloha"
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            backup = backup_root / f"Program_pred_2.2.13_{stamp}"
            suffix = 2
            while backup.exists():
                backup = backup_root / f"Program_pred_2.2.13_{stamp}_{suffix}"
                suffix += 1
            shutil.move(str(program), str(backup))

        try:
            os.replace(staging, program)
        except Exception:
            if backup is not None and backup.exists() and not program.exists():
                shutil.move(str(backup), str(program))
            raise

        _verify_program(program)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    install_runtime(Path(__file__).resolve().parent)
