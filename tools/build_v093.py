from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.9.2"
OUT = ROOT / "updates" / "0.9.3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def patch_workspace(text: str) -> str:
    text = replace_once(text, 'HIT_MODULE_VERSION = "0.5.1"', 'HIT_MODULE_VERSION = "0.5.2"', "module version")

    old_help = '''        ttk.Label(\n            outer,\n            text="První řádek je automaticky doporučená varianta. Dvojklikem nebo tlačítkem Použít variantu vyberete jiný vyhovující prvek.",\n            style="Muted.TLabel",\n        ).grid(row=2, column=0, sticky="w", pady=(0, 10))\n'''
    new_help = '''        economy_hint = (\n            row.connection_type.get().strip().upper() == "MVXL"\n            and row._family_info.get("mode") == "related"\n            and int(row._family_info.get("alternative_count", 0) or 0) > 0\n        )\n        help_text = (\n            "⚠ MVXL vyhovuje, ale vyhovuje i MVX. Bez cenové databáze je MVX označen jako možná úspornější alternativa; porovnejte varianty."\n            if economy_hint\n            else "První řádek je automaticky doporučená varianta. Dvojklikem nebo tlačítkem Použít variantu vyberete jiný vyhovující prvek."\n        )\n        ttk.Label(\n            outer,\n            text=help_text,\n            style="HitEconomy.TLabel" if economy_hint else "Muted.TLabel",\n        ).grid(row=2, column=0, sticky="ew", pady=(0, 10))\n'''
    text = replace_once(text, old_help, new_help, "variants economy help")

    old_tree = '''        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)\n        self.tree.grid(row=0, column=0, sticky="nsew")\n'''
    new_tree = '''        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)\n        economy_bg = "#FFF1C2" if getattr(parent, "theme_name", "light") == "light" else "#4A4126"\n        self.tree.tag_configure("economy_alt", background=economy_bg)\n        self.tree.grid(row=0, column=0, sticky="nsew")\n'''
    text = replace_once(text, old_tree, new_tree, "tree economy tag")

    old_rank = '''            if candidate.connection_type != preferred_type:\n                rank = "1 • náhrada" if index == 1 else ("náhrada" if not row._family_info.get("primary_available") else "alternativa")\n            else:\n                rank = "1 • preferovaný" if index == 1 else str(index)\n            self.tree.insert(\n                "", "end", iid=iid,\n                values=(\n'''
    new_rank = '''            if candidate.connection_type != preferred_type:\n                rank = "1 • náhrada" if index == 1 else ("náhrada" if not row._family_info.get("primary_available") else "alternativa")\n            else:\n                rank = "1 • preferovaný" if index == 1 else str(index)\n            row_tags = ("economy_alt",) if (preferred_type == "MVXL" and candidate.connection_type == "MVX") else ()\n            self.tree.insert(\n                "", "end", iid=iid, tags=row_tags,\n                values=(\n'''
    text = replace_once(text, old_rank, new_rank, "economy alternative tree rows")

    old_button = '''        alt_type = str(self._family_info.get("alternative_type", ""))\n        alt_count = int(self._family_info.get("alternative_count", 0) or 0)\n        button_text = f"Varianty… +{alt_type}" if alt_count else "Varianty…"\n        self.variants_button.configure(text=button_text, width=14, state="normal" if len(candidates) > 1 else "disabled")\n'''
    new_button = '''        alt_type = str(self._family_info.get("alternative_type", ""))\n        alt_count = int(self._family_info.get("alternative_count", 0) or 0)\n        economy_attention = (\n            self.connection_type.get().strip().upper() == "MVXL"\n            and alt_type == "MVX"\n            and alt_count > 0\n            and bool(self._family_info.get("primary_available"))\n        )\n        button_text = "⚠ Varianty… +MVX" if economy_attention else (f"Varianty… +{alt_type}" if alt_count else "Varianty…")\n        self.variants_button.configure(text=button_text, width=16 if economy_attention else 14, state="normal" if len(candidates) > 1 else "disabled")\n'''
    text = replace_once(text, old_button, new_button, "economy variant button")

    old_show = '''    def _show_candidate(self, candidate: Candidate) -> None:\n        self.util.set(fmt(candidate.utilization * 100.0) + " %")\n        self.page.set(str(candidate.page))\n        text = f"{len(self.candidates)} variant • {candidate.mode}"\n'''
    new_show = '''    def _show_candidate(self, candidate: Candidate) -> None:\n        self.util.set(fmt(candidate.utilization * 100.0) + " %")\n        self.page.set(str(candidate.page))\n        self.detail_label.configure(style="MutedCard.TLabel")\n        text = f"{len(self.candidates)} variant • {candidate.mode}"\n'''
    text = replace_once(text, old_show, new_show, "reset detail style")

    old_related = '''        elif self._family_info.get("mode") == "related":\n            text += " • vyhovuje také MVX – viz Varianty…"\n'''
    new_related = '''        elif self._family_info.get("mode") == "related":\n            text += " • ⚠ VYHOVUJE I MVX – zvažte jednodušší / možná úspornější variantu"\n            self.detail_label.configure(style="HitEconomy.TLabel")\n'''
    text = replace_once(text, old_related, new_related, "economy row emphasis")

    old_error = '''        self.page.set("—")\n        self.detail.set(text)\n        self.owner.update_hit_status()\n'''
    new_error = '''        self.page.set("—")\n        self.detail_label.configure(style="MutedCard.TLabel")\n        self.detail.set(text)\n        self.owner.update_hit_status()\n'''
    text = replace_once(text, old_error, new_error, "error style reset")

    old_wait = '''            self.page.set("—")\n            self.detail.set("čeká na MEd / VEd")\n            self.owner.update_hit_status()\n'''
    new_wait = '''            self.page.set("—")\n            self.detail_label.configure(style="MutedCard.TLabel")\n            self.detail.set("čeká na MEd / VEd")\n            self.owner.update_hit_status()\n'''
    text = replace_once(text, old_wait, new_wait, "waiting style reset")

    old_style_end = '''        self.style.map(\n            "HitLocked.TCombobox",\n            fieldbackground=[("disabled", locked_bg)],\n            background=[("disabled", locked_bg)],\n            foreground=[("disabled", self.colors["muted"])],\n            selectbackground=[("disabled", locked_bg)],\n            selectforeground=[("disabled", self.colors["muted"])],\n        )\n        self._hit_built = True\n'''
    new_style_end = '''        self.style.map(\n            "HitLocked.TCombobox",\n            fieldbackground=[("disabled", locked_bg)],\n            background=[("disabled", locked_bg)],\n            foreground=[("disabled", self.colors["muted"])],\n            selectbackground=[("disabled", locked_bg)],\n            selectforeground=[("disabled", self.colors["muted"])],\n        )\n        economy_bg = "#FFF1C2" if getattr(self, "theme_name", "light") == "light" else "#4A4126"\n        economy_fg = "#6B5200" if getattr(self, "theme_name", "light") == "light" else "#FFE7A3"\n        self.style.configure(\n            "HitEconomy.TLabel",\n            background=economy_bg,\n            foreground=economy_fg,\n            padding=(7, 4),\n            font=("Calibri", 10, "bold"),\n        )\n        self._hit_built = True\n'''
    text = replace_once(text, old_style_end, new_style_end, "economy label style")

    old_footer = 'Výška v označení HIT je v cm: 200 mm → 20."), style="Muted.TLabel"'
    new_footer = 'Výška v označení HIT je v cm: 200 mm → 20. Cenové doporučení zatím není aktivní: program nejprve hlídá statickou použitelnost a cenu budeme později používat až pro pořadí mezi technicky vyhovujícími variantami."), style="Muted.TLabel"'
    text = replace_once(text, old_footer, new_footer, "future pricing help")
    return text


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    app = OUT / "app.pyw"
    app_text = replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "0.9.2"', 'APP_VERSION = "0.9.3"', "app version")
    app.write_text(app_text, encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    ws = workspace.read_text(encoding="utf-8")
    assert 'HIT_MODULE_VERSION = "0.5.2"' in ws
    assert '⚠ VYHOVUJE I MVX' in ws
    assert 'HitEconomy.TLabel' in ws
    assert '⚠ Varianty… +MVX' in ws
    assert 'economy_alt' in ws
    assert 'Cenové doporučení zatím není aktivní' in ws

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.9.3\n"
        "- Pokud je zvolen MVXL a současně vyhovuje i MVX, řádek je nyní výrazně, ale nekřiklavě označen jako možná úspornější alternativa.\n"
        "- Stav / kontrola dostane jantarové zvýraznění a text 'VYHOVUJE I MVX'.\n"
        "- Tlačítko se změní na '⚠ Varianty… +MVX' a v okně Varianty jsou MVX alternativy podbarvené.\n"
        "- Bez cenové databáze program netvrdí, že MVX je levnější; pouze upozorní na technicky jednodušší alternativu.\n"
        "- Architektura doporučení zůstává připravena na budoucí cenové pořadí: nejdřív statická použitelnost, potom cena mezi vyhovujícími kandidáty.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.9.3/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.9.3",
        "notes": "HIT: výraznější upozornění na vyhovující MVX u zvoleného MVXL; příprava logiky pro budoucí cenové pořadí technicky vyhovujících variant.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v0.9.3")


if __name__ == "__main__":
    main()
