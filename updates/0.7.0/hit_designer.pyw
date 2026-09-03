from __future__ import annotations

import math
import os
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from hit_mvx_engine import Candidate, HitDataError, nearest_heights, propose

APP_TITLE = "TURTO - Návrh izolačních nosníků HIT MVX"
BASE_VERSION = "0.7.0"
CREATOR = "Vytvořil Ing. Jaroslav Kučera"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def installed_version() -> str:
    p = app_root() / "version.txt"
    try:
        value = p.read_text(encoding="utf-8").strip()
        return value or BASE_VERSION
    except Exception:
        return BASE_VERSION


APP_VERSION = installed_version()


def data_file() -> Path:
    external = app_root() / "catalogs" / "leviat_hit_mvx_07_23.json.xz.b64"
    if external.exists():
        return external
    return app_root() / "leviat_hit_mvx_07_23.json.xz.b64"


def parse_number(text: str, label: str) -> float:
    t = str(text).strip().replace(" ", "").replace(",", ".")
    if not t:
        raise ValueError(f"Vyplňte {label}.")
    try:
        return float(t)
    except ValueError as exc:
        raise ValueError(f"{label} musí být číslo.") from exc


def fmt(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    if not math.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}".replace(".", ",")


class HitDesigner(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_TITLE} {APP_VERSION}")
        self.geometry("1460x860")
        self.minsize(1180, 720)
        self.configure(bg="#F3F6F9")
        self._icon_image = None
        self._set_icon()
        self._candidates: list[Candidate] = []
        self._tree_items: dict[str, Candidate] = {}
        self._build_style()
        self._build_ui()
        self.after(120, self.calculate)


    def _set_icon(self) -> None:
        for candidate in (app_root() / "assets" / "app_icon.png", app_root() / "app_icon.png"):
            if candidate.exists():
                try:
                    self._icon_image = tk.PhotoImage(file=str(candidate))
                    self.iconphoto(True, self._icon_image)
                    return
                except Exception:
                    pass

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#F3F6F9")
        style.configure("Card.TFrame", background="#FFFFFF")
        style.configure("TLabel", background="#F3F6F9", foreground="#172230", font=("Calibri", 10))
        style.configure("Card.TLabel", background="#FFFFFF", foreground="#172230", font=("Calibri", 10))
        style.configure("Title.TLabel", background="#17324D", foreground="#FFFFFF", font=("Calibri", 18, "bold"))
        style.configure("SubTitle.TLabel", background="#17324D", foreground="#DCE8F2", font=("Calibri", 10))
        style.configure("Section.TLabel", background="#FFFFFF", foreground="#17324D", font=("Calibri", 12, "bold"))
        style.configure("Big.TLabel", background="#FFFFFF", foreground="#0E6E8E", font=("Calibri", 19, "bold"))
        style.configure("Muted.TLabel", background="#FFFFFF", foreground="#647181", font=("Calibri", 9))
        style.configure("Warn.TLabel", background="#FFF7E6", foreground="#6B4D12", font=("Calibri", 10))
        style.configure("Accent.TButton", font=("Calibri", 10, "bold"), foreground="#FFFFFF", background="#0E6E8E", padding=(12, 7))
        style.map("Accent.TButton", background=[("active", "#0A5D79")])
        style.configure("TButton", font=("Calibri", 10), padding=(10, 6))
        style.configure("TCombobox", font=("Calibri", 10), padding=4)
        style.configure("TEntry", font=("Calibri", 10), padding=5)
        style.configure("Result.Treeview", font=("Calibri", 10), rowheight=28, background="#FFFFFF", fieldbackground="#FFFFFF")
        style.configure("Result.Treeview.Heading", font=("Calibri", 10, "bold"))

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg="#17324D", height=86)
        header.pack(fill="x")
        header.pack_propagate(False)
        ttk.Label(header, text="TURTO - Návrh izolačních nosníků HIT MVX", style="Title.TLabel").pack(anchor="w", padx=24, pady=(15, 0))
        ttk.Label(header, text="Leviat HIT-HP / HIT-SP MVX | data z CONF-DOP_HIT-HP/SP-07-23 | konzervativní lineární M-V interakce", style="SubTitle.TLabel").pack(anchor="w", padx=24, pady=(1, 0))

        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=0)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        left = ttk.Frame(outer, style="Card.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        right = ttk.Frame(outer, style="Card.TFrame", padding=18)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        ttk.Label(left, text="Zadání", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self.series_var = tk.StringVar(value="HP")
        self.concrete_var = tk.StringVar(value="C25/30")
        self.cover_var = tk.StringVar(value="35")
        self.height_var = tk.StringVar(value="200")
        self.m_var = tk.StringVar(value="-30")
        self.v_var = tk.StringVar(value="40")
        self.length_var = tk.StringVar(value="Automaticky - preferovat 1000 mm")
        self.show_all_var = tk.BooleanVar(value=False)

        fields = [
            ("Řada", ttk.Combobox(left, textvariable=self.series_var, values=("HP", "SP"), state="readonly", width=24)),
            ("Beton", ttk.Combobox(left, textvariable=self.concrete_var, values=("C20/25", "C25/30", "C30/37"), state="readonly", width=24)),
            ("Krytí cnom [mm]", ttk.Combobox(left, textvariable=self.cover_var, values=("30", "35", "50"), state="readonly", width=24)),
            ("Výška prvku h [mm]", ttk.Entry(left, textvariable=self.height_var, width=26)),
            ("MEd [kNm/m]", ttk.Entry(left, textvariable=self.m_var, width=26)),
            ("VEd [kN/m]", ttk.Entry(left, textvariable=self.v_var, width=26)),
            ("Délka prvku", ttk.Combobox(left, textvariable=self.length_var, values=("Automaticky - preferovat 1000 mm", "1000 mm", "500 mm", "250 mm"), state="readonly", width=28)),
        ]
        for i, (label, widget) in enumerate(fields, 1):
            ttk.Label(left, text=label, style="Card.TLabel").grid(row=i, column=0, sticky="w", pady=5, padx=(0, 12))
            widget.grid(row=i, column=1, sticky="ew", pady=5)

        note = (
            "Program počítá h - cnom a vyhledá pouze odpovídající řádek tabulky. "
            "Znaménko MEd a VEd se pro kontrolu únosnosti převádí na absolutní hodnotu."
        )
        ttk.Label(left, text=note, style="Muted.TLabel", wraplength=360, justify="left").grid(row=9, column=0, columnspan=2, sticky="ew", pady=(12, 8))
        ttk.Checkbutton(left, text="Zobrazit všechny vyhovující typy", variable=self.show_all_var, command=self._render_results).grid(row=10, column=0, columnspan=2, sticky="w", pady=(4, 10))
        ttk.Button(left, text="Navrhnout výrobek", style="Accent.TButton", command=self.calculate).grid(row=11, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        ttk.Button(left, text="Zkontrolovat aktualizace", command=self.check_updates).grid(row=12, column=0, columnspan=2, sticky="ew")

        warning = tk.Frame(left, bg="#FFF7E6", bd=0)
        warning.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        self.warning_label = tk.Label(warning, text="", bg="#FFF7E6", fg="#6B4D12", font=("Calibri", 9), justify="left", wraplength=360, padx=10, pady=9)
        self.warning_label.pack(fill="x")
        self.warning_label.configure(text="Podmínka oblasti DoP: |MEd| / |VEd| >= 0,15 m. Výsledky mimo tuto oblast program nenavrhuje.")

        # Right panel - recommended product
        ttk.Label(right, text="Doporučený výrobek", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        summary = ttk.Frame(right, style="Card.TFrame")
        summary.grid(row=1, column=0, sticky="ew", pady=(6, 14))
        summary.columnconfigure(0, weight=1)
        self.designation_label = ttk.Label(summary, text="-", style="Big.TLabel")
        self.designation_label.grid(row=0, column=0, sticky="w")
        self.summary_label = ttk.Label(summary, text="", style="Card.TLabel", justify="left")
        self.summary_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        actions = ttk.Frame(summary, style="Card.TFrame")
        actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        ttk.Button(actions, text="Kopírovat označení", command=self.copy_recommended).pack(fill="x", pady=(0, 6))
        ttk.Button(actions, text="Kopírovat výsledek", command=self.copy_result).pack(fill="x")

        ttk.Label(right, text="Vyhovující alternativy", style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 8))
        tree_frame = ttk.Frame(right, style="Card.TFrame")
        tree_frame.grid(row=3, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        columns = ("rank", "designation", "util", "m1", "v1", "m2", "v2", "v_at_m", "page")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style="Result.Treeview", selectmode="browse")
        headings = {
            "rank": "#", "designation": "Výrobek", "util": "Využití", "m1": "MRd,1", "v1": "VRd,1",
            "m2": "MRd,2", "v2": "VRd,2", "v_at_m": "VRd při MEd", "page": "Str."
        }
        widths = {"rank": 42, "designation": 300, "util": 82, "m1": 82, "v1": 78, "m2": 82, "v2": 78, "v_at_m": 105, "page": 55}
        for c in columns:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w" if c == "designation" else "center", stretch=c == "designation")
        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.tag_configure("recommended", background="#EAF6EF")
        self.tree.bind("<Double-1>", lambda _e: self.copy_selected())

        self.detail_label = ttk.Label(right, text="", style="Muted.TLabel", wraplength=980, justify="left")
        self.detail_label.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)

        footer = tk.Label(self, text=f"{CREATOR}  |  HIT modul {APP_VERSION}", bg="#E8EDF2", fg="#536171", font=("Calibri", 9), anchor="e", padx=16, pady=5)
        footer.pack(fill="x", side="bottom")

        for var in (self.series_var, self.concrete_var, self.cover_var, self.length_var):
            var.trace_add("write", lambda *_: self.after_idle(self.calculate))
        self.bind("<Return>", lambda _e: self.calculate())
        self.bind("<Escape>", lambda _e: self.focus_set())

    def _preferred_length(self) -> int | None:
        txt = self.length_var.get()
        if txt.startswith("1000"): return 1000
        if txt.startswith("500"): return 500
        if txt.startswith("250"): return 250
        return None

    def calculate(self) -> None:
        try:
            h = int(round(parse_number(self.height_var.get(), "výšku h")))
            cover = int(self.cover_var.get())
            m = parse_number(self.m_var.get(), "MEd")
            v = parse_number(self.v_var.get(), "VEd")
            if h <= cover:
                raise ValueError("Výška h musí být větší než krytí cnom.")
            if not data_file().exists():
                raise HitDataError(f"Chybí datový soubor: {data_file()}")
            self._candidates = propose(
                data_file(), series=self.series_var.get(), height_mm=h, cover_mm=cover,
                concrete=self.concrete_var.get(), m_ed_knm_m=m, v_ed_kn_m=v,
                preferred_length_mm=self._preferred_length(), include_failing=False,
            )
            self._last_input = (h, cover, m, v)
        except (ValueError, HitDataError) as exc:
            self._candidates = []
            self.designation_label.configure(text="Zadání není kompletní")
            self.summary_label.configure(text=str(exc))
            self.detail_label.configure(text="")
            self._clear_tree()
            return

        if abs(v) > 1e-9 and abs(m) / abs(v) < 0.15 - 1e-12:
            self.designation_label.configure(text="Mimo oblast platnosti grafu")
            self.summary_label.configure(text=f"|MEd| / |VEd| = {fmt(abs(m)/abs(v), 3)} m < 0,15 m. Program podle DoP výrobek nenavrhuje.")
            self.detail_label.configure(text="Změňte zadání nebo ověřte kombinaci jiným postupem výrobce.")
            self._clear_tree()
            return

        if not self._candidates:
            h_eff = h - cover
            nearest = nearest_heights(data_file(), self.series_var.get(), self.concrete_var.get(), cover, h)
            # Distinguish missing table height from structural no-solution.
            possible_eff = {x - cover for x in nearest}
            if h_eff not in possible_eff:
                near_txt = ", ".join(f"{x} mm" for x in nearest) if nearest else "-"
                self.designation_label.configure(text="Pro tuto výšku není tabulkový řádek")
                self.summary_label.configure(text=f"h - cnom = {h_eff} mm. Nejbližší dostupné výšky při cnom {cover} mm: {near_txt}.")
            else:
                self.designation_label.configure(text="Žádný typ MVX nevyhovuje")
                self.summary_label.configure(text=f"Pro h = {h} mm, cnom = {cover} mm, {self.concrete_var.get()}, MEd = {fmt(m)} kNm/m a VEd = {fmt(v)} kN/m nebyl nalezen vyhovující typ.")
            self.detail_label.configure(text="")
            self._clear_tree()
            return

        best = self._candidates[0]
        self.designation_label.configure(text=best.designation)
        u = best.check.utilization
        util_txt = "-" if u is None else f"{u*100:.1f} %".replace(".", ",")
        ratio_txt = "∞" if best.check.ratio_m is None else fmt(best.check.ratio_m, 3)
        alt_txt = " | alternativní délka: " + ", ".join(best.alternatives) if best.alternatives else ""
        self.summary_label.configure(text=(
            f"Využití interakční obálky: {util_txt}   |   h - cnom = {best.h_minus_cnom_mm} mm   |   "
            f"|M|/|V| = {ratio_txt} m\n"
            f"MRd,1 = {fmt(best.mrd1_knm_m)} kNm/m   VRd,1 = {fmt(best.vrd1_kn_m)} kN/m   "
            f"MRd,2 = {fmt(best.mrd2_knm_m)} kNm/m   VRd,2 = {fmt(best.vrd2_kn_m)} kN/m   "
            f"VRd(MEd) = {fmt(best.check.allowed_v_kn_m)} kN/m   |   DoP str. {best.source_page}{alt_txt}"
        ))
        self._render_results()

    def _clear_tree(self) -> None:
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        self._tree_items.clear()

    def _render_results(self) -> None:
        self._clear_tree()
        if not self._candidates:
            return
        rows = self._candidates if self.show_all_var.get() else self._candidates[:12]
        for i, c in enumerate(rows, 1):
            u = c.check.utilization
            util = "-" if u is None else f"{u*100:.1f} %".replace(".", ",")
            iid = f"c{i}"
            self._tree_items[iid] = c
            self.tree.insert("", "end", iid=iid, tags=("recommended",) if i == 1 else (), values=(
                i, c.designation, util, fmt(c.mrd1_knm_m), fmt(c.vrd1_kn_m), fmt(c.mrd2_knm_m), fmt(c.vrd2_kn_m), fmt(c.check.allowed_v_kn_m), c.source_page
            ))
        if rows:
            self.tree.selection_set("c1")
            self.tree.focus("c1")
            self._selection_changed()

    def _selection_changed(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        c = self._tree_items.get(sel[0])
        if not c:
            return
        text = f"{c.designation}: katalogový řádek h-cnom {c.h_minus_cnom_mm} mm, beton {c.concrete}, zdroj DoP str. {c.source_page}."
        if c.alternatives:
            text += " Staticky ekvivalentní délkové varianty: " + ", ".join(c.alternatives) + "."
        if c.check.source_rounding_note:
            text += " Upozornění: " + c.check.source_rounding_note
        self.detail_label.configure(text=text)

    def copy_recommended(self) -> None:
        if not self._candidates:
            return
        self.clipboard_clear(); self.clipboard_append(self._candidates[0].designation)

    def copy_selected(self) -> None:
        sel = self.tree.selection()
        if not sel or sel[0] not in self._tree_items:
            return
        self.clipboard_clear(); self.clipboard_append(self._tree_items[sel[0]].designation)

    def copy_result(self) -> None:
        if not self._candidates:
            return
        c = self._candidates[0]
        h, cover, m, v = self._last_input
        u = c.check.utilization
        lines = [
            f"TURTO - návrh HIT MVX {APP_VERSION}",
            f"Výrobek: {c.designation}",
            f"Beton: {c.concrete}",
            f"h = {h} mm; cnom = {cover} mm; h-cnom = {c.h_minus_cnom_mm} mm",
            f"MEd = {fmt(m)} kNm/m; VEd = {fmt(v)} kN/m",
            f"MRd,1 = {fmt(c.mrd1_knm_m)} kNm/m; VRd,1 = {fmt(c.vrd1_kn_m)} kN/m",
            f"MRd,2 = {fmt(c.mrd2_knm_m)} kNm/m; VRd,2 = {fmt(c.vrd2_kn_m)} kN/m",
            f"VRd(MEd) = {fmt(c.check.allowed_v_kn_m)} kN/m",
            f"Využití = {fmt((u or 0)*100)} %",
            f"Zdroj: CONF-DOP_HIT-HP/SP-07-23, str. {c.source_page}; interakční graf str. 3.",
        ]
        self.clipboard_clear(); self.clipboard_append("\n".join(lines))

    def check_updates(self) -> None:
        try:
            from updater import check_and_update
        except Exception as exc:
            messagebox.showerror("Aktualizace", f"Modul aktualizací není dostupný.\n\n{exc}", parent=self)
            return
        check_and_update(self, APP_VERSION, relaunch="Spustit_HIT_navrh.vbs")


def main() -> None:
    HitDesigner().mainloop()


if __name__ == "__main__":
    main()
