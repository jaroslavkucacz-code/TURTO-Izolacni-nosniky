from __future__ import annotations

"""Sjednocení posuvnosti smykových trnů pro TURTO 2.2.2.

Interní kód zůstává kvůli kompatibilitě:
- ``axial`` = jednosměrný posun ve směru osy trnu,
- ``transverse`` = obousměrný posun: ve směru osy + příčně k ose.

Q varianty výrobců jsou vždy obousměrné.
"""

import re
from typing import Any, Callable

ONE_WAY = "axial"
TWO_WAY = "transverse"

ONE_WAY_LABEL = "Jednosměrný – podélný posun"
TWO_WAY_LABEL = "Obousměrný – podélný + příčný posun"
MOVEMENT_LABELS = (ONE_WAY_LABEL, TWO_WAY_LABEL)

_TWO_WAY_WORDS = (
    "obousměr", "obousmer", "dvousměr", "dvousmer",
    "2směr", "2smer", "2-směr", "2-smer", "2d",
    "příčný", "pricny", "transverse", "boční", "bocni", "lateral",
)
_ONE_WAY_WORDS = (
    "jednosměr", "jednosmer", "1směr", "1smer", "1-směr", "1-smer",
    "podélný", "podelny", "longitudinal", "axial", "axiální",
)

_SCHOCK_Q_BEFORE = re.compile(
    r"\b(?P<family>SLD|LD)\s*[- ]?Q\s*[- ]?(?P<size>\d+)\b",
    re.I,
)
_SCHOCK_Q_AFTER = re.compile(
    r"\b(?P<family>SLD|LD)\s*[- ]?(?P<size>\d+)\s*[- ]?Q\b",
    re.I,
)
_ANCON_Q_BEFORE = re.compile(
    r"\b(?P<family>ESD|HLD|DSD|DSDS)\s*[- ]?Q\s*[- ]?(?P<size>\d+)\b",
    re.I,
)
_ANCON_Q_AFTER = re.compile(
    r"\b(?P<family>ESD|HLD|DSD|DSDS)\s*[- ]?(?P<size>\d+)\s*[- ]?Q\b",
    re.I,
)


def normalize_movement(value: Any, default: str = ONE_WAY) -> str:
    text = str(value or "").strip().lower()
    if text in {TWO_WAY, "q", "two-way", "two_way", "2-way", "2way"}:
        return TWO_WAY
    if text in {ONE_WAY, "one-way", "one_way", "1-way", "1way"}:
        return ONE_WAY
    if any(token in text for token in _TWO_WAY_WORDS):
        return TWO_WAY
    if any(token in text for token in _ONE_WAY_WORDS):
        return ONE_WAY
    return TWO_WAY if str(default) == TWO_WAY else ONE_WAY


def movement_label(value: Any) -> str:
    return TWO_WAY_LABEL if normalize_movement(value) == TWO_WAY else ONE_WAY_LABEL


def _canonical_q_family(manufacturer: str, base_family: str) -> str:
    base = str(base_family or "").upper().replace(" ", "").replace("_", "-")
    if str(manufacturer).lower().startswith("sch"):
        if base in {"SLD", "LD"}:
            return base + "-Q"
    if base in {"ESD", "HLD", "DSD", "DSDS"}:
        return base + "Q"
    return ""


def explicit_q_variant(text: Any) -> tuple[str, str] | None:
    """Return (base family, size) when the designation explicitly denotes a Q variant."""
    raw = str(text or "").upper().replace("–", "-").replace("—", "-")
    for pattern in (_SCHOCK_Q_BEFORE, _SCHOCK_Q_AFTER, _ANCON_Q_BEFORE, _ANCON_Q_AFTER):
        match = pattern.search(raw)
        if match:
            return match.group("family").upper(), match.group("size")
    return None


def wrap_decoder(fallback: Callable[[str], Any]) -> Callable[[str], Any]:
    """Make an existing decoder tolerant to historical Q-after-size notation."""
    def decode(text: str):
        info = fallback(text)
        if not isinstance(info, dict):
            return info

        result = dict(info)
        family = str(result.get("family", "") or "")
        base_family = str(result.get("base_family", "") or family).upper()
        base_family = base_family.replace("-Q", "").removesuffix("Q")
        manufacturer = str(result.get("manufacturer", "") or "")
        size = str(result.get("size", "") or "")

        q = explicit_q_variant(text)
        family_is_q = family.upper().replace("-", "").endswith("Q")
        if q is not None:
            q_family, q_size = q
            if base_family.replace("-", "") == q_family.replace("-", "") and size == q_size:
                family_is_q = True

        if family_is_q:
            canonical = _canonical_q_family(manufacturer, base_family)
            if canonical:
                result["family"] = canonical
            result["base_family"] = base_family
            result["movement"] = TWO_WAY
        else:
            result["movement"] = ONE_WAY
        return result
    return decode


def validate_ancon_application(application: Any, movement: Any) -> str:
    """Return an error for combinations not supported by the verified Ancon range."""
    app = str(application or "").strip().lower()
    existing_wall = app in {"existing_wall", "existing", "stávající", "stavajici"} or "stávaj" in app
    if existing_wall and normalize_movement(movement) == TWO_WAY:
        return (
            "Pro napojení na stávající betonovou stěnu je v ověřeném katalogu Ancon "
            "uveden E-HLD pouze jako jednosměrně posuvný. Variantu E-HLDQ TURTO "
            "automaticky nenavrhuje; pro obousměrný pohyb je nutné zvolit jiný "
            "ověřený detail / typ."
        )
    return ""


def _has_two_way_word(text: Any) -> bool:
    lowered = str(text or "").lower()
    return any(token in lowered for token in _TWO_WAY_WORDS)


def _has_one_way_word(text: Any) -> bool:
    lowered = str(text or "").lower()
    return any(token in lowered for token in _ONE_WAY_WORDS)


def install(app_base: Any | None = None) -> None:
    """Install movement normalization after the historical Schöck decoder patch."""
    import tkinter.ttk as ttk

    import shear_dowels_catalog as catalog
    import shear_dowels_ui as base_ui
    import shear_dowels_ui_214 as ui214
    import shear_dowels_ui_215 as ui215
    import shear_dowels_schedule as schedule
    import shear_dowels_schedule_215 as schedule215
    import schoeck_dorn_decoder as schoeck_decoder

    if getattr(catalog, "_turto_movement_222_installed", False):
        if app_base is not None and hasattr(app_base, "ThermalConnectorApp"):
            cls = app_base.ThermalConnectorApp
            if hasattr(ui215, "_turto_movement_refresh"):
                cls.refresh_shear_tables = ui215._turto_movement_refresh
            if hasattr(ui215, "_turto_movement_report_rows"):
                cls.collect_shear_report_rows = ui215._turto_movement_report_rows
        return

    original_decoder = base_ui.decode_dowel
    decoder = wrap_decoder(original_decoder)
    catalog.decode_dowel = decoder
    base_ui.decode_dowel = decoder
    schoeck_decoder.decode_dowel = decoder

    original_ancon = catalog.design_ancon

    def design_ancon_checked(
        *,
        ved: float,
        slab_mm: float,
        gap_mm: float,
        concrete: str,
        movement: str = ONE_WAY,
        application: str = "new",
        low_sleeve: str = "stainless",
    ):
        movement_code = normalize_movement(movement)
        error = validate_ancon_application(application, movement_code)
        if error:
            return [], error
        return original_ancon(
            ved=ved,
            slab_mm=slab_mm,
            gap_mm=gap_mm,
            concrete=concrete,
            movement=movement_code,
            application=application,
            low_sleeve=low_sleeve,
        )

    original_schock = catalog.design_schock

    def design_schock_checked(
        *,
        required_vrd: float,
        slab_mm: float,
        gap_mm: float,
        movement: str = ONE_WAY,
        cover_mm: int = 30,
    ):
        return original_schock(
            required_vrd=required_vrd,
            slab_mm=slab_mm,
            gap_mm=gap_mm,
            movement=normalize_movement(movement),
            cover_mm=cover_mm,
        )

    catalog.design_ancon = design_ancon_checked
    catalog.design_schock = design_schock_checked
    ui214.design_ancon = design_ancon_checked
    ui215.design_ancon = design_ancon_checked
    ui215.design_schock = design_schock_checked

    ui214.MOVEMENTS = MOVEMENT_LABELS
    ui214._movement_code = normalize_movement
    ui214._movement_label = movement_label

    original_inline = schedule._inline_geometry

    def inline_geometry(raw: str, defaults: dict[str, str]) -> dict[str, str]:
        out = original_inline(raw, defaults)
        if _has_two_way_word(raw):
            out["movement"] = TWO_WAY_LABEL
        elif _has_one_way_word(raw):
            out["movement"] = ONE_WAY_LABEL
        return out

    schedule._inline_geometry = inline_geometry

    OriginalDialog = schedule215.ShearScheduleDialog

    class MovementScheduleDialog(OriginalDialog):
        def _build(self, title: str) -> None:
            super()._build(title)
            if self.mode != "design":
                return
            try:
                current = self.vars["movement"].get()
                self.vars["movement"].set(movement_label(current))
                movement_var = str(self.vars["movement"])
                stack = [self]
                while stack:
                    root = stack.pop()
                    children = list(root.winfo_children())
                    stack.extend(children)
                    for child in children:
                        if (
                            isinstance(child, ttk.Combobox)
                            and str(child.cget("textvariable")) == movement_var
                        ):
                            child.configure(values=MOVEMENT_LABELS, width=34)
            except Exception:
                pass

    schedule215.ShearScheduleDialog = MovementScheduleDialog
    ui214.ShearScheduleDialog = MovementScheduleDialog
    ui215.ShearScheduleDialog = MovementScheduleDialog

    original_refresh = ui215.refresh

    def refresh_with_movement_labels(self: Any) -> None:
        original_refresh(self)
        specs = (
            ("shear_decoder_tree", "shear_decoder_rows", "movement"),
            ("shear_design_tree", "shear_design_rows", "movement"),
            ("shear_substitution_tree", "shear_substitution_rows", "source"),
        )
        for tree_name, rows_name, mode in specs:
            tree = getattr(self, tree_name, None)
            rows = getattr(self, rows_name, None)
            if tree is None or not isinstance(rows, list):
                continue
            try:
                columns = list(tree["columns"])
                movement_index = columns.index("movement")
            except Exception:
                continue
            for iid in tree.get_children(""):
                try:
                    row = rows[int(iid)]
                    if mode == "source":
                        source = row.get("source") if isinstance(row, dict) else {}
                        code = source.get("movement") if isinstance(source, dict) else None
                        if not source:
                            continue
                    else:
                        code = row.get("movement") if isinstance(row, dict) else None
                    values = list(tree.item(iid, "values"))
                    if movement_index < len(values):
                        values[movement_index] = movement_label(code)
                        tree.item(iid, values=values)
                except Exception:
                    continue

    ui215.refresh = refresh_with_movement_labels
    ui214.refresh = refresh_with_movement_labels
    base_ui.refresh = refresh_with_movement_labels
    ui215._turto_movement_refresh = refresh_with_movement_labels

    original_report = ui215.report_rows

    def report_rows_with_movement(self: Any):
        reports = original_report(self)
        source_rows = {
            str(row.get("name", "")): row
            for row in getattr(self, "shear_design_rows", [])
            if isinstance(row, dict)
        }
        for report in reports:
            row = source_rows.get(str(report.get("name", "")), {})
            custom = report.setdefault("custom_actions", [])
            custom.append(
                {
                    "label": "Pohyb",
                    "value": movement_label(row.get("movement", ONE_WAY)),
                    "unit": "",
                }
            )
        return reports

    ui215.report_rows = report_rows_with_movement
    ui214.report_rows = report_rows_with_movement
    ui215._turto_movement_report_rows = report_rows_with_movement

    if app_base is not None and hasattr(app_base, "ThermalConnectorApp"):
        cls = app_base.ThermalConnectorApp
        cls.refresh_shear_tables = refresh_with_movement_labels
        cls.collect_shear_report_rows = report_rows_with_movement

    catalog._turto_movement_222_installed = True


def selftest() -> None:
    assert normalize_movement("Obousměrný") == TWO_WAY
    assert normalize_movement("dvousměrný") == TWO_WAY
    assert normalize_movement("Jednosměrný") == ONE_WAY
    assert explicit_q_variant("SLD 40 Q") == ("SLD", "40")
    assert explicit_q_variant("SLD Q 40") == ("SLD", "40")
    assert explicit_q_variant("LD 20 Q") == ("LD", "20")
    assert explicit_q_variant("HLD 22 Q") == ("HLD", "22")

    def fake_sld(_text: str):
        return {
            "manufacturer": "Schöck",
            "family": "SLD",
            "base_family": "SLD",
            "size": "40",
            "movement": ONE_WAY,
        }

    fixed = wrap_decoder(fake_sld)("SLD 40 Q")
    assert fixed["family"] == "SLD-Q"
    assert fixed["movement"] == TWO_WAY
    assert validate_ancon_application("existing_wall", TWO_WAY)
    assert not validate_ancon_application("existing_wall", ONE_WAY)


if __name__ == "__main__":
    selftest()
