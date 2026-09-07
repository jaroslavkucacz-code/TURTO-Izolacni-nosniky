from __future__ import annotations

"""TURTO ISO 1.1.23 – central AKCE workspace.

This is a thin compatibility entry point over the verified 1.1.17 application.
It deliberately keeps the calculation/catalogue modules intact and changes only
workspace composition and persistence: Decoder ISO, Návrh HIT and Záměny za HIT
now live under one central database record called AKCE.
"""

import tkinter as tk
from tkinter import ttk

import app_base as _base
import project_ui
import hit_workspace
import substitution_workspace
from action_workspace import build_action_bar, install as install_actions
from hit_decoder_catalog import CombinedCatalogDatabase

APP_VERSION = "1.1.23"
_base.APP_VERSION = APP_VERSION

# Decoder ISO receives the ordinary catalogue database plus the managed HIT
# database used by the design engine. Other application code keeps using the
# same CatalogDatabase-shaped interface.
_base.CatalogDatabase = CombinedCatalogDatabase

# All inherited methods live on the same mixin objects even though the app class
# was already declared while app_base was imported. Install persistence after
# the Decoder/HIT wrappers so it sees their final row lifecycle.
install_actions(project_ui.ProjectWorkspaceMixin, hit_workspace.HitInputRow, hit_workspace.HitWorkspaceMixin)

try:
    hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    hit_workspace._base.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
except Exception:
    pass


def _walk(root):
    stack = [root]
    while stack:
        widget = stack.pop(); yield widget
        try: stack.extend(widget.winfo_children())
        except Exception: pass


def _hide_button(root, text: str) -> None:
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text: widget.grid_remove()
        except Exception: pass


def _patch_header(self) -> None:
    _ORIGINAL_HEADER(self)
    for widget in _walk(self):
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text"))
                if text == "TURTO ISO | Databáze izolačních nosníků":
                    widget.configure(text="TURTO ISO | Izolační nosníky")
                elif text == "Projektový soupis a rychlé vyhledání statických hodnot podle výrobce, generace a úplného typu":
                    widget.configure(text="Jedna AKCE • Dekodér ISO • Návrh HIT • Záměny za HIT • společné centrální uložení")
            elif isinstance(widget, ttk.Button):
                text = str(widget.cget("text"))
                if text == "Složka databáze": widget.configure(text="Složka katalogů")
                elif text == "Kontrola databáze": widget.configure(text="Kontrola katalogů")
        except Exception: pass


def _build_body(self) -> None:
    body = ttk.Frame(self, style="App.TFrame", padding=(18, 12, 18, 12))
    body.grid(row=1, column=0, sticky="nsew"); body.columnconfigure(0, weight=1); body.rowconfigure(1, weight=1)
    action_bar = build_action_bar(self, body); action_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    self.main_notebook = ttk.Notebook(body, style="Workspace.TNotebook"); self.main_notebook.grid(row=1, column=0, sticky="nsew")
    self.project_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
    self.hit_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
    self.substitution_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
    self.main_notebook.add(self.project_tab, text="Dekodér ISO")
    self.main_notebook.add(self.hit_tab, text="Návrh HIT")
    self.main_notebook.add(self.substitution_tab, text="Záměny za HIT")
    self._build_project_tab(self.project_tab); self._build_hit_tab(self.hit_tab); self._build_substitution_tab(self.substitution_tab)
    _hide_button(self.hit_tab, "Uložit návrh"); _hide_button(self.hit_tab, "Návrhy…")
    self.main_notebook.bind("<<NotebookTabChanged>>", self._on_substitution_tab_selected, add="+")
    self.main_notebook.select(self.project_tab)
    self._action_loading = False
    if str(self.project_name_var.get()).strip() in {"", "Nový objekt"}:
        self._project_var_guard = True
        try: self.project.name = "Nová akce"; self.project_name_var.set("Nová akce")
        finally: self._project_var_guard = False
    self.project_dirty = False; self.project.path = None; self._update_action_info(); self._update_project_title()


def _noop(*_args, **_kwargs): return None

def _refresh_project_concrete_filter(self) -> None: return None


def _on_close(self) -> None:
    if not self.confirm_action_close(): return
    try:
        if hasattr(self, "capture_project_table_layout"): self.capture_project_table_layout(save=False)
    except Exception: pass
    self.settings["theme"] = self.theme_name; self.settings["geometry"] = self.geometry(); self._save_settings(); self.destroy()


_ORIGINAL_HEADER = _base.ThermalConnectorApp._build_header
_base.ThermalConnectorApp._build_header = _patch_header
_base.ThermalConnectorApp._build_body = _build_body
_base.ThermalConnectorApp._populate_initial_data = _noop
_base.ThermalConnectorApp._restore_selections = _noop
_base.ThermalConnectorApp.refresh_result = _noop
_base.ThermalConnectorApp._apply_initial_sash = _noop
_base.ThermalConnectorApp.refresh_project_concrete_filter = _refresh_project_concrete_filter
_base.ThermalConnectorApp.on_close = _on_close

_original_confirm_substitution = substitution_workspace.SubstitutionWorkspaceMixin.confirm_substitution_choice

def _confirm_substitution(self) -> None:
    _original_confirm_substitution(self)
    try: self.sub_status_var.set(str(self.sub_status_var.get()).replace("Uložte projekt", "Uložte AKCI"))
    except Exception: pass

substitution_workspace.SubstitutionWorkspaceMixin.confirm_substitution_choice = _confirm_substitution

if __name__ == "__main__":
    raise SystemExit(_base.main())
