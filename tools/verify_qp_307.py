from __future__ import annotations

"""Actual 306 -> 307 installation, manufacturer data, quick entry and SQLite.

No synthetic Schöck capacity fixture is used. --headless runs the data/update
checks only; the mandatory Windows/Linux CI runs also exercise real Tk widgets.
"""
import copy
import gc
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "updates/3.0.7"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    report = dict(version="3.0.7", platform=sys.platform, checks=[])
    cache = {}

    def source(request, *args, **kwargs):
        url = urlparse(request.full_url if hasattr(request, "full_url") else str(request))
        assert url.netloc == "raw.githubusercontent.com"
        owner, repo, commit, *parts = url.path.strip("/").split("/")
        assert (owner, repo) == ("jaroslavkucacz-code", "TURTO-Izolacni-nosniky")
        key = commit + ":" + "/".join(parts)
        if key not in cache:
            cache[key] = subprocess.check_output(["git", "show", key], cwd=ROOT)
        return io.BytesIO(cache[key])

    data = json.loads((REL / "schoeck_t_qp_307.json").read_text(encoding="utf-8"))
    # Validate the actual published table independently of the runtime builder.
    source_path = ROOT / "qp307-source.pdf"
    if not source_path.exists():
        source_path.write_bytes(urllib.request.urlopen(data["catalog"]["source_url"], timeout=90).read())
    assert digest(source_path) == data["catalog"]["source_sha256"]
    import pdfplumber
    with pdfplumber.open(source_path) as pdf:
        text = pdf.pages[127].extract_text()
        capacities = [float(x.replace(",", ".")) for x in re.findall(r"±(\d+,\d+)", text)]
        assert capacities == [r["vrd_kn"] for r in data["table"]]
        assert "C25/30" in text and "[kN/Element]" in text and "AT/2025.1" in text
        tables = pdf.pages[127].extract_tables()
        dimensions = [row for table in tables for row in table if row and any(re.sub(r"\s|\[mm\]", "", str(c)) == "Hmin" for c in row)]
        assert dimensions, tables
        heights = [int(c) for row in dimensions for c in row if c and str(c).isdigit()]
        assert heights == [r["height_min_mm"] for r in data["table"]], heights
        lengths = [row for table in tables for row in table if row and sum(str(c).isdigit() for c in row if c) == 5 and all(c in (None, "", "300", "400", "500") for c in row)]
        assert [int(c) for row in lengths for c in row if c] == [r["length_mm"] for r in data["table"]], lengths
    report["checks"].append("manufacturer PDF SHA, ten +/- capacities, lengths, minimum heights and kN/element")

    with tempfile.TemporaryDirectory(prefix="turto307_") as folder:
        root = Path(folder)
        program = root / "Program"
        os.environ.update(TURTO_ROOT=str(root), TURTO_PROGRAM_DIR=str(program),
                          APPDATA=str(root / "appdata"), LOCALAPPDATA=str(root / "localappdata"))
        shutil.copytree(ROOT / "updates/1.1.17/catalogs", root / "catalogs")
        sentinel = root / "actions.sqlite3"
        sentinel.write_bytes(b"TEST_ONLY_CUSTOMER_SENTINEL")
        before = digest(sentinel)
        with patch("urllib.request.urlopen", source):
            runpy.run_path(str(ROOT / "updates/3.0.6/runtime_installer.py"))["install_runtime"](root)
        protected = {p.name: digest(p) for p in (program / "turto_pdf_logo_305.png.b64", program / "turto_icon_301.png.b64", program / "design_rows_306.py")}
        installer = runpy.run_path(str(REL / "runtime_installer.py"))
        with patch("urllib.request.urlopen", source):
            installer["install_runtime"](root)
            installer["install_runtime"](root)
        assert digest(sentinel) == before
        assert protected == {name: digest(program / name) for name in protected}
        sentinel.unlink()
        shutil.copyfile(REL / "app.pyw", root / "app.pyw")
        (root / ".turto_runtime_current.ok").write_text("38")
        assert runpy.run_path(str(root / "app.pyw"))["_runtime_ready"]()
        report["checks"].append("306 to 307 actual installer, hashes, bootstrap, idempotency, database and logos preserved")

        sys.path.insert(0, str(program))
        runtime = runpy.run_path(str(program / "app_runtime.pyw"))
        runtime["selftest"]()
        import catalog_engine as catalog
        import bulk_import_engine as engine
        import isokorb_qp_307 as fix
        import isokorb_families_304 as families
        from project_model import create_project_row, query_from_selection
        db = catalog.CatalogDatabase(root / "catalogs")
        assert not db.validation_report()[0], db.validation_report()[0]
        original = catalog.CatalogDatabase(root / "catalogs")
        original.families = [f for f in original.families if f["catalog_id"] != fix.CATALOG_ID]
        assert not families.candidates(original, families.parse(fix.EXAMPLE), "C25/30")

        for entry in data["table"]:
            for height in [entry["height_min_mm"], 300]:
                code = f'T-QP-{entry["shear"]}-REI120-H{height}-L{entry["length_mm"]}-5.0'
                result = db.resolve_designation(code, preferred_concrete="C25/30")
                assert result.record["results"][0]["positive"] == entry["vrd_kn"]
                assert result.record["results"][0]["negative"] == -entry["vrd_kn"]
                assert result.insulation_thickness_mm == 80 and result.record["height_mm"] == str(height)
                saved = create_project_row(result, position="TEST_ONLY", quantity=2, source_text=code)
                assert query_from_selection(db, saved["selection"]).results == result.results
                assert saved["snapshot"]["element_length_mm"] == entry["length_mm"]
                assert len(db.suggest_designations(code, preferred_concrete="C25/30")) == 1
        for code, concrete in [(fix.EXAMPLE, "C20/25"), (fix.EXAMPLE, "C30/37")] + [(s, "C25/30") for s in (
                fix.EXAMPLE.replace("VV1", "V1"), fix.EXAMPLE.replace("L300", "L400"),
                fix.EXAMPLE.replace("H200", "H170"), fix.EXAMPLE.replace("H200", "H310"),
                fix.EXAMPLE.replace("5.0", "7.0"), fix.EXAMPLE.replace("REI120", "REI90"), fix.EXAMPLE + "-extra")]:
            assert not db.suggest_designations(code, preferred_concrete=concrete), code
            try:
                db.resolve_designation(code, preferred_concrete=concrete)
            except catalog.SelectionError:
                pass
            else:
                raise AssertionError(code)
            item = engine.BulkImportItem(1, code, "TEST_ONLY", 1, code)
            engine._classify_bulk_item(db, item, preferred_concrete=concrete, suggestion_limit=80)
            assert not item.ready and not item.candidates, code
        full = "Schöck Isokorb® T typ QP-VV1-REI120-H200-L300-5.0"
        assert db.resolve_designation(full, preferred_concrete="C25/30").record["height_mm"] == "200"
        report["checks"].append("real catalogue, all VV grades, strict rejects, aliases and persistent selections")

        if "--headless" not in sys.argv:
            import tkinter as tk
            from tkinter import messagebox
            import bulk_import, action_payload
            errors = []
            tk.Tk.report_callback_exception = lambda self, *exc: errors.append("".join(traceback.format_exception(*exc)))
            with patch.object(messagebox, "showerror", lambda *a, **kw: errors.append(str(a))), \
                 patch.object(messagebox, "showwarning", lambda *a, **kw: errors.append(str(a))):
                app = runtime["_base"].ThermalConnectorApp()
                app.update()
                app.quick_var.set(fix.EXAMPLE)
                app.apply_quick_designation()
                app.update()
                assert app.current_result is not None and app.current_result.record["height_mm"] == "200"
                assert app.current_result.record["results"][0]["negative"] == -30.9
                assert "3.0.7" in app._turto_brand_title.cget("text")
                dialog = bulk_import.BulkImportDialog(app, database=app.database, colors=app.colors,
                    preferred_concrete="C25/30", existing_positions=[], start_position="P001")
                dialog.text.insert("1.0", "P001\t2\t" + fix.EXAMPLE)
                dialog.analyze_button.invoke()
                deadline = time.monotonic() + 30
                while dialog._analysis_running and time.monotonic() < deadline:
                    app.update()
                    time.sleep(.02)
                assert len(dialog.items) == 1 and dialog.items[0].ready
                result = dialog.items[0].result
                assert result.record["results"][0]["positive"] == 30.9
                app.project.rows = [create_project_row(result, position="TEST_ONLY", quantity=2, source_text=fix.EXAMPLE)]
                dialog.destroy()
                assert not app.hit_rows and not app.aux_rows and not app.wt_rows
                assert action_payload.save_action(app, as_new=True, forced_name="TEST_ONLY QP 307")
                saved = action_payload.action_store(app).load(app.action_id)
                action_payload.load_action_record(app, saved)
                row = app.project.rows[0]
                assert row["quantity"] == 2 and row["selection"]["height_mm"] == "200"
                assert row["snapshot"]["element_length_mm"] == 300
                assert row["snapshot"]["results"][0]["negative"] == -30.9
                assert query_from_selection(app.database, row["selection"]).results == row["snapshot"]["results"]
                assert not errors, errors
                app.destroy()
                del app, dialog
                logging.shutdown()
                gc.collect()
            report["checks"].append("real quick-entry widget, progressive import dialog, SQLite Save/Load and no phantom design rows")
    (ROOT / f"qp307-test-{sys.platform}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
