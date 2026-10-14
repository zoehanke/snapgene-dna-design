"""Discover the project-owned pilot checks in the ordinary repository suite."""
from repository_paths import PROJECT_ROOT
import sys
sys.path.insert(0,str(PROJECT_ROOT/'genome-revival-toolkit'))
from kits.identity.tests.test_contract import IdentityKitContractTests
