from __future__ import annotations

import importlib.util
import sys

_original_module_from_spec = importlib.util.module_from_spec


def _module_from_spec(spec):
    module = _original_module_from_spec(spec)
    # dataclasses expects the executing module to be present in sys.modules.
    sys.modules[spec.name] = module
    return module


importlib.util.module_from_spec = _module_from_spec

import build_v092

if __name__ == "__main__":
    build_v092.main()
