from __future__ import annotations

"""Regression for TURTO 2.2.33 shared Leviat HIT design-group routing.

The release must not introduce a replacement structural calculator. It exposes
the verified runtime workspaces that already design standard HIT, supplementary
HT/AT/FT/OTX and HIT-WT elements.
"""

from contextlib import ExitStack
import gc
import io
import logging
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates/2.2.33"


def main() -> None:
    source = (RELEASE / "design_groups_restore.py").read_text(encoding="utf-8")
    for forbidden in ("design_wt(", "proposal_candidates(", "calculate(", "design_ht_candidates("):
        assert forbidden not in source, f"2.2.33 router must not calculate: {forbidden}"

    cache: dict[str, bytes] = {}
    reads: list[str] = []

    def urlopen(request, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        reads.append(url)
        parsed = urllib.parse.urlparse(url)
        assert parsed.netloc == "raw.githubusercontent.com"
        parts = parsed.path.strip("/").split("/")
        assert parts[:2] == ["jaroslavkucacz-code", "TURTO-Izolacni-nosniky"]
        key = parts[2] + ":" + "/".join(parts[3:])
        if key not in cache:
            cache[key] = subprocess.check_output(["git", "show", key], cwd=ROOT)
        return io.BytesIO(cache[key])

    with tempfile.TemporaryDirectory(prefix="turto_groups_233_") as folder, ExitStack() as cleanup:
        cleanup.callback(gc.collect)
        cleanup.callback(logging.shutdown)
        root = Path(folder)
        program = root / "Program"
        os.environ.update(
            TURTO_ROOT=str(root),
            TURTO_PROGRAM_DIR=str(program),
            APPDATA=str(root / "appdata"),
            LOCALAPPDATA=str(root / "localappdata"),
        )
        shutil.copytree(ROOT / "updates/1.1.17/catalogs", root / "catalogs")

        database = root / "actions.sqlite3"
        database.write_bytes(b"TEST CUSTOMER DATABASE SENTINEL")
        before = database.read_bytes()

        installer = runpy.run_path(str(RELEASE / "runtime_installer.py"))
        installer["selftest"]()
        with patch("urllib.request.urlopen", urlopen):
            installer["install_runtime"](root)
        assert installer["_revision_ok"](program)
        assert database.read_bytes() == before
        first_reads = len(reads)

        with patch("urllib.request.urlopen", urlopen):
            installer["install_runtime"](root)
        assert len(reads) == first_reads, "healthy 2.2.33 runtime should not download again"

        # Bootstrap contract and critical hashes must recognize the installed runtime.
        shutil.copy2(RELEASE / "app.pyw", root / "app.pyw")
        (root / ".turto_runtime_current.ok").write_text("21", encoding="utf-8")
        bootstrap = runpy.run_path(str(root / "app.pyw"))
        bootstrap["selftest"]()
        assert bootstrap["_runtime_ready"]()

        database.unlink()  # remove sentinel before exercising the real SQLite application
        sys.path.insert(0, str(program))
        ns = runpy.run_path(str(program / "app_runtime.pyw"))
        ns["selftest"]()

        import tkinter as tk
        from tkinter import messagebox

        failures = []
        dialogs = []
        tk.Tk.report_callback_exception = lambda self, *args: failures.append(args)

        with (
            patch.object(messagebox, "showwarning", lambda *a, **k: dialogs.append(a)),
            patch.object(messagebox, "showerror", lambda *a, **k: dialogs.append(a)),
        ):
            app = ns["_base"].ThermalConnectorApp()
            cleanup.callback(app.destroy)
            app.update()
            app.geometry("1180x704")
            app.main_notebook.select(app.hit_tab)
            app.update()

            shared = app.shared_thermal_design
            assert set(shared.hit_group_buttons) == {"standard", "aux", "wt"}
            assert shared.hit_group_bar.winfo_ismapped()

            assert "DVL" in shared.hit_group_buttons["standard"]._turto_group_detail
            assert "DDL" in shared.hit_group_buttons["standard"]._turto_group_detail
            assert "HT" in shared.hit_group_buttons["aux"]._turto_group_detail
            assert "AT" in shared.hit_group_buttons["aux"]._turto_group_detail
            assert "FT" in shared.hit_group_buttons["aux"]._turto_group_detail
            assert "OTX" in shared.hit_group_buttons["aux"]._turto_group_detail
            assert "WT" in shared.hit_group_buttons["wt"]._turto_group_detail

            assert callable(getattr(app, "add_aux_row_for_type", None))
            assert callable(getattr(app, "add_wt_row", None))
            assert callable(getattr(app, "add_hit_row_for_type", None))

            mapping = {
                "standard": "hit_standard_tab",
                "aux": "hit_aux_tab",
                "wt": "hit_wt_tab",
            }
            app.project_dirty = False
            for group, attr in mapping.items():
                shared.show_hit_group(group)
                app.update()
                assert app.hit_design_notebook.winfo_ismapped()
                assert app.hit_design_notebook.select() == str(getattr(app, attr))
                assert not shared.winfo_ismapped()
                assert not app.project_dirty, "navigation alone must not dirty the AKCE"
                shared.show_common()
                app.update()
                assert shared.winfo_ismapped()
                assert shared.hit_group_bar.winfo_ismapped()
                assert not app.project_dirty

            # Peikko keeps the same common form and never gains a new top-level tab.
            app.design_manufacturer_var.set("Peikko")
            app.update()
            assert shared.winfo_ismapped()
            assert not shared.hit_group_bar.winfo_ismapped()
            assert len(app.main_notebook.tabs()) == 3

            app.design_manufacturer_var.set("Leviat")
            app.update()
            assert shared.hit_group_bar.winfo_ismapped()
            assert "Vložit výkaz…" in shared.buttons

            assert not failures, failures
            assert not dialogs, dialogs

    print(
        "OK 2.2.33: standard DVL/DDL, HT/AT/FT/OTX and WT route to existing verified HIT workspaces; "
        "no new calculator, Peikko tabs unchanged, DB preserved."
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
