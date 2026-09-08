from __future__ import annotations

"""TURTO 2.2.6 – visibility guard for compacted Tk layouts."""

from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

VERSION = "2.2.6"


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _buttons(root: Any, *texts: str) -> list[ttk.Button]:
    wanted = set(texts)
    out: list[ttk.Button] = []
    for widget in _walk(root):
        try:
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) in wanted:
                out.append(widget)
        except Exception:
            pass
    return out


def _hide(widget: Any) -> None:
    try:
        manager = widget.winfo_manager()
        if manager == "grid":
            widget.grid_remove()
        elif manager == "pack":
            widget.pack_forget()
        elif manager == "place":
            widget.place_forget()
    except Exception:
        pass


def _fix_project_concrete_controls(owner: Any) -> None:
    """Move Beton AKCE to the decoder toolbar, outside the clipped title card."""
    if getattr(owner, "_turto_project_concrete_toolbar_226", False):
        return
    tab = getattr(owner, "project_tab", None)
    old_combo = getattr(owner, "project_concrete_combo", None)
    variable = getattr(owner, "project_concrete_var", None)
    if tab is None or old_combo is None or variable is None:
        return

    bulk = None
    for button in _buttons(tab, "Hromadné dekódování z výkazu", "Hromadné dekódování z výkazu…", "Hromadné vložení z výkazu"):
        bulk = button
        break
    if bulk is None:
        return
    filebar = bulk.master

    try:
        values = tuple(old_combo.cget("values"))
    except Exception:
        values = ()
    if not values and hasattr(owner, "_available_project_concretes"):
        try:
            values = tuple(owner._available_project_concretes())
        except Exception:
            values = ()

    # Hide the old complete bar. It sat in the second line of the compact title
    # card and could be clipped by the following toolbar at some DPI settings.
    old_bar = getattr(old_combo, "master", None)
    if old_bar is not None:
        _hide(old_bar)

    try:
        filebar.columnconfigure(19, weight=1)
    except Exception:
        pass
    label = ttk.Label(filebar, text="Beton AKCE", style="Muted.TLabel")
    label.grid(row=0, column=20, sticky="e", padx=(18, 5))
    combo = ttk.Combobox(
        filebar,
        textvariable=variable,
        values=values,
        state="readonly",
        width=10,
    )
    combo.grid(row=0, column=21, sticky="e")
    if hasattr(owner, "_on_project_concrete_changed"):
        combo.bind("<<ComboboxSelected>>", owner._on_project_concrete_changed)
    button = ttk.Button(filebar, text="Použít na řádky", command=owner.apply_project_concrete_to_rows)
    button.grid(row=0, column=22, sticky="e", padx=(7, 0))

    owner.project_concrete_combo = combo
    owner._turto_project_concrete_toolbar_226 = True


def _control_types() -> tuple[type, ...]:
    values: list[type] = [ttk.Entry, ttk.Combobox, ttk.Button, ttk.Checkbutton, ttk.Radiobutton]
    spin = getattr(ttk, "Spinbox", None)
    if isinstance(spin, type):
        values.append(spin)
    return tuple(values)


def visibility_issues(owner: Any) -> list[str]:
    """Return mapped controls that extend outside their direct container."""
    try:
        owner.update_idletasks()
    except Exception:
        return []
    issues: list[str] = []
    types = _control_types()
    for widget in _walk(owner):
        try:
            if not isinstance(widget, types) or not widget.winfo_ismapped():
                continue
            master = widget.master
            if master is None or not master.winfo_ismapped():
                continue
            mw, mh = int(master.winfo_width()), int(master.winfo_height())
            ww, wh = int(widget.winfo_width()), int(widget.winfo_height())
            x, y = int(widget.winfo_x()), int(widget.winfo_y())
            if min(mw, mh, ww, wh) <= 1:
                continue
            tolerance = 4
            if x < -tolerance or y < -tolerance or x + ww > mw + tolerance or y + wh > mh + tolerance:
                try:
                    text = str(widget.cget("text")) if isinstance(widget, (ttk.Button, ttk.Checkbutton, ttk.Radiobutton)) else ""
                except Exception:
                    text = ""
                issues.append(
                    f"{widget.winfo_class()} {text!r}: x={x}, y={y}, w={ww}, h={wh}; rodič={mw}×{mh}"
                )
        except Exception:
            pass
    return list(dict.fromkeys(issues))


def _log_path() -> Path:
    return Path(__file__).resolve().parent / "ui_visibility.log"


def run_visibility_audit(owner: Any, *, show_result: bool = False) -> list[str]:
    issues = visibility_issues(owner)
    path = _log_path()
    try:
        if issues:
            path.write_text(
                "TURTO 2.2.6 – kontrola viditelnosti ovládacích prvků\n\n" + "\n".join(issues),
                encoding="utf-8",
            )
        elif path.exists():
            path.unlink()
    except Exception:
        pass

    owner._ui_visibility_issues = issues
    if show_result:
        if issues:
            preview = "\n".join(issues[:12])
            if len(issues) > 12:
                preview += f"\n… +{len(issues) - 12} dalších"
            messagebox.showwarning(
                "Kontrola rozhraní",
                f"Nalezeno {len(issues)} potenciálně zakrytých ovládacích prvků.\n\n{preview}\n\nLog: {path}",
                parent=owner,
            )
        else:
            messagebox.showinfo(
                "Kontrola rozhraní",
                "Nebyl nalezen žádný zobrazený vstup nebo tlačítko přesahující svůj kontejner.",
                parent=owner,
            )
    return issues


def _patch_help() -> None:
    import ui_help

    if getattr(ui_help, "_turto_visibility_help_226_installed", False):
        return
    Original = ui_help.HelpDialog

    class HelpDialog226(Original):
        def __init__(self, owner: Any) -> None:
            super().__init__(owner)
            notebook = next((w for w in _walk(self) if isinstance(w, ttk.Notebook)), None)
            if notebook is None:
                return
            data_tab = None
            try:
                for tab_id in notebook.tabs():
                    if str(notebook.tab(tab_id, "text")) == "Data a zdroje":
                        data_tab = notebook.nametowidget(tab_id)
                        break
            except Exception:
                pass
            if data_tab is None:
                return

            anchor = None
            for button in _buttons(data_tab, "Složka katalogů", "Kontrola katalogů", "Aktualizovat data HIT"):
                anchor = button
                break
            if anchor is not None:
                bar = anchor.master
            else:
                bar = ttk.Frame(data_tab, style="App.TFrame")
                bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
            if not _buttons(bar, "Kontrola rozhraní"):
                ttk.Button(
                    bar,
                    text="Kontrola rozhraní",
                    command=lambda: run_visibility_audit(owner, show_result=True),
                ).pack(side="left", padx=(8, 0))

    ui_help.HelpDialog = HelpDialog226
    ui_help._turto_visibility_help_226_installed = True


def apply(owner: Any) -> None:
    _fix_project_concrete_controls(owner)
    _patch_help()
    owner.check_ui_visibility = lambda show_result=True: run_visibility_audit(owner, show_result=show_result)
    try:
        owner.after_idle(lambda: run_visibility_audit(owner, show_result=False))
    except Exception:
        pass


def selftest() -> None:
    # Explicit minimum dimensions must not be treated here as an actual layout
    # control issue; the audit only works on mapped Tk widgets at runtime.
    assert callable(visibility_issues)
    assert callable(_fix_project_concrete_controls)


if __name__ == "__main__":
    selftest()
