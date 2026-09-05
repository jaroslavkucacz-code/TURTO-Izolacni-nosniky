from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
build_path = Path(__file__).resolve().with_name("build_v111.py")
template_path = Path(__file__).resolve().with_name("v111_substitution_workspace.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)


# Opravíme pouze interní statickou kontrolu buildu; výsledný program se nemění.
build_text = build_path.read_text(encoding="utf-8")
build_text = replace_once(
    build_text,
    'assert "kNm/element" in generated and "HIT-SP odpovídá izolantu 120 mm" in generated',
    'assert "KNM/ELEMENT" in generated and "HIT-SP izolantu 120 mm" in generated',
    "generated-module assertion",
)
build_path.write_text(build_text, encoding="utf-8")

# Tabulka uživatele je vstupní vodítko, nikoli neověřená tvrdá záměna. Pro známé
# třídy Egcobox MXL vytvoříme odhad kódu HIT, ale každý takový odhad musí ještě
# projít skutečnou kontrolou kapacitami a interakční obálkou z DoP.
template = template_path.read_text(encoding="utf-8")
marker = '\n\ndef _capacity_values(candidate: Candidate) -> tuple[float, float, float]:\n'
helper = '''

_EGCOBOX_MOMENT_CODE = {"20": "04", "25": "05", "35": "07", "50": "08"}


def _egcobox_estimated_type(metadata: dict[str, Any]) -> str:
    source = str(metadata.get("source_text") or metadata.get("canonical_designation") or "").upper()
    manufacturer = str(metadata.get("manufacturer", "")).upper()
    if "EGCOBOX" not in source and "MAX FRANK" not in manufacturer:
        return ""
    moment = re.search(r"\\bMXL\\s*(20|25|35|50)(?:-K)?(?:-|\\b)", source)
    if not moment:
        return ""
    xx = _EGCOBOX_MOMENT_CODE.get(moment.group(1), "")
    cover = int(metadata.get("target_cover_mm") or 0)
    yy = ""
    if re.search(r"-V6(?:±|\\+/-|\\+-)?(?:-|\\b)", source) or re.search(r"-VS(?:-|\\b)", source):
        yy = "04"
    elif re.search(r"-V1(?:-|\\b)", source):
        yy = "06" if cover == 30 else ("05" if cover == 50 else "")
    elif re.search(r"-V2(?:-|\\b)", source):
        yy = "07" if cover == 50 else ""
    if not xx or not yy:
        return ""
    estimate = f"MVX-{xx}{yy}"
    geometry = str(metadata.get("geometry_target", ""))
    bx = int(metadata.get("geometry_bx_mm") or 0)
    if geometry and bx:
        estimate += f"-{geometry}{bx}"
    return estimate


def estimated_hit_type(metadata: dict[str, Any], actions: DirectionalActions) -> str:
    specific = _egcobox_estimated_type(metadata)
    if specific:
        return specific
    order = hit_type_order(
        actions,
        int(metadata.get("target_cover_mm") or 0),
        str(metadata.get("geometry_target", "")),
    )
    return order[0] if order else ""


def _designation_matches_estimate(designation: str, estimate: str) -> bool:
    match = re.search(r"MVX-(\\d{4})", str(estimate).upper())
    if not match:
        return False
    if f"MVX-{match.group(1)}-" not in str(designation).upper():
        return False
    geometry = re.search(r"-(OU|OD)(\\d+)$", str(estimate).upper())
    return not geometry or str(designation).upper().endswith(f"-{geometry.group(1)}{geometry.group(2)}")
'''
template = replace_once(template, marker, helper + marker, "Egcobox estimate helpers")

old_rank = '''def _candidate_rank(candidate: Candidate, actions: DirectionalActions, type_order: tuple[str, ...]) -> tuple[Any, ...]:
    try:
        type_index: float = float(type_order.index(candidate.connection_type))
    except ValueError:
        # MVXL je bezpečný fallback rodiny MVX.
        type_index = float(type_order.index("MVX")) + 0.5 if candidate.connection_type == "MVXL" and "MVX" in type_order else 99.0
    xx, yy = _code_parts(candidate)
    if xx < 999:
        reinforcement = (xx + yy, yy, xx)
    else:
        reinforcement = (1998, yy, xx)
    return (type_index, *reinforcement, -_overall_utilization(candidate, actions), candidate.designation)
'''
new_rank = '''def _candidate_rank(
    candidate: Candidate,
    actions: DirectionalActions,
    type_order: tuple[str, ...],
    estimated_type: str = "",
) -> tuple[Any, ...]:
    try:
        type_index: float = float(type_order.index(candidate.connection_type))
    except ValueError:
        # MVXL je bezpečný fallback rodiny MVX.
        type_index = float(type_order.index("MVX")) + 0.5 if candidate.connection_type == "MVXL" and "MVX" in type_order else 99.0
    estimate_rank = 0 if _designation_matches_estimate(candidate.designation, estimated_type) else 1
    xx, yy = _code_parts(candidate)
    if xx < 999:
        reinforcement = (xx + yy, yy, xx)
    else:
        reinforcement = (1998, yy, xx)
    return (estimate_rank, type_index, *reinforcement, -_overall_utilization(candidate, actions), candidate.designation)
'''
template = replace_once(template, old_rank, new_rank, "candidate estimate ranking")

template = replace_once(
    template,
    '    order = hit_type_order(actions, cover, geometry_target)\n    errors: list[str] = []\n',
    '    order = hit_type_order(actions, cover, geometry_target)\n'
    '    estimate = estimated_hit_type(metadata, actions)\n'
    '    errors: list[str] = []\n',
    "design estimate",
)
template = replace_once(
    template,
    '    rows.sort(key=lambda item: _candidate_rank(item[0], actions, order))\n',
    '    rows.sort(key=lambda item: _candidate_rank(item[0], actions, order, estimate))\n',
    "design estimate sort",
)

template = replace_once(
    template,
    '            order = hit_type_order(actions, int(meta.get("target_cover_mm") or 0), str(meta.get("geometry_target", ""))) if not fatal else ()\n',
    '            estimate = estimated_hit_type(meta, actions) if not fatal else ""\n'
    '            order = hit_type_order(actions, int(meta.get("target_cover_mm") or 0), str(meta.get("geometry_target", ""))) if not fatal else ()\n',
    "row estimate",
)
template = replace_once(
    template,
    '                    "source_meta": meta, "warnings": action_warnings, "errors": fatal, "estimated_type": "",\n',
    '                    "source_meta": meta, "warnings": action_warnings, "errors": fatal, "estimated_type": estimate,\n',
    "fatal estimate",
)
template = replace_once(
    template,
    '                    "source_meta": meta, "warnings": action_warnings, "errors": errors, "estimated_type": order[0],\n',
    '                    "source_meta": meta, "warnings": action_warnings, "errors": errors, "estimated_type": estimate or order[0],\n',
    "failed estimate",
)
template = replace_once(
    template,
    '            warnings = list(dict.fromkeys([*action_warnings, *meta.get("warnings", [])]))\n            row["mapping"] = {\n',
    '            warnings = list(dict.fromkeys([*action_warnings, *meta.get("warnings", [])]))\n'
    '            if estimate.startswith("MVX-") and not _designation_matches_estimate(str(targets[0].get("designation", "")), estimate):\n'
    '                warnings.append(f"odhad {estimate} nebyl staticky použitelný; použita nejbližší vyhovující varianta")\n'
    '            row["mapping"] = {\n',
    "estimate fallback warning",
)
template = replace_once(
    template,
    '                "estimated_type": order[0],\n',
    '                "estimated_type": estimate or order[0],\n',
    "success estimate",
)
template_path.write_text(template, encoding="utf-8")

subprocess.run([sys.executable, str(build_path)], check=True)
