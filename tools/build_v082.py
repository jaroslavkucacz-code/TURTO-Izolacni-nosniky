from __future__ import annotations

import hashlib
import importlib.util
import json
import py_compile
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.8.1"
OUT = ROOT / "updates" / "0.8.2"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def patch_workspace(text: str) -> str:
    text = replace_once(
        text,
        'HIT_MODULE_VERSION = "0.4.1"\n\n\nclass HitVariantsDialog',
        '''HIT_MODULE_VERSION = "0.4.2"\n\n# Aktivní návrhové účinky pro jednotlivé typy. False = pole je v UI uzamčené\n# a jeho případná dříve zadaná hodnota se při výpočtu ignoruje.\nHIT_ACTION_FIELD_MASKS: dict[str, dict[str, bool]] = {\n    "MVX": {"m_pos": False, "m_neg": True,  "v_pos": True, "v_neg": True},\n    "ZVX": {"m_pos": False, "m_neg": False, "v_pos": True, "v_neg": False},\n    "ZDX": {"m_pos": False, "m_neg": False, "v_pos": True, "v_neg": True},\n    "DD":  {"m_pos": True,  "m_neg": True,  "v_pos": True, "v_neg": True},\n    "DVL": {"m_pos": True,  "m_neg": True,  "v_pos": True, "v_neg": False},\n    "DDL": {"m_pos": True,  "m_neg": True,  "v_pos": True, "v_neg": True},\n}\n\nHIT_ACTION_META = {\n    "m_pos": ("MEd+", "kNm/m"),\n    "m_neg": ("MEd−", "kNm/m"),\n    "v_pos": ("VEd+", "kN/m"),\n    "v_neg": ("VEd−", "kN/m"),\n}\n\n\ndef hit_action_field_mask(connection_type: str) -> dict[str, bool]:\n    # Neznámý budoucí typ je bezpečně uzamčený, dokud mu výslovně neurčíme směry.\n    return dict(HIT_ACTION_FIELD_MASKS.get(str(connection_type or "").upper(), {key: False for key in HIT_ACTION_META}))\n\n\nclass HitVariantsDialog''',
        "module version and masks",
    )

    text = replace_once(
        text,
        '''                f"{row.series.get()} {row.connection_type.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "\n                f"MEd+ {row.med_pos.get()} / MEd− {row.med_neg.get()} kNm/m • VEd+ {row.ved_pos.get()} / VEd− {row.ved_neg.get()} kN/m"''',
        '''                f"{row.series.get()} {row.connection_type.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "\n                f"{row.action_summary()}"''',
        "variant action summary",
    )

    text = replace_once(
        text,
        '        self.widgets: list[tk.Widget] = []\n        self._build()',
        '        self.widgets: list[tk.Widget] = []\n        self.action_entries: dict[str, ttk.Entry] = {}\n        self._build()',
        "action entries member",
    )

    text = replace_once(
        text,
        '''        entry(self.name, 9)\n        combo(self.series, ("HP", "SP"), 6)\n        combo(self.connection_type, CONNECTION_TYPES, 7)\n        entry(self.height, 8)\n        combo(self.cover, tuple(str(value) for value in COVERS), 7)\n        combo(self.concrete, CONCRETES, 9)\n        entry(self.med_pos, 9)\n        entry(self.med_neg, 9)\n        entry(self.ved_pos, 9)\n        entry(self.ved_neg, 9)''',
        '''        entry(self.name, 9)\n        combo(self.series, ("HP", "SP"), 6)\n        self.type_combo = combo(self.connection_type, CONNECTION_TYPES, 7)\n        # Typ potřebuje nejprve změnit dostupnost vstupů a až potom přepočítat.\n        self.type_combo.bind("<<ComboboxSelected>>", self._type_changed)\n        entry(self.height, 8)\n        combo(self.cover, tuple(str(value) for value in COVERS), 7)\n        combo(self.concrete, CONCRETES, 9)\n        self.med_pos_entry = entry(self.med_pos, 9)\n        self.med_neg_entry = entry(self.med_neg, 9)\n        self.ved_pos_entry = entry(self.ved_pos, 9)\n        self.ved_neg_entry = entry(self.ved_neg, 9)\n        self.action_entries = {\n            "m_pos": self.med_pos_entry,\n            "m_neg": self.med_neg_entry,\n            "v_pos": self.ved_pos_entry,\n            "v_neg": self.ved_neg_entry,\n        }''',
        "type and action entries",
    )

    text = replace_once(
        text,
        '        self.regrid(self.row_no)\n\n    def regrid',
        '        self.regrid(self.row_no)\n        self._apply_action_field_states()\n\n    def regrid',
        "initial field states",
    )

    text = replace_once(
        text,
        '''    def regrid(self, row_no: int) -> None:\n        self.row_no = row_no\n        for column, widget in enumerate(self.widgets):\n            widget.grid(row=row_no, column=column, sticky="ew", padx=2, pady=2)\n\n    def _input_changed(self, _event: Any = None) -> None:''',
        '''    def regrid(self, row_no: int) -> None:\n        self.row_no = row_no\n        for column, widget in enumerate(self.widgets):\n            widget.grid(row=row_no, column=column, sticky="ew", padx=2, pady=2)\n\n    def _active_action_mask(self) -> dict[str, bool]:\n        return hit_action_field_mask(self.connection_type.get())\n\n    def _apply_action_field_states(self) -> None:\n        mask = self._active_action_mask()\n        for key, widget in self.action_entries.items():\n            widget.configure(state="normal" if mask.get(key, False) else "disabled")\n\n    def effective_action_texts(self) -> dict[str, str]:\n        mask = self._active_action_mask()\n        raw = {\n            "m_pos": self.med_pos.get().strip(),\n            "m_neg": self.med_neg.get().strip(),\n            "v_pos": self.ved_pos.get().strip(),\n            "v_neg": self.ved_neg.get().strip(),\n        }\n        return {key: (value if mask.get(key, False) else "") for key, value in raw.items()}\n\n    def action_summary(self) -> str:\n        values = self.effective_action_texts()\n        parts = []\n        for key in ("m_pos", "m_neg", "v_pos", "v_neg"):\n            if not self._active_action_mask().get(key, False):\n                continue\n            label, unit = HIT_ACTION_META[key]\n            parts.append(f"{label} {values[key] or '—'} {unit}")\n        return " • ".join(parts) if parts else "bez aktivního směru zatížení"\n\n    def _type_changed(self, _event: Any = None) -> None:\n        self._manual_product = False\n        if self._after_id:\n            try:\n                self.owner.after_cancel(self._after_id)\n            except Exception:\n                pass\n            self._after_id = None\n        self._apply_action_field_states()\n        self.recalculate()\n\n    def _input_changed(self, _event: Any = None) -> None:''',
        "field state methods",
    )

    text = replace_once(
        text,
        '        texts = [self.med_pos.get().strip(), self.med_neg.get().strip(), self.ved_pos.get().strip(), self.ved_neg.get().strip()]',
        '        effective = self.effective_action_texts()\n        texts = [effective["m_pos"], effective["m_neg"], effective["v_pos"], effective["v_neg"]]',
        "effective read values",
    )

    text = replace_once(
        text,
        '''        return {\n            "name": self.name.get().strip(), "series": self.series.get(), "connection_type": candidate.connection_type, "height_mm": candidate.height,\n            "cover_mm": candidate.cover, "concrete": candidate.concrete,\n            "med_pos": self.med_pos.get().strip(), "med_neg": self.med_neg.get().strip(),\n            "ved_pos": self.ved_pos.get().strip(), "ved_neg": self.ved_neg.get().strip(),\n            "med": self.med_neg.get().strip(), "ved": self.ved_pos.get().strip(),''',
        '''        effective = self.effective_action_texts()\n        return {\n            "name": self.name.get().strip(), "series": self.series.get(), "connection_type": candidate.connection_type, "height_mm": candidate.height,\n            "cover_mm": candidate.cover, "concrete": candidate.concrete,\n            "med_pos": effective["m_pos"], "med_neg": effective["m_neg"],\n            "ved_pos": effective["v_pos"], "ved_neg": effective["v_neg"],\n            "med": effective["m_neg"], "ved": effective["v_pos"],''',
        "future payload effective fields",
    )

    old_help = '''        ttk.Label(parent, text=("Zatížení lze zadat současně ve směrech +/−; do polí stačí zadat velikost a směr určuje záhlaví. Program pracuje s obálkou směrových maxim. MVX používá záporný moment a kontroluje oba směry smyku; ZVX a DVL jsou jednosměrné ve smyku, zatímco ZDX, DD a DDL kontrolují oba směry. Toto směrové rozhraní je připravené i pro další výrobce s rozdílnou únosností V+ a V−. Výška v označení HIT je v cm: 200 mm → 20."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'''
    new_help = '''        ttk.Label(parent, text=("Vstupy zatížení se automaticky zamykají podle zvoleného typu: MVX = M−, V±; ZVX = pouze V+; ZDX = V±; DD = M±, V±; DVL = M±, V+; DDL = M±, V±. Uzamčená pole jsou při výpočtu ignorována, ale jejich dříve zadaná hodnota se zachová pro případné přepnutí zpět. Do aktivních polí stačí zadat velikost; směr určuje záhlaví. Výška v označení HIT je v cm: 200 mm → 20."), style="Muted.TLabel", wraplength=1450, justify="left").grid(row=3, column=0, sticky="ew", pady=(8, 0))'''
    text = replace_once(text, old_help, new_help, "help text")

    text = replace_once(
        text,
        '''            lines.append("\\t".join([row.name.get(), row.series.get(), row.connection_type.get(), row.height.get(), row.cover.get(), row.concrete.get(), row.med_pos.get(), row.med_neg.get(), row.ved_pos.get(), row.ved_neg.get(), candidate.designation, fmt(candidate.utilization * 100.0) + " %", str(candidate.page), fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2)]))''',
        '''            effective = row.effective_action_texts()\n            lines.append("\\t".join([row.name.get(), row.series.get(), row.connection_type.get(), row.height.get(), row.cover.get(), row.concrete.get(), effective["m_pos"], effective["m_neg"], effective["v_pos"], effective["v_neg"], candidate.designation, fmt(candidate.utilization * 100.0) + " %", str(candidate.page), fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2)]))''',
        "copy effective fields",
    )

    return text


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    app = OUT / "app.pyw"
    app_text = app.read_text(encoding="utf-8")
    app_text = replace_once(app_text, 'APP_VERSION = "0.8.1"', 'APP_VERSION = "0.8.2"', "app version")
    app.write_text(app_text, encoding="utf-8")

    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    sys.path.insert(0, str(OUT))
    try:
        spec = importlib.util.spec_from_file_location("hit_workspace_v082", workspace)
        if spec is None or spec.loader is None:
            raise RuntimeError("Nelze načíst hit_workspace pro test.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected = {
            "MVX": {"m_pos": False, "m_neg": True, "v_pos": True, "v_neg": True},
            "ZVX": {"m_pos": False, "m_neg": False, "v_pos": True, "v_neg": False},
            "ZDX": {"m_pos": False, "m_neg": False, "v_pos": True, "v_neg": True},
            "DD": {"m_pos": True, "m_neg": True, "v_pos": True, "v_neg": True},
            "DVL": {"m_pos": True, "m_neg": True, "v_pos": True, "v_neg": False},
            "DDL": {"m_pos": True, "m_neg": True, "v_pos": True, "v_neg": True},
        }
        for typ, mask in expected.items():
            assert module.hit_action_field_mask(typ) == mask, (typ, module.hit_action_field_mask(typ))
        assert not any(module.hit_action_field_mask("UNKNOWN").values())
    finally:
        sys.path.pop(0)

    ws_text = workspace.read_text(encoding="utf-8")
    assert 'HIT_MODULE_VERSION = "0.4.2"' in ws_text
    assert 'self.type_combo.bind("<<ComboboxSelected>>", self._type_changed)' in ws_text
    assert 'widget.configure(state="normal" if mask.get(key, False) else "disabled")' in ws_text
    assert 'effective = self.effective_action_texts()' in ws_text

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.8.2\n"
        "- Vstupní pole MEd+/MEd−/VEd+/VEd− se dynamicky zamykají podle zvoleného typu HIT.\n"
        "- MVX: aktivní MEd−, VEd+, VEd−; ZVX: pouze VEd+; ZDX: VEd+ a VEd−.\n"
        "- DD a DDL: aktivní všechny čtyři směry; DVL: MEd+, MEd− a VEd+.\n"
        "- Uzamčené hodnoty zůstávají v řádku pro případ přepnutí zpět, ale výpočet, kopírování a budoucí provazby je ignorují.\n"
        "- Neznámý budoucí typ má bezpečně všechny směrové vstupy uzamčené, dokud mu není definován statický model.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.8.2/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.8.2",
        "notes": "Vstupní směry HIT se nyní automaticky zamykají podle zvoleného typu; neplatné směry se nezapočítávají do návrhu.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v0.8.2")


if __name__ == "__main__":
    main()
