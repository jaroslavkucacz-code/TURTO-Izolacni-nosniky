from __future__ import annotations

"""Do not create or count unused initial HIT rows; preserve explicit drafts."""

from contextlib import contextmanager
from functools import wraps
import json
import sys

VERSION = "3.0.6"
EXPLICIT = "explicit_rows"
SECTIONS = ("hit_design", "aux_design", "wt_design")
_FORCES = ("med_pos", "med_neg", "ned_pos", "ned_neg", "ved_pos", "ved_neg",
           "hed_parallel", "hed_perp", "load_x")
# Complete input defaults from the legacy row constructors/serializers. A row
# with any changed value, unknown field or explicit 3.0.6 provenance is kept.
DEFAULTS = {
    "hit_design": dict(name="N1", quantity=1, series="HP", connection_type="MVX",
        mvx_variant="Bez", mvx_bx="", height="200", required_length="", cover="35",
        concrete="C25/30", **dict.fromkeys(_FORCES, ""), import_source_text="",
        import_source_line="", selected_designation="", manual_product=False),
    "aux_design": dict(name="D001", quantity=1, series="HP", connection_type="HT",
        height="200", dimension="100", required_length="100", concrete="C25/30",
        **dict.fromkeys(_FORCES, ""), selected_designation="", manual_product=False),
    "wt_design": dict(name="W001", quantity=1, series="HP", wall_height="1500",
        width="150", concrete="C25/30", med_neg="", ved_vertical="",
        ved_horizontal="", selected_designation="", manual_product=False),
}


def is_legacy_initial_row(section, row):
    expected = DEFAULTS[section]
    # Require the complete known serialized signature, never a broad "no result"
    # or "zero load" heuristic that could discard an incomplete real design.
    return isinstance(row, dict) and row == expected


def clean_section(section, payload):
    if not isinstance(payload, dict) or payload.get(EXPLICIT) is True:
        return payload
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows or not is_legacy_initial_row(section, rows[0]):
        return payload
    return {**payload, "rows": rows[1:]}


def clean_action(payload):
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    for section in SECTIONS:
        if section in result:
            result[section] = clean_section(section, result[section])
    return result


@contextmanager
def _suppress_initial_rows(owner, *sections):
    previous = getattr(owner, "_turto_suppress_initial_rows", frozenset())
    owner._turto_suppress_initial_rows = previous | frozenset(sections)
    try:
        yield
    finally:
        owner._turto_suppress_initial_rows = previous


def _replace_imported(name, old, new):
    # Legacy action modules import these helpers by value. Replace only aliases
    # of the same function, retaining all other wrappers in the call chain.
    for module in tuple(sys.modules.values()):
        if module is not None and vars(module).get(name) is old:
            setattr(module, name, new)


def install(base):
    cls = base.ThermalConnectorApp
    if getattr(cls, "_turto_design_rows_306", False):
        return
    import action_store
    import hit_design_ui

    old_build = cls._build_hit_tab
    old_add_hit = cls.add_hit_row
    old_add_aux = cls.add_aux_row_for_type
    old_add_wt = cls.add_wt_row

    @wraps(old_build)
    def build(owner, *args, **kwargs):
        with _suppress_initial_rows(owner, *SECTIONS):
            result = old_build(owner, *args, **kwargs)
        owner.update_hit_status()
        owner.update_aux_status()
        owner.update_wt_status()
        return result

    @wraps(old_add_hit)
    def add_hit(owner, *args, **kwargs):
        if "hit_design" not in getattr(owner, "_turto_suppress_initial_rows", ()):
            return old_add_hit(owner, *args, **kwargs)

    @wraps(old_add_aux)
    def add_aux(owner, typ="HT", defaults=None, *, mark_dirty=True):
        if defaults is None and "aux_design" in getattr(owner, "_turto_suppress_initial_rows", ()):
            return None
        return old_add_aux(owner, typ, defaults, mark_dirty=mark_dirty)

    @wraps(old_add_wt)
    def add_wt(owner, defaults=None, *, mark_dirty=True):
        if defaults is None and "wt_design" in getattr(owner, "_turto_suppress_initial_rows", ()):
            return None
        return old_add_wt(owner, defaults, mark_dirty=mark_dirty)

    cls._build_hit_tab = build
    cls.add_hit_row = add_hit
    cls.add_aux_row_for_type = add_aux
    cls.add_wt_row = add_wt

    old_hit_load = hit_design_ui._load_design_record

    @wraps(old_hit_load)
    def load_hit(owner, workspace, record):
        work = {**record, "payload": clean_section("hit_design", record.get("payload"))}
        with _suppress_initial_rows(owner, "hit_design"):
            return old_hit_load(owner, workspace, work)

    _replace_imported("_load_design_record", old_hit_load, load_hit)

    def wrap_load(section, method):
        @wraps(method)
        def load(owner, payload):
            with _suppress_initial_rows(owner, section):
                return method(owner, clean_section(section, payload))
        return load

    cls.load_aux_design = wrap_load("aux_design", cls.load_aux_design)
    cls.load_wt_design = wrap_load("wt_design", cls.load_wt_design)

    def wrap_serialize(method):
        @wraps(method)
        def serialize(owner):
            result = dict(method(owner))
            # Every surviving/current row was explicitly added or imported.
            # Even a deliberately added blank draft must survive save/reopen.
            result[EXPLICIT] = True
            return result
        return serialize

    old_serialize = hit_design_ui.serialize_hit_design
    _replace_imported("serialize_hit_design", old_serialize, wrap_serialize(old_serialize))
    cls.serialize_aux_design = wrap_serialize(cls.serialize_aux_design)
    cls.serialize_wt_design = wrap_serialize(cls.serialize_wt_design)

    store = action_store.ActionStore
    old_counts, old_save, old_load, old_list = store._counts, store.save, store.load, store.list

    def counts(payload):
        return old_counts(clean_action(payload))

    @wraps(old_save)
    def save(self, *, action_name, payload, action_id=None):
        return old_save(self, action_name=action_name, payload=clean_action(payload), action_id=action_id)

    @wraps(old_load)
    def load(self, action_id):
        record = dict(old_load(self, action_id))
        record["payload"] = clean_action(record["payload"])
        record["decoder_count"], record["hit_count"] = self._counts(record["payload"])
        return record

    @wraps(old_list)
    def list_actions(self, search=""):
        records = old_list(self, search)
        by_id = {str(record["id"]): record for record in records}
        ids = list(by_id)
        # Recompute legacy cached counters for display using read-only SELECTs.
        # No startup migration, writes, timestamps or customer JSON are changed.
        with self._connect() as connection:
            for start in range(0, len(ids), 500):
                batch = ids[start:start + 500]
                query = "SELECT id, payload_json FROM actions WHERE id IN (" + ",".join("?" for _ in batch) + ")"
                for row in connection.execute(query, batch):
                    try:
                        payload = json.loads(row["payload_json"])
                    except (TypeError, ValueError):
                        continue  # Preserve the existing visible record; loading reports corruption.
                    if isinstance(payload, dict):
                        record = by_id[str(row["id"])]
                        record["decoder_count"], record["hit_count"] = self._counts(payload)
        return records

    store._counts = staticmethod(counts)
    store.save, store.load, store.list = save, load, list_actions
    cls._turto_design_rows_306 = True


def selftest():
    for section, row in DEFAULTS.items():
        source = {"rows": [dict(row)]}
        assert clean_section(section, source)["rows"] == []
        assert source["rows"] == [row]
        assert clean_section(section, {**source, EXPLICIT: True})["rows"] == [row]
        changed = {**row, "quantity": 2}
        assert clean_section(section, {"rows": [changed]})["rows"] == [changed]
