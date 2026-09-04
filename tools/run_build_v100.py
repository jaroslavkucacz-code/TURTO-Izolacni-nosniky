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
    return _original_replace_once(text, old, new, label)


build.gzip.decompress = _decompress_with_ft_zero
build.replace_once = _replace_once

if __name__ == "__main__":
    build.main()
