"""Compare catalogue values, search results and idle RAM in isolated real GUIs.

On Windows this runs inside the actual frozen EXE, without Python on PATH.
Only the catalogue engine differs between the two disposable installations.
"""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def memory_mb():
    if sys.platform == 'win32':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
                'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        values = Counters(); values.cb = ctypes.sizeof(values)
        assert psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(values), values.cb)
        return dict(rss=round(values.WorkingSetSize / 2**20, 2), private=round(values.PrivateUsage / 2**20, 2))
    status = Path('/proc/self/status').read_text().splitlines()
    return dict(rss=round(int(next(s for s in status if s.startswith('VmRSS:')).split()[1]) / 1024, 2))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def probe(root, label):
    from unittest.mock import patch
    from tkinter import messagebox
    os.environ.update(TURTO_ROOT=str(root), TURTO_PROGRAM_DIR=str(root / 'Program'))
    sys.path.insert(0, str(root / 'Program'))
    started = time.perf_counter()
    runtime = runpy.run_path(str(root / 'Program/app_runtime.pyw'))
    if label == '312':
        import catalog_engine
        catalog_engine.CatalogDatabase._ensure_suggestion_index = lambda self: None
    with patch.object(messagebox, 'showerror', side_effect=lambda *a, **k: (_ for _ in ()).throw(AssertionError(a))), \
         patch.object(messagebox, 'showinfo', return_value=None), \
         patch.object(messagebox, 'showwarning', return_value=None):
        app = runtime['_base'].ThermalConnectorApp()
        app.update()
        report = dict(label=label, startup_seconds=round(time.perf_counter()-started, 3), initial=memory_mb())
        cpu = time.process_time(); until = time.monotonic()+3
        while time.monotonic() < until:
            app.update(); time.sleep(.02)
        report.update(idle_cpu_seconds=round(time.process_time()-cpu, 3), idle=memory_mb())
        database = app.database
        while hasattr(database, 'base'):
            database = database.base
        assert type(database).__module__ == 'catalog_engine'
        assert not database.load_errors, database.load_errors
        if label == '313':
            assert database._suggestion_index_ready, 'Prepare the final index before editing'
        ready_entries = database._suggestion_entries
        # Hash ALL values, including capacities, units, sources and shared matrices.
        # Both copies use different paths; remove only the filesystem metadata.
        catalogue_hash = hashlib.sha256()
        encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=False)
        for family in database.families:
            normalized = dict(family, catalog={k: v for k, v in family['catalog'].items() if k != '_data_file'})
            for chunk in encoder.iterencode(normalized):
                catalogue_hash.update(chunk.encode())
        report['catalogue_sha256'] = catalogue_hash.hexdigest()
        queries = []
        for family in database.families:
            records = family.get('records', [])
            if records:
                for record in (records[0], records[-1]):
                    queries.append((record['designation'], None, None))
                    queries.extend((alias, None, None) for alias in record.get('aliases', [])[:1])
        answers = []
        def search(text, catalog=None, concrete=None):
            return [(s.designation, s.score, s.result.record, s.result.family['catalog_id'])
                    for s in database.suggest_designations(text, catalog, concrete)]
        answers.append(search(*queries[0]))
        if label == '313':
            assert database._suggestion_entries is ready_entries, 'Exact query must reuse the index'
        started = time.perf_counter()
        answers.append(search('egcobx'))
        report['first_fuzzy_seconds'] = round(time.perf_counter()-started, 3)
        assert database._suggestion_entries is ready_entries, 'First fuzzy query must reuse the index'
        for query in queries:
            answers.append(search(*query))
        for text in ('', 'X', 'AIPQ60', 'Isopro A-IPQ 60 H200', 'VM 130', 'egcobx',
                     'T-QP-VV1-REI120-H200-L300-5.0', 'KL-U', 'T KL M2', 'Maxfran', 'aipq', 'zzzzz'):
            for concrete in (None, 'C25/30'):
                answers.append(search(text, concrete=concrete))
        catalog_id = next(iter(database.catalogs))
        answers.append(search('egcobx', catalog_id))
        report.update(query_count=len(answers), answers_sha256=digest(answers), after_search=memory_mb())
        # New records invalidate the cache after extensions; rebuild must include them.
        if label == '313':
            import copy
            family = next(f for f in database.families if f.get('records'))
            record = copy.deepcopy(family['records'][0])
            record.update(designation='TEST_ONLY_UNIQUE_MEMORY_SENTINEL', aliases=[])
            family['records'].append(record)
            database._build_suggestion_index()
            result = search('MEMORY SENTINEL')
            assert any(r[0] == record['designation'] for r in result), result
            family['records'].pop()
            database._build_suggestion_index()
            assert not any(r[0] == record['designation'] for r in search('MEMORY SENTINEL'))
        app.destroy()
    (root / 'memory.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def main():
    frozen = sys.platform == 'win32'
    source = ROOT / ('dist/TURTO Statika' if frozen else 'build/windows/application')
    output = ROOT / 'build/windows/proof'; output.mkdir(parents=True, exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix='turto-memory-') as folder:
        if frozen:
            # Prove that the online update also runs in the already-released
            # 3.0.12 host; a new frozen dependency must not break existing EXEs.
            import urllib.request
            import zipfile
            archive = Path(folder) / '312.zip'
            urllib.request.urlretrieve('https://github.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/releases/download/v3.0.12/TURTO-Statika-3.0.12-Windows-x64.zip', archive)
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == '6c8d6d9b618b1acffe880b5789919081b32939eccdade4b4a93e386fe735ee38'
            with zipfile.ZipFile(archive) as package:
                package.extractall(Path(folder)/'host312')
            old_host = Path(folder)/'host312/TURTO Statika'
        for label, engine in [('312', 'updates/1.1.17/catalog_engine.py'), ('313', None)]:
            root = Path(folder) / label
            shutil.copytree(source, root)
            if frozen:
                shutil.copy2(old_host/'TURTO Statika.exe', root/'TURTO Statika.exe')
                shutil.rmtree(root/'_internal')
                shutil.copytree(old_host/'_internal', root/'_internal')
            if engine:
                shutil.copy2(ROOT / engine, root / 'Program/catalog_engine.py')
            # Give both engine representations the same restored manufacturer
            # data in the same order; the old engine predates bundled fallback.
            for name in ('isopro_2018_en.json.gz.b64','schoeck_cz_2024_1_2024_09.json.gz.b64'):
                if (root/'Program'/name).is_file():
                    shutil.copy2(root/'Program'/name, root/'catalogs'/name)
            for cache in (root / 'Program').rglob('__pycache__'):
                shutil.rmtree(cache)
            env = dict(os.environ, APPDATA=str(root/'TEST_ONLY_appdata'),
                       LOCALAPPDATA=str(root/'TEST_ONLY_localappdata'), XDG_CONFIG_HOME=str(root/'TEST_ONLY_config'),
                       PYTHONHASHSEED='0')
            env.pop('PYTHONPATH', None); env.pop('PYTHONHOME', None)
            if frozen:
                env['PATH'] = os.environ['SystemRoot'] + '\\System32'
                command = [str(root/'TURTO Statika.exe'), '--run-script']
            else:
                command = [sys.executable]
            try:
                subprocess.run(command + [str(Path(__file__).resolve()), '--probe', str(root), label],
                               env=env, check=True, timeout=180)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                for log in (root/'Logy').glob('*.log'):
                    print(log.read_text(encoding='utf-8', errors='replace')[-12000:], flush=True)
                raise
            results[label] = json.loads((root/'memory.json').read_text(encoding='utf-8'))
            print(json.dumps(results[label]), flush=True)
    old, new = results['312'], results['313']
    assert old['catalogue_sha256'] == new['catalogue_sha256'], results
    assert old['answers_sha256'] == new['answers_sha256'], results
    assert new['idle']['rss'] < old['idle']['rss'] * .75, results
    assert new['after_search']['rss'] < old['after_search']['rss'] * .8, results
    (output/'memory-313.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('Identical catalogues/search results; at least 25% lower idle RAM and 20% lower RAM after searching.')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe':
        probe(Path(sys.argv[2]), sys.argv[3])
    else:
        main()
