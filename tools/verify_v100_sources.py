from __future__ import annotations

import base64
import gzip
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / "updates" / "1.0.0"
DOP_URL = "https://www.leviat.com/nl-nl/mwdownloads/download/link/id/471.pdf"


def main() -> None:
    sys.path.insert(0, str(UPDATE))
    import hit_core as hc

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pdf = tmp / "CONF-DOP_HIT-HP_SP_07-23-E.pdf"
        response = requests.get(DOP_URL, timeout=90)
        response.raise_for_status()
        pdf.write_bytes(response.content)
        assert pdf.read_bytes()[:4] == b"%PDF"

        db_path = tmp / hc.DATA_FILENAME
        payload = hc.build_database_from_pdf(pdf, db_path)
        assert int(payload["schema_version"]) == 4
        assert len(payload.get("mvxl_records", [])) >= 90

        # Annex 2 must actually contribute the OD table family. The DoP labels
        # the same values as applicable to WD in parentheses; WD is therefore
        # generated as the structural mirror of the verified OD records.
        annex2_heads = []
        for heads, rows, page in payload.get("sections", []):
            if int(page) >= 55:
                annex2_heads.extend(heads)
        assert annex2_heads, "Annex 2 did not produce any MVX sections"
        assert any(head.endswith("-OD") for head in annex2_heads), "No MVX-OD from Annex 2"

        db = hc.HitDatabase(db_path)
        assert set(("MVX", "MVXL", "ZVX", "ZDX", "DD", "DVL", "DDL", "AT", "FT", "OTX")).issubset(set(db.available_connection_types))
        suffixes = Counter(str(row[3]) for row in db.records)
        for suffix in ("OD", "WD", "OU", "WU"):
            assert suffixes[suffix] > 0, f"Missing structural offset variant {suffix}"
        assert suffixes["WD"] == suffixes["OD"], "WD must mirror the complete verified OD record set"

        raw = gzip.decompress(base64.b64decode(db_path.read_text(encoding="ascii").strip()))
        decoded = json.loads(raw.decode("utf-8"))
        assert decoded["catalog_id"].endswith("_v4")
        print("DoP verified:", len(payload["sections"]), "MVX sections; offsets", dict(suffixes))


if __name__ == "__main__":
    main()
