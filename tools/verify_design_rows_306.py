from __future__ import annotations

"""Installed Tk/SQLite regression for unused legacy HIT rows, using TEST_ONLY data."""

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
import traceback
from urllib.parse import urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "updates/3.0.6"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def main():
    cache, errors = {}, []
    report = {"version": "3.0.6", "platform": sys.platform, "checks": []}

    def source(request, *args, **kwargs):
        url = urlparse(request.full_url if hasattr(request, "full_url") else str(request))
        assert url.netloc == "raw.githubusercontent.com"
        owner, repo, commit, *parts = url.path.strip("/").split("/")
        assert (owner, repo) == ("jaroslavkucacz-code", "TURTO-Izolacni-nosniky")
        key = commit + ":" + "/".join(parts)
        if key not in cache:
            cache[key] = subprocess.check_output(["git", "show", key], cwd=ROOT)
        return io.BytesIO(cache[key])

    with tempfile.TemporaryDirectory(prefix="turto306_") as folder:
        root = Path(folder)
        program = root / "Program"
        os.environ.update(TURTO_ROOT=str(root), TURTO_PROGRAM_DIR=str(program),
                          APPDATA=str(root / "appdata"), LOCALAPPDATA=str(root / "localappdata"))
        shutil.copytree(ROOT / "updates/1.1.17/catalogs", root / "catalogs")
        sentinel = root / "actions.sqlite3"
        sentinel.write_bytes(b"TEST_ONLY_CUSTOMER_SENTINEL")
        before = digest(sentinel)
        with patch("urllib.request.urlopen", source):
            runpy.run_path(str(ROOT / "updates/3.0.5/runtime_installer.py"))["install_runtime"](root)
        protected = {name: digest(program / name) for name in
                     ("branding_301.py", "turto_icon_301.png.b64", "pdf_branding_305.py", "turto_pdf_logo_305.png.b64")}
        installer = runpy.run_path(str(REL / "runtime_installer.py"))
        with patch("urllib.request.urlopen", source):
            installer["install_runtime"](root)
            installer["install_runtime"](root)
        assert digest(sentinel) == before
        assert protected == {name: digest(program / name) for name in protected}
        sentinel.unlink()
        shutil.copyfile(REL / "app.pyw", root / "app.pyw")
        (root / ".turto_runtime_current.ok").write_text("37")
        assert runpy.run_path(str(root / "app.pyw"))["_runtime_ready"]()
        report["checks"].append("305 to 306 update, bootstrap, idempotency, database and both logos preserved")

        sys.path.insert(0, str(program))
        runtime = runpy.run_path(str(program / "app_runtime.pyw"))
        runtime["selftest"]()
        import tkinter as tk
        from tkinter import ttk, messagebox, simpledialog
        import action_payload
        import design_rows_306 as fix
        import pdf_scope
        from action_store import ActionStore

        tk.Tk.report_callback_exception = lambda self, *exc: errors.append("".join(traceback.format_exception(*exc)))
        with patch.object(messagebox, "showerror", lambda *a, **kw: errors.append(str(a))), \
             patch.object(messagebox, "showwarning", lambda *a, **kw: None), \
             patch.object(messagebox, "askyesno", return_value=True):
            app = runtime["_base"].ThermalConnectorApp()
            app.update()

            def counts():
                return tuple(len(getattr(app, name)) for name in ("hit_rows", "aux_rows", "wt_rows"))

            assert counts() == (0, 0, 0), counts()
            assert not pdf_scope.rows_for_scope(app, "iso.design")
            app.shared_thermal_design.show_legacy()
            for text in ("Desky / balkony", "Doplňkové prvky", "Stěny WT"):
                button = next(w for w in walk(app) if isinstance(w, ttk.Button) and str(w.cget("text")) == text)
                button.invoke()
                app.update()
                assert counts() == (0, 0, 0), (text, counts())
            report["checks"].append("fresh application and all three real module buttons remain empty")

            app.add_hit_row()
            app.add_aux_row_for_type("HT")
            app.add_wt_row()
            assert counts() == (1, 1, 1)
            explicit = action_payload.serialize_action(app)
            assert all(explicit[key][fix.EXPLICIT] is True for key in fix.SECTIONS)
            # Capture real current row constructors, rather than inventing the
            # legacy fixture from the new classifier's DEFAULTS dictionary.
            legacy = copy.deepcopy(explicit)
            for key in fix.SECTIONS:
                legacy[key].pop(fix.EXPLICIT)
                assert fix.is_legacy_initial_row(key, legacy[key]["rows"][0]), (key, legacy[key])
            assert ActionStore._counts(legacy)[1] == 0
            assert ActionStore._counts(explicit)[1] == 3
            report["checks"].append("real factory signatures excluded; explicitly added blank drafts retained")

            store = ActionStore(root / "TEST_ONLY_counts.sqlite3")
            record = store.save(action_name="TEST_ONLY legacy defaults", payload=explicit)
            with store._connect() as connection:
                connection.execute("UPDATE actions SET payload_json=?, hit_count=3 WHERE id=?",
                                   (json.dumps(legacy, ensure_ascii=False), record["id"]))
            snapshot = Path(store.path).read_bytes()
            for query in ("", "legacy"):
                listed = store.list(query)
                assert len(listed) == 1 and listed[0]["hit_count"] == 0, listed
                assert listed[0]["updated_at"] == record["updated_at"]
            assert Path(store.path).read_bytes() == snapshot
            for _ in range(3):
                loaded = store.load(record["id"])
                action_payload.load_action_record(app, loaded)
                app.update()
                assert counts() == (0, 0, 0), counts()
                assert ActionStore._counts(action_payload.serialize_action(app))[1] == 0
                assert not pdf_scope.rows_for_scope(app, "iso.design")
            assert Path(store.path).read_bytes() == snapshot
            report["checks"].append("stale legacy count corrected read-only; repeated load never recreates defaults")

            # Every changed field (including an explicit zero, a name, quantity,
            # geometry, import provenance or selected result) must survive.
            cases = [("name", "rozpracováno"), ("quantity", 2), ("concrete", "C30/37"),
                     ("med_neg", "0"), ("med_neg", "12"), ("selected_designation", "TEST_ONLY PRODUCT"),
                     ("manual_product", True), ("user_note", "ponechat")]
            for key in fix.SECTIONS:
                for field, value in cases + [("height" if key != "wt_design" else "wall_height", "2250")]:
                    payload = copy.deepcopy(legacy)
                    payload[key]["rows"][0][field] = value
                    frozen = copy.deepcopy(payload)
                    assert len(fix.clean_action(payload)[key]["rows"]) == 1, (key, field)
                    assert ActionStore._counts(payload)[1] == 1, (key, field)
                    assert payload == frozen
            report["checks"].append("changed/incomplete/imported/zero-load/manual rows preserved without mutation")

            action_payload.load_action_record(app, {**record, "payload": explicit})
            assert counts() == (1, 1, 1)
            app.hit_rows[0].height.set("220")
            app.aux_rows[0].quantity.set("2")
            app.wt_rows[0].med_neg.set("0")
            app.project_name_var.set("TEST_ONLY saved drafts")
            assert action_payload.save_action(app, as_new=True, forced_name="TEST_ONLY saved drafts")
            actual_store = action_payload.action_store(app)
            saved = actual_store.load(app.action_id)
            assert saved["hit_count"] == 3
            action_payload.load_action_record(app, saved)
            assert counts() == (1, 1, 1)
            assert app.hit_rows[0].height.get() == "220"
            assert app.aux_rows[0].quantity.get() == "2"
            assert app.wt_rows[0].med_neg.get() == "0"
            retained = copy.deepcopy(action_payload.serialize_action(app))
            with patch.object(action_payload, "confirm_action_close", return_value=False):
                app.new_action()
            assert action_payload.serialize_action(app) == retained
            with patch.object(simpledialog, "askstring", return_value="TEST_ONLY new empty action"):
                app.project_dirty = False
                app.new_action()
            assert counts() == (0, 0, 0), counts()
            assert action_payload.save_action(app, as_new=True, forced_name="TEST_ONLY new empty action")
            assert actual_store.load(app.action_id)["hit_count"] == 0
            report["checks"].append("actual Save/New/Cancel paths and SQLite round-trip preserve drafts and zero counts")

            from PIL import ImageGrab
            ImageGrab.grab().save(ROOT / f"design306-window-{sys.platform}.png")
            assert not errors, errors
            app.destroy()
            del app, store, actual_store
            logging.shutdown()
            gc.collect()
    (ROOT / f"design306-test-{sys.platform}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
