"""Owned public migration cases; construction oracles do not call Core."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from kits.shared.tests.contract import KitContractCases

class OwnedContractTests(KitContractCases):
    kit=Path(__file__).resolve().parents[1]
    command='crispr'

# Do not discover the abstract base itself.
del KitContractCases
