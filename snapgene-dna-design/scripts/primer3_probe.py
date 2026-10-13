# -*- coding: utf-8 -*-
"""primer3_probe.py - Detect whether the optional Primer3 binding is usable.

primer3-py is an *optional* dependency. Its native extension can be missing,
broken, or even crash the interpreter at import time on some environments
(observed: access violation on this development machine for every available
wheel). Importing it directly in-process would therefore kill the caller, so
availability is probed in a **subprocess**: a crash only kills the probe.

Status values:

    available     primer3 imports and a smoke calc_tm() call succeeds
    not-installed import raises ImportError
    import-crash  the probe process died while importing primer3
                  (native extension failure - never silently assume usable)
    probe-error   probe could not be started / timed out

The result is cached per process. The probe result must always be surfaced
to the user as ``primer3_status``; an ``unavailable`` status means NO
Primer3-based claim may be made in the output.
"""
import os
import subprocess
import sys

_PROBE_CODE = (
    "import sys\n"
    "try:\n"
    "    import primer3\n"
    "except ImportError as e:\n"
    "    print('P3_IMPORT_ERROR: %r' % (e,))\n"
    "    sys.exit(3)\n"
    "try:\n"
    "    primer3.calc_tm('ACGTACGTACGTACGT')\n"
    "except Exception as e:\n"
    "    print('P3_CALC_ERROR: %r' % (e,))\n"
    "    sys.exit(4)\n"
    "print('P3_OK')\n"
    "sys.exit(0)\n"
)

_CACHE = {}


def probe_primer3(python=None, timeout=30):
    """Return (status, detail). Result is cached for the process lifetime."""
    key = python or sys.executable
    if key in _CACHE:
        return _CACHE[key]

    interpreter = python or sys.executable
    try:
        completed = subprocess.run(
            [interpreter, "-c", _PROBE_CODE],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        _CACHE[key] = ("probe-error", "probe timed out after %ds" % timeout)
        return _CACHE[key]
    except (OSError, ValueError) as error:
        _CACHE[key] = ("probe-error", "probe failed to start: %r" % (error,))
        return _CACHE[key]

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.returncode == 0 and "P3_OK" in stdout:
        _CACHE[key] = ("available", None)
        return _CACHE[key]
    if "P3_IMPORT_ERROR" in stdout:
        _CACHE[key] = ("not-installed", stdout.strip().splitlines()[-1][:200])
        return _CACHE[key]
    if "P3_CALC_ERROR" in stdout:
        _CACHE[key] = ("probe-error", stdout.strip().splitlines()[-1][:200])
        return _CACHE[key]
    # Native crash (negative / 0xC0000005 style exit codes) or unknown error.
    tail = (stderr or stdout).strip()[-300:]
    _CACHE[key] = ("import-crash",
                   "primer3 native extension crashed the probe process "
                   "(returncode=%s); last output: %s" % (completed.returncode, tail))
    return _CACHE[key]


def primer3_status():
    """Convenience: return just the status string for the current interpreter."""
    return probe_primer3()[0]


def is_available():
    return probe_primer3()[0] == "available"


if __name__ == "__main__":
    status, detail = probe_primer3()
    print("primer3_status: %s" % status)
    if detail:
        print("primer3_detail: %s" % detail)
