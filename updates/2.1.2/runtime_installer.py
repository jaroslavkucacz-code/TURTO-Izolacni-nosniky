from __future__ import annotations

"""Pinned installer for TURTO 2.1.2 startup hotfix.

Reinstalls the verified 2.1.0 runtime and overlays only the startup-safe
historical Schöck decoder patch. No AKCE database is modified.
"""

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
RUNTIME_COMMIT = "2a0428af98b064770fffe84d430dee3388a1bfb9"

OVERLAY = {
    "app_runtime.pyw": "updates/2.1.2/app_runtime.pyw",
    "legacy_schoeck_decoder.py": "updates/2.1.2/legacy_schoeck_decoder.py",
}


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


def _install_verified_base(root: Path) -> None:
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/{BASE_INSTALLER_COMMIT}/"
        "updates/2.1.0/runtime_installer.py"
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_210_base_"))
    try:
        installer = temp_dir / "runtime_installer.py"
        installer.write_bytes(_download(url, "TURTO-2.1.2-base"))
        namespace = runpy.run_path(str(installer))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Ověřený instalační modul 2.1.0 neobsahuje install_runtime().")
        install(root)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def install_runtime(root: Path | str) -> None:
    root = Path(root).resolve()
    _install_verified_base(root)

    temp_root = Path(tempfile.mkdtemp(prefix="turto_212_", dir=str(root)))
    window = tk.Tk()
    window.title("TURTO 2.1.2 – oprava spuštění")
    window.geometry("700x200")
    window.resizable(False, False)
    window.configure(background="#F3F6F9")
    try:
        window.eval("tk::PlaceWindow . center")
    except Exception:
        pass

    tk.Label(
        window,
        text="Připravuji TURTO 2.1.2",
        font=("Calibri", 15, "bold"),
        bg="#F3F6F9",
        fg="#17324D",
    ).pack(anchor="w", padx=22, pady=(22, 8))
    status = tk.Label(
        window,
        text="Obnovuji ověřený runtime a bezpečný historický Dekodér Schöck…",
        font=("Calibri", 10),
        bg="#F3F6F9",
        fg="#172230",
    )
    status.pack(anchor="w", padx=22)
    counter = tk.Label(window, text="", font=("Calibri", 9), bg="#F3F6F9", fg="#5C6878")
    counter.pack(anchor="w", padx=22, pady=(8, 0))
    window.update()

    downloaded: list[tuple[Path, Path]] = []
    try:
        for index, (local, remote) in enumerate(OVERLAY.items(), 1):
            status.configure(text=f"Stahuji: {local}")
            counter.configure(text=f"{index} / {len(OVERLAY)}")
            window.update()
            url = f"https://raw.githubusercontent.com/{REPOSITORY}/{RUNTIME_COMMIT}/{remote}"
            source = temp_root / local
            source.write_bytes(_download(url, "TURTO-2.1.2"))
            downloaded.append((source, root / local))

        status.configure(text="Instaluji opravenou startovací vrstvu…")
        window.update()
        for source, target in downloaded:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)

        # Old 2.1.1 compatibility aliases are intentionally not used anymore.
        for obsolete in (
            "app_runtime_210.pyw",
            "shear_dowels_catalog_210.py",
            "shear_dowels_ui_210.py",
        ):
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
