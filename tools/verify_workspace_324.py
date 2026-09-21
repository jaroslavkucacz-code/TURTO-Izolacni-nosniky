"""Real drag events, durable table preferences, all workspaces and ZL exports."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json


def exercise(app):
    import infill, source_completion as completion, table_controls as tables
    import bulk_import, bulk_import_engine, project_model, action_payload, pdf_data_304, hit_pdf
    from tkinter import ttk
    from workspace_controls_317 import walk
    from verify_workflow_317 import pump

    texts = ('T typ ZL - EI120 - H200 - 2.0', 'XT-ZL-EI120-H220-2.0', 'T-ZL')
    items, _ = bulk_import_engine.analyze_bulk_text(app.database, texts[0]+'\t8', preferred_concrete='C25/30')
    assert len(items) == 1
    app.project.rows = []
    def insert(dialog):
        dialog.items = items
        dialog._refresh_review_tree()
        dialog._insert_ready()
    with patch.object(app, 'wait_window', side_effect=insert):
        app.bulk_paste_project_rows()
    assert len(app.project.rows) == 1 and app.project.rows[0]['quantity'] == 8
    app.project.rows[0]['position'] = 'Z01'
    for i, text in enumerate(texts[1:], 2):
        app.project.add(completion.unresolved_row(dict(source_text=text, quantity=i, position=f'Z0{i}')))
    app.refresh_substitution_tree()
    database = app.hit_db
    app.hit_db = None
    with patch.object(app, '_settings', side_effect=AssertionError('ZL must not need HIT capacities')):
        app.design_substitutions(False)
    app.hit_db = database
    rows = app.project.rows
    assert rows[0]['mapping']['status'] == 'infill'
    assert all(not r['mapping']['targets'] for r in rows)
    assert app._payload(rows[0])[0]['target'] == 'Mezivýplň tl. 80 mm, výšky 200 mm'
    assert app._payload(rows[1])[0]['target'] == 'Mezivýplň tl. 120 mm, výšky 220 mm'
    assert app._payload(rows[2])[0]['status'] == 'Doplnit rozměry'
    initial = completion.form_values(rows[2])
    assert initial['insulation'] == '80'
    repaired = completion.apply_manual(rows[2], dict(initial, height_mm='210'), initial)
    rows[2].clear(); rows[2].update(repaired)
    assert app._payload(rows[2])[0]['target'] == 'Mezivýplň tl. 80 mm, výšky 210 mm'
    cleared = completion.apply_manual(rows[0], dict(completion.form_values(rows[0]), height_mm=''), completion.form_values(rows[0]))
    assert infill.dimensions(cleared)['missing'] == ['výšku']
    unknown = deepcopy(rows[0]); unknown['selection']['model'] = 'Jiná'
    assert infill.dimensions(unknown)['missing'] == ['tloušťku izolantu']
    for family in ('QP', 'ZLX', 'KL'):
        other = deepcopy(rows[0]); other['selection']['type_name'] = family
        assert infill.dimensions(other) is None
    other = deepcopy(rows[0]); other['selection']['manufacturer'] = 'Jiný výrobce'
    assert infill.dimensions(other) is None
    app.design_substitutions(False)
    before = deepcopy(app.project.rows)
    store = action_payload.action_store(app)
    saved = store.save(action_name='TEST_ONLY workspace324', payload=action_payload.serialize_action(app))
    action_payload.load_action_record(app, store.load(saved['id']))
    assert app.project.rows == [project_model.normalize_project_row(row) for row in before]
    for row in app.project.rows:
        p, _ = app._payload(row)
        assert p['target'].startswith('Mezivýplň tl.')
        assert all(p[k] == '' for k in ('utilization','target_m','target_v','target_n','m_pos','v_pos'))
    output = Path(app.settings_path).parent
    records = pdf_data_304.iso_substitution_rows(app)
    assert len(records) == 3 and all(r['non_structural'] and not r['target'] for r in records)
    pdf = output/'TEST_ONLY_infill.pdf'
    hit_pdf.write_hit_proposal_pdf(pdf, project_name='TEST_ONLY mezivýplně', rows=records)
    import pdfplumber
    with pdfplumber.open(pdf) as book:
        text = '\n'.join(p.extract_text() or '' for p in book.pages)
    assert 'Mezivýplň tl. 80 mm, výšky 200 mm' in text, text
    assert 'Mezivýplň tl. 120 mm, výšky 220 mm' in text
    assert 'Celkové využití' not in text and 'Náhrada HIT:' not in text
    assert all(r.get('non_structural') for r in app._pdf_report_rows())
    xlsx = output/'TEST_ONLY_infill.xlsx'
    import substitution_workspace as sub
    app.sub_tree.selection_set(app.project.rows[0]['id'])
    with patch.object(sub.filedialog, 'asksaveasfilename', return_value=str(output/'TEST_ONLY_infill_selected.pdf')), patch('os.startfile', create=True):
        app.export_substitution_pdf()
    with pdfplumber.open(output/'TEST_ONLY_infill_selected.pdf') as book:
        text = '\n'.join(p.extract_text() or '' for p in book.pages)
    assert '80 mm, výšky 200 mm' in text and '120 mm, výšky 220 mm' not in text
    app.sub_tree.selection_remove(app.sub_tree.selection())
    with patch.object(sub.filedialog, 'asksaveasfilename', return_value=str(xlsx)), patch('os.startfile', create=True):
        app.export_substitution_xlsx()
    import openpyxl
    book = openpyxl.load_workbook(xlsx, data_only=True)
    values = str([list(sheet.values) for sheet in book]); book.close()
    assert 'Mezivýplň tl. 80 mm, výšky 200 mm' in values

    app.deiconify()
    iso = app.product_domain_tab_by_id['thermal_breaks']
    shear = app.product_domain_tab_by_id['shear_dowels']
    plans = [(iso, app.main_notebook, app.project_tab, app.project_tree),
             (iso, app.main_notebook, app.substitution_tab, app.sub_tree)]
    for tab, tree in zip(app.shear_notebook.tabs(), (app.shear_decoder_tree, app.shear_design_tree, app.shear_substitution_tree)):
        plans.append((shear, app.shear_notebook, tab, tree))
    dragged = []
    for domain, notebook, tab, tree in plans:
        app.product_domain_notebook.select(domain); notebook.select(tab); pump(app)
        visible = tree['displaycolumns']
        if visible == ('#all',): visible = tree['columns']
        col = visible[0]; before_width = tree.column(col, 'width')
        # Find the real separator (theme borders can offset it by two pixels).
        x = next(x for x in range(before_width-2,before_width+5) if tree.identify_region(x,10) == 'separator' and tree.identify_column(x) == '#1')
        tree.event_generate('<ButtonPress-1>', x=x, y=10)
        tree.event_generate('<B1-Motion>', x=x+57, y=10)
        tables.reapply(app)
        tree.event_generate('<ButtonRelease-1>', x=x+57, y=55)
        pump(app)
        after = tree.column(col, 'width')
        assert after >= before_width+45, (str(tree), before_width, after, x, col, tree.column(col), tree['displaycolumns'])
        tables.reapply(app); pump(app)
        assert tree.column(col, 'width') == after
        if tree is app.project_tree:
            state = app._project_layout_state()
            assert state['widths'][col] == after
            app._set_project_column_visible('note', False)
        else:
            controller = tables.controller_for(app, tree)
            assert controller.state['widths'][col] == after
            hide = controller.defaults.order[-1]
            controller.set_visible(hide, False)
            assert hide not in tree['displaycolumns']
        dragged.append(str(tree))
    # Main tables use stable attribute keys, dialog tables use component/schema
    # keys. Neither title nor version may influence the latter.
    dialog = completion.CompletionDialog(app, app.project.rows[0]); pump(app)
    key = tables._semantic_key(app, dialog.tree)
    dialog.title('TURTO 9.8.7 – úplně jiná AKCE')
    assert tables._semantic_key(app, dialog.tree) == key
    controller = tables.controller_for(app, dialog.tree)
    col = controller.defaults.order[0]
    controller.state['widths'][col] = 333; controller.set_visible(controller.defaults.order[-1], False)
    hidden = list(controller.state['hidden']); dialog.destroy(); pump(app)
    dialog = completion.CompletionDialog(app, app.project.rows[1]); pump(app)
    controller = tables.controller_for(app, dialog.tree)
    assert controller.state['widths'][col] == 333 and controller.state['hidden'] == hidden
    dialog.destroy()
    # Bulk import owns its review layout; a universal controller must not race
    # with it. Exercise a real drag and its existing hidden-column preference.
    dialog = bulk_import.BulkImportDialog(app, database=app.database, colors=app.colors,
        preferred_concrete='C25/30', existing_positions=[], start_position='P001',
        settings=app.settings, save_settings=app._save_settings)
    pump(app)
    assert not tables._eligible(app, dialog.review_tree)
    tree = dialog.review_tree
    col = tree['displaycolumns'][0]; before_width = tree.column(col, 'width')
    x = next(x for x in range(before_width-2,before_width+5) if tree.identify_region(x,10)=='separator')
    tree.event_generate('<ButtonPress-1>', x=x, y=10)
    tree.event_generate('<B1-Motion>', x=x+57, y=10)
    tables.reapply(app)
    tree.event_generate('<ButtonRelease-1>', x=x+57, y=55); pump(app)
    assert tree.column(col,'width') >= before_width+45
    assert dialog._review_layout_state()['widths'][col] == tree.column(col,'width')
    dialog.destroy()
    settings = json.loads(Path(app.settings_path).read_text(encoding='utf-8'))
    assert settings['table_layouts']['project']['widths'] == app._project_layout_state()['widths']
    assert 'note' in settings['table_layouts']['project']['hidden']
    assert settings[tables.SETTING_KEY]['sub_tree']['widths'] == tables.controller_for(app, app.sub_tree).state['widths']
    # Record exact preferences for a separate-process reopen/update probe.
    (output/'TEST_ONLY_layout324.json').write_text(json.dumps({k:settings[k] for k in ('table_layouts',tables.SETTING_KEY)}, ensure_ascii=False), encoding='utf-8')
    for width in (1250,1900):
        app.geometry(f'{width}x950+10+10')
        for domain, notebook, tab, tree in plans:
            app.product_domain_notebook.select(domain); notebook.select(tab); pump(app)
            assert tree.winfo_ismapped() and tree.winfo_height() > 100, (width,str(tree),tree.winfo_ismapped(),tree.winfo_height(),app.winfo_height())
            # No header, empty spacer or toolbar row may absorb extra height.
            for frame in walk(notebook.nametowidget(str(tab))):
                if not isinstance(frame, ttk.Frame): continue
                children = [w for w in frame.winfo_children() if w.winfo_manager() == 'grid']
                table_rows = set()
                for child in children:
                    import tkinter as tk
                    if any(isinstance(w, (ttk.Treeview, tk.Canvas, ttk.Notebook)) for w in walk(child)):
                        info = child.grid_info(); table_rows.add(int(info['row'])+int(info.get('rowspan',1))-1)
                if table_rows:
                    assert all(not frame.grid_rowconfigure(r)['weight'] or r in table_rows for r in range(frame.grid_size()[1])),str(frame)
        app.product_domain_notebook.select(iso); app.main_notebook.select(app.project_tab); pump(app)
        title = next(w for w in walk(app.project_tab) if isinstance(w,ttk.Label) and str(w.cget('text')).startswith('Dekodér ISO'))
        assert title.winfo_rooty()-app.project_tab.winfo_rooty()<45
    return dict(infill=3,manual_dimensions=True,sqlite=True,pdf=True,xlsx=True,dragged_tables=len(dragged),durable_preferences=True,compact_tabs=len(plans),widths=[1250,1900])


def reopen_saved(app):
    import table_controls
    path=Path(app.settings_path).parent/'TEST_ONLY_layout324.json'
    expected=json.loads(path.read_text(encoding='utf-8'))
    for key, value in expected.items():
        assert app.settings[key] == value, key
    assert 'note' not in app.project_tree['displaycolumns']
    col=table_controls.controller_for(app,app.sub_tree).defaults.order[0]
    assert app.sub_tree.column(col,'width') == expected[table_controls.SETTING_KEY]['sub_tree']['widths'][col]
