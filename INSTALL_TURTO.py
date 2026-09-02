from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import urllib.request
import zipfile
from pathlib import Path

REPO = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
EXPECTED_SHA256 = "38640f4cff62be037c8711641c3dbbf68c6198e7744278c3ca61b0812d36a9bc"
TARGET_DIR = Path.home() / "Documents" / "TURTO-Izolacni-nosniky"
BLOB_SHAS = [
    "e3a1d7802bc294bfb7bbab3d68593ab08d61b6a2",
    "0f70ce13d3381fb86021337492e3c0a98de195ad",
    "b6b495113f98e370a0166b7a637564152aa7e2ad",
    "216b757215435bef95c4fcee42f4f0f68b8ebabe",
    "da7dbd30198fa4ba26253492328857ff7bdad899",
    "a490c145893364241c239294109b61a8ffd64bc4",
    "924aa5c66a672b0a0726edbf05dedd82b5f370dc",
    "7839acfdf4edfca22a32228be5a404ced8727614",
    "7d40322c3c809447c7e14c7a68d0afdabc88f1f3",
    "4a3b09c9b8b486e93dcb74f90cbb1961d09a0b08",
    "0931c9051d3a54f0ba7e247f3e5857f7dab9d644",
    "ed8980e832cdf30f25b3cb4f5002a99cb603e1bc",
    "b7a333876162bfacf765473208584399650b9a3e",
    "4733547d5607bf37c0fc3650e6f543a2dff48964",
    "735476dfa1da39c5b1e4f99e093cb52efaf37d5a",
    "3532b5293b4a8781f6a3e63a9bec19940008db02",
    "7d4cc0dc6e4242674487f42159cdca70f4b8b630",
    "ee38704ed4a92243a3387b2de93f7493e024fda8",
]


def pause_exit(message: str, code: int = 1) -> None:
    print(f"\nCHYBA: {message}")
    input("Stiskněte Enter pro ukončení...")
    raise SystemExit(code)


def download_blob(sha: str) -> str:
    url = f"https://api.github.com/repos/{REPO}/git/blobs/{sha}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TURTO-Installer/0.5.1",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data.get("sha") != sha or data.get("encoding") != "base64":
        raise RuntimeError(f"Neočekávaná odpověď GitHubu pro objekt {sha}")

    raw = base64.b64decode(data["content"])
    return raw.decode("ascii")


def safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    root = target.resolve()
    for member in archive.infolist():
        destination = (target / member.filename).resolve()
        if root != destination and root not in destination.parents:
            raise RuntimeError(f"Neplatná cesta v instalačním balíčku: {member.filename}")
    archive.extractall(target)


def main() -> None:
    print("TURTO – instalace z GitHubu")
    print("Stahuji ověřený instalační balíček 0.5.1...")

    chunks: list[str] = []
    total = len(BLOB_SHAS)
    for index, sha in enumerate(BLOB_SHAS, start=1):
        print(f"  část {index}/{total}")
        try:
            chunks.append(download_blob(sha))
        except Exception as exc:
            pause_exit(f"Nepodařilo se stáhnout instalační část {index}/{total}: {exc}")

    try:
        payload = base64.b64decode("".join(chunks), validate=True)
    except Exception as exc:
        pause_exit(f"Stažená instalační data nelze dekódovat: {exc}")

    digest = hashlib.sha256(payload).hexdigest()
    if digest.lower() != EXPECTED_SHA256.lower():
        pause_exit(
            "Kontrolní součet instalačního balíčku nesouhlasí.\n"
            f"Očekáváno: {EXPECTED_SHA256}\n"
            f"Nalezeno:   {digest}"
        )

    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            bad_file = archive.testzip()
            if bad_file:
                pause_exit(f"Poškozený soubor v instalačním ZIPu: {bad_file}")
            TARGET_DIR.mkdir(parents=True, exist_ok=True)
            safe_extract(archive, TARGET_DIR)
    except zipfile.BadZipFile:
        pause_exit("Stažená data netvoří platný instalační ZIP.")
    except Exception as exc:
        pause_exit(f"Program se nepodařilo rozbalit: {exc}")

    print(f"\nHotovo. Program je nainstalován v:\n{TARGET_DIR}")
    launcher = TARGET_DIR / "Spustit_program.vbs"
    if launcher.exists():
        try:
            os.startfile(str(launcher))
            print("Program spouštím...")
        except Exception as exc:
            print(f"Automatické spuštění se nepodařilo: {exc}")
            print("Spusťte ručně Spustit_program.vbs v cílové složce.")
    else:
        print("Spustit_program.vbs nebyl nalezen. Zkontrolujte cílovou složku.")

    input("\nStiskněte Enter pro ukončení instalátoru...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInstalace přerušena.")
        raise SystemExit(130)
