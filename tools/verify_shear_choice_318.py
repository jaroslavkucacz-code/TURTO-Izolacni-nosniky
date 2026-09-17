"""Actual Tk selection, calculation, SQLite and report regressions for alternatives."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
from verify_workflow_317 import pump


def exercise(app):
    import shear_choice_318 as choice
    from action_payload import action_store, serialize_action, load_action_record
    app.product_domain_notebook.select(app.product_domain_tab_by_id['shear_dowels'])
    app.shear_notebook.select(1)
    app.shear_design_rows = []
    app.shear_design_manufacturer_var.set('Ancon')
    values = app.shear_design_vars
    for key, value in dict(name='TEST_ONLY alternative318', qty='4', ved='5', slab='240', gap='20', concrete='C25/30').items():
        values[key].set(value)
    app.add_shear_design_row(); pump(app)
    assert len(app.shear_design_rows) == 1
    row = app.shear_design_rows[0]
    automatic = row['candidate']['designation']
    main, tree = app.shear_design_tree, app.shear_design_alternatives_tree
    assert tree.get_children(), (main.selection(), row, choice.panel._row_candidates(row, 'Ancon'), app.shear_design_alternatives_status.get())
    assert app.shear_use_alternative_button.instate(['disabled'])
    iid = tree.get_children()[-1]
    wanted = tree.set(iid, 'designation')
    tree.selection_set(iid); pump(app)
    assert not app.shear_use_alternative_button.instate(['disabled'])
    # Refresh must preserve the selected alternative, including before acceptance.
    app.refresh_shear_tables(); pump(app)
    assert tree.set(tree.selection()[0], 'designation') == wanted
    app.shear_use_alternative_button.invoke(); pump(app)
    assert row['candidate']['designation'] == wanted != automatic
    assert main.set('0', 'designation') == wanted
    assert row[choice.CHOICE]['designation'] == wanted
    row['name'] = 'TEST_ONLY renamed318'; row['quantity'] = 7
    for tab in (0, 2, 1):
        app.shear_notebook.select(tab); pump(app)
    app.recalculate_shear_design_all(); pump(app)
    assert row['candidate']['designation'] == wanted
    # Changed loads recalculate utilization, retaining the chosen valid type.
    old_util = row['candidate']['utilization']
    row['ved'] = 6
    app.recalculate_shear_design_all(); pump(app)
    assert row['candidate']['designation'] == wanted
    assert abs(row['candidate']['utilization'] - old_util * 6 / 5) < 1e-10
    exported = app.collect_shear_report_rows()
    assert any(r['candidate']['designation'] == wanted and r['quantity'] == 7 for r in exported)
    app.copy_shear_table('design'); assert wanted in app.clipboard_get()
    store = action_store(app)
    saved = store.save(payload=serialize_action(app), action_name='TEST_ONLY 318 manual alternative')
    meta = dict(action_id=saved['id'], wanted=wanted)
    (Path(app.settings_path).parent/'TEST_ONLY_saved318.json').write_text(json.dumps(meta), encoding='utf-8')
    load_action_record(app, store.load(saved['id'])); pump(app)
    row = app.shear_design_rows[0]
    assert row['candidate']['designation'] == wanted and row['quantity'] == 7
    app.recalculate_shear_design_all(); pump(app)
    assert row['candidate']['designation'] == wanted
    main.selection_set('0'); pump(app)
    # Invalid manual choice stays explicit; no stale capacities or silent fallback.
    row['ved'] = 1e8
    with patch('tkinter.messagebox.showwarning'):
        app.recalculate_shear_design_all()
    pump(app)
    assert not row['candidate'] and wanted in row['error']
    assert row[choice.CHOICE]['designation'] == wanted
    assert not app.collect_shear_report_rows()
    row['ved'] = 6
    app.recalculate_shear_design_all(); pump(app)
    assert row['candidate']['designation'] == wanted
    app.shear_auto_design_button.invoke(); pump(app)
    assert choice.CHOICE not in row and row['candidate']['designation'] == automatic
    assert app.shear_auto_design_button.instate(['disabled'])
    # No selection and stale alternative events cannot affect another row.
    iid = tree.get_children()[0]; tree.selection_set(iid); pump(app)
    app.shear_design_rows.append(deepcopy(row))
    app.refresh_shear_tables(); pump(app)
    before = deepcopy(app.shear_design_rows)
    main.selection_set('1')  # deliberately do not pump the pending selection event
    choice.apply_alternative(app)
    assert app.shear_design_rows == before
    pump(app)
    main.selection_remove(*main.selection()); pump(app)
    assert app.shear_use_alternative_button.instate(['disabled'])
    # Current catalogue families keep the existing fully-passing filter.
    brands = {}
    for brand in ('Ancon', 'Schöck', 'PohlCon', 'MAXFRANK', 'Aschwanden CRET'):
        sample = dict(name='TEST_ONLY '+brand, quantity=1, manufacturer=brand, ved=5,
                      slab_mm=240, gap_mm=20, concrete='C25/30', movement='axial',
                      application='new', low_sleeve='stainless', cover_mm=30)
        candidate, error = choice.design_row(sample)
        assert candidate, (brand, error)
        sample.update(candidate=candidate, error='')
        app.shear_design_rows = [sample]
        app.refresh_shear_tables(); main.selection_set('0'); pump(app)
        if brand == 'MAXFRANK':
            assert not tree.get_children()  # These require a separate slab check.
            assert app.shear_use_alternative_button.instate(['disabled'])
            brands[brand] = 'KONTROLA DESKY; excluded from fully passing alternatives'
            continue
        assert tree.get_children(), brand
        iid = tree.get_children()[-1]; tree.selection_set(iid); pump(app)
        selected = tree.set(iid, 'designation')
        # Keyboard Return uses the real binding and same validated acceptance.
        tree.focus_force(); pump(app); tree.event_generate('<Return>'); pump(app)
        assert sample['candidate']['designation'] == selected, (brand, sample)
        app.recalculate_shear_design_all(); pump(app)
        assert sample['candidate']['designation'] == selected
        brands[brand] = selected
    # CRET alternatives must keep CRET even if the quick-add manufacturer changes.
    app.shear_design_manufacturer_var.set('Ancon')
    app.refresh_shear_tables(); pump(app)
    assert all(tree.set(iid, 'designation').startswith('CRET') for iid in tree.get_children())
    # A candidate displayed before structural edits is revalidated on acceptance.
    main.selection_set('0'); pump(app)
    tree.selection_set(tree.get_children()[0]); pump(app)
    sample['ved'] = 1e8
    previous_choice = deepcopy(sample[choice.CHOICE])
    choice.apply_alternative(app)
    assert sample[choice.CHOICE] == previous_choice
    assert 'nevyhovuje' in app.shear_design_alternatives_status.get()
    # Restore the saved action for the EXE roundtrip and leave a reviewable UI.
    reopen_saved(app); main.selection_set('0'); pump(app)
    app.product_domain_notebook.select(app.product_domain_tab_by_id['shear_dowels'])
    app.shear_notebook.select(1); pump(app)
    app.geometry('1280x900'); pump(app)
    iid = tree.get_children()[0]; tree.see(iid); pump(app)
    expected = tree.set(iid, 'designation')
    box = tree.bbox(iid, 'designation'); assert box, (iid, tree.winfo_ismapped())
    x, y = box[0]+20, box[1]+box[3]//2
    assert tree.identify_region(x,y) == 'cell', (box, tree.winfo_width(), tree.winfo_height(), app.winfo_geometry())
    for index in range(2):
        tree.event_generate('<ButtonPress-1>', x=x, y=y, time=10000+index*100)
        tree.event_generate('<ButtonRelease-1>', x=x, y=y, time=10010+index*100)
    pump(app)
    assert app.shear_design_rows[0]['candidate']['designation'] == expected, (expected, app.shear_design_rows[0], tree.identify_region(x,y), tree.selection(), tree.bind('<Double-1>'))
    reopen_saved(app); main.selection_set('0'); pump(app)
    # Both buttons remain reachable at the smallest supported window width.
    app.geometry('1120x850'); pump(app)
    for table in (main, tree):
        first = table.get_children()[0]; table.see(first); pump(app)
        bbox = table.bbox(first); assert bbox and bbox[1]+bbox[3] <= table.winfo_height(), (str(table), bbox, table.winfo_height(), app.shear_design_alternatives_status.get())
    for button in (app.shear_use_alternative_button, app.shear_auto_design_button):
        assert button.winfo_ismapped()
        assert button.winfo_rootx()+button.winfo_width() <= app.winfo_rootx()+app.winfo_width()
        assert button.winfo_rooty()+button.winfo_height() <= app.winfo_rooty()+app.winfo_height()
    return dict(selected=wanted, manufacturers=brands, saved_action=True,
                keyboard=True, stale_events_blocked=True, invalid_choice_reported=True)


def reopen_saved(app):
    from action_payload import action_store, load_action_record
    saved = json.loads((Path(app.settings_path).parent/'TEST_ONLY_saved318.json').read_text(encoding='utf-8'))
    load_action_record(app, action_store(app).load(saved['action_id'])); pump(app)
    row = app.shear_design_rows[0]
    assert row['manual_candidate']['designation'] == saved['wanted']
    assert row['candidate']['designation'] == saved['wanted'] and row['quantity'] == 7
    assert app.shear_design_tree.set('0', 'designation') == saved['wanted']
