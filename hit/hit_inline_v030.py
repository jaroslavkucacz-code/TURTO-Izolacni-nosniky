from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hit_design_legacy import (
    Candidate,
    HitDatabase,
    build_database_from_pdf,
    root_dir,
    version_tuple,
    fmt,
    CONCRETES,
    COVERS,
    DATA_FILENAME,
    REPO_RAW,
    CREATOR,
)

APP_NAME = "TURTO – Návrh nosníků HIT"
APP_VERSION = "0.3.0"
MANIFEST_URL = REPO_RAW + "/hit/update_manifest.json"


class InputRow:
    def __init__(self, app: "App", row_no: int, defaults: dict | None = None):
        self.app = app
        self.row_no = row_no
        defaults = defaults or {}
        self.name = tk.StringVar(value=defaults.get("name", f"N{row_no}"))
        self.series = tk.StringVar(value=defaults.get("series", "HP"))
        self.height = tk.StringVar(value=defaults.get("height", "200"))
        self.cover = tk.StringVar(value=defaults.get("cover", "35"))
        self.concrete = tk.StringVar(value=defaults.get("concrete", "C25/30"))
        self.med = tk.StringVar(value=defaults.get("med", ""))
        self.ved = tk.StringVar(value=defaults.get("ved", ""))
        self.product = tk.StringVar(value="—")
        self.util = tk.StringVar(value="—")
        self.page = tk.StringVar(value="—")
        self.detail = tk.StringVar(value="čeká na MEd / VEd")
        self.candidates: list[Candidate] = []
        self._after_id = None
        self._manual_product = False
        self.widgets = []
        self._build()

    def _build(self):
        parent = self.app.rows_frame
        r = self.row_no

        def entry(var, width):
            w = ttk.Entry(parent, textvariable=var, width=width)
            w.grid(row=r, column=len(self.widgets), sticky="ew", padx=2, pady=2)
            self.widgets.append(w)
            w.bind("<KeyRelease>", self._input_changed)
            w.bind("<FocusOut>", self._input_changed_now)
            w.bind("<Return>", self._input_changed_now)
            return w

        def combo(var, values, width):
            w = ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=width)
            w.grid(row=r, column=len(self.widgets), sticky="ew", padx=2, pady=2)
            self.widgets.append(w)
            w.bind("<<ComboboxSelected>>", self._input_changed_now)
            return w

        entry(self.name, 9)
        combo(self.series, ("HP", "SP"), 6)
        entry(self.height, 8)
        combo(self.cover, tuple(map(str, COVERS)), 7)
        combo(self.concrete, CONCRETES, 9)
        entry(self.med, 10)
        entry(self.ved, 10)

        self.product_combo = ttk.Combobox(
            parent, textvariable=self.product, values=(), state="readonly", width=39
        )
        self.product_combo.grid(row=r, column=len(self.widgets), sticky="ew", padx=2, pady=2)
        self.widgets.append(self.product_combo)
        self.product_combo.bind("<<ComboboxSelected>>", self._product_changed)

        self.util_label = ttk.Label(parent, textvariable=self.util, width=10, anchor="center")
        self.util_label.grid(row=r, column=len(self.widgets), sticky="ew", padx=2, pady=2)
        self.widgets.append(self.util_label)
        self.page_label = ttk.Label(parent, textvariable=self.page, width=7, anchor="center")
        self.page_label.grid(row=r, column=len(self.widgets), sticky="ew", padx=2, pady=2)
        self.widgets.append(self.page_label)
        self.detail_label = ttk.Label(parent, textvariable=self.detail, width=24, anchor="w")
        self.detail_label.grid(row=r, column=len(self.widgets), sticky="ew", padx=2, pady=2)
        self.widgets.append(self.detail_label)
        self.remove_button = ttk.Button(parent, text="×", width=3, command=lambda: self.app.remove_row(self))
        self.remove_button.grid(row=r, column=len(self.widgets), sticky="ew", padx=(4, 2), pady=2)
        self.widgets.append(self.remove_button)

    def _input_changed(self, _event=None):
        self._manual_product = False
        self.detail.set("počítám…")
        if self._after_id:
            try:
                self.app.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.app.after(350, self.recalculate)

    def _input_changed_now(self, _event=None):
        self._manual_product = False
        if self._after_id:
            try:
                self.app.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.recalculate()

    def _read_values(self):
        if not self.med.get().strip() or not self.ved.get().strip():
            return None
        h = int(float(self.height.get().replace(",", ".")))
        c = int(self.cover.get())
        med = float(self.med.get().replace(",", "."))
        ved = float(self.ved.get().replace(",", "."))
        return h, c, med, ved

    def recalculate(self, preserve_product: str | None = None):
        self._after_id = None
        try:
            values = self._read_values()
        except ValueError:
            self._set_error("neplatný číselný vstup")
            return
        if values is None:
            self.candidates = []
            self.product_combo.configure(values=())
            self.product.set("—")
            self.util.set("—")
            self.page.set("—")
            self.detail.set("čeká na MEd / VEd")
            self.app.update_status()
            return

        h, c, med, ved = values
        lengths = self.app.allowed_lengths()
        if not lengths:
            self._set_error("není povolena žádná délka")
            return

        candidates, err = self.app.db.candidates(
            self.series.get(), h, c, self.concrete.get(), med, ved, lengths, self.app.offsets.get()
        )
        self.candidates = candidates
        if err:
            self._set_error(err)
            return
        if not candidates:
            self._set_error(f"bez vyhovující varianty (h−cnom {h-c} mm)")
            return

        names = [c.designation for c in candidates]
        self.product_combo.configure(values=names)
        chosen = candidates[0]
        if preserve_product and preserve_product in names:
            chosen = candidates[names.index(preserve_product)]
        self.product.set(chosen.designation)
        self._manual_product = chosen is not candidates[0]
        self._show_candidate(chosen)
        self.app.update_status()

    def _product_changed(self, _event=None):
        value = self.product.get()
        for i, cand in enumerate(self.candidates):
            if cand.designation == value:
                self._manual_product = i != 0
                self._show_candidate(cand)
                self.app.update_status()
                break

    def _show_candidate(self, cand: Candidate):
        self.util.set(fmt(cand.utilization * 100) + " %")
        self.page.set(str(cand.page))
        text = f"{len(self.candidates)} variant"
        text += " • ručně zvoleno" if self._manual_product else " • nejbližší shoda"
        self.detail.set(text)

    def _set_error(self, text: str):
        self.candidates = []
        self.product_combo.configure(values=())
        self.product.set("NELZE NAVRHNOUT")
        self.util.set("—")
        self.page.set("—")
        self.detail.set(text)
        self.app.update_status()

    def destroy(self):
        if self._after_id:
            try:
                self.app.after_cancel(self._after_id)
            except Exception:
                pass
        for w in self.widgets:
            try:
                w.destroy()
            except Exception:
                pass

    def data(self):
        return {
            "name": self.name.get(), "series": self.series.get(), "height": self.height.get(),
            "cover": self.cover.get(), "concrete": self.concrete.get(), "med": self.med.get(),
            "ved": self.ved.get(), "selected": self.product.get(),
        }

    def defaults_for_next(self):
        return {
            "series": self.series.get(), "height": self.height.get(), "cover": self.cover.get(),
            "concrete": self.concrete.get(), "med": "", "ved": "",
        }


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1540x840")
        self.minsize(1120, 650)
        self.option_add("*Font", ("Calibri", 10))
        self.data_path = root_dir() / DATA_FILENAME

        if not self.data_path.exists():
            self.withdraw()
            pdf = filedialog.askopenfilename(
                title="Vyberte CONF-DOP HIT-HP/SP-07-23", filetypes=[("PDF", "*.pdf")]
            )
            if not pdf:
                messagebox.showerror("TURTO HIT", "Pro první spuštění je nutné vybrat zdrojové DoP.")
                self.destroy()
                return
            try:
                build_database_from_pdf(Path(pdf), self.data_path)
            except Exception as exc:
                messagebox.showerror("TURTO HIT", f"Databázi se nepodařilo vytvořit:\n{exc}")
                self.destroy()
                return
            self.deiconify()

        self.db = HitDatabase(self.data_path)
        self.rows: list[InputRow] = []
        self.l100 = tk.BooleanVar(value=True)
        self.l050 = tk.BooleanVar(value=True)
        self.l025 = tk.BooleanVar(value=False)
        self.offsets = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Zadávej nosníky přímo do řádků.")
        self._build()
        self.add_row()

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Calibri", 18, "bold"))
        style.configure("Sub.TLabel", font=("Calibri", 10))
        style.configure("Good.TLabel", font=("Calibri", 10, "bold"))

        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        hdr = ttk.Frame(outer)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="TURTO | Návrh nosníků Leviat HIT", style="Title.TLabel").pack(side="left")
        ttk.Button(hdr, text="Aktualizace", command=self.check_updates).pack(side="right")
        ttk.Button(hdr, text="Obnovit data z DoP", command=self.rebuild_data).pack(side="right", padx=(0, 8))
        ttk.Label(
            outer, text="Přímé řádkové zadávání HIT-HP/SP MVX • " + CREATOR, style="Sub.TLabel"
        ).pack(anchor="w", pady=(2, 12))

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="+ PŘIDAT ŘÁDEK", command=self.add_row).pack(side="left")
        ttk.Button(toolbar, text="PŘEPOČÍTAT VŠE", command=self.recalculate_all).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="VYMAZAT VŠE", command=self.clear_all).pack(side="left", padx=(8, 0))
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=14, pady=2)
        ttk.Label(toolbar, text="Povolené délky:").pack(side="left")
        for text, var in (("1000 mm", self.l100), ("500 mm", self.l050), ("250 mm", self.l025)):
            ttk.Checkbutton(toolbar, text=text, variable=var, command=self.recalculate_all).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(
            toolbar, text="zahrnout OD/OU/WD/WU", variable=self.offsets, command=self.recalculate_all
        ).pack(side="left", padx=(16, 0))
        ttk.Label(toolbar, textvariable=self.status, style="Good.TLabel").pack(side="right")

        table_box = ttk.Frame(outer)
        table_box.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(table_box, highlightthickness=0)
        ybar = ttk.Scrollbar(table_box, orient="vertical", command=self.canvas.yview)
        xbar = ttk.Scrollbar(table_box, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        table_box.columnconfigure(0, weight=1)
        table_box.rowconfigure(0, weight=1)
        self.rows_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>", self._on_rows_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        headers = [
            "Označení", "Řada", "h [mm]", "cnom", "Beton", "MEd [kNm/m]", "VEd [kN/m]",
            "Navržený výrobek ▼", "Využití", "DoP", "Stav / varianty", "",
        ]
        for col, text in enumerate(headers):
            ttk.Label(
                self.rows_frame, text=text, font=("Calibri", 10, "bold"),
                anchor="w" if col in (0, 7, 10) else "center",
            ).grid(row=0, column=col, sticky="ew", padx=2, pady=(0, 5))
        for col in range(len(headers)):
            self.rows_frame.columnconfigure(col, weight=1 if col in (0, 7, 10) else 0)

        ttk.Label(
            outer,
            text=(
                "Každý řádek je samostatný návrh. Po zadání nebo změně vstupů se výrobek přepočítá automaticky. "
                "Ve sloupci Navržený výrobek je jako první nejbližší vyhovující shoda; rozbalením stejné buňky "
                "můžeš okamžitě zvolit jinou vyhovující variantu. Výpočet používá lineární M–V interakční obálku "
                "z DoP a podmínku |MEd|/|VEd| ≥ 0,15 m."
            ), wraplength=1450, justify="left",
        ).pack(fill="x", pady=(9, 0))

    def _on_rows_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=max(event.width, self.rows_frame.winfo_reqwidth()))

    def _on_mousewheel(self, event):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def allowed_lengths(self):
        return {code for code, var in ((100, self.l100), (50, self.l050), (25, self.l025)) if var.get()}

    def add_row(self):
        defaults = self.rows[-1].defaults_for_next() if self.rows else {}
        row = InputRow(self, len(self.rows) + 1, defaults)
        self.rows.append(row)
        self.update_status()
        self.after(10, self._on_rows_configure)
        try:
            row.widgets[5].focus_set()
        except Exception:
            pass

    def remove_row(self, row: InputRow):
        if row not in self.rows:
            return
        row.destroy()
        self.rows.remove(row)
        self._rebuild_rows()
        self.update_status()

    def _rebuild_rows(self):
        saved = [r.data() for r in self.rows]
        for r in self.rows:
            r.destroy()
        self.rows = []
        for i, data in enumerate(saved, 1):
            row = InputRow(self, i, data)
            self.rows.append(row)
            preserve = data["selected"] if data["selected"] not in ("—", "NELZE NAVRHNOUT") else None
            row.recalculate(preserve_product=preserve)

    def clear_all(self):
        if self.rows and not messagebox.askyesno("TURTO HIT", "Vymazat všechny řádky a začít znovu?"):
            return
        for row in self.rows:
            row.destroy()
        self.rows = []
        self.add_row()

    def recalculate_all(self):
        for row in self.rows:
            current = row.product.get()
            preserve = current if current not in ("—", "NELZE NAVRHNOUT") else None
            row.recalculate(preserve_product=preserve)
        self.update_status()

    def update_status(self):
        total = len(self.rows)
        completed = sum(1 for r in self.rows if r.candidates)
        waiting = sum(1 for r in self.rows if not r.med.get().strip() or not r.ved.get().strip())
        bad = max(0, total - completed - waiting)
        text = f"Řádků: {total} • navrženo: {completed}"
        if waiting:
            text += f" • čeká: {waiting}"
        if bad:
            text += f" • nevyhovuje/chyba: {bad}"
        self.status.set(text)

    def rebuild_data(self):
        pdf = filedialog.askopenfilename(
            title="Vyberte CONF-DOP HIT-HP/SP-07-23", filetypes=[("PDF", "*.pdf")]
        )
        if not pdf:
            return
        try:
            build_database_from_pdf(Path(pdf), self.data_path)
            self.db = HitDatabase(self.data_path)
            self.recalculate_all()
            messagebox.showinfo("TURTO HIT", "Databáze byla úspěšně obnovena.")
        except Exception as exc:
            messagebox.showerror("TURTO HIT", f"Databázi se nepodařilo vytvořit:\n{exc}")

    def check_updates(self):
        try:
            req = urllib.request.Request(MANIFEST_URL, headers={"User-Agent": "TURTO-HIT-Updater"})
            with urllib.request.urlopen(req, timeout=20) as f:
                manifest = json.loads(f.read().decode("utf-8"))
            latest = str(manifest.get("version", "0"))
            if version_tuple(latest) <= version_tuple(APP_VERSION):
                messagebox.showinfo("Aktualizace", f"Používáte aktuální HIT verzi {APP_VERSION}.")
                return
            if not messagebox.askyesno(
                "Aktualizace", f"Je dostupná HIT verze {latest}.\n\n{manifest.get('notes', '')}\n\nNainstalovat?"
            ):
                return

            temp = Path(tempfile.mkdtemp(prefix="turto_hit_"))
            files = manifest.get("files", [])
            for item in files:
                req = urllib.request.Request(item["url"], headers={"User-Agent": "TURTO-HIT-Updater"})
                with urllib.request.urlopen(req, timeout=30) as f:
                    content = f.read()
                if hashlib.sha256(content).hexdigest().lower() != item["sha256"].lower():
                    raise RuntimeError("Nesouhlasí SHA-256: " + item["path"])
                p = temp / item["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(content)

            script = temp / "apply.py"
            paths = [x["path"] for x in files]
            script.write_text(
                "import os,shutil,sys,time\nfrom pathlib import Path\ntime.sleep(1.2)\n"
                "s=Path(__file__).parent; d=Path(sys.argv[1])\n" + f"paths={paths!r}\n" +
                "[((d/p).parent.mkdir(parents=True,exist_ok=True),shutil.copy2(s/p,d/p)) for p in paths]\n"
                "try: os.startfile(str(d/'hit_design.pyw'))\nexcept Exception: pass\n",
                encoding="utf-8",
            )
            subprocess.Popen(
                [sys.executable, str(script), str(root_dir())],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.after(200, self.destroy)
        except Exception as exc:
            messagebox.showerror("Aktualizace", f"Aktualizaci se nepodařilo provést:\n{exc}")
