from __future__ import annotations

import base64
import hashlib
import os
import shutil
import sys
import zlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

TARGET_VERSION = "0.5.1"
HERE = Path(__file__).resolve().parent
PAYLOAD_DIR = HERE / "upgrade_v040"
REQUIRED_OLD = ["app.pyw", "catalog_engine.py", "project_ui.py", "project_model.py", "Spustit_program.vbs"]
FILES = {
    "app.pyw": "f53a2d3259362689886256d5d2a18ca70fe0fa0101eec92d74136cf3614e1d82",
    "catalog_engine.py": "10d39bfa5fd71807a1b5e0b54ba7e0832bb42fb56da0634cd5de29052cd33dab",
    "project_ui.py": "a643de1b706ae0616e4c953237b849164862d5e2009a37a5261bdd34d3138b4a",
    "autocomplete.py": "49212e2fe6f9e61e1f19d6d972d08c7e1d4d5cc0632b649af62f29b7d1fa274b",
    "updater.py": "a1ac4e1b5c4a4604f7af22854b0cc96d3d7d503fe11f8379468b9542b1c59344",
}
PAYLOAD_PARTS = {
    "app.pyw": [
        "app.pyw.part01.txt",
        "app.pyw.part02.txt",
        "app.pyw.part03.txt",
        "app.pyw.part04.txt",
    ],
    "catalog_engine.py": [
        "catalog_engine.py.part01.txt",
        "catalog_engine.py.part02.txt",
    ],
}
VERSION_BYTES = b"0.5.1\n"


def is_valid_folder(path: Path) -> bool:
    return path.is_dir() and all((path / name).exists() for name in REQUIRED_OLD) and (path / "catalogs").is_dir()


def choose_folder() -> Path | None:
    if len(sys.argv) > 1:
        p = Path(sys.argv[1]).expanduser()
        if is_valid_folder(p):
            return p

    guesses = [
        HERE / "TURTO_Izolacni_nosniky_v0.4.0",
        HERE.parent / "TURTO_Izolacni_nosniky_v0.4.0",
        Path.home() / "Documents" / "TURTO_Izolacni_nosniky_v0.4.0",
        Path.home() / "Downloads" / "TURTO_Izolacni_nosniky_v0.4.0",
    ]
    for guess in guesses:
        if is_valid_folder(guess):
            return guess

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(
        title="Vyberte složku TURTO_Izolacni_nosniky_v0.4.0",
        initialdir=str(Path.home()),
        mustexist=True,
    )
    root.destroy()
    return Path(selected) if selected else None


def payload_text(name: str) -> str:
    if name in PAYLOAD_PARTS:
        pieces: list[str] = []
        for rel in PAYLOAD_PARTS[name]:
            src = PAYLOAD_DIR / rel
            if not src.is_file():
                raise RuntimeError(f"V instalačním ZIPu chybí {src.relative_to(HERE)}")
            pieces.append(src.read_text(encoding="ascii").strip())
        return "".join(pieces)

    src = PAYLOAD_DIR / f"{name}.zlib.b64"
    if not src.is_file():
        raise RuntimeError(f"V instalačním ZIPu chybí {src.relative_to(HERE)}")
    return src.read_text(encoding="ascii").strip()


def decode_payload(name: str) -> bytes:
    compressed = base64.b64decode(payload_text(name), validate=True)
    data = zlib.decompress(compressed)
    digest = hashlib.sha256(data).hexdigest()
    if digest != FILES[name]:
        raise RuntimeError(f"Kontrolní součet nesouhlasí: {name}")
    return data


def main() -> int:
    print("TURTO - převod v0.4.0 na GitHub verzi v0.5.1")
    print("Tento krok nestahuje instalační data z internetu.")
    print("Použije vaše existující katalogy Schöck + ISOPRO z v0.4.0.\n")

    target = choose_folder()
    if target is None:
        print("Nebyla vybrána žádná složka.")
        return 1
    target = target.resolve()
    if not is_valid_folder(target):
        print("CHYBA: Vybraná složka nevypadá jako TURTO v0.4.0:")
        print(target)
        input("Stiskněte Enter pro ukončení...")
        return 1

    catalogs = list((target / "catalogs").glob("*.json")) + list((target / "catalogs").glob("*.json.gz.b64"))
    if not catalogs:
        print("CHYBA: Ve složce catalogs nejsou katalogová data.")
        input("Stiskněte Enter pro ukončení...")
        return 1

    print("Ověřuji instalační data...")
    try:
        decoded = {name: decode_payload(name) for name in FILES}
        decoded["version.txt"] = VERSION_BYTES
    except Exception as exc:
        print("CHYBA: Instalační ZIP není kompletní nebo je poškozený:", exc)
        print("Stáhněte repozitář znovu přes Code -> Download ZIP.")
        input("Stiskněte Enter pro ukončení...")
        return 1

    backup = target / ".backup_pred_github_v0.5.1"
    backup.mkdir(exist_ok=True)
    print(f"Aktualizuji: {target}")
    print(f"Záloha změněných souborů: {backup}")

    try:
        for rel, data in decoded.items():
            dst = target / rel
            if dst.exists():
                b = backup / rel
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, b)
            tmp = dst.with_name(dst.name + ".new")
            tmp.write_bytes(data)
            os.replace(tmp, dst)
            print(f"  OK  {rel}")

        catalogs_after = list((target / "catalogs").glob("*.json")) + list((target / "catalogs").glob("*.json.gz.b64"))
        if len(catalogs_after) < len(catalogs):
            raise RuntimeError("Po aktualizaci chybí některá katalogová data.")
        (target / "GITHUB_REPO.txt").write_text(
            "https://github.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky\n", encoding="utf-8"
        )
    except Exception as exc:
        print("\nCHYBA při aktualizaci:", exc)
        print("Záloha je v:", backup)
        input("Stiskněte Enter pro ukončení...")
        return 1

    print("\nHOTOVO. TURTO je ve verzi 0.5.1.")
    print("Katalogy Schöck a ISOPRO zůstaly zachované.")
    print("Další verze už půjdou přes tlačítko Aktualizace v programu.")
    launcher = target / "Spustit_program.vbs"
    try:
        os.startfile(str(launcher))
        print("Program spouštím...")
    except Exception as exc:
        print("Automatické spuštění se nepodařilo:", exc)
        print("Spusťte ručně:", launcher)
    input("\nStiskněte Enter pro ukončení tohoto okna...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
