# -*- coding: utf-8 -*-
"""Compatibility import for the shared Core Primer3 process backend."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.tools import primer3_backend as _backend

# One module identity preserves existing CLI imports and injected test doubles.
sys.modules[__name__] = _backend
