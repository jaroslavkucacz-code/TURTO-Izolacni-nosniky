from __future__ import annotations

"""Load the approved symbol in the real icon/header lifecycle, without Pillow."""
import base64
import logging
from pathlib import Path
import struct
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
import zlib

VERSION = "3.0.1"
LOGO_FILE = Path(__file__).resolve().with_name("turto_icon_301.png.b64")
LOG = logging.getLogger(__name__)


def logo_bytes():
    raw = base64.b64decode("".join(LOGO_FILE.read_text(encoding="ascii").split()), validate=True)
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Logo není PNG.")
    position, end, pixels = 8, False, bytearray()
    while position + 12 <= len(raw):
        length = struct.unpack_from(">I", raw, position)[0]
        kind = raw[position+4:position+8]
        stop = position + 12 + length
        if stop > len(raw):
            raise ValueError("Logo PNG je neúplné.")
        payload = raw[position+8:stop-4]
        if zlib.crc32(kind + payload) & 0xffffffff != struct.unpack_from(">I", raw, stop-4)[0]:
            raise ValueError("Logo PNG má poškozený blok.")
        if kind == b"IDAT":
            pixels.extend(payload)
        position = stop
        if kind == b"IEND":
            end = True
            break
    if not end or position != len(raw) or not pixels:
        raise ValueError("Logo PNG nemá platný konec.")
    zlib.decompress(pixels)
    return raw


def ico_bytes(square):
    """Encode 16/32px BMP-based ICO for native Windows, without image libraries."""
    images = []
    for size in (16, 32):
        pixels, mask = bytearray(), bytearray()
        stride = ((size + 31) // 32) * 4
        for y in reversed(range(size)):
            row = bytearray(stride)
            sy = min(square.height() - 1, y * square.height() // size)
            for x in range(size):
                sx = min(square.width() - 1, x * square.width() // size)
                r, g, b = square.get(sx, sy)
                transparent = square.transparency_get(sx, sy)
                pixels.extend((b, g, r, 0 if transparent else 255))
                if transparent:
                    row[x // 8] |= 128 >> (x % 8)
            mask.extend(row)
        header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                             len(pixels), 0, 0, 0, 0)
        images.append((size, header + pixels + mask))
    offset = 6 + 16 * len(images)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    for size, data in images:
        directory.extend(struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    return bytes(directory) + b"".join(data for size, data in images)


def native_icon(window):
    """Apply after the Windows wrapper HWND exists, not before initial mapping."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            ctypes.c_wchar_p("TURTO.Statika"))
        # Tcl/Tk loads both icon handles synchronously; the temporary file can
        # be removed immediately afterwards. No customer directories are written.
        with tempfile.TemporaryDirectory(prefix="turto_icon_301_") as folder:
            path = Path(folder) / "turto.ico"
            path.write_bytes(ico_bytes(window._turto_icon_square))
            window.iconbitmap(str(path))
            window.iconbitmap(default=str(path))
        window._turto_native_icon_loaded = True
        window._turto_logo_loaded = True
    except Exception:
        window._turto_native_icon_loaded = False
        window._turto_logo_loaded = False
        LOG.exception("TURTO 3.0.1: systémovou ikonu Windows nelze nastavit")


def install(base):
    cls = base.ThermalConnectorApp
    if getattr(cls, "_turto_branding_301", False):
        return
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TURTO.Statika")
        except Exception:
            LOG.exception("Nelze nastavit identitu ikony na hlavním panelu Windows")
    previous_icon = cls._set_icon
    previous_header = cls._build_header

    def set_icon(self):
        try:
            data = base64.b64encode(logo_bytes()).decode("ascii")
            logo = tk.PhotoImage(master=self, data=data, format="png")
            self._turto_logo_master = self._icon_image = logo
            self._header_icon_image = logo.subsample(2, 2)
            side = max(logo.width(), logo.height())
            square = tk.PhotoImage(master=self, width=side, height=side)
            self.tk.call(square, "copy", logo, "-to", (side-logo.width())//2, (side-logo.height())//2)
            self._turto_icon_square = square
            self._turto_icon_sizes = [square.subsample(k, k) for k in (1, 2, 4, 8)]
            self.iconphoto(True, *self._turto_icon_sizes)
            self._turto_logo_loaded = sys.platform != "win32"
            if sys.platform == "win32":
                self.after_idle(lambda: native_icon(self))
        except Exception:
            self._turto_logo_loaded = False
            LOG.exception("TURTO 3.0.1: logo nelze načíst")
            previous_icon(self)

    def header(self):
        previous_header(self)
        # Stable widget style and parent, not a title string which is changed
        # by several later workspace wrappers.
        for frame in self.winfo_children():
            if not isinstance(frame, ttk.Frame) or str(frame.cget("style")) != "Header.TFrame":
                continue
            for widget in frame.winfo_children():
                if isinstance(widget, ttk.Label) and str(widget.cget("style")) == "HeaderTitle.TLabel":
                    widget.configure(text="TURTO 3.0.1 | Izolační nosníky a smykové trny")
                    self._turto_brand_title = widget
        if getattr(self, "_turto_logo_master", None) is None:
            LOG.error("Záhlaví TURTO běží bez nové ikony; viz Logy.")

    cls._set_icon = set_icon
    cls._build_header = header
    cls._turto_branding_301 = True


def selftest():
    assert VERSION == "3.0.1"
    assert logo_bytes()
