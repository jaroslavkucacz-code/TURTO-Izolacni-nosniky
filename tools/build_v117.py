from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "updates" / "1.1.6"
OUT = ROOT / "updates" / "1.1.7"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


def compile_sources(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.suffix not in {".py", ".pyw"}:
            continue
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def patch_substitution(text: str) -> str:
    text = replace_once(
        text,
        'SUBSTITUTION_MODULE_VERSION = "1.1.6"',
        'SUBSTITUTION_MODULE_VERSION = "1.1.7"',
        "substitution module version",
    )

    text = replace_once(
        text,
        '_WIRE_DIAMETERS = (6, 8, 10, 12)\n',
        '_WIRE_DIAMETERS = (6, 8, 10, 12)\n_DIAMETER_TYPES = {"ZVX", "ZDX", "DD", "DVL", "DDL"}\n',
        "diameter type constants",
    )

    old_overview = '''def _variant_overview(targets: list[dict[str, Any]]) -> str:
    diameters = sorted({value for value in (_target_wire_diameter(target) for target in targets) if value})
    suffix = "/".join(f"Ø{value:02d}" for value in diameters)
    return f"{len(targets)} ({suffix})" if suffix else str(len(targets))
'''
    new_overview = '''def _variant_overview(
    targets: list[dict[str, Any]],
    availability: dict[str, Any] | None = None,
) -> str:
    availability = availability if isinstance(availability, dict) else {}
    if availability:
        markers = []
        for diameter in _WIRE_DIAMETERS:
            status = availability.get(str(diameter), {})
            available = bool(status.get("available")) if isinstance(status, dict) else False
            markers.append(f"Ø{diameter:02d}{'✓' if available else '×'}")
        return f"{len(targets)} • " + " ".join(markers)
    diameters = sorted({value for value in (_target_wire_diameter(target) for target in targets) if value})
    suffix = "/".join(f"Ø{value:02d}" for value in diameters)
    return f"{len(targets)} ({suffix})" if suffix else str(len(targets))
'''
    text = replace_once(text, old_overview, new_overview, "variant overview")

    marker = '\n\nclass SubstitutionVariantsDialog(tk.Toplevel):\n'
    availability_helpers = r'''

def _raw_zvx_compression_category(record: dict[str, Any]) -> str:
    code = str(record.get("code", "")).strip()
    match = re.match(r"^(\d{2})(\d{2})", code)
    if not match:
        return "unknown"
    return "bearing" if int(match.group(2)) > 0 else "without"


def _zvx_unavailable_diameter_reason(
    database: HitDatabase,
    diameter: int,
    metadata: dict[str, Any],
    source_totals: DirectionalActions,
    allowed_length_codes: set[int] | None,
) -> str:
    records = getattr(database, "zvx_records", None)
    if not isinstance(records, list) or not records:
        return "v načtených datech HIT není pro tento průměr ověřená katalogová varianta"

    series = str(metadata.get("target_series", ""))
    concrete = "C20/25" if str(metadata.get("target_concrete", "")) == "C20/25" else "C25/30"
    height = int(metadata.get("target_height_mm") or 0)
    source_length = int(metadata.get("source_length_mm") or 0)
    source_compression = str(metadata.get("source_compression_category", "unknown"))
    length_options = _target_length_options(source_length, allowed_length_codes)
    length_by_code = {code: length for code, length in length_options}
    length_text = "/".join(str(length) for _code, length in length_options) or "žádná"

    diameter_rows: list[tuple[dict[str, Any], int]] = []
    for record in records:
        try:
            length_code = int(record.get("length_code", 0))
            record_diameter = int(record.get("diameter", 0))
        except (TypeError, ValueError):
            continue
        if (
            str(record.get("series", "")) == series
            and str(record.get("concrete", "")) == concrete
            and length_code in length_by_code
            and record_diameter == int(diameter)
        ):
            diameter_rows.append((record, length_by_code[length_code]))

    if not diameter_rows:
        return f"v přípustných délkách {length_text} mm není katalogová varianta Ø{diameter:02d}"

    compression_rows = [
        (record, length)
        for record, length in diameter_rows
        if _raw_zvx_compression_category(record) == source_compression
    ]
    if not compression_rows:
        return "v přípustné délce existuje pouze provedení s jiným tlakovým přenosem"

    height_rows = [
        (record, length)
        for record, length in compression_rows
        if int(record.get("h_min", 0)) <= height <= int(record.get("h_max", 0))
    ]
    if not height_rows:
        minimum = min(int(record.get("h_min", 0)) for record, _length in compression_rows)
        maximum = max(int(record.get("h_max", 0)) for record, _length in compression_rows)
        if height < minimum:
            return f"katalogový rozsah pro přípustnou délku začíná na h = {minimum} mm; zdroj má h = {height} mm"
        if height > maximum:
            return f"katalogový rozsah pro přípustnou délku končí na h = {maximum} mm; zdroj má h = {height} mm"
        ranges = sorted({f"{int(record.get('h_min', 0))}–{int(record.get('h_max', 0))}" for record, _length in compression_rows})
        return f"výška h = {height} mm neleží v katalogových intervalech {', '.join(ranges)} mm"

    requirement = max(
        float(source_totals.normalized().v_pos),
        float(source_totals.normalized().v_neg),
    )
    best_record, best_length = max(
        height_rows,
        key=lambda item: abs(float(item[0].get("vrd", 0.0))) * item[1] / 1000.0,
    )
    capacity = abs(float(best_record.get("vrd", 0.0))) * best_length / 1000.0
    if capacity + _TOL < requirement:
        return (
            f"max. {fmt(capacity)} kN/prvek při L = {best_length} mm "
            f"je méně než požadovaných {fmt(requirement)} kN/prvek"
        )
    return "katalogový prvek splní dílčí smyk, ale byl vyloučen jinou technickou podmínkou"


def _diameter_availability(
    database: HitDatabase,
    targets: list[dict[str, Any]],
    metadata: dict[str, Any],
    source_totals: DirectionalActions,
    allowed_length_codes: set[int] | None,
) -> dict[str, dict[str, Any]]:
    clean = [target for target in targets if isinstance(target, dict)]
    target_types = {str(target.get("connection_type", "")).upper() for target in clean}
    if not (target_types & _DIAMETER_TYPES):
        return {}

    normalized = source_totals.normalized()
    pure_shear = (
        max(normalized.v_pos, normalized.v_neg) > _TOL
        and max(normalized.m_pos, normalized.m_neg, normalized.n_pos, normalized.n_neg) <= _TOL
    )
    result: dict[str, dict[str, Any]] = {}
    for diameter in _WIRE_DIAMETERS:
        candidates = [target for target in clean if _target_wire_diameter(target) == diameter]
        if candidates:
            result[str(diameter)] = {
                "available": True,
                "count": len(candidates),
                "best_id": str(candidates[0].get("id", "")),
                "reason": f"{len(candidates)} staticky a geometricky vyhovující varianta" + ("y" if len(candidates) != 1 else ""),
            }
            continue
        if pure_shear and ("ZVX" in target_types or "ZDX" in target_types):
            reason = _zvx_unavailable_diameter_reason(
                database, diameter, metadata, source_totals, allowed_length_codes
            )
        else:
            reason = "pro zadané M/N/V, délku, výšku a tlakový přenos není vyhovující varianta"
        result[str(diameter)] = {
            "available": False,
            "count": 0,
            "best_id": "",
            "reason": reason,
        }
    return result


def _diameter_availability_summary(availability: dict[str, Any] | None) -> str:
    availability = availability if isinstance(availability, dict) else {}
    if not availability:
        return ""
    parts = []
    for diameter in _WIRE_DIAMETERS:
        status = availability.get(str(diameter), {})
        if not isinstance(status, dict):
            continue
        if status.get("available"):
            parts.append(f"Ø{diameter:02d}: vyhovuje ({int(status.get('count', 0) or 0)} variant)")
        else:
            parts.append(f"Ø{diameter:02d}: ne – {status.get('reason', 'není vyhovující varianta')}")
    return "Dostupnost průměrů: " + " | ".join(parts) if parts else ""
'''
    text = replace_once(text, marker, availability_helpers + marker, "diameter availability helpers")

    text = replace_once(
        text,
        '    def __init__(self, parent: "SubstitutionWorkspaceMixin", targets: list[dict[str, Any]], current_id: str) -> None:',
        '    def __init__(self, parent: "SubstitutionWorkspaceMixin", targets: list[dict[str, Any]], current_id: str, diameter_availability: dict[str, Any] | None = None) -> None:',
        "variants dialog signature",
    )
    text = replace_once(
        text,
        '        self._current_id = str(current_id or "")\n        self._target_by_iid: dict[str, dict[str, Any]] = {}',
        '        self._current_id = str(current_id or "")\n        self._diameter_availability = diameter_availability if isinstance(diameter_availability, dict) else {}\n        self._target_by_iid: dict[str, dict[str, Any]] = {}',
        "dialog availability state",
    )
    text = replace_once(
        text,
        '                "Základní pohled zobrazuje nejlepší vyhovující prvek pro každý dostupný průměr smykové výztuže 06 / 08 / 10 / 12. "\n                "Volbou Zobrazit všechny lze vybrat i jinou délku, výztužnou třídu nebo konstrukční typ. Všechny řádky již splňují statickou a geometrickou kontrolu."',
        '                "Základní pohled uvádí všechny průměry 06 / 08 / 10 / 12. Vyhovující varianty lze vybrat; šedé řádky vysvětlují, proč jiný průměr pro zadanou výšku, délku, únosnost nebo tlakový přenos dostupný není. "\n                "Volbou Zobrazit všechny lze rozbalit všechny skutečně vyhovující délky, výztužné třídy a konstrukční typy."',
        "dialog help text",
    )
    text = replace_once(
        text,
        '        self.tree.tag_configure("current", background=current_bg)\n        self.tree.tag_configure("diameter_best", background=recommended_bg)',
        '        self.tree.tag_configure("current", background=current_bg)\n        self.tree.tag_configure("diameter_best", background=recommended_bg)\n        self.tree.tag_configure("unavailable", background=parent.colors.get("panel_alt", "#F3F6F9"), foreground=parent.colors.get("muted", "#6B7280"))',
        "unavailable row style",
    )

    populate_start = text.index('    def _populate(self) -> None:\n', text.index('class SubstitutionVariantsDialog'))
    populate_end = text.index('    def _use_selected(self, _event: Any = None) -> str | None:\n', populate_start)
    old_populate = text[populate_start:populate_end]
    new_populate = '''    def _populate(self) -> None:
        previous = self.tree.selection()
        previous_id = ""
        if previous:
            old = self._target_by_iid.get(previous[0])
            previous_id = str(old.get("id")) if old else ""
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        self._target_by_iid.clear()

        displayed = _diameter_representatives(
            self._targets,
            current_id=self._current_id,
            show_all=bool(self.show_all_var.get()),
        )
        groups: dict[int, list[dict[str, Any]]] = {diameter: [] for diameter in _WIRE_DIAMETERS}
        without_diameter: list[dict[str, Any]] = []
        for target in displayed:
            diameter = _target_wire_diameter(target)
            if diameter in groups:
                groups[diameter].append(target)
            else:
                without_diameter.append(target)

        first_by_diameter: set[int] = set()
        selected_iid = ""
        row_index = 0
        for diameter in _WIRE_DIAMETERS:
            group = groups[diameter]
            if not group:
                status = self._diameter_availability.get(str(diameter), {})
                if self._diameter_availability:
                    iid = f"unavailable_{diameter}"
                    reason = str(status.get("reason") or "pro zadané podmínky není vyhovující varianta") if isinstance(status, dict) else "pro zadané podmínky není vyhovující varianta"
                    self.tree.insert(
                        "", "end", iid=iid, tags=("unavailable",),
                        values=(
                            "není vyhovující",
                            f"Ø {diameter:02d}",
                            "—", "—", "—", "—", "—", "—", "—", "—",
                            reason,
                        ),
                    )
                continue

            for target in group:
                iid = f"variant_{row_index}"
                row_index += 1
                self._target_by_iid[iid] = target
                target_id = str(target.get("id"))
                is_current = target_id == self._current_id
                is_best = diameter not in first_by_diameter
                first_by_diameter.add(diameter)
                role = "aktuálně vybraná" if is_current else ("doporučená pro Ø" if is_best else "další vyhovující")
                spacing = float(target.get("spacing_max_m", 0.0) or 0.0)
                utilization = f"a max {fmt(spacing, 3)} m" if spacing > 0 else f"{fmt(float(target.get('utilization', 0.0) or 0.0) * 100.0)} %"
                tags = ("current",) if is_current else (("diameter_best",) if is_best else ())
                self.tree.insert(
                    "", "end", iid=iid, tags=tags,
                    values=(
                        role,
                        _wire_diameter_text(target),
                        str(target.get("connection_type", "")),
                        str(target.get("designation", "")),
                        f"{target.get('length_mm', '—')} mm",
                        str(target.get("compression_text", "")),
                        self._capacity(target, "m_capacity_element"),
                        self._capacity(target, "v_capacity_element"),
                        self._capacity(target, "n_capacity_element"),
                        utilization,
                        str(target.get("mode", "")),
                    ),
                )
                if target_id == (previous_id or self._current_id):
                    selected_iid = iid

        for target in without_diameter:
            iid = f"variant_{row_index}"
            row_index += 1
            self._target_by_iid[iid] = target
            target_id = str(target.get("id"))
            is_current = target_id == self._current_id
            spacing = float(target.get("spacing_max_m", 0.0) or 0.0)
            utilization = f"a max {fmt(spacing, 3)} m" if spacing > 0 else f"{fmt(float(target.get('utilization', 0.0) or 0.0) * 100.0)} %"
            self.tree.insert(
                "", "end", iid=iid, tags=(("current",) if is_current else ()),
                values=(
                    "aktuálně vybraná" if is_current else "další vyhovující",
                    "—",
                    str(target.get("connection_type", "")),
                    str(target.get("designation", "")),
                    f"{target.get('length_mm', '—')} mm",
                    str(target.get("compression_text", "")),
                    self._capacity(target, "m_capacity_element"),
                    self._capacity(target, "v_capacity_element"),
                    self._capacity(target, "n_capacity_element"),
                    utilization,
                    str(target.get("mode", "")),
                ),
            )
            if target_id == (previous_id or self._current_id):
                selected_iid = iid

        children = self.tree.get_children("")
        if not selected_iid:
            selected_iid = next((iid for iid in children if iid in self._target_by_iid), "")
        if selected_iid:
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
            self.tree.see(selected_iid)

'''
    text = text[:populate_start] + new_populate + text[populate_end:]

    old_use = '''    def _use_selected(self, _event: Any = None) -> str | None:
        selected = self.tree.selection()
        if not selected:
            return "break"
        target = self._target_by_iid.get(selected[0])
        if target is not None:
            self.result = target
            self.destroy()
        return "break"
'''
    new_use = '''    def _use_selected(self, _event: Any = None) -> str | None:
        selected = self.tree.selection()
        if not selected:
            return "break"
        target = self._target_by_iid.get(selected[0])
        if target is None:
            reason = str(self.tree.set(selected[0], "mode") or "Pro zadané podmínky není tento průměr dostupný.")
            messagebox.showinfo("Průměr není vyhovující", reason, parent=self)
            return "break"
        self.result = target
        self.destroy()
        return "break"
'''
    text = replace_once(text, old_use, new_use, "unavailable row click")

    text = replace_once(
        text,
        '("alternatives", "Varianty", 118, "center", False),',
        '("alternatives", "Varianty / průměry", 220, "center", False),',
        "variant column width",
    )

    text = replace_once(
        text,
        '        targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []\n        utilization = ""',
        '        targets = mapping.get("targets") if isinstance(mapping.get("targets"), list) else []\n        diameter_availability = mapping.get("diameter_availability") if isinstance(mapping.get("diameter_availability"), dict) else {}\n        utilization = ""',
        "payload availability",
    )
    text = replace_once(
        text,
        '            "utilization": utilization, "alternatives": _variant_overview(targets), "calculation": calculation_text,',
        '            "utilization": utilization, "alternatives": _variant_overview(targets, diameter_availability), "calculation": calculation_text,',
        "payload diameter overview",
    )

    text = replace_once(
        text,
        '        dialog = SubstitutionVariantsDialog(self, targets, str(mapping.get("selected_target_id") or ""))',
        '        dialog = SubstitutionVariantsDialog(\n            self, targets, str(mapping.get("selected_target_id") or ""),\n            mapping.get("diameter_availability") if isinstance(mapping.get("diameter_availability"), dict) else {},\n        )',
        "dialog availability call",
    )

    text = replace_once(
        text,
        '            warnings = list(dict.fromkeys([*action_warnings, *meta.get("warnings", [])]))\n            if estimate.startswith("MVX-")',
        '            source_totals, _total_warnings = source_element_actions(row)\n            diameter_availability = _diameter_availability(\n                database, targets, meta, source_totals, allowed_lengths\n            )\n            warnings = list(dict.fromkeys([*action_warnings, *meta.get("warnings", [])]))\n            if estimate.startswith("MVX-")',
        "design diameter availability",
    )
    text = replace_once(
        text,
        '                "estimated_type": estimate or order[0],\n                "source_overrides": overrides,',
        '                "estimated_type": estimate or order[0],\n                "diameter_availability": diameter_availability,\n                "source_overrides": overrides,',
        "store diameter availability",
    )

    text = replace_once(
        text,
        '            notes.extend(str(value) for value in action_warnings if str(value))\n            if payload.get("note"):',
        '            notes.extend(str(value) for value in action_warnings if str(value))\n            diameter_summary = _diameter_availability_summary(\n                mapping.get("diameter_availability") if isinstance(mapping.get("diameter_availability"), dict) else {}\n            )\n            if diameter_summary:\n                notes.append(diameter_summary)\n            if payload.get("note"):',
        "PDF diameter summary",
    )

    return text


def run_real_dop_regression(out: Path) -> None:
    dop_value = os.environ.get("HIT_DOP_PATH", "").strip()
    if not dop_value:
        print("HIT_DOP_PATH not set; real DoP regression skipped")
        return
    dop_path = Path(dop_value)
    if not dop_path.exists():
        raise RuntimeError(f"HIT_DOP_PATH does not exist: {dop_path}")

    from bulk_import_engine import preprocess_bulk_designation
    from catalog_engine import CatalogDatabase
    from hit_core import HitDatabase, build_database_from_pdf
    from project_model import create_project_row
    import substitution_workspace as sw

    with tempfile.TemporaryDirectory() as temp_dir:
        hit_path = Path(temp_dir) / "hit.json.gz.b64"
        build_database_from_pdf(dop_path, hit_path)
        hit_db = HitDatabase(hit_path)
        catalog = CatalogDatabase(out / "catalogs")
        cases = (
            (
                "EGCOBOX VXL Z 48-K-C30-h160-REI120-SW",
                "without",
                "HIT-SP ZVX-0500-16-033-30-08",
                {6: "max.", 8: "available", 10: "h = 170", 12: "h = 180"},
            ),
            (
                "EGCOBOX VXL48-K-C30-h160-REI120-SW",
                "bearing",
                "HIT-SP ZVX-0302-16-033-30-08",
                {6: "max.", 8: "available", 10: "h = 170", 12: "h = 170"},
            ),
        )
        for index, (raw, pressure, expected, expected_reasons) in enumerate(cases, start=1):
            clean, note = preprocess_bulk_designation(raw)
            result = catalog.resolve_designation(clean, preferred_concrete="C25/30")
            row = create_project_row(result, position=f"P{index:03d}", quantity=1, note=note, source_text=raw)
            meta = sw.source_metadata(row)
            targets, errors = sw.design_targets(
                hit_db,
                row=row,
                metadata=meta,
                allowed_length_codes=set(sw.SUBSTITUTION_LENGTH_CODES),
            )
            assert targets, (raw, errors)
            assert targets[0]["designation"] == expected, (raw, targets[0]["designation"])
            source_totals, warnings = sw.source_element_actions(row)
            assert not warnings
            availability = sw._diameter_availability(
                hit_db, targets, meta, source_totals, set(sw.SUBSTITUTION_LENGTH_CODES)
            )
            assert availability["8"]["available"] is True
            assert availability["6"]["available"] is False
            assert availability["10"]["available"] is False
            assert availability["12"]["available"] is False
            assert meta["source_compression_category"] == pressure
            for diameter, fragment in expected_reasons.items():
                if fragment == "available":
                    continue
                assert fragment in str(availability[str(diameter)]["reason"]), (raw, diameter, availability)
            print(raw)
            for diameter in sw._WIRE_DIAMETERS:
                status = availability[str(diameter)]
                print(f"  Ø{diameter:02d}: {'ANO' if status['available'] else 'NE'} - {status['reason']}")


def main() -> None:
    if not BASE.exists():
        raise RuntimeError(f"Base update not found: {BASE}")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    app = OUT / "app.pyw"
    app.write_text(
        replace_once(app.read_text(encoding="utf-8"), 'APP_VERSION = "1.1.6"', 'APP_VERSION = "1.1.7"', "app version"),
        encoding="utf-8",
    )

    substitution = OUT / "substitution_workspace.py"
    substitution.write_text(patch_substitution(substitution.read_text(encoding="utf-8")), encoding="utf-8")

    compile_sources(OUT)

    sys.path.insert(0, str(OUT))
    from hit_core import DirectionalActions
    import substitution_workspace as sw

    assert sw.SUBSTITUTION_MODULE_VERSION == "1.1.7"
    fake_targets = [{
        "id": "hit-08", "designation": "HIT-SP ZVX-0500-16-033-30-08",
        "connection_type": "ZVX", "wire_diameter_mm": 8,
    }]
    fake_meta = {
        "target_series": "SP", "target_concrete": "C25/30", "target_height_mm": 160,
        "source_length_mm": 300, "source_compression_category": "without",
    }

    class FakeDatabase:
        zvx_records = [
            {"series": "SP", "concrete": "C25/30", "length_code": 25, "diameter": "06", "code": "0300", "h_min": 160, "h_max": 190, "vrd": 52.1},
            {"series": "SP", "concrete": "C25/30", "length_code": 33, "diameter": "08", "code": "0500", "h_min": 160, "h_max": 190, "vrd": 163.9},
            {"series": "SP", "concrete": "C25/30", "length_code": 33, "diameter": "10", "code": "0500", "h_min": 170, "h_max": 190, "vrd": 256.1},
            {"series": "SP", "concrete": "C25/30", "length_code": 33, "diameter": "12", "code": "0400", "h_min": 180, "h_max": 210, "vrd": 295.0},
        ]

    availability = sw._diameter_availability(
        FakeDatabase(), fake_targets, fake_meta, DirectionalActions(v_pos=48.6), set(sw.SUBSTITUTION_LENGTH_CODES)
    )
    assert availability["8"]["available"] is True
    assert "max." in availability["6"]["reason"]
    assert "h = 170" in availability["10"]["reason"]
    assert "h = 180" in availability["12"]["reason"]
    overview = sw._variant_overview(fake_targets, availability)
    assert "Ø06×" in overview and "Ø08✓" in overview and "Ø10×" in overview and "Ø12×" in overview
    assert "Dostupnost průměrů:" in sw._diameter_availability_summary(availability)

    run_real_dop_regression(OUT)

    generated = substitution.read_text(encoding="utf-8")
    assert "šedé řádky vysvětlují" in generated
    assert "Průměr není vyhovující" in generated
    assert "diameter_availability" in generated
    assert 'APP_VERSION = "1.1.7"' in app.read_text(encoding="utf-8")
    assert not any(OUT.rglob("*.pyc"))
    assert not any(path.name == "__pycache__" for path in OUT.rglob("__pycache__"))

    (OUT / "RELEASE_NOTES.txt").write_text(
        "TURTO ISO v1.1.7\n"
        "- Dialog Vybrat variantu nyní vždy ukáže stav všech průměrů Ø06, Ø08, Ø10 a Ø12.\n"
        "- Vyhovující průměry zůstávají volitelné; nedostupné průměry se zobrazí šedě s konkrétním technickým důvodem.\n"
        "- Rozlišuje se chybějící katalogová délka, odlišný tlakový přenos, výška mimo katalogový rozsah a nedostatečná celková únosnost jednoho prvku.\n"
        "- U VXL Z 48-K a VXL48-K při h160 je jediným platným průměrem Ø08; program nyní vysvětlí, proč Ø06, Ø10 a Ø12 nelze nabídnout.\n"
        "- Hlavní tabulka záměn zobrazuje přehled Ø06× / Ø08✓ / Ø10× / Ø12× a stejné vysvětlení se přenese do poznámky PDF výpočtu.\n"
        "- Žádná nevyhovující varianta se nestane volitelnou; statická, délková a tlaková kontrola zůstává beze změny.\n",
        encoding="utf-8",
    )

    previous_manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    paths = [str(item["path"]) for item in previous_manifest.get("files", [])]
    manifest_files = []
    for rel in paths:
        data = (OUT / rel).read_bytes()
        manifest_files.append({
            "path": rel,
            "url": f"https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main/updates/1.1.7/{rel}",
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "version": "1.1.7",
        "notes": "TURTO ISO: úplný přehled dostupnosti Ø06/08/10/12 včetně důvodů, proč jiný průměr nevyhovuje.",
        "files": manifest_files,
    }
    (ROOT / "update_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Built TURTO ISO v1.1.7")


if __name__ == "__main__":
    main()
