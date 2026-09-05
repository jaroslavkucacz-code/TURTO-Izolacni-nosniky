from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "build_v112.py"

spec = importlib.util.spec_from_file_location("turto_build_v112", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError("Nelze načíst build_v112.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

helper = r'''def _direction_requirement(actions: DirectionalActions, prefix: str) -> tuple[str, float]:
    a = actions.normalized()
    pos = float(getattr(a, prefix + "_pos"))
    neg = float(getattr(a, prefix + "_neg"))
    symbol = prefix.upper()
    if pos > _TOL and neg > _TOL:
        label = symbol + ("±" if abs(pos - neg) <= _TOL else "+/−")
        return label, max(pos, neg)
    if pos > _TOL:
        return symbol + "+", pos
    if neg > _TOL:
        return symbol + "−", neg
    return symbol, 0.0


'''
marker = "def calculation(\n"
if marker not in module.CAPACITY_AND_DESIGN:
    raise RuntimeError("Marker pro _direction_requirement nebyl nalezen")
module.CAPACITY_AND_DESIGN = module.CAPACITY_AND_DESIGN.replace(marker, helper + marker, 1)
module.main()
