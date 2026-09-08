from __future__ import annotations
from typing import Any
import action_payload_200 as _prev
from action_payload_200 import *  # noqa
from platform_registry import default_platform_state
from platform_state import apply_platform_state,capture_platform_state,reset_platform_state
_ORIGINAL_SERIALIZE=_prev.serialize_action;_ORIGINAL_LOAD=_prev.load_action_record;_ORIGINAL_NEW=_prev.new_action;_ORIGINAL_SAVE=_prev.save_action

def serialize_action(owner:Any)->dict[str,Any]:
    payload=_ORIGINAL_SERIALIZE(owner);payload["schema_version"]=max(5,int(payload.get("schema_version",1) or 1));payload["platform_state"]=capture_platform_state(owner)
    payload["shear_dowels"]=owner.serialize_shear_dowels() if hasattr(owner,"serialize_shear_dowels") else {"schema_version":1,"decoder":[],"design":[],"substitution":[]}
    domains=payload.get("product_domains") if isinstance(payload.get("product_domains"),dict) else {};domains["shear_dowels"]={"storage":"shear_dowels","status":"active"};payload["product_domains"]=domains;return payload

def load_action_record(owner:Any,record:dict[str,Any])->None:
    _ORIGINAL_LOAD(owner,record);payload=record.get("payload") if isinstance(record.get("payload"),dict) else {};apply_platform_state(owner,payload.get("platform_state",default_platform_state()))
    if hasattr(owner,"load_shear_dowels"):
        owner._action_loading=True
        try:owner.load_shear_dowels(payload.get("shear_dowels"))
        finally:owner._action_loading=False
    try:owner.project_dirty=False;owner._update_project_title();owner._update_action_info()
    except Exception:pass

def save_action(owner:Any,*,as_new:bool=False,forced_name:str|None=None)->bool:capture_platform_state(owner);return bool(_ORIGINAL_SAVE(owner,as_new=as_new,forced_name=forced_name))
def new_action(owner:Any)->None:
    _ORIGINAL_NEW(owner)
    try:
        owner._action_loading=True;reset_platform_state(owner)
        if hasattr(owner,"clear_shear_dowels"):owner.clear_shear_dowels()
        owner.project_dirty=False;owner._update_project_title();owner._update_action_info()
    finally:owner._action_loading=False
_prev.serialize_action=serialize_action;_prev.load_action_record=load_action_record;_prev.save_action=save_action;_prev.new_action=new_action
for obj in (getattr(_prev,"_prev",None),getattr(getattr(_prev,"_prev",None),"_prev",None)):
    if obj is not None:
        try:obj.serialize_action=serialize_action;obj.load_action_record=load_action_record;obj.save_action=save_action;obj.new_action=new_action
        except Exception:pass
save_action_as_new=_prev.save_action_as_new
confirm_action_close=_prev.confirm_action_close
action_store=_prev.action_store
