from __future__ import annotations

"""Regression check for TURTO 2.2.38 PDF vector-logo repair."""

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "updates" / "2.2.38"
GUARD = RELEASE / "pdf_logo_guard_238.py"
RUNTIME = RELEASE / "app_runtime.pyw"
INSTALLER = RELEASE / "runtime_installer.py"
BOOTSTRAP = RELEASE / "app.pyw"


def _load_guard():
    spec = importlib.util.spec_from_file_location("turto_pdf_logo_guard_238", GUARD)
    if spec is None or spec.loader is None:
        raise RuntimeError("Nelze načíst pdf_logo_guard_238.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    for path in (GUARD, RUNTIME, INSTALLER, BOOTSTRAP):
        assert path.is_file(), f"Chybí {path.relative_to(ROOT)}"

    guard = _load_guard()
    guard.selftest()

    with tempfile.TemporaryDirectory(prefix="turto_pdf_logo_2238_") as folder:
        program = Path(folder) / "Program"
        target = program / "assets" / "turto_logo_vector.json"

        created = guard.ensure_logo(program)
        assert created == target and target.is_file()
        first = target.read_bytes()
        data = json.loads(first.decode("utf-8"))
        assert data["width"] == 942 and data["height"] == 849 and data["shapes"]

        target.write_text("{broken", encoding="utf-8")
        repaired = guard.ensure_logo(program)
        assert repaired == target
        assert target.read_bytes() == first, "Poškozené logo nebylo deterministicky obnoveno"

        target.unlink()
        guard.ensure_logo(program)
        assert target.read_bytes() == first, "Chybějící logo nebylo znovu vytvořeno"

    runtime = RUNTIME.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")

    assert 'APP_VERSION = "2.2.38"' in runtime
    assert 'app_runtime_237.pyw' in runtime
    assert 'pdf_logo_guard_238.ensure_logo(PROGRAM)' in runtime
    assert '_turto_shear_substitution_237' in runtime

    assert 'VERSION = "2.2.38"' in installer
    assert 'RUNTIME_LAYOUT = "22"' in installer
    assert '"pdf_logo_guard_238.py"' in installer
    assert 'actions.sqlite3' in installer
    assert 'ensure_logo(program)' in installer

    assert 'VERSION = "2.2.38"' in bootstrap
    assert 'RUNTIME_LAYOUT = "22"' in bootstrap
    assert 'updates/2.2.38/runtime_installer.py' in bootstrap

    print(
        "TURTO 2.2.38 PDF logo repair OK; vector JSON sha256="
        + hashlib.sha256(first).hexdigest()
    )


if __name__ == "__main__":
    main()
