from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().with_name("build_v0612.py")
text = SOURCE.read_text(encoding="utf-8")
text = text.replace("XLSX_EXPORT = r'''", 'XLSX_EXPORT = r"""', 1)
text = text.replace("\n'''\n\n\nEXPORT_DIALOG = r'''", '\n"""\n\n\nEXPORT_DIALOG = r\'\'\'', 1)
code = compile(text, str(SOURCE), "exec")
namespace = {"__name__": "__main__", "__file__": str(SOURCE)}
exec(code, namespace, namespace)
