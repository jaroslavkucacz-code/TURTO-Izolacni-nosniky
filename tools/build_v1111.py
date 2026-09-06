from __future__ import annotations

import base64
import lzma
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parts = sorted((ROOT / "tools").glob("build_v1111_payload.part*"))
if not parts:
    raise RuntimeError("Chybí build payload pro v1.1.11")
payload = "".join(path.read_text(encoding="ascii").strip() for path in parts)
code = lzma.decompress(base64.b85decode(payload.encode("ascii"))).decode("utf-8")
exec(compile(code, __file__ + "<payload>", "exec"), {"__name__": __name__, "__file__": __file__})
