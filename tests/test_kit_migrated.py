"""Discover owned sub-Skill tests without a second fixed Kit registry."""
from repository_paths import PROJECT_ROOT
import importlib.util
import sys
import unittest

sys.path.insert(0,str(PROJECT_ROOT/'genome-revival-toolkit'))


def load_tests(loader,tests,pattern):
    result=unittest.TestSuite()
    for path in sorted((PROJECT_ROOT/'genome-revival-toolkit/kits').glob('*/tests/test_migration.py')):
        spec=importlib.util.spec_from_file_location('migration_'+path.parents[1].name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        result.addTests(loader.loadTestsFromModule(module))
    return result
