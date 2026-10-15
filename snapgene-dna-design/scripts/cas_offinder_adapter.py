# -*- coding: utf-8 -*-
"""cas_offinder_adapter.py - Cas-OFFinder detection, execution, parsing.

Real CLI contract implemented and verified against Cas-OFFinder v2.4.1 and
v3.0.0 beta:

    cas-offinder {input_filename|-} {C|G|A}[device_id(s)] {output_filename|-}

Input file layout (one query per run, with an optional label):

    <reference FASTA file or chromosome directory>
    <full-length IUPAC pattern including PAM> [dna_bulge] [rna_bulge]   # 3.x
    <query sequence of the same length> <max_mismatches> [label]

v2.4 output columns:
    query  chromosome  start(0-based)  sequence  strand  mismatches

v3.0 output columns (after the ``##Generated`` header):
    id  bulge_type  crRNA  DNA  chromosome  location  direction  mismatches  bulge_size
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from provenance import probe_executable, sha256_of_file, source, source_id, now_iso, read_version

ROOT = pathlib.Path(__file__).resolve().parents[1]
def default_index_registry_path():
    """User-writable registry location; never the packaged source tree.

    Override with the ``CAS_OFFINDER_REGISTRY`` environment variable.
    """
    env_path = os.environ.get("CAS_OFFINDER_REGISTRY")
    if env_path:
        return pathlib.Path(env_path)
    if os.name == "nt":
        base = pathlib.Path(os.environ.get("LOCALAPPDATA")
                            or pathlib.Path.home() / "AppData" / "Local")
        return base / "SnapGeneDNADesign" / "cas-offinder-index-registry.json"
    base = pathlib.Path(os.environ.get("XDG_STATE_HOME")
                        or pathlib.Path.home() / ".local" / "state")
    return base / "snapgene-dna-design" / "cas-offinder-index-registry.json"


DEFAULT_INDEX_REGISTRY = default_index_registry_path()
CAS_OFFINDER_URL = "https://github.com/snugel/cas-offinder"
CAS_OFFINDER_LICENSE = "BSD-3-Clause"

# Registry nucleases -> Cas-OFFinder PAM pattern constraints.  The pattern
# line fixes only the PAM bases; the protospacer positions stay 'N' so every
# mismatch is counted inside the protospacer, never in the PAM.
NUCLEASE_SEARCH_RULES = {
    "spcas9-wt": {
        "pam_side": "3prime",
        "pam_pattern": "NGG",
        "pam_length": 3,
        "spacer_length": 20,
    },
    "ascas12a-wt": {
        "pam_side": "5prime",
        "pam_pattern": "TTTV",
        "pam_length": 4,
        "spacer_length": 23,
    },
    "lbcas12a-wt": {
        "pam_side": "5prime",
        "pam_pattern": "TTTV",
        "pam_length": 4,
        "spacer_length": 23,
    },
}


def _normalise_version(text):
    """Extract ``2.4.1`` from Cas-OFFinder's first help line."""
    if not text:
        return None
    match = re.search(r"Cas-OFFinder\s+v?([0-9]+(?:\.[0-9]+)+)", text)
    if match:
        return match.group(1)
    match = re.search(r"([0-9]+(?:\.[0-9]+)+)", text)
    return match.group(1) if match else None


def detect(executable=None):
    """Detect a real Cas-OFFinder binary.

    Cas-OFFinder has no ``--version`` switch; the no-argument invocation
    prints the banner and the OpenCL device list and exits 0.
    """
    exe = executable or shutil.which("cas-offinder")
    if not exe and shutil.which("cas-offinder.exe"):
        exe = shutil.which("cas-offinder.exe")
    if not exe:
        return {
            "installed": False,
            "executable": None,
            "version": None,
            "opencl_detected": None,
            "available_devices": [],
            "recommended_device": None,
            "verification": {"method": "path-probe", "status": "unavailable"},
            "provenance": [source(
                "software", "Cas-OFFinder", "off-target-search",
                url=CAS_OFFINDER_URL, version=None, license_value=CAS_OFFINDER_LICENSE,
                status="unavailable",
                verification={"method": "path-probe", "status": "unavailable"})],
        }
    path, first_line, verification = probe_executable(exe, [])
    version = _normalise_version(first_line or "")
    opencl_detected = False
    available_devices = []
    try:
        completed = subprocess.run(
            [path], capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace", shell=False)
        banner = (completed.stdout or "") + "\n" + (completed.stderr or "")
        # Cas-OFFinder prints the actual OpenCL inventory in its no-argument
        # banner.  Keep the parsed inventory so ``auto`` can select a device
        # that is really present instead of assuming ``C0``.
        for match in re.finditer(
                r"Type:\s*(GPU|CPU),\s*ID:\s*(\d+)", banner,
                flags=re.IGNORECASE):
            available_devices.append({
                "type": match.group(1).upper(),
                "id": int(match.group(2)),
            })
        opencl_detected = bool(
            "Available device list" in banner and available_devices)
        if not version:
            version = _normalise_version(banner)
    except Exception:  # noqa: BLE001 - probe is informational only
        opencl_detected = False
    provenance = source(
        "software", "Cas-OFFinder", "off-target-search",
        url=CAS_OFFINDER_URL, version=version, license_value=CAS_OFFINDER_LICENSE,
        status=verification["status"], verification=verification)
    if verification.get("status") == "verified":
        provenance["source_id"] = source_id(provenance)
    return {
        "installed": bool(path and verification.get("status") == "verified"),
        "executable": path if verification.get("status") == "verified" else None,
        "version": version,
        "opencl_detected": opencl_detected,
        "available_devices": available_devices,
        "recommended_device": (
            next(("G%d" % item["id"] for item in available_devices
                  if item["type"] == "GPU"), None)
            or next(("C%d" % item["id"] for item in available_devices
                     if item["type"] == "CPU"), None)
        ),
        "verification": verification,
        "provenance": [provenance],
    }


def _read_fasta_stats(fasta_path):
    from Bio import SeqIO
    count = 0
    total = 0
    with open(fasta_path, "r", encoding="utf-8-sig") as handle:
        for record in SeqIO.parse(handle, "fasta"):
            count += 1
            total += len(record.seq)
    return count, total


def genome_record(fasta_path, annotation_path=None, species=None, strain=None,
                  assembly=None, index_time=None, backend=None):
    """Bind reference identity (SHA-256, sequence count/length).

    A missing FASTA is a structured failure, never a traceback.
    """
    fasta = pathlib.Path(fasta_path)
    if not fasta.exists():
        return {
            "status": "failed",
            "reason": "REFERENCE_FASTA_NOT_FOUND",
            "fasta_path": str(fasta),
            "fasta_sha256": None,
            "species": species,
            "strain": strain,
            "assembly": assembly,
            "annotation_path": str(annotation_path) if annotation_path else None,
            "annotation_sha256": None,
            "sequence_count": None,
            "total_length": None,
            "index_time": index_time,
            "backend_version": (backend or {}).get("version") if backend else None,
        }
    annotation = pathlib.Path(annotation_path) if annotation_path else None
    if annotation is not None and not annotation.exists():
        return {
            "status": "failed",
            "reason": "REFERENCE_ANNOTATION_NOT_FOUND",
            "fasta_path": str(fasta),
            "fasta_sha256": sha256_of_file(fasta),
            "annotation_path": str(annotation),
            "annotation_sha256": None,
            "sequence_count": None,
            "total_length": None,
            "species": species, "strain": strain, "assembly": assembly,
            "index_time": index_time,
            "backend_version": (backend or {}).get("version") if backend else None,
        }
    count, total = _read_fasta_stats(fasta)
    result = {
        "status": "ready" if count and total else "incomplete",
        "species": species,
        "strain": strain,
        "assembly": assembly,
        "fasta_path": str(fasta),
        "fasta_sha256": sha256_of_file(fasta),
        "annotation_path": str(annotation) if annotation else None,
        "annotation_sha256": (sha256_of_file(annotation) if annotation else None),
        "sequence_count": count,
        "total_length": total,
        "index_time": index_time,
        "backend_version": (backend or {}).get("version") if backend else None,
    }
    return result


def load_index_registry(path=None):
    path = pathlib.Path(path or DEFAULT_INDEX_REGISTRY)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_index_registry(registry, path=None):
    path = pathlib.Path(path or DEFAULT_INDEX_REGISTRY)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def check_reference_binding(reference, registry=None, registry_path=None):
    """Return the reference's binding state relative to the index registry.

    A FASTA whose SHA-256 no longer matches the recorded index is ``stale``
    and must be rebuilt before another search may be trusted.
    """
    if reference.get("status") != "ready":
        return {"status": reference.get("status"),
                "reason": reference.get("reason", "REFERENCE_NOT_READY")}
    registry = registry if registry is not None else load_index_registry(registry_path)
    fasta_path = reference.get("fasta_path")
    recorded = registry.get(fasta_path) if fasta_path else None
    if recorded is None:
        return {"status": "unbound", "reason": "REFERENCE_INDEX_NOT_RECORDED"}
    recorded_sha = recorded.get("fasta_sha256")
    current_sha = reference.get("fasta_sha256")
    if recorded_sha != current_sha:
        return {"status": "stale",
                "reason": "REFERENCE_FASTA_CHANGED_STALE_INDEX",
                "recorded_sha256": recorded_sha,
                "current_sha256": current_sha}
    return {"status": "bound", "reason": None,
            "index_time": recorded.get("index_time")}


def record_reference_binding(reference, backend, registry_path=None):
    registry = load_index_registry(registry_path)
    fasta_path = reference.get("fasta_path")
    if not fasta_path:
        return registry
    registry[fasta_path] = {
        "fasta_sha256": reference.get("fasta_sha256"),
        "sequence_count": reference.get("sequence_count"),
        "total_length": reference.get("total_length"),
        "annotation_path": reference.get("annotation_path"),
        "annotation_sha256": reference.get("annotation_sha256"),
        "backend": backend.get("version"),
        "backend_executable": backend.get("executable"),
        "index_time": now_iso(),
    }
    save_index_registry(registry, registry_path)
    return registry


def search_rules(nuclease_id, parameters=None):
    parameters = parameters or {}
    rules = dict(NUCLEASE_SEARCH_RULES.get(nuclease_id, {}))
    if not rules:
        raise ValueError("CAS_OFFINDER_UNSUPPORTED_NUCLEASE: %s" % nuclease_id)
    rules.update({key: parameters[key] for key in (
        "pam_side", "pam_pattern", "pam_length", "spacer_length")
        if key in parameters})
    rules["pam_pattern"] = str(rules["pam_pattern"]).upper()
    rules["pam_length"] = int(rules["pam_length"])
    rules["spacer_length"] = int(rules["spacer_length"])
    return rules


def build_input_text(query_sequence, nuclease_id, parameters):
    """Assemble a real Cas-OFFinder input file body."""
    rules = search_rules(nuclease_id, parameters)
    query = str(query_sequence).strip().upper()
    spacer_length = rules["spacer_length"]
    if len(query) != spacer_length:
        raise ValueError(
            "QUERY_LENGTH_MISMATCH: expected %d protospacer bases, got %d"
            % (spacer_length, len(query)))
    if not all(base in "ACGTRYSWKMBDHVN" for base in query):
        raise ValueError("QUERY_CONTAINS_UNSUPPORTED_BASES: %s" % query)
    pam_length = rules["pam_length"]
    if rules["pam_side"] == "5prime":
        pattern = rules["pam_pattern"] + "N" * spacer_length
    else:
        pattern = "N" * spacer_length + rules["pam_pattern"]
    if len(rules["pam_pattern"]) != pam_length:
        raise ValueError("CAS_OFFINDER_PAM_LENGTH_MISMATCH")
    # Query PAM positions are wildcarded so the fixed pattern column, not the
    # query, enforces the PAM and mismatch counting stays spacer-only.
    query_full = query + ("N" * pam_length) if rules["pam_side"] == "3prime" \
        else ("N" * pam_length) + query
    if len(pattern) != len(query_full):
        raise ValueError("CAS_OFFINDER_PATTERN_QUERY_LENGTH_MISMATCH")
    mismatches = int(parameters.get("mismatches", 3))
    dna_bulge = int(parameters.get("dna_bulge", 0))
    rna_bulge = int(parameters.get("rna_bulge", 0))
    label = str(parameters.get("label", "query1")).replace(" ", "_")
    pattern_line = pattern
    if dna_bulge or rna_bulge:
        pattern_line += " %d %d" % (dna_bulge, rna_bulge)
    return "\n".join([pattern_line, "%s %d %s" % (query_full, mismatches, label)]) + "\n"


def parse_output(text, query_sequence=None, pattern=None):
    """Parse v2.4 (6-column) and v3.0 (9-column) Cas-OFFinder output.

    ``start``/``end`` are returned as 0-based half-open genomic coordinates
    (v2 output already provides a 0-based start; v3 likewise).
    """
    hits = []
    lines = [line.strip().replace("\r", "") for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    if not lines:
        return [], "CAS_OFFINDER_EMPTY_OUTPUT"
    for raw_line in lines:
        fields = raw_line.split("\t")
        if len(fields) == 6:
            # v2.4 without an input-file label.
            query, chromosome, start_s, sequence, strand, mismatches_s = fields
            bulge_type = None
            bulge_size = 0
        elif len(fields) == 7 and not fields[0].isdigit():
            # v2.4 with an input-file label appended as column 7.
            query, chromosome, start_s, sequence, strand, mismatches_s, _label = fields
            bulge_type = None
            bulge_size = 0
        elif len(fields) >= 9:
            # v3.0 output; the first column is the numeric id or the label.
            (_, bulge_type, query, sequence, chromosome, start_s,
             strand, mismatches_s) = fields[:8]
            bulge_size_s = fields[8] if len(fields) > 8 else "0"
            try:
                bulge_size = int(bulge_size_s)
            except ValueError:
                return None, "EXTERNAL_OUTPUT_PARSE_ERROR: non-integer bulge size"
        else:
            return None, "EXTERNAL_OUTPUT_PARSE_ERROR: %r" % raw_line[:160]
        try:
            start = int(start_s)
            mismatches = int(mismatches_s)
        except ValueError:
            return None, "EXTERNAL_OUTPUT_PARSE_ERROR: non-integer coordinate"
        if start < 0:
            return None, "EXTERNAL_OUTPUT_PARSE_ERROR: invalid coordinate"
        if strand not in ("+", "-"):
            return None, "EXTERNAL_OUTPUT_PARSE_ERROR: unknown strand %r" % strand
        dna = str(sequence).strip()
        if not dna:
            return None, "EXTERNAL_OUTPUT_PARSE_ERROR: empty hit sequence"
        normalized_bulge = bulge_type if bulge_type and bulge_type != "X" else None
        mismatch_positions = _mismatch_positions(
            dna, query, query_sequence, pattern, bulge=bool(normalized_bulge))
        pam_side = _infer_pam_side(pattern, query_sequence)
        pam = _extract_pam(dna.replace("-", ""), pam_side)
        reference_span = len(dna.replace("-", ""))
        hits.append({
            "chromosome": chromosome.split()[0] if chromosome else chromosome,
            "start": start,
            "end": start + reference_span,
            "reference_span": reference_span,
            "strand": strand,
            "sequence": dna.upper(),
            "mismatches": mismatches,
            "mismatch_positions": mismatch_positions,
            "pam": pam,
            "bulge_type": normalized_bulge,
            "bulge_size": bulge_size,
            "annotation": None,
        })
    return hits, None


def _mismatch_positions(dna, query, query_sequence=None, pattern=None,
                        bulge=False):
    """Positions (0-based within the hit) where the found DNA differs.

    Lowercase bases in Cas-OFFinder output mark mismatches directly.  The
    query-column comparison is used as corroboration and for v3 output.
    Bulge alignments contain gap columns, so column-by-column comparison is
    invalid there and only the lowercase mismatch markup is used.
    """
    positions = set()
    dna_upper = dna.upper()
    for idx, base in enumerate(dna):
        if base.islower():
            positions.add(idx)
    if bulge:
        return sorted(positions)
    reference_query = query.upper()
    for idx in range(min(len(dna_upper), len(reference_query))):
        ref_base = reference_query[idx]
        if ref_base not in "ACGT":
            continue
        if dna_upper[idx] != ref_base:
            positions.add(idx)
    return sorted(positions)


def _infer_pam_side(pattern, query_sequence=None):
    """Return 3prime/5prime from a Cas-OFFinder full-length pattern.

    Default is 3prime (SpCas9) because that is the historical Cas-OFFinder
    layout; callers passing ``pattern`` explicitly set the correct side.
    """
    if pattern:
        stripped = pattern.strip().replace("N", "")
        if stripped and pattern.startswith("N"):
            # PAM bases sit at the 3' end, e.g. NNN...NGG.
            return "3prime"
        if stripped and pattern.endswith("N"):
            return "5prime"
    return "3prime"


def _extract_pam(sequence, pam_side, pam_length_hint=None):
    seq = str(sequence).upper()
    if pam_side == "5prime":
        length = pam_length_hint or min(4, len(seq))
        return seq[:length]
    length = pam_length_hint or min(3, len(seq))
    return seq[-length:]


def search_offtargets(query_sequence, reference_fasta, parameters,
                      executable=None, timeout=120, device=None,
                      nuclease_id="spcas9-wt", annotation_path=None,
                      registry_path=None, rebuild_stale=True):
    """Run the real Cas-OFFinder CLI and parse its output file."""
    if isinstance(parameters, dict):
        params = dict(parameters)
    else:
        raise ValueError("CAS_OFFINDER_PARAMETERS_MUST_BE_DICT")
    reference = genome_record(reference_fasta, annotation_path=annotation_path)
    if reference.get("status") != "ready":
        return {
            "schema_version": "0.8.0",
            "status": "failed",
            "reason": reference.get("reason") or "REFERENCE_GENOME_NOT_READY",
            "detail": "reference genome is not ready for off-target search",
            "reference_genome": reference,
            "hits": [],
            "provenance": [source(
                "software", "Cas-OFFinder", "off-target-search",
                url=CAS_OFFINDER_URL, license_value=CAS_OFFINDER_LICENSE,
                status="unavailable",
                verification={"method": "preflight-reference-check",
                              "status": "unavailable"})],
        }
    binding = check_reference_binding(reference, registry_path=registry_path)
    if binding.get("status") == "stale" and not rebuild_stale:
        return {
            "schema_version": "0.8.0",
            "status": "failed",
            "reason": binding.get("reason"),
            "detail": binding,
            "reference_genome": reference,
            "hits": [],
            "provenance": [source(
                "software", "Cas-OFFinder", "off-target-search",
                url=CAS_OFFINDER_URL, license_value=CAS_OFFINDER_LICENSE,
                status="stale", verification={"method": "index-registry",
                                              "status": "stale"})],
        }
    try:
        rules = search_rules(nuclease_id, params)
        input_body = build_input_text(query_sequence, nuclease_id, params)
        pattern = (rules["pam_pattern"] + "N" * rules["spacer_length"]
                   if rules["pam_side"] == "5prime"
                   else "N" * rules["spacer_length"] + rules["pam_pattern"])
    except (ValueError, KeyError) as error:
        return _failed_payload(reference, {"provenance": []},
                               str(error).split(":")[0], str(error))
    detection = detect(executable)
    if not detection["installed"]:
        return {
            "schema_version": "0.8.0",
            "status": "unavailable",
            "reason": "CAS_OFFINDER_NOT_INSTALLED",
            "detail": detection["verification"],
            "reference_genome": reference,
            "hits": [],
            "provenance": detection["provenance"],
        }
    requested_device = "auto" if device is None else str(device)
    selected_device = device
    if selected_device is None or str(selected_device).lower() == "auto":
        selected_device = detection.get("recommended_device") or "C0"
    selected_device = str(selected_device)
    if (int(params.get("dna_bulge", 0)) or int(params.get("rna_bulge", 0))) and \
            (detection["version"] or "2").startswith("2"):
        return _failed_payload(
            reference, detection, "CAS_OFFINDER_BULGE_UNSUPPORTED",
            "DNA/RNA bulge search requires Cas-OFFinder 3.x, detected %s"
            % detection["version"])
    try:
        reference_path = pathlib.Path(reference_fasta).resolve()
        run = _run_cas_offinder_cli(
            detection["executable"], reference_path, input_body,
            selected_device, timeout)
        completed = run["completed"]
        output_path = run["output_path"]
        if completed.returncode != 0:
            return _failed_payload(
                reference, detection, "CAS_OFFINDER_EXECUTION_FAILED",
                (completed.stderr or completed.stdout or "").strip()[-600:],
                completed.returncode)
        stderr_text = (completed.stderr or "")
        if ("non-acceptable" in stderr_text.lower()
                or "Skipping non-acceptable file" in stderr_text):
            return _failed_payload(
                reference, detection,
                "CAS_OFFINDER_REFERENCE_EXTENSION_UNSUPPORTED",
                ("Cas-OFFinder skipped one or more reference files because "
                 "their extension is not accepted by this backend version. "
                 "Use .fna/.fas/.fa.gz/.2bit/.faa. stderr tail: %s"
                 % stderr_text.strip()[-400:]))
        if not output_path.exists() or output_path.stat().st_size == 0:
            return {
                "schema_version": "0.8.0",
                "status": "incomplete",
                "reason": "CAS_OFFINDER_EMPTY_OUTPUT",
                "detail": ("returncode=0 but the output file is empty; "
                           "this is either a true zero-hit result or a "
                           "backend silent failure and must be reviewed. "
                           "stderr tail: %s"
                           % (completed.stderr or "").strip()[-400:]),
                "reference_genome": reference,
                "hits": [],
                "provenance": detection["provenance"],
            }
        output_text = output_path.read_text(encoding="utf-8", errors="replace")
        hits, error = parse_output(
            output_text, query_sequence=str(query_sequence).upper(),
            pattern=pattern)
        if error:
            return _failed_payload(reference, detection, error,
                                   output_text[:400])
        record_reference_binding(reference, detection, registry_path)
        result = {
            "schema_version": "0.8.0",
            "status": "complete",
            "reference_genome": reference,
            "hits": hits,
            "provenance": detection["provenance"],
        }
        if detection["version"]:
            result["backend_version"] = detection["version"]
        version = detection["version"] or ""
        experimental_backend = version.startswith("3")
        result["experimental_backend"] = experimental_backend
        result["production_ready"] = not experimental_backend
        if experimental_backend:
            result["backend_warning"] = (
                "Cas-OFFinder 3.x is an experimental beta backend; its "
                "results are not production-grade and must be cross-checked "
                "with v2.x or an independent off-target tool before any "
                "low-off-target claim.")
        result["search_parameters"] = {
            "nuclease": nuclease_id,
            "mismatches": int(params.get("mismatches", 3)),
            "dna_bulge": int(params.get("dna_bulge", 0)),
            "rna_bulge": int(params.get("rna_bulge", 0)),
            "device": selected_device,
            "requested_device": requested_device,
        }
        return result
    except subprocess.TimeoutExpired as error:
        return _failed_payload(reference, detection,
                               "CAS_OFFINDER_TIMEOUT",
                               "timeout after %ds: %s" % (timeout, error))
    except OSError as error:
        return _failed_payload(reference, detection,
                               "CAS_OFFINDER_EXECUTION_FAILED", str(error))
    finally:
        output_path = locals().get("output_path")
        if output_path is not None:
            try:
                pathlib.Path(output_path).unlink()
            except OSError:
                pass



def _run_cas_offinder_cli(executable, reference_path, input_body, device,
                          timeout):
    r"""Run the real CLI in a way that survives non-ASCII Windows paths.

    Cas-OFFinder 2.x parses its input/output file arguments with the ANSI
    code page while Python writes the input file as UTF-8.  Absolute
    ``C:\Users\<Chinese>\...`` paths therefore break the backend.  The
    robust form (verified against v2.4.1 and v3.0.0b3) keeps every argument
    relative: the working directory is the FASTA directory and the input
    file's first line is just the FASTA file name.
    """
    reference_dir = reference_path.parent
    token = uuid.uuid4().hex[:12]
    input_name = ".cas-offinder-%s-in.txt" % token
    output_name = ".cas-offinder-%s-out.txt" % token
    input_path = reference_dir / input_name
    output_path = reference_dir / output_name
    first_line = reference_path.name
    if any(ord(char) > 127 for char in first_line):
        # The first line is parsed with the ANSI code page too.  A copied,
        # ASCII-only file name keeps the search reproducible without touching
        # the user's original file.
        if not os.access(str(reference_dir), os.W_OK):
            raise OSError(
                "CAS_OFFINDER_NON_ASCII_FILENAME_READONLY_DIR: %s"
                % reference_path)
        copied_name = ".cas-offinder-%s-ref.fna" % token
        shutil.copyfile(reference_path, reference_dir / copied_name)
        first_line = copied_name
        try:
            return _invoke_cli(executable, reference_dir, first_line,
                               input_name, output_name, input_body, device,
                               timeout)
        finally:
            try:
                (reference_dir / copied_name).unlink()
            except OSError:
                pass
    return _invoke_cli(executable, reference_dir, first_line, input_name,
                       output_name, input_body, device, timeout)


def _invoke_cli(executable, cwd, first_line, input_name, output_name,
                input_body, device, timeout):
    cwd = pathlib.Path(cwd)
    input_path = cwd / input_name
    output_path = cwd / output_name
    input_path.write_text(first_line + "\n" + input_body, encoding="utf-8")
    try:
        completed = subprocess.run(
            [executable, input_name, device, output_name],
            cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace", shell=False)
    finally:
        try:
            input_path.unlink()
        except OSError:
            pass
    return {"completed": completed, "output_path": output_path}

def _failed_payload(reference, detection, reason, detail, returncode=None):
    payload = {
        "schema_version": "0.8.0",
        "status": "failed",
        "reason": reason,
        "detail": detail,
        "reference_genome": reference,
        "hits": [],
        "provenance": detection["provenance"],
    }
    if returncode is not None:
        payload["returncode"] = returncode
    return payload


if __name__ == "__main__":
    print(json.dumps(detect(), ensure_ascii=False, indent=2))
    sys.exit(0)
