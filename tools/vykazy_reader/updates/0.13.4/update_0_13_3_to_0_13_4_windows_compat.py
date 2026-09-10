from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.3"
TO_VERSION = "0.13.4"
CANONICAL_PATCH_URL = (
    "https://raw.githubusercontent.com/jaroslavkucacz-code/"
    "TURTO-Izolacni-nosniky/c066bcbfa0e53bb0b14af0e953f0a62204613028/"
    "tools/vykazy_reader/updates/0.13.4/update_0_13_3_to_0_13_4.py"
)
CANONICAL_PATCH_SHA256 = "07e9344557d55b5c3cc3c3501b0eea94d9a7a8ace50b1a7f3bebf90a82930b22"
EXPECTED_LF_SHA256 = {
    "app.py": "c4698dcd7f2548815e9474ed349cf21a03e97bf5487f8a9ba6e055d71a797d1d",
    "README.txt": "51e2141a20518bf020aa362e55607e332b3221fc13c480a6c3e7c9996ea04f6d",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_newlines(data: bytes) -> bytes:
    # v0.13.3 was a text-mode rename patch. On Windows it can legitimately
    # rewrite LF source files as CRLF. Normalizing CRLF back to LF restores
    # the exact canonical v0.13.3 content without changing Python semantics.
    return data.replace(b"\r\n", b"\n")


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "TURTO-Vykazy-Update-Compat"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".compat_tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    version_file = root / "VERSION.txt"
    app = root / "app.py"
    readme = root / "README.txt"

    if not app.exists():
        raise RuntimeError("Ve zvolené složce nebyl nalezen app.py.")

    current = (
        version_file.read_text(encoding="utf-8-sig", errors="replace").strip()
        if version_file.exists()
        else ""
    )
    if current == TO_VERSION:
        return 0
    if current != FROM_VERSION:
        raise RuntimeError(f"Tento krok očekává v{FROM_VERSION}, nalezena v{current or '?'}.")

    # Verify that the mismatch is ONLY Windows newline conversion. If any
    # actual source content is different, stop instead of overwriting it.
    normalized: dict[Path, bytes] = {}
    for name, expected in EXPECTED_LF_SHA256.items():
        path = root / name
        if not path.exists():
            if name == "README.txt":
                continue
            raise RuntimeError(f"Chybí soubor {name}.")
        original = path.read_bytes()
        lf_data = normalize_newlines(original)
        if sha256(lf_data) != expected:
            raise RuntimeError(
                f"Soubor {name} se neliší pouze konci řádků Windows; "
                "aktualizace jej z bezpečnostních důvodů nepřepíše."
            )
        normalized[path] = lf_data

    backup_root = root / ".update_backup" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_windows_compat_0134"
    )
    backups: list[tuple[Path, Path | None]] = []
    targets = [app, version_file] + ([readme] if readme.exists() else [])

    patch_path: Path | None = None
    try:
        for target in targets:
            backup = None
            if target.exists():
                backup = backup_root / target.relative_to(root)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            backups.append((target, backup))

        # Canonicalize only files proven byte-for-byte equal after CRLF -> LF.
        for path, lf_data in normalized.items():
            if path.read_bytes() != lf_data:
                atomic_write(path, lf_data)

        payload = download(CANONICAL_PATCH_URL)
        if sha256(payload) != CANONICAL_PATCH_SHA256:
            raise RuntimeError("Nesouhlasí SHA-256 kanonického aktualizačního kroku v0.13.4.")

        fd, temp_name = tempfile.mkstemp(prefix="turto_vykazy_0134_", suffix=".py")
        os.close(fd)
        patch_path = Path(temp_name)
        patch_path.write_bytes(payload)

        proc = subprocess.run(
            [sys.executable, str(patch_path), str(root)],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "neznámá chyba").strip()
            raise RuntimeError(detail)

        final = version_file.read_text(encoding="utf-8-sig", errors="replace").strip()
        if final != TO_VERSION:
            raise RuntimeError("Aktualizační krok nezapsal očekávanou verzi v0.13.4.")
        return 0
    except Exception:
        for target, backup in reversed(backups):
            try:
                if backup is not None and backup.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, target)
                elif backup is None and target.exists():
                    target.unlink()
            except Exception:
                pass
        raise
    finally:
        if patch_path is not None:
            try:
                patch_path.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
