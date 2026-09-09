from __future__ import annotations

"""TURTO 2.2.10 verified bootstrap."""

import hashlib
import runpy
import shutil
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

VERSION = "2.2.10"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
INSTALLER_COMMIT = "570afd46824049ac22dd82f462797dd5a3c15c3c"
INSTALLER_SHA256 = "c8225bc86871f6ce5c36e5f12475eae6da0f4e253d297dd105ed21f74171f15a"
RUNTIME_LAYOUT = "3"
ROOT = Path(__file__).resolve().parent
MARKER = ROOT / ".turto_runtime_current.ok"
STARTUP_LOG = ROOT / "startup.log"
REQUIRED_RUNTIME_FILES = (
    "app_runtime.pyw", "platform_workspace.py", "pdf_scope.py", "catalog_browser.py",
    "ui_cleanup_229.py", "ui_cleanup_228.py", "hit_workspace.py", "hit_pdf.py", "updater.py",
    "shear_dowels_current.py", "shear_catalogs_227.py", "shear_ui_227.py", "ui_help.py",
    "table_controls.py", "ui_consistency.py", "ui_layout.py", "ui_visibility.py",
)


def _runtime_ready() -> bool:
    try:
        return (
            MARKER.is_file()
            and MARKER.read_text(encoding="utf-8").strip() == RUNTIME_LAYOUT
            and all((ROOT / name).is_file() for name in REQUIRED_RUNTIME_FILES)
        )
    except Exception:
        return False


def _download_installer() -> Path:
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{INSTALLER_COMMIT}/updates/2.2.10/runtime_installer.py"
    last = None
    temp_dir = Path(tempfile.mkdtemp(prefix="turto_bootstrap_"))
    target = temp_dir / "runtime_installer.py"
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url + f"?turto={int(time.time()*1000)}_{attempt}",
                headers={
                    "User-Agent": "TURTO-2.2.10-Bootstrap",
                    "Cache-Control": "no-cache, no-store",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest().lower()
            if not data or actual != INSTALLER_SHA256:
                raise RuntimeError(
                    "Kontrolní součet instalačního modulu nesouhlasí.\n"
                    f"Očekáváno: {INSTALLER_SHA256}\nStaženo: {actual}"
                )
            target.write_bytes(data)
            return target
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    shutil.rmtree(temp_dir, ignore_errors=True)
    raise RuntimeError(f"Nelze stáhnout ověřený instalační modul.\n{last}")


def _install_runtime() -> None:
    installer = _download_installer()
    try:
        namespace = runpy.run_path(str(installer))
        install = namespace.get("install_runtime")
        if not callable(install):
            raise RuntimeError("Instalační modul neobsahuje install_runtime().")
        install(ROOT)
        MARKER.write_text(RUNTIME_LAYOUT, encoding="utf-8")
    finally:
        shutil.rmtree(installer.parent, ignore_errors=True)


def _failure(stage: str, exc: BaseException) -> int:
    try:
        STARTUP_LOG.write_text(
            f"TURTO {VERSION} – {stage}\n\n{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
    except Exception:
        pass
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "TURTO – chyba při spuštění",
            f"{exc}\n\nPodrobnosti: {STARTUP_LOG}",
            parent=root,
        )
        root.destroy()
    except Exception:
        pass
    return 2


def main() -> int:
    try:
        if not _runtime_ready():
            _install_runtime()
    except Exception as exc:
        return _failure("obnova runtime", exc)
    try:
        runpy.run_path(str(ROOT / "app_runtime.pyw"), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 0
    except BaseException as exc:
        return _failure("spuštění programu", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
