"""User's actual dowel schedule through the installed decoder and import dialog."""
TEXT = 'Smykový trn LD25-S-A4\t1\nSmykový trn SCHOECK STACON LD Ø20 S-A4\t9'


def exercise(app):
    import shear_dowels_ui as ui
    import shear_dowels_catalog as catalog
    from shear_schedule_io_236 import parse_rows
    from shear_workflow_236 import DecoderFileDialog
    defaults = dict(slab='240', gap='20', concrete='C30/37')
    modern = ui.decode_dowel('Smykový trn SCHOECK STACON LD Ø20 S-A4')
    assert modern and modern['manufacturer'] == 'Schöck' and modern['size'] == '20', modern
    assert not modern.get('legacy'), modern
    assert ui.decode_dowel('LD25-S-A4')['legacy']
    for brand in ('Schöck', 'SCHOECK', 'SCHOCK'):
        for symbol in ('Ø', 'ø', '⌀', ''):
            info = ui.decode_dowel(f'{brand} STACON LD {symbol}20 S-A4')
            assert info['family'] == 'LD' and info['size'] == '20' and not info.get('legacy'), info
            assert ui.decode_dowel(f'{brand} STACON LD-Q {symbol}20 S-A4')['movement'] == 'transverse'
    # Preserve archival full assemblies and component-only restrictions.
    assert ui.decode_dowel('LD Ø25-S-A4')['legacy']
    assert ui.decode_dowel('LD 20 Part A4')['decoder_only']
    assert ui.decode_dowel('SLD 40')['legacy']
    assert not ui.decode_dowel('SCHOECK STACON LD Ø S-A4')
    expected = catalog.schock_capacity_from_designation('Schöck Stacon LD 20', 240, 20, 30)
    actual = catalog.schock_capacity_from_designation('SCHOECK STACON LD Ø20 S-A4', 240, 20, 30)
    assert actual and expected and actual.vrd == expected.vrd and actual.source == expected.source
    for text in (TEXT, TEXT.replace('\t', ' ')):
        rows = parse_rows(text, decoder=ui.decode_dowel, defaults=defaults, existing_names=set(), use_defaults=True)
        assert len(rows) == 2 and not any(r.error for r in rows), [(r.error, r.values) for r in rows]
        assert [r.quantity for r in rows] == [1, 9]
        assert [r.values['size'] for r in rows] == ['25','20']
    dialog = DecoderFileDialog(app, mode='decoder', decoder=ui.decode_dowel, defaults=defaults, existing_names=set())
    dialog.text.insert('1.0', TEXT)
    dialog.use_geometry.set(True)
    dialog._analyze()
    assert len(dialog.items) == 2 and not any(r.error for r in dialog.items)
    assert not dialog.insert_button.instate(['disabled'])
    dialog.insert_button.invoke()
    assert [r['quantity'] for r in dialog.result] == [1,9], dialog.result
    assert dialog.result[1]['designation'] == 'Smykový trn SCHOECK STACON LD Ø20 S-A4'
    return dict(rows=2, quantities=[1,9], modern_catalogue=actual.source, capacity=actual.vrd)
