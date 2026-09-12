from __future__ import annotations
"""Verified incremental HSD workflow repair. Never write actions.sqlite3."""
import hashlib
import os
from pathlib import Path
import runpy
import tempfile
import time
import urllib.request

VERSION = "2.2.36"
RUNTIME_LAYOUT = "21"
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
PAYLOAD_COMMIT = "fd3d85311e086c567b381bb89507422d6294a2cb"
BASE_COMMIT = "4b648ef95c8261150a9c1b4bf33bbc83e0f34794"
BASE_INSTALLER_SHA256 = "cd9e576a6a9ff331f4c821d4023af163feff3e3f9095b42aaff8ac8b1f98b0db"
# Full known 2.2.35 runtime digest (the base installer digest is distinct).
BASE_RUNTIME_SHA256 = "8e4c7e8b5ec4a56379e8fa7d1b44ac8a9c6bb8a4a94ac322c29ee1079d7b4290"
PAYLOADS = {
    "app_runtime.pyw": "4a8920c497177730214f01fdadf133b26899a385454c814bb49fc907753f8a3f",
    "shear_schedule_io_236.py": "1822fe73a0e09cd0e4f5d4b226a5fdde939ae372b92d2b7bbbbe3a46ed263647",
    "shear_workflow_236.py": "f52650bee99e82d41fc34bb9c283faf8cf88ee0979266963d98229991fd813e5",
    "hsd_windows_ocr.ps1": "b76a281f1b8eef02c7bbfc6aa4d4cc3c3f41b5abef814d49f526b9dff79babf3",
}
BASE_CRITICAL = {
    "app_runtime_234.pyw": "5576cdae794c9c8fd4f566573acb55bb5e687b5fbcc5c3f1fb521afc0cfcc883",
    "halfen_hsd_2026.py": "805f811bee2a8302c2c8ced979ecd2c26a3c92fbe6fd1024940a28dd98e617be",
    "shear_dowels_hsd_234.py": "299705a9091784ad88be8d38b6fdbdc69c1bc29d4baf813fb69030e1c11aadf7",
    "design_groups_restore.py": "8aa2b4507f96a8b34b2e79d266e9779732d1a38f29050f64b49a7ed75d00aea8",
}
MARKER = ".turto_runtime_2_2_36.ok"

def _matches(path, sha):
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha

def _base_ready(program):
    return all(_matches(program/n,s) for n,s in BASE_CRITICAL.items()) and any(
        _matches(program/n, BASE_RUNTIME_SHA256) for n in ("app_runtime.pyw", "app_runtime_235.pyw")) and all(
        (program/n).is_file() for n in ("runtime_paths.py","platform_workspace.py","shear_dowels_ui_215.py","shear_dowels_catalog.py","unified_schedule.py"))

def _revision_ok(program):
    return _base_ready(program) and _matches(program/"app_runtime_235.pyw",BASE_RUNTIME_SHA256) and all(
        _matches(program/n,s) for n,s in PAYLOADS.items()) and (program/MARKER).is_file() and (program/MARKER).read_text().strip()==VERSION

def _download(commit,path,sha):
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"
    last = None
    for attempt in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"TURTO-2.2.36","Cache-Control":"no-cache"})
            with urllib.request.urlopen(req,timeout=45) as response:
                data=response.read()
            if hashlib.sha256(data).hexdigest()!=sha:
                raise RuntimeError(f"Nesouhlasí kontrolní součet: {path}")
            return data
        except Exception as exc:
            last=exc
            if attempt<3: time.sleep(attempt+1)
    raise RuntimeError(f"Stažení ověřeného souboru selhalo: {path}\n{last}")

def install_runtime(root):
    root=Path(root).resolve();program=root/"Program"
    program.mkdir(parents=True,exist_ok=True)
    if _revision_ok(program):return program/"app_runtime.pyw"
    db=root/"actions.sqlite3";before=db.read_bytes() if db.exists() else None
    data={name:_download(PAYLOAD_COMMIT,f"updates/{VERSION}/{name}",sha) for name,sha in PAYLOADS.items()}
    if not _base_ready(program):
        with tempfile.TemporaryDirectory(prefix="turto_2236_base_") as folder:
            installer=Path(folder)/"installer.py"
            installer.write_bytes(_download(BASE_COMMIT,"updates/2.2.35/runtime_installer.py",BASE_INSTALLER_SHA256))
            runpy.run_path(str(installer))["install_runtime"](root)
    if not _base_ready(program):raise RuntimeError("Základ 2.2.35 se nepodařilo ověřit.")
    if not _matches(program/"app_runtime_235.pyw",BASE_RUNTIME_SHA256):
        data["app_runtime_235.pyw"]=(program/"app_runtime.pyw").read_bytes()
    backups={name:(program/name).read_bytes() if (program/name).exists() else None for name in data}
    try:
        for name,blob in data.items():
            fd,temp=tempfile.mkstemp(prefix=".hsd_",dir=program)
            try:
                with os.fdopen(fd,"wb") as f:f.write(blob)
                os.replace(temp,program/name)
            finally:
                if os.path.exists(temp):os.unlink(temp)
        if before is not None and db.read_bytes()!=before:raise RuntimeError("Kontrola ochrany databáze selhala.")
        (program/MARKER).write_text(VERSION,encoding="utf-8")
        if not _revision_ok(program):raise RuntimeError("Ověření runtime 2.2.36 selhalo.")
    except Exception:
        for name,blob in backups.items():
            if blob is None:(program/name).unlink(missing_ok=True)
            else:(program/name).write_bytes(blob)
        (program/MARKER).unlink(missing_ok=True)
        raise
    return program/"app_runtime.pyw"

def selftest():
    assert VERSION=="2.2.36"
    assert all(len(sha)==64 for sha in PAYLOADS.values())
    assert "actions.sqlite3" not in PAYLOADS
