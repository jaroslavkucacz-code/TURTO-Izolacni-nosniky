from __future__ import annotations

"""TURTO 2.2.5 – verified current runtime installation path.

Installs the verified compatible base 2.1.0 and then the exact current layers.
Does not modify actions.sqlite3.
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
    "app_runtime.pyw": ("9a7fa44bf0d5c9692f2c85041c26ceaf09a0ade2", "updates/2.2.5/app_runtime.pyw", "f522ee97d6aa53175993812e6fcfc08581260c7e68b029e889121636fafe2bea"),
    "platform_workspace.py": ("06e4fea2b4e862b6200a36aafd609a883a87668b", "updates/2.2.5/platform_workspace.py", "ee200bb793ab72941e6716563f3f3f232d753c8a61c821853c334d20fc7b4ce4"),
    "ui_layout.py": ("4e278f47673f2990c133308ad47038076248cbcd", "updates/2.2.5/ui_layout.py", "c89b95f063e75cb233530f10e581f187a25da2f0c197bb0c6b466fd476b9293e"),
    "table_controls.py": ("27abf30ad53991059ae3ea6c33f6c5e80ff57527", "updates/2.2.4/table_controls.py", "51b25e386bcff215c24b65b030cb43a3c5a354f082859aeec047b5baaf610807"),
    "ui_consistency.py": ("9c0569aa2cd4b80fb229129b7ed099d3121e47c5", "updates/2.2.4/ui_consistency.py", "40c8dd14eefc88a8d9e90d4d4cba32f5f12568e7e79c59396c16d3e780d8b6de"),
    "isokorb_compat.py": ("05c915c9c8f4142cbaf8a16f6166ee937a0f6eeb", "updates/2.2.3/isokorb_compat.py", "2e73004bbb050aba9d2153a7feea8dc824da91619fc0fc7f879d197b0e35c93f"),
    "shear_autocomplete.py": ("b3f2cd32253c8fbbf3dc159c43a4af967b6decdf", "updates/2.2.3/shear_autocomplete.py", "38cc593992992ae8e3d4ca7b957b938572877f300a99346f5a65676cf8cb04f3"),
    "ui_help.py": ("6fbf99c65cf1e18cad0127a57819e24653b3596e", "updates/2.2.3/ui_help.py", "8f2e08057a8221ff6e08f15838437a5452a726ebb9a8046164511ddf11741ef9"),
    "shear_movement.py": ("cbac3861a41040f8da59683898820767fd4f43a9", "updates/2.2.2/shear_movement.py", "fbe257543cf6ce6ffb901c8378d2c9ebaaa71fedbeef717b2fcf20d0597caa6d"),
    "shear_dowels_current.py": ("2f138cacf2d434c7b195311e05f1144f815a5e24", "updates/2.2.0/shear_dowels_current.py", "a37e244096660b5b827241c5f0eb2c8cd80a9f0b44f6c587d1711b0c05a065ce"),
    "schoeck_dorn_decoder.py": ("2f138cacf2d434c7b195311e05f1144f815a5e24", "updates/2.2.0/schoeck_dorn_decoder.py", "310fff1beda0eaf8c7d0c489facf9ddd5c5205219d3c2da0c1008c45a0c648b0"),
    "hit_workspace.py": ("44994a40b3d018269841c915b4742adae26acafa", "updates/2.1.3/hit_workspace.py", "79e4f24e58d0fed61f8b4481222593b7ec6d58599913525aa21fa5640e4841cb"),
    "hit_pdf.py": ("44994a40b3d018269841c915b4742adae26acafa", "updates/2.1.2/hit_pdf.py", "62909e7ecbcc5f56d7dca077cf95421cb1ee10931599433557abece32d629ea8"),
    "updater.py": ("5f395e56a8911e12783bdbd8378592963352cf69", "updates/2.2.1/updater.py", "4b680b86e3f4b7546f600ae56254dc34e65494824f3fe74bd9149c1a41e559c4"),
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
        installer.write_bytes(_download(url, "TURTO-2.2.5-base"))
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
    window.title("TURTO 2.2.5 – obnova runtime")
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
                _download_checked(commit, remote, expected, "TURTO-2.2.5-runtime")
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
