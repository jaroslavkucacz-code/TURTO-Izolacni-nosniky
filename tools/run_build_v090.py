from __future__ import annotations

import build_v090 as build

_original_replace_once = build.replace_once


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    # The ZVX/ZDX branch appears in several methods. In HitDatabase the first
    # occurrence is the directional branch where MVXL must be inserted.
    if label == "directional MVXL":
        if old not in text:
            raise RuntimeError(f"{label}: marker not found")
        return text.replace(old, new, 1)
    return _original_replace_once(text, old, new, label)


build.replace_once = _replace_once

if __name__ == "__main__":
    build.main()
