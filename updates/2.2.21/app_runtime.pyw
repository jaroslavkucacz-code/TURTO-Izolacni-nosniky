from __future__ import annotations

"""TURTO 2.2.21 runtime – central AKCE layer flattened directly over app_base."""

import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from runtime_paths import data_directory, install_root, program_root

ROOT = install_root()
PROGRAM = program_root()
os.environ["TURTO_ROOT"] = str(ROOT)
os.environ["TURTO_PROGRAM_DIR"] = str(PROGRAM)

import app_base as _base
import project_ui
import hit_workspace
import substitution_workspace
import bulk_import
from action_workspace import build_action_bar, install as install_actions
from hit_decoder_catalog import CombinedCatalogDatabase
from table_polish import install_substitution
import wt_safety_guard  # noqa: F401
from platform_workspace import install as install_platform_workspace
from schoeck_dorn_decoder import install as install_schoeck_dorn_decoder
from shear_movement import install as install_shear_movement
from isokorb_compat import install as install_isokorb_compat
from substitution_guard import install as install_substitution_guard

APP_VERSION = "2.2.21"
_BASE = _base

# Former app_central_prev (1.1.23): central AKCE composition is installed here.
_base.APP_VERSION = APP_VERSION
_base.CatalogDatabase = CombinedCatalogDatabase

install_actions(
    project_ui.ProjectWorkspaceMixin,
    hit_workspace.HitInputRow,
    hit_workspace.HitWorkspaceMixin,
)

try:
    hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    if hasattr(hit_workspace, "_base"):
        hit_workspace._base.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
except Exception:
    pass


def _walk(root):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _hide_button(root, text: str) -> None:
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
                widget.grid_remove()
        except Exception:
            pass


_CENTRAL_ORIGINAL_HEADER = _base.ThermalConnectorApp._build_header


def _central_header(self) -> None:
    _CENTRAL_ORIGINAL_HEADER(self)
    for widget in _walk(self):
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text"))
                if text == "TURTO ISO | Databáze izolačních nosníků":
                    widget.configure(text="TURTO ISO | Izolační nosníky")
                elif text == (
                    "Projektový soupis a rychlé vyhledání statických hodnot "
                    "podle výrobce, generace a úplného typu"
                ):
                    widget.configure(
                        text=(
                            "Jedna AKCE • Dekodér ISO • Návrh HIT • Záměny za HIT "
                            "• společné centrální uložení"
                        )
                    )
            elif isinstance(widget, ttk.Button):
                text = str(widget.cget("text"))
                if text == "Složka databáze":
                    widget.configure(text="Složka katalogů")
                elif text == "Kontrola databáze":
                    widget.configure(text="Kontrola katalogů")
        except Exception:
            pass


def _central_build_body(self) -> None:
    body = ttk.Frame(self, style="App.TFrame", padding=(18, 12, 18, 12))
    body.grid(row=1, column=0, sticky="nsew")
    body.columnconfigure(0, weight=1)
    body.rowconfigure(1, weight=1)

    action_bar = build_action_bar(self, body)
    action_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

    self.main_notebook = ttk.Notebook(body, style="Workspace.TNotebook")
    self.main_notebook.grid(row=1, column=0, sticky="nsew")

    self.project_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
    self.hit_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))
    self.substitution_tab = ttk.Frame(self.main_notebook, style="App.TFrame", padding=(0, 12, 0, 0))

    self.main_notebook.add(self.project_tab, text="Dekodér ISO")
    self.main_notebook.add(self.hit_tab, text="Návrh HIT")
    self.main_notebook.add(self.substitution_tab, text="Záměny za HIT")

    self._build_project_tab(self.project_tab)
    self._build_hit_tab(self.hit_tab)
    self._build_substitution_tab(self.substitution_tab)
    for widget in _walk(self.substitution_tab):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Aktualizovat z projektu":
                widget.configure(text="Aktualizovat z Dekodéru ISO")
        except Exception:
            pass

    _hide_button(self.hit_tab, "Uložit návrh")
    _hide_button(self.hit_tab, "Návrhy…")

    self.main_notebook.bind("<<NotebookTabChanged>>", self._on_substitution_tab_selected, add="+")
    self.main_notebook.select(self.project_tab)

    self._action_loading = False
    if str(self.project_name_var.get()).strip() in {"", "Nový objekt"}:
        self._project_var_guard = True
        try:
            self.project.name = "Nová akce"
            self.project_name_var.set("Nová akce")
        finally:
            self._project_var_guard = False
    self.project_dirty = False
    self.project.path = None
    self._update_action_info()
    self._update_project_title()


def _central_noop(*_args, **_kwargs):
    return None


def _central_refresh_project_concrete_filter(self) -> None:
    return None


def _central_on_close(self) -> None:
    if not self.confirm_action_close():
        return
    try:
        if hasattr(self, "capture_project_table_layout"):
            self.capture_project_table_layout(save=False)
    except Exception:
        pass
    self.settings["theme"] = self.theme_name
    self.settings["geometry"] = self.geometry()
    self._save_settings()
    self.destroy()


_base.ThermalConnectorApp._build_header = _central_header
_base.ThermalConnectorApp._build_body = _central_build_body
_base.ThermalConnectorApp._populate_initial_data = _central_noop
_base.ThermalConnectorApp._restore_selections = _central_noop
_base.ThermalConnectorApp.refresh_result = _central_noop
_base.ThermalConnectorApp._apply_initial_sash = _central_noop
_base.ThermalConnectorApp.refresh_project_concrete_filter = _central_refresh_project_concrete_filter
_base.ThermalConnectorApp.on_close = _central_on_close

_CENTRAL_SUB_REFRESH = substitution_workspace.SubstitutionWorkspaceMixin.refresh_substitution_tree


def _central_refresh_substitution(self) -> None:
    _CENTRAL_SUB_REFRESH(self)
    try:
        self.sub_status_var.set(
            str(self.sub_status_var.get()).replace("řádků projektu", "řádků Dekodéru ISO")
        )
    except Exception:
        pass


substitution_workspace.SubstitutionWorkspaceMixin.refresh_substitution_tree = _central_refresh_substitution

_CENTRAL_BULK_INIT = bulk_import.BulkImportDialog.__init__


def _central_bulk_decoder_init(self, *args, **kwargs):
    _CENTRAL_BULK_INIT(self, *args, **kwargs)
    try:
        self.title("Hromadné dekódování z výkazu")
    except Exception:
        pass
    for widget in _walk(self):
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text"))
                if text == "Hromadné vložení z výkazu":
                    widget.configure(text="Hromadné dekódování z výkazu")
                elif text.startswith("Beton projektu:"):
                    widget.configure(text=text.replace("Beton projektu:", "Beton AKCE:"))
        except Exception:
            pass


bulk_import.BulkImportDialog.__init__ = _central_bulk_decoder_init

_CENTRAL_CONFIRM_SUBSTITUTION = substitution_workspace.SubstitutionWorkspaceMixin.confirm_substitution_choice


def _central_confirm_substitution(self) -> None:
    _CENTRAL_CONFIRM_SUBSTITUTION(self)
    try:
        self.sub_status_var.set(str(self.sub_status_var.get()).replace("Uložte projekt", "Uložte AKCI"))
    except Exception:
        pass


substitution_workspace.SubstitutionWorkspaceMixin.confirm_substitution_choice = _central_confirm_substitution


def _root_aware_app_root() -> Path:
    return ROOT


def _root_aware_bundled_root() -> Path:
    return PROGRAM


def _root_aware_choose_data_directory(name: str) -> Path:
    return data_directory(name)


_base.app_root = _root_aware_app_root
_base.bundled_root = _root_aware_bundled_root
_base.choose_data_directory = _root_aware_choose_data_directory

install_substitution(substitution_workspace.SubstitutionWorkspaceMixin)

_CURRENT_ORIGINAL_HEADER = _base.ThermalConnectorApp._build_header


def _current_header(self) -> None:
    _CURRENT_ORIGINAL_HEADER(self)
    for widget in _walk(self):
        if not isinstance(widget, ttk.Label):
            continue
        try:
            text = str(widget.cget("text"))
            if text.startswith("Jedna AKCE • Dekodér ISO"):
                widget.configure(
                    text=(
                        "Jedna AKCE • Dekodér ISO • Návrh HIT pro desky i WT stěny • "
                        "Záměny za HIT • společné centrální uložení"
                    )
                )
        except Exception:
            pass


_base.ThermalConnectorApp._build_header = _current_header
install_platform_workspace(_base)

try:
    _base.APP_VERSION = APP_VERSION
    _base.APP_NAME = "TURTO"
except Exception:
    pass

try:
    hit_workspace.HIT_MODULE_VERSION = APP_VERSION
    if hasattr(hit_workspace, "_prev"):
        hit_workspace._prev.HIT_MODULE_VERSION = APP_VERSION  # type: ignore[attr-defined]
except Exception:
    pass

try:
    import platform_workspace as _platform_workspace
    _platform_workspace.WORKSPACE_VERSION = APP_VERSION
except Exception:
    pass

install_schoeck_dorn_decoder(_base)
install_shear_movement(_base)
install_isokorb_compat(_base)
install_substitution_guard(_base)


def selftest() -> None:
    assert ROOT == install_root()
    assert PROGRAM == program_root()
    assert PROGRAM.name == "Program"
    assert _root_aware_choose_data_directory("Katalogy").parent in {ROOT, PROGRAM}
    assert APP_VERSION == "2.2.21"
    assert hit_workspace.HitWorkspaceMixin is not None
    assert _base.CatalogDatabase is CombinedCatalogDatabase
    assert _base.ThermalConnectorApp._build_body is _central_build_body


if __name__ == "__main__":
    raise SystemExit(_base.main())
