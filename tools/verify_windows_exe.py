"""Exercise the actual frozen executable with no Python on its PATH.

All fixtures and generated actions stay in a disposable copy of the package.
The shipping distribution is never opened or populated by the test.
"""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'CURRENT_VERSION').read_text().strip()
LAYOUT = json.loads((ROOT / 'update_manifest.json').read_text(encoding='utf-8'))['runtime_layout']


def windows():
    from ctypes import wintypes
    result = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32 = ctypes.windll.user32
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    @callback_type
    def callback(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        text = ctypes.create_unicode_buffer(1024)
        user32.GetWindowTextW(hwnd, text, len(text))
        if user32.IsWindowVisible(hwnd):
            result.append((hwnd, pid.value, text.value))
        return True
    user32.EnumWindows(callback, 0)
    return result


def wait_window(process_id=None):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        for hwnd, pid, title in windows():
            if (process_id is None or process_id == pid) and title.startswith(f'TURTO Statika {VERSION}'):
                return hwnd, pid, title
        time.sleep(.2)
    raise AssertionError(('Application window did not open', windows()))


def probe(root):
    """Runs inside the EXE; assert genuine frozen imports and actual UI/export."""
    import base64
    import gzip
    import runpy
    import traceback
    from unittest.mock import patch
    import tkinter as tk
    from tkinter import messagebox
    from PIL import ImageGrab
    assert getattr(sys, 'frozen', False)
    assert Path(sys.executable).name == 'TURTO Statika.exe'
    assert all('site-packages' not in p.lower() for p in sys.path), sys.path
    assert shutil.which('python') is None
    boot = runpy.run_path(str(root / 'app.pyw'))
    assert boot['_runtime_ready'](), 'Shipped payload must start completely offline.'
    runtime = runpy.run_path(str(root / 'Program/app_runtime.pyw'))
    runtime['selftest']()
    import hit_core, hit_workspace, hit_export_ui, hit_pdf, hit_excel, hit_units_310, action_payload
    errors = []
    tk.Tk.report_callback_exception = lambda self, *exc: errors.append(''.join(traceback.format_exception(*exc)))
    def pump(app, duration=.2):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            app.update(); time.sleep(.01)
    with patch.object(messagebox, 'showerror', lambda *a, **k: errors.append(str(a))), \
         patch.object(messagebox, 'showinfo', return_value=None), \
         patch.object(messagebox, 'showwarning', return_value=None):
        app = runtime['_base'].ThermalConnectorApp(); pump(app)
        assert app.title().startswith(f'TURTO Statika {VERSION}'), app.title()
        assert app._turto_brand_title.cget('text').startswith(f'TURTO Statika {VERSION}')
        assert app._turto_native_icon_loaded
        assert not app.hit_rows and not app.aux_rows and not app.wt_rows
        data = {'schema_version': 4, 'source_document': 'TEST_ONLY; NOT FOR DESIGN', 'zvx_records': [
            {'series': 'HP', 'concrete': 'C25/30', 'length_code': 50, 'h_min': 160, 'h_max': 300,
             'vrd': cap, 'code': code, 'diameter': '08', 'page': 0}
            for code, cap in [('0202', 100.), ('0302', 200.)]]}
        fixture = root / 'TEST_ONLY_hit.b64'
        fixture.write_bytes(base64.b64encode(gzip.compress(json.dumps(data).encode())))
        app.hit_db = hit_core.HitDatabase(fixture)
        app.main_notebook.select(app.hit_tab)
        app.shared_thermal_design.show_legacy()
        app.shared_thermal_design.show_hit_group('standard')
        row = hit_workspace.HitInputRow(app, 1, dict(name='TEST_ONLY EXE', connection_type='ZDX',
            series='HP', height='200', cover='30', concrete='C25/30', required_length='500',
            quantity='2', ved_pos='20', ved_neg='10', load_basis='per_element'))
        app.hit_rows.append(row); app.recalculate_hit_all(); pump(app)
        assert row.selected_candidate and hit_units_310.basis(row) == 'per_element'
        assert action_payload.save_action(app, as_new=True, forced_name='TEST_ONLY EXE roundtrip')
        store = action_payload.action_store(app); saved = store.load(app.action_id)
        action_payload.load_action_record(app, saved); pump(app)
        assert len(app.hit_rows) == 1 and hit_units_310.basis(app.hit_rows[0]) == 'per_element'
        rows = hit_export_ui.collect_hit_rows(app)
        assert rows[0]['actions_per_metre']['v_pos'] == 40
        hit_pdf.write_hit_proposal_pdf(root / 'probe.pdf', project_name='TEST_ONLY EXE', rows=rows)
        import pdfplumber
        with pdfplumber.open(root / 'probe.pdf') as pdf:
            assert 'kN/prvek' in '\n'.join(p.extract_text() or '' for p in pdf.pages)
            assert any(p.images for p in pdf.pages), 'TURTO PDF logo missing'
        hit_excel.write_hit_request_xlsx(root / 'probe.xlsx', action_name='TEST_ONLY EXE', rows=rows, include_statics=True)
        import openpyxl
        book = openpyxl.load_workbook(root / 'probe.xlsx', data_only=True)
        assert 'kN/prvek' in str(list(book['Statická data'].values)); book.close()
        # Real TLS support and PDF rasterizer DLL are bundled, not borrowed.
        import ssl, pypdfium2
        assert ssl.create_default_context().cert_store_stats()['x509'] > 0
        pdf = pypdfium2.PdfDocument(str(root / 'probe.pdf'))
        bitmap = pdf[0].render(scale=1); bitmap.to_pil().save(root / 'probe-pdf.png'); pdf.close()
        ImageGrab.grab().save(root / 'probe-window.png')
        assert not errors, errors
        (root / 'probe.json').write_text(json.dumps({'frozen': True, 'title': app.title(),
            'database': str(store.path), 'action_id': app.action_id,
            'checks': ['offline bootstrap', 'Tk icon and title', 'empty initial rows', 'HIT per element',
                       'SQLite roundtrip', 'PDF with logo', 'XLSX', 'TLS', 'PDF rasterizer']}), encoding='utf-8')
        app.destroy()


def update_probe(root):
    """Use the real updater + child EXE + automatic default EXE restart."""
    import runpy
    from unittest.mock import patch
    import tkinter as tk
    from tkinter import messagebox
    updater = runpy.run_path(str(root / 'updater.py'))
    # A deterministic local manifest uses the exact released bytes. Download and
    # replacement logic are unmodified; network discovery alone is substituted.
    source = root / 'TEST_ONLY_update'; source.mkdir()
    files = []
    for name in ('app.pyw', 'updater.py'):
        data = (root / name).read_bytes(); (source / name).write_bytes(data)
        files.append({'path': name, 'url': (source / name).as_uri(), 'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'version': VERSION, 'runtime_layout': LAYOUT, 'files': files}
    # urllib's file handler treats query strings literally; substitute transport,
    # keeping _download_checked, worker creation and transactional apply real.
    from urllib.parse import urlparse, unquote
    def download(url, **kwargs):
        return Path(unquote(urlparse(url).path).lstrip('/')).read_bytes()
    function = updater['check_and_update']
    function.__globals__['_load_manifest'] = lambda: manifest
    function.__globals__['_download'] = download
    app = tk.Tk(); app.withdraw()
    with patch.object(messagebox, 'askyesno', return_value=True), \
         patch.object(messagebox, 'showinfo', return_value=None), \
         patch.object(messagebox, 'showerror', side_effect=lambda *a, **k: (_ for _ in ()).throw(AssertionError(a))):
        function(app, '0.0.0'); app.mainloop()


def main():
    assert sys.platform == 'win32'
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    output = ROOT / 'build/windows/proof'; output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='TURTO český test ') as folder:
        root = Path(folder) / 'TURTO Statika'
        shutil.copytree(ROOT / 'dist/TURTO Statika', root)
        env = dict(os.environ, PATH=os.environ['SystemRoot'] + '\\System32',
                   APPDATA=str(root / 'TEST_ONLY_appdata'), LOCALAPPDATA=str(root / 'TEST_ONLY_localappdata'))
        env.pop('PYTHONPATH', None); env.pop('PYTHONHOME', None)
        exe = root / 'TURTO Statika.exe'
        try:
            subprocess.run([str(exe), '--run-script', str(Path(__file__).resolve()), '--probe', str(root)],
                           env=env, cwd=folder, check=True, timeout=120)
            proof = json.loads((root / 'probe.json').read_text(encoding='utf-8'))
            database = Path(proof['database']); before = database.read_bytes()
            process = subprocess.Popen([str(exe)], env=env, cwd=folder)
            try:
                _, _, title = wait_window(process.pid)
                proof['default_launch'] = title
            finally:
                process.terminate(); process.wait(timeout=10)
            subprocess.run([str(exe), '--run-script', str(Path(__file__).resolve()), '--update-probe', str(root)],
                           env=env, cwd=folder, check=True, timeout=60)
            hwnd, pid, title = wait_window()
            try:
                assert f'OK: TURTO {VERSION}' in (root / 'Logy/update_apply.log').read_text(encoding='utf-8')
                assert database.read_bytes() == before, 'Update changed existing AKCE'
                proof['update_restart'] = title; proof['database_preserved'] = True
            finally:
                # This PID belongs to the isolated test application just restarted.
                subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], check=True, capture_output=True)
            (output / 'windows-exe-test.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
            print(json.dumps(proof, indent=2))
        finally:
            for name in ('probe-window.png', 'probe-pdf.png', 'probe.pdf', 'probe.xlsx'):
                if (root / name).exists(): shutil.copy2(root / name, output / name)
            if (root / 'Logy').exists():
                shutil.copytree(root / 'Logy', output / 'Logy', dirs_exist_ok=True)
                for log in (root / 'Logy').glob('*.log'):
                    print(log.name + '\n' + log.read_text(encoding='utf-8', errors='replace')[-12000:])


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe': probe(Path(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == '--update-probe': update_probe(Path(sys.argv[2]))
    else: main()
