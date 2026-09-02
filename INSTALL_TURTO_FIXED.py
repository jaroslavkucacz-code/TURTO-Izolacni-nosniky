from __future__ import annotations

import base64
import binascii
import os
import struct
import urllib.request
import zlib
from pathlib import Path

REPO_RAW = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main"
VERSION = "0.5.1"
PARTS = 16
OUT_DIR = Path.home() / "Documents" / "TURTO-Izolacni-nosniky"

REQUIRED_FILES = {
    "app.pyw",
    "catalog_engine.py",
    "project_model.py",
    "project_ui.py",
    "updater.py",
    "update_helper.py",
    "Spustit_program.vbs",
}


def download_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "TURTO-Installer/0.5.1"},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read().decode("ascii").strip()


def safe_target(root: Path, name: str) -> Path:
    # ZIP cesty převádíme na bezpečné lokální cesty a blokujeme ../ únik.
    target = (root / Path(name)).resolve()
    root_resolved = root.resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise RuntimeError(f"Nebezpečná cesta v instalačním balíčku: {name}") from exc
    return target


def extract_complete_local_entries(data: bytes, root: Path) -> int:
    """Rozbalí všechny kompletní lokální ZIP záznamy z ověřené části balíčku.

    GitHub distribuce 0.5.1 záměrně nepřenáší nepovinný konec vývojového ZIPu
    (ukázkové soubory/dokumentaci). Všechny běhové soubory a katalogy jsou před
    tímto bodem a mají standardní ZIP local-file headers bez data descriptoru.
    """
    pos = 0
    extracted = 0
    local_sig = 0x04034B50

    while pos + 30 <= len(data):
        sig = struct.unpack_from("<I", data, pos)[0]
        if sig != local_sig:
            break

        (
            _sig,
            _ver,
            flags,
            method,
            _mtime,
            _mdate,
            crc_expected,
            compressed_size,
            uncompressed_size,
            name_len,
            extra_len,
        ) = struct.unpack_from("<IHHHHHIIIHH", data, pos)

        if flags & 0x08:
            raise RuntimeError("Instalační ZIP používá nepodporovaný data descriptor.")

        name_start = pos + 30
        name_end = name_start + name_len
        data_start = name_end + extra_len
        data_end = data_start + compressed_size

        # Poslední stažená část může končit uprostřed nepovinného souboru.
        if name_end > len(data) or data_start > len(data) or data_end > len(data):
            break

        encoding = "utf-8" if (flags & 0x0800) else "cp437"
        name = data[name_start:name_end].decode(encoding)
        target = safe_target(root, name)

        if name.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            compressed = data[data_start:data_end]
            if method == 0:
                raw = compressed
            elif method == 8:
                raw = zlib.decompress(compressed, -15)
            else:
                raise RuntimeError(f"Nepodporovaná ZIP komprese {method}: {name}")

            if len(raw) != uncompressed_size:
                raise RuntimeError(f"Nesouhlasí velikost souboru: {name}")
            crc_actual = binascii.crc32(raw) & 0xFFFFFFFF
            if crc_actual != crc_expected:
                raise RuntimeError(f"CRC kontrola selhala: {name}")

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            extracted += 1

        pos = data_end

    return extracted


def validate_install(root: Path) -> None:
    missing = sorted(name for name in REQUIRED_FILES if not (root / name).is_file())
    if missing:
        raise RuntimeError("Po instalaci chybí: " + ", ".join(missing))

    catalog_dir = root / "catalogs"
    catalogs = list(catalog_dir.glob("*.json")) + list(catalog_dir.glob("*.b64"))
    if not catalog_dir.is_dir() or not catalogs:
        raise RuntimeError("Po instalaci nebyla nalezena katalogová databáze.")


def main() -> None:
    print("TURTO - instalace z GitHubu")
    print(f"Stahuji opraveny instalacni balicek {VERSION}...")

    chunks: list[str] = []
    for i in range(1, PARTS + 1):
        print(f"  cast {i}/{PARTS}")
        url = f"{REPO_RAW}/package_parts/part_{i:03d}.txt"
        try:
            chunk = download_text(url)
        except Exception as exc:
            raise RuntimeError(
                f"Nepodarilo se stahnout instalacni cast {i}/{PARTS}: {exc}"
            ) from exc

        expected_len = 14000 if i == 1 else 20000
        if len(chunk) != expected_len:
            raise RuntimeError(
                f"Instalacni cast {i}/{PARTS} ma neocekavanou delku "
                f"{len(chunk)} (ocekavano {expected_len})."
            )
        chunks.append(chunk)

    try:
        partial_zip = base64.b64decode("".join(chunks), validate=True)
    except Exception as exc:
        raise RuntimeError("Instalacni data nejsou platna Base64 data.") from exc

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    extracted = extract_complete_local_entries(partial_zip, OUT_DIR)
    validate_install(OUT_DIR)

    print(f"\nInstalace dokoncena. Rozbaleno souboru: {extracted}")
    print(f"Program: {OUT_DIR}")

    launcher = OUT_DIR / "Spustit_program.vbs"
    if launcher.exists():
        try:
            os.startfile(str(launcher))
        except Exception:
            pass

    input("Stisknete Enter pro ukonceni instalatoru...")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nCHYBA: {exc}")
        input("Stisknete Enter pro ukonceni...")
        raise SystemExit(1)
