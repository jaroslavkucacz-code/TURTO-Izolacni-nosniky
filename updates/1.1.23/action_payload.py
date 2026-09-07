from __future__ import annotations

"""Serialize/load/save one complete TURTO ISO AKCE."""

from pathlib import Path
from typing import Any
from tkinter import messagebox, simpledialog

from action_store import ActionStore
from project_model import ProjectDocument
from hit_design_ui import serialize_hit_design, _load_design_record
import hit_workspace as _hit_workspace_module


def action_store(owner: Any) -> ActionStore:
    return ActionStore(Path(owner.settings_path).resolve().parent / "actions.sqlite3")


def serialize_action(owner: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "application": "TURTO ISO",
        "action_name": owner.project_name_var.get().strip() or owner.project.name or "Nová akce",
        "project": owner.project.to_dict(),
        "hit_design": serialize_hit_design(owner),
    }


def _clear_hit_rows(owner: Any) -> None:
    for row in list(getattr(owner, "hit_rows", [])):
        try:
            row.destroy()
        except Exception:
            pass
    owner.hit_rows.clear()
    if getattr(owner, "_hit_built", False):
        owner.add_hit_row()
    owner.hit_design_id = None
    owner.hit_design_action = ""
    owner.hit_design_name = ""


def _set_project(owner: Any, document: ProjectDocument) -> None:
    document.path = None
    owner.project = document
    owner.project_edit_row_id = None
    owner.project_sort_column = None
    owner.project_sort_reverse = False
    owner._project_var_guard = True
    try:
        owner.project_name_var.set(document.name)
        owner.project_concrete_var.set(getattr(document, "concrete_class", "C25/30") or "C25/30")
        owner.project_filter_var.set("")
    finally:
        owner._project_var_guard = False
    try:
        owner.cancel_project_row_edit()
    except Exception:
        pass
    owner.refresh_project_tree()


def load_action_record(owner: Any, record: dict[str, Any]) -> None:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    raw = payload.get("project") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        raise ValueError("Uložené AKCI chybí data Dekodéru ISO.")
    document = ProjectDocument.from_dict(raw)
    document.name = str(record.get("action_name") or document.name or "AKCE")
    owner._action_loading = True
    try:
        _set_project(owner, document)
        hit_payload = payload.get("hit_design") if isinstance(payload.get("hit_design"), dict) else {
            "schema_version": 1, "lengths": [100, 50], "rows": []
        }
        if getattr(owner, "_hit_built", False):
            _load_design_record(owner, _hit_workspace_module, {
                "id": "", "action_name": document.name,
                "design_name": "Návrh HIT", "payload": hit_payload,
            })
        owner.hit_design_id = None
        owner.hit_design_action = ""
        owner.hit_design_name = ""
        owner.action_id = str(record.get("id") or "") or None
        owner.action_created_at = str(record.get("created_at") or "")
        owner.action_updated_at = str(record.get("updated_at") or "")
        owner.project_dirty = False
        owner.project.path = None
        if hasattr(owner, "refresh_substitution_tree"):
            owner.refresh_substitution_tree()
        owner._update_action_info()
        owner._update_project_title()
    finally:
        owner._action_loading = False
    owner.set_status(
        f"Načtena AKCE {document.name} • {len(document.rows)} řádků Dekodéru ISO • "
        f"{len(getattr(owner, 'hit_rows', []))} řádků Návrhu HIT."
    )


def save_action(owner: Any, *, as_new: bool = False, forced_name: str | None = None) -> bool:
    name = str(forced_name or owner.project_name_var.get() or owner.project.name or "").strip()
    if not name or name in {"Nový objekt", "Nová akce"}:
        asked = simpledialog.askstring(
            "Uložit AKCI", "Název AKCE:",
            initialvalue="" if name in {"Nový objekt", "Nová akce"} else name,
            parent=owner,
        )
        if asked is None:
            return False
        name = asked.strip()
    if not name:
        messagebox.showwarning("Uložit AKCI", "Název AKCE nesmí být prázdný.", parent=owner)
        return False
    owner._action_loading = True
    try:
        owner.project.name = name
        owner.project_name_var.set(name)
        saved = action_store(owner).save(
            action_name=name,
            payload=serialize_action(owner),
            action_id=None if as_new else getattr(owner, "action_id", None),
        )
        owner.action_id = str(saved["id"])
        owner.action_created_at = str(saved["created_at"])
        owner.action_updated_at = str(saved["updated_at"])
        owner.project.path = None
        owner.project_dirty = False
        owner.hit_design_id = None
        owner.hit_design_action = ""
        owner.hit_design_name = ""
    except Exception as exc:
        messagebox.showerror("AKCI se nepodařilo uložit", str(exc), parent=owner)
        return False
    finally:
        owner._action_loading = False
    owner._update_project_title()
    owner._update_action_info()
    owner.set_status(
        f"AKCE „{name}“ uložena do centrální databáze "
        f"({saved['decoder_count']} dekódovaných řádků, {saved['hit_count']} řádků Návrhu HIT)."
    )
    return True


def save_action_as_new(owner: Any) -> bool:
    current = owner.project_name_var.get().strip() or owner.project.name or "AKCE"
    name = simpledialog.askstring(
        "Uložit AKCI jako", "Název nové AKCE:",
        initialvalue=current + " – kopie", parent=owner,
    )
    return bool(name and save_action(owner, as_new=True, forced_name=name.strip()))


def confirm_action_close(owner: Any) -> bool:
    if not getattr(owner, "project_dirty", False):
        return True
    name = owner.project_name_var.get().strip() or "AKCE"
    answer = messagebox.askyesnocancel(
        "Neuložené změny",
        f"AKCE „{name}“ obsahuje neuložené změny. Chcete uložit celou AKCI?",
        parent=owner,
    )
    if answer is None:
        return False
    return save_action(owner) if answer else True


def new_action(owner: Any) -> None:
    if not confirm_action_close(owner):
        return
    owner._action_loading = True
    try:
        owner.action_id = None
        owner.action_created_at = ""
        owner.action_updated_at = ""
        _set_project(owner, ProjectDocument(name="Nová akce", concrete_class="C25/30"))
        _clear_hit_rows(owner)
        if hasattr(owner, "refresh_substitution_tree"):
            owner.refresh_substitution_tree()
        owner.project_dirty = False
        owner.project.path = None
        owner._update_action_info()
        owner._update_project_title()
    finally:
        owner._action_loading = False
    try:
        owner.project_quick_entry.focus_set()
    except Exception:
        pass
    owner.set_status("Založena nová prázdná AKCE.")
