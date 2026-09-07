from __future__ import annotations

"""Patch verified project/HIT workspaces onto one centrally stored AKCE."""

from typing import Any
from action_browser import ActionBrowser, build_action_bar
from action_payload import new_action, save_action, save_action_as_new, confirm_action_close


def _fmt_date(value: str) -> str:
    from datetime import datetime
    try: return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M")
    except Exception: return str(value or "")


def install(project_mixin: Any, hit_row_class: Any, hit_mixin: Any) -> None:
    p_init = project_mixin._init_project_workspace
    p_dirty = project_mixin.mark_project_dirty
    p_refresh = project_mixin.refresh_project_tree
    h_init = hit_row_class.__init__
    h_product = hit_row_class._product_changed
    h_add = hit_mixin.add_hit_row; h_remove = hit_mixin.remove_hit_row
    h_clear = hit_mixin.clear_hit_rows; h_schedule = hit_mixin.open_hit_schedule
    h_options = hit_mixin._hit_options_changed

    def project_init(self) -> None:
        p_init(self); self.project.name = "Nová akce"
        self.action_id = None; self.action_created_at = ""; self.action_updated_at = ""
        self._action_loading = True

    def mark_dirty(self) -> None:
        if not getattr(self, "_action_loading", False): p_dirty(self)

    def update_title(self) -> None:
        name = (self.project_name_var.get().strip() if hasattr(self, "project_name_var") else self.project.name) or "Nová akce"
        self.title(f"{self.base_window_title} — AKCE: {name}{' *' if self.project_dirty else ''}")
        if hasattr(self, "_update_action_info"): self._update_action_info()

    def update_info(self) -> None:
        if not hasattr(self, "action_info_var"): return
        suffix = " • neuložené změny" if self.project_dirty else ""
        if self.action_id:
            self.action_info_var.set(f"Centrální databáze • poslední úprava {_fmt_date(self.action_updated_at)}{suffix}")
        else:
            self.action_info_var.set(f"Nová AKCE • dosud neuloženo{suffix}")

    def refresh(self, *args, **kwargs):
        result = p_refresh(self, *args, **kwargs)
        if hasattr(self, "project_path_var"):
            self.project_path_var.set("Centrální databáze AKCÍ" if self.action_id else "AKCE dosud není uložena v centrální databázi")
        return result

    project_mixin._init_project_workspace = project_init
    project_mixin.mark_project_dirty = mark_dirty
    project_mixin._update_project_title = update_title
    project_mixin._update_action_info = update_info
    project_mixin.refresh_project_tree = refresh
    project_mixin.new_action = new_action
    project_mixin.open_action_browser = lambda self: ActionBrowser(self)
    project_mixin.save_action = lambda self: save_action(self)
    project_mixin.save_action_as_new = lambda self: save_action_as_new(self)
    project_mixin.confirm_action_close = lambda self: confirm_action_close(self)
    # Old project commands and Ctrl+S are redirected, never written as .tinp.
    project_mixin.new_project = new_action
    project_mixin.open_project = lambda self: ActionBrowser(self)
    project_mixin.save_project = lambda self: save_action(self)
    project_mixin.save_project_as = lambda self: save_action_as_new(self)
    project_mixin.confirm_project_close = lambda self: confirm_action_close(self)

    tracked = (
        "name", "quantity", "series", "connection_type", "mvx_variant", "mvx_bx",
        "height", "required_length", "cover", "concrete", "med_pos", "med_neg",
        "ned_pos", "ned_neg", "ved_pos", "ved_neg", "hed_parallel", "hed_perp", "load_x",
    )

    def hit_init(self, owner, row_no: int, defaults=None) -> None:
        h_init(self, owner, row_no, defaults)
        for attr in tracked:
            var = getattr(self, attr, None)
            if var is not None and hasattr(var, "trace_add"):
                var.trace_add("write", lambda *_a, _owner=owner: None if getattr(_owner, "_action_loading", False) else _owner.mark_project_dirty())

    def product_changed(self, event=None):
        result = h_product(self, event)
        if event is not None and not getattr(self.owner, "_action_loading", False): self.owner.mark_project_dirty()
        return result

    def wrap_count(original):
        def wrapped(self, *args, **kwargs):
            before = len(self.hit_rows); result = original(self, *args, **kwargs)
            if len(self.hit_rows) != before and not getattr(self, "_action_loading", False): self.mark_project_dirty()
            return result
        return wrapped

    def clear(self):
        result = h_clear(self)
        if not getattr(self, "_action_loading", False): self.mark_project_dirty()
        return result

    def options(self):
        result = h_options(self)
        if not getattr(self, "_action_loading", False): self.mark_project_dirty()
        return result

    hit_row_class.__init__ = hit_init; hit_row_class._product_changed = product_changed
    hit_mixin.add_hit_row = wrap_count(h_add); hit_mixin.remove_hit_row = wrap_count(h_remove)
    hit_mixin.open_hit_schedule = wrap_count(h_schedule); hit_mixin.clear_hit_rows = clear
    hit_mixin._hit_options_changed = options


__all__ = ["build_action_bar", "install"]
