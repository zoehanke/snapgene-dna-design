"""Retain the established application and file receipt boundary."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from revival.bootstrap import CORE_VERSION
from revival.runner import run as legacy_run

def run(inputs,out_dir):
    return legacy_run('crispr',inputs['request_file'],inputs['context_file'],out_dir,
                      language=inputs.get('language','zh'),trace_mode=inputs.get('trace_mode','normal'))
