from __future__ import annotations

import base64
import gzip
import hashlib
import json
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.9.3"
OUT = ROOT / "updates" / "1.0.0"

SPECIAL_GZ_B64 = """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"""


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def replace_in_method(text: str, method: str, old: str, new: str, label: str) -> str:
    start = text.find(f"    def {method}(")
    if start < 0:
        raise RuntimeError(f"{label}: method {method} not found")
    end = text.find("\n    def ", start + 8)
    if end < 0:
        end = len(text)
    block = text[start:end]
    count = block.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match in {method}, got {count}")
    block = block.replace(old, new, 1)
    return text[:start] + block + text[end:]


def patch_core(text: str) -> str:
    text = replace_once(text, "from typing import Any\n", "from typing import Any\n\nfrom hit_special import design_special\n", "special import")
    text = replace_once(text, 'DATA_FILENAME = "hit_all_2023_v3.json.gz.b64"', 'DATA_FILENAME = "hit_all_2023_v4.json.gz.b64"', "data filename")
    text = replace_once(text, 'CONNECTION_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL")', 'CONNECTION_TYPES = ("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL", "AT", "FT", "OTX")', "connection types")

    old_actions = '''    m_pos: float = 0.0\n    m_neg: float = 0.0\n    v_pos: float = 0.0\n    v_neg: float = 0.0\n\n    def normalized(self) -> "DirectionalActions":\n        return DirectionalActions(\n            abs(float(self.m_pos)), abs(float(self.m_neg)),\n            abs(float(self.v_pos)), abs(float(self.v_neg)),\n        )\n\n    def has_any(self) -> bool:\n        a = self.normalized()\n        return max(a.m_pos, a.m_neg, a.v_pos, a.v_neg) > TOL\n'''
    new_actions = '''    m_pos: float = 0.0\n    m_neg: float = 0.0\n    v_pos: float = 0.0\n    v_neg: float = 0.0\n    n_pos: float = 0.0\n    n_neg: float = 0.0\n\n    def normalized(self) -> "DirectionalActions":\n        return DirectionalActions(\n            m_pos=abs(float(self.m_pos)), m_neg=abs(float(self.m_neg)),\n            v_pos=abs(float(self.v_pos)), v_neg=abs(float(self.v_neg)),\n            n_pos=abs(float(self.n_pos)), n_neg=abs(float(self.n_neg)),\n        )\n\n    def has_any(self) -> bool:\n        a = self.normalized()\n        return max(a.m_pos, a.m_neg, a.v_pos, a.v_neg, a.n_pos, a.n_neg) > TOL\n'''
    text = replace_once(text, old_actions, new_actions, "directional actions")

    text = replace_once(
        text,
        '    source_note: str = ""\n\n    @property\n    def designation',
        '    source_note: str = ""\n    nrd: float = 0.0\n    spacing_max: float = 0.0\n    load_distance_x: float = 0.0\n\n    @property\n    def designation',
        "candidate special fields",
    )
    text = replace_once(
        text,
        '        if typ in {"ZVX", "ZDX"}:\n',
        '        if typ in {"AT", "FT"}:\n            return f"HIT-{self.series} {self.code}-{hcode}-025"\n        if typ == "OTX":\n            dia = self.suffix or "06"\n            return f"HIT-{self.series} {self.code}-{hcode}-025-{dia}"\n        if typ in {"ZVX", "ZDX"}:\n',
        "special designations",
    )

    text = replace_once(text, '        for pi in range(3, 54):', '        for pi in range(3, 93):', "annex 2 range")
    text = replace_once(text, 'Z Annexu 1 se podařilo načíst jen', 'Z Annexů 1/2 se podařilo načíst jen', "annex error text")
    text = replace_once(text, '"schema_version": 3,', '"schema_version": 4,', "schema version")
    text = replace_once(text, '"catalog_id": "leviat_hit_hp_sp_07_23_all_v3",', '"catalog_id": "leviat_hit_hp_sp_07_23_all_v4",', "catalog id")

    clone_marker = '        self.zvx_records = list(self.data.get("zvx_records", []))\n'
    clone_code = '''        # Annex 2 provides dedicated OD/WD tables. For OU/WU the DoP states\n        # that capacities correspond to the standard MVX; create those structural\n        # variants from the verified standard records without changing capacities.\n        if self.schema_version >= 4:\n            existing = {(r[0], r[1], int(r[2]), r[3], int(r[4]), r[5]) for r in self.records}\n            standard = [r for r in self.records if not r[3]]\n            derived = []\n            for r in standard:\n                for suffix in ("OU", "WU"):\n                    key = (r[0], r[1], int(r[2]), suffix, int(r[4]), r[5])\n                    if key not in existing:\n                        derived.append([r[0], r[1], int(r[2]), suffix, int(r[4]), r[5], *r[6:]])\n                        existing.add(key)\n            self.records.extend(derived)\n\n'''
    text = replace_once(text, clone_marker, clone_code + clone_marker, "derived OU WU")

    text = replace_once(
        text,
        '        if self.dvl_moment:\n            values.extend(["DVL", "DDL"])\n        return tuple(values)\n',
        '        if self.dvl_moment:\n            values.extend(["DVL", "DDL"])\n        if self.schema_version >= 4:\n            values.extend(["AT", "FT", "OTX"])\n        return tuple(values)\n',
        "available special types",
    )

    text = replace_in_method(
        text, "directional_candidates",
        '        actions: DirectionalActions, lengths: set[int], include_offsets: bool = False,\n    ):',
        '        actions: DirectionalActions, lengths: set[int], include_offsets: bool = False,\n        load_distance_x: float = 0.0,\n    ):',
        "directional signature",
    )
    special_branch = '''        if typ in {"AT", "FT", "OTX"}:\n            if self.schema_version < 4:\n                return [], "Databáze HIT je ze starší verze. Obnovte ji ze spravovaného DoP."\n            rows, error = design_special(\n                typ, series, height, concrete,\n                m_pos=a.m_pos, m_neg=a.m_neg, n_pos=a.n_pos, n_neg=a.n_neg,\n                v_pos=a.v_pos, v_neg=a.v_neg, x_mm=load_distance_x,\n            )\n            if error:\n                return [], error\n            out: list[Candidate] = []\n            for row in rows:\n                amax = float(row.get("amax", 0.0) or 0.0)\n                utilization_at_250 = 0.0 if amax <= TOL else min(1.0, 0.25 / amax)\n                out.append(Candidate(\n                    series, typ, str(row["code"]), 25, str(row.get("suffix", "")), height, concrete,\n                    float(row.get("mrd", 0.0)), float(row.get("vrd", 0.0)), 0.0, 0.0,\n                    f"HIT20.2 p.{row.get('page', '')}", 30, height, utilization_at_250,\n                    str(row.get("mode", "")), str(row.get("source", "HIT 20.2-EN")),\n                    nrd=float(row.get("nrd", 0.0)), spacing_max=amax,\n                    load_distance_x=float(row.get("x_mm", 0.0) or 0.0),\n                ))\n            return out, ""\n\n'''
    text = replace_in_method(text, "directional_candidates", '        if typ in {"ZVX", "ZDX"}:\n', special_branch + '        if typ in {"ZVX", "ZDX"}:\n', "special directional branch")

    text = replace_in_method(
        text, "proposal_candidates",
        '        actions: DirectionalActions, lengths: set[int], include_offsets: bool = False,\n    ):',
        '        actions: DirectionalActions, lengths: set[int], include_offsets: bool = False,\n        load_distance_x: float = 0.0,\n    ):',
        "proposal signature",
    )
    # Both calls inside proposal_candidates must preserve x for special types.
    start = text.find('    def proposal_candidates(')
    end = text.find('\n    def ', start + 8)
    block = text[start:end]
    block = block.replace('actions, lengths, include_offsets\n        )', 'actions, lengths, include_offsets, load_distance_x\n        )')
    text = text[:start] + block + text[end:]
    return text


def patch_workspace(text: str) -> str:
    text = replace_once(text, 'HIT_MODULE_VERSION = "0.5.1"', 'HIT_MODULE_VERSION = "1.0.0"', "module version")
    old_masks = '''HIT_ACTION_FIELD_MASKS: dict[str, dict[str, bool]] = {\n    "MVX":  {"m_pos": False, "m_neg": True,  "v_pos": True, "v_neg": True},\n    "MVXL": {"m_pos": False, "m_neg": True,  "v_pos": True, "v_neg": True},\n    "ZVX": {"m_pos": False, "m_neg": False, "v_pos": True, "v_neg": False},\n    "ZDX": {"m_pos": False, "m_neg": False, "v_pos": True, "v_neg": True},\n    "DD":  {"m_pos": True,  "m_neg": True,  "v_pos": True, "v_neg": True},\n    "DVL": {"m_pos": True,  "m_neg": True,  "v_pos": True, "v_neg": False},\n    "DDL": {"m_pos": True,  "m_neg": True,  "v_pos": True, "v_neg": True},\n}\n\nHIT_ACTION_META = {\n    "m_pos": ("MEd+", "kNm/m"),\n    "m_neg": ("MEd−", "kNm/m"),\n    "v_pos": ("VEd+", "kN/m"),\n    "v_neg": ("VEd−", "kN/m"),\n}\n'''
    new_masks = '''HIT_ACTION_FIELD_MASKS: dict[str, dict[str, bool]] = {\n    "MVX":  {"m_pos": False, "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},\n    "MVXL": {"m_pos": False, "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},\n    "ZVX":  {"m_pos": False, "m_neg": False, "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": False},\n    "ZDX":  {"m_pos": False, "m_neg": False, "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},\n    "DD":   {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},\n    "DVL":  {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": False},\n    "DDL":  {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": False, "v_pos": True, "v_neg": True},\n    "AT":   {"m_pos": True,  "m_neg": True,  "n_pos": False, "n_neg": True,  "v_pos": True, "v_neg": True},\n    "FT":   {"m_pos": True,  "m_neg": True,  "n_pos": True,  "n_neg": True,  "v_pos": True, "v_neg": True},\n    "OTX":  {"m_pos": False, "m_neg": False, "n_pos": True,  "n_neg": True,  "v_pos": True, "v_neg": False},\n}\n\nHIT_ACTION_META = {\n    "m_pos": ("MEd+", "kNm/m"),\n    "m_neg": ("MEd−", "kNm/m"),\n    "n_pos": ("NEd+", "kN/m"),\n    "n_neg": ("NEd−", "kN/m"),\n    "v_pos": ("VEd+", "kN/m"),\n    "v_neg": ("VEd−", "kN/m"),\n}\n'''
    text = replace_once(text, old_masks, new_masks, "action masks")
    text = replace_once(
        text,
        '    "ZDX": "30",\n}',
        '    "ZDX": "30",\n    "AT": "30",\n    "FT": "30",\n    "OTX": "30",\n}',
        "fixed covers special",
    )

    text = replace_once(
        text,
        '        self.ved_neg = tk.StringVar(value=str(defaults.get("ved_neg", "")))\n',
        '        self.ved_neg = tk.StringVar(value=str(defaults.get("ved_neg", "")))\n        self.ned_pos = tk.StringVar(value=str(defaults.get("ned_pos", "")))\n        self.ned_neg = tk.StringVar(value=str(defaults.get("ned_neg", "")))\n        self.load_x = tk.StringVar(value=str(defaults.get("load_x", "")))\n        self.spacing = tk.StringVar(value="—")\n',
        "special row vars",
    )

    old_entries = '''        self.med_pos_entry = entry(self.med_pos, 9)\n        self.med_neg_entry = entry(self.med_neg, 9)\n        self.ved_pos_entry = entry(self.ved_pos, 9)\n        self.ved_neg_entry = entry(self.ved_neg, 9)\n        self.action_entries = {\n            "m_pos": self.med_pos_entry,\n            "m_neg": self.med_neg_entry,\n            "v_pos": self.ved_pos_entry,\n            "v_neg": self.ved_neg_entry,\n        }\n'''
    new_entries = '''        self.med_pos_entry = entry(self.med_pos, 9)\n        self.med_neg_entry = entry(self.med_neg, 9)\n        self.ned_pos_entry = entry(self.ned_pos, 9)\n        self.ned_neg_entry = entry(self.ned_neg, 9)\n        self.ved_pos_entry = entry(self.ved_pos, 9)\n        self.ved_neg_entry = entry(self.ved_neg, 9)\n        self.load_x_entry = entry(self.load_x, 8)\n        self.action_entries = {\n            "m_pos": self.med_pos_entry,\n            "m_neg": self.med_neg_entry,\n            "n_pos": self.ned_pos_entry,\n            "n_neg": self.ned_neg_entry,\n            "v_pos": self.ved_pos_entry,\n            "v_neg": self.ved_neg_entry,\n        }\n'''
    text = replace_once(text, old_entries, new_entries, "special entries")
    text = replace_once(
        text,
        '        self.util_label = ttk.Label(parent, textvariable=self.util, width=10, anchor="center", style="Card.TLabel")\n        self.widgets.append(self.util_label)\n        self.page_label',
        '        self.util_label = ttk.Label(parent, textvariable=self.util, width=10, anchor="center", style="Card.TLabel")\n        self.widgets.append(self.util_label)\n        self.spacing_label = ttk.Label(parent, textvariable=self.spacing, width=10, anchor="center", style="Card.TLabel")\n        self.widgets.append(self.spacing_label)\n        self.page_label',
        "spacing output widget",
    )

    apply_marker = '''    def _apply_cover_field_state(self) -> None:\n'''
    x_method = '''    def _apply_x_field_state(self) -> None:\n        active = self.connection_type.get().strip().upper() == "OTX"\n        self.load_x_entry.configure(\n            state="normal" if active else "disabled",\n            style="HitEditable.TEntry" if active else "HitLocked.TEntry",\n        )\n\n'''
    text = replace_once(text, apply_marker, x_method + apply_marker, "x field method")
    text = replace_once(
        text,
        '    def _apply_type_constraints(self) -> None:\n        self._apply_action_field_states()\n        self._apply_cover_field_state()\n',
        '    def _apply_type_constraints(self) -> None:\n        self._apply_action_field_states()\n        self._apply_x_field_state()\n        self._apply_cover_field_state()\n',
        "type constraints x",
    )

    old_effective = '''        raw = {\n            "m_pos": self.med_pos.get().strip(),\n            "m_neg": self.med_neg.get().strip(),\n            "v_pos": self.ved_pos.get().strip(),\n            "v_neg": self.ved_neg.get().strip(),\n        }\n'''
    new_effective = '''        raw = {\n            "m_pos": self.med_pos.get().strip(),\n            "m_neg": self.med_neg.get().strip(),\n            "n_pos": self.ned_pos.get().strip(),\n            "n_neg": self.ned_neg.get().strip(),\n            "v_pos": self.ved_pos.get().strip(),\n            "v_neg": self.ved_neg.get().strip(),\n        }\n'''
    text = replace_once(text, old_effective, new_effective, "effective N")
    text = replace_once(text, '        for key in ("m_pos", "m_neg", "v_pos", "v_neg"):', '        for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg"):', "summary N")

    # Replace value reader as one contiguous method.
    start = text.find('    def _read_values(self)')
    end = text.find('\n    def recalculate(', start)
    if start < 0 or end < 0:
        raise RuntimeError("_read_values bounds not found")
    read_method = '''    def _read_values(self) -> tuple[int, int, DirectionalActions, float] | None:\n        effective = self.effective_action_texts()\n        texts = [effective[key] for key in ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg")]\n        if not any(texts):\n            return None\n        height = int(float(self.height.get().replace(",", ".")))\n        cover = int(self.cover.get())\n\n        def load_value(value: str) -> float:\n            return abs(float((value or "0").replace(",", ".")))\n\n        actions = DirectionalActions(\n            m_pos=load_value(effective["m_pos"]), m_neg=load_value(effective["m_neg"]),\n            v_pos=load_value(effective["v_pos"]), v_neg=load_value(effective["v_neg"]),\n            n_pos=load_value(effective["n_pos"]), n_neg=load_value(effective["n_neg"]),\n        )\n        x_mm = load_value(self.load_x.get().strip()) if self.connection_type.get().strip().upper() == "OTX" else 0.0\n        return height, cover, actions, x_mm\n\n'''
    text = text[:start] + read_method + text[end:]

    text = replace_once(text, '        height, cover, actions = values\n', '        height, cover, actions, x_mm = values\n', "recalc x unpack")
    text = replace_once(
        text,
        '            self.owner.hit_offsets_var.get(),\n        )\n',
        '            self.owner.hit_offsets_var.get(), load_distance_x=x_mm,\n        )\n',
        "proposal x call",
    )

    # Reset spacing wherever a row has no valid proposal.
    text = text.replace('            self.page.set("—")\n            self.detail_label.configure(style="MutedCard.TLabel")', '            self.page.set("—")\n            self.spacing.set("—")\n            self.detail_label.configure(style="MutedCard.TLabel")')
    text = text.replace('        self.page.set("—")\n        self.detail_label.configure(style="MutedCard.TLabel")', '        self.page.set("—")\n        self.spacing.set("—")\n        self.detail_label.configure(style="MutedCard.TLabel")')

    # Candidate display: special 250mm elements return maximum allowed axial spacing.
    text = replace_once(
        text,
        '        self.util.set(fmt(candidate.utilization * 100.0) + " %")\n        self.page.set(str(candidate.page))\n',
        '        if candidate.spacing_max > 0:\n            self.util.set("—")\n            self.spacing.set(fmt(candidate.spacing_max, 3) + " m")\n        else:\n            self.util.set(fmt(candidate.utilization * 100.0) + " %")\n            self.spacing.set("—")\n        self.page.set(str(candidate.page))\n',
        "special candidate display",
    )
    text = replace_once(
        text,
        '        if candidate.connection_type == "MVX":\n',
        '        if candidate.connection_type in {"AT", "FT", "OTX"}:\n            text += f" • NRd {fmt(candidate.nrd)} • VRd {fmt(candidate.v1)} • amax {fmt(candidate.spacing_max,3)} m"\n            if candidate.connection_type == "OTX":\n                text += f" • x {fmt(candidate.load_distance_x,0)} mm"\n        elif candidate.connection_type == "MVX":\n',
        "special detail",
    )

    # Defaults / future payload.
    old_defaults = '        return {"series": self.series.get(), "connection_type": self.connection_type.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med_pos": "", "med_neg": "", "ved_pos": "", "ved_neg": ""}\n'
    new_defaults = '        return {"series": self.series.get(), "connection_type": self.connection_type.get(), "height": self.height.get(), "cover": self.cover.get(), "concrete": self.concrete.get(), "med_pos": "", "med_neg": "", "ned_pos": "", "ned_neg": "", "ved_pos": "", "ved_neg": "", "load_x": ""}\n'
    text = replace_once(text, old_defaults, new_defaults, "next defaults")
    text = replace_once(
        text,
        '            "ved_pos": effective["v_pos"], "ved_neg": effective["v_neg"],\n',
        '            "ned_pos": effective["n_pos"], "ned_neg": effective["n_neg"],\n            "ved_pos": effective["v_pos"], "ved_neg": effective["v_neg"],\n            "load_distance_x_mm": candidate.load_distance_x, "spacing_max_m": candidate.spacing_max, "nrd": candidate.nrd,\n',
        "future special payload",
    )

    # Variant dialog special columns.
    text = replace_once(
        text,
        '        columns = ("rank", "type", "designation", "length", "variant", "util", "mode", "m1", "v1", "m2", "v2", "page")\n',
        '        columns = ("rank", "type", "designation", "length", "variant", "util", "amax", "nrd", "mode", "m1", "v1", "m2", "v2", "page")\n',
        "variant special columns",
    )
    text = replace_once(
        text,
        '            "util": ("Využití", 82, "center"),\n            "mode":',
        '            "util": ("Využití", 82, "center"),\n            "amax": ("a max", 82, "center"),\n            "nrd": ("NRd", 78, "center"),\n            "mode":',
        "variant special headings",
    )
    text = replace_once(
        text,
        '                    fmt(candidate.utilization * 100.0) + " %", candidate.mode,\n                    fmt(candidate.m1),',
        '                    ("—" if candidate.spacing_max > 0 else fmt(candidate.utilization * 100.0) + " %"),\n                    (fmt(candidate.spacing_max,3) + " m" if candidate.spacing_max > 0 else "—"),\n                    (fmt(candidate.nrd) if candidate.spacing_max > 0 else "—"), candidate.mode,\n                    fmt(candidate.m1),',
        "variant special row",
    )

    # Header row must match widget order.
    old_headers = '("Označení", "Řada", "Typ", "h [mm]", "cnom", "Beton", "MEd+", "MEd−", "VEd+", "VEd−", "Navržený výrobek ▼", "Varianty", "Využití", "Zdroj", "Stav / kontrola", "")'
    new_headers = '("Označení", "Řada", "Typ", "h [mm]", "cnom", "Beton", "MEd+", "MEd−", "NEd+", "NEd−", "VEd+", "VEd−", "x [mm]", "Navržený výrobek ▼", "Varianty", "Využití", "a max", "Zdroj", "Stav / kontrola", "")'
    text = replace_once(text, old_headers, new_headers, "headers")
    text = replace_once(text, 'column in (0, 10, 14)', 'column in (0, 13, 18)', "header anchors")
    text = replace_once(text, 'column in (0, 10, 14) else 0', 'column in (0, 13, 18) else 0', "header weights")

    # Main type summary/help.
    text = replace_once(
        text,
        'HIT-HP/SP • MVX / MVXL / ZVX / ZDX / DD / DVL / DDL • modul',
        'HIT-HP/SP • MVX / MVXL / ZVX / ZDX / DD / DVL / DDL / AT / FT / OTX • modul',
        "type summary",
    )
    text = replace_once(
        text,
        'Vstupy zatížení se automaticky zamykají podle zvoleného typu: MVX/MVXL = M−, V±; good/poor bond se volí automaticky podle h−cnom; ZVX = pouze V+; ZDX = V±; DD = M±, V±; DVL = M±, V+; DDL = M±, V±.',
        'Vstupy zatížení se automaticky zamykají podle zvoleného typu: MVX/MVXL = M−, V±; ZVX = pouze V+; ZDX = V±; DD = M±, V±; DVL = M±, V+; DDL = M±, V±; AT = M±, N−, V±; FT = M±, N±, V±; OTX = N±, V+ a vzdálenost x. Good/poor bond MVXL se volí automaticky podle h−cnom.',
        "help current types",
    )

    # Copy result fields.
    text = replace_once(
        text,
        'lines = ["Označení\\tŘada\\tTyp\\th [mm]\\tcnom [mm]\\tBeton\\tMEd+ [kNm/m]\\tMEd− [kNm/m]\\tVEd+ [kN/m]\\tVEd− [kN/m]\\tNavržený výrobek\\tVyužití\\tZdroj\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2"]',
        'lines = ["Označení\\tŘada\\tTyp\\th [mm]\\tcnom [mm]\\tBeton\\tMEd+ [kNm/m]\\tMEd− [kNm/m]\\tNEd+ [kN/m]\\tNEd− [kN/m]\\tVEd+ [kN/m]\\tVEd− [kN/m]\\tx [mm]\\tNavržený výrobek\\tVyužití\\ta max [m]\\tZdroj\\tNRd\\tMRd,1\\tVRd,1\\tMRd,2\\tVRd,2"]',
        "copy header",
    )
    old_copy = 'lines.append("\\t".join([row.name.get(), row.series.get(), candidate.connection_type, row.height.get(), row.cover.get(), row.concrete.get(), effective["m_pos"], effective["m_neg"], effective["v_pos"], effective["v_neg"], candidate.designation, fmt(candidate.utilization * 100.0) + " %", str(candidate.page), fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2)]))'
    new_copy = 'lines.append("\\t".join([row.name.get(), row.series.get(), candidate.connection_type, row.height.get(), row.cover.get(), row.concrete.get(), effective["m_pos"], effective["m_neg"], effective["n_pos"], effective["n_neg"], effective["v_pos"], effective["v_neg"], (fmt(candidate.load_distance_x,0) if candidate.load_distance_x else ""), candidate.designation, ("" if candidate.spacing_max > 0 else fmt(candidate.utilization * 100.0) + " %"), (fmt(candidate.spacing_max,3) if candidate.spacing_max > 0 else ""), str(candidate.page), fmt(candidate.nrd), fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2)]))'
    text = replace_once(text, old_copy, new_copy, "copy row")
    return text


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    special = OUT / "hit_special.py"
    special.write_bytes(gzip.decompress(base64.b64decode(SPECIAL_GZ_B64)))

    core = OUT / "hit_core.py"
    core.write_text(patch_core(core.read_text(encoding="utf-8")), encoding="utf-8")
    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")
    app = OUT / "app.pyw"
    app.write_text(replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "0.9.3"', 'APP_VERSION = "1.0.0"', "app version"), encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    # Functional regression in a subprocess so dataclasses see a normal module import.
    regression = r'''
from hit_special import design_at, design_ft, design_otx
from hit_core import CONNECTION_TYPES, Candidate, DirectionalActions
assert CONNECTION_TYPES == ("MVX","MVXL","ZVX","ZDX","DD","DVL","DDL","AT","FT","OTX")
rows, err = design_at("SP", 200, 4.72, 0, 0, 9.45, 0, 6.05)
assert not err and rows
r = next(x for x in rows if x["code"] == "AT2-0301")
assert abs(r["amax"] - 1.1756) < 0.002
assert abs(r["vrd"] - 7.5) < 1e-9
c = Candidate("SP","AT","AT2-0301",25,"",200,"C25/30",r["mrd"],r["vrd"],0,0,"HIT20.2 p.133",30,200,0.0,"",nrd=r["nrd"],spacing_max=r["amax"])
assert c.designation == "HIT-SP AT2-0301-20-025"
rows, err = design_ft("HP", 200, "C25/30", 2, 3, 10, 5, 5, 10)
assert not err and rows and all(not x["code"].startswith("FT1") for x in rows)
rows, err = design_otx("HP", 200, "C25/30", 0, 2, 10, 0, 80)
assert not err and rows
assert any(x["code"].startswith("OTX1") and x["x_used"] == 85 for x in rows)
assert all(abs(x["nrd"] - 0.1*x["vrd"]) < 1e-9 for x in rows)
a = DirectionalActions(n_pos=2,n_neg=3)
assert a.normalized().n_neg == 3
'''
    subprocess.run([sys.executable, "-c", regression], cwd=OUT, check=True)

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v1.0.0\n"
        "- Návrh HIT nyní obsahuje všechny aktuální typy z CONF-DOP HIT-HP/SP-07-23: MVX, MVXL, ZVX, ZDX, DD, DVL, DDL, AT, FT a OTX.\n"
        "- Dokončen Annex 2 MVX-OD/OU/WD/WU; OD/WD se načítají z vlastních DoP tabulek, OU/WU používají podle DoP statické hodnoty standardního MVX.\n"
        "- Přidány směrové vstupy NEd+ / NEd−. AT používá M±, N−, V±; FT používá M±, N±, V±; OTX používá N±, V+ a vstup x [mm].\n"
        "- AT/FT/OTX jsou 250mm prvky a program pro ně přímo navrhuje maximální přípustnou osovou rozteč a_max.\n"
        "- AT/FT jsou automaticky omezeny na katalogově tabulované výšky 160–250 mm; OTX na 180–250 mm. Hodnoty nad tento rozsah jsou v katalogu pouze na vyžádání a program je neodhaduje.\n"
        "- OTX volí pro mezilehlé x konzervativně nejbližší vyšší tabulkovou vzdálenost; NRd = ±0,1 VRd podle katalogu.\n"
        "- Historické HIT typy nejsou součástí automatického návrhu.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.0.0/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.0.0",
        "notes": "HIT: kompletní aktuální návrhová rodina MVX/MVXL/ZVX/ZDX/DD/DVL/DDL/AT/FT/OTX, Annex 2 a nové NEd/x/a_max vstupy.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v1.0.0")


if __name__ == "__main__":
    main()
