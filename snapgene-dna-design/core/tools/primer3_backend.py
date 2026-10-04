# -*- coding: utf-8 -*-
"""Safe external-process integration for the official Primer3 engine.

This module never imports ``primer3-py``.  It discovers and executes the
``primer3_core`` command-line program, exchanges Boulder-IO records, and maps
the returned primer pairs into the JSON objects used by design_primers.py.
Keeping Primer3 in a child process prevents a native crash from terminating
the DNA-design tool itself.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys


class Primer3CoreError(RuntimeError):
    """Raised when primer3_core cannot complete or returns invalid output."""
    def __init__(self,message,error_code='BACKEND_EXECUTION_FAILED'):
        super().__init__(message)
        self.error_code=error_code


def check_complete_oligo_pair(forward, reverse=None, core_path=None, annealing_temperature=None):
    """Measure complete oligos; omit reverse for an individual sequencing primer."""
    core_path = core_path or discover_primer3_core()
    if not core_path:
        raise Primer3CoreError("Full-oligo structural QC requires primer3_core",'BACKEND_UNAVAILABLE')
    lengths = [len(forward)] + ([len(reverse)] if reverse is not None else [])
    if max(lengths) > 60:
        raise Primer3CoreError("Primer3 cannot measure complete oligos above 60 nt; structural QC remains incomplete",'BACKEND_LIMIT_UNSUPPORTED')
    # A common partition satisfies the engine's core + overhang size limit.
    # Only structural metrics are used here; binding-core Tm is measured by
    # the design call on the real template, not on this bookkeeping partition.
    core_length = min(36, *lengths)
    parameters = {
        "PRIMER_TASK": "check_primers", "PRIMER_PICK_ANYWAY": 1,
        "SEQUENCE_PRIMER": forward[-core_length:],
        "SEQUENCE_OVERHANG_LEFT": forward[:-core_length],
        "PRIMER_MIN_SIZE": min(18, core_length),
        "PRIMER_OPT_SIZE": min(20, core_length), "PRIMER_MAX_SIZE": core_length,
        "PRIMER_SECONDARY_STRUCTURE_ALIGNMENT": 1,
    }
    sides = [("forward", "PRIMER_LEFT_0")]
    if reverse is None:
        parameters["PRIMER_PICK_RIGHT_PRIMER"] = 0
    else:
        parameters["SEQUENCE_PRIMER_REVCOMP"] = reverse[-core_length:]
        parameters["SEQUENCE_OVERHANG_RIGHT"] = reverse[:-core_length]
        sides.append(("reverse", "PRIMER_RIGHT_0"))
    raw = run_boulder(core_path, parameters)
    metrics = {}
    for side, prefix in sides:
        metrics[side] = {key: float(raw[prefix + suffix]) for key, suffix in (
            ("hairpin_tm", "_HAIRPIN_TH"), ("self_any_tm", "_SELF_ANY_TH"), ("self_end_tm", "_SELF_END_TH"))}
    if reverse is not None:
        metrics["pair"] = {"any_tm": float(raw["PRIMER_PAIR_0_COMPL_ANY_TH"]),
                           "end_tm": float(raw["PRIMER_PAIR_0_COMPL_END_TH"])}
    # 47 C is the Primer3 default for its usual design window, not a
    # temperature-independent biological cutoff. When the caller supplies
    # its planned annealing temperature, retain a 5 C structure margin.
    limit = 47.0 if annealing_temperature is None else float(annealing_temperature) - 5.0
    passed = all(value < limit for section in metrics.values() for value in section.values())
    return {"passed": passed, "scope": "complete oligos including all 5prime tails",
            "engine": "Primer3 check_primers", "metrics": metrics,
            "annealing_temperature_C": annealing_temperature, "structure_limit_C": limit,
            "conditions": {"monovalent_mM": 50, "divalent_mM": 1.5, "dNTP_mM": 0.6, "DNA_nM": 50}}


def _candidate_names():
    return ("primer3_core.exe", "primer3_core")


_DISCOVERED_CORE_CACHE: dict[str, str | None] = {}


def discover_primer3_core(explicit=None):
    """Return an absolute primer3_core path, or ``None``.

    Search order is intentionally deterministic: explicit CLI value, the
    PRIMER3_CORE environment variable, PATH, entries in sys.path, site-packages,
    and cross-environment Python installations (e.g. %LOCALAPPDATA%/Programs/Python).
    The wheel is inspected as files only; its native Python extension is never imported.
    """
    cache_key = str(explicit) if explicit else "__default__"
    if cache_key in _DISCOVERED_CORE_CACHE:
        cached = _DISCOVERED_CORE_CACHE[cache_key]
        if cached and pathlib.Path(cached).is_file():
            return cached

    candidates = []
    if explicit:
        candidate = pathlib.Path(explicit).expanduser()
        try:
            resolved = candidate.resolve()
        except OSError:
            _DISCOVERED_CORE_CACHE[cache_key] = None
            return None
        res_str = str(resolved) if resolved.is_file() else None
        _DISCOVERED_CORE_CACHE[cache_key] = res_str
        return res_str

    env_path = os.environ.get("PRIMER3_CORE")
    if env_path:
        candidates.append(pathlib.Path(env_path).expanduser())
    for name in _candidate_names():
        found = shutil.which(name)
        if found:
            candidates.append(pathlib.Path(found))
    for entry in sys.path:
        if not entry:
            continue
        base = pathlib.Path(entry)
        for name in _candidate_names():
            candidates.append(base / "primer3" / "src" / "libprimer3" / name)

    # Cross-environment inspection on Windows & Unix
    import glob
    extra_patterns = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python3*\Lib\site-packages\primer3\src\libprimer3\primer3_core.exe"),
        os.path.expandvars(r"%APPDATA%\Python\Python3*\site-packages\primer3\src\libprimer3\primer3_core.exe"),
        r"C:\Python3*\Lib\site-packages\primer3\src\libprimer3\primer3_core.exe",
        r"D:\anaconda\envs\*\Lib\site-packages\primer3\src\libprimer3\primer3_core.exe",
        r"C:\anaconda3\envs\*\Lib\site-packages\primer3\src\libprimer3\primer3_core.exe",
        r"C:\miniconda3\envs\*\Lib\site-packages\primer3\src\libprimer3\primer3_core.exe",
        os.path.expanduser(r"~/.local/lib/python3.*/site-packages/primer3/src/libprimer3/primer3_core"),
        r"/usr/local/lib/python3.*/dist-packages/primer3/src/libprimer3/primer3_core",
        r"/opt/conda/envs/*/lib/python3.*/site-packages/primer3/src/libprimer3/primer3_core",
    ]
    for pattern in extra_patterns:
        try:
            matches = glob.glob(pattern)
            matches.sort(reverse=True)
            for matched in matches:
                candidates.append(pathlib.Path(matched))
        except Exception:
            pass

    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_file():
            if os.name != "nt" and not os.access(resolved, os.X_OK):
                continue
            found_path = str(resolved)
            _DISCOVERED_CORE_CACHE[cache_key] = found_path
            return found_path
    _DISCOVERED_CORE_CACHE[cache_key] = None
    return None


def clear_core_cache():
    """Clear cached discovery results."""
    _DISCOVERED_CORE_CACHE.clear()


def ensure_primer3_core(explicit=None, auto_install=False, verbose=True):
    """Ensure primer3_core is available, optionally attempting pip auto-install.

    Returns the absolute path to primer3_core executable if available, or None.

    If primer3_core is not initially discovered and ``auto_install`` is True
    (or the PRIMER3_AUTO_INSTALL environment variable is set to "1" or "true"),
    this function executes ``sys.executable -m pip install "primer3-py>=2.3.0"``
    to fetch the precompiled binary wheel for the current platform.

    On success, the discovery cache is refreshed and the path is returned.
    If installation fails or is not attempted, returns None cleanly without
    raising an unhandled exception, allowing caller fallback.
    """
    found = discover_primer3_core(explicit)
    if found:
        return found

    should_install = auto_install or (
        os.environ.get("PRIMER3_AUTO_INSTALL", "").strip().lower() in ("1", "true", "yes")
    )
    if not should_install:
        return None

    if verbose:
        sys.stderr.write(
            "[Primer3 Bootstrap] primer3_core not found. Installing official precompiled wheel via:\n"
            "  %s -m pip install 'primer3-py>=2.3.0'...\n" % sys.executable
        )
        sys.stderr.flush()

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "primer3-py>=2.3.0"],
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",
            timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0:
            clear_core_cache()
            newly_found = discover_primer3_core(explicit)
            if newly_found:
                if verbose:
                    sys.stderr.write(
                        "[Primer3 Bootstrap] Successfully installed primer3-py! primer3_core ready at:\n"
                        "  %s\n" % newly_found
                    )
                    sys.stderr.flush()
                return newly_found
            elif verbose:
                sys.stderr.write(
                    "[Primer3 Bootstrap] pip install succeeded, but primer3_core executable was not found.\n"
                )
        else:
            if verbose:
                err_snippet = (proc.stderr or proc.stdout or "").strip()[-300:]
                sys.stderr.write(
                    "[Primer3 Bootstrap] pip install failed (exit=%d): %s\n"
                    % (proc.returncode, err_snippet)
                )
    except Exception as exc:
        if verbose:
            sys.stderr.write("[Primer3 Bootstrap] Auto-installation error: %s\n" % exc)

    return None


def probe_primer3_core(explicit=None, timeout=10):
    """Return a structured, honest availability report."""
    path = discover_primer3_core(explicit)
    if not path:
        detail = ("explicit primer3_core path was not found: %s" % explicit
                  if explicit else
                  "primer3_core was not found in PRIMER3_CORE, PATH, or an installed primer3-py wheel")
        return {
            "status": "unavailable",
            "backend": "primer3-core",
            "path": None,
            "version": None,
            "detail": detail,
        }
    try:
        completed = subprocess.run(
            [path, "--about"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        return {"status": "probe-error", "backend": "primer3-core",
                "path": path, "version": None,
                "detail": "primer3_core --about timed out after %ss" % timeout}
    except OSError as error:
        return {"status": "probe-error", "backend": "primer3-core",
                "path": path, "version": None,
                "detail": "primer3_core could not start: %r" % error}

    output = ((completed.stdout or "") + "\n" +
              (completed.stderr or "")).strip()
    match = re.search(r"(?:release\s+)?(\d+\.\d+(?:\.\d+)?)", output,
                      re.IGNORECASE)
    if completed.returncode != 0 or not match:
        return {"status": "probe-error", "backend": "primer3-core",
                "path": path, "version": None,
                "detail": "primer3_core --about failed (exit=%s): %s" %
                          (completed.returncode, output[-300:])}
    return {"status": "available", "backend": "primer3-core",
            "path": path, "version": match.group(1), "detail": None}


def encode_boulder(tags):
    """Encode one strict Boulder-IO record."""
    lines = []
    for key, value in tags.items():
        key = str(key)
        value = str(value)
        if not re.match(r"^[A-Z][A-Z0-9_]*$", key):
            raise ValueError("invalid Boulder-IO tag: %s" % key)
        if "\n" in value or "\r" in value:
            raise ValueError("Boulder-IO value contains a newline: %s" % key)
        lines.append("%s=%s" % (key, value))
    lines.append("=")
    return "\n".join(lines) + "\n"


def parse_boulder(text):
    """Parse the first Boulder-IO record into a string dictionary."""
    result = {}
    for raw_line in str(text).splitlines():
        line = raw_line.rstrip("\r")
        if line == "=":
            break
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


def run_boulder(core_path, tags, timeout=30):
    """Execute primer3_core once and return parsed output tags."""
    payload = encode_boulder(tags)
    try:
        completed = subprocess.run(
            [core_path, "--strict_tags"], input=payload,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        raise Primer3CoreError(
            "primer3_core timed out after %ss" % timeout)
    except OSError as error:
        raise Primer3CoreError("primer3_core could not start: %r" % error)

    parsed = parse_boulder(completed.stdout)
    primer_error = parsed.get("PRIMER_ERROR")
    if completed.returncode != 0 or primer_error:
        message = primer_error or (completed.stderr or completed.stdout)[-500:]
        raise Primer3CoreError(
            "primer3_core failed (exit=%s): %s" %
            (completed.returncode, message))
    if not parsed:
        raise Primer3CoreError(
            "primer3_core returned no Boulder-IO result (exit=%s): %s" %
            (completed.returncode, (completed.stderr or "")[-500:]))
    return parsed


def _float(tags, key, default=None):
    value = tags.get(key)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int(tags, key, default=0):
    value = tags.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _location(value):
    try:
        start, length = value.split(",", 1)
        return int(start), int(length)
    except (AttributeError, TypeError, ValueError):
        raise Primer3CoreError("invalid Primer3 location: %r" % value)


def _candidate(tags, prefix, index, tail, region_start, product_size, side,
               slide=False, slide_budget=0):
    key = "%s_%d" % (prefix, index)
    location_start, binding_length = _location(tags.get(key))
    full = tags.get(key + "_SEQUENCE", "")
    if tail and not full.startswith(tail):
        raise Primer3CoreError(
            "%s sequence does not contain the requested 5' overhang" % key)
    binding = full[len(tail):] if tail else full
    if len(binding) != binding_length:
        raise Primer3CoreError(
            "%s binding length mismatch: output=%d location=%d" %
            (key, len(binding), binding_length))

    if side == "forward":
        bind_start = region_start + location_start
        bind_end = bind_start + binding_length - 1
        # Positive offset means the primer 5' end moved inward from the
        # exact amplicon boundary (slide-retry relaxation).
        boundary_offset = location_start if slide else 0
    else:
        bind_end = region_start + location_start
        bind_start = bind_end - binding_length + 1
        boundary_offset = (product_size - 1 - location_start) if slide else 0

    self_any = _float(tags, key + "_SELF_ANY_TH")
    self_end = _float(tags, key + "_SELF_END_TH")
    hairpin_tm = _float(tags, key + "_HAIRPIN_TH")
    end_stability = _float(tags, key + "_END_STABILITY")
    return {
        "side": side,
        "binding": binding,
        "tail": tail,
        "sequence": full,
        "tm": round(_float(tags, key + "_TM", 0.0), 1),
        "gc": round(_float(tags, key + "_GC_PERCENT", 0.0), 1),
        "length": len(full),
        "binding_length": binding_length,
        "bind_start": bind_start,
        "bind_end": bind_end,
        "boundary_offset": boundary_offset,
        "hairpin": {"tm": hairpin_tm, "source": "primer3-core",
                    "metric": "HAIRPIN_TH"},
        "self_dimer": {"tm_any": self_any, "tm_3p": self_end,
                       "source": "primer3-core",
                       "metrics": ["SELF_ANY_TH", "SELF_END_TH"]},
        "heterodimer": None,
        "end_stability_3p": {"value": end_stability,
                             "source": "primer3-core",
                             "metric": "END_STABILITY"},
        "product_size": product_size,
        "primer3_penalty": _float(tags, key + "_PENALTY"),
        "penalties": [],
        "recommended": None,
    }


def design_anchored_pairs(core_path, sequence, region_start, target_tm,
                          min_len, max_len, top_n, fwd_tail="", rev_tail="",
                          timeout=30, tm_range=None, slide=False,
                          slide_budget=None, product_pad=100):
    """Ask Primer3 for exact-boundary or slide-relaxed PCR primer pairs.

    Exact mode (``slide=False``) preserves v0.6/v0.7 semantics: the left
    primer is forced to the first base and the right primer to the last base
    of ``sequence``.

    Slide mode is the release-iteration layer-4 fallback: Primer3's forced
    starts are released, each primer 5' end may move inward up to
    ``slide_budget`` (default ``min(25, n//4)``), and the product size range
    is widened to ``[n-product_pad, n+product_pad]``.  Coverage of the
    requested amplicon is enforced by the caller-facing post-filter
    (``boundary_offset <= budget``), not by ``SEQUENCE_INCLUDED_REGION``
    (which constrains primer placement and would exclude small offsets).
    GC constraints are left at Primer3 defaults (20-80%); relaxing GC is a
    user-consent decision handled by the caller, not by this layer.
    """
    sequence = str(sequence).upper()
    if not sequence:
        raise Primer3CoreError("cannot design primers for an empty region")
    product_size = len(sequence)
    tm_min, tm_max = tm_range or (target_tm - 5.0, target_tm + 5.0)
    if slide:
        budget = int(slide_budget if slide_budget is not None
                     else min(25, max(0, product_size // 4)))
        tags = {
            "SEQUENCE_ID": "snapgene-dna-design",
            "SEQUENCE_TEMPLATE": sequence,
            "PRIMER_TASK": "generic",
            "PRIMER_PICK_LEFT_PRIMER": 1,
            "PRIMER_PICK_RIGHT_PRIMER": 1,
            # Request more candidates than needed: the first top_n Primer3
            # ranks may sit outside the consented slide budget while later
            # candidates satisfy it.
            "PRIMER_NUM_RETURN": max(top_n, 50),
            "PRIMER_MIN_SIZE": min_len,
            "PRIMER_OPT_SIZE": max(min_len, min(max_len, 20)),
            "PRIMER_MAX_SIZE": max_len,
            "PRIMER_MIN_TM": max(0.0, tm_min),
            "PRIMER_OPT_TM": target_tm,
            "PRIMER_MAX_TM": tm_max,
            "PRIMER_PRODUCT_SIZE_RANGE": "%d-%d" % (
                max(min_len * 2, product_size - product_pad),
                product_size + product_pad),
            "PRIMER_EXPLAIN_FLAG": 1,
            "PRIMER_SECONDARY_STRUCTURE_ALIGNMENT": 1,
        }
        # Slide mode is deliberately binding-only: tails are reattached by
        # the engine after Primer3 ranking so tail bases do not pollute Tm or
        # hairpin scoring.  GC stays at Primer3's 20-80 defaults.
    else:
        tags = {
            "SEQUENCE_ID": "snapgene-dna-design",
            "SEQUENCE_TEMPLATE": sequence,
            "SEQUENCE_FORCE_LEFT_START": 0,
            "SEQUENCE_FORCE_RIGHT_START": product_size - 1,
            "PRIMER_TASK": "generic",
            "PRIMER_PICK_LEFT_PRIMER": 1,
            "PRIMER_PICK_RIGHT_PRIMER": 1,
            "PRIMER_NUM_RETURN": top_n,
            "PRIMER_MIN_SIZE": min_len,
            "PRIMER_OPT_SIZE": max(min_len, min(max_len, 20)),
            "PRIMER_MAX_SIZE": max_len,
            "PRIMER_MIN_TM": max(0.0, tm_min),
            "PRIMER_OPT_TM": target_tm,
            "PRIMER_MAX_TM": tm_max,
            "PRIMER_PRODUCT_SIZE_RANGE": "%d-%d" % (product_size, product_size),
            "PRIMER_EXPLAIN_FLAG": 1,
            "PRIMER_SECONDARY_STRUCTURE_ALIGNMENT": 1,
        }
        if fwd_tail:
            tags["SEQUENCE_OVERHANG_LEFT"] = fwd_tail
        if rev_tail:
            tags["SEQUENCE_OVERHANG_RIGHT"] = rev_tail

    # Candidate generation must not discard a valid high-Tm pair using the
    # low end of the requested window. The full-oligo check then applies the
    # stricter margin for the actual selected pair's lower binding Tm.
    structure_limit = tm_max - 10.0
    for key in ("PRIMER_MAX_HAIRPIN_TH", "PRIMER_MAX_SELF_ANY_TH", "PRIMER_MAX_SELF_END_TH",
                "PRIMER_PAIR_MAX_COMPL_ANY_TH", "PRIMER_PAIR_MAX_COMPL_END_TH"):
        tags[key] = structure_limit
    raw = run_boulder(core_path, tags, timeout=timeout)
    count = _int(raw, "PRIMER_PAIR_NUM_RETURNED")
    forward = []
    reverse = []
    pairs = []
    for index in range(count):
        fwd = _candidate(raw, "PRIMER_LEFT", index, fwd_tail if not slide else "",
                         region_start, product_size, "forward",
                         slide=slide, slide_budget=budget if slide else 0)
        rev = _candidate(raw, "PRIMER_RIGHT", index, rev_tail if not slide else "",
                         region_start, product_size, "reverse",
                         slide=slide, slide_budget=budget if slide else 0)
        rank = index + 1
        recommendation = "high" if rank == 1 else "medium"
        fwd["recommended"] = recommendation
        rev["recommended"] = recommendation
        pair_key = "PRIMER_PAIR_%d" % index
        heterodimer = {
            "tm_any": _float(raw, pair_key + "_COMPL_ANY_TH"),
            "tm_3p": _float(raw, pair_key + "_COMPL_END_TH"),
            "source": "primer3-core",
            "metrics": ["COMPL_ANY_TH", "COMPL_END_TH"],
        }
        fwd["heterodimer"] = heterodimer
        rev["heterodimer"] = heterodimer
        forward.append(fwd)
        reverse.append(rev)
        primer3_product_size = _int(raw, pair_key + "_PRODUCT_SIZE",
                                    product_size)
        pairs.append({
            "rank": rank,
            "forward_index": index,
            "reverse_index": index,
            "product_size": product_size,
            "primer3_product_size_with_overhangs": primer3_product_size,
            "actual_product_size": primer3_product_size,
            "boundary_offset_5p": fwd["boundary_offset"],
            "boundary_offset_3p": rev["boundary_offset"],
            "heterodimer": heterodimer,
            "penalties": [],
            "combined_penalties": [],
            "weight": _float(raw, pair_key + "_PENALTY"),
            "primer3_penalty": _float(raw, pair_key + "_PENALTY"),
            "recommended": recommendation,
            "recommendation_basis": "primer3 pair rank; not an experimental success prediction",
        })

    if slide:
        # Primer3's SEQUENCE_INCLUDED_REGION is advisory in some builds; enforce
        # the release-iteration slide contract ourselves: each primer 5' end may
        # move inward at most ``budget`` nt from the exact boundary.
        keep = []
        for new_index, (candidate_fwd, candidate_rev) in enumerate(
                zip(forward, reverse)):
            if (0 <= candidate_fwd["boundary_offset"] <= budget and
                    0 <= candidate_rev["boundary_offset"] <= budget):
                keep.append(new_index)
        forward = [forward[i] for i in keep]
        reverse = [reverse[i] for i in keep]
        kept_pairs = []
        for new_index, old_index in enumerate(keep):
            old_pair = pairs[old_index]
            old_pair.update({
                "rank": new_index + 1,
                "forward_index": new_index,
                "reverse_index": new_index,
                "recommended": "high" if new_index == 0 else "medium",
            })
            kept_pairs.append(old_pair)
        pairs = kept_pairs
        for index, candidate in enumerate(forward):
            candidate["recommended"] = "high" if index == 0 else "medium"
        for index, candidate in enumerate(reverse):
            candidate["recommended"] = "high" if index == 0 else "medium"

    return {
        "forward_candidates": forward,
        "reverse_candidates": reverse,
        "pairs": pairs,
        "explain": {
            "left": raw.get("PRIMER_LEFT_EXPLAIN"),
            "right": raw.get("PRIMER_RIGHT_EXPLAIN"),
            "pair": raw.get("PRIMER_PAIR_EXPLAIN"),
        },
        "returned_pairs": count,
        "accepted_pairs": len(pairs),
        "raw_error": raw.get("PRIMER_ERROR"),
        "mode": "slide" if slide else "exact-boundary",
        "slide_budget": budget if slide else 0,
    }
