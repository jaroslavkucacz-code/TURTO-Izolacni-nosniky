from __future__ import annotations

"""TURTO 2.1.3 multi-domain workspace and workflow polish."""

from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

import platform_workspace_200 as _prev
import action_report as _action_report
import shear_dowels_ui as _shear_ui
from shear_dowels_ui import build_shear_workspace, init_shear_workspace, install_methods


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _fix_decoder_layout(owner: Any) -> None:
    decoder = getattr(owner, "project_tab", None)
    if decoder is None:
        return
    try:
        decoder.grid_rowconfigure(0, minsize=80, weight=0)
        decoder.grid_rowconfigure(1, minsize=52, weight=0)
        decoder.grid_rowconfigure(2, minsize=128, weight=0)
        decoder.grid_rowconfigure(3, weight=1)
    except Exception:
        pass

    for child in decoder.winfo_children():
        try:
            row = int(child.grid_info().get("row", -1))
            if row == 0:
                child.grid_configure(pady=(10, 8))
            elif row in {1, 2}:
                child.grid_configure(pady=(0, 10))
        except Exception:
            pass


def _update_branding(owner: Any) -> None:
    for widget in _walk(owner):
        try:
            if not isinstance(widget, ttk.Label):
                continue
            text = str(widget.cget("text"))
            if text in {
                "TURTO 2.0 | Technické prvky",
                "TURTO 2.1.2 | Technické prvky",
            }:
                widget.configure(text="TURTO 2.1.3 | Technické prvky")
            elif text.startswith("PDF je nadřazené produktovým oblastem."):
                widget.configure(
                    text="PDF je nadřazené produktovým oblastem a zahrnuje "
                         "izolační nosníky i návrhy smykových trnů."
                )
        except Exception:
            pass


def _hide_inactive_domains(owner: Any) -> None:
    notebook = getattr(owner, "product_domain_notebook", None)
    frames = getattr(owner, "product_domain_tab_by_id", {})
    if notebook is None or not isinstance(frames, dict):
        return
    for spec in domains():
        if getattr(spec, "enabled", False):
            continue
        frame = frames.get(spec.id)
        if frame is None:
            continue
        try:
            notebook.forget(frame)
        except Exception:
            pass


def _decoder_to_substitution(self: Any) -> None:
    """Transfer the selected Decoder row and the explicitly selected target."""
    tree = getattr(self, "shear_decoder_tree", None)
    selected = tree.selection() if tree is not None else ()
    if not selected:
        messagebox.showinfo(
            "Záměna z Dekodéru",
            "Nejprve vyberte řádek v tabulce Dekodéru.",
            parent=self,
        )
        return

    try:
        row = self.shear_decoder_rows[int(selected[0])]
        values = self.shear_substitution_vars

        target_var = getattr(self, "shear_decoder_target_var", None)
        target = str(target_var.get() if target_var is not None else "Schöck").strip()
        if target not in {"Ancon", "Schöck"}:
            target = "Schöck"

        values["name"].set(str(row.get("name", "") or "Z001"))
        values["qty"].set(str(row.get("quantity", 1)))
        values["source"].set(str(row.get("designation", "")))
        values["slab"].set(str(row.get("slab_mm", "")))
        values["gap"].set(str(row.get("gap_mm", "")))
        values["concrete"].set(str(row.get("concrete", "C25/30")))
        values["cover"].set(str(row.get("cover_mm", 30)))
        values["target"].set(target)

        self.shear_notebook.select(2)
        try:
            self.update_idletasks()
        except Exception:
            pass
    except Exception as exc:
        messagebox.showerror("Záměna z Dekodéru", str(exc), parent=self)


def _enhance_shear_workspace(owner: Any) -> None:
    notebook = getattr(owner, "shear_notebook", None)
    if notebook is None:
        return

    try:
        tabs = notebook.tabs()
        decoder = notebook.nametowidget(tabs[0]) if tabs else None
    except Exception:
        decoder = None

    if decoder is not None and not hasattr(owner, "shear_decoder_target_var"):
        top = None
        for child in decoder.winfo_children():
            try:
                if int(child.grid_info().get("row", -1)) == 0:
                    top = child
                    break
            except Exception:
                continue

        if top is not None:
            owner.shear_decoder_target_var = tk.StringVar(master=owner, value="Schöck")
            transfer = ttk.Frame(top, style="Card.TFrame")
            transfer.grid(row=3, column=0, sticky="ew", pady=(9, 0))

            ttk.Label(
                transfer,
                text="Záměna vybraného řádku:",
                style="Card.TLabel",
                font=("Calibri", 10, "bold"),
            ).pack(side="left")
            ttk.Label(
                transfer,
                text="zaměnit za",
                style="MutedCard.TLabel",
            ).pack(side="left", padx=(12, 5))
            ttk.Combobox(
                transfer,
                textvariable=owner.shear_decoder_target_var,
                values=("Ancon", "Schöck"),
                state="readonly",
                width=12,
            ).pack(side="left")
            ttk.Button(
                transfer,
                text="Převést do Záměn",
                style="Accent.TButton",
                command=owner.shear_decoder_to_substitution,
            ).pack(side="left", padx=(8, 0))
            ttk.Label(
                transfer,
                text="Vyberte řádek v tabulce; dvojklik používá stejnou zvolenou značku.",
                style="MutedCard.TLabel",
            ).pack(side="left", padx=(12, 0))

    for widget in _walk(notebook):
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("text")) == "Cíl":
                widget.configure(text="Cílový výrobce")
            elif isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Překlopit":
                widget.configure(text="Navrhnout záměnu")
        except Exception:
            pass


def install(app_base: Any) -> None:
    cls = app_base.ThermalConnectorApp
    if getattr(cls, "_turto_platform_workspace_213_installed", False):
        return

    _prev.install(app_base)

    _shear_ui.decoder_to_substitution = _decoder_to_substitution

    cls = app_base.ThermalConnectorApp
    install_methods(cls)
    _prev.export_action_pdf = _action_report.export_action_pdf
    original_body = cls._build_body

    def body(self) -> None:
        original_body(self)
        init_shear_workspace(self)
        _fix_decoder_layout(self)
        _update_branding(self)

        frame = getattr(self, "product_domain_tab_by_id", {}).get("shear_dowels")
        if frame is not None:
            for child in list(frame.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            build_shear_workspace(self, frame)
            _enhance_shear_workspace(self)

        _hide_inactive_domains(self)
        try:
            self.base_window_title = "TURTO 2.1.3 – Technické prvky"
            self._update_project_title()
        except Exception:
            pass

    cls._build_body = body
    cls._turto_platform_workspace_213_installed = True


domain = _prev.domain
domains = _prev.domains
manufacturer = _prev.manufacturer
manufacturer_id_from_label = _prev.manufacturer_id_from_label
manufacturer_labels = _prev.manufacturer_labels
