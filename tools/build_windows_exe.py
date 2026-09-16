"""Build an offline portable Windows distribution from verified Git sources.

TURTO modules stay outside PyInstaller's archive so online updates take effect.
Only Python, standard library and third-party dependencies are frozen.
"""
from pathlib import Path
import ast
import base64
import hashlib
import io
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'CURRENT_VERSION').read_text().strip()
WORK = ROOT / 'build' / 'windows'
STAGE = WORK / 'application'
DIST = ROOT / 'dist' / 'TURTO Statika'


def git_source(request, *args, **kwargs):
    url = urlparse(getattr(request, 'full_url', str(request)))
    parts = url.path.strip('/').split('/')
    assert url.netloc == 'raw.githubusercontent.com' and parts[:2] == ['jaroslavkucacz-code', 'TURTO-Izolacni-nosniky'], url
    commit = parts[2]
    assert len(commit) == 40 and all(c in '0123456789abcdef' for c in commit)
    return io.BytesIO(subprocess.check_output(['git', 'show', commit + ':' + '/'.join(parts[3:])], cwd=ROOT))


def prepare():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    os.environ.update(TURTO_ROOT=str(STAGE), TURTO_PROGRAM_DIR=str(STAGE / 'Program'))
    shutil.copytree(ROOT / 'updates/1.1.17/catalogs', STAGE / 'catalogs')
    # Historical installers atomically rename from the temporary directory.
    # Windows CI has TEMP on C: and checkout on D:, so stage on the same volume.
    temporary = WORK / 'installer-temp'
    temporary.mkdir(parents=True, exist_ok=True)
    with patch('urllib.request.urlopen', git_source), patch.object(tempfile, 'tempdir', str(temporary)):
        installer = runpy.run_path(str(ROOT / f'updates/{VERSION}/runtime_installer.py'))
        installer['install_runtime'](STAGE)
    manifest = json.loads((ROOT / 'update_manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        data = git_source(item['url']).read()
        assert hashlib.sha256(data).hexdigest() == item['sha256']
        (STAGE / item['path']).write_bytes(data)
    (STAGE / '.turto_runtime_current.ok').write_text(manifest['runtime_layout'])
    (STAGE / 'version.txt').write_text(VERSION)
    assert runpy.run_path(str(STAGE / 'app.pyw'))['_runtime_ready']()
    # Copy only release-owned sources/data. Installer logs, settings and generated
    # databases must never be distributed to another person.
    for path in STAGE.rglob('__pycache__'):
        shutil.rmtree(path)
    from PIL import Image
    logo = Image.open(io.BytesIO(base64.b64decode((STAGE / 'Program/turto_icon_301.png.b64').read_bytes())))
    side = max(logo.size)
    icon = Image.new('RGBA', (side, side))
    icon.paste(logo, ((side-logo.width)//2, (side-logo.height)//2))
    icon.save(WORK / 'turto.ico', sizes=[(n, n) for n in (16, 32, 48, 64, 128, 256)])


def hidden_imports():
    files = list((STAGE / 'Program').glob('*.py*')) + [STAGE / 'app.pyw', STAGE / 'updater.py']
    own = {p.stem for p in files}
    imports = {'unittest.mock', 'tkinter', 'tkinter.ttk', 'sqlite3', 'ssl', 'encodings', 'ctypes.wintypes'}
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and not node.level else [])
            imports.update(n for n in names if n.split('.')[0] not in own and n != '__future__')
    return sorted(imports)


def main():
    assert sys.platform == 'win32', 'Windows EXE must be built on Windows.'
    prepare()
    number = tuple(int(n) for n in VERSION.split('.')) + (0,)
    (WORK / 'version_info.txt').write_text(f'''VSVersionInfo(
      ffi=FixedFileInfo(filevers={number!r}, prodvers={number!r}, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)),
      kids=[StringFileInfo([StringTable('040904B0', [
        StringStruct('CompanyName', 'TURTO'), StringStruct('FileDescription', 'TURTO Statika'),
        StringStruct('FileVersion', '{VERSION}'), StringStruct('ProductVersion', '{VERSION}'),
        StringStruct('ProductName', 'TURTO Statika'), StringStruct('OriginalFilename', 'TURTO Statika.exe')])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])])''', encoding='utf-8')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
               '--noupx', '--name', 'TURTO Statika', '--icon', str(WORK / 'turto.ico'),
               '--version-file', str(WORK / 'version_info.txt'), '--distpath', str(ROOT / 'dist'),
               '--workpath', str(WORK / 'pyinstaller'), '--specpath', str(WORK)]
    for name in hidden_imports():
        command += ['--hidden-import', name]
    for name in ('PIL', 'reportlab', 'openpyxl', 'pdfplumber'):
        command += ['--collect-all', name]
    command += [str(ROOT / 'packaging/windows/launcher.py')]
    subprocess.run(command, check=True)
    for name in ('Program', 'catalogs'):
        shutil.copytree(STAGE / name, DIST / name, dirs_exist_ok=True)
    for name in ('app.pyw', 'updater.py', 'RELEASE_NOTES.txt', 'version.txt', '.turto_runtime_current.ok'):
        shutil.copy2(STAGE / name, DIST / name)
    shutil.copy2(ROOT / 'packaging/windows/CTETE_ME.txt', DIST)
    # Preserve third-party license files in the redistributed runtime.
    import importlib.metadata
    licenses = DIST / 'Licence'
    for source in [Path(sys.base_prefix) / 'LICENSE.txt', *Path(sys.base_prefix).glob('tcl/**/license.terms')]:
        if source.is_file():
            destination = licenses / 'Python-Tcl-Tk' / source.relative_to(sys.base_prefix)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    for package in ('pyinstaller', 'Pillow', 'openpyxl', 'pdfplumber', 'reportlab',
                    'pdfminer.six', 'pypdfium2', 'cryptography', 'cffi', 'charset-normalizer', 'et_xmlfile'):
        distribution = importlib.metadata.distribution(package)
        for entry in distribution.files or []:
            if any(token in entry.name.lower() for token in ('license', 'licence', 'copying', 'notice')):
                source = Path(distribution.locate_file(entry))
                if source.is_file() and source.suffix.lower() not in ('.py', '.pyc'):
                    destination = licenses / package / Path(str(entry)).name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    # Do not replace the legacy VBS launcher or include customer files.
    assert not list(DIST.rglob('*.sqlite3'))
    assert not list(DIST.rglob('TEST_ONLY*'))
    (DIST / 'build-info.json').write_text(json.dumps({
        'product': 'TURTO Statika', 'version': VERSION, 'architecture': 'Windows x64',
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'python': sys.version,
    }, indent=2), encoding='utf-8')
    print(f'Built {DIST / "TURTO Statika.exe"}', flush=True)


if __name__ == '__main__':
    main()
