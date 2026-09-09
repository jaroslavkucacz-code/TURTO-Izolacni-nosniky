from __future__ import annotations

"""TURTO 2.2.9 – one compact in-program entry point to all active catalogues."""

from typing import Any
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk

from catalog_links_229 import CATALOG_RESOURCES, CatalogResource


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


def _open_online(owner: Any, resource: CatalogResource) -> None:
    try:
        opened = webbrowser.open_new_tab(resource.url)
        if opened is False:
            raise RuntimeError("Systémový prohlížeč nepotvrdil otevření odkazu.")
        try:
            owner.set_status(f"Otevřen katalog: {resource.label}")
        except Exception:
            pass
    except Exception as exc:
        messagebox.showerror(
            "Katalog nelze otevřít",
            f"{resource.label}\n\n{exc}\n\n{resource.url}",
            parent=owner,
        )


class CatalogDialog(tk.Toplevel):
    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.title("Katalogy a technické podklady")
        self.geometry("900x640")
        self.minsize(740, 520)
        self.transient(owner)
        self.grab_set()
        try:
            self.configure(background=owner.colors["bg"])
        except Exception:
            pass

        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Katalogy a technické podklady", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Katalogové rodiny, ze kterých program aktuálně čerpá, jsou dostupné z jednoho místa. Odkazy vedou na oficiální stránky výrobců s technickými podklady a aktuálními dokumenty.",
            style="Muted.TLabel",
            wraplength=840,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        canvas_frame = ttk.Frame(outer, style="App.TFrame")
        canvas_frame.pack(fill="both", expand=True)
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        canvas = tk.Canvas(canvas_frame, highlightthickness=0, background=getattr(owner, "colors", {}).get("bg", "#F3F6F9"))
        scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas, style="App.TFrame")
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        body.columnconfigure(0, weight=1)

        def _configure(_event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.itemconfigure(window_id, width=canvas.winfo_width())
            except Exception:
                pass

        body.bind("<Configure>", _configure)
        canvas.bind("<Configure>", _configure)

        last_domain = None
        row = 0
        for resource in CATALOG_RESOURCES:
            if resource.domain != last_domain:
                title = "Izolační nosníky" if resource.domain == "thermal_breaks" else "Smykové trny"
                ttk.Label(body, text=title, style="Section.TLabel").grid(
                    row=row, column=0, sticky="w", pady=(8 if row else 0, 6)
                )
                row += 1
                last_domain = resource.domain
            card = ttk.Frame(body, style="Card.TFrame", padding=(12, 9))
            card.grid(row=row, column=0, sticky="ew", pady=3)
            card.columnconfigure(0, weight=1)
            ttk.Label(card, text=f"{resource.manufacturer} • {resource.label}", style="Card.TLabel", font=("Calibri", 10, "bold")).grid(
                row=0, column=0, sticky="w"
            )
            ttk.Label(card, text=resource.source, style="MutedCard.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))
            ttk.Button(card, text="Nahlédnout", command=lambda item=resource: _open_online(owner, item)).grid(
                row=0, column=1, rowspan=2, sticky="e", padx=(12, 0)
            )
            row += 1

        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.pack(fill="x", pady=(12, 0))
        if callable(getattr(owner, "open_hit_source", None)):
            ttk.Button(bottom, text="Načtené DoP HIT", command=owner.open_hit_source).pack(side="left")
        ttk.Button(bottom, text="Zavřít", command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda _event: self.destroy())


def _find_report_bar(owner: Any):
    """Find the AKCE report bar after all older cleanup layers have run."""
    for widget in _walk(owner):
        try:
            if isinstance(widget, ttk.Button) and "Export PDF" in str(widget.cget("text")):
                return widget.master
        except Exception:
            pass
    return None


def _cleanup_source_controls(owner: Any) -> None:
    """Remove duplicated source controls now covered by the catalogue dialog."""
    for widget in _walk(owner):
        try:
            if isinstance(widget, ttk.Button):
                text = str(widget.cget("text"))
                if text == "Otevřít zdroj":
                    widget.grid_remove()
                elif text == "Otevřít zdrojové DoP":
                    widget.configure(text="Zdrojové DoP")
            elif isinstance(widget, ttk.Label):
                text = str(widget.cget("text"))
                if "Ancon" in text and "Schöck" in text and ("PohlCon" in text or "MAX FRANK" in text):
                    widget.grid_remove()
        except Exception:
            pass


def _patch_help() -> None:
    """Keep the 2.2.8 help card aligned with multi-selection and catalogue access."""
    try:
        import ui_help
    except Exception:
        return
    if getattr(ui_help, "_turto_help_229", False):
        return
    base = getattr(ui_help, "HelpDialog", None)
    if base is None:
        return

    class HelpDialog229(base):
        def __init__(self, owner: Any) -> None:
            super().__init__(owner)
            for widget in _walk(self):
                try:
                    if not isinstance(widget, ttk.Label):
                        continue
                    text = str(widget.cget("text"))
                    if text.startswith("PDF lze exportovat jako"):
                        widget.configure(
                            text=(
                                "PDF lze exportovat jako celou AKCI nebo jako kombinaci jedné či více "
                                "produktových oblastí a záložek. Výběr se provede těsně před uložením PDF. "
                                "Technické katalogy otevřete tlačítkem „Katalogy / podklady“ u výstupu AKCE."
                            )
                        )
                except Exception:
                    pass

    ui_help.HelpDialog = HelpDialog229
    ui_help._turto_help_229 = True


def apply_catalog_access(owner: Any) -> None:
    if getattr(owner, "_turto_catalog_access_229_applied", False):
        return
    _cleanup_source_controls(owner)
    _patch_help()
    bar = _find_report_bar(owner)
    if bar is not None:
        button = ttk.Button(bar, text="Katalogy / podklady", command=lambda: CatalogDialog(owner))
        try:
            button.grid(row=0, column=4, sticky="e", padx=(7, 0))
        except Exception:
            button.pack(side="right", padx=(7, 0))
        owner.catalog_access_button = button
    owner._turto_catalog_access_229_applied = True
