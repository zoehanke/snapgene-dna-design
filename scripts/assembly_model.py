# -*- coding: utf-8 -*-
"""scripts/assembly_model.py - Backward-compatible re-export from core.models.assembly_model."""
from __future__ import annotations

import pathlib
import sys

_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.models.assembly_model as _am

# Export all symbols (including internal helpers)
for _k, _v in _am.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v
