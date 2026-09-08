from __future__ import annotations

"""Statická kontrola vydání TURTO; používá pouze standardní knihovnu."""

import hashlib
import json
import py_compile
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "jaroslavkucacz-code/TURTO-Izolacni-nosniky"
MANIFEST = ROOT / "update_manifest.json"
VERSION_FILE = ROOT / "CURRENT_VERSION"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_ROOT_PATHS = (
    "ACCESS_OK.txt", "AKTUALIZOVAT_Z_V040.py", "HIT_INSTALOVAT.bat",
    "dist17", "hit", "installer_parts", "package_parts", "payload",
    "payload_tail", "release_builder_fixes", "release_builder_parts",
    "release_code_payloads", "upgrade_v040",
)
DEFAULT_REQUIRED_TARGETS = {
    "app_runtime.pyw", "platform_workspace.py", "hit_workspace.py",
    "hit_pdf.py", "updater.py", "RELEASE_NOTES.txt",
}

class VerificationError(RuntimeError):
    pass

def fail(message: str) -> None:
    raise VerificationError(message)

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Nelze načíst JSON {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} musí obsahovat JSON objekt.")
    return value

def raw_source(url: str) -> tuple[str, str]:
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or parsed.netloc != "raw.githubusercontent.com":
        fail(f"Release URL musí používat HTTPS raw.githubusercontent.com: {url}")
    parts = [part for part in parsed.path.split("/") if part]
    expected_prefix = REPOSITORY.split("/")
    if len(parts) < 4 or parts[:2] != expected_prefix:
        fail(f"Release URL nepatří do {REPOSITORY}: {url}")
    commit = parts[2].lower()
    if not COMMIT_RE.fullmatch(commit):
        fail(f"Release URL musí být připnutá na 40znakový commit SHA: {url}")
    source = "/".join(parts[3:])
    if not source or ".." in Path(source).parts:
        fail(f"Neplatná zdrojová cesta v URL: {url}")
    return commit, source

def verify_manifest() -> str:
    manifest = load_json(MANIFEST)
    version = str(manifest.get("version", "")).strip()
    if not SEMVER_RE.fullmatch(version):
        fail(f"Neplatná verze v manifestu: {version!r}")
    if VERSION_FILE.is_file():
        repo_version = VERSION_FILE.read_text(encoding="utf-8").strip()
        if repo_version != version:
            fail(f"CURRENT_VERSION={repo_version!r}, ale manifest={version!r}")
    release_dir = ROOT / "updates" / version
    if not release_dir.is_dir():
        fail(f"Chybí release adresář updates/{version}.")
    required_targets = set(DEFAULT_REQUIRED_TARGETS)
    contract_path = release_dir / "release_contract.json"
    if contract_path.is_file():
        contract = load_json(contract_path)
        if str(contract.get("version", "")).strip() != version:
            fail("release_contract.json má jinou verzi než manifest.")
        configured = contract.get("required_targets")
        if configured is not None:
            if not isinstance(configured, list) or not all(isinstance(x, str) for x in configured):
                fail("release_contract.json: required_targets musí být seznam řetězců.")
            required_targets.update(configured)
    items = manifest.get("files")
    if not isinstance(items, list) or not items:
        fail("Manifest neobsahuje žádné soubory.")
    seen: set[str] = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            fail(f"Manifest files[{index}] není objekt.")
        target = str(item.get("path", "")).replace("\\", "/").strip()
        rel = Path(target)
        if not target or rel.is_absolute() or ".." in rel.parts:
            fail(f"Neplatná cílová cesta v manifestu: {target!r}")
        if target in seen:
            fail(f"Duplicitní cílová cesta v manifestu: {target}")
        seen.add(target)
        expected = str(item.get("sha256", "")).lower().strip()
        if not HEX64_RE.fullmatch(expected):
            fail(f"Neplatné SHA-256 pro {target}: {expected!r}")
        _commit, source = raw_source(str(item.get("url", "")))
        local_source = ROOT / source
        if not local_source.is_file():
            fail(f"Zdroj release URL není v aktuálním stromu: {source}")
        actual = sha256(local_source)
        if actual != expected:
            fail(f"SHA-256 nesouhlasí pro {target}: očekáváno {expected}, lokálně {actual} ({source})")
    missing = sorted(required_targets - seen)
    if missing:
        fail("Manifest neobsahuje povinné cílové soubory: " + ", ".join(missing))
    app_runtime = release_dir / "app_runtime.pyw"
    if app_runtime.is_file() and f'APP_VERSION = "{version}"' not in app_runtime.read_text(encoding="utf-8"):
        fail(f"updates/{version}/app_runtime.pyw nemá správné APP_VERSION.")
    if not (release_dir / "RELEASE_NOTES.txt").is_file():
        fail(f"Chybí updates/{version}/RELEASE_NOTES.txt.")
    for path in sorted(release_dir.iterdir()):
        if path.suffix.lower() in {".py", ".pyw"}:
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                fail(f"Syntax chyba v {path.relative_to(ROOT)}: {exc}")
    return version

def verify_repository_hygiene() -> None:
    present = [name for name in FORBIDDEN_ROOT_PATHS if (ROOT / name).exists()]
    if present:
        fail("Historické/dočasné soubory se vrátily do kořene: " + ", ".join(present))
    workflows = ROOT / ".github" / "workflows"
    workflow_names = sorted(
        path.name for path in workflows.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    ) if workflows.is_dir() else []
    if workflow_names != ["ci.yml"]:
        fail(f"Má existovat právě .github/workflows/ci.yml; nalezeno: {workflow_names}")
    if not (ROOT / "legacy" / "migration_v051" / "AKTUALIZOVAT_Z_V040.py").is_file():
        fail("Chybí legacy/migration_v051/AKTUALIZOVAT_Z_V040.py.")
    for required in (ROOT / "docs" / "ARCHITECTURE.md", ROOT / "docs" / "RELEASE_PROCESS.md"):
        if not required.is_file():
            fail(f"Chybí {required.relative_to(ROOT)}.")

def main() -> int:
    try:
        version = verify_manifest()
        verify_repository_hygiene()
    except VerificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: TURTO {version} – manifest, SHA-256, syntax a repo hygiene.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
