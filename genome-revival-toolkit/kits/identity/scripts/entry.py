"""Adapt the existing complete application/receipt boundary to Kit API v1."""
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import url2pathname

TOOLKIT_ROOT = Path(__file__).resolve().parents[3]
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))
from revival.bootstrap import CORE_VERSION
from revival.runner import run as legacy_run, FIELDS, COMMON
from revival.context import ProjectContext
from revival.identity import run_identity
from core.tools.result import ToolResult


def run(inputs, out_dir):
    return legacy_run('identity', inputs['request_file'], inputs['context_file'], out_dir,
                      language=inputs.get('language', 'zh'),
                      trace_mode=inputs.get('trace_mode', 'normal'))


def assess(request: dict, context_uri: str):
    """Read given references and return the unchanged scoped analytical result."""
    unknown = set(request) - FIELDS['identity'] - COMMON
    if unknown:
        raise ValueError('Unsupported identity fields: ' + ', '.join(sorted(unknown)))
    address = urlsplit(context_uri)
    if address.scheme != 'file' or address.netloc not in ('', 'localhost'):
        raise ValueError('context_uri must identify a local file URI.')
    path = Path(url2pathname(address.path))
    context = ProjectContext.load(path)
    result = run_identity(request, context, path.resolve().parent)
    return ToolResult(analysis=result, checks=result['checks'])
