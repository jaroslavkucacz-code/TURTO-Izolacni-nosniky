from __future__ import annotations

import base64
import hashlib
import json
import py_compile
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.7.3"
OUT = ROOT / "updates" / "0.7.4"
ICON_SOURCE = ROOT / "assets" / "app_icon.png.b64"

UI_UTILS = '''from __future__ import annotations

import sys
from typing import Any


def place_dialog_on_parent(dialog: Any, parent: Any) -> None:
    """Umístí dialog nad rodičovské okno, tedy na stejný monitor."""
    def _place() -> None:
        try:
            parent.update_idletasks()
            dialog.update_idletasks()

            width = int(dialog.winfo_width())
            height = int(dialog.winfo_height())
            if width <= 1:
                width = max(1, int(dialog.winfo_reqwidth()))
            if height <= 1:
                height = max(1, int(dialog.winfo_reqheight()))

            parent_x = int(parent.winfo_rootx())
            parent_y = int(parent.winfo_rooty())
            parent_w = max(1, int(parent.winfo_width()))
            parent_h = max(1, int(parent.winfo_height()))

            x = parent_x + (parent_w - width) // 2
            y = parent_y + (parent_h - height) // 2
            dialog.geometry(f"{width}x{height}{x:+d}{y:+d}")
            dialog.lift(parent)
        except Exception:
            pass

    try:
        dialog.after_idle(_place)
    except Exception:
        pass


def maximize_window_on_pointer_monitor(window: Any, pointer: tuple[int, int] | None = None) -> None:
    """Při startu přesune hlavní okno na monitor pod kurzorem a maximalizuje ho.

    Na Windows používá pracovní plochu monitoru z WinAPI, takže fungují i monitory
    vlevo/nad primárním monitorem se zápornými souřadnicemi. Pozice kurzoru se může
    předat zachycená už při vytvoření hlavního Tk okna.
    """
    def _maximize() -> None:
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                class POINT(ctypes.Structure):
                    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", wintypes.LONG), ("top", wintypes.LONG),
                        ("right", wintypes.LONG), ("bottom", wintypes.LONG),
                    ]

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("rcMonitor", RECT),
                        ("rcWork", RECT),
                        ("dwFlags", wintypes.DWORD),
                    ]

                user32 = ctypes.windll.user32
                if pointer is None:
                    point = POINT()
                    if not user32.GetCursorPos(ctypes.byref(point)):
                        raise OSError("GetCursorPos selhalo")
                else:
                    point = POINT(int(pointer[0]), int(pointer[1]))

                monitor = user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
                if not monitor:
                    raise OSError("MonitorFromPoint selhalo")
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    raise OSError("GetMonitorInfoW selhalo")

                left, top = int(info.rcWork.left), int(info.rcWork.top)
                area_w = max(800, int(info.rcWork.right - info.rcWork.left))
                area_h = max(600, int(info.rcWork.bottom - info.rcWork.top))

                window.update_idletasks()
                width = int(window.winfo_width())
                height = int(window.winfo_height())
                if width <= 1:
                    width = int(window.winfo_reqwidth())
                if height <= 1:
                    height = int(window.winfo_reqheight())
                width = max(900, min(width, max(900, area_w - 80)))
                height = max(650, min(height, max(650, area_h - 80)))
                x = left + (area_w - width) // 2
                y = top + (area_h - height) // 2

                window.state("normal")
                window.geometry(f"{width}x{height}{x:+d}{y:+d}")
                window.update_idletasks()
                window.state("zoomed")
                window.lift()
                return

            try:
                window.state("zoomed")
            except Exception:
                window.attributes("-zoomed", True)
        except Exception:
            try:
                window.state("zoomed")
            except Exception:
                pass

    try:
        window.after_idle(_maximize)
    except Exception:
        pass
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_app(text: str) -> str:
    text = replace_once(text, 'APP_VERSION = "0.7.3"', 'APP_VERSION = "0.7.4"', "app version")
    text = replace_once(
        text,
        'from ui_utils import place_dialog_on_parent\n',
        'from ui_utils import place_dialog_on_parent, maximize_window_on_pointer_monitor\n',
        "maximize import",
    )
    text = replace_once(
        text,
        'def enable_high_dpi() -> None:\n    """Zapne rozumné škálování na Windows; na ostatních systémech nic nemění."""\n    if sys.platform != "win32":\n        return\n',
        'def enable_high_dpi() -> None:\n    """Zapne rozumné škálování a vlastní identitu aplikace na Windows."""\n    if sys.platform != "win32":\n        return\n    try:\n        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p("TURTO.IzolacniNosniky"))\n    except Exception:\n        pass\n',
        "windows app id",
    )
    text = replace_once(
        text,
        '    def __init__(self):\n        super().__init__()\n        self.root_dir = app_root()\n',
        '    def __init__(self):\n        super().__init__()\n        self._startup_pointer = tuple(int(v) for v in self.winfo_pointerxy())\n        self.root_dir = app_root()\n',
        "capture startup pointer",
    )
    text = replace_once(
        text,
        '        self._icon_image: tk.PhotoImage | None = None\n',
        '        self._icon_image: tk.PhotoImage | None = None\n        self._header_icon_image: tk.PhotoImage | None = None\n',
        "header icon field",
    )
    text = replace_once(
        text,
        '        self.finalize_project_workspace()\n        self.after(100, self._apply_initial_sash)\n',
        '        self.finalize_project_workspace()\n        maximize_window_on_pointer_monitor(self, self._startup_pointer)\n        self.after(100, self._apply_initial_sash)\n',
        "startup maximize",
    )

    old_icon = '''    def _set_icon(self) -> None:\n        icon_path = self.asset_dir / "app_icon.png"\n        if not icon_path.exists():\n            return\n        try:\n            self._icon_image = tk.PhotoImage(file=str(icon_path))\n            self.iconphoto(True, self._icon_image)\n        except Exception as exc:\n            LOGGER.warning("Ikonu se nepodařilo načíst: %s", exc)\n'''
    new_icon = '''    def _set_icon(self) -> None:\n        icon_b64 = self.asset_dir / "app_icon.png.b64"\n        icon_png = self.asset_dir / "app_icon.png"\n        try:\n            if icon_b64.exists():\n                encoded = icon_b64.read_text(encoding="ascii").strip()\n                self._icon_image = tk.PhotoImage(data=encoded)\n            elif icon_png.exists():\n                self._icon_image = tk.PhotoImage(file=str(icon_png))\n            else:\n                return\n            self.iconphoto(True, self._icon_image)\n            factor = max(1, int(self._icon_image.width()) // 64)\n            self._header_icon_image = self._icon_image.subsample(factor, factor) if factor > 1 else self._icon_image\n        except Exception as exc:\n            self._icon_image = None\n            self._header_icon_image = None\n            LOGGER.warning("Ikonu se nepodařilo načíst: %s", exc)\n'''
    text = replace_once(text, old_icon, new_icon, "transparent icon loader")
    text = replace_once(
        text,
        '        if self._icon_image is not None:\n            icon = ttk.Label(header, image=self._icon_image, style="HeaderSubtitle.TLabel")\n',
        '        if self._header_icon_image is not None:\n            icon = ttk.Label(header, image=self._header_icon_image, style="HeaderSubtitle.TLabel")\n',
        "header uses scaled icon",
    )
    return text


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if not ICON_SOURCE.exists():
        raise SystemExit(f"Missing icon source: {ICON_SOURCE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    (OUT / "ui_utils.py").write_text(UI_UTILS, encoding="utf-8")
    app_path = OUT / "app.pyw"
    app_path.write_text(patch_app(app_path.read_text(encoding="utf-8")), encoding="utf-8")

    asset_dir = OUT / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ICON_SOURCE, asset_dir / "app_icon.png.b64")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    # Regression: icon is a real transparent PNG, 128 x 128.
    encoded = (asset_dir / "app_icon.png.b64").read_text(encoding="ascii").strip()
    png = base64.b64decode(encoded, validate=True)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (128, 128)
    assert png[25] == 6, "PNG must be RGBA (color type 6)"

    app_text = app_path.read_text(encoding="utf-8")
    ui_text = (OUT / "ui_utils.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.7.4"' in app_text
    assert "maximize_window_on_pointer_monitor(self, self._startup_pointer)" in app_text
    assert "SetCurrentProcessExplicitAppUserModelID" in app_text
    assert 'app_icon.png.b64' in app_text
    assert "_header_icon_image" in app_text
    assert "MonitorFromPoint" in ui_text and 'window.state("zoomed")' in ui_text

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.7.4\n"
        "- Hlavní okno se při každém spuštění otevře maximalizované na monitoru, kde byl při startu kurzor myši.\n"
        "- Fungují i monitory vlevo nebo nad primárním monitorem se zápornými souřadnicemi.\n"
        "- Přidána nová průhledná ikona TURTO podle dodaného firemního loga.\n"
        "- Ikona se používá v titulkové liště, na hlavním panelu Windows i v hlavičce aplikace; v hlavičce je automaticky zmenšena.\n"
        "- Vlastní dialogy zůstávají otevírané nad rodičovským oknem na stejném monitoru.\n",
        encoding="utf-8",
    )

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_workspace.py", "ui_utils.py",
        "assets/app_icon.png.b64", "schoeck_archive_sources.json", "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.7.4/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "0.7.4",
        "notes": (
            "TURTO se nyní při startu vždy maximalizuje na monitoru pod kurzorem. "
            "Součástí aktualizace je také průhledná firemní ikona TURTO pro okno, hlavní panel a hlavičku programu."
        ),
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("v0.7.4 OK; startup monitor maximization + transparent TURTO icon")


if __name__ == "__main__":
    main()
