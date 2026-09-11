from __future__ import annotations

"""Offline rebuild + actual Tk/SQLite integration smoke for release 2.2.30.

Uses only pinned repository history, no customer data and no network. Run with
xvfb-run on Linux and directly on Windows with tkinter available.
"""
from contextlib import ExitStack
import gc
import io
import logging
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates/2.2.30"


def main():
    cache = {}
    network_reads = []
    def urlopen(request, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        network_reads.append(url)
        parsed = urllib.parse.urlparse(url)
        assert parsed.netloc == "raw.githubusercontent.com", url
        parts = parsed.path.strip("/").split("/")
        assert parts[:2] == ["jaroslavkucacz-code", "TURTO-Izolacni-nosniky"]
        commit, path = parts[2], "/".join(parts[3:])
        key = commit + ":" + path
        if key not in cache:
            cache[key] = subprocess.check_output(["git", "show", key], cwd=ROOT)
        return io.BytesIO(cache[key])

    with tempfile.TemporaryDirectory(prefix="turto_230_smoke_") as folder, ExitStack() as cleanup:
        # ExitStack runs before deletion, including when a GUI assertion fails.
        cleanup.callback(gc.collect)
        cleanup.callback(logging.shutdown)
        root = Path(folder)
        os.environ["TURTO_ROOT"] = str(root)
        os.environ["TURTO_PROGRAM_DIR"] = str(root / "Program")
        os.environ["APPDATA"] = str(root / "appdata")
        os.environ["LOCALAPPDATA"] = str(root / "localappdata")
        # The production installer uses the customer's existing catalog folders.
        shutil.copytree(ROOT / "updates/1.1.17/catalogs", root / "catalogs")
        # Exercise genuine installed 2.2.29 baseline before the new overlay.
        with patch("urllib.request.urlopen", urlopen):
            ns = runpy.run_path(str(ROOT / "updates/2.2.29/runtime_installer.py"))
            ns["install_runtime"](root)
        # The outer bootstrap writes the layout marker after its installer.
        (root / ".turto_runtime_current.ok").write_text("21", encoding="utf-8")
        program = root / "Program"
        if (RELEASE / "runtime_installer.py").exists():
            import sqlite3
            database = root / "actions.sqlite3"
            with sqlite3.connect(database) as con:
                con.execute("CREATE TABLE sentinel (value TEXT)")
                con.execute("INSERT INTO sentinel VALUES ('customer data must survive')")
            con.close()
            before = database.read_bytes()
            with patch("urllib.request.urlopen", urlopen):
                installer = runpy.run_path(str(RELEASE / "runtime_installer.py"))
                installer["selftest"]()
                reads = len(network_reads)
                installer["install_runtime"](root)
                assert len(network_reads) - reads == 7, "Expected an incremental seven-file update"
                assert database.read_bytes() == before
                assert installer["_revision_ok"](program)
                reads = len(network_reads)
                installer["install_runtime"](root)
                assert len(network_reads) == reads, "Second install must not download unchanged files"
                # Corrupt one new file and exercise genuine repair through pinned sources.
                (program / "peikko_catalog.py").write_text("# broken")
                assert not installer["_revision_ok"](program)
                installer["install_runtime"](root)
                assert installer["_revision_ok"](program)
                assert database.read_bytes() == before
            shutil.copy2(RELEASE / "app.pyw", root / "app.pyw")
            bootstrap = runpy.run_path(str(root / "app.pyw"))
            bootstrap["selftest"]()
            assert bootstrap["_runtime_ready"]()
        else:
            # Local development before immutable release commits have been made.
            for name in ("app_runtime.pyw", "peikko_catalog.py", "peikko_workspace.py", "peikko_thermal_breaks.py", "peikko_technical.py", "peikko_documents.py", "peikko_technical_data.json.gz"):
                shutil.copy2(RELEASE / name, program / name)
        sys.path.insert(0, str(program))
        ns = runpy.run_path(str(program / "app_runtime.pyw"))
        ns["selftest"]()
        import tkinter as tk
        from tkinter import messagebox, ttk
        failures = []
        dialogs = []
        tk.Tk.report_callback_exception = lambda self, *a: failures.append(a)
        with patch.object(messagebox, "showwarning", lambda *a, **k: dialogs.append(a)), \
             patch.object(messagebox, "showerror", lambda *a, **k: dialogs.append(a)):
            app = ns["_base"].ThermalConnectorApp()
            def close_app():
                try:
                    app.destroy()
                except tk.TclError:
                    pass
            cleanup.callback(close_app)
            app.update()
            # Cover ordinary 720p workspaces, not only a tall CI virtual display.
            app.geometry("1180x704")
            app.update()
            assert [app.main_notebook.tab(t, "text") for t in app.main_notebook.tabs()] == ["Dekodér", "Návrh", "Záměny"]
            assert not hasattr(app, "peikko_tab")
            from peikko_thermal_breaks import decode_peikko
            from bulk_import_engine import analyze_bulk_text_progressive
            from project_model import create_project_row, row_status
            # Read sample definitions without shadowing the active runtime modules.
            test_ns = runpy.run_path(str(ROOT / "tools/verify_peikko_2229.py"), run_name="fixture_only")
            samples = test_ns["SAMPLES"]
            # Remove source prepend inserted by fixture script: active installed code is authoritative.
            sys.path[:] = [str(program)] + [p for p in sys.path if p not in {str(program), str(RELEASE), str(ROOT / "updates/1.1.17")}]
            items, skipped, cancelled = analyze_bulk_text_progressive(
                app.database, test_ns["pasted_samples"](), preferred_concrete="C25/30")
            assert len(items) == 14 and all(i.ready for i in items), [(i.position, i.message) for i in items]
            assert [i.position for i in items] == [p for p, _ in samples]
            for item in items:
                app.project.add(create_project_row(item.result, position=item.position, quantity=item.quantity,
                    note=item.note, source_text=item.source_designation))
            app.refresh_project_tree()
            first = app.project.rows[0]
            assert app._row_payload(first, 1)[0]["status"] == "K ověření"
            assert app._row_payload(first, 1)[0]["moment"] == "neověřeno"
            assert len(app.project_tree.get_children()) == 14
            app.project_tree.selection_set(first["id"])
            # Manufacturer switching must work in both operations and restore original controls.
            for mode, parent, variable in (("design", app.hit_tab, app.design_manufacturer_var),
                                           ("substitution", app.substitution_tab, app.substitution_manufacturer_var)):
                app.main_notebook.select(parent)
                variable.set("Peikko")
                app.update()
                panel = app._peikko_shared_panels[mode][1]
                assert panel.winfo_ismapped()
                # Numeric output and action rows must fit even at default window height.
                out=panel._peikko_output
                assert out.winfo_rooty()+out.winfo_height() <= parent.winfo_rooty()+parent.winfo_height()
                assert out.winfo_height() >= 80, (mode, app.geometry(), parent.winfo_geometry(), panel.winfo_geometry(), out.winfo_geometry())
                for controls in panel._peikko_action_frames:
                    assert controls.winfo_rooty()+controls.winfo_height() <= parent.winfo_rooty()+parent.winfo_height()
                canvas=panel._peikko_form_canvas
                canvas.yview_moveto(1);app.update();canvas.yview_moveto(0)
                assert all(not w.winfo_ismapped() for w in app._peikko_shared_panels[mode][2])
                panel._peikko_values["designation"].set(samples[8][1])
                panel._peikko_show()
                output = panel._peikko_output.get("1.0", "end")
                assert "S11=120" in output and "Chybí standardní D" in output
                variable.set("Leviat")
                app.update()
                assert not panel.winfo_ismapped()
                assert any(w.winfo_ismapped() for w in app._peikko_shared_panels[mode][2])
            # Actual new controls and invalidation; no background network on construction.
            app.main_notebook.select(app.hit_tab)
            app.design_manufacturer_var.set("Peikko")
            app.project_concrete_var.set("C25/30")
            app.update()
            panel=app._peikko_shared_panels["design"][1]
            v=panel._peikko_values
            v['designation'].set(samples[8][1]);v['D'].set('200');panel._peikko_show()
            output=panel._peikko_output.get('1.0','end')
            assert '|MRd|: 15' in output and 'OQ' in output, output
            v['moment'].set('-10');v['shear'].set('20');v['geometry'].set(True);panel._peikko_check()
            assert 'POROVNÁNÍ NEPROVEDENO' in panel._peikko_output.get('1.0','end')
            v['designation'].set('EBEA-100 RS 4x10-2 D200 SW80 L500')
            assert not v['geometry'].get(), 'Changed product must reset geometry confirmation'
            v['geometry'].set(True);panel._peikko_check()
            output=panel._peikko_output.get('1.0','end')
            assert 'meze nepřekročeny' in output and '43,4783' in output, output
            v['basis'].set('Na metr spoje');v['width'].set('');panel._peikko_check()
            assert 'POROVNÁNÍ NEPROVEDENO' in panel._peikko_output.get('1.0','end')
            v['width'].set('400');panel._peikko_check()
            assert '400 mm' in panel._peikko_output.get('1.0','end')
            v['designation'].set('');v['D'].set('200');v['moment'].set('-19');v['shear'].set('21')
            v['basis'].set('Na jeden prvek');v['geometry'].set(True)
            panel._peikko_preselect();assert len(panel._peikko_candidates)==29
            picker=panel._peikko_picker;picker.current(0);panel._peikko_choose()
            assert v['designation'].get().startswith('EBEA-100') and not v['geometry'].get()
            v['designation'].set('');v['geometry'].set(True);panel._peikko_preselect()
            assert panel._peikko_candidates
            app.project_concrete_var.set('C20/25')
            assert not panel._peikko_candidates and str(picker.cget('state'))=='disabled'
            app.project_concrete_var.set('C25/30')
            v['designation'].set('EBEA-100 RS 4x10-2 SW80 L500');v['D'].set('200')
            panel._peikko_add();assert len(app.project.rows)==15
            assert 'D200' in app.project.rows[-1]['snapshot']['designation']
            added=app.project.rows.pop();app.refresh_project_tree()
            v['family'].set('TEBEA');v['designation'].set('TEBEA CM-V');panel._peikko_show()
            assert 'JEDNU SOUČÁST' in panel._peikko_output.get('1.0','end')
            v['family'].set('EBEA')
            # Optional GUI image for visual QA; never required on customer machines.
            if os.environ.get('TURTO_QA_SCREENSHOT'):
                v['designation'].set('EBEA-100 RS 4x10-2 D200 SW80 L500');v['geometry'].set(True)
                panel._peikko_check();app.main_notebook.select(app.hit_tab);app.update()
                from PIL import ImageGrab
                ImageGrab.grab().save(os.environ['TURTO_QA_SCREENSHOT'])
            # Real save/reload of the central action and manufacturer choices.
            app.design_manufacturer_var.set("Peikko")
            app.substitution_manufacturer_var.set("Peikko")
            from action_payload import serialize_action, load_action_record
            from action_store import ActionStore
            payload = serialize_action(app)
            assert payload["platform_state"]["domains"]["thermal_breaks"]["design_manufacturer"] == "peikko"
            store = ActionStore(root / "roundtrip.sqlite3")
            saved = store.save(action_name="Peikko reference set", payload=payload)
            record = store.load(saved["id"])
            load_action_record(app, record)
            app.update()
            assert len(app.project.rows) == 14
            assert app.design_manufacturer_var.get() == "Peikko"
            assert app.substitution_manufacturer_var.get() == "Peikko"
            for row, (pos, text) in zip(app.project.rows, samples):
                assert row["position"] == pos
                assert row["snapshot"]["designation"] == decode_peikko(text).canonical
                assert row_status(app.database, row)[0] == "ok"
            assert app.project.rows[8]["selection"] != app.project.rows[9]["selection"]
            # Test direct bypass attempts, not just disabled UI buttons.
            import substitution_workspace as sw
            from substitution_review import review_state
            from peikko_catalog import BLOCK_REASON
            for row in app.project.rows:
                metadata = sw.source_metadata(row)
                assert BLOCK_REASON in metadata["errors"]
                targets, errors = sw.design_targets(None, row=row, metadata={})
                assert not targets and BLOCK_REASON in errors
                assert not review_state(row, metadata)["can_accept"]
            # Original shear runtime/Ancon ED and HIT methods are still installed.
            import shear_dowels_current
            shear_dowels_current.selftest()
            assert "plast" in shear_dowels_current.ED_EXPLANATION.lower()
            for method in ("open_shear_design_schedule", "shear_decoder_to_substitution", "refresh_shear_tables",
                           "_build_hit_tab", "rebuild_hit_data"):
                assert callable(getattr(app, method))
            assert not failures, failures
            assert not dialogs, dialogs
    print("OK: installed Tk runtime; 14 bulk rows, no extra tab, manufacturer switching, SQLite roundtrip, safety guards, original HIT/Ancon methods.")


if __name__ == "__main__":
    main()
