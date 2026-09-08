from __future__ import annotations

"""TURTO 2.1.5 – výkaz smykových trnů bez zbytečné volby cnom v Dekodéru."""

from tkinter import ttk

import shear_dowels_schedule as _prev


class ShearScheduleDialog(_prev.ShearScheduleDialog):
    def _build(self, title: str) -> None:
        super()._build(title)
        if self.mode != "decoder":
            return

        # Archivní SLD rozlišuje také C20/25. Dekodér proto může pracovat
        # s touto třídou, i když návrhový katalog Ancon začíná na C25/30.
        concrete_var = str(self.vars["concrete"])
        stack = [self]
        while stack:
            root = stack.pop()
            try:
                children = list(root.winfo_children())
            except Exception:
                continue
            stack.extend(children)
            for child in children:
                try:
                    if isinstance(child, ttk.Combobox) and str(child.cget("textvariable")) == concrete_var:
                        child.configure(values=("C20/25", "C25/30", "C30/37", "C35/45", "C40/50"))
                except Exception:
                    pass

        # Krytí není vstupem Dekodéru. U archivních Dorn je referenční cnom
        # vlastností zdrojové tabulky (SLD 30 mm, LD 20 mm); u záměny se krytí
        # cílového Schöck zadává až v kartě Záměny.
        for widget in self.winfo_children():
            pass
        stack = [self]
        for root in stack:
            try:
                children = list(root.winfo_children())
            except Exception:
                continue
            stack.extend(children)
            for child in children:
                try:
                    if isinstance(child, ttk.Label) and str(child.cget("text")) == "cnom Schöck":
                        info = child.grid_info()
                        row = int(info.get("row", 0))
                        column = int(info.get("column", 0))
                        parent = child.master
                        child.grid_remove()
                        for sibling in parent.winfo_children():
                            if sibling is child:
                                continue
                            try:
                                sinfo = sibling.grid_info()
                                if int(sinfo.get("row", -1)) == row and int(sinfo.get("column", -1)) == column + 1:
                                    sibling.grid_remove()
                                    break
                            except Exception:
                                pass
                        return
                except Exception:
                    pass


ScheduleItem = _prev.ScheduleItem
parse_decoder_schedule = _prev.parse_decoder_schedule
parse_design_schedule = _prev.parse_design_schedule
