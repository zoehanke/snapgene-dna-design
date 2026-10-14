"""Development-only paths; runtime modules do not depend on this file."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PROJECT_ROOT / "snapgene-dna-design"
TOOLS_ROOT = PROJECT_ROOT / "tools"
RUNTIME_SCRIPTS = SKILL_ROOT / "scripts"
TESTS_ROOT = PROJECT_ROOT / "tests"

for directory in (PROJECT_ROOT, SKILL_ROOT, RUNTIME_SCRIPTS, TOOLS_ROOT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
