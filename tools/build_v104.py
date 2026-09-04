from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.0.3"
# Čistá průhledná TURTO ikona před doplněním ISO.
ORIGINAL_ICON = ROOT / "updates" / "1.0.1" / "assets" / "app_icon.png.b64"
OUT = ROOT / "updates" / "1.0.4"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def compile_sources(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.suffix not in {".py", ".pyw"}:
            continue
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def patch_app(text: str) -> str:
    text = replace_once(text, 'APP_VERSION = "1.0.3"', 'APP_VERSION = "1.0.4"', "app version")

    # Autor už nebude schovaný v dlouhém horním podtitulu; bude trvale viditelný dole.
    text = replace_once(
        text,
        '            text=f"Projektový soupis a rychlé vyhledání statických hodnot podle výrobce, generace a úplného typu • {CREATOR}",\n',
        '            text="Projektový soupis a rychlé vyhledání statických hodnot podle výrobce, generace a úplného typu",\n',
        "remove creator from header subtitle",
    )

    text = replace_once(
        text,
        '        self.style.configure("Status.TLabel", background=c["header"], foreground="#D7E3ED", font=("Calibri", 9))\n',
        '        self.style.configure("Status.TLabel", background=c["header"], foreground="#D7E3ED", font=("Calibri", 9))\n'
        '        self.style.configure("CreatorStatus.TLabel", background=c["header"], foreground="#D4AF37", font=("Calibri", 9, "bold"))\n',
        "creator footer style",
    )

    text = replace_once(
        text,
        '        bar.columnconfigure(0, weight=1)\n'
        '        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")\n'
        '        ttk.Button(bar, text="Aktualizace", command=self._check_updates).grid(row=0, column=1, padx=(12, 12))\n',
        '        bar.columnconfigure(0, weight=1)\n'
        '        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")\n'
        '        ttk.Label(bar, text=CREATOR, style="CreatorStatus.TLabel").grid(row=0, column=1, padx=(18, 14))\n'
        '        ttk.Button(bar, text="Aktualizace", command=self._check_updates).grid(row=0, column=2, padx=(0, 12))\n',
        "creator footer layout",
    )
    text = replace_once(
        text,
        '        ttk.Label(bar, text=right, style="Status.TLabel").grid(row=0, column=2, sticky="e")\n',
        '        ttk.Label(bar, text=right, style="Status.TLabel").grid(row=0, column=3, sticky="e")\n',
        "status right column",
    )
    return text


def patch_icon(destination: Path) -> None:
    encoded = ORIGINAL_ICON.read_text(encoding="ascii").strip()
    image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGBA")
    if image.size != (64, 64):
        image.thumbnail((64, 64), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((64 - image.width) // 2, (64 - image.height) // 2))
        image = canvas

    alpha_before = sum(1 for p in image.getdata() if p[3] == 0)
    draw = ImageDraw.Draw(image)
    font = None
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ):
        try:
            font = ImageFont.truetype(candidate, 27)
            break
        except OSError:
            pass
    if font is None:
        font = ImageFont.load_default()

    gold = (212, 175, 55, 255)  # #D4AF37
    bbox = draw.textbbox((0, 0), "ISO", font=font, stroke_width=2)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = (64 - width) // 2 - bbox[0]
    # Stejná velikost jako v1.0.3, ale o 8 px výš pro lepší čitelnost přes TURTO logo.
    y = max(1, (64 - height) // 2 - bbox[1] - 8)
    draw.text((x, y), "ISO", font=font, fill=gold, stroke_width=2, stroke_fill=(18, 22, 26, 245))

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    destination.write_text(base64.b64encode(out.getvalue()).decode("ascii"), encoding="ascii")

    verify = Image.open(io.BytesIO(out.getvalue())).convert("RGBA")
    assert verify.size == (64, 64)
    assert sum(1 for p in verify.getdata() if p[3] == 0) > 0, "icon transparency lost"
    assert alpha_before > 0, "source icon was unexpectedly opaque"
    gold_points = [
        (x, y)
        for y in range(verify.height)
        for x in range(verify.width)
        if (lambda p: p[0] > 190 and 130 < p[1] < 210 and p[2] < 100 and p[3] > 200)(verify.getpixel((x, y)))
    ]
    assert len(gold_points) >= 80, f"large gold ISO text missing ({len(gold_points)} pixels)"
    avg_y = sum(y for _x, y in gold_points) / len(gold_points)
    assert avg_y < 29.0, f"ISO text was not moved upward enough (average y={avg_y:.1f})"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    app = OUT / "app.pyw"
    app.write_text(patch_app(app.read_text(encoding="utf-8")), encoding="utf-8")
    patch_icon(OUT / "assets" / "app_icon.png.b64")
    compile_sources(OUT)

    app_text = app.read_text(encoding="utf-8")
    assert 'APP_NAME = "TURTO ISO"' in app_text
    assert 'APP_VERSION = "1.0.4"' in app_text
    assert 'CREATOR = "Vytvořil Ing. Jaroslav Kučera"' in app_text
    assert 'CreatorStatus.TLabel' in app_text
    assert 'ttk.Label(bar, text=CREATOR, style="CreatorStatus.TLabel")' in app_text
    assert 'úplného typu • {CREATOR}' not in app_text
    assert not any(OUT.rglob("*.pyc"))
    assert not any(p.name == "__pycache__" for p in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.0.4\n"
        "- Zlatý text ISO v ikoně zůstává stejně velký jako ve v1.0.3, ale je posunut o 8 px výše pro lepší rozlišení aplikace na hlavním panelu.\n"
        "- Text Vytvořil Ing. Jaroslav Kučera je přesunut z horního podtitulu do trvale viditelné spodní stavové lišty.\n"
        "- Autor je ve spodní liště zvýrazněn decentní zlatou barvou a tučným Calibri, vedle stavu programu, aktualizace a verze/databázových statistik.\n"
        "- Název aplikace zůstává TURTO ISO.\n",
        encoding="utf-8",
    )

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_special.py", "hit_workspace.py", "ui_utils.py",
        "assets/app_icon.png.b64", "schoeck_archive_sources.json", "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.0.4/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    manifest = {
        "version": "1.0.4",
        "notes": "TURTO ISO: ISO posunuto výš v ikoně a autor trvale přesunut do spodní stavové lišty.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.0.4")


if __name__ == "__main__":
    main()
