"""One user-level collection setting, independent of the failure policy."""
import json
import os
from pathlib import Path

LEVELS = ("off", "observed", "full")


def settings_path():
    # A location override supports isolated installations/tests, not conversation modes.
    return Path(os.environ.get("SNAPGENE_TRACE_CONFIG") or
                Path.home() / ".snapgene-dna-design" / "trace.json").expanduser()


def get_level():
    path = settings_path()
    if not path.exists():
        return "full"
    data = json.loads(path.read_text(encoding="utf-8"))
    level = data.get("trace_level") if isinstance(data, dict) else None
    if level not in LEVELS:
        raise ValueError("trace_level must be off, observed or full")
    return level


def set_level(level):
    if level not in LEVELS:
        raise ValueError("trace_level must be off, observed or full")
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"trace_level": level}, indent=2) + "\n", encoding="utf-8")
    return path
