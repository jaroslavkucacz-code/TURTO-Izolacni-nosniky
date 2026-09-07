from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from tkinter import messagebox

MANIFEST_URL = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/update_manifest.json"
ROOT = Path(__file__).resolve().parent


def _version_tuple(v: str):
    out = []
    for part in str(v).split("."):
        n = "".join(c for c in part if c.isdigit())
        out.append(int(n or 0))
    return tuple(out)


def _cache_bust(url: str, token: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}turto_cb={urllib.parse.quote(str(token))}"


def _download(url: str, *, token: str = "", attempts: int = 3) -> bytes:
    last = None
    for attempt in range(max(1, attempts)):
        try:
            effective = _cache_bust(url, f"{token}-{attempt}-{time.time_ns()}")
            req = urllib.request.Request(
                effective,
                headers={
                    "User-Agent": "TURTO-Updater-1.1.24",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Server vrátil prázdný soubor.")
            return data
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.8 + attempt)
    raise RuntimeError(f"Stažení selhalo: {url}\n{last}")


def _download_checked(item: dict, latest: str) -> bytes:
    url = str(item["url"])
    expected = str(item.get("sha256", "")).lower().strip()
    if not expected:
        raise RuntimeError(f"V manifestu chybí SHA-256: {item.get('path', url)}")
    last_actual = ""
    last_error = None
    for attempt in range(4):
        try:
            data = _download(url, token=f"{latest}-{item.get('path','')}-{attempt}", attempts=2)
            actual = hashlib.sha256(data).hexdigest().lower()
            last_actual = actual
            if actual == expected:
                return data
        except Exception as exc:
            last_error = exc
        time.sleep(0.6 + attempt * 0.4)
    detail = (
        f"Kontrolní součet nesouhlasí: {item.get('path', '')}\n"
        f"Očekáváno: {expected}\n"
        f"Staženo:    {last_actual or 'soubor se nepodařilo stáhnout'}"
    )
    if last_error is not None:
        detail += f"\n\nPoslední chyba: {last_error}"
    raise RuntimeError(detail)


def check_and_update(parent, current_version: str) -> None:
    try:
        manifest = json.loads(
            _download(MANIFEST_URL, token=f"manifest-{time.time_ns()}", attempts=3).decode("utf-8")
        )
    except Exception as exc:
        messagebox.showerror(
            "Aktualizace",
            f"Nelze načíst informace o aktualizaci.\n\n{exc}",
            parent=parent,
        )
        return

    latest = str(manifest.get("version", "0"))
    if _version_tuple(latest) <= _version_tuple(current_version):
        messagebox.showinfo(
            "Aktualizace",
            f"Používáte aktuální verzi {current_version}.",
            parent=parent,
        )
        return

    notes = str(manifest.get("notes", "")).strip()
    message = f"Je dostupná verze {latest}.\n\n{notes}\n\nStáhnout a nainstalovat aktualizaci?"
    if not messagebox.askyesno("Aktualizace TURTO", message, parent=parent):
        return

    files = list(manifest.get("files") or [])
    if not files:
        messagebox.showerror("Aktualizace", "Manifest neobsahuje žádné soubory.", parent=parent)
        return

    temp = Path(tempfile.mkdtemp(prefix="turto_update_"))
    try:
        for item in files:
            rel = Path(str(item["path"]))
            if rel.is_absolute() or ".." in rel.parts:
                raise RuntimeError(f"Neplatná cesta v manifestu: {rel}")
            data = _download_checked(item, latest)
            destination = temp / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)

        script = temp / "apply_update.py"
        script.write_text(_apply_script(latest, files), encoding="utf-8")
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
        messagebox.showerror(
            "Aktualizace",
            f"Aktualizace se nezdařila.\n\n{exc}",
            parent=parent,
        )


def _apply_script(version, files):
    paths = [str(x["path"]).replace("\\", "/") for x in files]
    return f'''import os, shutil, sys, time
from pathlib import Path
time.sleep(1.5)
src=Path(__file__).resolve().parent
dst=Path(sys.argv[1]).resolve()
backup=dst/'.update_backup'
backup.mkdir(exist_ok=True)
for rel in {paths!r}:
    s=src/rel; d=dst/rel
    d.parent.mkdir(parents=True, exist_ok=True)
    if d.exists():
        b=backup/rel; b.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(d,b)
    shutil.copy2(s,d)
(dst/'version.txt').write_text({version!r}, encoding='utf-8')
launcher=dst/'Spustit_program.vbs'
if launcher.exists():
    try:
        os.startfile(str(launcher))
    except Exception:
        pass
'''


