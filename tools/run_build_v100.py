from __future__ import annotations

import build_v100 as build

_original_decompress = build.gzip.decompress


def _decompress_with_ft_zero(data: bytes) -> bytes:
    raw = _original_decompress(data)
    text = raw.decode("utf-8")
    # FT compression interaction tables include the origin N/M=0, NRd=0.
    # The compact embedded source starts at |N/M|=2; add the origin so
    # linear interpolation 0..2 is available and pure small-N cases work.
    text = text.replace('"HP": {-2:', '"HP": {0:(0,0,0,0),-2:', 1)
    text = text.replace('"SP": {-2:', '"SP": {0:(0,0,0,0),-2:', 1)
    return text.encode("utf-8")


build.gzip.decompress = _decompress_with_ft_zero

if __name__ == "__main__":
    build.main()
