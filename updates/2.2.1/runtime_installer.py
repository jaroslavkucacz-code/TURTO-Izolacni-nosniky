from __future__ import annotations

"""TURTO 2.2.1 – aktuální instalační cesta runtime.

Instaluje ověřený kompatibilní základ 2.1.0 a potom přesně definované
současné vrstvy. Neprovádí žádné změny v actions.sqlite3.
"""

import hashlib
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
import tkinter as tk

REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
BASE_INSTALLER_COMMIT = "db23c1787e493f5dc4aa4fbf79282f45708f2bd8"
RUNTIME_LAYOUT = "2"
PAYLOADS = {
    "app_runtime.pyw": ("8378095160f5656b5310ba69d574b3075769334c", "updates/2.2.1/app_runtime.pyw", "0422a58a9545eaad766684869bd69e3c9b9711020847243a5793efb3d460a616"),
    "platform_workspace.py": ("8378095160f5656b5310ba69d574b3075769334c", "updates/2.2.1/platform_workspace.py", "e5f770c9efc567676f0d25bdf86c9c153a218d9d03ef2918dd7d6b7969d0ec95"),
    "shear_dowels_current.py": ("2f138cacf2d434c7b195311e05f1144f815a5e24", "updates/2.2.0/shear_dowels_current.py", "a37e244096660b5b827241c5f0eb2c8cd80a9f0b44f6c587d1711b0c05a065ce"),
    "schoeck_dorn_decoder.py": ("2f138cacf2d434c7b195311e05f1144f815a5e24", "updates/2.2.0/schoeck_dorn_decoder.py", "310fff1beda0eaf8c7d0c489facf9ddd5c5205219d3c2da0c1008c45a0c648b0"),
    "hit_workspace.py": ("44994a40b3d018269841c915b4742adae26acafa", "updates/2.1.3/hit_workspace.py", "79e4f24e58d0fed61f8b4481222593b7ec6d58599913525aa21fa5640e4841cb"),
    "hit_pdf.py": ("44994a40b3d018269841c915b4742adae26acafa", "updates/2.1.2/hit_pdf.py", "62909e7ecbcc5f56d7dca077cf95421cb1ee10931599433557abece32d629ea8"),
    "updater.py": ("2f138cacf2d434c7b195311e05f1144f815a5e24", "updates/2.1.3/updater.py", "57c66d4d3aacd3d8fcd007e32fb6a218023abd5f8e4044215b1056ca9538739d"),
    "shear_dowels_schedule.py": ("b198cbb7bf0720d694dfda5e9baf66c07d9bc23e", "updates/2.1.4/shear_dowels_schedule.py", "72ac97981f2d1952fc508ecb1b47fef21b7f45199259f72f40d5812eb2374cfa"),
    "shear_dowels_schedule_guard.py": ("b198cbb7bf0720d694dfda5e9baf66c07d9bc23e", "updates/2.1.4/shear_dowels_schedule_guard.py", "c9b09cdc563de7622a5fa900e15f056c6b5d25d281c5bbd47dfc27e387b7e786"),
    "shear_dowels_ui_214.py": ("b198cbb7bf0720d694dfda5e9baf66c07d9bc23e", "updates/2.1.4/shear_dowels_ui_214.py", "ece048d76888dbdb398ea9b6c67ef4bcb2765a0904987ae358cc59765a069813"),
    "shear_dowels_schedule_215.py": ("58f5bcd6b322b85446672270c5881630e89cd172", "updates/2.1.5/shear_dowels_schedule_215.py", "83553525a96dedd11484c63e52f81957441fc58abae0401fd256543c562e96f5"),
    "shear_dowels_ui_215.py": ("58f5bcd6b322b85446672270c5881630e89cd172", "updates/2.1.5/shear_dowels_ui_215.py", "e510f974ac9f98320e563424da924a00c5dd9868fa5c836338ea2fac136ae265"),
    "historical_schoeck_dorn.py": ("58f5bcd6b322b85446672270c5881630e89cd172", "updates/2.1.5/historical_schoeck_dorn.py", "b1e1b18903a0af04111829fe68d878a665a9cf5eef3ec57bba7c3dc334ab8e2c"),
}

OBSOLETE_FILES = (
    "app_runtime_210.pyw",
    "shear_dowels_catalog_210.py",
    "shear_dowels_ui_210.py",
    "legacy_schoeck_decoder.py",
)


def _raw_url(commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"


def _download(url: str, user_agent: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={
                    "User-Agent": user_agent,
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Stažený soubor je prázdný.")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout {url}\n{last}")


def _download_checked(commit: str, remote: str, expected_sha256: str, user_agent: str) -> bytes:
    data = _download(_raw_url(commit, remote), user_agent)
    actual = hashlib.sha256(data).hexdigest().lower()
    if actual != expected_sha256.lower():
        raise RuntimeError(
            f"Kontrolní součet nesouhlasí: {remote}\n"
            f"Očekáváno: {expected_sha256}\n"
            f"Staženo:    {actual}"
        )
    return data


def _install_verified_base(root: Path) -> None:
    url = _raw_url(BASE_INSTALLER_COMMIT, "updates/2.1.0/runtime_installer.py")
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_base_"))
    try:
        installer = temp_dir / "runtime_installer.py"
        installer.write_bytes(_download(url, "TURTO-2.2.1-base"))
        namespace = runpy.run_path(str(installer))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Kompatibilní instalační základ neobsahuje install_runtime().")
        install(root)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    _install_verified_base(root)

    temp_root = Path(tempfile.mkdtemp(prefix="turto_current_", dir=str(root)))
    window = tk.Tk()
    window.title("TURTO 2.2.1 – obnova runtime")
    window.geometry("720x205")
    window.resizable(False, False)
    window.configure(background="#F3F6F9")
    try:
        window.eval("tk::PlaceWindow . center")
    except Exception:
        pass

    tk.Label(
        window,
        text="Připravuji aktuální TURTO",
        font=("Calibri", 15, "bold"),
        bg="#F3F6F9",
        fg="#17324D",
    ).pack(anchor="w", padx=22, pady=(22, 8))
    status = tk.Label(
        window,
        text="Obnovuji současné programové vrstvy…",
        font=("Calibri", 10),
        bg="#F3F6F9",
        fg="#172230",
    )
    status.pack(anchor="w", padx=22)
    counter = tk.Label(
        window,
        text="",
        font=("Calibri", 9),
        bg="#F3F6F9",
        fg="#5C6878",
    )
    counter.pack(anchor="w", padx=22, pady=(8, 0))
    window.update()

    downloaded: list[tuple[Path, Path]] = []
    try:
        for index, (local, (commit, remote, expected)) in enumerate(PAYLOADS.items(), 1):
            status.configure(text=f"Stahuji: {local}")
            counter.configure(text=f"{index} / {len(PAYLOADS)}")
            window.update()
            source = temp_root / local
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(
                _download_checked(commit, remote, expected, "TURTO-2.2.1-runtime")
            )
            downloaded.append((source, root / local))

        status.configure(text="Instaluji ověřené programové soubory…")
        window.update()
        for source, target in downloaded:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)

        for obsolete in OBSOLETE_FILES:
            try:
                (root / obsolete).unlink(missing_ok=True)
            except Exception:
                pass
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        shutil.rmtree(temp_root, ignore_errors=True)
