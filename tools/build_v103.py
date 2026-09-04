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
BASE = ROOT / "updates" / "1.0.2"
ORIGINAL_ICON = ROOT / "updates" / "1.0.1" / "assets" / "app_icon.png.b64"
OUT = ROOT / "updates" / "1.0.3"


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


def patch_workspace(text: str) -> str:
    text = replace_once(text, 'HIT_MODULE_VERSION = "1.0.2"', 'HIT_MODULE_VERSION = "1.0.3"', "module version")

    marker = '''def hit_action_field_mask(connection_type: str) -> dict[str, bool]:\n    # Neznámý budoucí typ je bezpečně uzamčený, dokud mu výslovně neurčíme směry.\n    return dict(HIT_ACTION_FIELD_MASKS.get(str(connection_type or "").upper(), {key: False for key in HIT_ACTION_META}))\n\n\n'''
    helper = marker + '''def mvx_bx_limits(series: str) -> tuple[int, int]:\n    """Standardní katalogový rozsah bx pro HIT MVX-OU/OD.\n\n    HIT 20.2 uvádí pro standardní provedení HP 175..330 mm a SP\n    175..290 mm. Katalog zároveň výslovně používá bx=175 mm jako příklad\n    a vztah pro délku tahového prutu potvrzuje krajní hodnoty.\n    """\n    return 175, (290 if str(series).strip().upper() == "SP" else 330)\n\n\ndef mvx_bx_is_standard(series: str, bx_mm: int) -> bool:\n    bx_min, bx_max = mvx_bx_limits(series)\n    return bx_min <= int(bx_mm) <= bx_max\n\n\n'''
    text = replace_once(text, marker, helper, "bx limit helpers")

    text = replace_once(
        text,
        '        combo(self.series, ("HP", "SP"), 6)\n        self.type_combo = combo(self.connection_type, CONNECTION_TYPES, 7)\n',
        '        self.series_combo = combo(self.series, ("HP", "SP"), 6)\n'
        '        self.series_combo.bind("<<ComboboxSelected>>", self._series_changed)\n'
        '        self.type_combo = combo(self.connection_type, CONNECTION_TYPES, 7)\n',
        "series combo handler",
    )

    text = replace_once(
        text,
        '        self.mvx_bx_entry = entry(self.mvx_bx, 8)\n        entry(self.height, 8)\n',
        '        self.mvx_bx_entry = entry(self.mvx_bx, 8)\n'
        '        self.mvx_bx_entry.configure(\n'
        '            validate="key",\n'
        '            validatecommand=(parent.register(self._validate_mvx_bx_keystroke), "%P"),\n'
        '        )\n'
        '        self.mvx_bx_entry.bind("<FocusOut>", self._mvx_bx_finished)\n'
        '        self.mvx_bx_entry.bind("<Return>", self._mvx_bx_finished)\n'
        '        entry(self.height, 8)\n',
        "bx input hard validation",
    )

    state_marker = '    def _apply_mvx_variant_state(self) -> None:\n'
    state_helpers = '''    def _validate_mvx_bx_keystroke(self, proposed: str) -> bool:\n        # Při psaní dovolíme prázdnou hodnotu a rozpracované číslo pod minimem,\n        # ale nikdy nedovolíme překročit horní katalogovou mez ani zadat nečíselný znak.\n        value = str(proposed).strip()\n        if value == "":\n            return True\n        if not value.isdigit():\n            return False\n        _bx_min, bx_max = mvx_bx_limits(self.series.get())\n        return int(value) <= bx_max\n\n    def _normalize_mvx_bx(self, fill_default: bool = False) -> None:\n        typ = self.connection_type.get().strip().upper()\n        variant = self.mvx_variant.get().strip().upper()\n        if typ != "MVX" or variant not in {"OU", "OD"}:\n            return\n        bx_min, bx_max = mvx_bx_limits(self.series.get())\n        raw = self.mvx_bx.get().strip()\n        if not raw:\n            if fill_default:\n                self.mvx_bx.set(str(bx_min))\n            return\n        try:\n            bx = int(raw)\n        except ValueError:\n            self.mvx_bx.set(str(bx_min))\n            return\n        if bx < bx_min:\n            self.mvx_bx.set(str(bx_min))\n        elif bx > bx_max:\n            self.mvx_bx.set(str(bx_max))\n\n    def _mvx_bx_finished(self, _event: Any = None) -> None:\n        self._manual_product = False\n        self._normalize_mvx_bx(fill_default=True)\n        self._input_changed_now()\n\n    def _series_changed(self, _event: Any = None) -> None:\n        self._manual_product = False\n        # HP -> SP může snížit horní mez z 330 na 290 mm; existující bx proto\n        # ihned stáhneme na platný standardní rozsah místo ponechání neplatné hodnoty.\n        self._normalize_mvx_bx(fill_default=False)\n        self._input_changed_now()\n\n'''
    text = replace_once(text, state_marker, state_helpers + state_marker, "bx validation methods")

    text = replace_once(
        text,
        '        bx_active = is_mvx and variant in {"OU", "OD"}\n        self.mvx_bx_entry.configure(\n',
        '        bx_active = is_mvx and variant in {"OU", "OD"}\n'
        '        if bx_active and not self.mvx_bx.get().strip():\n'
        '            self._normalize_mvx_bx(fill_default=True)\n'
        '        self.mvx_bx_entry.configure(\n',
        "default bx on OU OD",
    )

    text = replace_once(
        text,
        '        series = self.series.get().strip().upper()\n        bx_max = 330 if series == "HP" else 290\n        if bx < 175 or bx > bx_max:\n            return [], (\n                f"MVX-{variant}: standardní katalogový rozsah bx je 175–{bx_max} mm pro HIT-{series}. "\n',
        '        series = self.series.get().strip().upper()\n'
        '        bx_min, bx_max = mvx_bx_limits(series)\n'
        '        if not mvx_bx_is_standard(series, bx):\n'
        '            return [], (\n'
        '                f"MVX-{variant}: standardní katalogový rozsah bx je {bx_min}–{bx_max} mm pro HIT-{series}. "\n',
        "use shared bx limits",
    )

    text = replace_once(
        text,
        'U MVX se provedení volí přímo v řádku jako Bez / OU / OD. Při OU/OD je bx povinné; číslo za OU/OD je bx [mm] a určuje délku části tahového prutu na straně hlavní desky bx−20 mm. ',
        'U MVX se provedení volí přímo v řádku jako Bez / OU / OD. Při OU/OD je bx povinné; číslo za OU/OD je bx [mm] a určuje délku části tahového prutu na straně hlavní desky bx−20 mm. Pole bx nepustí hodnotu nad katalogové maximum a po dokončení vstupu drží standardní rozsah 175–330 mm (HP), resp. 175–290 mm (SP). ',
        "bx help text",
    )
    return text


def patch_icon(destination: Path) -> None:
    # Vycházíme z čisté průhledné TURTO ikony před prvním malým nápisem ISO,
    # aby ve výsledku nebyly dvě vrstvy textu.
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
    y = (64 - height) // 2 - bbox[1]
    # Velký zlatý nápis přes střed loga; tmavý obrys drží čitelnost i na hlavním panelu Windows.
    draw.text((x, y), "ISO", font=font, fill=gold, stroke_width=2, stroke_fill=(18, 22, 26, 245))

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    destination.write_text(base64.b64encode(out.getvalue()).decode("ascii"), encoding="ascii")

    verify = Image.open(io.BytesIO(out.getvalue())).convert("RGBA")
    assert verify.size == (64, 64)
    assert sum(1 for p in verify.getdata() if p[3] == 0) > 0, "icon transparency lost"
    assert alpha_before > 0, "source icon was unexpectedly opaque"
    gold_pixels = sum(1 for p in verify.getdata() if p[0] > 190 and 130 < p[1] < 210 and p[2] < 100 and p[3] > 200)
    assert gold_pixels >= 80, f"large gold ISO text missing ({gold_pixels} pixels)"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    app = OUT / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    app_text = replace_once(app_text, 'APP_VERSION = "1.0.2"', 'APP_VERSION = "1.0.3"', "app version")
    app.write_text(app_text, encoding="utf-8")

    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    patch_icon(OUT / "assets" / "app_icon.png.b64")
    compile_sources(OUT)

    ws = workspace.read_text(encoding="utf-8")
    assert 'HIT_MODULE_VERSION = "1.0.3"' in ws
    assert 'def mvx_bx_limits' in ws
    assert 'return 175, (290 if str(series).strip().upper() == "SP" else 330)' in ws
    assert 'validatecommand=(parent.register(self._validate_mvx_bx_keystroke), "%P")' in ws
    assert 'self._normalize_mvx_bx(fill_default=False)' in ws
    assert 'if not mvx_bx_is_standard(series, bx):' in ws
    assert not any(OUT.rglob("*.pyc"))
    assert not any(p.name == "__pycache__" for p in OUT.rglob("__pycache__"))

    # Pure regression of the hard standard bx bounds.
    namespace: dict[str, object] = {}
    exec(
        'def mvx_bx_limits(series):\n    return 175, (290 if str(series).strip().upper() == "SP" else 330)\n'
        'def mvx_bx_is_standard(series,bx):\n    lo,hi=mvx_bx_limits(series); return lo <= int(bx) <= hi\n',
        namespace,
    )
    check = namespace["mvx_bx_is_standard"]
    assert check("HP", 175) and check("HP", 330) and not check("HP", 331)
    assert check("SP", 175) and check("SP", 290) and not check("SP", 291)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.0.3\n"
        "- MVX-OU/OD: bx je nyní hard-limitované přímo ve vstupním poli; nelze zadat hodnotu nad katalogové maximum.\n"
        "- Standardní rozsah bx: HIT-HP 175–330 mm, HIT-SP 175–290 mm; po změně HP/SP se existující bx automaticky stáhne do platného rozsahu.\n"
        "- Při nové volbě OU/OD se prázdné bx předvyplní hodnotou 175 mm. Hodnoty pod minimem se po dokončení vstupu upraví na 175 mm.\n"
        "- Statická kontrola bx zůstává i ve výpočtovém resolveru jako druhá bezpečnostní pojistka; nestandardní větší geometrie se automaticky nenavrhuje.\n"
        "- Ikona TURTO ISO má výrazně větší zlatý nápis ISO přes střed původního loga pro lepší rozlišení více TURTO aplikací na hlavním panelu.\n"
        "- Název aplikace zůstává TURTO ISO; Vytvořil Ing. Jaroslav Kučera.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.0.3/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.0.3",
        "notes": "TURTO ISO: hard-limit bx pro MVX-OU/OD a výrazně větší zlaté ISO přes ikonu.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.0.3")


if __name__ == "__main__":
    main()
