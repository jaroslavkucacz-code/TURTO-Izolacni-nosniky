from __future__ import annotations

import base64
import gzip
import hashlib
import json
import py_compile
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.9.1"
OUT = ROOT / "updates" / "0.9.2"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


PROPOSAL_METHOD = r'''
    def proposal_candidates(
        self, connection_type: str, series: str, height: int, cover: int, concrete: str,
        actions: DirectionalActions, lengths: set[int], include_offsets: bool = False,
    ):
        """Návrh s bezpečnou vazbou příbuzné rodiny MVX <-> MVXL.

        Zvolený typ je preferovaný. MVX hledá MVXL pouze tehdy, když žádný MVX
        nevyhoví. U zvoleného MVXL se MVX zkontroluje vždy a pokud vyhoví, přidá
        se jako alternativa za preferované MVXL. Funkce nikdy potichu nemění
        zvolený filtr; každý Candidate nese svůj skutečný connection_type.
        """
        typ = str(connection_type or "MVX").upper()
        primary, primary_error = self.directional_candidates(
            typ, series, height, cover, concrete, actions, lengths, include_offsets
        )
        info: dict[str, Any] = {
            "preferred_type": typ,
            "primary_available": bool(primary) and not bool(primary_error),
            "alternative_type": "",
            "alternative_count": 0,
            "mode": "preferred",
            "note": "",
        }
        if typ not in {"MVX", "MVXL"}:
            return primary, primary_error, info

        alternative_type = "MVXL" if typ == "MVX" else "MVX"
        info["alternative_type"] = alternative_type

        # U MVX se silnější rodina nemá nabízet, pokud vyhovuje některý MVX.
        if typ == "MVX" and primary and not primary_error:
            return primary, "", info

        alternative, alternative_error = self.directional_candidates(
            alternative_type, series, height, cover, concrete, actions, lengths, include_offsets
        )
        info["alternative_count"] = len(alternative)

        if typ == "MVX":
            if alternative:
                info.update({
                    "mode": "fallback",
                    "note": "MVX nevyhovuje; nabídnuta vyhovující náhrada MVXL.",
                })
                return alternative, "", info
            return primary, primary_error or alternative_error, info

        # Zvolený MVXL: pokud vyhovuje i MVX, zachová se MVXL jako první
        # (preferovaný) a MVX se přidá do Variant jako jednodušší alternativa.
        if primary and not primary_error:
            if alternative:
                seen: set[str] = set()
                combined: list[Candidate] = []
                for candidate in [*primary, *alternative]:
                    if candidate.designation in seen:
                        continue
                    seen.add(candidate.designation)
                    combined.append(candidate)
                info.update({
                    "mode": "related",
                    "note": f"Vyhovuje také {len(alternative)} variant MVX; viz Varianty…",
                })
                return combined, "", info
            return primary, "", info

        # I opačný fallback je bezpečný: pokud z nějakého geometrického důvodu
        # MVXL není dostupný, ale MVX zadané účinky splní, uživatel o něj nepřijde.
        if alternative:
            info.update({
                "mode": "fallback",
                "note": "MVXL nemá vyhovující variantu; nabídnuta náhrada MVX.",
            })
            return alternative, "", info
        return primary, primary_error or alternative_error, info

'''


def patch_core(text: str) -> str:
    marker = "    def candidates(self, connection_type: str, series: str, height: int, cover: int, concrete: str, med: float, ved: float, lengths: set[int], include_offsets: bool = False):\n"
    return replace_once(text, marker, PROPOSAL_METHOD + marker, "proposal_candidates insertion")


def patch_workspace(text: str) -> str:
    text = replace_once(text, 'HIT_MODULE_VERSION = "0.5.0"', 'HIT_MODULE_VERSION = "0.5.1"', "module version")
    text = replace_once(
        text,
        '        self._manual_product = False\n        self.widgets: list[tk.Widget] = []\n',
        '        self._manual_product = False\n        self._family_info: dict[str, Any] = {}\n        self.widgets: list[tk.Widget] = []\n',
        "family info init",
    )

    # Variant dialog: show actual type explicitly.
    text = replace_once(
        text,
        '        columns = ("rank", "designation", "length", "variant", "util", "mode", "m1", "v1", "m2", "v2", "page")\n',
        '        columns = ("rank", "type", "designation", "length", "variant", "util", "mode", "m1", "v1", "m2", "v2", "page")\n',
        "variant type column",
    )
    text = replace_once(
        text,
        '            "rank": ("Poř.", 58, "center"),\n            "designation": ("Varianta HIT", 340, "w"),\n',
        '            "rank": ("Poř.", 92, "center"),\n            "type": ("Typ", 72, "center"),\n            "designation": ("Varianta HIT", 340, "w"),\n',
        "variant type heading",
    )
    text = replace_once(
        text,
        '            rank = "1 • doporučeno" if index == 1 else str(index)\n',
        '            preferred_type = row.connection_type.get().strip().upper()\n            if candidate.connection_type != preferred_type:\n                rank = "1 • náhrada" if index == 1 else ("náhrada" if not row._family_info.get("primary_available") else "alternativa")\n            else:\n                rank = "1 • preferovaný" if index == 1 else str(index)\n',
        "variant rank role",
    )
    text = replace_once(
        text,
        '                    rank, candidate.designation, f"{candidate.physical_length_mm} mm", suffix,\n',
        '                    rank, candidate.connection_type, candidate.designation, f"{candidate.physical_length_mm} mm", suffix,\n',
        "variant row type",
    )

    # Always clear relationship metadata before a new calculation.
    text = replace_once(
        text,
        '        database = self.owner.hit_db\n        if database is None:\n',
        '        database = self.owner.hit_db\n        self._family_info = {}\n        if database is None:\n',
        "reset family info",
    )

    old_call = '''        candidates, error = database.directional_candidates(\n            self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), actions, lengths,\n            self.owner.hit_offsets_var.get(),\n        )\n        self.candidates = candidates\n'''
    new_call = '''        candidates, error, family_info = database.proposal_candidates(\n            self.connection_type.get(), self.series.get(), height, cover, self.concrete.get(), actions, lengths,\n            self.owner.hit_offsets_var.get(),\n        )\n        self._family_info = family_info\n        self.candidates = candidates\n'''
    text = replace_once(text, old_call, new_call, "proposal call")

    text = replace_once(
        text,
        '        self.variants_button.configure(state="normal" if len(candidates) > 1 else "disabled")\n',
        '        alt_type = str(self._family_info.get("alternative_type", ""))\n        alt_count = int(self._family_info.get("alternative_count", 0) or 0)\n        button_text = f"Varianty… +{alt_type}" if alt_count else "Varianty…"\n        self.variants_button.configure(text=button_text, width=14, state="normal" if len(candidates) > 1 else "disabled")\n',
        "variant button relation",
    )

    disabled_marker = '        self.variants_button.configure(state="disabled")\n'
    disabled_count = text.count(disabled_marker)
    if disabled_count < 2:
        raise RuntimeError(f"reset variant button: expected at least 2 matches, got {disabled_count}")
    text = text.replace(disabled_marker, '        self.variants_button.configure(text="Varianty…", state="disabled")\n')

    text = replace_once(
        text,
        '        if self._manual_product:\n            text += " • ručně zvoleno"\n        if candidate.connection_type == "MVX":\n',
        '        if self._manual_product:\n            text += " • ručně zvoleno"\n        preferred_type = self.connection_type.get().strip().upper()\n        if candidate.connection_type != preferred_type:\n            if preferred_type == "MVX" and candidate.connection_type == "MVXL":\n                text += " • náhradní typ MVXL (MVX nevyhovuje)"\n            elif preferred_type == "MVXL" and candidate.connection_type == "MVX":\n                text += " • alternativa MVX místo MVXL"\n        elif self._family_info.get("mode") == "related":\n            text += " • vyhovuje také MVX – viz Varianty…"\n        if candidate.connection_type == "MVX":\n',
        "candidate relation note",
    )

    # Copy/export must contain the actual selected product type, not only the preferred filter.
    text = replace_once(
        text,
        'row.name.get(), row.series.get(), row.connection_type.get(), row.height.get(), row.cover.get(), row.concrete.get()',
        'row.name.get(), row.series.get(), candidate.connection_type, row.height.get(), row.cover.get(), row.concrete.get()',
        "copy actual type",
    )

    return text


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    core = OUT / "hit_core.py"
    core.write_text(patch_core(core.read_text(encoding="utf-8")), encoding="utf-8")

    workspace = OUT / "hit_workspace.py"
    workspace.write_text(patch_workspace(workspace.read_text(encoding="utf-8")), encoding="utf-8")

    app = OUT / "app.pyw"
    app_text = replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "0.9.1"', 'APP_VERSION = "0.9.2"', "app version")
    app.write_text(app_text, encoding="utf-8")

    for path in OUT.iterdir():
        if path.suffix in {".py", ".pyw"}:
            py_compile.compile(str(path), doraise=True)

    # Functional regression of the MVX <-> MVXL recommendation rules.
    import importlib.util
    spec = importlib.util.spec_from_file_location("hit_core_v092", core)
    hc = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(hc)

    payload = {
        "schema_version": 3,
        "catalog_id": "regression",
        "source_document": "regression",
        "ratio_min_m": 0.15,
        "concretes": ["C20/25", "C25/30", "C30/37"],
        "sections": [], "zvx_records": [], "dd_moment": [], "dvl_moment": [],
        "mvxl_records": [{
            "series": "HP", "code": "0806", "length_code": 100, "tail": "0810", "page": 104,
            "mrd_rows": [{"h_eff": 165, "bond": "good", "values": {"C25/30": 100.0}}],
            "vrd_pos_ranges": [{"h_min": 165, "h_max": 165, "values": {"C25/30": 200.0}}],
        }],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "db.b64"
        raw = json.dumps(payload).encode("utf-8")
        db_path.write_text(base64.b64encode(gzip.compress(raw)).decode("ascii"), encoding="ascii")
        db = hc.HitDatabase(db_path)
        # Equivalent MVX: lower capacity than MVXL.
        db.records.append(["HP", "0806", 100, "", 165, "C25/30", 40.0, 100.0, 60.0, 50.0, 11])

        # MVX is sufficient -> do NOT offer MVXL.
        rows, err, info = db.proposal_candidates(
            "MVX", "HP", 200, 35, "C25/30", hc.DirectionalActions(m_neg=30.0), {100}, False
        )
        assert not err and rows and all(row.connection_type == "MVX" for row in rows)
        assert info["mode"] == "preferred" and info["alternative_count"] == 0

        # MVX insufficient -> fallback to MVXL.
        rows, err, info = db.proposal_candidates(
            "MVX", "HP", 200, 35, "C25/30", hc.DirectionalActions(m_neg=70.0, v_pos=80.0), {100}, False
        )
        assert not err and rows and rows[0].connection_type == "MVXL"
        assert rows[0].designation == "HIT-HP MVXL-0806-20-100-35-0810"
        assert info["mode"] == "fallback" and info["alternative_type"] == "MVXL"

        # MVXL selected but MVX is sufficient -> keep MVXL first and append MVX alternatives.
        rows, err, info = db.proposal_candidates(
            "MVXL", "HP", 200, 35, "C25/30", hc.DirectionalActions(m_neg=30.0), {100}, False
        )
        assert not err and rows and rows[0].connection_type == "MVXL"
        assert any(row.connection_type == "MVX" for row in rows[1:])
        assert info["mode"] == "related" and info["alternative_count"] >= 1

    ws_text = workspace.read_text(encoding="utf-8")
    assert 'candidate.connection_type, row.height.get()' in ws_text
    assert '"type": ("Typ", 72, "center")' in ws_text
    assert 'Varianty… +{alt_type}' in ws_text

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO v0.9.2\n"
        "- MVX a MVXL jsou propojeny jako příbuzná návrhová rodina.\n"
        "- Zvolený MVX se nejprve hledá samostatně; teprve když žádný MVX nevyhoví, program automaticky nabídne vyhovující MVXL.\n"
        "- U zvoleného MVXL se současně ověří MVX. Pokud MVX vyhovuje, MVXL zůstává preferovaným hlavním návrhem a MVX je zobrazen jako alternativa v okně Varianty.\n"
        "- Okno Varianty má nový sloupec Typ a rozlišuje preferovaný typ, alternativu a náhradní typ.\n"
        "- Kopírování výsledků i budoucí provazby používají skutečný typ vybraného produktu, nikoli jen původní typ ve filtru.\n",
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
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.9.2/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.9.2",
        "notes": "HIT: inteligentní nabídka příbuzných typů MVX/MVXL – MVXL jako náhrada při nedostatečné MVX a MVX jako alternativa k předimenzované MVXL.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO v0.9.2")


if __name__ == "__main__":
    main()
