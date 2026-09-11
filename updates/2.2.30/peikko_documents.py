"""On-demand, hash-verified local manufacturer PDFs. No network at app startup."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import queue
import tempfile
import threading
import urllib.parse
import urllib.request
import webbrowser

MAX_PDF_BYTES = 60_000_000

def _trusted(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == 'media.peikko.com' and not parsed.username

class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _trusted(newurl): raise ValueError('Neočekávané přesměrování zdrojového PDF.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch_document(folder: Path, source: dict, *, opener=None) -> Path:
    """Atomic cache write; corrupt/changed PDFs never replace a verified edition."""
    url=source['url'];expected=source['sha256']
    if not _trusted(url) or len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('Neplatný zdroj katalogu Peikko.')
    folder=Path(folder);folder.mkdir(parents=True, exist_ok=True)
    # SHA-derived filename cannot escape cache directory or confuse revisions.
    name=('TEBEA_ETA_' if 'ETA' in source['title'].upper() else 'EBEA_Manual_')+expected[:12]+'.pdf'
    target=folder/name
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==expected: return target
    open_url=opener or urllib.request.build_opener(_Redirects()).open
    temp=None
    try:
        request=urllib.request.Request(url, headers={'User-Agent':'TURTO/2.2.30 Peikko-source-cache'})
        with open_url(request, timeout=45) as response, tempfile.NamedTemporaryFile(dir=folder, suffix='.part', delete=False) as stream:
            temp=Path(stream.name);size=0;digest=hashlib.sha256();prefix=b''
            while True:
                block=response.read(1024*1024)
                if not block:break
                if not prefix:prefix=block[:5]
                size+=len(block)
                if size>MAX_PDF_BYTES:raise ValueError('Zdrojové PDF překročilo limit velikosti.')
                digest.update(block);stream.write(block)
        if prefix!=b'%PDF-' or digest.hexdigest()!=expected:
            raise ValueError('PDF neodpovídá ověřené revizi. Soubor nebyl použit; kontaktujte správce katalogových dat.')
        os.replace(temp,target);temp=None
        return target
    finally:
        if temp is not None: temp.unlink(missing_ok=True)

def open_source_async(owner, button, source):
    from tkinter import messagebox
    import runtime_paths
    root=runtime_paths.catalog_root() / 'Peikko'
    result=queue.Queue(maxsize=1)
    button.configure(state='disabled', text='Ověřuji / stahuji PDF…')
    def worker():
        try: result.put((True,fetch_document(root,source)))
        except Exception as exc:result.put((False,str(exc)))
    threading.Thread(target=worker, daemon=True, name='Peikko-PDF-cache').start()
    def poll():
        try: ok,value=result.get_nowait()
        except queue.Empty:
            owner.after(100,poll);return
        button.configure(state='normal', text='Zdrojové PDF (lokální)')
        if not ok:
            messagebox.showerror('Zdroj Peikko', value, parent=owner);return
        try:
            if os.name=='nt':os.startfile(str(value))
            elif not webbrowser.open(value.resolve().as_uri()):
                messagebox.showinfo('Zdroj Peikko', 'PDF je uložené zde:\n'+str(value), parent=owner)
        except OSError as exc:messagebox.showerror('Otevření PDF',str(exc),parent=owner)
    owner.after(100,poll)
