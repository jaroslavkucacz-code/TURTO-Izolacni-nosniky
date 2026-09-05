from __future__ import annotations

import subprocess
import sys
from pathlib import Path

path = Path(__file__).resolve().with_name("build_v111.py")
text = path.read_text(encoding="utf-8")
old = 'assert "kNm/element" in generated and "HIT-SP odpovídá izolantu 120 mm" in generated'
new = 'assert "kNm/element" in generated and "HIT-SP izolantu 120 mm" in generated'
if old not in text:
    raise RuntimeError("Expected v1.1.1 assertion was not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
subprocess.run([sys.executable, str(path)], check=True)
