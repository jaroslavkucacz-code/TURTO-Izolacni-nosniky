from __future__ import annotations

import hashlib
import importlib.util
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
PATCH_URL = (
    "https://raw.githubusercontent.com/jaroslavkucacz-code/"
    "TURTO-Izolacni-nosniky/c066bcbfa0e53bb0b14af0e953f0a62204613028/"
    "tools/vykazy_reader/updates/0.13.4/update_0_13_3_to_0_13_4.py"
)
PATCH_SHA256 = "07e9344557d55b5c3cc3c3501b0eea94d9a7a8ace50b1a7f3bebf90a82930b22"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> bytes:
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}cb={datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TURTO-Vykazy-Recovery-v2",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def choose_root() -> Path:
    candidates: list[Path] = []
    if len(sys.argv) > 1:
        candidates.append(Path(sys.argv[1]))
    candidates.extend([Path.cwd(), Path(__file__).resolve().parent])
    for candidate in candidates:
        try:
            root = candidate.resolve()
            if (root / "app.py").exists() and (root / "VERSION.txt").exists():
                return root
        except Exception:
            pass

    import tkinter as tk
    from tkinter import filedialog

    tkroot = tk.Tk()
    tkroot.withdraw()
    folder = filedialog.askdirectory(
        title="Vyberte složku TURTO – Výkazy kladecích plánů (obsahuje app.py)"
    )
    tkroot.destroy()
    if not folder:
        raise RuntimeError("Nebyla vybrána složka programu.")
    root = Path(folder).resolve()
    if not (root / "app.py").exists() or not (root / "VERSION.txt").exists():
        raise RuntimeError("Ve vybrané složce nebyly nalezeny app.py a VERSION.txt.")
    return root


def notify(title: str, text: str, error: bool = False) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, text, parent=root)
        root.destroy()
    except Exception:
        print(text, file=sys.stderr if error else sys.stdout)


def normalize_source(data: bytes) -> bytes:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".recovery_tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def load_patch_module(payload: bytes):
    fd, temp_name = tempfile.mkstemp(prefix="turto_vykazy_patch_data_", suffix=".py")
    os.close(fd)
    temp = Path(temp_name)
    temp.write_bytes(payload)
    try:
        spec = importlib.util.spec_from_file_location("turto_vykazy_patch_0134_data", temp)
        if spec is None or spec.loader is None:
            raise RuntimeError("Nepodařilo se načíst data aktualizačního kroku.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        try:
            temp.unlink()
        except Exception:
            pass


def write_log(root: Path, lines: list[str]) -> Path:
    path = root / "TURTO_AKTUALIZACE_DIAGNOSTIKA.txt"
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass
    return path


def restart(root: Path) -> None:
    vbs = root / "SPUSTIT_BEZ_OKNA.vbs"
    bat = root / "SPUSTIT.bat"
    if os.name == "nt" and vbs.exists():
        subprocess.Popen(["wscript.exe", str(vbs)], cwd=str(root))
    elif os.name == "nt" and bat.exists():
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            cwd=str(root),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        subprocess.Popen([sys.executable, str(root / "app.py")], cwd=str(root))


def main() -> int:
    root = choose_root()
    app = root / "app.py"
    readme = root / "README.txt"
    version_file = root / "VERSION.txt"
    log: list[str] = [
        "TURTO – Výkazy kladecích plánů / oprava aktualizace 0.13.4 v2",
        f"Složka: {root}",
    ]

    current = version_file.read_text(encoding="utf-8-sig", errors="replace").strip()
    log.append(f"VERSION.txt: {current!r}")
    if current == TO_VERSION:
        notify("TURTO – Oprava aktualizace", "Verze 0.13.4 už je nainstalovaná.")
        return 0
    if current != FROM_VERSION:
        raise RuntimeError(f"Opravný krok očekává v{FROM_VERSION}, nalezena v{current or '?'}.")

    app_original = app.read_bytes()
    app_normalized = normalize_source(app_original)
    log.append(f"app.py SHA-256: {sha256(app_original)}")
    log.append(f"app.py SHA-256 po normalizaci: {sha256(app_normalized)}")
    try:
        app_text = app_normalized.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"app.py není platný UTF-8 soubor: {exc}") from exc

    if 'APP_VERSION = "0.13.3"' not in app_text:
        raise RuntimeError("V app.py nebyla nalezena deklarace APP_VERSION = 0.13.3.")
    if "TURTO – Výkazy kladecích plánů" not in app_text:
        raise RuntimeError("app.py neodpovídá programu TURTO – Výkazy kladecích plánů.")

    payload = download(PATCH_URL)
    actual_patch_sha = sha256(payload)
    log.append(f"Stažený patch SHA-256: {actual_patch_sha}")
    if actual_patch_sha != PATCH_SHA256:
        raise RuntimeError(
            "Nesouhlasí SHA-256 zdrojového patche. Aktualizace byla zastavena ještě před změnou souborů."
        )
    patch_module = load_patch_module(payload)
    patches = getattr(patch_module, "PATCHES", None)
    apply_line_patch = getattr(patch_module, "apply_line_patch", None)
    if not isinstance(patches, list) or not callable(apply_line_patch):
        raise RuntimeError("Stažený aktualizační krok nemá očekávanou strukturu.")

    by_path = {str(item.get("path")): item for item in patches if isinstance(item, dict)}
    app_spec = by_path.get("app.py")
    if not app_spec:
        raise RuntimeError("V aktualizačním kroku chybí změny app.py.")

    try:
        new_app = apply_line_patch(app_normalized, app_spec)
    except Exception as exc:
        log.append(f"Chyba segmentové kontroly app.py: {exc}")
        log_path = write_log(root, log)
        raise RuntimeError(
            f"Tvoje app.py se liší přímo v některém z míst, která má aktualizace změnit. "
            f"Diagnostika byla uložena do:\n{log_path}\n\nPodrobnost: {exc}"
        ) from exc

    try:
        new_app_text = new_app.decode("utf-8")
        compile(new_app_text, str(app), "exec")
    except Exception as exc:
        raise RuntimeError(f"Kontrola syntaxe aktualizovaného app.py selhala: {exc}") from exc
    if 'APP_VERSION = "0.13.4"' not in new_app_text:
        raise RuntimeError("Aktualizovaný app.py neobsahuje očekávanou verzi 0.13.4.")
    if "TURTO – Výkazy kladecích plánů" not in new_app_text:
        raise RuntimeError("Aktualizovaný app.py neobsahuje očekávaný název programu.")

    new_readme: bytes | None = None
    if readme.exists() and "README.txt" in by_path:
        readme_original = readme.read_bytes()
        readme_normalized = normalize_source(readme_original)
        log.append(f"README.txt SHA-256: {sha256(readme_original)}")
        try:
            new_readme = apply_line_patch(readme_normalized, by_path["README.txt"])
        except Exception as exc:
            # README is documentation only. Do not block the functional application update
            # if a local README was edited by the user.
            log.append(f"README.txt ponechán beze změny: {exc}")
            new_readme = None

    backup_root = root / ".update_backup" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_recovery_v2_0134"
    )
    backup_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(app, backup_root / "app.py")
    shutil.copy2(version_file, backup_root / "VERSION.txt")
    if readme.exists():
        shutil.copy2(readme, backup_root / "README.txt")
    log.append(f"Záloha: {backup_root}")

    try:
        atomic_write(app, new_app)
        if new_readme is not None:
            atomic_write(readme, new_readme)
        atomic_write(version_file, (TO_VERSION + "\n").encode("utf-8"))

        final_version = version_file.read_text(encoding="utf-8-sig", errors="replace").strip()
        final_app = app.read_text(encoding="utf-8", errors="strict")
        if final_version != TO_VERSION or 'APP_VERSION = "0.13.4"' not in final_app:
            raise RuntimeError("Závěrečná kontrola verze po zápisu selhala.")
    except Exception:
        try:
            shutil.copy2(backup_root / "app.py", app)
            shutil.copy2(backup_root / "VERSION.txt", version_file)
            if (backup_root / "README.txt").exists():
                shutil.copy2(backup_root / "README.txt", readme)
        finally:
            raise

    log.append(f"Výsledek app.py SHA-256: {sha256(app.read_bytes())}")
    log.append("Výsledek: OK, verze 0.13.4")
    write_log(root, log)

    notify(
        "TURTO – Oprava aktualizace",
        "Online aktualizace na v0.13.4 proběhla úspěšně.\n\n"
        "Databáze akcí ani archiv PDF nebyly měněny. Program se nyní znovu spustí.",
    )
    restart(root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        try:
            root = choose_root()
            log_path = root / "TURTO_AKTUALIZACE_DIAGNOSTIKA.txt"
            extra = f"\n\nDiagnostika: {log_path}" if log_path.exists() else ""
        except Exception:
            extra = ""
        notify(
            "TURTO – Chyba opravy",
            f"Oprava se nepodařila:\n\n{exc}{extra}",
            error=True,
        )
        raise SystemExit(1)
