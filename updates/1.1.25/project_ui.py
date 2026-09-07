from __future__ import annotations

"""TURTO ISO 1.1.25 Decoder ISO UI polish over the 1.1.23 central-action layer."""

import project_ui_prev as _prev
from project_ui_prev import *  # noqa: F401,F403
from table_polish import install as _install_table_polish

_install_table_polish(_prev.ProjectWorkspaceMixin)
ProjectWorkspaceMixin = _prev.ProjectWorkspaceMixin
