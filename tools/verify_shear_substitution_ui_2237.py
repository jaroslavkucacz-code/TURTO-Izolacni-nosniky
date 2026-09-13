from __future__ import annotations

"""Installed TURTO 2.2.37 Tk regression for shear-dowel substitutions.

The test installs the pinned runtime into a disposable root, preserves a
sentinel actions.sqlite3 byte-for-byte and drives the actual substitution UI.
"""

import gc
import io
import json
import logging
import os
from pathlib import Path
import runpy
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.parse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates/2.2.37"


def main() -> None:
    cache: dict[str, bytes] = {}
    reads: list[str] = []

    def urlopen(request, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        parsed = urllib.parse.urlparse(url)
        assert parsed.netloc == "raw.githubusercontent.com", url
        owner, repo, ref, *parts = parsed.path.strip("/").split("/")
        assert (owner, repo) == ("jaroslavkucacz-code", "TURTO-Izolacni-nosniky")
        assert len(ref) == 40, ref
        key = ref + ":" + "/".join(parts)
        reads.append(key)
        if key not in cache:
            cache[key] = subprocess.check_output(["git", "show", key], cwd=ROOT)
        return io.BytesIO(cache[key])

    report = {"version": "2.2.37", "platform": sys.platform}
    with tempfile.TemporaryDirectory(prefix="turto_2237_ui_", ignore_cleanup_errors=True) as folder:
        root = Path(folder)
        program = root / "Program"
        os.environ.update(
            TURTO_ROOT=str(root),
            TURTO_PROGRAM_DIR=str(program),
            APPDATA=str(root / "appdata"),
            LOCALAPPDATA=str(root / "localappdata"),
        )
        shutil.copytree(ROOT / "updates/1.1.17/catalogs", root / "catalogs")

        db = root / "actions.sqlite3"
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE sentinel(v TEXT)")
            con.execute("INSERT INTO sentinel VALUES ('unchanged customer data')")
        before = db.read_bytes()

        installer = runpy.run_path(str(RELEASE / "runtime_installer.py"))
        installer["selftest"]()
        with patch("urllib.request.urlopen", urlopen):
            installer["install_runtime"](root)
        assert installer["_revision_ok"](program)
        assert db.read_bytes() == before
        (root / ".turto_runtime_current.ok").write_text("21", encoding="utf-8")

        sys.path.insert(0, str(program))
        runtime = runpy.run_path(str(program / "app_runtime.pyw"))
        runtime["selftest"]()

        import tkinter as tk
        from tkinter import messagebox, ttk
        import shear_substitution_237 as s237

        failures: list[str] = []

        def callback_error(_owner, *exc):
            import traceback
            failures.append("".join(traceback.format_exception(*exc)))

        tk.Tk.report_callback_exception = callback_error
        with (
            patch.object(messagebox, "showerror", lambda *a, **k: failures.append(str(a))),
            patch.object(messagebox, "showwarning", lambda *a, **k: None),
            patch.object(messagebox, "showinfo", lambda *a, **k: None),
            patch.object(messagebox, "askyesno", return_value=True),
        ):
            app = runtime["_base"].ThermalConnectorApp()
            app.update()
            assert getattr(app, "_turto_substitution_ui_237", False)
            columns = tuple(app.shear_substitution_tree["columns"])
            assert "mode237" in columns and "ved237" in columns, columns

            app.shear_target_manufacturer_var.set("Ancon")
            app.shear_substitution_rows = [{
                "name": "S005",
                "quantity": 6,
                "source_designation": "CRET 140",
                "slab_mm": 350.0,
                "gap_mm": 20.0,
                "concrete": "C30/37",
                "cover_mm": 30,
                "low_sleeve": "stainless",
                "origin": "manual",
                "verification_mode": "catalog",
            }]
            app.refresh_shear_tables()
            app.update()

            row = app.shear_substitution_rows[0]
            assert row["source"]["designation"] == "HSD-CRET 140", row
            assert row["source"]["vrd"] == 347.0, row
            assert row["target"]["designation"] == "Ancon HLD 42", row
            assert row["target"]["vrd"] == 334.0, row
            assert row["status"] == "OVĚŘIT VEd", row
            assert app.shear_substitution_tree.set("0", "mode237") == "Katalogová VRd"
            assert app.shear_substitution_tree.set("0", "ved237") == "—"

            tab = app.shear_notebook.nametowidget(app.shear_notebook.tabs()[2])
            ved_button = s237._find_widget(tab, ttk.Button, "Ověřit vybrané dle VEd…")
            catalog_button = s237._find_widget(tab, ttk.Button, "Vybrané zpět na katalogovou VRd")
            assert ved_button is not None and catalog_button is not None

            app.shear_substitution_tree.selection_set("0")
            with patch.object(s237.simpledialog, "askfloat", return_value=320.0):
                ved_button.invoke()
            app.update()
            row = app.shear_substitution_rows[0]
            assert row["status"] == "VYHOVUJE dle VEd", row
            assert row["target"]["designation"] == "Ancon HLD 42", row
            assert row["target"]["vrd"] == 334.0, row
            assert app.shear_substitution_tree.set("0", "mode237") == "Podle VEd"
            assert app.shear_substitution_tree.set("0", "ved237") == "320,0"

            app.shear_substitution_tree.selection_set("0")
            with patch.object(s237.simpledialog, "askfloat", return_value=340.0):
                ved_button.invoke()
            app.update()
            row = app.shear_substitution_rows[0]
            assert row["status"] == "NELZE dle VEd", row
            assert row["target"]["designation"] == "Ancon HLD 42", row
            assert row["target"]["vrd"] == 334.0, row
            assert app.shear_substitution_tree.set("0", "ved237") == "340,0"

            app.shear_substitution_tree.selection_set("0")
            catalog_button.invoke()
            app.update()
            row = app.shear_substitution_rows[0]
            assert row["status"] == "OVĚŘIT VEd", row
            assert row["target"]["designation"] == "Ancon HLD 42", row
            assert app.shear_substitution_tree.set("0", "mode237") == "Katalogová VRd"
            assert app.shear_substitution_tree.set("0", "ved237") == "—"
            assert not failures, failures

            report.update(
                database_bytes_preserved=True,
                source="HSD-CRET 140",
                source_vrd=347.0,
                candidate="Ancon HLD 42",
                candidate_vrd=334.0,
                catalog_status="OVĚŘIT VEd",
                ved_320_status="VYHOVUJE dle VEd",
                ved_340_status="NELZE dle VEd",
                interpolation=False,
                runtime_downloads=len(reads),
            )
            app.destroy()
            logging.shutdown()
            del app
            gc.collect()

        assert db.read_bytes() == before

    output = ROOT / f"shear-2237-test-{sys.platform}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("2.2.37 installed Tk substitution regression: PASS")


if __name__ == "__main__":
    main()
