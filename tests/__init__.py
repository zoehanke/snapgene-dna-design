"""Make direct test-module invocation use the same paths as discovery."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from . import repository_paths
