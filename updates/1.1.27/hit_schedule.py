from __future__ import annotations

"""TURTO ISO 1.1.27 schedule import: route supplementary rows to their own tab."""

from tkinter import messagebox

import hit_schedule_126 as _prev
from hit_schedule_126 import *  # noqa: F401,F403

AUX_TYPES = {"HT", "AT", "FT", "OTX"}


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


def _refresh_standard(owner, created) -> None:
    try:
        if hasattr(owner, "_hit_reconfigure_row_minsizes"):
            owner._hit_reconfigure_row_minsizes()
        if hasattr(owner, "_hit_schedule_virtual_refresh"):
            owner._hit_schedule_virtual_refresh()
        if hasattr(owner, "_hit_schedule_scrollregion"):
            owner._hit_schedule_scrollregion()
    except Exception:
        pass
    if created and hasattr(owner, "hit_canvas"):
        try:
            first = owner.hit_rows.index(created[0]) + 1
            total = max(1, len(owner.hit_rows))
            owner.hit_canvas.yview_moveto(max(0.0, min(1.0, (first - 2) / total)))
            if hasattr(owner, "_hit_schedule_virtual_refresh"):
                owner._hit_schedule_virtual_refresh()
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
        messagebox.showinfo("Není co vložit", "Nejprve vložte výkaz a použijte „Načíst náhled“.", parent=self)
        return
    if not self.included:
        messagebox.showinfo("Není vybraná žádná pozice", "Zahrňte alespoň jednu pozici.", parent=self)
        return

    missing = sorted(i for i in self.included if i not in self.payloads)
    if missing:
        _select_problem(self, missing)
        lines = ", ".join(str(self.records[i].line) for i in missing[:12] if 0 <= i < len(self.records))
        messagebox.showwarning(
            "Některé pozice nejsou připravené",
            f"{len(missing)} zahrnutých pozic má nevyřešenou chybu nebo neplatné parametry.\n\n"
            f"Řádky výkazu: {lines}{'…' if len(missing) > 12 else ''}",
            parent=self,
        )
        return
    if not self.ack.get():
        messagebox.showwarning(
            "Potvrďte přiřazení",
            "Před vložením zaškrtněte potvrzení přiřazení MEd/VEd/HEd a jednotek.",
            parent=self,
        )
        return

    replace_existing = bool(self.replace.get())
    if replace_existing and (getattr(self.owner, "hit_rows", None) or getattr(self.owner, "aux_rows", None)):
        if not messagebox.askyesno(
            "Nahradit zadání HIT",
            "Nahradit dosavadní řádky Desky / balkony a Doplňkové prvky?\n\n"
            "Stěny WT, Dekodér ISO a Záměny za HIT zůstanou beze změny.",
            parent=self,
        ):
            return

    values = [self.payloads[i] for i in sorted(self.included)]
    standard_values = [v for v in values if str(v.get("connection_type", "")).upper() not in AUX_TYPES]
    aux_values = [v for v in values if str(v.get("connection_type", "")).upper() in AUX_TYPES]
    created_standard = []
    created_aux = []

    try:
        if replace_existing:
            if hasattr(self.owner, "clear_aux_rows"):
                self.owner.clear_aux_rows(mark_dirty=False)
            if not standard_values and hasattr(self.owner, "clear_hit_rows"):
                self.owner.clear_hit_rows()

        if standard_values:
            created_standard = _prev._prev.install_rows(self.owner, standard_values, replace_existing)
            _refresh_standard(self.owner, created_standard)
        if aux_values:
            if not hasattr(self.owner, "import_aux_defaults"):
                raise RuntimeError("Doplňková část Návrhu HIT není dostupná.")
            created_aux = self.owner.import_aux_defaults(aux_values)

        if hasattr(self.owner, "mark_project_dirty"):
            self.owner.mark_project_dirty()
        self.owner.update_idletasks()
    except Exception as exc:
        messagebox.showerror(
            "Import HIT",
            "Import se nezdařil.\n\n" + str(exc),
            parent=self,
        )
        return

    created = len(created_standard) + len(created_aux)
    if not created:
        messagebox.showwarning("Import HIT", "Import nevrátil žádný nový řádek.", parent=self)
        return

    try:
        if created_standard and hasattr(self.owner, "hit_standard_tab"):
            self.owner.hit_design_notebook.select(self.owner.hit_standard_tab)
        elif created_aux and hasattr(self.owner, "hit_aux_tab"):
            self.owner.hit_design_notebook.select(self.owner.hit_aux_tab)
    except Exception:
        pass

    total_qty = 0
    for payload in values:
        try:
            total_qty += int(payload.get("quantity", 1) or 1)
        except Exception:
            total_qty += 1

    try:
        self.owner.hit_status_var.set(
            f"Importováno {created} řádků / {total_qty} ks • "
            f"desky {len(created_standard)} • doplňky {len(created_aux)}."
        )
        self.owner.set_status(
            f"Do Návrhu HIT bylo vloženo {created} řádků ({total_qty} ks). Uložte AKCI."
        )
    except Exception:
        pass
    self.destroy()


_prev.HitScheduleDialog.commit = _commit

HitScheduleDialog = _prev.HitScheduleDialog
ScheduleRecord = _prev.ScheduleRecord
required_length_codes = _prev.required_length_codes
