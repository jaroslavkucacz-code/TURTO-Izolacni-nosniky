from __future__ import annotations

"""Stabilní veřejná hranice pracovního prostoru smykových trnů.

Aktuální ověřená implementace zůstává kvůli zpětné kompatibilitě ve
verzovaném modulu 2.1.5. Zbytek aplikace od TURTO 2.2.0 importuje pouze
tento modul, takže další úpravy už nevyžadují přepisování celé platformy.
"""

from shear_dowels_ui_215 import build_shear_workspace, init_shear_workspace, install_methods

__all__ = ("build_shear_workspace", "init_shear_workspace", "install_methods")
