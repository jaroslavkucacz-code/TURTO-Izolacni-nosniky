from __future__ import annotations

"""TURTO ISO 1.1.26 immutable runtime bootstrap."""

import json
import os
import runpy
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

VERSION = "1.1.26"
PINNED_COMMIT = "33397e798da1f2b9db81ae49abb52ab75eef8844"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
ROOT = Path(__file__).resolve().parent
MARKER = ROOT / ".turto_runtime_1_1_26.ok"
RUNTIME_MANIFEST = "updates/1.1.26/runtime_manifest.json"


def _url(repo_path: str) -> str:
    return "https://raw.githubusercontent.com/" + REPOSITORY + "/" + PINNED_COMMIT + "/" + repo_path


def _download(url: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            suffix = "?turto=" + str(int(time.time() * 1000)) + "_" + str(attempt)
            req = urllib.request.Request(
                url + suffix,
                headers={
                    "User-Agent": "TURTO-ISO-1.1.26",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=40) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Stažený soubor je prázdný.")
            return data
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1.0 + attempt)
    raise RuntimeError(f"Nelze stáhnout {url}\n{last}")


def _runtime_files() -> dict[str, str]:
    data = json.loads(_download(_url(RUNTIME_MANIFEST)).decode("utf-8"))
    if not isinstance(data, dict) or not data:
        raise RuntimeError("Runtime manifest 1.1.26 je prázdný nebo neplatný.")
    files: dict[str, str] = {}
    for local, remote in data.items():
        local_path = Path(str(local))
        if local_path.is_absolute() or ".." in local_path.parts:
            raise RuntimeError(f"Neplatná lokální cesta runtime: {local}")
        remote_text = str(remote)
        if not remote_text.startswith("updates/"):
            raise RuntimeError(f"Neplatná vzdálená cesta runtime: {remote_text}")
        files[str(local_path)] = remote_text
    return files


def _runtime_ready(files: dict[str, str]) -> bool:
    if not MARKER.exists():
        return False
    try:
        if MARKER.read_text(encoding="utf-8").strip() != PINNED_COMMIT:
            return False
    except Exception:
        return False
    return all((ROOT / local).is_file() for local in files)


def _install_runtime(files: dict[str, str]) -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="turto_1126_", dir=str(ROOT)))
    window = tk.Tk()
    window.title("TURTO ISO – dokončení aktualizace")
    window.geometry("660x190")
    window.resizable(False, False)
    window.configure(background="#F3F6F9")
    try:
        window.eval("tk::PlaceWindow . center")
    except Exception:
        pass

    tk.Label(
        window,
        text="Dokončuji aktualizaci TURTO ISO 1.1.26",
        font=("Calibri", 15, "bold"),
        bg="#F3F6F9",
        fg="#17324D",
    ).pack(anchor="w", padx=22, pady=(22, 8))
    status = tk.Label(
        window,
        text="Připravuji pracovní prostředí…",
        font=("Calibri", 10),
        bg="#F3F6F9",
        fg="#172230",
        justify="left",
        wraplength=610,
    )
    status.pack(anchor="w", padx=22)
    counter = tk.Label(window, text="", font=("Calibri", 9), bg="#F3F6F9", fg="#5C6878")
    counter.pack(anchor="w", padx=22, pady=(8, 0))
    window.update()

    downloaded = []
    try:
        total = len(files)
        for index, (local, remote) in enumerate(files.items(), 1):
            status.configure(text=f"Stahuji: {local}")
            counter.configure(text=f"{index} / {total}")
            window.update()
            data = _download(_url(remote))
            temp_path = temp_root / local
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(data)
            downloaded.append((temp_path, ROOT / local))

        status.configure(text="Instaluji ověřenou sadu souborů…")
        window.update()
        for source, target in downloaded:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
        MARKER.write_text(PINNED_COMMIT, encoding="utf-8")
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        shutil.rmtree(temp_root, ignore_errors=True)


def _show_failure(exc: Exception) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Aktualizace TURTO ISO",
            "Dokončení aktualizace 1.1.26 se nezdařilo. Centrální databáze AKCÍ ani katalogy nebyly měněny.\n\n"
            + str(exc)
            + "\n\nZkuste program spustit znovu; stažení se zopakuje z neměnného Git commitu.",
            parent=root,
        )
        root.destroy()
    except Exception:
        pass


def main() -> int:
    try:
        files = _runtime_files()
        if not _runtime_ready(files):
            _install_runtime(files)
    except Exception as exc:
        _show_failure(exc)
        return 2

    target = ROOT / "app_runtime.pyw"
    if not target.exists():
        _show_failure(RuntimeError("Chybí app_runtime.pyw po dokončení aktualizace."))
        return 3
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
