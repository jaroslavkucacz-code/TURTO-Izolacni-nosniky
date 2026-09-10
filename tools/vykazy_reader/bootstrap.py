from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

MANIFEST_URL = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/tools/vykazy_reader/update_manifest.json"
APP_FILE = "app.py"


def version_tuple(value: str):
    return tuple(int(x) for x in re.findall(r"\d+", str(value))) or (0,)


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "TURTO-Vykazy-Bootstrap"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def current_version(root: Path) -> str:
    vf = root / "VERSION.txt"
    if vf.exists():
        return vf.read_text(encoding="utf-8-sig", errors="replace").strip() or "0"
    app = root / APP_FILE
    if app.exists():
        m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)', app.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            return m.group(1)
    return "0"


def choose_root() -> Path:
    candidates = []
    if len(sys.argv) > 1:
        candidates.append(Path(sys.argv[1]))
    candidates.extend([Path.cwd(), Path(__file__).resolve().parent])
    for root in candidates:
        try:
            if (root / APP_FILE).exists():
                return root.resolve()
        except Exception:
            pass

    import tkinter as tk
    from tkinter import filedialog

    tkroot = tk.Tk()
    tkroot.withdraw()
    folder = filedialog.askdirectory(
        title="Vyberte složku TURTO – Výkazy izolačních prvků (obsahuje app.py)"
    )
    tkroot.destroy()
    if not folder:
        raise SystemExit(2)
    root = Path(folder).resolve()
    if not (root / APP_FILE).exists():
        raise RuntimeError("Ve vybrané složce nebyl nalezen app.py.")
    return root


def safe_target(root: Path, relative: str) -> Path:
    rel = Path(str(relative).replace("\\", "/"))
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise RuntimeError(f"Neplatný cíl aktualizace: {relative}")
    forbidden = {"turto_vykazy.sqlite3", "database_settings.json"}
    if rel.name.lower() in forbidden or rel.parts[0].lower() in {"archive", "database", ".update_backup"}:
        raise RuntimeError(f"Chráněný soubor nelze aktualizovat: {relative}")
    target = (root / rel).resolve()
    if root != target and root not in target.parents:
        raise RuntimeError(f"Cíl leží mimo instalaci: {relative}")
    return target


def apply(root: Path, manifest: dict):
    version = str(manifest.get("version") or manifest.get("latest_version") or "").strip()
    patches = manifest.get("patches") or []
    if version and isinstance(patches, list) and patches:
        current = current_version(root)
        safety = 0
        while version_tuple(current) < version_tuple(version):
            safety += 1
            if safety > 25:
                raise RuntimeError("Online aktualizace obsahuje příliš mnoho kroků.")
            patch = next((x for x in patches if str(x.get("from") or "").strip() == current), None)
            if patch is None:
                raise RuntimeError(f"Pro přechod z v{current} na v{version} chybí aktualizační krok.")
            target_version = str(patch.get("to") or "").strip()
            url = str(patch.get("url") or "").strip()
            expected = str(patch.get("sha256") or "").strip().lower()
            if not target_version or not url or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise RuntimeError(f"Neplatný aktualizační krok z v{current}.")
            payload = download(url)
            if hashlib.sha256(payload).hexdigest() != expected:
                raise RuntimeError(f"Nesouhlasí SHA-256 aktualizačního kroku v{target_version}.")
            fd, temp_name = tempfile.mkstemp(prefix="turto_vykazy_patch_", suffix=".py")
            os.close(fd)
            temp_patch = Path(temp_name)
            temp_patch.write_bytes(payload)
            try:
                proc = subprocess.run(
                    [sys.executable, str(temp_patch), str(root)],
                    cwd=str(root), capture_output=True, text=True,
                )
            finally:
                try:
                    temp_patch.unlink()
                except Exception:
                    pass
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "neznámá chyba").strip()
                raise RuntimeError(detail)
            current = current_version(root)
            if version_tuple(current) < version_tuple(target_version):
                raise RuntimeError(f"Aktualizační krok nezapsal očekávanou verzi v{target_version}.")
        return version

    files = manifest.get("files") or []
    if not version or not files:
        raise RuntimeError("Online manifest je neúplný.")

    staged = []
    for item in files:
        relative = str(item.get("target") or "").strip()
        url = str(item.get("url") or "").strip()
        urls = item.get("urls") or []
        if isinstance(urls, str):
            urls = [urls]
        urls = [str(x).strip() for x in urls if str(x).strip()] if isinstance(urls, list) else []
        expected = str(item.get("sha256") or "").strip().lower()
        if not relative or (not url and not urls) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise RuntimeError(f"Neplatná položka manifestu: {relative or '?'}")
        payload = b"".join(download(part_url) for part_url in urls) if urls else download(url)
        encoding = str(item.get("encoding") or "raw").lower()
        if encoding in {"gzip-base64", "gzip-base64-parts"}:
            payload = gzip.decompress(base64.b64decode(payload))
        elif encoding == "base64":
            payload = base64.b64decode(payload)
        elif encoding != "raw":
            raise RuntimeError(f"Nepodporované kódování: {encoding}")
        if hashlib.sha256(payload).hexdigest() != expected:
            raise RuntimeError(f"Nesouhlasí SHA-256: {relative}")
        staged.append((safe_target(root, relative), payload, relative))

    backup_root = root / ".update_backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backups = []
    try:
        for target, payload, relative in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if target.exists():
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            backups.append((target, backup))
            temp = target.with_name(target.name + ".update_tmp")
            temp.write_bytes(payload)
            os.replace(temp, target)
    except Exception:
        for target, backup in reversed(backups):
            try:
                if backup and backup.exists():
                    shutil.copy2(backup, target)
                elif backup is None and target.exists():
                    target.unlink()
            except Exception:
                pass
        raise
    return version


def restart(root: Path):
    vbs = root / "SPUSTIT_BEZ_OKNA.vbs"
    bat = root / "SPUSTIT.bat"
    if os.name == "nt" and vbs.exists():
        subprocess.Popen(["wscript.exe", str(vbs)], cwd=str(root))
    elif os.name == "nt" and bat.exists():
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(root), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        subprocess.Popen([sys.executable, str(root / APP_FILE)], cwd=str(root))


def notify(title: str, text: str, error: bool = False):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, text, parent=root)
        root.destroy()
    except Exception:
        print(text, file=sys.stderr if error else sys.stdout)


def main() -> int:
    try:
        root = choose_root()
        manifest = json.loads(download(MANIFEST_URL).decode("utf-8-sig"))
        latest = str(manifest.get("version") or manifest.get("latest_version") or "").strip()
        current = current_version(root)
        if version_tuple(latest) <= version_tuple(current):
            notify("TURTO – Aktualizace", f"Používáte aktuální verzi v{current}.")
            return 0
        version = apply(root, manifest)
        notify(
            "TURTO – Aktualizace",
            f"Online aktualizace na v{version} byla nainstalována.\n\n"
            "Databáze akcí ani archiv PDF nebyly součástí aktualizace.\nProgram se nyní spustí znovu.",
        )
        restart(root)
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        notify("TURTO – Chyba aktualizace", f"Aktualizace se nepodařila:\n\n{exc}", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
