from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
for name in ("runtime_installer.py", "app.pyw", "RELEASE_NOTES.txt"):
    path = ROOT / "updates" / "2.2.17" / name
    if path.is_file():
        print(f"SHA256 {name} {hashlib.sha256(path.read_bytes()).hexdigest()}")
