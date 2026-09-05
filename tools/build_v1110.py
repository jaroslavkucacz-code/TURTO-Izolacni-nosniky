from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "updates" / "1.1.9"
TARGET = ROOT / "updates" / "1.1.10"
PDF_TEMPLATE = ROOT / "tools" / "substitution_pdf_v1110.py"
VERSION = "1.1.10"
RAW_BASE = "https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: očekáván právě jeden výskyt, nalezeno {count}")
    return text.replace(old, new, 1)


def patch_app() -> None:
    path = TARGET / "app.pyw"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, 'APP_VERSION = "1.1.9"', f'APP_VERSION = "{VERSION}"', "verze aplikace")
    path.write_text(text, encoding="utf-8")


def patch_project_ui() -> None:
    path = TARGET / "project_ui.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''        filter_entry = ttk.Entry(actionbar, textvariable=self.project_filter_var, width=27)\n        filter_entry.grid(row=0, column=9, sticky="e")\n''',
        '''        filter_entry = ttk.Entry(actionbar, textvariable=self.project_filter_var, width=27)\n        filter_entry.grid(row=0, column=9, sticky="e")\n        self.project_filter_entry = filter_entry\n''',
        "uložení filtru projektu",
    )

    marker = "    # ---------- inicializace a klávesové zkratky ----------\n"
    marker_index = text.find(marker)
    if marker_index < 0:
        raise RuntimeError("projektové zkratky: nenalezen koncový oddíl")

    shortcuts = r'''    # ---------- inicializace a klávesové zkratky ----------

    @staticmethod
    def _shortcut_tree_items(tree: ttk.Treeview, parent: str = "") -> list[str]:
        rows: list[str] = []
        for item in tree.get_children(parent):
            item_id = str(item)
            rows.append(item_id)
            rows.extend(ProjectWorkspaceMixin._shortcut_tree_items(tree, item_id))
        return rows

    def _shortcut_select_all(self, _event: tk.Event[Any] | None = None) -> str | None:
        """Ctrl+A vybere obsah právě aktivního pole nebo všechny řádky tabulky."""
        widget = self.focus_get()
        if widget is None:
            return None

        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "end-1c")
            widget.see("insert")
            return "break"

        if isinstance(widget, ttk.Treeview):
            rows = self._shortcut_tree_items(widget)
            if not rows:
                return "break"
            mode = str(widget.cget("selectmode"))
            if mode == "none":
                return "break"
            if mode == "browse":
                widget.selection_set(rows[0])
                widget.focus(rows[0])
                widget.see(rows[0])
            else:
                widget.selection_set(rows)
                widget.focus(rows[0])
                widget.see(rows[0])
            return "break"

        if isinstance(widget, tk.Listbox):
            widget.selection_set(0, "end")
            if widget.size():
                widget.activate(0)
                widget.see(0)
            return "break"

        if str(widget.winfo_class()) in {"Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox"}:
            try:
                widget.selection_range(0, "end")
                widget.icursor("end")
                return "break"
            except (tk.TclError, AttributeError):
                return None
        return None

    def _shortcut_copy_tree(self, _event: tk.Event[Any] | None = None) -> str | None:
        """Ctrl+C kopíruje označené řádky aktivní tabulky jako TSV pro Excel."""
        widget = self.focus_get()
        if not isinstance(widget, ttk.Treeview):
            return None
        selected = [str(item) for item in widget.selection()]
        if not selected:
            return "break"

        raw_columns = widget.cget("columns")
        if isinstance(raw_columns, str):
            all_columns = [str(value) for value in widget.tk.splitlist(raw_columns)]
        else:
            all_columns = [str(value) for value in raw_columns]

        raw_display = widget.cget("displaycolumns")
        if raw_display in ("#all", ("#all",), ["#all"]):
            columns = all_columns
        elif isinstance(raw_display, str):
            columns = [str(value) for value in widget.tk.splitlist(raw_display) if str(value) != "#0"]
        else:
            columns = [str(value) for value in raw_display if str(value) != "#0"]
        columns = columns or all_columns

        headers = [str(widget.heading(column, "text") or column) for column in columns]
        lines = ["\t".join(headers)]
        for item in selected:
            values = [
                str(widget.set(item, column)).replace("\t", " ").replace("\r", " ").replace("\n", " ")
                for column in columns
            ]
            lines.append("\t".join(values))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        if hasattr(self, "set_status"):
            self.set_status(f"Zkopírováno {len(selected)} označených řádků do schránky.")
        return "break"

    def _shortcut_focus_filter(self, _event: tk.Event[Any] | None = None) -> str:
        """Ctrl+F přejde na filtr projektové tabulky."""
        if hasattr(self, "main_notebook") and hasattr(self, "project_tab"):
            try:
                self.main_notebook.select(self.project_tab)
            except tk.TclError:
                pass
        entry = getattr(self, "project_filter_entry", None)
        if entry is not None:
            entry.focus_set()
            try:
                entry.selection_range(0, "end")
            except tk.TclError:
                pass
        return "break"

    def _show_keyboard_shortcuts(self, _event: tk.Event[Any] | None = None) -> str:
        widget = self.focus_get()
        parent = widget.winfo_toplevel() if widget is not None else self
        messagebox.showinfo(
            "Klávesové zkratky - TURTO ISO",
            "Výběr a tabulky\n"
            "Ctrl+A  - vybrat vše v aktivním poli nebo tabulce\n"
            "Ctrl+C  - kopírovat označené řádky aktivní tabulky\n"
            "Ctrl+F  - přejít na filtr projektové tabulky\n\n"
            "Projekt\n"
            "Ctrl+N  - nový projekt\n"
            "Ctrl+O  - otevřít projekt\n"
            "Ctrl+S  - uložit projekt\n"
            "Ctrl+Shift+S  - uložit projekt jako\n\n"
            "Dialogy\n"
            "Enter / Ctrl+Enter  - potvrdit nebo spustit hlavní akci\n"
            "Esc  - zavřít / zrušit\n"
            "Delete  - smazat označené projektové řádky\n"
            "F1  - zobrazit tento přehled",
            parent=parent,
        )
        return "break"

    def finalize_project_workspace(self) -> None:
        self.project_quick_position_var.set(self.project.next_position())
        self.refresh_project_tree()
        self._update_project_title()

        self.bind_all("<Control-s>", lambda _event: (self.save_project(), "break")[1])
        self.bind_all("<Control-Shift-s>", lambda _event: (self.save_project_as(), "break")[1])
        self.bind_all("<Control-Shift-S>", lambda _event: (self.save_project_as(), "break")[1])
        self.bind_all("<Control-o>", lambda _event: (self.open_project(), "break")[1])
        self.bind_all("<Control-n>", lambda _event: (self.new_project(), "break")[1])

        self.bind_all("<Control-a>", self._shortcut_select_all, add="+")
        self.bind_all("<Control-A>", self._shortcut_select_all, add="+")
        self.bind_all("<Control-c>", self._shortcut_copy_tree, add="+")
        self.bind_all("<Control-f>", self._shortcut_focus_filter, add="+")
        self.bind_all("<F1>", self._show_keyboard_shortcuts, add="+")
'''
    text = text[:marker_index] + shortcuts.rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def patch_substitution_workspace() -> None:
    path = TARGET / "substitution_workspace.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'SUBSTITUTION_MODULE_VERSION = "1.1.8"',
        f'SUBSTITUTION_MODULE_VERSION = "{VERSION}"',
        "verze modulu záměn",
    )
    path.write_text(text, encoding="utf-8")


def write_release_notes() -> None:
    text = """TURTO ISO v1.1.10
- Doplněn kontextový Ctrl+A: vybere vše v aktivním textovém poli, vstupu, seznamu nebo tabulce; v tabulkách s vícenásobným výběrem označí všechny zobrazené řádky.
- Ctrl+C umí kopírovat označené řádky aktivní tabulky jako tabulátorový výstup pro Excel.
- Ctrl+F přejde přímo na filtr projektové tabulky; F1 zobrazí přehled dostupných klávesových zkratek.
- Zachovány a sjednoceny Ctrl+N, Ctrl+O, Ctrl+S a Ctrl+Shift+S.
- Úvodní PDF souhrn byl graficky přepracován a neobsahuje tlakový přenos. Zobrazuje pouze pozici, počet kusů, původní a navržený typ, délku, I/h/cnom, průměr, rozhodující kontrolu a stav.
- První strana PDF obsahuje pět souhrnných ukazatelů: počet pozic, celkové množství, počet vyhovujících, počet k posouzení a maximální využití.
- Detailní výpočtové listy jsou nově po dvou prvcích na stránku, mají výraznější hierarchii, rozhodující kontrolu, graf využití se značkou 100 %, až šest směrových kontrol a samostatný blok technické shody.
- Tlakový přenos zůstává uveden v detailu, kde je důležitý pro technické ověření, ale nezatěžuje úvodní přehled.
"""
    (TARGET / "RELEASE_NOTES.txt").write_text(text, encoding="utf-8")


def compile_sources() -> None:
    for path in TARGET.rglob("*"):
        if path.suffix.lower() not in {".py", ".pyw"}:
            continue
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def run_regressions() -> None:
    project_ui = (TARGET / "project_ui.py").read_text(encoding="utf-8")
    assert 'self.bind_all("<Control-a>"' in project_ui
    assert 'self.bind_all("<Control-c>"' in project_ui
    assert 'self.bind_all("<Control-f>"' in project_ui
    assert 'self.bind_all("<F1>"' in project_ui
    assert "self.project_filter_entry = filter_entry" in project_ui

    pdf_source = (TARGET / "substitution_pdf.py").read_text(encoding="utf-8")
    summary = pdf_source.split("def _summary_pages", 1)[1].split("def _detail_card", 1)[0]
    assert '("governing", "Rozhoduje"' in summary
    assert '("geometry", "I / h / cnom"' in summary
    assert '("source_compression", "Tlakový přenos"' not in summary
    assert "cards_per_page = 2" in pdf_source
    assert "ROZHODUJÍCÍ KONTROLA" in pdf_source

    sys.path.insert(0, str(TARGET))
    spec = importlib.util.spec_from_file_location("turto_pdf_v1110", TARGET / "substitution_pdf.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Nelze načíst substitution_pdf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rows = [
        {
            "position": "P001",
            "quantity": 4,
            "source": "EGCOBOX VXL48-K-C30-h160-REI120-SW",
            "source_meta": {
                "source_length_mm": 300,
                "source_insulation_mm": 120,
                "source_cover_mm": 30,
                "source_height_mm": 160,
                "source_concrete": "C25/30",
                "source_compression_text": "s tlakovými ložisky",
            },
            "source_actions": {"v_pos": 48.6},
            "target": {
                "designation": "HIT-SP ZVX-0302-16-033-30-08",
                "series": "SP",
                "cover_mm": 30,
                "height_mm": 160,
                "length_mm": 333,
                "wire_diameter_mm": 8,
                "utilization": 0.848,
                "interaction_utilization": 0.0,
                "length_relation": "povolená výjimka 300→333 mm",
                "compression_text": "s tlakovými ložisky (2 CSB)",
                "v_capacity_element": 57.3,
                "checks": [
                    {
                        "label": "V+",
                        "requirement": 48.6,
                        "capacity": 57.3,
                        "unit": "kN/prvek",
                        "eta": 0.848,
                        "result": "VYHOVUJE",
                    }
                ],
            },
            "status": "VYHOVUJE",
            "estimated_type": "ZVX",
            "notes": [],
        },
        {
            "position": "P002",
            "quantity": 8,
            "source": "EGCOBOX MXL50-V2-C50-h200-REI120-SW",
            "source_meta": {
                "source_length_mm": 1000,
                "source_insulation_mm": 120,
                "source_cover_mm": 50,
                "source_height_mm": 200,
                "source_concrete": "C25/30",
                "source_compression_text": "s tlakovými ložisky",
            },
            "source_actions": {"m_neg": 41.1, "v_pos": 97.3},
            "target": {
                "designation": "HIT-SP MVX-0807-20-100-50",
                "series": "SP",
                "cover_mm": 50,
                "height_mm": 200,
                "length_mm": 1000,
                "utilization": 0.923,
                "interaction_utilization": 0.923,
                "length_relation": "shodná délka",
                "compression_text": "s tlakovými ložisky (CSB)",
                "m_capacity_element": 52.0,
                "v_capacity_element": 113.0,
                "checks": [
                    {"label": "M-", "requirement": 41.1, "capacity": 52.0, "unit": "kNm/prvek", "eta": 0.790, "result": "VYHOVUJE"},
                    {"label": "V+", "requirement": 97.3, "capacity": 113.0, "unit": "kN/prvek", "eta": 0.861, "result": "VYHOVUJE"},
                    {"label": "M-V", "requirement": 0.923, "capacity": 1.0, "unit": "-", "eta": 0.923, "result": "VYHOVUJE"},
                ],
            },
            "status": "VYHOVUJE",
            "estimated_type": "MVX-0807",
            "notes": ["Interakce M-V ověřena podle bilančních bodů."],
        },
        {
            "position": "P003",
            "quantity": 2,
            "source": "ISOPRO 120 O 40 h200",
            "source_meta": {
                "source_length_mm": 250,
                "source_insulation_mm": 120,
                "source_cover_mm": 30,
                "source_height_mm": 200,
                "source_concrete": "C25/30",
                "source_compression_text": "tlačené ocelové pruty",
            },
            "source_actions": {"n_pos": 40.0},
            "target": {},
            "status": "KONTROLA",
            "estimated_type": "OTX",
            "notes": ["Vzdálenost zatížení x není jednoznačně známá."],
        },
    ]

    diagnostic_pdf = ROOT / "_diag_v1110.pdf"
    module.write_substitution_pdf(
        diagnostic_pdf,
        project_name="BD TEST",
        rows=rows,
        creator="Vytvořil Ing. Jaroslav Kučera",
    )
    if diagnostic_pdf.stat().st_size < 50_000:
        raise RuntimeError("Diagnostické PDF je podezřele malé")

    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(diagnostic_pdf))
    if len(document) < 3:
        raise RuntimeError(f"Očekávány alespoň 3 strany, vytvořeno {len(document)}")
    for index in (0, 1):
        page = document[index]
        bitmap = page.render(scale=1.30)
        image = bitmap.to_pil().convert("RGB")
        if image.width < 1000 or image.height < 700:
            raise RuntimeError("Diagnostický render má neočekávané rozměry")
        pixels = image.resize((128, 90)).getdata()
        non_white = sum(1 for red, green, blue in pixels if min(red, green, blue) < 245)
        if non_white < 450:
            raise RuntimeError(f"Diagnostická strana {index + 1} je pravděpodobně prázdná")
        image.save(ROOT / f"_diag_v1110_page{index + 1}.png")
        try:
            bitmap.close()
            page.close()
        except Exception:
            pass
    try:
        document.close()
    except Exception:
        pass


def write_manifest() -> None:
    files = []
    for path in sorted(TARGET.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(TARGET).as_posix()
        files.append(
            {
                "path": relative,
                "url": f"{RAW_BASE}/updates/{VERSION}/{relative}",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "version": VERSION,
        "notes": "TURTO ISO: klávesové zkratky a profesionálně přepracovaný PDF výstup záměn.",
        "files": files,
    }
    (ROOT / "update_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    if not SOURCE.exists():
        raise RuntimeError(f"Chybí zdrojová verze: {SOURCE}")
    if not PDF_TEMPLATE.exists():
        raise RuntimeError(f"Chybí PDF šablona: {PDF_TEMPLATE}")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(PDF_TEMPLATE, TARGET / "substitution_pdf.py")

    patch_app()
    patch_project_ui()
    patch_substitution_workspace()
    write_release_notes()
    compile_sources()
    run_regressions()
    write_manifest()
    print(f"Built TURTO ISO v{VERSION}")


if __name__ == "__main__":
    main()
