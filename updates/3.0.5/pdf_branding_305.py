from __future__ import annotations

"""Standard TURTO company logo for PDF only; application branding stays separate."""

import base64
import hashlib
import io
from pathlib import Path

VERSION = "3.0.5"
LOGO_FILE = "turto_pdf_logo_305.png.b64"
# Exact, unmodified LOGO - TURTO(1).png supplied by the user.
LOGO_SHA256 = "303ea4c6a931e112ba8bc1526d9bc72eb7b085745fa6aa26e5060b9c8671f05b"


def logo_bytes() -> bytes:
    encoded = (Path(__file__).resolve().parent / LOGO_FILE).read_bytes()
    data = base64.b64decode(b"".join(encoded.split()), validate=True)
    if hashlib.sha256(data).hexdigest() != LOGO_SHA256:
        raise ValueError("Nesouhlasí kontrolní součet firemního loga TURTO pro PDF.")
    return data


def _load_logo(self):
    from reportlab.lib.utils import ImageReader
    from hit_pdf import PdfExportError

    try:
        image = ImageReader(io.BytesIO(logo_bytes()))
        width, height = image.getSize()
        if width <= 0 or height <= 0:
            raise ValueError("Neplatné rozměry loga.")
        image.getRGBData()  # Validate the pixels before opening the output file.
        return image
    except Exception as exc:
        raise PdfExportError(
            "Nelze načíst firemní logo TURTO pro PDF. Dokončete aktualizaci programu.\n"
            + str(exc)
        ) from exc


def _draw_logo(self, canvas):
    width, height = self.logo.getSize()
    scale = min(69.0 / width, 64.0 / height)
    width, height = width * scale, height * scale
    canvas.drawImage(
        self.logo,
        self.margin + (69.0 - width) / 2,
        self.h - 15.0 - height,
        width=width,
        height=height,
        preserveAspectRatio=True,
        mask="auto",
    )


def install() -> None:
    import hit_pdf
    import pdf_data_304

    # Cover both the shared AKCE/design renderer and the original substitution
    # entry point. Neither may depend on the old vector asset or GUI symbol.
    hit_pdf._base._Report._load_logo = _load_logo
    hit_pdf._base._Report.logo_draw = _draw_logo
    hit_pdf._ProposalReport.logo_draw = _draw_logo
    pdf_data_304.VERSION = VERSION
    hit_pdf._turto_pdf_branding_305 = True


def selftest() -> None:
    assert logo_bytes().startswith(b"\x89PNG\r\n\x1a\n")
