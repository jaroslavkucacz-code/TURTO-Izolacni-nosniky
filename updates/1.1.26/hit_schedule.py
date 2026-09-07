from __future__ import annotations

"""TURTO ISO 1.1.26 – robust schedule-import commit path.

The 1.1.22 parser/preview remains unchanged.  This layer removes silent no-op
branches from the final "Přidat do návrhu HIT" action and explicitly refreshes
the virtualized HIT grid after constructing imported rows.
"""

from typing import Any
from tkinter import messagebox

import hit_schedule_prev as _prev
from hit_schedule_prev import *  # noqa: F401,F403

_ORIGINAL_RENDER = _prev.HitScheduleDialog.render


def _render(self) -> None:
    _ORIGINAL_RENDER(self)
    # A disabled button produced no feedback at all.  Once a preview exists,
    # keep the action clickable and let commit() explain the exact blocker.
    try:
        if self.records and self.included:
            self.import_button.configure(state="normal")
            missing = [i for i in self.included if i not in self.payloads]
            if missing:
                self.import_button.configure(
                    text=f"Přidat do návrhu HIT ({len(self.included)}) – vyřešit chyby"
                )
            elif not self.ack.get():
                self.import_button.configure(
                    text=f"Přidat do návrhu HIT ({len(self.included)}) – potvrdit přiřazení"
                )
            else:
                self.import_button.configure(text=f"Přidat do návrhu HIT ({len(self.included)})")
    except Exception:
        pass


def _select_problem(self, indices: list[int]) -> None:
    if not indices:
        return
    iid = str(indices[0])
    try:
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
            self.show_source()
    except Exception:
        pass


def _refresh_after_import(owner: Any, created: list[Any]) -> None:
    try:
        if hasattr(owner, "_hit_reconfigure_row_minsizes"):
            owner._hit_reconfigure_row_minsizes()
        if hasattr(owner, "_hit_schedule_virtual_refresh"):
            owner._hit_schedule_virtual_refresh()
        if hasattr(owner, "_hit_schedule_scrollregion"):
            owner._hit_schedule_scrollregion()
    except Exception:
        pass

    # Show the first imported row.  This is especially important when rows are
    # appended to a long virtualized table – otherwise the import can succeed
    # while the user still sees the old viewport and reasonably thinks nothing
    # happened.
    if created and hasattr(owner, "hit_canvas"):
        try:
            first = owner.hit_rows.index(created[0]) + 1
            total = max(1, len(owner.hit_rows))
            fraction = max(0.0, min(1.0, (first - 2) / total))
            owner.hit_canvas.yview_moveto(fraction)
            if hasattr(owner, "_hit_schedule_virtual_refresh"):
                owner._hit_schedule_virtual_refresh()
        except Exception:
            pass

    try:
        owner.update_idletasks()
    except Exception:
        pass


def _commit(self) -> None:
    current_text = self.text.get("1.0", "end-1c")
    if current_text != self.last_text:
        self.analyze()
        messagebox.showinfo(
            "Výkaz se změnil",
            "Náhled byl obnoven. Zkontrolujte jej a znovu potvrďte přiřazení typů a směrů.",
            parent=self,
        )
        return

    if not self.records:
        messagebox.showinfo(
            "Není co vložit",
            "Nejprve vložte výkaz a použijte „Načíst náhled“.",
            parent=self,
        )
        return

    if not self.included:
        messagebox.showinfo(
            "Není vybraná žádná pozice",
            "Zahrňte alespoň jednu pozici, kterou chcete přidat do Návrhu HIT.",
            parent=self,
        )
        return

    missing = sorted(i for i in self.included if i not in self.payloads)
    if missing:
        _select_problem(self, missing)
        lines = ", ".join(str(self.records[i].line) for i in missing[:12] if 0 <= i < len(self.records))
        suffix = "…" if len(missing) > 12 else ""
        messagebox.showwarning(
            "Některé pozice nejsou připravené",
            f"{len(missing)} zahrnutých pozic má nevyřešenou chybu nebo neplatné parametry.\n\n"
            f"Řádky výkazu: {lines}{suffix}\n\n"
            "Opravte zvýrazněnou pozici nebo ji vynechte. Potom lze import dokončit.",
            parent=self,
        )
        return

    if not self.ack.get():
        messagebox.showwarning(
            "Potvrďte přiřazení",
            "Před vložením zaškrtněte potvrzení, že přiřazení MEd/VEd/HEd a jejich jednotek odpovídá skutečnému zadání.\n\n"
            "Po zaškrtnutí zůstane náhled beze změny a můžete import dokončit.",
            parent=self,
        )
        return

    replace_existing = bool(self.replace.get())
    if replace_existing and self.owner.hit_rows:
        if not messagebox.askyesno(
            "Nahradit zadání HIT",
            "Nahradit dosavadní řádky Návrhu HIT?\n\n"
            "Dekodér ISO, Záměny za HIT ani ostatní data AKCE se tím nemažou.",
            parent=self,
        ):
            return

    values = [self.payloads[i] for i in sorted(self.included)]
    before_count = len(getattr(self.owner, "hit_rows", []))
    try:
        created = _prev.install_rows(self.owner, values, replace_existing)
        _refresh_after_import(self.owner, created)
        # Direct row construction bypasses the ordinary +Přidat řádek hook.
        # Mark the central AKCE dirty even when replacement keeps the same count.
        if hasattr(self.owner, "mark_project_dirty"):
            self.owner.mark_project_dirty()
    except Exception as exc:
        messagebox.showerror(
            "Import HIT",
            "Import se nezdařil. Dosavadní řádky byly zachovány, pokud selhalo vytváření nových řádků.\n\n" + str(exc),
            parent=self,
        )
        return

    if not created:
        messagebox.showwarning(
            "Import HIT",
            "Import nevrátil žádný nový řádek. Návrh HIT nebyl změněn.",
            parent=self,
        )
        return

    try:
        if hasattr(self.owner, "hit_design_notebook") and hasattr(self.owner, "hit_standard_tab"):
            self.owner.hit_design_notebook.select(self.owner.hit_standard_tab)
    except Exception:
        pass

    total_qty = 0
    for payload in values:
        try:
            total_qty += int(payload.get("quantity", 1) or 1)
        except Exception:
            total_qty += 1
    after_count = len(getattr(self.owner, "hit_rows", []))
    try:
        self.owner.hit_status_var.set(
            f"Importováno {len(created)} řádků / {total_qty} ks • Návrh HIT má nyní {after_count} řádků."
        )
        self.owner.set_status(
            f"Do Návrhu HIT bylo vloženo {len(created)} řádků ({total_qty} ks). Uložte AKCI."
        )
    except Exception:
        pass

    # Keep an explicit success signal before closing the modal dialog.
    self.destroy()


_prev.HitScheduleDialog.render = _render
_prev.HitScheduleDialog.commit = _commit
HitScheduleDialog = _prev.HitScheduleDialog
ScheduleRecord = _prev.ScheduleRecord
required_length_codes = _prev.required_length_codes
