from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from hit_core import Candidate, DirectionalActions, HitDatabase, fmt
from xlsx_export import write_xlsx


SUBSTITUTION_MODULE_VERSION = "1.1.0"
_KEYS = ("m_pos", "m_neg", "n_pos", "n_neg", "v_pos", "v_neg")
_LABELS = {
    "m_pos": "M+", "m_neg": "M−", "n_pos": "N+", "n_neg": "N−", "v_pos": "V+", "v_neg": "V−",
}
_FIXED_COVER = {"ZVX", "ZDX", "AT", "FT", "OTX"}


def _num(value: Any) -> float | None:
    if value in (None, "", "—", "-", "–"):
        return None
    try:
        return float(str(value).strip().replace("−", "-").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _unit(value: Any) -> str:
    return str(value or "").upper().replace(" ", "").replace("·", "").replace("−", "-")


def _per_m(kind: str, unit: Any) -> bool:
    value = _unit(unit)
    return value in ({"KNM/M", "KNM/M1"} if kind == "moment" else {"KN/M", "KN/M1"})


def _hint(record: dict[str, Any]) -> str:
    text = " ".join(str(record.get(k, "")) for k in ("label", "key", "note", "text")).upper().replace("−", "-")
    if "±" in text or "+/-" in text or "+-" in text:
        return "both"
    if any(x in text for x in ("NEGATIVE", "ZÁPORN", "ZAPORN", "M-", "V-", "N-")):
        return "neg"
    if any(x in text for x in ("POSITIVE", "KLADN", "M+", "V+", "N+")):
        return "pos"
    return ""


def _read_result(values: dict[str, float], prefix: str, record: dict[str, Any]) -> None:
    positive = _num(record.get("positive"))
    negative = _num(record.get("negative"))
    if positive is not None or negative is not None:
        if positive is not None:
            values[prefix + "_pos"] = max(values[prefix + "_pos"], abs(positive))
        if negative is not None:
            values[prefix + "_neg"] = max(values[prefix + "_neg"], abs(negative))
        return
    value = _num(record.get("value"))
    if value is None:
        return
    hint = _hint(record)
    if hint == "both":
        values[prefix + "_pos"] = max(values[prefix + "_pos"], abs(value))
        values[prefix + "_neg"] = max(values[prefix + "_neg"], abs(value))
    elif hint == "neg" or value < 0:
        values[prefix + "_neg"] = max(values[prefix + "_neg"], abs(value))
    elif value > 0:
        values[prefix + "_pos"] = max(values[prefix + "_pos"], abs(value))


def source_actions(row: dict[str, Any]) -> tuple[DirectionalActions, list[str]]:
    snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
    results = snapshot.get("results") if isinstance(snapshot.get("results"), list) else []
    values = {key: 0.0 for key in _KEYS}
    warnings: list[str] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        kind = str(result.get("kind", "")).lower()
        label = str(result.get("label") or result.get("key") or kind or "hodnota")
        if kind not in {"moment", "shear", "normal"}:
            if kind or result.get("value") not in (None, "") or result.get("text"):
                warnings.append(f"mimo převod: {label}")
            continue
        if not _per_m(kind, result.get("unit")):
            warnings.append(f"mimo převod: {label} [{result.get('unit') or 'bez jednotky'}]")
            continue
        _read_result(values, {"moment": "m", "shear": "v", "normal": "n"}[kind], result)
    actions = DirectionalActions(**values)
    if not actions.has_any():
        warnings.append("nebyly nalezeny jednoznačné účinky M/N/V na metr")
    return actions, list(dict.fromkeys(warnings))


def action_values(actions: DirectionalActions) -> dict[str, float]:
    value = actions.normalized()
    return {key: float(getattr(value, key)) for key in _KEYS}


def action_text(actions: DirectionalActions) -> str:
    units = {"m": "kNm/m", "n": "kN/m", "v": "kN/m"}
    return " • ".join(
        f"{_LABELS[key]} {fmt(value)} {units[key[0]]}"
        for key, value in action_values(actions).items() if value > 1e-9
    ) or "—"


def hit_concrete(project_concrete: str) -> str | None:
    match = re.search(r"C\s*(\d{2})\s*/\s*(\d{2})", str(project_concrete or "").upper())
    if not match or int(match.group(1)) < 20:
        return None
    strength = int(match.group(1))
    return "C20/25" if strength < 25 else ("C25/30" if strength < 30 else "C30/37")


def hit_type_order(actions: DirectionalActions) -> tuple[str, ...]:
    a = actions.normalized()
    if a.n_pos > 1e-9 or a.n_neg > 1e-9:
        return ("AT", "FT") if a.n_pos <= 1e-9 else ("FT",)
    if a.m_pos > 1e-9:
        return ("DDL", "DD") if a.v_neg > 1e-9 else ("DVL", "DD", "DDL")
    if a.m_neg > 1e-9:
        return ("MVX", "DDL", "DD") if a.v_neg > 1e-9 else ("MVX", "DVL", "DD", "DDL")
    if a.v_neg > 1e-9:
        return ("ZDX",)
    if a.v_pos > 1e-9:
        return ("ZVX",)
    return ()


def design_targets(
    database: HitDatabase,
    actions: DirectionalActions,
    *,
    series: str,
    height: int,
    cover: int,
    concrete: str,
    lengths: set[int],
) -> tuple[list[dict[str, Any]], list[str]]:
    targets: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for connection_type in hit_type_order(actions):
        target_cover = 30 if connection_type in _FIXED_COVER else cover
        candidates, error, _info = database.proposal_candidates(
            connection_type, series, height, target_cover, concrete, actions, lengths, False, load_distance_x=0.0
        )
        if error and not candidates:
            errors.append(f"{connection_type}: {error}")
            continue
        for candidate in candidates[:20]:
            if candidate.designation in seen:
                continue
            seen.add(candidate.designation)
            targets.append(target_dict(candidate, actions))
            if len(targets) >= 50:
                return targets, errors
    return targets, errors


def calculation(candidate: Candidate, actions: DirectionalActions) -> str:
    if candidate.spacing_max > 0:
        return f"{action_text(actions)} → amax {fmt(candidate.spacing_max, 3)} m ({candidate.mode})"
    eta = 100.0 * max(0.0, float(candidate.utilization))
    text = f"{action_text(actions)} → ηHIT {fmt(eta)} %; rezerva {fmt(max(0.0, 100.0 - eta))} p. b.; {candidate.mode}"
    if candidate.connection_type in {"MVX", "MVXL"}:
        text += f"; M1/V1 {fmt(candidate.m1)}/{fmt(candidate.v1)}; M2/V2 {fmt(candidate.m2)}/{fmt(candidate.v2)}"
    return text


def target_dict(candidate: Candidate, actions: DirectionalActions) -> dict[str, Any]:
    return {
        "id": candidate.designation,
        "designation": candidate.designation,
        "connection_type": candidate.connection_type,
        "series": candidate.series,
        "cover_mm": candidate.cover,
        "height_mm": candidate.height,
        "concrete": candidate.concrete,
        "length_mm": candidate.physical_length_mm,
        "utilization": float(candidate.utilization),
        "spacing_max_m": float(candidate.spacing_max),
        "mode": candidate.mode,
        "page": candidate.page,
        "m1": float(candidate.m1), "v1": float(candidate.v1),
        "m2": float(candidate.m2), "v2": float(candidate.v2),
        "actions": action_values(actions),
        "calculation": calculation(candidate, actions),
    }


def selected_target(mapping: dict[str, Any]) -> dict[str, Any] | None:
    targets = mapping.get("targets") if isinstance(mapping, dict) else []
    if not isinstance(targets, list):
        return None
    selected = str(mapping.get("selected_target_id") or "")
    if selected:
        for target in targets:
            if isinstance(target, dict) and str(target.get("id")) == selected:
                return target
    return next((target for target in targets if isinstance(target, dict)), None)


class SubstitutionWorkspaceMixin:
    COLUMNS = (
        ("position", "Pozice", 78, "w", False),
        ("quantity", "Ks", 48, "center", False),
        ("manufacturer", "Původní výrobce", 120, "w", False),
        ("source", "Původní typ", 300, "w", True),
        ("height", "h [mm]", 68, "center", False),
        ("source_concrete", "Beton zdroje", 90, "center", False),
        ("m_pos", "M+", 72, "center", False), ("m_neg", "M−", 72, "center", False),
        ("n_pos", "N+", 72, "center", False), ("n_neg", "N−", 72, "center", False),
        ("v_pos", "V+", 72, "center", False), ("v_neg", "V−", 72, "center", False),
        ("target_type", "HIT typ", 72, "center", False),
        ("target", "Navržený HIT", 320, "w", True),
        ("utilization", "Využití", 82, "center", False),
        ("alternatives", "Varianty", 70, "center", False),
        ("calculation", "Drobný statický výpočet", 430, "w", True),
        ("status", "Stav", 112, "center", False),
        ("note", "Poznámka / omezení", 280, "w", True),
    )

    def _init_substitution_workspace(self) -> None:
        state = self.settings.setdefault("substitution", {})
        if not isinstance(state, dict):
            state = {}
            self.settings["substitution"] = state
        self.sub_series_var = tk.StringVar(value=str(state.get("series", "HP")))
        self.sub_cover_var = tk.StringVar(value=str(state.get("cover", "35")))
        self.sub_status_var = tk.StringVar(value="Připraveno k vytvoření tabulky záměn.")

    def _build_substitution_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        head = ttk.Frame(parent, style="Card.TFrame", padding=(16, 13))
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Tabulka záměn jiných výrobců za Leviat HIT", style="ProjectTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            head,
            text="Původní typy se přebírají z karty Projektové řádky. Jako požadavek se použijí jejich plné katalogové únosnosti.",
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        bar = ttk.Frame(parent, style="App.TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bar, text="Aktualizovat z projektu", command=self.refresh_substitution_tree).grid(row=0, column=0)
        ttk.Button(bar, text="Navrhnout vybrané", style="Accent.TButton", command=lambda: self.design_substitutions(True)).grid(row=0, column=1, padx=(7, 0))
        ttk.Button(bar, text="Navrhnout vše", command=lambda: self.design_substitutions(False)).grid(row=0, column=2, padx=(7, 0))
        ttk.Button(bar, text="Kopírovat tabulku", command=self.copy_substitution_table).grid(row=0, column=3, padx=(7, 0))
        ttk.Button(bar, text="Export Excel", command=self.export_substitution_xlsx).grid(row=0, column=4, padx=(7, 0))
        ttk.Separator(bar, orient="vertical").grid(row=0, column=5, sticky="ns", padx=12)
        ttk.Label(bar, text="Řada HIT").grid(row=0, column=6, padx=(0, 5))
        series = ttk.Combobox(bar, textvariable=self.sub_series_var, values=("HP", "SP"), state="readonly", width=5)
        series.grid(row=0, column=7)
        ttk.Label(bar, text="cnom").grid(row=0, column=8, padx=(12, 5))
        cover = ttk.Combobox(bar, textvariable=self.sub_cover_var, values=("30", "35", "50"), state="readonly", width=5)
        cover.grid(row=0, column=9)
        series.bind("<<ComboboxSelected>>", self._sub_setting_changed)
        cover.bind("<<ComboboxSelected>>", self._sub_setting_changed)
        bar.columnconfigure(20, weight=1)
        ttk.Label(bar, textvariable=self.sub_status_var, style="Muted.TLabel").grid(row=0, column=20, sticky="e")

        warning = ttk.Frame(parent, style="Warning.TFrame", padding=(12, 9))
        warning.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            warning,
            text=(
                "Jde o předběžnou statickou záměnu M/N/V. Neověřuje tuhost, deformace, požární odolnost, tloušťku izolantu, "
                "tlakový přenos, geometrii, kotvení, spáry ani montáž. Maxima původního typu se konzervativně kontrolují současně."
            ),
            style="Warning.TLabel", wraplength=1450, justify="left",
        ).pack(anchor="w")

        card = ttk.Frame(parent, style="Card.TFrame", padding=(10, 10, 10, 8))
        card.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        frame = ttk.Frame(card, style="Card.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = tuple(item[0] for item in self.COLUMNS)
        self.sub_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended", style="Project.Treeview")
        for column, label, width, anchor, stretch in self.COLUMNS:
            self.sub_tree.heading(column, text=label)
            self.sub_tree.column(column, width=width, minwidth=42, anchor=anchor, stretch=stretch)
        y = ttk.Scrollbar(frame, orient="vertical", command=self.sub_tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=self.sub_tree.xview)
        self.sub_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.sub_tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        self.sub_tree.tag_configure("odd", background=self.colors["panel_alt"])
        self.sub_tree.tag_configure("ok", foreground=self.colors["success"])
        self.sub_tree.tag_configure("review", foreground=self.colors["warning_text"])
        self.sub_tree.tag_configure("error", foreground=self.colors["danger"])
        self.sub_tree.bind("<Control-c>", lambda _event: self.copy_substitution_table())
        self.refresh_substitution_tree()

    def _sub_setting_changed(self, _event: Any = None) -> None:
        state = self.settings.setdefault("substitution", {})
        if isinstance(state, dict):
            state["series"] = self.sub_series_var.get()
            state["cover"] = self.sub_cover_var.get()
        if hasattr(self, "_save_settings"):
            self._save_settings()
        self.sub_status_var.set("Nastavení změněno – spusťte Navrhnout vše.")

    def _on_substitution_tab_selected(self, _event: Any = None) -> None:
        try:
            if str(self.main_notebook.select()) == str(self.substitution_tab):
                self.refresh_substitution_tree()
        except Exception:
            pass

    def _payload(self, row: dict[str, Any]) -> tuple[dict[str, Any], str]:
        selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
        snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
        mapping = row.get("mapping") if isinstance(row.get("mapping"), dict) else {}
        actions, warnings = source_actions(row)
        values = action_values(actions)
        target = selected_target(mapping)
        status = str(mapping.get("status", "not_run"))
        status_text = {"not_run": "NEPOSOUZENO", "ok": "VYHOVUJE", "review": "KONTROLA", "error": "NELZE", "already_hit": "JIŽ HIT"}.get(status, status.upper())
        targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []
        utilization = ""
        calculation_text = ""
        if target:
            spacing = float(target.get("spacing_max_m", 0.0) or 0.0)
            utilization = ("a max " + fmt(spacing, 3) + " m") if spacing > 0 else fmt(100.0 * float(target.get("utilization", 0.0))) + " %"
            calculation_text = str(target.get("calculation", ""))
        note = " • ".join(warnings)
        if status == "error" and mapping.get("selected_target_id"):
            note = str(mapping.get("selected_target_id"))
        return {
            "position": str(row.get("position", "")), "quantity": int(row.get("quantity", 1)),
            "manufacturer": str(selection.get("manufacturer", "")), "source": str(snapshot.get("designation", "")),
            "height": str(selection.get("height_mm", "")), "source_concrete": str(selection.get("concrete_min", "")),
            **{key: (fmt(values[key]) if values[key] > 1e-9 else "") for key in _KEYS},
            "target_type": str(target.get("connection_type", "")) if target else "",
            "target": str(target.get("designation", "")) if target else "",
            "utilization": utilization, "alternatives": len(targets), "calculation": calculation_text,
            "status": status_text, "note": note,
        }, status

    def refresh_substitution_tree(self) -> None:
        if not hasattr(self, "sub_tree"):
            return
        selected = set(self.sub_tree.selection())
        for item in self.sub_tree.get_children(""):
            self.sub_tree.delete(item)
        mapped = 0
        for index, row in enumerate(self.project.rows):
            payload, status = self._payload(row)
            tags = ["odd"] if index % 2 else []
            if status in {"ok", "review", "error"}:
                tags.append(status)
            row_id = str(row.get("id"))
            self.sub_tree.insert("", "end", iid=row_id, values=tuple(payload[c] for c, *_ in self.COLUMNS), tags=tuple(tags))
            if status in {"ok", "review"}:
                mapped += 1
        valid = [row_id for row_id in selected if self.sub_tree.exists(row_id)]
        if valid:
            self.sub_tree.selection_set(valid)
        self.sub_status_var.set(f"{len(self.project.rows)} řádků projektu • {mapped} s návrhem HIT")

    def _settings(self) -> tuple[HitDatabase, str, int, str, set[int]] | None:
        database = getattr(self, "hit_db", None)
        if database is None:
            messagebox.showwarning("Data HIT", "Nejprve načtěte data v kartě Návrh HIT.", parent=self)
            return None
        project_concrete = self.project_concrete_var.get() if hasattr(self, "project_concrete_var") else self.project.concrete_class
        concrete = hit_concrete(project_concrete)
        if concrete is None:
            messagebox.showwarning("Beton", "Automatická záměna vyžaduje projektový beton alespoň C20/25.", parent=self)
            return None
        lengths = self.allowed_hit_lengths() if hasattr(self, "allowed_hit_lengths") else {100, 50, 33, 25}
        if not lengths:
            messagebox.showwarning("Délky HIT", "V kartě Návrh HIT povolte alespoň jednu délku.", parent=self)
            return None
        return database, self.sub_series_var.get().upper(), int(self.sub_cover_var.get()), concrete, set(lengths)

    @staticmethod
    def _height(row: dict[str, Any]) -> int | None:
        selection = row.get("selection") if isinstance(row.get("selection"), dict) else {}
        raw = str(selection.get("height_mm", "")).strip()
        if not re.fullmatch(r"\d+", raw):
            return None
        value = int(raw)
        return value if value > 0 and value % 10 == 0 else None

    @staticmethod
    def _already_hit(row: dict[str, Any]) -> bool:
        snapshot = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
        text = str(snapshot.get("designation", "")).upper()
        return "HIT-HP" in text or "HIT-SP" in text

    def design_substitutions(self, selected_only: bool) -> None:
        settings = self._settings()
        if settings is None:
            return
        database, series, cover, concrete, lengths = settings
        selected = set(self.sub_tree.selection())
        if selected_only and not selected:
            messagebox.showinfo("Záměny za HIT", "Vyberte alespoň jeden řádek.", parent=self)
            return
        rows = [row for row in self.project.rows if not selected_only or str(row.get("id")) in selected]
        ok = review = failed = skipped = 0
        for row in rows:
            if self._already_hit(row):
                row["mapping"] = {"status": "already_hit", "targets": [], "selected_target_id": None}
                skipped += 1
                continue
            actions, warnings = source_actions(row)
            height = self._height(row)
            if not actions.has_any() or height is None:
                message = "Chybí použitelné účinky." if not actions.has_any() else "Výška musí být jednoznačná a po 10 mm."
                row["mapping"] = {"status": "error", "targets": [], "selected_target_id": message}
                failed += 1
                continue
            targets, errors = design_targets(database, actions, series=series, height=height, cover=cover, concrete=concrete, lengths=lengths)
            if not targets:
                row["mapping"] = {"status": "error", "targets": [], "selected_target_id": " | ".join(errors[:4]) or "Bez vyhovujícího HIT."}
                failed += 1
                continue
            row["mapping"] = {
                "status": "review" if warnings else "ok",
                "targets": targets,
                "selected_target_id": str(targets[0]["id"]),
            }
            if warnings:
                review += 1
            else:
                ok += 1
        self.project.touch()
        if hasattr(self, "mark_project_dirty"):
            self.mark_project_dirty()
        self.refresh_substitution_tree()
        if hasattr(self, "refresh_project_tree"):
            self.refresh_project_tree()
        self.sub_status_var.set(f"Navrženo {ok} • ke kontrole {review} • nelze {failed} • již HIT {skipped}")

    def _output_rows(self) -> list[dict[str, Any]]:
        selected = set(self.sub_tree.selection())
        rows = []
        for row in self.project.rows:
            if selected and str(row.get("id")) not in selected:
                continue
            rows.append(self._payload(row)[0])
        return rows

    def copy_substitution_table(self) -> str:
        rows = self._output_rows()
        if not rows:
            return "break"
        headers = [label for _, label, *_ in self.COLUMNS]
        ids = [column for column, *_ in self.COLUMNS]
        lines = ["\t".join(headers)]
        lines.extend("\t".join(str(row.get(column, "")).replace("\n", " ") for column in ids) for row in rows)
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self.sub_status_var.set(f"Zkopírováno {len(rows)} řádků.")
        return "break"

    def export_substitution_xlsx(self) -> None:
        rows = self._output_rows()
        if not rows:
            messagebox.showinfo("Export", "Není co exportovat.", parent=self)
            return
        name = re.sub(r'[\\/:*?"<>|]+', "_", str(self.project.name or "projekt")).strip() or "projekt"
        path = filedialog.asksaveasfilename(
            parent=self, title="Uložit tabulku záměn", defaultextension=".xlsx",
            initialfile=f"Tabulka_zamen_HIT_{name}.xlsx", filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        headers = [label for _, label, *_ in self.COLUMNS]
        ids = [column for column, *_ in self.COLUMNS]
        target = write_xlsx(
            Path(path), headers=headers, rows=[[row.get(column, "") for column in ids] for row in rows],
            sheet_name="Tabulka záměn za HIT", creator="TURTO ISO – Vytvořil Ing. Jaroslav Kučera",
        )
        self.sub_status_var.set(f"Exportováno {len(rows)} řádků: {target.name}")
        try:
            if sys.platform == "win32":
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception:
            pass
