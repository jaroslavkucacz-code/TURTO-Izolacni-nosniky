from __future__ import annotations

import hashlib
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates/2.2.37"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    sys.path.insert(0, str(ROOT / "updates/2.1.0"))
    module = runpy.run_path(str(RELEASE / "shear_substitution_237.py"))
    evaluate = module["evaluate"]

    def base(values, target_manufacturer):
        result = dict(values)
        result.update(
            target_manufacturer=target_manufacturer,
            source={
                "manufacturer": "Leviat / HALFEN",
                "designation": "HSD-CRET 140",
                "family": "HSD-CRET",
                "size": "140",
                "vrd": 347.0,
                "movement": "axial",
            },
            target={},
            status="NELZE",
            error="strict 1:1 target not found",
        )
        return result

    common = {
        "name": "S005",
        "source_designation": "CRET 140",
        "slab_mm": 350.0,
        "gap_mm": 20.0,
        "concrete": "C30/37",
        "cover_mm": 30,
        "low_sleeve": "stainless",
    }

    catalog = evaluate({**common, "verification_mode": "catalog"}, "Ancon", base)
    assert catalog["status"] == "OVĚŘIT VEd", catalog
    assert catalog["target"]["designation"] == "Ancon HLD 42", catalog
    assert catalog["target"]["vrd"] == 334.0, catalog
    assert catalog["target"]["slab_table_mm"] == 350, catalog
    assert catalog["target"]["gap_table_mm"] == 20, catalog
    assert abs(catalog["capacity_ratio"] - 334.0 / 347.0) < 1e-12, catalog
    assert "96.3 %" in catalog["target"]["note"], catalog
    assert "nejsou interpolovány" in catalog["target"]["note"], catalog

    ved_ok = evaluate({**common, "verification_mode": "ved", "ved": 320.0}, "Ancon", base)
    assert ved_ok["status"] == "VYHOVUJE dle VEd", ved_ok
    assert ved_ok["target"]["designation"] == "Ancon HLD 42", ved_ok
    assert ved_ok["target"]["vrd"] == 334.0, ved_ok
    assert abs(ved_ok["target"]["utilization"] - 320.0 / 334.0) < 1e-12, ved_ok

    ved_limit = evaluate({**common, "verification_mode": "ved", "ved": 334.0}, "Ancon", base)
    assert ved_limit["status"] == "VYHOVUJE dle VEd", ved_limit
    assert ved_limit["target"]["vrd"] == 334.0, ved_limit

    ved_fail = evaluate({**common, "verification_mode": "ved", "ved": 340.0}, "Ancon", base)
    assert ved_fail["status"] == "NELZE dle VEd", ved_fail
    assert ved_fail["target"]["designation"] == "Ancon HLD 42", ved_fail
    assert ved_fail["target"]["vrd"] == 334.0, ved_fail

    missing = evaluate({**common, "verification_mode": "ved", "ved": ""}, "Ancon", base)
    assert missing["status"] == "CHYBÍ VEd", missing
    assert not missing["target"], missing

    print("2.2.37 substitution regression: PASS")
    print("PAYLOAD shear_substitution_237.py", _sha(RELEASE / "shear_substitution_237.py"))
    print("PAYLOAD app_runtime.pyw", _sha(RELEASE / "app_runtime.pyw"))


if __name__ == "__main__":
    main()
