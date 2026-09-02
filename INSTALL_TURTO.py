from __future__ import annotations
import base64, io, os, sys, urllib.request, zipfile
from pathlib import Path

REPO_RAW = 'https://raw.githubusercontent.com/jaroslavkucacz-code/TURTO-Izolacni-nosniky/main'
PARTS = 17
OUT_DIR = Path.home() / 'Documents' / 'TURTO-Izolacni-nosniky'

def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent':'TURTO-Installer'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def main():
    print('TURTO - instalace z GitHubu')
    print('Stahuji instalační data...')
    chunks=[]
    for i in range(1, PARTS+1):
        print(f'  část {i}/{PARTS}')
        chunks.append(get(f'{REPO_RAW}/installer_parts/part_{i:03d}.txt').decode('ascii'))
    payload = base64.b64decode(''.join(chunks))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload), 'r') as z:
        z.extractall(OUT_DIR)
    print(f'Hotovo. Program je v: {OUT_DIR}')
    launcher = OUT_DIR / 'Spustit_program.vbs'
    if launcher.exists():
        try:
            os.startfile(str(launcher))
        except Exception:
            pass
    input('Stiskněte Enter pro ukončení instalátoru...')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('\nCHYBA:', exc)
        input('Stiskněte Enter...')
        raise
