from __future__ import annotations

"""Read-only decoded product detail replacing the old lookup/detail tab."""

from typing import Any
import tkinter as tk
from tkinter import ttk

from catalog_engine import format_result
from ui_utils import place_dialog_on_parent

HIT_CATALOG_ID = "leviat_hit_2023"


def _mapping_lines(row: dict[str, Any]) -> list[str]:
    mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
    if not mapping: return []
    lines: list[str] = []
    status = str(mapping.get("status", "not_run"))
    if status and status != "not_run": lines.append(f"Stav záměny za HIT: {status}")
    targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []
    chosen = str(mapping.get("selected_target_id") or "")
    selected = next((x for x in targets if isinstance(x, dict) and str(x.get("id")) == chosen), None)
    if selected:
        lines.append(f"Vybraný HIT: {selected.get('designation', chosen)}")
        try: lines.append(f"Využití záměny: {float(selected.get('utilization', 0))*100:.1f} %".replace(".", ","))
        except Exception: pass
    lines.extend(f"Upozornění: {v}" for v in mapping.get("warnings", []) if str(v).strip())
    lines.extend(f"Chyba: {v}" for v in mapping.get("errors", []) if str(v).strip())
    return lines


class DecoderDetailDialog(tk.Toplevel):
    def __init__(self, owner: Any, row: dict[str, Any]) -> None:
        super().__init__(owner)
        self.title(f"Detail nosníku – {row.get('position', '')}")
        self.geometry("980x700"); self.minsize(760, 520)
        self.transient(owner); self.grab_set(); self.configure(background=owner.colors["bg"])
        place_dialog_on_parent(self, owner)
        outer = ttk.Frame(self, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True); outer.columnconfigure(0, weight=1); outer.rowconfigure(3, weight=1)
        snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
        selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
        designation = str(snapshot.get("designation") or row.get("source_text") or "—")
        position = str(row.get("position") or "—"); quantity = int(row.get("quantity", 1) or 1)
        ttk.Label(outer, text=f"{position}  •  {quantity} ks", style="DialogTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, text=designation, style="Designation.TLabel", wraplength=900, justify="left").grid(row=1, column=0, sticky="ew", pady=(4, 12))
        meta = ttk.Frame(outer, style="Card.TFrame", padding=12); meta.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        meta.columnconfigure(1, weight=1); meta.columnconfigure(3, weight=1)
        items = (
            ("Výrobce", selection.get("manufacturer", "—")),
            ("Řada / typ", " • ".join(v for v in (str(selection.get("model", "")), str(selection.get("type_name", ""))) if v and v != "—") or "—"),
            ("Beton", selection.get("concrete_min", "—")), ("Výška / rozměr", selection.get("height_mm", "—")),
            ("Varianta / krytí", selection.get("cover", "—")),
            ("Izolant", f"{snapshot.get('insulation_thickness_mm')} mm" if snapshot.get("insulation_thickness_mm") else "—"),
            ("Tlakový přenos", snapshot.get("compression_transfer", "—")),
            ("Katalog", " • ".join(v for v in (str(snapshot.get("catalog_edition", "")), str(snapshot.get("publication_label", ""))) if v) or "—"),
        )
        for idx, (label, value) in enumerate(items):
            r, pair = divmod(idx, 2); c = pair * 2
            ttk.Label(meta, text=label, style="MutedCard.TLabel").grid(row=r, column=c, sticky="nw", padx=(0, 8), pady=3)
            ttk.Label(meta, text=str(value), style="Card.TLabel", wraplength=330, justify="left").grid(row=r, column=c+1, sticky="nw", padx=(0, 22), pady=3)
        body = ttk.Frame(outer, style="Card.TFrame", padding=1); body.grid(row=3, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1); body.rowconfigure(0, weight=1)
        text = tk.Text(body, wrap="word", font=("Calibri", 11), background=owner.colors["panel"], foreground=owner.colors["text"], insertbackground=owner.colors["text"], relief="flat", padx=14, pady=12)
        bar = ttk.Scrollbar(body, orient="vertical", command=text.yview); text.configure(yscrollcommand=bar.set)
        text.grid(row=0, column=0, sticky="nsew"); bar.grid(row=0, column=1, sticky="ns")
        results = snapshot.get("results") if isinstance(snapshot.get("results"), list) else []
        lines = ["STATICKÉ / KATALOGOVÉ HODNOTY", ""]
        if results:
            for result in results:
                if isinstance(result, dict):
                    try: lines.append("• " + format_result(result))
                    except Exception: lines.append("• " + str(result))
        else: lines.append("• Bez samostatně uložených statických hodnot.")
        pages = snapshot.get("source_pages") if isinstance(snapshot.get("source_pages"), list) else []
        lines.extend(["", "ZDROJ A POZNÁMKY", "• Strany: " + (", ".join(str(v) for v in pages) if pages else "—")])
        if str(row.get("source_text") or "").strip(): lines.append("• Původní vstup: " + str(row.get("source_text")).strip())
        if str(row.get("note") or "").strip(): lines.append("• Poznámka: " + str(row.get("note")).strip())
        mapping = _mapping_lines(row)
        if mapping: lines.extend(["", "ZÁMĚNA ZA HIT", *["• " + line for line in mapping]])
        if str(selection.get("catalog_id")) == HIT_CATALOG_ID:
            lines.extend(["", "HIT V DEKODÉRU", "• Jde již o výrobek Leviat HIT; karta Záměny za HIT jej proto nemá znovu převádět."])
        text.insert("1.0", "\n".join(lines)); text.configure(state="disabled")
        buttons = ttk.Frame(outer, style="App.TFrame"); buttons.grid(row=4, column=0, sticky="ew", pady=(12, 0)); buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Zavřít", command=self.destroy).grid(row=0, column=1)
        self.bind("<Escape>", lambda _e: self.destroy())


def show_decoder_detail(owner: Any, _event: Any = None) -> str | None:
    row = owner._single_selected_project_row(warn=True)
    if row is None: return "break"
    DecoderDetailDialog(owner, row)
    return "break"
