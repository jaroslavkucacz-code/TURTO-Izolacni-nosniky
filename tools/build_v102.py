from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.0.1"
OUT = ROOT / "updates" / "1.0.2"


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
    text = replace_once(text, 'APP_NAME = "TURTO – Databáze izolačních nosníků"', 'APP_NAME = "TURTO ISO"', "app name")
    text = replace_once(text, 'APP_VERSION = "1.0.1"', 'APP_VERSION = "1.0.2"', "app version")
    text = replace_once(text, 'ctypes.c_wchar_p("TURTO.IzolacniNosniky")', 'ctypes.c_wchar_p("TURTO.ISO")', "windows app id")
    text = replace_once(text, 'text="TURTO | Databáze izolačních nosníků"', 'text="TURTO ISO | Databáze izolačních nosníků"', "header name")
    # Creator string is intentionally kept exact and regression-tested below.
    return text


def patch_workspace(text: str) -> str:
    text = replace_once(text, 'import webbrowser\nfrom pathlib import Path', 'import webbrowser\nfrom dataclasses import replace\nfrom pathlib import Path', "dataclasses import")
    text = replace_once(text, 'HIT_MODULE_VERSION = "1.0.1"', 'HIT_MODULE_VERSION = "1.0.2"', "module version")

    text = replace_once(
        text,
        '        self.connection_type = tk.StringVar(value=str(defaults.get("connection_type", "MVX")))\n        self.height = tk.StringVar',
        '        self.connection_type = tk.StringVar(value=str(defaults.get("connection_type", "MVX")))\n'
        '        self.mvx_variant = tk.StringVar(value=str(defaults.get("mvx_variant", "Bez")))\n'
        '        self.mvx_bx = tk.StringVar(value=str(defaults.get("mvx_bx", "")))\n'
        '        self.height = tk.StringVar',
        "MVX row variables",
    )

    text = replace_once(
        text,
        '        self.type_combo.bind("<<ComboboxSelected>>", self._type_changed)\n        entry(self.height, 8)\n',
        '        self.type_combo.bind("<<ComboboxSelected>>", self._type_changed)\n'
        '        self.mvx_variant_combo = combo(self.mvx_variant, ("Bez", "OU", "OD"), 7)\n'
        '        self.mvx_variant_combo.bind("<<ComboboxSelected>>", self._mvx_variant_changed)\n'
        '        self.mvx_bx_entry = entry(self.mvx_bx, 8)\n'
        '        entry(self.height, 8)\n',
        "MVX row widgets",
    )

    marker = '    def _apply_type_constraints(self) -> None:\n'
    insert = '''    def _apply_mvx_variant_state(self) -> None:\n        typ = self.connection_type.get().strip().upper()\n        is_mvx = typ == "MVX"\n        if is_mvx:\n            self.mvx_variant_combo.configure(state="readonly", style="TCombobox")\n        else:\n            self.mvx_variant_combo.configure(state="disabled", style="HitLocked.TCombobox")\n        variant = self.mvx_variant.get().strip().upper()\n        bx_active = is_mvx and variant in {"OU", "OD"}\n        self.mvx_bx_entry.configure(\n            state="normal" if bx_active else "disabled",\n            style="HitEditable.TEntry" if bx_active else "HitLocked.TEntry",\n        )\n\n    def _mvx_variant_changed(self, _event: Any = None) -> None:\n        self._manual_product = False\n        self._apply_mvx_variant_state()\n        self._input_changed_now()\n\n'''
    text = replace_once(text, marker, insert + marker, "MVX state methods")
    text = replace_once(
        text,
        '    def _apply_type_constraints(self) -> None:\n        self._apply_action_field_states()\n        self._apply_x_field_state()\n        self._apply_cover_field_state()\n',
        '    def _apply_type_constraints(self) -> None:\n        self._apply_action_field_states()\n        self._apply_x_field_state()\n        self._apply_cover_field_state()\n        self._apply_mvx_variant_state()\n',
        "MVX type constraints",
    )

    helper_marker = '\n\n    def recalculate(self, preserve_product: str | None = None) -> None:\n'
    helper = '''\n\n    def _mvx_candidates_for_row(self, database: HitDatabase, height: int, cover: int, actions: DirectionalActions, lengths: set[int], x_mm: float):\n        variant = self.mvx_variant.get().strip().upper()\n        if variant in {"", "BEZ"}:\n            return database.proposal_candidates(\n                "MVX", self.series.get(), height, cover, self.concrete.get(), actions, lengths,\n                False, load_distance_x=x_mm,\n            )\n        if variant not in {"OU", "OD"}:\n            return [], f"Neznámé provedení MVX: {variant}", {"preferred_type": "MVX", "mode": "preferred"}\n\n        bx_text = self.mvx_bx.get().strip()\n        if not bx_text:\n            return [], f"MVX-{variant}: zadejte bx [mm] – číslo se zapisuje přímo za {variant}, např. {variant}175.", {"preferred_type": "MVX", "mode": "preferred"}\n        try:\n            bx_float = float(bx_text.replace(",", "."))\n        except ValueError:\n            return [], f"MVX-{variant}: bx musí být celé číslo v mm.", {"preferred_type": "MVX", "mode": "preferred"}\n        bx = int(round(bx_float))\n        if abs(bx_float - bx) > 1e-9:\n            return [], f"MVX-{variant}: bx musí být celé číslo v mm.", {"preferred_type": "MVX", "mode": "preferred"}\n\n        series = self.series.get().strip().upper()\n        bx_max = 330 if series == "HP" else 290\n        if bx < 175 or bx > bx_max:\n            return [], (\n                f"MVX-{variant}: standardní katalogový rozsah bx je 175–{bx_max} mm pro HIT-{series}. "\n                "Větší geometrie je podle katalogu zákaznické řešení a program ji automaticky neodhaduje."\n            ), {"preferred_type": "MVX", "mode": "preferred"}\n\n        raw, error = database.directional_candidates(\n            "MVX", self.series.get(), height, cover, self.concrete.get(), actions, lengths,\n            True, load_distance_x=x_mm,\n        )\n        if error:\n            return [], error, {"preferred_type": "MVX", "mode": "preferred"}\n        chosen = []\n        for candidate in raw:\n            if candidate.suffix != variant:\n                continue\n            chosen.append(replace(\n                candidate,\n                suffix=f"{variant}{bx}",\n                mode=(\n                    f"{candidate.mode} • {variant} bx={bx} mm • "\n                    f"část tahového prutu na straně hlavní desky {bx - 20} mm"\n                ),\n            ))\n        info = {\n            "preferred_type": "MVX",\n            "primary_available": bool(chosen),\n            "alternative_type": "",\n            "alternative_count": 0,\n            "mode": "preferred",\n            "note": f"MVX-{variant}, bx={bx} mm",\n        }\n        return chosen, "", info\n'''
    text = replace_once(text, helper_marker, helper + helper_marker, "MVX proposal helper")

    old_call = '''        candidates, error, family_info = database.proposal_candidates(\n            self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), actions, lengths,\n            self.owner.hit_offsets_var.get(), load_distance_x=x_mm,\n        )\n'''
    new_call = '''        if self.connection_type.get().strip().upper() == "MVX":\n            candidates, error, family_info = self._mvx_candidates_for_row(database, height, cover, actions, lengths, x_mm)\n        else:\n            candidates, error, family_info = database.proposal_candidates(\n                self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), actions, lengths,\n                False, load_distance_x=x_mm,\n            )\n'''
    text = replace_once(text, old_call, new_call, "row proposal call")

    # Global offset switch is obsolete; MVX geometry is now explicitly per row.
    text = replace_once(text, '        self.hit_offsets_var = tk.BooleanVar(value=bool(state.get("include_offsets", False)))\n', '', "remove offset variable")
    text = replace_once(text, '        ttk.Checkbutton(toolbar, text="MVX: zahrnout OD/OU/WD/WU", variable=self.hit_offsets_var, command=self._hit_options_changed).grid(row=0, column=10, padx=(16, 0))\n', '', "remove offset checkbox")
    text = replace_once(text, '        state["include_offsets"] = bool(self.hit_offsets_var.get())\n', '', "remove offset setting")

    old_headers = '        headers = ("Označení", "Řada", "Typ", "h [mm]", "cnom", "Beton", "MEd+", "MEd−", "NEd+", "NEd−", "VEd+", "VEd−", "x [mm]", "Navržený výrobek ▼", "Varianty", "Využití", "a max", "Zdroj", "Stav / kontrola", "")\n'
    new_headers = '        headers = ("Označení", "Řada", "Typ", "MVX prov.", "bx [mm]", "h [mm]", "cnom", "Beton", "MEd+", "MEd−", "NEd+", "NEd−", "VEd+", "VEd−", "x [mm]", "Navržený výrobek ▼", "Varianty", "Využití", "a max", "Zdroj", "Stav / kontrola", "")\n'
    text = replace_once(text, old_headers, new_headers, "HIT headers")
    text = replace_once(text, 'anchor="w" if column in (0, 13, 18) else "center"', 'anchor="w" if column in (0, 15, 20) else "center"', "header anchors")
    text = replace_once(text, 'weight=1 if column in (0, 13, 18) else 0', 'weight=1 if column in (0, 15, 20) else 0', "header weights")

    help_old = 'Good/poor bond MVXL se volí automaticky podle h−cnom.'
    help_new = ('U MVX se provedení volí přímo v řádku jako Bez / OU / OD. Při OU/OD je bx povinné; číslo za OU/OD je bx [mm] a určuje délku části tahového prutu na straně hlavní desky bx−20 mm. '
                'Good/poor bond MVXL se volí automaticky podle h−cnom.')
    text = replace_once(text, help_old, help_new, "MVX help")

    old_defaults = '        return {"series": self.series.get(), "connection_type": self.connection_type.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med_pos": "", "med_neg": "", "ned_pos": "", "ned_neg": "", "ved_pos": "", "ved_neg": "", "load_x": ""}\n'
    new_defaults = '        return {"series": self.series.get(), "connection_type": self.connection_type.get(), "mvx_variant": self.mvx_variant.get(), "mvx_bx": self.mvx_bx.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med_pos": "", "med_neg": "", "ned_pos": "", "ned_neg": "", "ved_pos": "", "ved_neg": "", "load_x": ""}\n'
    text = replace_once(text, old_defaults, new_defaults, "row defaults")

    old_payload = '            "name": self.name.get().strip(), "series": self.series.get(), "connection_type": candidate.connection_type, "height_mm": candidate.height,\n            "cover_mm": candidate.cover, "concrete": candidate.concrete,\n'
    new_payload = '            "name": self.name.get().strip(), "series": self.series.get(), "connection_type": candidate.connection_type, "height_mm": candidate.height,\n            "cover_mm": candidate.cover, "concrete": candidate.concrete,\n            "mvx_variant": (self.mvx_variant.get().strip().upper() if candidate.connection_type == "MVX" else ""),\n            "mvx_bx_mm": (self.mvx_bx.get().strip() if candidate.connection_type == "MVX" and self.mvx_variant.get().strip().upper() in {"OU", "OD"} else ""),\n'
    text = replace_once(text, old_payload, new_payload, "future payload MVX geometry")

    old_copy_header = '        lines = ["Označení\\tŘada\\tTyp\\th [mm]\\tcnom [mm]\\tBeton\\tMEd+ [kNm/m]\\tMEd− [kNm/m]\\tNEd+ [kN/m]\\tNEd− [kN/m]\\tVEd+ [kN/m]\\tVEd− [kN/m]\\tx [mm]\\tNavržený výrobek\\tVyužití\\ta max [m]\\tZdroj\\tNRd\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2"]\n'
    new_copy_header = '        lines = ["Označení\\tŘada\\tTyp\\tMVX prov.\\tbx [mm]\\th [mm]\\tcnom [mm]\\tBeton\\tMEd+ [kNm/m]\\tMEd− [kNm/m]\\tNEd+ [kN/m]\\tNEd− [kN/m]\\tVEd+ [kN/m]\\tVEd− [kN/m]\\tx [mm]\\tNavržený výrobek\\tVyužití\\ta max [m]\\tZdroj\\tNRd\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2"]\n'
    text = replace_once(text, old_copy_header, new_copy_header, "copy header")
    old_copy_row = '            lines.append("\\t".join([row.name.get(), row.series.get(), candidate.connection_type, row.height.get(), row.cover.get(), row.concrete.get(), effective["m_pos"], effective["m_neg"], effective["n_pos"], effective["n_neg"], effective["v_pos"], effective["v_neg"], (fmt(candidate.load_distance_x,0) if candidate.load_distance_x else ""), candidate.designation, ("" if candidate.spacing_max > 0 else fmt(candidate.utilization * 100.0) + " %"), (fmt(candidate.spacing_max,3) if candidate.spacing_max > 0 else ""), str(candidate.page), fmt(candidate.nrd), fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2)]))\n'
    new_copy_row = '            lines.append("\\t".join([row.name.get(), row.series.get(), candidate.connection_type, (row.mvx_variant.get() if candidate.connection_type == "MVX" else ""), (row.mvx_bx.get() if candidate.connection_type == "MVX" and row.mvx_variant.get().strip().upper() in {"OU", "OD"} else ""), row.height.get(), row.cover.get(), row.concrete.get(), effective["m_pos"], effective["m_neg"], effective["n_pos"], effective["n_neg"], effective["v_pos"], effective["v_neg"], (fmt(candidate.load_distance_x,0) if candidate.load_distance_x else ""), candidate.designation, ("" if candidate.spacing_max > 0 else fmt(candidate.utilization * 100.0) + " %"), (fmt(candidate.spacing_max,3) if candidate.spacing_max > 0 else ""), str(candidate.page), fmt(candidate.nrd), fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2)]))\n'
    text = replace_once(text, old_copy_row, new_copy_row, "copy row")

    return text


def patch_icon(path: Path) -> None:
    encoded = path.read_text(encoding="ascii").strip()
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
            font = ImageFont.truetype(candidate, 13)
            break
        except OSError:
            pass
    if font is None:
        font = ImageFont.load_default()
    gold = (212, 175, 55, 255)  # #D4AF37
    bbox = draw.textbbox((0, 0), "ISO", font=font, stroke_width=1)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = max(1, 63 - width)
    y = max(1, 62 - height)
    draw.text((x, y), "ISO", font=font, fill=gold, stroke_width=1, stroke_fill=(22, 26, 30, 230))

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    path.write_text(base64.b64encode(out.getvalue()).decode("ascii"), encoding="ascii")

    verify = Image.open(io.BytesIO(out.getvalue())).convert("RGBA")
    assert verify.size == (64, 64)
    assert sum(1 for p in verify.getdata() if p[3] == 0) > 0, "icon transparency lost"
    assert alpha_before > 0, "source icon was unexpectedly opaque"
    assert sum(1 for p in verify.getdata() if p[0] > 190 and 130 < p[1] < 210 and p[2] < 100 and p[3] > 200) >= 5, "gold ISO text missing"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    app = OUT / "app.pyw"
    app.write_text(patch_app(app.read_text(encoding="utf-8")), encoding="utf-8")

    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    patch_icon(OUT / "assets" / "app_icon.png.b64")
    compile_sources(OUT)

    app_text = app.read_text(encoding="utf-8")
    ws = workspace.read_text(encoding="utf-8")
    assert 'APP_NAME = "TURTO ISO"' in app_text
    assert 'APP_VERSION = "1.0.2"' in app_text
    assert 'CREATOR = "Vytvořil Ing. Jaroslav Kučera"' in app_text
    assert 'text="TURTO ISO | Databáze izolačních nosníků"' in app_text
    assert 'HIT_MODULE_VERSION = "1.0.2"' in ws
    assert '("Bez", "OU", "OD")' in ws
    assert 'bx_max = 330 if series == "HP" else 290' in ws
    assert 'suffix=f"{variant}{bx}"' in ws
    assert 'část tahového prutu na straně hlavní desky {bx - 20} mm' in ws
    assert 'hit_offsets_var' not in ws
    assert 'MVX: zahrnout OD/OU/WD/WU' not in ws
    assert '"MVX prov.", "bx [mm]"' in ws
    assert not any(OUT.rglob("*.pyc"))
    assert not any(p.name == "__pycache__" for p in OUT.rglob("__pycache__"))

    # Designation regression: the selected geometry number must remain part of the type.
    import sys
    sys.path.insert(0, str(OUT))
    import hit_core as hc
    c = hc.Candidate("HP", "MVX", "0201", 50, "OU175", 165, "C25/30", -10, 20, -15, 5, 55, 35, 200, 0.5, "test")
    assert c.designation == "HIT-HP MVX-0201-20-050-35-OU175"

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.0.2\n"
        "- Aplikace se nově jmenuje TURTO ISO; autor zůstává Vytvořil Ing. Jaroslav Kučera.\n"
        "- Průhledná TURTO ikona dostala zlatý nápis ISO.\n"
        "- Zrušen globální přepínač MVX OD/OU/WD/WU. Provedení MVX se volí v každém řádku jako Bez / OU / OD.\n"
        "- Pro OU/OD je povinné bx [mm]. Číslo se stává součástí označení, např. OU175 / OD200.\n"
        "- bx je kontrolováno v katalogovém standardním rozsahu 175–330 mm pro HP a 175–290 mm pro SP; mimo rozsah program neextrapoluje.\n"
        "- Detail návrhu zobrazuje také délku části tahového prutu na straně hlavní desky bx−20 mm.\n"
        "- Standardní MVX (Bez) zachovává vazbu MVX ↔ MVXL; explicitní OU/OD se neposílá do MVXL fallbacku, protože by se ztratila geometrie výškového odsazení.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.0.2/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.0.2",
        "notes": "TURTO ISO: MVX Bez/OU/OD po řádcích, povinné bx v označení a nová průhledná ikona se zlatým ISO.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.0.2")


if __name__ == "__main__":
    main()
