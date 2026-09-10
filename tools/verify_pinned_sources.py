from __future__ import annotations

"""Verify that every release pin resolves to the exact bytes at commit:path."""

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise VerificationError(f"{path.relative_to(ROOT)}: chybí literální přiřazení {name}")


def _git_bytes(commit: str, path: str) -> bytes:
    if not HEX40.fullmatch(str(commit).lower()):
        raise VerificationError(f"Neplatný commit SHA: {commit}")
    rel = str(path).replace("\\", "/").strip("/")
    if not rel or ".." in Path(rel).parts:
        raise VerificationError(f"Neplatná cesta v pinu: {path!r}")
    try:
        return subprocess.check_output(
            ["git", "show", f"{commit}:{rel}"],
            cwd=ROOT,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise VerificationError(
            f"Pin neexistuje v historii: {commit}:{rel}" + (f" ({detail})" if detail else "")
        ) from exc


def _verify_pin(label: str, commit: str, path: str, expected: str) -> None:
    expected = str(expected).lower()
    if not HEX64.fullmatch(expected):
        raise VerificationError(f"{label}: neplatné SHA-256 {expected!r}")
    data = _git_bytes(str(commit).lower(), path)
    actual = _sha256(data)
    if actual != expected:
        raise VerificationError(
            f"{label}: SHA-256 nesouhlasí pro {commit}:{path}; "
            f"očekáváno {expected}, v historii {actual}"
        )


def _raw_pin(url: str) -> tuple[str, str]:
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or parsed.netloc != "raw.githubusercontent.com":
        raise VerificationError(f"Neplatná raw URL: {url}")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5 or parts[0:2] != ["jaroslavkucacz-code", "TURTO-Izolacni-nosniky"]:
        raise VerificationError(f"Raw URL nepatří do TURTO repozitáře: {url}")
    return parts[2].lower(), "/".join(parts[3:])


def _verify_manifest() -> str:
    manifest = json.loads((ROOT / "update_manifest.json").read_text(encoding="utf-8"))
    version = str(manifest.get("version", "")).strip()
    for item in manifest.get("files", []):
        target = str(item.get("path", ""))
        commit, source = _raw_pin(str(item.get("url", "")))
        _verify_pin(f"manifest {target}", commit, source, str(item.get("sha256", "")))
    return version


def _verify_bootstrap(version: str) -> Path:
    release = ROOT / "updates" / version
    app = release / "app.pyw"
    installer = release / "runtime_installer.py"
    if not app.is_file() or not installer.is_file():
        raise VerificationError(f"Chybí bootstrap nebo installer pro {version}.")

    commit = str(_literal(app, "INSTALLER_COMMIT")).lower()
    expected = str(_literal(app, "INSTALLER_SHA256")).lower()
    _verify_pin(
        "bootstrap installer",
        commit,
        f"updates/{version}/runtime_installer.py",
        expected,
    )
    if _sha256(installer.read_bytes()) != expected:
        raise VerificationError("Lokální runtime_installer.py neodpovídá bootstrap hash pinu.")
    return installer


def _verify_runtime_installer(installer: Path) -> None:
    base_commit = str(_literal(installer, "BASE_COMMIT")).lower()
    base_path = str(_literal(installer, "BASE_PATH"))
    base_hash = str(_literal(installer, "BASE_SHA256")).lower()
    _verify_pin("BASE installer", base_commit, base_path, base_hash)

    payloads = _literal(installer, "PAYLOADS")
    if not isinstance(payloads, dict) or not payloads:
        raise VerificationError("PAYLOADS musí být neprázzdný slovník.")
    for local, value in payloads.items():
        if not isinstance(value, tuple) or len(value) != 3:
            raise VerificationError(f"PAYLOADS[{local!r}] nemá tvar (commit, path, sha256).")
        commit, source, expected = value
        _verify_pin(f"runtime payload {local}", str(commit).lower(), str(source), str(expected).lower())


def main() -> int:
    try:
        shallow = subprocess.check_output(
            ["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, text=True
        ).strip().lower()
        if shallow == "true":
            raise VerificationError(
                "Repozitář je shallow; pinned-source kontrola vyžaduje checkout s fetch-depth: 0."
            )
        version = _verify_manifest()
        installer = _verify_bootstrap(version)
        _verify_runtime_installer(installer)
    except (VerificationError, subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"OK: TURTO {version} – manifest, bootstrap, BASE a všechny runtime PAYLOADS "
        "existují na připnutých commit:path a mají správné SHA-256."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
