"""Compatibility import: unchanged scientific implementation lives in its Kit."""
import importlib
import sys

implementation = importlib.import_module('kits.crispr.scripts.selection')
# Preserve public callable identity and shared globals, including caller patches.
for value in vars(implementation).values():
    if callable(value) and getattr(value, '__module__', None) == implementation.__name__:
        value.__module__ = __name__
sys.modules[__name__] = implementation
