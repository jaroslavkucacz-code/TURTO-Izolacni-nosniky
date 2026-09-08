from __future__ import annotations
from typing import Any
import tkinter as tk
import platform_state_200 as _prev
from platform_registry import default_platform_state,manufacturer_id_from_label,manufacturer_label,normalize_platform_state

def ensure_platform_variables(owner:Any)->None:
    if not hasattr(owner,"platform_state") or not hasattr(owner,"design_manufacturer_var"):_prev.ensure_platform_variables(owner)
    state=normalize_platform_state(getattr(owner,"platform_state",None));owner.platform_state=state
    if not hasattr(owner,"shear_design_manufacturer_var"):
        shear=state["domains"]["shear_dowels"]
        owner.shear_design_manufacturer_var=tk.StringVar(master=owner,value=manufacturer_label("shear_dowels",shear.get("design_manufacturer","ancon")) or "Ancon / Leviat")
        owner.shear_substitution_manufacturer_var=tk.StringVar(master=owner,value=manufacturer_label("shear_dowels",shear.get("substitution_manufacturer","schoeck")) or "Schöck")

def capture_platform_state(owner:Any)->dict:
    ensure_platform_variables(owner);state=normalize_platform_state(_prev.capture_platform_state(owner));shear=state["domains"]["shear_dowels"]
    shear["design_manufacturer"]=manufacturer_id_from_label("shear_dowels",owner.shear_design_manufacturer_var.get()) or "ancon"
    shear["substitution_manufacturer"]=manufacturer_id_from_label("shear_dowels",owner.shear_substitution_manufacturer_var.get()) or "schoeck";owner.platform_state=state;return state

def apply_platform_state(owner:Any,raw:object)->None:
    ensure_platform_variables(owner);state=normalize_platform_state(raw);_prev.apply_platform_state(owner,state);owner.platform_state=state;shear=state["domains"]["shear_dowels"]
    owner.shear_design_manufacturer_var.set(manufacturer_label("shear_dowels",shear.get("design_manufacturer","ancon")) or "Ancon / Leviat")
    owner.shear_substitution_manufacturer_var.set(manufacturer_label("shear_dowels",shear.get("substitution_manufacturer","schoeck")) or "Schöck")

def reset_platform_state(owner:Any)->None:apply_platform_state(owner,default_platform_state())
