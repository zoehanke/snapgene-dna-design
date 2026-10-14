"""Locate one bundled Core or its documented sibling in the source checkout."""
from pathlib import Path
import sys

SKILL_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = SKILL_ROOT / 'vendor' / 'dna-design-core'
if not (CORE_ROOT / 'core').is_dir():
    CORE_ROOT = SKILL_ROOT.parent / 'snapgene-dna-design'
if not (CORE_ROOT / 'core').is_dir() or not (CORE_ROOT / 'VERSION').is_file():
    raise RuntimeError('DNA Core missing. Install the complete Toolkit package, not only its entry script.')
loaded = sys.modules.get('core')
if loaded is not None and Path(loaded.__file__).resolve().parent != (CORE_ROOT / 'core').resolve():
    raise RuntimeError('Another DNA Core is already loaded; use a fresh process with the Toolkit package.')
for directory in (CORE_ROOT, CORE_ROOT / 'scripts'):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
CORE_VERSION = (CORE_ROOT / 'VERSION').read_text(encoding='utf-8', errors='replace').strip()
