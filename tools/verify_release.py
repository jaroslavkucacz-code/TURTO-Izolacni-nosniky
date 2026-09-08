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
    "app.pyw", "app_runtime.pyw", "platform_workspace.py", "hit_workspace.py",
    "hit_pdf.py", "updater.py", "RELEASE_NOTES.txt",
}
PROTECTED_TARGETS = {"actions.sqlite3"}


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


def assignment(text: str, name: str, quote: str = '"') -> str:
    escaped = re.escape(name)
    if quote == "'":
        pattern = rf"^\s*{escaped}\s*=\s*'([^']+)'\s*$"
    else:
        pattern = rf'^\s*{escaped}\s*=\s*"([^"]+)"\s*$'
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        fail(f"Chybí jednoznačné přiřazení {name}.")
    return match.group(1).strip()


def verify_bootstrap(
    version: str,
    runtime_layout: str,
    manifest_targets: dict[str, tuple[str, str, str]],
) -> None:
    release_dir = ROOT / "updates" / version
    bootstrap = release_dir / "app.pyw"
    installer = release_dir / "runtime_installer.py"
    if not bootstrap.is_file():
        fail(f"Chybí updates/{version}/app.pyw.")
    if not installer.is_file():
        fail(f"Chybí updates/{version}/runtime_installer.py.")

    text = bootstrap.read_text(encoding="utf-8")
    if assignment(text, "VERSION") != version:
        fail(f"updates/{version}/app.pyw nemá správné VERSION.")
    installer_commit = assignment(text, "INSTALLER_COMMIT").lower()
    installer_hash = assignment(text, "INSTALLER_SHA256").lower()
    bootstrap_layout = assignment(text, "RUNTIME_LAYOUT")
    if not COMMIT_RE.fullmatch(installer_commit):
        fail("Bootstrap INSTALLER_COMMIT není 40znakový commit SHA.")
    if not HEX64_RE.fullmatch(installer_hash):
        fail("Bootstrap INSTALLER_SHA256 není platný SHA-256.")
    if bootstrap_layout != runtime_layout:
        fail(
            f"Bootstrap RUNTIME_LAYOUT={bootstrap_layout!r}, ale manifest runtime_layout={runtime_layout!r}."
        )
    actual_installer_hash = sha256(installer)
    if actual_installer_hash != installer_hash:
        fail(
            "Bootstrap má jiný hash runtime_installer.py: "
            f"očekáváno {installer_hash}, lokálně {actual_installer_hash}."
        )

    app_target = manifest_targets.get("app.pyw")
    if app_target is None:
        fail("Manifest neobsahuje app.pyw.")
    _app_commit, app_hash, source = app_target
    if source != f"updates/{version}/app.pyw":
        fail(f"app.pyw v manifestu musí pocházet z updates/{version}/app.pyw.")
    if sha256(bootstrap) != app_hash:
        fail("Hash app.pyw v manifestu neodpovídá aktuálnímu bootstrapu.")


def verify_recovery(
    version: str,
    manifest_targets: dict[str, tuple[str, str, str]],
) -> None:
    recovery = ROOT / "OPRAVIT_TURTO.ps1"
    launcher = ROOT / "OPRAVIT_TURTO.bat"
    if not recovery.is_file() or not launcher.is_file():
        fail("Chybí OPRAVIT_TURTO.ps1 nebo OPRAVIT_TURTO.bat.")

    text = recovery.read_text(encoding="utf-8")
    if assignment(text, "$Version", quote="'") != version:
        fail("OPRAVIT_TURTO.ps1 nemá aktuální $Version.")
    if ".turto_runtime_current.ok" not in text:
        fail("Recovery nepoužívá současný runtime marker.")
    if "startup.log" not in text or "recovery.log" not in text:
        fail("Recovery musí používat obecné startup.log a recovery.log.")
    if "Invoke-WebRequest -UseBasicParsing" not in text:
        fail("Recovery musí používat Invoke-WebRequest -UseBasicParsing.")

    app = manifest_targets.get("app.pyw")
    updater = manifest_targets.get("updater.py")
    if app is None or updater is None:
        fail("Manifest musí obsahovat app.pyw a updater.py pro recovery.")
    app_commit, app_hash, _app_source = app
    updater_commit, updater_hash, _updater_source = updater

    if assignment(text, "$AppCommit", quote="'").lower() != app_commit:
        fail("Recovery $AppCommit neodpovídá manifestu.")
    if assignment(text, "$UpdaterCommit", quote="'").lower() != updater_commit:
        fail("Recovery $UpdaterCommit neodpovídá manifestu.")
    if assignment(text, "$AppSha256", quote="'").lower() != app_hash:
        fail("Recovery $AppSha256 neodpovídá manifestu.")
    if assignment(text, "$UpdaterSha256", quote="'").lower() != updater_hash:
        fail("Recovery $UpdaterSha256 neodpovídá manifestu.")

    batch_text = launcher.read_text(encoding="utf-8", errors="replace")
    if "recovery.log" not in batch_text:
        fail("OPRAVIT_TURTO.bat neodkazuje na obecný recovery.log.")


def verify_updater_protection(manifest_targets: dict[str, tuple[str, str, str]]) -> None:
    updater = manifest_targets.get("updater.py")
    if updater is None:
        fail("Manifest neobsahuje updater.py.")
    _commit, _expected, source = updater
    path = ROOT / source
    text = path.read_text(encoding="utf-8")
    if 'PROTECTED_TARGETS = {"actions.sqlite3"}' not in text:
        fail("Aktuální updater nemá výslovnou ochranu actions.sqlite3.")
    for token in (".update_backup", "rollback", "os.replace"):
        if token not in text:
            fail(f"Aktuálnímu updateru chybí prvek transakční aktualizace: {token}")


def verify_manifest() -> tuple[str, str, dict[str, tuple[str, str, str]]]:
    manifest = load_json(MANIFEST)
    version = str(manifest.get("version", "")).strip()
    if not SEMVER_RE.fullmatch(version):
        fail(f"Neplatná verze v manifestu: {version!r}")
    if VERSION_FILE.is_file():
        repo_version = VERSION_FILE.read_text(encoding="utf-8").strip()
        if repo_version != version:
            fail(f"CURRENT_VERSION={repo_version!r}, ale manifest={version!r}")

    runtime_layout = str(manifest.get("runtime_layout", "")).strip()
    if not runtime_layout:
        fail("Manifest musí obsahovat neprázdné runtime_layout.")

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
        preserve = contract.get("preserve")
        if preserve is not None:
            if not isinstance(preserve, list) or not all(isinstance(x, str) for x in preserve):
                fail("release_contract.json: preserve musí být seznam řetězců.")
            if "actions.sqlite3" not in preserve:
                fail("release_contract.json musí výslovně chránit actions.sqlite3.")

    items = manifest.get("files")
    if not isinstance(items, list) or not items:
        fail("Manifest neobsahuje žádné soubory.")

    seen: set[str] = set()
    targets: dict[str, tuple[str, str, str]] = {}
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            fail(f"Manifest files[{index}] není objekt.")
        target = str(item.get("path", "")).replace("\\", "/").strip()
        rel = Path(target)
        if not target or rel.is_absolute() or ".." in rel.parts:
            fail(f"Neplatná cílová cesta v manifestu: {target!r}")
        if target in PROTECTED_TARGETS:
            fail(f"Manifest se pokouší aktualizovat chráněný soubor: {target}")
        if target in seen:
            fail(f"Duplicitní cílová cesta v manifestu: {target}")
        seen.add(target)

        expected = str(item.get("sha256", "")).lower().strip()
        if not HEX64_RE.fullmatch(expected):
            fail(f"Neplatné SHA-256 pro {target}: {expected!r}")
        commit, source = raw_source(str(item.get("url", "")))
        local_source = ROOT / source
        if not local_source.is_file():
            fail(f"Zdroj release URL není v aktuálním stromu: {source}")
        actual = sha256(local_source)
        if actual != expected:
            fail(
                f"SHA-256 nesouhlasí pro {target}: očekáváno {expected}, "
                f"lokálně {actual} ({source})"
            )
        targets[target] = (commit, expected, source)

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

    return version, runtime_layout, targets


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
        version, runtime_layout, targets = verify_manifest()
        verify_bootstrap(version, runtime_layout, targets)
        verify_recovery(version, targets)
        verify_updater_protection(targets)
        verify_repository_hygiene()
    except VerificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: TURTO {version} – manifest, bootstrap, recovery, rollback, "
        "SHA-256, syntax a repo hygiene."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
