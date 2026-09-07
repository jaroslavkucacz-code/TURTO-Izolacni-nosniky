from __future__ import annotations

"""Runtime variables for TURTO 2.0 platform selections."""

from typing import Any
import tkinter as tk

from platform_registry import (
    DEFAULT_DOMAIN_ID,
    default_platform_state,
    manufacturer_id_from_label,
    manufacturer_label,
    normalize_platform_state,
)


def ensure_platform_variables(owner: Any) -> None:
    if hasattr(owner, "platform_state") and hasattr(owner, "design_manufacturer_var"):
        return
    state = normalize_platform_state(getattr(owner, "platform_state", None))
    owner.platform_state = state
    thermal = state["domains"]["thermal_breaks"]
    owner.design_manufacturer_var = tk.StringVar(
        master=owner,
        value=manufacturer_label("thermal_breaks", thermal.get("design_manufacturer", "leviat")) or "Leviat",
    )
    owner.substitution_manufacturer_var = tk.StringVar(
        master=owner,
        value=manufacturer_label("thermal_breaks", thermal.get("substitution_manufacturer", "leviat")) or "Leviat",
    )


def capture_platform_state(owner: Any) -> dict:
    ensure_platform_variables(owner)
    state = normalize_platform_state(getattr(owner, "platform_state", None))
    thermal = state["domains"]["thermal_breaks"]
    design_id = manufacturer_id_from_label("thermal_breaks", owner.design_manufacturer_var.get()) or "leviat"
    substitution_id = manufacturer_id_from_label("thermal_breaks", owner.substitution_manufacturer_var.get()) or "leviat"
    thermal["design_manufacturer"] = design_id
    thermal["substitution_manufacturer"] = substitution_id
    notebook = getattr(owner, "product_domain_notebook", None)
    tab_by_id = getattr(owner, "product_domain_tab_by_id", {})
    if notebook is not None and isinstance(tab_by_id, dict):
        try:
            selected = str(notebook.select())
            for domain_id, frame in tab_by_id.items():
                if str(frame) == selected:
                    state["active_domain"] = domain_id
                    break
        except Exception:
            pass
    owner.platform_state = state
    return state


def apply_platform_state(owner: Any, raw: object) -> None:
    ensure_platform_variables(owner)
    state = normalize_platform_state(raw)
    owner.platform_state = state
    thermal = state["domains"]["thermal_breaks"]
    owner.design_manufacturer_var.set(
        manufacturer_label("thermal_breaks", thermal.get("design_manufacturer", "leviat")) or "Leviat"
    )
    owner.substitution_manufacturer_var.set(
        manufacturer_label("thermal_breaks", thermal.get("substitution_manufacturer", "leviat")) or "Leviat"
    )
    notebook = getattr(owner, "product_domain_notebook", None)
    tab_by_id = getattr(owner, "product_domain_tab_by_id", {})
    active = state.get("active_domain", DEFAULT_DOMAIN_ID)
    if notebook is not None and isinstance(tab_by_id, dict) and active in tab_by_id:
        try:
            notebook.select(tab_by_id[active])
        except Exception:
            pass


def reset_platform_state(owner: Any) -> None:
    apply_platform_state(owner, default_platform_state())
