from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from tkinter import messagebox

MANIFEST_URL = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/update_manifest.json"
ROOT = Path(__file__).resolve().parent


def _version_tuple(v: str):
    out = []
    for part in str(v).split('.'):
        n = ''.join(c for c in part if c.isdigit())
        out.append(int(n or 0))
    return tuple(out)


def _installed_version(fallback: str) -> str:
    try:
        value = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
        if value and _version_tuple(value) >= _version_tuple(fallback):
            return value
    except Exception:
        pass
    return fallback


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "TURTO-Updater"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()


def check_and_update(parent, current_version: str, relaunch: str | None = None) -> None:
    current_version = _installed_version(current_version)
    try:
        manifest = json.loads(_download(MANIFEST_URL).decode("utf-8"))
    except Exception as exc:
        messagebox.showerror("Aktualizace", f"Nelze načíst informace o aktualizaci.\n\n{exc}", parent=parent)
        return

    latest = str(manifest.get("version", "0"))
    if _version_tuple(latest) <= _version_tuple(current_version):
        messagebox.showinfo("Aktualizace", f"Používáte aktuální verzi {current_version}.", parent=parent)
        return

    notes = str(manifest.get("notes", "")).strip()
    msg = f"Je dostupná verze {latest}.\n\n{notes}\n\nStáhnout a nainstalovat aktualizaci?"
    if not messagebox.askyesno("Aktualizace TURTO", msg, parent=parent):
        return

    files = list(manifest.get("files") or [])
    temp = Path(tempfile.mkdtemp(prefix="turto_update_"))
    try:
        for item in files:
            rel = Path(item["path"])
            data = _download(item["url"])
            sha = hashlib.sha256(data).hexdigest().lower()
            if sha != str(item["sha256"]).lower():
                raise RuntimeError(f"Kontrolní součet nesouhlasí: {rel}")
            dst = temp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)

        script = temp / "apply_update.py"
        script.write_text(_apply_script(latest, files, relaunch), encoding="utf-8")
        subprocess.Popen(
            [sys.executable, str(script), str(ROOT)],
            cwd=str(temp),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        messagebox.showinfo(
            "Aktualizace",
            "Aktualizace byla stažena. Program se ukončí a soubory se nahradí.",
            parent=parent,
        )
        parent.after(200, parent.destroy)
    except Exception as exc:
        shutil.rmtree(temp, ignore_errors=True)
        messagebox.showerror("Aktualizace", f"Aktualizace se nezdařila.\n\n{exc}", parent=parent)


def _apply_script(version: str, files: list[dict], relaunch: str | None) -> str:
    paths = [str(x["path"]).replace("\\", "/") for x in files]
    launcher = relaunch or "Spustit_program.vbs"
    return f'''import os, shutil, sys, time\nfrom pathlib import Path\ntime.sleep(1.5)\nsrc=Path(__file__).resolve().parent\ndst=Path(sys.argv[1]).resolve()\nbackup=dst/'.update_backup'\nbackup.mkdir(exist_ok=True)\nfor rel in {paths!r}:\n    s=src/rel; d=dst/rel\n    d.parent.mkdir(parents=True, exist_ok=True)\n    if d.exists():\n        b=backup/rel; b.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(d,b)\n    shutil.copy2(s,d)\n(dst/'version.txt').write_text({version!r}, encoding='utf-8')\nlauncher=dst/{launcher!r}\nif launcher.exists():\n    try:\n        os.startfile(str(launcher))\n    except Exception:\n        pass\n'''
