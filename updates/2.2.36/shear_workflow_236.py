from __future__ import annotations

"""Repair the installed Decoder workflow, not just standalone HSD lookup.

Own the two broken dispatch boundaries explicitly. Never call the rebound
2.1.5 wrappers through their mutable 2.1.4 globals (infinite recursion).
"""
import math
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from shear_dowels_schedule_215 import ShearScheduleDialog
from shear_schedule_io_236 import parse_rows, read_file


class DecoderFileDialog(ShearScheduleDialog):
    def __init__(self, owner, **kwargs):
        self.file_source = ""
        self.ocr_required = False
        self.loading = False
        self.inbox = queue.Queue()
        super().__init__(owner, **kwargs)
        self.title("Výkaz smykových trnů – soubor nebo text")
        self.use_geometry = tk.BooleanVar(self, False)
        self.ocr_confirmed = tk.BooleanVar(self, False)
        toolbar = ttk.Frame(self.text.master, style="Card.TFrame")
        toolbar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(7,0))
        self.file_button = ttk.Button(toolbar, text="Otevřít soubor…", command=self._choose_file)
        self.file_button.pack(side="left")
        ttk.Checkbutton(toolbar, text="Použít výchozí h, spáru a beton", variable=self.use_geometry, command=self._analyze).pack(side="left", padx=10)
        ttk.Checkbutton(toolbar, text="Zkontroloval jsem typy a počty z OCR", variable=self.ocr_confirmed, command=self._refresh).pack(side="left")
        self.notice = tk.StringVar(self, "PDF / Excel / CSV / text / obrázek. Bez potvrzené geometrie se načtou jen typy a počty.")
        ttk.Label(self.text.master, textvariable=self.notice, wraplength=1120, style="MutedCard.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6,0))
        self.summary_var.set("Otevřete soubor nebo vložte text výkazu. Nic se nepřevezme bez kontrolního náhledu.")

    def _choose_file(self):
        path = filedialog.askopenfilename(parent=self, title="Výkaz smykových trnů", filetypes=[
            ("Výkazy", "*.pdf *.xlsx *.xlsm *.csv *.txt *.tsv *.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
            ("PDF", "*.pdf"), ("Excel", "*.xlsx *.xlsm"), ("Obrázky", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Všechny soubory", "*.*")])
        if not path:
            return
        page = None
        try:
            if Path(path).suffix.lower() == ".pdf":
                import fitz
                with fitz.open(path) as doc:
                    count = len(doc)
                if count > 1:
                    page = simpledialog.askinteger("Stránka PDF", f"Číslo stránky s výkazem (1–{count}):", parent=self, minvalue=1, maxvalue=count)
                    if page is None:
                        return
        except Exception as exc:
            messagebox.showerror("Načtení výkazu", str(exc), parent=self)
            return
        self.loading = True
        self.file_button.configure(state="disabled")
        self.insert_button.configure(state="disabled")
        self.notice.set("Načítám soubor; obrázky se rozpoznávají lokálně…")
        def worker():
            try:
                self.inbox.put((True, read_file(path, page=page)))
            except Exception as exc:
                self.inbox.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self):
        if not self.winfo_exists():
            return
        try:
            ok, result = self.inbox.get_nowait()
        except queue.Empty:
            self.after(100, self._poll)
            return
        self.loading = False
        self.file_button.configure(state="normal")
        if ok:
            self.set_file_text(result)
        else:
            self.notice.set("Soubor se nepodařilo načíst; dosavadní vstup zůstal zachovaný.")
            messagebox.showerror("Načtení výkazu", result, parent=self)
            self._refresh()

    def set_file_text(self, result):
        self.file_source = result.source
        self.ocr_required = result.review_required
        self.ocr_confirmed.set(False)
        self.notice.set(result.notice or result.source)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", result.text)
        self._analyze()

    def _paste(self):
        self.file_source = "schránka"
        self.ocr_required = False
        super()._paste()

    def _analyze(self):
        if self.loading:
            return
        try:
            self.items = parse_rows(self.text.get("1.0", "end-1c"), decoder=self.decoder,
                defaults=self._defaults(), existing_names=set() if self.replace_existing.get() else self.existing_names,
                use_defaults=self.use_geometry.get())
        except Exception as exc:
            self.items = []
            messagebox.showerror("Kontrola výkazu", str(exc), parent=self)
        self._refresh()

    def _refresh(self):
        super()._refresh()
        ready = [i for i in self.items if not i.error]
        errors = len(self.items)-len(ready)
        self.summary_var.set(f"{len(self.items)} položek • {sum(i.quantity for i in ready)} ks • {errors} chyb k opravě")
        allowed = bool(ready) and not errors and not self.loading and (not self.ocr_required or self.ocr_confirmed.get())
        self.insert_button.configure(state="normal" if allowed else "disabled")

    def _accept(self):
        # Re-parse here as well: edits after the last preview must never import stale rows.
        if self.loading:
            return
        self._analyze()
        if not self.items or any(i.error for i in self.items):
            return
        if self.ocr_required and not self.ocr_confirmed.get():
            messagebox.showwarning("Kontrola OCR", "Nejprve zkontrolujte a potvrďte označení a počty z obrázku.", parent=self)
            return
        for item in self.items:
            item.values.update(import_source_file=self.file_source, import_method="ocr-reviewed" if self.ocr_required else "text-reviewed")
        super()._accept()


def _walk(root):
    yield root
    for child in root.winfo_children():
        yield from _walk(child)


def open_schedule(owner):
    import shear_dowels_ui as base
    import shear_dowels_ui_214 as ui
    values = owner.shear_decoder_vars
    defaults = {key: values[key].get() for key in ("slab", "gap", "concrete", "cover")}
    dialog = DecoderFileDialog(owner, mode="decoder", decoder=base.decode_dowel, defaults=defaults,
        existing_names={str(r.get("name", "")) for r in owner.shear_decoder_rows})
    owner._hsd_last_import_dialog = dialog
    owner.wait_window(dialog)
    if not dialog.result:
        return
    if dialog.replace_existing.get():
        owner.shear_decoder_rows = []
    owner.shear_decoder_rows.extend(dict(r) for r in dialog.result)
    ui._mark(owner)
    owner.refresh_shear_tables()
    values["name"].set(ui._next("S", owner.shear_decoder_rows))


def transfer(owner):
    """Populate the existing substitution form; no implicit geometry/capacity."""
    import shear_dowels_ui_214 as ui
    indices = ui._selected_indices(owner.shear_decoder_tree)
    if not indices:
        messagebox.showinfo("Záměna z Dekodéru", "Nejprve vyberte řádek v tabulce Dekodéru.", parent=owner)
        return
    row = owner.shear_decoder_rows[indices[0]]
    values = owner.shear_substitution_vars
    for key, source in (("name","name"),("qty","quantity"),("source","designation"),("slab","slab_mm"),("gap","gap_mm"),("concrete","concrete")):
        value = row.get(source, "")
        if key in {"slab", "gap"} and row.get("geometry_confirmed") is False:
            value = ""
        values[key].set(str(value))
    # Leave the target's cover and sleeve selection unchanged.
    owner.shear_notebook.select(2)
    owner.update_idletasks()


def edit_geometry(owner):
    import shear_dowels_ui_214 as ui
    indices = ui._selected_indices(owner.shear_decoder_tree)
    if not indices:
        messagebox.showinfo("Parametry řádků", "Vyberte jeden nebo více řádků Dekodéru.", parent=owner)
        return
    win = tk.Toplevel(owner)
    win.title("Parametry vybraných smykových trnů")
    win.transient(owner)
    win.grab_set()
    first = owner.shear_decoder_rows[indices[0]]
    box = ttk.Frame(win, padding=16); box.pack(fill="both", expand=True)
    variables = {}
    for n,(key,label) in enumerate((("slab_mm","Tloušťka h [mm]"),("gap_mm","Návrhová spára [mm]"),("concrete","Beton"))):
        variables[key] = tk.StringVar(win, str(first.get(key) or ""))
        ttk.Label(box,text=label).grid(row=n,column=0,sticky="w",pady=5)
        widget = ttk.Combobox(box,textvariable=variables[key],values=("C20/25","C25/30","C30/37","C35/45","C40/50"),state="readonly") if key=="concrete" else ttk.Entry(box,textvariable=variables[key])
        widget.grid(row=n,column=1,padx=10)
    def apply():
        try:
            data = {"slab_mm":float(variables["slab_mm"].get().replace(",",".")), "gap_mm":float(variables["gap_mm"].get().replace(",",".")), "concrete":variables["concrete"].get()}
            if not all(math.isfinite(data[k]) for k in ("slab_mm","gap_mm")) or data["slab_mm"]<=0 or data["gap_mm"]<0 or not data["concrete"]:
                raise ValueError("Vyplňte kladnou tloušťku, nezápornou spáru a beton.")
            for index in indices:
                owner.shear_decoder_rows[index].update(data, geometry_confirmed=True)
            ui._mark(owner); owner.refresh_shear_tables(); win.destroy()
        except ValueError as exc:
            messagebox.showerror("Parametry",str(exc),parent=win)
    ttk.Button(box,text="Použít na vybrané řádky",command=apply).grid(row=3,column=1,pady=10)
    win.bind("<Escape>",lambda e:win.destroy())


def install(app_base: Any):
    cls = app_base.ThermalConnectorApp
    if getattr(cls, "_turto_hsd_workflow_236", False):
        return
    import halfen_hsd_2026 as hsd
    import shear_autocomplete as ac
    import shear_dowels_ui_215 as ui215
    import shear_dowels_ui_214 as ui214
    import shear_dowels_current_221 as current
    original_decode, original_capacity = hsd.decode_designation, hsd.capacity_for
    def decode(text):
        raw = hsd._norm(text)
        if "HSD" not in raw and re.search(r"\bCRET\s*[- ]?\s*\d", raw):
            raw = re.sub(r"\bCRET(?=\s*[- ]?\s*\d)", "HSD-CRET", raw, count=1)
        return original_decode(raw)
    def capacity(info, slab_mm, gap_mm, concrete="C25/30"):
        try:
            h,g = float(slab_mm),float(gap_mm)
        except (ValueError,TypeError):
            return None,"Pro VRd doplňte tloušťku, návrhovou spáru a beton."
        if not math.isfinite(h) or not math.isfinite(g) or h<=0 or g<0:
            return None,"Pro VRd doplňte platnou tloušťku, návrhovou spáru a beton."
        table,note = hsd._concrete(concrete)
        if table is None:
            return None,note
        return original_capacity(info,h,g,concrete)
    hsd.decode_designation,hsd.capacity_for = decode,capacity
    original_catalog = ac._build_catalog
    def catalog():
        rows = list(original_catalog())
        for size in hsd.GEOM:
            for v in ("", " V"):
                rows.append(ac.ShearSuggestion(f"HSD-CRET {size}{v}", "Leviat / HALFEN • " + ("podélný + příčný" if v else "podélný"), (f"CRET {size}{v}",f"HALFEN CRET {size}{v}",f"Leviat HSD-CRET {size}{v}")))
        for size in (20,22,25,30):
            for kind in ("D","S","P","SV","SET"):
                rows.append(ac.ShearSuggestion(f"HSD-{kind} {size}","Leviat / HALFEN • HSD",()))
            rows.append(ac.ShearSuggestion(f"HSD-SET {size} V-A4","Leviat / HALFEN • komplet, podélný + příčný",()))
        return rows
    ac._build_catalog = catalog
    ac._CACHE = None
    original_enrich = ui215._enrich_decoder_row
    def enrich(row):
        original_enrich(row)
        if row.get("geometry_confirmed") is False:
            row.pop("hsd_capacity",None)
            row["archive_vrd"] = None
            row["archive_note"] = "Pouze typ a počet. Doplňte h, návrhovou spáru a beton."
    ui215._enrich_decoder_row = enrich
    def refresh(owner):
        # Preserve the newer alternatives/selection refresh, which includes HSD.
        current.refresh(owner)
        tree = getattr(owner,"shear_decoder_tree",None)
        if tree is None:
            return
        for index,row in enumerate(owner.shear_decoder_rows):
            if row.get("geometry_confirmed") is False and tree.exists(str(index)):
                enrich(row)
                for key in ("vrd","slab","gap","concrete"):
                    tree.set(str(index),key,"—")
                tree.set(str(index),"source",row["archive_note"])
    cls.refresh_shear_tables = refresh
    cls.open_shear_decoder_schedule = open_schedule
    cls.shear_decoder_to_substitution = transfer
    # Also repair callers that retain these module globals.
    ui215.open_decoder_schedule = ui214.open_decoder_schedule = open_schedule
    ui215.decoder_to_substitution = ui214.decoder_to_substitution = transfer
    original_body = cls._build_body
    def body(owner):
        original_body(owner)
        tab = owner.shear_notebook.nametowidget(owner.shear_notebook.tabs()[0])
        for widget in list(_walk(tab)):
            if isinstance(widget,ttk.Button) and widget.cget("text")=="Hromadné dekódování z výkazu…":
                widget.configure(text="Načíst výkaz ze souboru / textu…",command=owner.open_shear_decoder_schedule)
                frame = widget.master
                choices = [s.designation for s in ac.all_suggestions() if s.designation.startswith("HSD-")]
                choice = ttk.Combobox(frame,values=choices,state="readonly",width=24)
                choice.set("Leviat / HALFEN HSD…")
                choice.grid(row=0,column=3,sticky="e",padx=(10,0))
                choice.bind("<<ComboboxSelected>>",lambda e:owner.shear_decoder_vars["designation"].set(choice.get()))
                owner.hsd_catalog_choice = choice
                for child in frame.winfo_children():
                    if isinstance(child,ttk.Label) and str(child.cget("text")).startswith("Dekódované řádky"):
                        child.grid_remove()
                ttk.Button(frame,text="Doplnit h / spáru / beton…",command=lambda:edit_geometry(owner)).grid(row=1,column=0,columnspan=2,sticky="w",pady=(5,0))
                break
        # Keep a usable result table at laptop height; long help belongs in Help.
        for widget in list(_walk(tab)):
            if isinstance(widget,ttk.Label):
                text = str(widget.cget("text"))
                if text.startswith(("Stejně jako u izolačních", "Dvojklik na řádek provede", "Historické Schöck Dorn")):
                    widget.grid_remove() if widget.winfo_manager()=="grid" else widget.pack_forget()
        for child in tab.winfo_children():
            if isinstance(child,ttk.Frame) and str(child.grid_info().get("row")) in {"2","3"}:
                child.configure(padding=(8,4))
    cls._build_body = body
    cls._turto_hsd_workflow_236 = True
