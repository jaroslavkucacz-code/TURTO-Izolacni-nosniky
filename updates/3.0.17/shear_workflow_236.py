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
from shear_schedule_io_236 import FileText, parse_rows, read_file


class DecoderFileDialog(ShearScheduleDialog):
    """Small-screen file/text preview. No partial or unreviewed OCR import."""
    def __init__(self, owner, **kwargs):
        self.file_source = ""
        self.original_file_text = ""
        self.ocr_required = False
        self.loading = False
        self.inbox = queue.Queue()
        self._poll_id = None
        self._analysis_text = ""
        self._reviewed_text = None
        super().__init__(owner, **kwargs)
        self.title("Výkaz smykových trnů – soubor nebo text")
        self.minsize(860, 540)
        width = min(1160, self.winfo_screenwidth()-60)
        height = min(760, self.winfo_screenheight()-100)
        self.geometry(f"{width}x{height}")
        from ui_utils import place_dialog_on_parent
        place_dialog_on_parent(self, owner)
        self.text.bind("<<Modified>>", self._text_changed, add="+")
        self.text.edit_modified(False)
        self.replace_existing.trace_add("write", lambda *_: self._analyze())

    def _build(self, title):
        self.use_geometry = tk.BooleanVar(self, False)
        self.ocr_confirmed = tk.BooleanVar(self, False)
        self.notice = tk.StringVar(self, "PDF, Excel, CSV, text nebo obrázek. Vstup lze před vložením opravit.")
        outer = ttk.Frame(self, style="App.TFrame", padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)
        toolbar = ttk.Frame(outer, style="App.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.file_button = ttk.Button(toolbar, text="Otevřít soubor…", command=self._choose_file)
        self.file_button.pack(side="left")
        ttk.Button(toolbar, text="Vložit text ze schránky", command=self._paste).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Obnovit náhled", command=self._analyze).pack(side="left")
        self.source_button = ttk.Button(toolbar, text="Zobrazit zdroj", command=self._show_source, state="disabled")
        self.source_button.pack(side="right")
        ttk.Label(outer, textvariable=self.notice, wraplength=820, style="Muted.TLabel").grid(row=1, column=0, sticky="ew", pady=(0, 5))
        source = ttk.Frame(outer, style="Card.TFrame")
        source.grid(row=2, column=0, sticky="ew")
        source.columnconfigure(0, weight=1)
        self.text = tk.Text(source, height=5, wrap="none", undo=True, font=("Calibri", 11),
                            background=self.owner.colors["panel"], foreground=self.owner.colors["text"],
                            insertbackground=self.owner.colors["text"])
        self.text.grid(row=0, column=0, sticky="ew")
        sy = ttk.Scrollbar(source, command=self.text.yview); sy.grid(row=0, column=1, sticky="ns")
        sx = ttk.Scrollbar(source, orient="horizontal", command=self.text.xview); sx.grid(row=1, column=0, sticky="ew")
        self.text.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        options = ttk.Frame(outer, style="App.TFrame")
        options.grid(row=3, column=0, sticky="ew", pady=6)
        ttk.Checkbutton(options, text="Použít výchozí h / spáru / beton", variable=self.use_geometry, command=self._toggle_geometry).pack(side="left")
        ttk.Checkbutton(options, text="Nahradit stávající řádky", variable=self.replace_existing).pack(side="right")
        self.geometry_frame = ttk.Frame(outer, style="Card.TFrame")
        for n, (key, label) in enumerate((("slab", "h [mm]"), ("gap", "Návrhová spára [mm]"), ("concrete", "Beton"), ("cover", "cnom SLD [mm]"))):
            ttk.Label(self.geometry_frame, text=label).grid(row=0, column=2*n, padx=(8, 3), pady=5)
            if key == "concrete":
                field = ttk.Combobox(self.geometry_frame, textvariable=self.vars[key], values=("C20/25", "C25/30", "C30/37", "C35/45", "C40/50"), state="readonly", width=10)
            elif key == "cover":
                field = ttk.Combobox(self.geometry_frame,textvariable=self.vars[key],values=("20","30"),state="readonly",width=5)
            else:
                field = ttk.Entry(self.geometry_frame, textvariable=self.vars[key], width=9)
            field.grid(row=0, column=2*n+1, pady=5)
        preview = ttk.Frame(outer, style="Card.TFrame", padding=4)
        preview.grid(row=5, column=0, sticky="nsew", pady=(5, 0))
        preview.columnconfigure(0, weight=1); preview.rowconfigure(0, weight=1)
        columns = ("line", "status", "position", "qty", "source", "result", "issue")
        self.tree = ttk.Treeview(preview, columns=columns, show="headings", style="Data.Treeview", height=5)
        for key, label, width in zip(columns, ("Ř.", "Stav", "Pozice", "Ks", "Ze souboru", "Rozpoznáno", "Kontrola / chyba"), (38, 85, 65, 45, 215, 245, 260)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=35, stretch=key in {"source", "result", "issue"}, anchor="w" if key in {"source", "result", "issue"} else "center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        ty = ttk.Scrollbar(preview, command=self.tree.yview); ty.grid(row=0, column=1, sticky="ns")
        tx = ttk.Scrollbar(preview, orient="horizontal", command=self.tree.xview); tx.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=ty.set, xscrollcommand=tx.set)
        self.tree.tag_configure("ok", foreground=self.owner.colors["success"])
        self.tree.tag_configure("error", foreground=self.owner.colors["danger"])
        self.ocr_check = ttk.Checkbutton(outer, text="Zkontroloval jsem všechny typy a počty z OCR podle zdroje", variable=self.ocr_confirmed, command=self._confirm_ocr)
        self.ocr_check.grid(row=6, column=0, sticky="w", pady=(6, 0))
        self.ocr_check.grid_remove()
        bottom = ttk.Frame(outer, style="App.TFrame")
        bottom.grid(row=7, column=0, sticky="ew", pady=(8, 0)); bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.summary_var, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Zrušit", command=self._cancel).grid(row=0, column=1)
        self.insert_button = ttk.Button(bottom, text="Vložit připravené", style="Accent.TButton", command=self._accept, state="disabled")
        self.insert_button.grid(row=0, column=2, padx=(8, 0))
        self.bind("<Escape>", lambda e: self._cancel())

    def _toggle_geometry(self):
        if self.use_geometry.get():
            self.geometry_frame.grid(row=4, column=0, sticky="ew")
        else:
            self.geometry_frame.grid_remove()
        self._analyze()

    def _text_changed(self, *_):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self.text.get("1.0", "end-1c") != self._analysis_text:
            self.ocr_confirmed.set(False)
            self._reviewed_text = None
            self.insert_button.configure(state="disabled")
            self.summary_var.set("Vstup byl změněn – obnovte náhled.")

    def _confirm_ocr(self):
        checked = self.ocr_confirmed.get()
        self._analyze()
        self.ocr_confirmed.set(checked and bool(self.items) and not any(i.error for i in self.items))
        self._reviewed_text = self.text.get("1.0", "end-1c") if self.ocr_confirmed.get() else None
        self._refresh()

    def _show_source(self):
        path = self.file_source.rsplit(" | ", 1)[0]
        if not Path(path).is_file():
            return
        import os, subprocess, sys
        try:
            if os.name == "nt": os.startfile(path)
            else: subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
        except OSError as exc:
            messagebox.showerror("Zdroj výkazu", str(exc), parent=self)

    def _choose_file(self):
        path = filedialog.askopenfilename(parent=self, title="Výkaz smykových trnů", filetypes=[
            ("Výkazy", "*.pdf *.xlsx *.xlsm *.csv *.txt *.tsv *.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
            ("PDF", "*.pdf"), ("Excel", "*.xlsx *.xlsm"), ("Obrázky", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Všechny soubory", "*.*")])
        if not path: return
        page = None
        try:
            if Path(path).suffix.lower() == ".pdf":
                import pdfplumber
                with pdfplumber.open(path) as doc: count = len(doc.pages)
                if count > 1:
                    page = simpledialog.askinteger("Stránka PDF", f"Číslo stránky s výkazem (1–{count}):", parent=self, minvalue=1, maxvalue=count)
                    if page is None: return
        except Exception as exc:
            messagebox.showerror("Načtení výkazu", str(exc), parent=self); return
        self.loading = True
        self.file_button.configure(state="disabled"); self.insert_button.configure(state="disabled")
        self.text.configure(state="disabled")
        self.notice.set("Načítám soubor; obrázky se rozpoznávají lokálně…")
        def worker():
            try: self.inbox.put((True, read_file(path, page=page)))
            except Exception as exc: self.inbox.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        self._poll_id = self.after(100, self._poll)

    def _poll(self):
        self._poll_id = None
        try: ok, result = self.inbox.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(100, self._poll); return
        self.loading = False
        self.file_button.configure(state="normal"); self.text.configure(state="normal")
        if ok: self.set_file_text(result)
        else:
            self.notice.set("Soubor se nepodařilo načíst; dosavadní vstup zůstal zachovaný.")
            messagebox.showerror("Načtení výkazu", result, parent=self); self._refresh()

    def set_file_text(self, result):
        self.file_source = result.source
        self.original_file_text = result.text
        self.ocr_required = result.review_required
        self.ocr_confirmed.set(False); self._reviewed_text = None
        self.notice.set(result.notice or result.source)
        self.source_button.configure(state="normal" if Path(result.source.rsplit(" | ", 1)[0]).is_file() else "disabled")
        self.text.delete("1.0", "end"); self.text.insert("1.0", result.text)
        self._analyze()

    def _paste(self):
        if self.loading: return
        try: text = self.clipboard_get()
        except tk.TclError: return
        self.set_file_text(FileText(text, "schránka"))

    def _analyze(self):
        if self.loading: return
        raw = self.text.get("1.0", "end-1c")
        if raw != self._reviewed_text: self.ocr_confirmed.set(False)
        try:
            self.items = parse_rows(raw, decoder=self.decoder, defaults=self._defaults(),
                existing_names=set() if self.replace_existing.get() else self.existing_names,
                use_defaults=self.use_geometry.get())
        except Exception as exc:
            self.items = []; messagebox.showerror("Kontrola výkazu", str(exc), parent=self)
        self._analysis_text = raw
        self._refresh()

    def _refresh(self):
        super()._refresh()
        ready = [i for i in self.items if not i.error]
        errors = len(self.items)-len(ready)
        self.summary_var.set(f"{len(self.items)} položek • {sum(i.quantity for i in ready)} ks • {errors} chyb k opravě")
        if self.ocr_required: self.ocr_check.grid()
        else: self.ocr_check.grid_remove()
        raw = self.text.get("1.0", "end-1c")
        reviewed = not self.ocr_required or (self.ocr_confirmed.get() and raw == self._reviewed_text)
        allowed = bool(ready) and not errors and not self.loading and reviewed and raw == self._analysis_text
        self.insert_button.configure(state="normal" if allowed else "disabled")

    def _accept(self):
        if self.loading: return
        self._analyze()
        if not self.items or any(i.error for i in self.items): return
        if self.ocr_required and (not self.ocr_confirmed.get() or self._reviewed_text != self._analysis_text):
            messagebox.showwarning("Kontrola OCR", "Nejprve zkontrolujte a potvrďte označení a počty z obrázku.", parent=self); return
        if self.replace_existing.get() and self.existing_names and not messagebox.askyesno("Nahradit řádky", "Nahradit všechny dosavadní řádky Dekodéru načteným výkazem?", parent=self): return
        original_lines=self.original_file_text.splitlines()
        for item in self.items:
            item.values.update(import_source_file=self.file_source, import_method="ocr-reviewed" if self.ocr_required else "text-reviewed", import_original_line=(original_lines[item.line-1] if item.line <= len(original_lines) else ""))
        super()._accept()

    def _cancel(self):
        if self._poll_id is not None:
            self.after_cancel(self._poll_id); self._poll_id = None
        super()._cancel()


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
    # SLD cnom belongs to the shared physical geometry of this row.
    info = ui._base.decode_dowel(str(row.get('designation') or ''))
    if info and not info.get('legacy') and info.get('base_family') == 'SLD' and row.get('cover_mm') in (20,30):
        values['cover'].set(str(int(row['cover_mm'])))
    # Other families retain the target's cover and sleeve preferences.
    domain = getattr(owner, "product_domain_tab_by_id", {}).get("shear_dowels")
    if domain is not None: owner.product_domain_notebook.select(domain)
    for helper in getattr(owner, "_shear_autocompletes", []): helper.hide()
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
    for n,(key,label) in enumerate((("slab_mm","Tloušťka h [mm]"),("gap_mm","Návrhová spára [mm]"),("concrete","Beton"),("cover_mm","cnom Stacon SLD [mm]"))):
        variables[key] = tk.StringVar(win, str(first.get(key) or ""))
        ttk.Label(box,text=label).grid(row=n,column=0,sticky="w",pady=5)
        widget = ttk.Combobox(box,textvariable=variables[key],values=("C20/25","C25/30","C30/37","C35/45","C40/50"),state="readonly") if key=="concrete" else ttk.Entry(box,textvariable=variables[key])
        if key == "cover_mm":
            widget.destroy()
            widget = ttk.Combobox(box, textvariable=variables[key], values=("", "20", "30"), state="readonly")
        widget.grid(row=n,column=1,padx=10)
    def apply():
        try:
            data = {"slab_mm":float(variables["slab_mm"].get().replace(",",".")), "gap_mm":float(variables["gap_mm"].get().replace(",",".")), "concrete":variables["concrete"].get()}
            if not all(math.isfinite(data[k]) for k in ("slab_mm","gap_mm")) or data["slab_mm"]<=0 or data["gap_mm"]<0 or not data["concrete"]:
                raise ValueError("Vyplňte kladnou tloušťku, nezápornou spáru a beton.")
            cover = variables["cover_mm"].get()
            data["cover_mm"] = int(cover) if cover in ("20", "30") else None
            for index in indices:
                owner.shear_decoder_rows[index].update(data, geometry_confirmed=True)
            ui._mark(owner); owner.refresh_shear_tables(); win.destroy()
        except ValueError as exc:
            messagebox.showerror("Parametry",str(exc),parent=win)
    ttk.Button(box,text="Použít na vybrané řádky",command=apply).grid(row=4,column=1,pady=10)
    win.bind("<Escape>",lambda e:win.destroy())



def add_single(owner):
    import shear_dowels_ui as base
    import shear_dowels_ui_214 as ui
    values = owner.shear_decoder_vars
    line = '\t'.join(values[k].get() for k in ('name','designation','qty'))
    rows = parse_rows(line, decoder=base.decode_dowel,
        defaults={key:values[key].get() for key in ('slab','gap','concrete','cover')},
        existing_names={str(r.get('name','')) for r in owner.shear_decoder_rows},
        use_defaults=owner.hsd_manual_geometry.get())
    if len(rows)!=1 or rows[0].error:
        messagebox.showerror('Dekódování', rows[0].error if rows else 'Vyplňte označení a počet.', parent=owner); return
    item=rows[0]
    owner.shear_decoder_rows.append(dict(item.values,name=item.name,quantity=item.quantity))
    ui._mark(owner);owner.refresh_shear_tables()
    values['name'].set(ui._next('S',owner.shear_decoder_rows))


def _compact_decoder(owner, ac):
    """Keep the existing table and actions, replace only its overgrown controls."""
    tab = owner.shear_notebook.nametowidget(owner.shear_notebook.tabs()[0])
    original_buttons={str(w.cget('text')):w for w in _walk(tab) if isinstance(w,ttk.Button)}
    for child in tab.winfo_children():
        info=child.grid_info()
        if info and int(info.get('row',-1))<5:child.grid_remove()
    for row in range(5):tab.rowconfigure(row,weight=0,minsize=0,pad=0)
    # The two adjacent tab captions already identify this workspace.
    for child in owner.shear_notebook.master.winfo_children():
        if child is not owner.shear_notebook and child.grid_info().get('row')==0:child.grid_remove()
    controls=ttk.Frame(tab,style='App.TFrame')
    controls.grid(row=0,column=0,sticky='ew',pady=(0,6));controls.columnconfigure(0,weight=1)
    toolbar=ttk.Frame(controls,style='App.TFrame');toolbar.grid(row=0,column=0,sticky='ew',pady=(0,6));toolbar.columnconfigure(4,weight=1)
    ttk.Button(toolbar,text='Načíst výkaz ze souboru / textu…',style='Accent.TButton',command=owner.open_shear_decoder_schedule).grid(row=0,column=0)
    ttk.Button(toolbar,text='Kopírovat pro Excel',command=lambda:owner.copy_shear_table('decoder')).grid(row=0,column=1,padx=(6,0))
    if 'Export Excel…' in original_buttons:
        ttk.Button(toolbar,text='Export Excel…',command=original_buttons['Export Excel…'].invoke).grid(row=0,column=2,padx=(6,0))
    ttk.Label(toolbar,textvariable=owner.shear_decoder_status_var,style='Muted.TLabel').grid(row=0,column=4,sticky='e',padx=8)
    choices=list(dict.fromkeys(s.designation for s in ac.all_suggestions() if s.designation.startswith('HSD-')))
    choice=ttk.Combobox(toolbar,values=choices,state='readonly',width=25)
    choice.set('Leviat / HALFEN HSD…');choice.grid(row=0,column=5,sticky='e')
    owner.hsd_catalog_choice=choice
    values=owner.shear_decoder_vars
    quick=ttk.Frame(controls,style='Card.TFrame',padding=(6,4));quick.grid(row=1,column=0,sticky='ew');quick.columnconfigure(5,weight=1)
    for col,(key,label,width) in enumerate((('name','Pozice',7),('qty','Ks',5),('designation','Označení',28))):
        ttk.Label(quick,text=label,style='Card.TLabel').grid(row=0,column=2*col)
        entry=ttk.Entry(quick,textvariable=values[key],width=width)
        entry.grid(row=0,column=2*col+1,sticky='ew',padx=(4,8))
        if key=='designation':owner.hsd_designation_entry=entry
    ttk.Button(quick,text='Dekódovat a přidat',style='Accent.TButton',command=owner.add_shear_decoder_row).grid(row=0,column=6)
    owner.hsd_manual_geometry=tk.BooleanVar(owner,False)
    params=ttk.Frame(controls,style='Card.TFrame',padding=(6,2))
    def toggle():
        if owner.hsd_manual_geometry.get():params.grid(row=2,column=0,sticky='ew')
        else:params.grid_remove()
    ttk.Checkbutton(quick,text='h / spára / beton',variable=owner.hsd_manual_geometry,command=toggle).grid(row=0,column=7,padx=(6,0))
    for col,(key,label) in enumerate((('slab','h [mm]'),('gap','Návrhová spára [mm]'),('concrete','Beton'),('cover','cnom SLD [mm]'))):
        ttk.Label(params,text=label,style='Card.TLabel').grid(row=0,column=2*col,padx=(4,3))
        entry=ttk.Combobox(params,textvariable=values[key],values=('C20/25','C25/30','C30/37','C35/45','C40/50'),state='readonly',width=9) if key=='concrete' else ttk.Entry(params,textvariable=values[key],width=9)
        if key == 'cover':
            entry.destroy()
            entry=ttk.Combobox(params,textvariable=values[key],values=('20','30'),state='readonly',width=5)
        entry.grid(row=0,column=2*col+1,padx=(0,12))
    actions=ttk.Frame(controls,style='App.TFrame');actions.grid(row=3,column=0,sticky='ew',pady=(6,0));actions.columnconfigure(4,weight=1)
    ttk.Button(actions,text='Upravit pozici / ks',command=lambda:owner.shear_edit_meta('decoder')).grid(row=0,column=0)
    ttk.Button(actions,text='Doplnit h / spáru / beton…',command=lambda:edit_geometry(owner)).grid(row=0,column=1,padx=6)
    ttk.Button(actions,text='Převést do Záměn',command=owner.shear_decoder_to_substitution).grid(row=0,column=2)
    more=ttk.Menubutton(actions,text='Další…',width=7);more.grid(row=0,column=3,padx=6)
    menu=tk.Menu(more,tearoff=False,font=('Calibri',11));more.configure(menu=menu)
    for label in ('Detail prvku','Duplikovat','Nahoru','Dolů','Smazat','Sloupce…'):
        if label in original_buttons:menu.add_command(label=label,command=original_buttons[label].invoke)
    menu.add_separator();menu.add_command(label='Vymazat vše',command=lambda:owner.clear_shear_kind('decoder'))
    ttk.Label(actions,text='Filtr',style='Muted.TLabel').grid(row=0,column=5,padx=(6,4))
    query=ttk.Entry(actions,textvariable=owner.shear_decoder_filter_var,width=18);query.grid(row=0,column=6)
    query.bind('<KeyRelease>',lambda e:owner.refresh_shear_tables())
    ttk.Button(actions,text='×',width=2,command=lambda:(owner.shear_decoder_filter_var.set(''),owner.refresh_shear_tables())).grid(row=0,column=7,padx=(4,0))
    choice.bind('<<ComboboxSelected>>',lambda e:(values['designation'].set(choice.get()),owner.hsd_designation_entry.focus_set()))
    # Bind directly to the visible input, not the legacy hidden duplicate.
    helper=ac.ShearAutocomplete(entry=owner.hsd_designation_entry,variable=values['designation'],owner=owner,submit_callback=owner.add_shear_decoder_row)
    owner._shear_autocompletes.append(helper)
    import tkinter.font as tkfont
    rowheight=max(24,tkfont.Font(owner,font=("Calibri",11)).metrics("linespace")+6)
    ttk.Style(owner).configure("HSD.Data.Treeview",rowheight=rowheight)
    owner.shear_decoder_tree.configure(style="HSD.Data.Treeview")
    owner.shear_decoder_tree.column("designation",width=220,minwidth=190)
    original_min=owner.minsize()
    def minimum(_event=None):
        active=owner.product_domain_notebook.select()==str(owner.product_domain_tab_by_id.get('shear_dowels'))
        owner.minsize(*( (980,640) if active else original_min ))
    owner.product_domain_notebook.bind('<<NotebookTabChanged>>',minimum,add='+')
    owner.after_idle(minimum)

def install(app_base: Any):
    cls = app_base.ThermalConnectorApp
    if getattr(cls, "_turto_hsd_workflow_236", False):
        return
    import halfen_hsd_2026 as hsd
    import shear_autocomplete as ac
    import shear_dowels_ui_215 as ui215
    import shear_dowels_ui_214 as ui214
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
    original_suggest = ac.suggest_values
    def suggest(text, limit=10):
        q = ac._compact(text)
        exact = [r for r in ac.all_suggestions() if r.designation.startswith("HSD-") and any(ac._compact(v)==q for v in (r.designation, *r.aliases))]
        return exact or original_suggest(text, limit)
    ac.suggest_values = suggest
    original_ac_refresh = ac.ShearAutocomplete.refresh
    def ac_refresh(helper):
        if not helper.entry.winfo_exists(): return
        if not helper.entry.winfo_ismapped() or helper.entry.focus_get() not in (helper.entry, helper.tree):
            helper.hide(); return
        original_ac_refresh(helper)
    ac.ShearAutocomplete.refresh = ac_refresh
    original_enrich = ui215._enrich_decoder_row
    def enrich(row):
        original_enrich(row)
        if row.get("geometry_confirmed") is False:
            row.pop("hsd_capacity",None)
            row["archive_vrd"] = None
            row["archive_note"] = "Pouze typ a počet. Doplňte h, návrhovou spáru a beton."
    ui215._enrich_decoder_row = enrich
    original_refresh = cls.refresh_shear_tables
    def refresh(owner):
        selections={name:tuple(getattr(owner,name).selection()) for name in ("shear_decoder_tree","shear_design_tree","shear_substitution_tree") if hasattr(owner,name)}
        original_refresh(owner)
        tree = getattr(owner,"shear_decoder_tree",None)
        if tree is None:
            return
        for index,row in enumerate(owner.shear_decoder_rows):
            if str(row.get("canonical_designation", "")).startswith("HSD-") and tree.exists(str(index)):
                tree.set(str(index),"movement","Podélný + příčný" if row.get("movement")=="transverse" else "Podélný")
            if row.get("geometry_confirmed") is False and tree.exists(str(index)):
                enrich(row)
                for key in ("vrd","slab","gap","concrete"):
                    tree.set(str(index),key,"—")
                tree.set(str(index),"source",row["archive_note"])
        for name,selected in selections.items():
            target=getattr(owner,name)
            retained=[iid for iid in selected if target.exists(iid)]
            if retained:target.selection_set(retained)
        import shear_dowels_current_221 as current
        current._refresh_alternatives(owner)
    cls.refresh_shear_tables = refresh
    cls.add_shear_decoder_row = add_single
    cls.open_shear_decoder_schedule = open_schedule
    cls.shear_decoder_to_substitution = transfer
    # Also repair callers that retain these module globals.
    ui215.open_decoder_schedule = ui214.open_decoder_schedule = open_schedule
    ui215.decoder_to_substitution = ui214.decoder_to_substitution = transfer
    original_body = cls._build_body
    def body(owner):
        original_body(owner)
        _compact_decoder(owner, ac)
    cls._build_body = body
    cls._turto_hsd_workflow_236 = True
