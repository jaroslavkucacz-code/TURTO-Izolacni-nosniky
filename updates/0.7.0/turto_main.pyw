from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.pyw"
VERSION = ROOT / "version.txt"


def _inject_hit_button(source: str) -> str:
    """Přidá do stavového řádku hlavní databáze tlačítko pro nový HIT návrh.

    Úprava probíhá pouze v paměti, takže základní app.pyw zůstává beze změny.
    Pokud se v některé budoucí verzi rozložení hlavní aplikace změní, aplikace se
    stále spustí; jen se tlačítko nepřidá, dokud se neaktualizuje tento wrapper.
    """
    update_button = (
        'ttk.Button(bar, text="Aktualizace", command=self._check_updates)'
        '.grid(row=0, column=1, padx=(12, 12))'
    )
    if update_button not in source:
        return source

    hit_button = (
        'ttk.Button(bar, text="Návrh HIT", command=lambda: subprocess.Popen('
        '[sys.executable, str(Path(__file__).resolve().parent / "hit_designer.pyw")], '
        'creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))'
        '.grid(row=0, column=1, padx=(12, 6))\n        '
        'ttk.Button(bar, text="Aktualizace", command=self._check_updates)'
        '.grid(row=0, column=2, padx=(6, 12))'
    )
    source = source.replace(update_button, hit_button, 1)
    source = source.replace(
        'ttk.Label(bar, text=right, style="Status.TLabel").grid(row=0, column=2, sticky="e")',
        'ttk.Label(bar, text=right, style="Status.TLabel").grid(row=0, column=3, sticky="e")',
        1,
    )
    return source


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    try:
        version = VERSION.read_text(encoding="utf-8").strip()
    except Exception:
        version = ""
    if version:
        source = re.sub(
            r'(?m)^APP_VERSION\s*=\s*["\'][^"\']+["\']',
            f'APP_VERSION = "{version}"',
            source,
            count=1,
        )
    source = _inject_hit_button(source)
    namespace = {
        "__name__": "__main__",
        "__file__": str(APP),
        "__package__": None,
    }
    exec(compile(source, str(APP), "exec"), namespace, namespace)


if __name__ == "__main__":
    main()
