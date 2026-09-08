from __future__ import annotations

"""TURTO 2.1.2 small immutable bootstrap with startup diagnostics."""

import runpy
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

VERSION = "2.1.2"
INSTALLER_COMMIT = "f98ffee94aafd3d6bbf1e15ff44714dd9978ff14"
RUNTIME_COMMIT = "2a0428af98b064770fffe84d430dee3388a1bfb9"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
ROOT = Path(__file__).resolve().parent
MARKER = ROOT / ".turto_runtime_2_1_2.ok"
STARTUP_LOG = ROOT / "startup_2_1_2.log"


def _runtime_ready() -> bool:
    try:
        return (
            MARKER.is_file()
            and MARKER.read_text(encoding="utf-8").strip() == RUNTIME_COMMIT
            and (ROOT / "app_runtime.pyw").is_file()
            and (ROOT / "legacy_schoeck_decoder.py").is_file()
            and (ROOT / "shear_dowels_catalog.py").is_file()
            and (ROOT / "shear_dowels_ui.py").is_file()
        )
    except Exception:
        return False


def _download_installer() -> Path:
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/"
        "updates/2.1.2/runtime_installer.py"
    )
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={
                    "User-Agent": "TURTO-2.1.2",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            if not data:
                raise RuntimeError("Stažený instalační soubor je prázdný.")
            target = Path(tempfile.mkdtemp(prefix="turto_bootstrap_")) / "runtime_installer.py"
            target.write_bytes(data)
            return target
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"Nelze stáhnout instalační modul.\n{last}")


def _install_runtime() -> None:
    namespace = runpy.run_path(str(_download_installer()))
    install = namespace.get("install_runtime")
    if not callable(install):
        raise RuntimeError("Stažený instalační modul neobsahuje install_runtime().")
    install(ROOT)
    MARKER.write_text(RUNTIME_COMMIT, encoding="utf-8")


def _write_log(stage: str, exc: BaseException) -> None:
    try:
        STARTUP_LOG.write_text(
            f"TURTO {VERSION} – {stage}\n\n{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
    except Exception:
        pass


def _show_failure(title: str, message: str) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:
        pass


def main() -> int:
    try:
        if not _runtime_ready():
            _install_runtime()
    except Exception as exc:
        _write_log("instalace runtime", exc)
        _show_failure(
            "Aktualizace TURTO 2.1.2",
            "Dokončení opravy se nezdařilo. Databáze AKCÍ nebyla měněna.\n\n"
            + str(exc)
            + f"\n\nPodrobnosti: {STARTUP_LOG}",
        )
        return 2

    target = ROOT / "app_runtime.pyw"
    if not target.is_file():
        exc = RuntimeError("Chybí app_runtime.pyw po aktualizaci.")
        _write_log("kontrola runtime", exc)
        _show_failure("TURTO 2.1.2", str(exc))
        return 3

    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 0
    except BaseException as exc:
        _write_log("spuštění programu", exc)
        _show_failure(
            "TURTO 2.1.2 – chyba při spuštění",
            "Program se nepodařilo spustit. Tentokrát byl uložen úplný traceback.\n\n"
            + str(exc)
            + f"\n\nPodrobnosti: {STARTUP_LOG}",
        )
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
