from __future__ import annotations

import build_v090 as build

_original_replace_once = build.replace_once


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    # The ZVX/ZDX branch also appears in Candidate.designation and in the
    # legacy candidates API. Insert MVXL specifically inside directional_candidates.
    if label == "directional MVXL":
        method_marker = "    def directional_candidates("
        method_pos = text.find(method_marker)
        if method_pos < 0:
            raise RuntimeError(f"{label}: directional_candidates not found")
        pos = text.find(old, method_pos)
        if pos < 0:
            raise RuntimeError(f"{label}: branch marker not found in directional_candidates")
        return text[:pos] + new + text[pos + len(old):]

    # The explanatory paragraph changed slightly between patch releases.
    # Keep the functional build independent of its exact long wording and
    # update only the stable type summary.
    if label == "help text":
        marker = "MVX = M−, V±; ZVX = pouze V+"
        if marker in text:
            text = text.replace(marker, "MVX/MVXL = M−, V±; ZVX = pouze V+", 1)
        return text

    return _original_replace_once(text, old, new, label)


build.replace_once = _replace_once

if __name__ == "__main__":
    build.main()
