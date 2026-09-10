from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

EXPECTED_PATCH_SHA256 = "e7090305ea2591705177a6aa7f3514cd76b2368f2426a14e4284434a68b2981e"
BASE = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/d8d593bbb7e9f3f6088bc60c64c0b45fd305dbf7/tools/vykazy_reader/updates/0.13.5/exact"
PART_URLS = [f"{BASE}/part{i}.b64" for i in range(1, 7)]


def download(url: str) -> bytes:
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(
        f"{url}{sep}_turto={os.urandom(6).hex()}",
        headers={
            "User-Agent": "TURTO-Vykazy-0135-Exact",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def choose_root() -> Path:
    if len(sys.argv) > 1:
        root = Path(sys.argv[1]).resolve()
        if (root / "app.py").exists():
            return root
    cwd = Path.cwd().resolve()
    if (cwd / "app.py").exists():
        return cwd
    import tkinter as tk
    from tkinter import filedialog
    window = tk.Tk()
    window.withdraw()
    folder = filedialog.askdirectory(
        title="Vyberte složku TURTO – Výkazy kladecích plánů (obsahuje app.py)"
    )
    window.destroy()
    if not folder:
        raise SystemExit(2)
    root = Path(folder).resolve()
    if not (root / "app.py").exists():
        raise RuntimeError("Ve vybrané složce nebyl nalezen app.py.")
    return root


def notify(title: str, text: str, error: bool = False) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        window = tk.Tk()
        window.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, text, parent=window)
        window.destroy()
    except Exception:
        print(text, file=sys.stderr if error else sys.stdout)


def restart(root: Path) -> None:
    vbs = root / "SPUSTIT_BEZ_OKNA.vbs"
    bat = root / "SPUSTIT.bat"
    if os.name == "nt" and vbs.exists():
        subprocess.Popen(["wscript.exe", str(vbs)], cwd=str(root))
    elif os.name == "nt" and bat.exists():
        subprocess.Popen(
            ["cmd", "/c", str(bat)], cwd=str(root),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        subprocess.Popen([sys.executable, str(root / "app.py")], cwd=str(root))


def main() -> int:
    standalone = len(sys.argv) <= 1
    root = choose_root()
    encoded_parts = [download(url).strip() for url in PART_URLS]
    try:
        patch = b"".join(base64.b64decode(part, validate=True) for part in encoded_parts)
    except Exception as exc:
        raise RuntimeError(f"Online aktualizační data jsou poškozená: {exc}") from exc
    actual = hashlib.sha256(patch).hexdigest()
    if actual != EXPECTED_PATCH_SHA256:
        raise RuntimeError(
            "Kontrolní součet přesného aktualizačního kroku nesouhlasí. "
            f"Očekáváno {EXPECTED_PATCH_SHA256}, načteno {actual}."
        )

    fd, name = tempfile.mkstemp(prefix="turto_vykazy_0135_exact_", suffix=".py")
    os.close(fd)
    temp = Path(name)
    try:
        temp.write_bytes(patch)
        proc = subprocess.run(
            [sys.executable, str(temp), str(root)],
            cwd=str(root), capture_output=True, text=True,
        )
    finally:
        try:
            temp.unlink()
        except Exception:
            pass
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "neznámá chyba").strip()
        raise RuntimeError(detail)

    if standalone:
        notify(
            "TURTO – Aktualizace",
            "Aktualizace na v0.13.5 proběhla úspěšně.\n\n"
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
        notify("TURTO – Chyba aktualizace", f"Aktualizace se nepodařila:\n\n{exc}", error=True)
        raise SystemExit(1)
