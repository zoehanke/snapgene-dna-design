# -*- coding: utf-8 -*-
"""scripts/construct_model.py - Backward-compatible re-export from core.models.construct_model."""
from __future__ import annotations

import pathlib
import sys

_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.models.construct_model as _cm

# Export all symbols (including internal helpers like _location, _parts, _part)
for _k, _v in _cm.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v
