from __future__ import annotations

"""TURTO 2.2.8 – keep explanatory text in Help, not in the workspace."""

from typing import Any
from tkinter import ttk


def _walk(root: Any):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass


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


def _cleanup_main_workspace(owner: Any) -> None:
    for widget in _walk(owner):
        try:
            if isinstance(widget, ttk.Label):
                text = str(widget.cget("text") or "").strip()
                if (
                    text.startswith("PDF je nadřazené produktovým oblastem")
                    or text.startswith("Dekodér pracuje se všemi katalogy")
                    or ((text.startswith("Ancon:") or text.startswith("Ancon/Leviat:")) and "Schöck" in text)
                ):
                    _hide(widget)
                elif text == "Výstup celé AKCE":
                    widget.configure(text="PDF")
            elif isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Export PDF AKCE":
                widget.configure(text="Export PDF…")
        except Exception:
            pass

    shear = getattr(owner, "product_domain_tab_by_id", {}).get("shear_dowels")
    if shear is not None:
        # The heading card is now a single-line title card. Remove any empty
        # vertical reservation left by the former catalog-summary row.
        for child in shear.winfo_children():
            try:
                if isinstance(child, ttk.Frame):
                    child.grid_rowconfigure(1, minsize=0, weight=0)
            except Exception:
                pass


def _patch_help() -> None:
    import ui_help
    if getattr(ui_help, "_turto_cleanup_help_228_installed", False):
        return
    Original = ui_help.HelpDialog

    class HelpDialog228(Original):
        def __init__(self, owner: Any) -> None:
            super().__init__(owner)
            notebook = next((widget for widget in _walk(self) if isinstance(widget, ttk.Notebook)), None)
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
            info = ttk.Frame(data_tab, style="Card.TFrame", padding=(12, 10))
            try:
                info.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            except Exception:
                info.pack(fill="x", pady=(10, 0))
            ttk.Label(info, text="PDF a produktové oblasti", style="Card.TLabel", font=("Calibri", 10, "bold")).pack(anchor="w")
            ttk.Label(
                info,
                text=(
                    "PDF lze exportovat jako celou AKCI, jednu produktovou oblast nebo jednotlivou záložku "
                    "Dekodér / Návrh / Záměny. Smykové trny používají katalogy Ancon/Leviat, Schöck, "
                    "PohlCon a MAX FRANK; technické zdroje a omezení jsou uvedeny v detailu řádku a ve zdrojových katalozích."
                ),
                style="MutedCard.TLabel",
                wraplength=1050,
                justify="left",
            ).pack(anchor="w", pady=(4, 0))

    ui_help.HelpDialog = HelpDialog228
    ui_help._turto_cleanup_help_228_installed = True


def apply(owner: Any) -> None:
    _patch_help()
    _cleanup_main_workspace(owner)


def selftest() -> None:
    assert callable(_cleanup_main_workspace)
    assert callable(_patch_help)


if __name__ == "__main__":
    selftest()
