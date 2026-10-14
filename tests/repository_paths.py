"""Load the shared repository layout for development tests."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from project_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
