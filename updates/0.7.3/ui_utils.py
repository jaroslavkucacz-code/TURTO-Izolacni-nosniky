from __future__ import annotations

from typing import Any


def place_dialog_on_parent(dialog: Any, parent: Any) -> None:
    """Umístí dialog nad rodičovské okno, tedy na stejný monitor.

    Zachová velikost nastavenou pomocí geometry()/minsize(). Souřadnice mohou být
    záporné, což je důležité pro monitory vlevo nebo nad primárním monitorem.
    Volání je odloženo přes after_idle, aby už Tk znal skutečnou velikost oken.
    """
    def _place() -> None:
        try:
            parent.update_idletasks()
            dialog.update_idletasks()

            width = int(dialog.winfo_width())
            height = int(dialog.winfo_height())
            if width <= 1:
                width = max(1, int(dialog.winfo_reqwidth()))
            if height <= 1:
                height = max(1, int(dialog.winfo_reqheight()))

            parent_x = int(parent.winfo_rootx())
            parent_y = int(parent.winfo_rooty())
            parent_w = max(1, int(parent.winfo_width()))
            parent_h = max(1, int(parent.winfo_height()))

            x = parent_x + (parent_w - width) // 2
            y = parent_y + (parent_h - height) // 2
            dialog.geometry(f"{width}x{height}{x:+d}{y:+d}")
            dialog.lift(parent)
        except Exception:
            # Umístění dialogu nesmí nikdy zablokovat jeho otevření.
            pass

    try:
        dialog.after_idle(_place)
    except Exception:
        pass
