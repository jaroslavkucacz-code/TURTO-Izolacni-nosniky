from __future__ import annotations
"""TURTO 2.2.36: tested HSD / CRET file-to-decoder workflow."""
import runpy
import sys
from pathlib import Path
APP_VERSION = "2.2.36"
PROGRAM = Path(__file__).resolve().parent
if str(PROGRAM) not in sys.path:
    sys.path.insert(0,str(PROGRAM))
_namespace = runpy.run_path(str(PROGRAM / "app_runtime_235.pyw"),run_name="turto_runtime_235")
_base = _namespace["_base"]
_hit_workspace = _namespace.get("_hit_workspace")
import shear_workflow_236
shear_workflow_236.install(_base)
# Compact button padding is local to the HSD controls. Windows work areas lose
# additional vertical pixels to window chrome/taskbar; do not shrink font sizes.
_build_hsd_body = _base.ThermalConnectorApp._build_body
def _build_hsd_display(owner):
    _build_hsd_body(owner)
    from tkinter import ttk
    style = ttk.Style(owner)
    style.configure("HSD.TButton", padding=(8, 4))
    style.configure("HSD.Accent.TButton", padding=(8, 5))
    style.configure("HSD.Workspace.TNotebook.Tab", padding=(10, 4))
    owner.shear_notebook.configure(style="HSD.Workspace.TNotebook")
    controls = owner.hsd_designation_entry.master.master
    for widget in shear_workflow_236._walk(controls):
        if isinstance(widget, ttk.Button):
            widget.configure(style="HSD.Accent.TButton" if "Accent" in str(widget.cget("style")) else "HSD.TButton")
_base.ThermalConnectorApp._build_body = _build_hsd_display

_base.APP_VERSION = APP_VERSION
_base.APP_NAME = "TURTO"
import platform_workspace
platform_workspace.WORKSPACE_VERSION = APP_VERSION
if _hit_workspace is not None:
    _hit_workspace.HIT_MODULE_VERSION = APP_VERSION

def selftest():
    assert _base.ThermalConnectorApp._turto_hsd_workflow_236
    import halfen_hsd_2026 as hsd
    hsd.selftest()
    assert hsd.decode_designation("CRET 122 V")["designation"] == "HSD-CRET 122 V"

if __name__ == "__main__":
    raise SystemExit(_base.main())
