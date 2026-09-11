from __future__ import annotations
"""One-off reproducible pin builder for 2.2.30; run only on the release branch.

Requires a clean commit containing the finished 2.2.30 payload. Creates distinct
source -> installer -> bootstrap -> manifest commits, never pushes or merges.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'updates/2.2.29'
NEW=ROOT/'updates/2.2.30'
REPO='jaroslavkucacz-code/TURTO-Izolacni-nosniky'
BASE='e345a1a8d9e2a509dde698892c9cfbb0c4755a59'
FILES=('app_runtime.pyw','peikko_thermal_breaks.py','peikko_catalog.py','peikko_workspace.py',
       'peikko_technical.py','peikko_documents.py','peikko_technical_data.json.gz')

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def literal(text,key):
    for node in ast.parse(text).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==key for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Missing literal: '+key)

def assign(text,key,value):
    # Preserve exact byte content outside the selected top-level assignment.
    lines=text.splitlines(keepends=True)
    for node in ast.parse(text).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==key for t in node.targets):
            lines[node.lineno-1:node.end_lineno]=[key+' = '+repr(value)+'\n']
            return ''.join(lines)
    raise ValueError('Missing assignment: '+key)

def commit(message,paths):
    subprocess.run(['git','add','--',*paths],cwd=ROOT,check=True)
    subprocess.run(['git','-c','commit.gpgsign=false','commit','-m',message],cwd=ROOT,check=True)
    return git('rev-parse','HEAD')

def main():
    if git('status','--porcelain'):raise RuntimeError('Commit payload first; working tree must be clean.')
    if (NEW/'runtime_installer.py').exists():raise RuntimeError('Pins already prepared; do not overwrite frozen release.')
    source_commit=git('rev-parse','HEAD')
    payloads={name:(source_commit,'updates/2.2.30/'+name,sha(NEW/name)) for name in FILES}
    previous=(OLD/'runtime_installer.py').read_text(encoding='utf-8')
    old_required=literal(previous,'CURRENT_REQUIRED')
    installer=previous.replace('2.2.29','2.2.30').replace('2.2.28','2.2.29').replace('2_2_29','2_2_30').replace('turto_2229_','turto_2230_').replace('runtime_228.py','runtime_229.py')
    for key,value in dict(BASE_COMMIT=BASE,BASE_PATH='updates/2.2.29/runtime_installer.py',
        BASE_SHA256=sha(OLD/'runtime_installer.py'),PAYLOADS=payloads,
        PREVIOUS_REQUIRED=old_required,CURRENT_REQUIRED=tuple(dict.fromkeys(old_required+FILES))).items():
        installer=assign(installer,key,value)
    installer=installer.replace('assert len(PAYLOADS) == 4','assert len(PAYLOADS) == 7')
    (NEW/'runtime_installer.py').write_text(installer,encoding='utf-8')
    installer_commit=commit('Freeze 2.2.30 incremental installer and exact Peikko payload pins',['updates/2.2.30/runtime_installer.py'])
    bootstrap=(OLD/'app.pyw').read_text(encoding='utf-8').replace('2.2.29','2.2.30').replace('2_2_29','2_2_30')
    critical=literal(bootstrap,'CRITICAL_PROGRAM_SHA256');critical.update({name:entry[2] for name,entry in payloads.items()})
    # verify_release expects these scalar bootstrap pins in double quotes.
    bootstrap=assign(bootstrap,'CRITICAL_PROGRAM_SHA256',critical)
    bootstrap=re.sub(r'^INSTALLER_COMMIT = .*$',f'INSTALLER_COMMIT = "{installer_commit}"',bootstrap,flags=re.M)
    bootstrap=re.sub(r'^INSTALLER_SHA256 = .*$',f'INSTALLER_SHA256 = "{sha(NEW / "runtime_installer.py")}"',bootstrap,flags=re.M)
    (NEW/'app.pyw').write_text(bootstrap,encoding='utf-8')
    app_commit=commit('Freeze 2.2.30 bootstrap with installer and runtime SHA verification',['updates/2.2.30/app.pyw'])
    manifest=json.loads((ROOT/'update_manifest.json').read_text(encoding='utf-8'))
    manifest['version']='2.2.30'
    manifest['notes']='Peikko: ověřené tabulky EBEA-100/E-100/700, reference TEBEA ETA, přesné D/S11 a jednotky, tabulkové porovnání M/V bez automatického statického schválení. Zdrojové PDF lokálně s SHA kontrolou. Chrání databázi AKCE i dosavadní HIT/Ancon.'
    for item in manifest['files']:
        if item['path'] in ('app.pyw','RELEASE_NOTES.txt'):
            pin=app_commit if item['path']=='app.pyw' else source_commit
            item['url']=f'https://raw.githubusercontent.com/{REPO}/{pin}/updates/2.2.30/'+item['path']
            item['sha256']=sha(NEW/item['path'])
    (ROOT/'update_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'CURRENT_VERSION').write_text('2.2.30\n',encoding='utf-8')
    recovery=(ROOT/'OPRAVIT_TURTO.ps1').read_text(encoding='utf-8').replace('2.2.29','2.2.30').replace('TURTO-Recovery-2.2.28','TURTO-Recovery-2.2.30')
    for key,value in [('AppCommit',app_commit),('AppSha256',sha(NEW/'app.pyw'))]:
        recovery=re.sub(r'^\$'+key+r' = .*$',f"${key} = '{value}'",recovery,flags=re.M)
    (ROOT/'OPRAVIT_TURTO.ps1').write_text(recovery,encoding='utf-8')
    readme=(ROOT/'README.md').read_text(encoding='utf-8').replace('Aktuální vydání: TURTO 2.2.29','Aktuální vydání: TURTO 2.2.30')
    readme=readme.replace('Peikko: rozpoznání / předvýběr; bez ověřených únosností se nepotvrzuje statická záměna,',
        'Peikko: ověřené tabulky EBEA-100/E-100/700, součásti TEBEA ETA a omezené porovnání M/V; bez automaticky potvrzené statické záměny,\n- explicitní standardní D, jednotky na prvek / na metr se zatěžovací šířkou, lokální zdrojové PDF s SHA kontrolou,')
    (ROOT/'README.md').write_text(readme,encoding='utf-8')
    final=commit('TURTO 2.2.30: publish candidate manifest and matching recovery pins',['update_manifest.json','CURRENT_VERSION','OPRAVIT_TURTO.ps1','README.md'])
    print(json.dumps(dict(source_commit=source_commit,installer_commit=installer_commit,bootstrap_commit=app_commit,head=final,
        payload_bytes=sum((NEW/n).stat().st_size for n in FILES)),indent=2))

if __name__=='__main__':main()
