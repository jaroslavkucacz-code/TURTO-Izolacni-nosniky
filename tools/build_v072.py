from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "0.7.1"
OUT = ROOT / "updates" / "0.7.2"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_app(text: str) -> str:
    return replace_once(text, 'APP_VERSION = "0.7.1"', 'APP_VERSION = "0.7.2"', "app version")


def patch_hit_workspace(text: str) -> str:
    marker = 'HIT_MODULE_VERSION = "0.3.0"\n\n\nclass HitInputRow:\n'
    dialog = r'''HIT_MODULE_VERSION = "0.3.0"


class HitVariantsDialog(tk.Toplevel):
    """Přehled všech vyhovujících variant pro jeden řádek návrhu HIT."""

    def __init__(self, parent: "HitWorkspaceMixin", row: "HitInputRow") -> None:
        super().__init__(parent)
        self.row = row
        self.result: Candidate | None = None
        self._candidate_by_iid: dict[str, Candidate] = {}
        self.title(f"Vyhovující varianty HIT – {row.name.get().strip() or 'řádek'}")
        self.geometry("1280x620")
        self.minsize(940, 460)
        self.transient(parent)
        self.grab_set()
        self.configure(background=parent.colors["bg"])
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(outer, text="Vyhovující varianty Leviat HIT", style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=(
                f"{row.series.get()} • h {row.height.get()} mm • cnom {row.cover.get()} mm • {row.concrete.get()} • "
                f"MEd {row.med.get()} kNm/m • VEd {row.ved.get()} kN/m"
            ),
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 2))
        ttk.Label(
            outer,
            text="První řádek je automaticky doporučená varianta. Dvojklikem nebo tlačítkem Použít variantu vyberete jiný vyhovující prvek.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(0, 10))

        frame = ttk.Frame(outer, style="Card.TFrame", padding=1)
        frame.grid(row=3, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = ("rank", "designation", "length", "variant", "util", "mode", "m1", "v1", "m2", "v2", "page")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", style="Data.Treeview")
        headings = {
            "rank": ("Poř.", 58, "center"),
            "designation": ("Varianta HIT", 340, "w"),
            "length": ("Délka", 82, "center"),
            "variant": ("Provedení", 84, "center"),
            "util": ("Využití", 82, "center"),
            "mode": ("Rozhoduje", 105, "center"),
            "m1": ("M1", 82, "center"),
            "v1": ("V1", 82, "center"),
            "m2": ("M2", 82, "center"),
            "v2": ("V2", 82, "center"),
            "page": ("DoP", 62, "center"),
        }
        for column, (label, width, anchor) in headings.items():
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=50, anchor=anchor, stretch=column == "designation")
        ybar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")

        selected_iid = None
        selected = row.selected_candidate
        for index, candidate in enumerate(row.candidates, start=1):
            iid = f"v{index - 1}"
            self._candidate_by_iid[iid] = candidate
            suffix = candidate.suffix or "standard"
            rank = "1 • doporučeno" if index == 1 else str(index)
            self.tree.insert(
                "", "end", iid=iid,
                values=(
                    rank, candidate.designation, f"{candidate.physical_length_mm} mm", suffix,
                    fmt(candidate.utilization * 100.0) + " %", candidate.mode,
                    fmt(candidate.m1), fmt(candidate.v1), fmt(candidate.m2), fmt(candidate.v2), str(candidate.page),
                ),
            )
            if candidate == selected:
                selected_iid = iid
        children = self.tree.get_children("")
        if selected_iid is None and children:
            selected_iid = children[0]
        if selected_iid:
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
            self.tree.see(selected_iid)

        self.tree.bind("<Double-1>", self._use_selected)
        self.tree.bind("<Return>", self._use_selected)
        actions = ttk.Frame(outer, style="App.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Zavřít", command=self.destroy).grid(row=0, column=1)
        ttk.Button(actions, text="Použít variantu", style="Accent.TButton", command=self._use_selected).grid(row=0, column=2, padx=(8, 0))
        self.bind("<Escape>", lambda _e: self.destroy())

    def _use_selected(self, _event: Any = None) -> str | None:
        selected = self.tree.selection()
        if not selected:
            return "break"
        candidate = self._candidate_by_iid.get(selected[0])
        if candidate is None:
            return "break"
        self.result = candidate
        self.destroy()
        return "break"


class HitInputRow:
'''
    text = replace_once(text, marker, dialog, "variants dialog")

    old_product = '''        self.product_combo = ttk.Combobox(parent, textvariable=self.product, values=(), state="readonly", width=41)\n        self.widgets.append(self.product_combo)\n        self.product_combo.bind("<<ComboboxSelected>>", self._product_changed)\n        self.util_label = ttk.Label(parent, textvariable=self.util, width=10, anchor="center", style="Card.TLabel")\n'''
    new_product = '''        self.product_combo = ttk.Combobox(parent, textvariable=self.product, values=(), state="readonly", width=41)\n        self.widgets.append(self.product_combo)\n        self.product_combo.bind("<<ComboboxSelected>>", self._product_changed)\n        self.variants_button = ttk.Button(parent, text="Varianty…", width=10, command=self.open_variants, state="disabled")\n        self.widgets.append(self.variants_button)\n        self.util_label = ttk.Label(parent, textvariable=self.util, width=10, anchor="center", style="Card.TLabel")\n'''
    text = replace_once(text, old_product, new_product, "variants button")

    text = replace_once(
        text,
        '            self.product_combo.configure(values=())\n            self.product.set("—")\n',
        '            self.product_combo.configure(values=())\n            self.variants_button.configure(state="disabled")\n            self.product.set("—")\n',
        "disable variants waiting",
    )
    text = replace_once(
        text,
        '        self.product_combo.configure(values=names)\n        chosen = candidates[0]\n',
        '        self.product_combo.configure(values=names)\n        self.variants_button.configure(state="normal" if len(candidates) > 1 else "disabled")\n        chosen = candidates[0]\n',
        "enable variants",
    )
    text = replace_once(
        text,
        '        self.product_combo.configure(values=())\n        self.product.set("NELZE NAVRHNOUT")\n',
        '        self.product_combo.configure(values=())\n        self.variants_button.configure(state="disabled")\n        self.product.set("NELZE NAVRHNOUT")\n',
        "disable variants error",
    )

    marker_method = '    def _product_changed(self, _event: Any = None) -> None:\n'
    method = r'''    def open_variants(self) -> None:
        if len(self.candidates) <= 1:
            return
        dialog = HitVariantsDialog(self.owner, self)
        self.owner.wait_window(dialog)
        candidate = dialog.result
        if candidate is None:
            return
        try:
            index = self.candidates.index(candidate)
        except ValueError:
            return
        self.product.set(candidate.designation)
        self._manual_product = index != 0
        self._show_candidate(candidate)
        self.owner.update_hit_status()

'''
    text = replace_once(text, marker_method, method + marker_method, "open variants method")

    old_headers = '        headers = ("Označení", "Řada", "h [mm]", "cnom", "Beton", "MEd [kNm/m]", "VEd [kN/m]", "Navržený výrobek ▼", "Využití", "DoP", "Stav / interakce", "")\n'
    new_headers = '        headers = ("Označení", "Řada", "h [mm]", "cnom", "Beton", "MEd [kNm/m]", "VEd [kN/m]", "Navržený výrobek ▼", "Varianty", "Využití", "DoP", "Stav / interakce", "")\n'
    text = replace_once(text, old_headers, new_headers, "headers")
    text = replace_once(text, 'anchor="w" if column in (0, 7, 10) else "center"', 'anchor="w" if column in (0, 7, 11) else "center"', "header anchors")
    text = replace_once(text, 'weight=1 if column in (0, 7, 10) else 0', 'weight=1 if column in (0, 7, 11) else 0', "header weights")
    return text


def main() -> None:
    if not BASE.exists():
        raise SystemExit(f"Missing base update: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)

    (OUT / "app.pyw").write_text(patch_app((OUT / "app.pyw").read_text(encoding="utf-8")), encoding="utf-8")
    (OUT / "hit_workspace.py").write_text(patch_hit_workspace((OUT / "hit_workspace.py").read_text(encoding="utf-8")), encoding="utf-8")

    notes = (
        "TURTO v0.7.2\n"
        "- Návrh HIT: vedle navrženého výrobku je nové tlačítko Varianty….\n"
        "- Otevře přehled všech vyhovujících HIT s délkou, provedením, využitím, rozhodující kontrolou, M1/V1, M2/V2 a stranou DoP.\n"
        "- První varianta je označena jako doporučená; dvojklikem lze vybrat jinou a vrátit ji do hlavního řádku.\n"
        "- Původní rozbalovací seznam Navržený výrobek zůstává zachován.\n"
    )
    (OUT / "RELEASE_NOTES.txt").write_text(notes, encoding="utf-8")

    for rel in ["app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py", "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_workspace.py"]:
        py_compile.compile(str(OUT / rel), doraise=True)

    ui = (OUT / "hit_workspace.py").read_text(encoding="utf-8")
    assert "class HitVariantsDialog" in ui
    assert 'text="Varianty…"' in ui
    assert "def open_variants" in ui
    assert "1 • doporučeno" in ui
    assert 'APP_VERSION = "0.7.2"' in (OUT / "app.pyw").read_text(encoding="utf-8")

    files = [
        "app.pyw", "catalog_engine.py", "project_model.py", "project_ui.py", "autocomplete.py", "updater.py",
        "bulk_import_engine.py", "bulk_import.py", "xlsx_export.py", "hit_core.py", "hit_workspace.py",
        "schoeck_archive_sources.json", "catalogs/schoeck_sconnex_w_2023.json",
        "catalogs/maxfrank_egcobox_m_2022.json.gz.b64", "catalogs/maxfrank_egcobox_xl_2022.json.gz.b64",
    ]
    manifest_files = []
    for rel in files:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/0.7.2/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "0.7.2",
        "notes": "Návrh HIT má samostatný přehled Varianty… se všemi vyhovujícími výrobky a jejich statickými hodnotami; jinou variantu lze dvojklikem ručně zvolit.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("v0.7.2 OK")


if __name__ == "__main__":
    main()
