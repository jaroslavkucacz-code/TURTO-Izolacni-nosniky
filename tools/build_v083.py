from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.8.2"
OUT = ROOT / "updates" / "0.8.3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def patch_workspace(text: str) -> str:
    text = replace_once(text, 'HIT_MODULE_VERSION = "0.4.2"', 'HIT_MODULE_VERSION = "0.4.3"', "module version")

    old_meta = '''HIT_ACTION_META = {
    "m_pos": ("MEd+", "kNm/m"),
    "m_neg": ("MEd−", "kNm/m"),
    "v_pos": ("VEd+", "kN/m"),
    "v_neg": ("VEd−", "kN/m"),
}


def hit_action_field_mask'''
    new_meta = '''HIT_ACTION_META = {
    "m_pos": ("MEd+", "kNm/m"),
    "m_neg": ("MEd−", "kNm/m"),
    "v_pos": ("VEd+", "kN/m"),
    "v_neg": ("VEd−", "kN/m"),
}

# Typy, u kterých katalog nepřipouští volbu krytí. Hodnota je přímo kód cnom v mm.
# Annex 3 vede ZVX/ZDX výhradně s cnom = 30 mm.
HIT_FIXED_COVER_TYPES: dict[str, str] = {
    "ZVX": "30",
    "ZDX": "30",
}


def hit_action_field_mask'''
    text = replace_once(text, old_meta, new_meta, "fixed cover map")

    old_init = '''        self._manual_product = False
        self.widgets: list[tk.Widget] = []
        self.action_entries: dict[str, ttk.Entry] = {}
        self._build()'''
    new_init = '''        self._manual_product = False
        self.widgets: list[tk.Widget] = []
        self.action_entries: dict[str, ttk.Entry] = {}
        self._cover_forced = False
        self._last_free_cover = self.cover.get().strip() or "35"
        self._build()'''
    text = replace_once(text, old_init, new_init, "cover state init")

    old_cover = '        combo(self.cover, tuple(str(value) for value in COVERS), 7)\n        combo(self.concrete, CONCRETES, 9)'
    new_cover = '''        self.cover_combo = combo(self.cover, tuple(str(value) for value in COVERS), 7)
        self.cover_combo.bind("<<ComboboxSelected>>", self._cover_changed)
        combo(self.concrete, CONCRETES, 9)'''
    text = replace_once(text, old_cover, new_cover, "cover combo")

    text = replace_once(
        text,
        '        self.regrid(self.row_no)\n        self._apply_action_field_states()',
        '        self.regrid(self.row_no)\n        self._apply_type_constraints()',
        "initial type constraints",
    )

    old_state_block = '''    def _apply_action_field_states(self) -> None:
        mask = self._active_action_mask()
        for key, widget in self.action_entries.items():
            widget.configure(state="normal" if mask.get(key, False) else "disabled")

    def effective_action_texts(self) -> dict[str, str]:'''
    new_state_block = '''    def _apply_action_field_states(self) -> None:
        mask = self._active_action_mask()
        for key, widget in self.action_entries.items():
            active = bool(mask.get(key, False))
            widget.configure(
                state="normal" if active else "disabled",
                style="HitEditable.TEntry" if active else "HitLocked.TEntry",
            )

    def _apply_cover_field_state(self) -> None:
        typ = self.connection_type.get().strip().upper()
        fixed_cover = HIT_FIXED_COVER_TYPES.get(typ)
        if fixed_cover is not None:
            if not self._cover_forced:
                current = self.cover.get().strip()
                if current:
                    self._last_free_cover = current
            self.cover.set(fixed_cover)
            self.cover_combo.configure(state="disabled", style="HitLocked.TCombobox")
            self._cover_forced = True
            return

        if self._cover_forced:
            restore = self._last_free_cover if self._last_free_cover in {str(value) for value in COVERS} else "35"
            self.cover.set(restore)
        self.cover_combo.configure(state="readonly", style="TCombobox")
        self._cover_forced = False

    def _apply_type_constraints(self) -> None:
        self._apply_action_field_states()
        self._apply_cover_field_state()

    def _cover_changed(self, _event: Any = None) -> None:
        if not self._cover_forced:
            current = self.cover.get().strip()
            if current:
                self._last_free_cover = current
        self._input_changed_now()

    def effective_action_texts(self) -> dict[str, str]:'''
    text = replace_once(text, old_state_block, new_state_block, "state methods")

    text = replace_once(
        text,
        '        self._apply_action_field_states()\n        self.recalculate()',
        '        self._apply_type_constraints()\n        self.recalculate()',
        "type change constraints",
    )

    old_build_start = '''    def _build_hit_tab(self, parent: ttk.Frame) -> None:
        self._ensure_hit_variables()
        self._hit_built = True'''
    new_build_start = '''    def _build_hit_tab(self, parent: ttk.Frame) -> None:
        self._ensure_hit_variables()
        # Vstupy, které se pro zvolený typ nepoužívají, musí být na první pohled
        # odlišné od editovatelných polí. Používáme vlastní styl i v tmavém režimu.
        locked_bg = "#DCE3EA" if getattr(self, "theme_name", "light") == "light" else "#35414D"
        editable_bg = self.colors["panel_alt"]
        self.style.configure(
            "HitEditable.TEntry",
            fieldbackground=editable_bg,
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=7,
            font=("Calibri", 10),
        )
        self.style.configure(
            "HitLocked.TEntry",
            fieldbackground=locked_bg,
            foreground=self.colors["muted"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=7,
            font=("Calibri", 10),
        )
        self.style.map(
            "HitLocked.TEntry",
            fieldbackground=[("disabled", locked_bg)],
            foreground=[("disabled", self.colors["muted"])],
        )
        self.style.configure(
            "HitLocked.TCombobox",
            fieldbackground=locked_bg,
            background=locked_bg,
            foreground=self.colors["muted"],
            arrowcolor=self.colors["muted"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=6,
            font=("Calibri", 10),
        )
        self.style.map(
            "HitLocked.TCombobox",
            fieldbackground=[("disabled", locked_bg)],
            background=[("disabled", locked_bg)],
            foreground=[("disabled", self.colors["muted"])],
            selectbackground=[("disabled", locked_bg)],
            selectforeground=[("disabled", self.colors["muted"])],
        )
        self._hit_built = True'''
    text = replace_once(text, old_build_start, new_build_start, "input styles")

    old_help = 'ttk.Label(parent, text=("Vstupy zatížení se automaticky zamykají podle zvoleného typu: MVX = M−, V±; ZVX = pouze V+; ZDX = V±; DD = M±, V±; DVL = M±, V+; DDL = M±, V±. Uzamčená pole jsou při výpočtu ignorována, ale jejich dříve zadaná hodnota se zachová pro případné přepnutí zpět. Do aktivních polí stačí zadat velikost; směr určuje záhlaví. Výška v označení HIT je v cm: 200 mm → 20."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'
    new_help = 'ttk.Label(parent, text=("Vstupy zatížení se automaticky zamykají podle zvoleného typu: MVX = M−, V±; ZVX = pouze V+; ZDX = V±; DD = M±, V±; DVL = M±, V+; DDL = M±, V±. Uzamčená pole mají odlišné podbarvení a při výpočtu se ignorují, ale jejich dříve zadaná hodnota se zachová pro případné přepnutí zpět. ZVX/ZDX mají podle Annexu 3 pevné cnom = 30 mm, proto se u nich volba krytí automaticky nastaví na 30 a uzamkne. Po návratu k jinému typu se obnoví poslední volitelné krytí. Výška v označení HIT je v cm: 200 mm → 20."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'
    text = replace_once(text, old_help, new_help, "help text")
    return text


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    app = OUT / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    app_text = replace_once(app_text, 'APP_VERSION = "0.8.2"', 'APP_VERSION = "0.8.3"', "app version")
    app.write_text(app_text, encoding="utf-8")

    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    ws_text = workspace.read_text(encoding="utf-8")
    assert 'HIT_MODULE_VERSION = "0.4.3"' in ws_text
    assert 'HIT_FIXED_COVER_TYPES' in ws_text
    assert '"ZVX": "30"' in ws_text and '"ZDX": "30"' in ws_text
    assert 'style="HitEditable.TEntry" if active else "HitLocked.TEntry"' in ws_text
    assert 'self.cover_combo.configure(state="disabled", style="HitLocked.TCombobox")' in ws_text
    assert 'self.cover.set(fixed_cover)' in ws_text
    assert 'self.cover.set(restore)' in ws_text

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.8.3\n"
        "- Uzamčené vstupní buňky HIT jsou nyní barevně odlišeny od editovatelných polí ve světlém i tmavém režimu.\n"
        "- ZVX a ZDX mají podle Annexu 3 pevné krytí cnom = 30 mm; výběr krytí se po zvolení těchto typů automaticky nastaví na 30 a uzamkne.\n"
        "- Po přepnutí ze ZVX/ZDX zpět na jiný typ se obnoví poslední dříve zvolené volitelné krytí.\n"
        "- Hodnoty v uzamčených směrových polích se nadále zachovávají pro přepnutí typu, ale do výpočtu nevstupují.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.8.3/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.8.3",
        "notes": "HIT: uzamčené vstupy jsou barevně odlišeny a ZVX/ZDX mají automaticky pevné krytí cnom 30 mm.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v0.8.3")


if __name__ == "__main__":
    main()
