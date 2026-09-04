from __future__ import annotations

import build_v100 as build

_original_decompress = build.gzip.decompress
_original_replace_once = build.replace_once


def _decompress_with_ft_zero(data: bytes) -> bytes:
    raw = _original_decompress(data)
    text = raw.decode("utf-8")
    text = text.replace('"HP": {-2:', '"HP": {0:(0,0,0,0),-2:', 1)
    text = text.replace('"SP": {-2:', '"SP": {0:(0,0,0,0),-2:', 1)
    return text.encode("utf-8")


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if label == "special designations":
        marker = "    def designation(self) -> str:"
        pos = text.find(marker)
        if pos < 0:
            raise RuntimeError("Candidate.designation not found")
        hit = text.find(old, pos)
        if hit < 0:
            raise RuntimeError("special designation insertion point not found")
        return text[:hit] + new + text[hit + len(old):]
    if label == "module version":
        import re
        updated, count = re.subn(r'HIT_MODULE_VERSION = "[^"]+"', 'HIT_MODULE_VERSION = "1.0.0"', text, count=1)
        if count != 1:
            raise RuntimeError("HIT module version marker not found")
        return updated
    if label == "header anchors":
        if old not in text:
            raise RuntimeError("header anchor marker not found")
        return text.replace(old, new, 1)
    if label == "derived OU WU":
        corrected = '''        # Annex 2 gives the OD/WD design values in common tables headed OD.\n        # Therefore WD is the structural mirror variant of the verified OD record.\n        # For OU/WU the DoP explicitly states that capacities equal standard MVX.\n        if self.schema_version >= 4:\n            existing = {(r[0], r[1], int(r[2]), r[3], int(r[4]), r[5]) for r in self.records}\n            standard = [r for r in self.records if not r[3]]\n            od_records = [r for r in self.records if r[3] == "OD"]\n            derived = []\n            for r in standard:\n                for suffix in ("OU", "WU"):\n                    key = (r[0], r[1], int(r[2]), suffix, int(r[4]), r[5])\n                    if key not in existing:\n                        derived.append([r[0], r[1], int(r[2]), suffix, int(r[4]), r[5], *r[6:]])\n                        existing.add(key)\n            for r in od_records:\n                key = (r[0], r[1], int(r[2]), "WD", int(r[4]), r[5])\n                if key not in existing:\n                    derived.append([r[0], r[1], int(r[2]), "WD", int(r[4]), r[5], *r[6:]])\n                    existing.add(key)\n            self.records.extend(derived)\n\n'''
        if old not in text:
            raise RuntimeError("offset derivation marker not found")
        return text.replace(old, corrected + old, 1)
    return _original_replace_once(text, old, new, label)


build.gzip.decompress = _decompress_with_ft_zero
build.replace_once = _replace_once

if __name__ == "__main__":
    build.main()
    notes = build.OUT / "RELEASE_NOTES.txt"
    if notes.exists():
        text = notes.read_text(encoding="utf-8")
        text = text.replace(
            "OD/WD se načítají z vlastních DoP tabulek, OU/WU používají podle DoP statické hodnoty standardního MVX.",
            "OD se načítá z tabulek Annexu 2; WD používá podle DoP stejné tabulkové hodnoty jako OD. OU/WU používají statické hodnoty standardního MVX.",
        )
        notes.write_text(text, encoding="utf-8")
