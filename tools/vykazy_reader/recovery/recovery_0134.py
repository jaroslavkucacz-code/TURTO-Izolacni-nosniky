from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

PATCH_URL = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/8545c91ec129a1824a623f2834351ddc2aaf7204/tools/vykazy_reader/updates/0.13.4/update_0_13_3_to_0_13_4_windows_compat.py"
PATCH_SHA256 = "90cac5a5d92f935f90d8a655d28aa38fb6430f38b443cdb3b1858ecd52cc6132"


def choose_root() -> Path:
    candidates = []
    if len(sys.argv) > 1:
        candidates.append(Path(sys.argv[1]))
    candidates.extend([Path.cwd(), Path(__file__).resolve().parent])
    for p in candidates:
        try:
            p = p.resolve()
            if (p / "app.py").exists() and (p / "VERSION.txt").exists():
                return p
        except Exception:
            pass

    import tkinter as tk
    from tkinter import filedialog
    r = tk.Tk()
    r.withdraw()
    folder = filedialog.askdirectory(title="Vyberte složku TURTO – Výkazy kladecích plánů (obsahuje app.py)")
    r.destroy()
    if not folder:
        raise SystemExit(2)
    p = Path(folder).resolve()
    if not (p / "app.py").exists():
        raise RuntimeError("Ve vybrané složce nebyl nalezen app.py.")
    return p


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "TURTO-Vykazy-Recovery",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def notify(title: str, text: str, error: bool = False) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, text, parent=r)
        r.destroy()
    except Exception:
        print(text, file=sys.stderr if error else sys.stdout)


def restart(root: Path) -> None:
    vbs = root / "SPUSTIT_BEZ_OKNA.vbs"
    bat = root / "SPUSTIT.bat"
    if os.name == "nt" and vbs.exists():
        subprocess.Popen(["wscript.exe", str(vbs)], cwd=str(root))
    elif os.name == "nt" and bat.exists():
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(root), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        subprocess.Popen([sys.executable, str(root / "app.py")], cwd=str(root))


def main() -> int:
    root = choose_root()
    version_file = root / "VERSION.txt"
    current = version_file.read_text(encoding="utf-8-sig", errors="replace").strip() if version_file.exists() else ""
    if current == "0.13.4":
        notify("TURTO – Oprava aktualizace", "Verze 0.13.4 už je nainstalovaná.")
        return 0
    if current != "0.13.3":
        raise RuntimeError(f"Opravný krok očekává v0.13.3, nalezena v{current or '?'}.")

    payload = download(PATCH_URL)
    if hashlib.sha256(payload).hexdigest() != PATCH_SHA256:
        raise RuntimeError("Nesouhlasí kontrolní SHA-256 opravného patche.")

    fd, name = tempfile.mkstemp(prefix="turto_vykazy_recovery_0134_", suffix=".py")
    os.close(fd)
    temp = Path(name)
    try:
        temp.write_bytes(payload)
        proc = subprocess.run([sys.executable, str(temp), str(root)], cwd=str(root), capture_output=True, text=True)
    finally:
        try:
            temp.unlink()
        except Exception:
            pass
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "neznámá chyba").strip())

    final = version_file.read_text(encoding="utf-8-sig", errors="replace").strip()
    if final != "0.13.4":
        raise RuntimeError("Opravný krok nezapsal očekávanou verzi 0.13.4.")

    notify("TURTO – Oprava aktualizace", "Online aktualizace na v0.13.4 proběhla úspěšně.\n\nDatabáze akcí ani archiv PDF nebyly měněny.")
    restart(root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        notify("TURTO – Chyba opravy", f"Oprava se nepodařila:\n\n{exc}", error=True)
        raise SystemExit(1)
