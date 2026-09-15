from __future__ import annotations

"""Installed 3.0.0 -> 3.0.1 regression. Fixtures are TEST_ONLY, not design data."""
import copy
import gc
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.parse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates/3.0.1"


def main():
    cache, reads = {}, []
    report = {"version": "3.0.1", "platform": sys.platform}

    def source(request, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        parsed = urllib.parse.urlparse(url)
        assert parsed.netloc == "raw.githubusercontent.com"
        owner, repo, ref, *parts = parsed.path.strip("/").split("/")
        assert (owner, repo) == ("jaroslavkucacz-code", "TURTO-Izolacni-nosniky") and len(ref) == 40
        key = ref + ":" + "/".join(parts)
        reads.append(key)
        if key not in cache:
            cache[key] = subprocess.check_output(["git", "show", key], cwd=ROOT)
        return io.BytesIO(cache[key])

    def snapshot(folder):
        return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in folder.rglob("*") if p.is_file()}

    with tempfile.TemporaryDirectory(prefix="turto_iso301_") as folder:
        root = Path(folder)
        program = root / "Program"
        os.environ.update(TURTO_ROOT=str(root), TURTO_PROGRAM_DIR=str(program),
                          APPDATA=str(root / "appdata"), LOCALAPPDATA=str(root / "localappdata"))
        shutil.copytree(ROOT / "updates/1.1.17/catalogs", root / "catalogs")
        database = root / "actions.sqlite3"
        database.write_bytes(b"UNTOUCHED CUSTOMER DATA")
        original_db = database.read_bytes()
        with patch("urllib.request.urlopen", source):
            runpy.run_path(str(ROOT / "updates/3.0.0/runtime_installer.py"))["install_runtime"](root)
        assert database.read_bytes() == original_db
        baseline = snapshot(program)
        catalog_before = snapshot(root / "catalogs")
        installer = runpy.run_path(str(RELEASE / "runtime_installer.py"))
        installer["selftest"]()

        # Inject one write error, then permit the real rollback writes to finish.
        replace = os.replace
        fault = [False]
        def fail_once(src, dst):
            if Path(dst).name == "iso_bulk_301.py" and not fault[0]:
                fault[0] = True
                raise OSError("TEST_ONLY injected write failure")
            return replace(src, dst)
        with patch("urllib.request.urlopen", source), patch("os.replace", fail_once):
            try:
                installer["install_runtime"](root)
            except OSError:
                pass
            else:
                raise AssertionError("The injected write failure was ignored")
        assert fault[0] and snapshot(program) == baseline
        assert database.read_bytes() == original_db
        with patch("urllib.request.urlopen", source):
            installer["install_runtime"](root)
            count = len(reads)
            installer["install_runtime"](root)
            assert len(reads) == count
        assert installer["_revision_ok"](program)
        assert database.read_bytes() == original_db and snapshot(root / "catalogs") == catalog_before

        shutil.copy2(RELEASE / "app.pyw", root / "app.pyw")
        (root / ".turto_runtime_current.ok").write_text("32", encoding="utf-8")
        boot = runpy.run_path(str(root / "app.pyw"))
        boot["selftest"]()
        assert boot["_runtime_ready"]()
        (program / "turto_icon_301.png.b64").write_text("damaged", encoding="ascii")
        assert not boot["_runtime_ready"]()
        with patch("urllib.request.urlopen", source):
            boot["_repair_runtime"]()
        assert boot["_runtime_ready"]() and database.read_bytes() == original_db
        database.unlink()  # Only remove our test sentinel before the real SQLite application starts.
        boot["_activate_program"]()
        runtime = runpy.run_path(str(program / "app_runtime.pyw"))
        runtime["selftest"]()

        import tkinter as tk
        from tkinter import messagebox, ttk
        import bulk_import
        import bulk_import_engine as engine
        import iso_bulk_301 as iso
        from catalog_engine import CatalogDatabase
        from isokorb_xt_parser_243 import _SAMPLE_ROWS, parse_xt_designation
        from project_model import create_project_row, query_from_selection
        from action_payload import serialize_action, load_action_record
        from action_store import ActionStore
        from PIL import ImageGrab

        failures = []
        tk.Tk.report_callback_exception = lambda self, *exc: failures.append("".join(traceback.format_exception(*exc)))
        text = "\n".join(f"P{i:03d}\t{qty}\t{name}" for i, (name, qty, family) in enumerate(_SAMPLE_ROWS, 1))
        assert len(_SAMPLE_ROWS) == 30 and sum(x[1] for x in _SAMPLE_ROWS) == 601
        with patch.object(messagebox, "showerror", lambda *a, **k: failures.append(str(a))), \
             patch.object(messagebox, "showwarning", lambda *a, **k: None), \
             patch.object(messagebox, "askyesno", return_value=True):
            app = runtime["_base"].ThermalConnectorApp()
            app.update()
            assert app._turto_logo_loaded and app._turto_logo_master.width() == 80
            assert "3.0.1" in app._turto_brand_title.cget("text")
            assert app._turto_brand_title.winfo_ismapped()
            assert any(isinstance(w, ttk.Label) and str(w.cget("image"))
                       for frame in app.winfo_children() if isinstance(frame, ttk.Frame)
                       and str(frame.cget("style")) == "Header.TFrame" for w in frame.winfo_children())
            # Explorer/DWM paints taskbar icons asynchronously, after Tk idle.
            until = time.monotonic() + 1.0
            while time.monotonic() < until:
                app.update()
                time.sleep(0.05)
            if sys.platform == "win32":
                assert app._turto_native_icon_loaded
            report["native_windows_icon_loaded"] = bool(getattr(app, "_turto_native_icon_loaded", False))
            ImageGrab.grab().save(ROOT / f"iso301-window-{sys.platform}.png")

            def analyze(db):
                dialog = bulk_import.BulkImportDialog(app, database=db, colors=app.colors,
                    preferred_concrete="C25/30", existing_positions=[], start_position="P001")
                dialog.text.insert("1.0", text)
                dialog.analyze_button.invoke()  # Actual Tk button, worker, queue and tree refresh.
                deadline = time.monotonic() + 25
                while dialog._analysis_running and time.monotonic() < deadline:
                    app.update()
                    time.sleep(0.02)
                app.update()
                assert not dialog._analysis_running and not failures, failures
                assert len(dialog.items) == 30 and sum(x.quantity for x in dialog.items) == 601
                assert "ISO 3.0.1" in dialog.summary_var.get()
                return dialog

            d = analyze(app.database)
            report["bundled_catalog"] = [{"position": i.position, "status": i.status,
                "candidates": len(i.candidates)} for i in d.items]
            for iid, item in d._item_by_iid.items():
                if item.status == "error":
                    assert not item.candidates and d.review_tree.set(iid, "status") == "Chybí data"
            d.destroy()

            # Exercise the real legacy record schema using isolated, explicitly non-design fixtures.
            families = {}
            for index, (name, quantity, family_name) in enumerate(_SAMPLE_ROWS, 1):
                if index in (3, 13):
                    continue  # Missing KL-VV1 must never be replaced by V1.
                parsed = parse_xt_designation(name)
                f = parsed.fields
                family = families.setdefault((family_name, f["generation"]), {
                    "manufacturer": "Schöck", "model": "XT", "type": family_name,
                    "generation": f["generation"], "insulation_thickness_mm": 120, "records": []})
                record = {"designation": "TEST_ONLY " + parsed.canonical if family_name == "KL" else "TEST_ONLY",
                    "moment_class": "M" + f["moment"] if family_name == "KL" else f.get("shear", "—"),
                    "shear_class": f["shear"] if family_name == "KL" else "—",
                    "cover": "CV" + f["cover"] if family_name == "KL" else "L=" + f["length"] + " mm" if "length" in f else "—",
                    "height_mm": f["height"] if family_name == "KL" else "≥180", "concrete_min": "C25/30",
                    "results": [{"key": "test", "label": "TEST_ONLY", "kind": "shear", "value": 0, "unit": "TEST_ONLY"}]}
                if record not in family["records"]:
                    family["records"].append(record)
            fixture = root / "TEST_ONLY"
            fixture.mkdir()
            (fixture / "fixture.json").write_text(json.dumps({"schema_version": 2,
                "catalog": {"id": "TEST_ONLY", "edition": "TEST_ONLY"}, "families": list(families.values())}), encoding="utf-8")
            db = CatalogDatabase(fixture)
            d = analyze(db)
            assert sum(i.ready for i in d.items) == 28
            assert all(not d.items[i].candidates and not d.items[i].ready for i in (2, 12))
            for item in d.items:
                if item.ready:
                    parsed = parse_xt_designation(item.designation)
                    assert item.result.designation.endswith(parsed.canonical)
                    assert iso._record_matches(item.result.family, item.result.record, parsed, "C25/30")
            p = parse_xt_designation(_SAMPLE_ROWS[21][0])
            assert not iso.candidates_for(db, p, "C30/37")
            assert not iso.candidates_for(db, parse_xt_designation(p.canonical.replace("L300", "L999")), "C25/30")
            assert not iso.candidates_for(db, parse_xt_designation(p.canonical.replace("H240", "H170")), "C25/30")
            assert not iso.candidates_for(db, parse_xt_designation(p.canonical.replace("5.0", "9.9")), "C25/30")
            fam = next(f for f in db.families if f["type"] == "QP")
            original = fam["records"][0]
            different = copy.deepcopy(original)
            different["results"][0]["value"] = 1
            fam["records"].append(different)
            assert len(iso.candidates_for(db, parse_xt_designation(_SAMPLE_ROWS[20][0]), "C25/30")) == 2
            fam["records"].pop()
            app.database = db
            app.project.rows = [create_project_row(i.result, position=i.position, quantity=i.quantity,
                source_text=i.source_designation or i.designation) for i in d.items if i.ready]
            saved_rows = copy.deepcopy(app.project.rows)
            store = ActionStore(root / "test_roundtrip.sqlite3")
            saved = store.save(action_name="TEST_ONLY", payload=serialize_action(app))
            app.project.rows = []
            load_action_record(app, store.load(saved["id"]))
            app.update()
            assert len(app.project.rows) == 28
            for row, before_row in zip(app.project.rows, saved_rows):
                assert row["source_text"] == before_row["source_text"] and row["selection"] == before_row["selection"]
                assert row["snapshot"]["designation"] == before_row["snapshot"]["designation"]
                query_from_selection(db, row["selection"])
            assert not failures, failures
            d.destroy()
            app.destroy()
            del app, d, store
            logging.shutdown()
            gc.collect()
        report.update(update_from_300=True, rollback=True, database_bytes_preserved=True,
            installed_logo_repair=True, bootstrap_ready=True, actual_tk_button=True,
            rows=30, pieces=601, logo_loaded=True, sqlite_roundtrip=True,
            fixture_ready=28, fixture_missing=2, fixture_is_not_manufacturer_data=True)
        (ROOT / f"iso301-test-{sys.platform}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
