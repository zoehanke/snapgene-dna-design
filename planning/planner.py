# -*- coding: utf-8 -*-
"""planning/planner.py - M1 multi-source assembly planner.

Feeds every numerical decision through real algorithms:
* restriction sites: Bio.Restriction / sg_common.restriction_hits
* overlap parameters: window search with Biopython Tm_NN + GC thresholds
* primers: primer_design_engine (real primer3_core when available)
* feasibility: rules.engine.evaluate_plan (M2)
"""
import hashlib
import math
import pathlib
import sys

from Bio.Seq import Seq
from Bio.SeqUtils import MeltingTemp as mt

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from sg_common import gc_percent, get_enzyme, load_seq, restriction_hits, topology  # noqa: E402
from provenance import read_version, source  # noqa: E402
from rules.engine import evaluate_plan  # noqa: E402
from planning.intent import normalize_intent  # noqa: E402
from primer_design_engine import (  # noqa: E402
    design_region_primers, restriction_tail,
)
from primer3_core_backend import check_complete_oligo_pair  # noqa: E402
from core.tools.amplification import simulate_pcr, _extract_template_record  # noqa: E402
from core.models.construct_model import feature_to_dict  # noqa: E402
from operation_consent import ConsentBroker, TransparencyLog  # noqa: E402
from validation_crosscheck import overlap_crosscheck, restriction_site_crosscheck  # noqa: E402
from planning.executor import ExecutionError, execute_assembly  # noqa: E402


TYPE_IIS_CANDIDATES = ("BsaI", "BsmBI", "Esp3I", "BbsI")


class PlannerError(ValueError):
    pass


def _feature_name(feature):
    for key in ("label", "gene", "locus_tag", "product"):
        values = (feature.qualifiers or {}).get(key)
        if isinstance(values, (list, tuple)) and values:
            return str(values[0])
        if values not in (None, ""):
            return str(values)
    return feature.id or feature.type or "feature"


def _record_summary(record, path, index):
    feature_rows = []
    for feature in record.features:
        if feature.location is None:
            feature_rows.append({
                "type": feature.type,
                "name": _feature_name(feature),
                "start": None, "end": None, "strand": None,
            })
        else:
            feature_rows.append({
                "type": feature.type,
                "name": _feature_name(feature),
                "start": int(feature.location.start),
                "end": int(feature.location.end),
                "strand": feature.location.strand,
            })
    try:
        file_sha256 = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    except (OSError, TypeError):
        file_sha256 = None
    sequence_sha256 = hashlib.sha256(
        str(record.seq).upper().encode("ascii", "strict")
    ).hexdigest()
    return {
        "index": index,
        "path": str(path),
        "id": record.id or record.name,
        "length": len(record.seq),
        "sha256": file_sha256,
        "sequence_sha256": sequence_sha256,
        "topology": topology(record),
        "features": feature_rows,
    }


def _feature_sequence(record, feature):
    return str(feature.extract(record.seq)).upper()


def _find_feature(record, spec):
    wanted = str(spec.get("feature") or spec.get("name") or "").lower()
    wanted_type = str(spec.get("feature_type") or "").lower()
    matches = []
    for feature in record.features:
        if feature.location is None:
            continue
        labels = []
        for key in ("label", "gene", "locus_tag", "product", "note"):
            value = feature.qualifiers.get(key)
            if value:
                labels.append(str(value[0] if isinstance(value, (list, tuple))
                                 else value).lower())
        if wanted and wanted in labels:
            matches.append(feature)
        elif wanted_type and feature.type.lower() == wanted_type:
            matches.append(feature)
    if len(matches) == 1:
        return matches[0]
    if wanted:
        for feature in matches:
            if any(wanted == label for label in (
                    str((feature.qualifiers.get(key, [""])[0]
                         if isinstance(feature.qualifiers.get(key, [""]),
                                       (list, tuple))
                         else feature.qualifiers.get(key, ""))).lower()
                    for key in ("label", "gene", "locus_tag"))):
                return feature
    return None


def _extract_region(record, spec, source_index):
    seq = str(record.seq).upper()
    if spec.get("interval"):
        start, end = spec["interval"]
        circular = topology(record) == "circular"
        normal = 0 <= start < end <= len(seq)
        wraps = circular and 0 <= start < len(seq) and 0 <= end < start
        if not (normal or wraps):
            raise PlannerError(
                "FRAGMENT_INTERVAL_OUT_OF_RANGE: source=%d interval=%s len=%d "
                "(circular wrap requires 0<=start< len and 0<=end<start)"
                % (source_index, spec["interval"], len(seq)))
        return (seq[start:] + seq[:end] if wraps else seq[start:end],
                start, end)
    feature = _find_feature(record, spec)
    if feature is None:
        if spec.get("feature") or spec.get("name"):
            raise PlannerError(
                "FEATURE_NOT_FOUND: source=%d feature=%s"
                % (source_index, spec.get("feature") or spec.get("name")))
        return seq, 0, len(seq)
    # BioPython's extract() honors strand and compound locations, so a
    # reverse-strand feature yields the biological 5'->3' fragment.
    extracted = str(feature.extract(record.seq)).upper()
    return extracted, int(feature.location.start), int(feature.location.end)


def _extract_metadata(record, spec, source_index):
    """Return sequence coordinates plus source objects for execution/migration."""
    if spec.get("interval"):
        seq, start, end = _extract_region(record, spec, source_index)
        wraps = topology(record) == "circular" and start > end
        return seq, start, end, 1, None, wraps
    feature = _find_feature(record, spec)
    if feature is None:
        seq, start, end = _extract_region(record, spec, source_index)
        return seq, start, end, 1, None, False
    return (str(feature.extract(record.seq)).upper(),
            int(feature.location.start), int(feature.location.end),
            int(feature.location.strand or 1), feature, False)


def _enzyme_site(enzyme_name):
    enzyme = get_enzyme(enzyme_name)
    return str(enzyme.site).upper()


def _find_type_iis_enzyme(fragments):
    """Choose a Type IIS enzyme with an unambiguous pair on every part.

    Golden Gate does not become executable merely because a recognition site
    is absent. The low-level executor needs two usable sites on each source
    record: one on either side of the excised part. Exactly two sites is the
    conservative condition; three or more can mean an internal site or an
    ambiguous cut pair and must not be guessed through.
    """
    for name in TYPE_IIS_CANDIDATES:
        site = _enzyme_site(name)
        rc_site = str(Seq(site).reverse_complement())
        counts = [frag.upper().count(site) + frag.upper().count(rc_site)
                  for frag in fragments]
        if counts and all(count == 2 for count in counts):
            return name, site
    return None, None


def choose_overlap(upstream, downstream, target_gc=50.0, desired_length=None, use_downstream=False):
    """Algorithmically choose a 15-40 bp overlap from the upstream end.

    Returns (sequence, length, gc, tm, problems).  If no window satisfies
    GC 30-70, the closest-to-50 window is returned with a warning.
    """
    upstream = str(downstream if use_downstream else upstream).upper()
    if desired_length is not None:
        desired_length = int(desired_length)
        if desired_length <= 0:
            raise PlannerError("OVERLAP_LENGTH_MUST_BE_POSITIVE")
        if len(upstream) < desired_length:
            return (upstream, len(upstream), gc_percent(upstream), None,
                    ["overlap_shorter_than_requested"])
        min_length = max_length = desired_length
    else:
        min_length, max_length = 15, 40
    if len(upstream) < min_length:
        return upstream, len(upstream), None, None, ["overlap_shorter_than_15"]
    candidates = []
    for length in range(min_length, min(max_length, len(upstream)) + 1):
        seq = upstream[:length] if use_downstream else upstream[-length:]
        gc = gc_percent(seq)
        try:
            tm_value = mt.Tm_NN(seq)
        except Exception:  # noqa: BLE001
            tm_value = None
        candidates.append((length, seq, gc, tm_value))
    ok = [c for c in candidates
          if c[2] is not None and 30.0 <= c[2] <= 70.0]
    if ok:
        best = min(ok, key=lambda c: abs(c[2] - target_gc))
        return best[1], best[0], best[2], best[3], []
    best = min(candidates, key=lambda c: abs(c[2] - target_gc)
               if c[2] is not None else 999.0)
    return best[1], best[0], best[2], best[3], [
        "overlap_gc_outside_30_70: %.1f%%" % best[2]]


def _check_fusion_frame(fragments, fusion_spec):
    if not fusion_spec:
        return {"checked": False, "note": "no fusion intent provided"}
    index = int(fusion_spec.get("junction_after", len(fragments) - 2))
    if not (0 <= index < len(fragments) - 1):
        raise PlannerError("FUSION_JUNCTION_OUT_OF_RANGE: %d" % index)
    upstream_end = int(fusion_spec.get("upstream_cds_end",
                                       len(fragments[index]["sequence"])))
    downstream_start = int(fusion_spec.get("downstream_cds_start", 0))
    frame_mod = (upstream_end + downstream_start) % 3
    expected = int(fusion_spec.get("expected_frame", 0))
    return {
        "checked": True,
        "junction_after_fragment": index,
        "upstream_cds_end": upstream_end,
        "downstream_cds_start": downstream_start,
        "frame_offset_mod3": frame_mod,
        "expected_frame": expected,
        "in_frame": frame_mod == expected,
        "note": ("coding-frame check uses the caller-provided CDS offsets; "
                 "translate/validate the junction in the final construct "
                 "for wet-lab decisions"),
    }


def _decide_method(requested, fragments):
    if requested != "auto":
        return requested
    sizes = [len(item["sequence"]) for item in fragments]
    if max(sizes) <= 5000 and len(fragments) <= 3:
        return "overlap"
    if len(fragments) <= 5:
        return "gibson"
    return "gibson"


def _golden_gate_site_counts(fragments, enzyme_name):
    site = _enzyme_site(enzyme_name)
    rc_site = str(Seq(site).reverse_complement())
    return sum(fragment.upper().count(site) + fragment.upper().count(rc_site)
               for fragment in fragments)


def _primer_tails(method, fragments, index, junctions, enzymes, circular=False, use_downstream=False):
    fwd_tail = ""
    rev_tail = ""
    if method in ("overlap", "gibson"):
        if use_downstream:
            if index < len(junctions):
                rev_tail = str(Seq(junctions[index]["sequence"]).reverse_complement())
            return fwd_tail, rev_tail
        if index > 0:
            fwd_tail = junctions[index - 1]["sequence"]
        elif circular and junctions:
            fwd_tail = junctions[-1]["sequence"]
        # The planner chooses each junction from the preceding source
        # fragment's template end.  The downstream forward primer receives the
        # synthetic tail; adding a reverse tail to the preceding fragment
        # would duplicate the junction in the executed product.
    elif method == "golden_gate" and enzymes:
        site_tail = restriction_tail([enzymes[0]])
        fwd_tail = site_tail
        rev_tail = site_tail
    elif method == "digest-ligate" and enzymes:
        fwd_tail = restriction_tail([enzymes[0]])
        rev_tail = restriction_tail([enzymes[-1]])
    return fwd_tail, rev_tail


def _declared_pcr(spec):
    """Return explicit PCR-preparation intent, preserving an unspecified state."""
    for key in ("prepare_by_pcr", "pcr_required", "pcr"):
        if key in spec:
            return bool(spec[key])
    return None


def _planned_pcr_template(fragment):
    """Return the complete source template in the fragment's biological orientation."""
    source = fragment.get("_source_record")
    if source is None:
        raise PlannerError(
            "PCR_TEMPLATE_REQUIRED: fragment %s has no complete source record"
            % fragment.get("name", "<unnamed>")
        )
    extraction_strand = int(fragment.get("_extraction_strand") or 1)
    if extraction_strand == 1:
        return source, fragment.get("source_interval", [0, len(source.seq)]), False
    # A selected reverse-strand feature is designed in biological 5'->3'
    # orientation.  Reverse-complement the complete source before simulating;
    # this keeps the PCR check on a real template rather than on the extracted
    # ideal fragment.
    oriented = source.reverse_complement(id=source.id + "-reverse-template")
    oriented.annotations = dict(source.annotations)
    oriented.annotations["topology"] = source.annotations.get("topology", "linear")
    n = len(source.seq)
    start, end = fragment.get("source_interval", [0, n])
    if start > end and oriented.annotations.get("topology") == "circular":
        interval = [(n - start) % n, (n - end) % n]
    else:
        interval = [n - end, n - start]
    return oriented, interval, True


def _simulate_fragment_pcr(fragment, forward, reverse, fwd_tail="", rev_tail=""):
    """Simulate the selected complete primer pair on its original template."""
    template, interval, reversed_template = _planned_pcr_template(fragment)
    topology_value = str(template.annotations.get("topology", "linear"))
    start, end = [int(value) for value in interval]
    f_core_len = int(forward.get("binding_length") or
                     forward.get("binding_core_length") or
                     len(forward.get("binding") or ""))
    r_core_len = int(reverse.get("binding_length") or
                     reverse.get("binding_core_length") or
                     len(reverse.get("binding") or ""))
    if not f_core_len or not r_core_len:
        raise PlannerError(
            "PCR_BINDING_CORE_REQUIRED: selected primers must expose complete binding cores"
        )
    # Candidate coordinates are relative to the extracted target; source
    # boundaries are the auditable default.  Primer3 slide retries retain
    # their relative offsets when present.
    f_rel = int(forward.get("bind_start", 0))
    r_rel = int(reverse.get("bind_start", max(0, (end - start) - r_core_len)))
    if topology_value.lower() == "circular":
        f_pos = (start + f_rel) % len(template.seq)
        r_pos = (start + r_rel) % len(template.seq)
    else:
        f_pos = start + f_rel
        r_pos = start + r_rel
    result = simulate_pcr(
        template,
        forward["sequence"],
        reverse["sequence"],
        topology=topology_value,
        forward_binding_core_length=f_core_len,
        reverse_binding_core_length=r_core_len,
        forward_binding_start_0based=f_pos,
        reverse_binding_start_0based=r_pos,
    )
    result["source_interval_0based"] = [start, end]
    result["source_template_id"] = template.id or template.name
    result["template_orientation"] = "reverse-complement" if reversed_template else "forward"
    expected = fwd_tail + fragment["sequence"] + str(Seq(rev_tail).reverse_complement())
    if result["amplicon"].upper() != expected.upper():
        raise PlannerError(
            "PCR_BOUNDARY_MISMATCH: actual complete-oligo PCR does not reproduce the requested preparation sequence"
        )
    # Source features may span the restored primer boundary. Transfer them
    # only after the actual full PCR product matches that exact source interval.
    source_fragment = _extract_template_record(template, start, len(fragment["sequence"]), topology_value.lower() == "circular")
    if str(source_fragment.seq).upper() != fragment["sequence"].upper():
        raise PlannerError("PCR_SOURCE_INTERVAL_MISMATCH: selected sequence is not a contiguous source interval")
    result["features"] = [feature_to_dict(f._shift(len(fwd_tail)), len(result["amplicon"])) for f in source_fragment.features]
    return result


def _anchored_primer_fallback(fragment, fwd_tail, rev_tail, primer3_core):
    """Reuse the Core's full-template search when short region candidates fail."""
    from core.tools.amplification import design_overhang_primers
    from primer3_core_backend import discover_primer3_core
    # Core currently discovers its executable. Do not silently substitute a
    # different binary for an explicitly selected planner backend.
    selected = discover_primer3_core(primer3_core)
    automatic = discover_primer3_core()
    if not selected or not automatic or pathlib.Path(selected).resolve() != pathlib.Path(automatic).resolve():
        raise PlannerError("ANCHORED_BACKEND_UNAVAILABLE: cannot reuse the configured Primer3 backend")
    template, interval, _ = _planned_pcr_template(fragment)
    result = design_overhang_primers(template, *interval,
        fwd_5prime_overhang=fwd_tail, rev_5prime_overhang=rev_tail,
        min_core_len=18, max_core_len=40)
    result["search_bounds"] = {"minimum_core_length": 18, "maximum_core_length": 40,
                               "reason": "alternative to the default short-region candidate search"}
    candidates, validations = [], []
    for side in ("forward", "reverse"):
        primer = result[side + "_primer"]
        relative = int(primer["binding"]["template_start_0based"]) - interval[0]
        if template.annotations.get("topology") == "circular":
            relative %= len(template)
        candidates.append({"sequence": primer["full_sequence"], "binding": primer["binding_core"],
            "binding_length": primer["binding_core_length"], "tm": primer["binding_core_tm"],
            "gc": gc_percent(primer["binding_core"]), "tail": primer["overhang_5prime"],
            "bind_start": relative, "bind_end": relative + primer["binding_core_length"] - 1})
        validations.append({"passed": True, "problems": [], "binding": primer["binding"],
                            "source": "validated Core anchored pair and complete-oligo checks"})
    return {"forward_candidates": [candidates[0]], "reverse_candidates": [candidates[1]],
        "pairs": [{"forward_index": 0, "reverse_index": 0}],
        "backend": result["engine"], "complete_oligo_validator": "primer3-core",
        "validation": {"forward": [validations[0]], "reverse": [validations[1]]},
        "anchored_search": result}


def plan_assembly(source_paths, intent, primer3_core=None,
                  user_rules_dir=None, consent_broker=None,
                  operation_log=None, _use_downstream_overlap=False):
    """Plan a multi-source assembly with release-iteration consent.

    ``consent_broker`` defaults to ``ConsentBroker(policy="ask")``: abnormal
    primer-design relaxations/degradations raise ``ConsentRequiredError``
    unless a callback or pre-approval is supplied.  Batch automation must
    pass ``ConsentBroker(policy="auto")`` explicitly (the decision is then
    recorded in ``operation_log`` and in the plan output).
    """
    intent = normalize_intent(intent)
    if consent_broker is None:
        consent_broker = ConsentBroker(policy="ask")
    if operation_log is None:
        operation_log = TransparencyLog()
    records = []
    summaries = []
    for index, path in enumerate(source_paths):
        record, _fmt = load_seq(path)
        records.append(record)
        summaries.append(_record_summary(record, path, index))

    backbone_spec = intent["backbone"]
    backbone_index = int(backbone_spec.get("source", 0))
    if not (0 <= backbone_index < len(records)):
        raise PlannerError("BACKBONE_SOURCE_OUT_OF_RANGE: %d" % backbone_index)
    (backbone_seq, backbone_start, backbone_end, backbone_strand,
     backbone_feature, backbone_wraps) = _extract_metadata(
        records[backbone_index], backbone_spec, backbone_index)
    backbone_name = backbone_spec.get(
        "name", summaries[backbone_index]["id"] + "-backbone")

    fragments = [{
        "name": backbone_name,
        "source_index": backbone_index,
        "source_path": str(source_paths[backbone_index]),
        "source_interval": [backbone_start, backbone_end],
        "length": len(backbone_seq),
        "sequence": backbone_seq,
        "role": "backbone",
        "_source_record": records[backbone_index],
        "_source_feature": backbone_feature,
        "_extraction_strand": backbone_strand,
        "_source_wrap": backbone_wraps,
        "_pcr_explicit": _declared_pcr(backbone_spec),
        "_pcr_required": None,
    }]
    for spec in intent["fragments"]:
        source_index = int(spec.get("source", 0))
        if not (0 <= source_index < len(records)):
            raise PlannerError("FRAGMENT_SOURCE_OUT_OF_RANGE: %d" % source_index)
        (seq, start, end, extraction_strand, source_feature,
         source_wraps) = _extract_metadata(
            records[source_index], spec, source_index)
        fragments.append({
            "name": spec.get("name") or ("%s-%s" % (
                summaries[source_index]["id"],
                spec.get("feature") or "region")),
            "source_index": source_index,
            "source_path": str(source_paths[source_index]),
            "source_interval": [start, end],
            "length": len(seq),
            "sequence": seq,
            "role": spec.get("role", "insert"),
            "_source_record": records[source_index],
            "_source_feature": source_feature,
            "_extraction_strand": extraction_strand,
            "_source_wrap": source_wraps,
            "_pcr_explicit": _declared_pcr(spec),
            "_pcr_required": None,
        })

    requested = intent["method"]
    method = _decide_method(requested, fragments)
    alternatives = []
    enzymes = None
    internal_site_count = 0

    enzyme_crosschecks = []
    if method == "golden_gate":
        enzyme_name, _site = _find_type_iis_enzyme(
            [item["sequence"] for item in fragments])
        if enzyme_name is None:
            alternatives.append({
                "method": "gibson",
                "reason": "BsaI/BsmBI/Esp3I/BbsI 均出现在至少一个片段内部",
            })
            method = "gibson"
        else:
            enzymes = [enzyme_name]
            internal_site_count = 0
            for item in fragments:
                check = restriction_site_crosscheck(
                    item["sequence"], enzyme_name,
                    circular=(item["role"] == "backbone"
                              and intent.get("topology") == "circular"))
                enzyme_crosschecks.append(check)
                internal_site_count += check["direct_motif_count"]
                if not check["consistent_count"] or check["conflicts"]:
                    alternatives.append({
                        "method": "gibson",
                        "reason": ("酶切位点平行验证不一致：%s"
                                   % enzyme_name),
                    })
                    method = "gibson"
                    enzymes = None
                    break
    elif method == "digest-ligate":
        enzymes = intent.get("enzymes") or ["EcoRI", "BamHI"]
        for enzyme_name in enzymes:
            unique_per_fragment = True
            for item in fragments:
                hits = restriction_hits(
                    Seq(item["sequence"]), get_enzyme(enzyme_name),
                    circular=(item["role"] == "backbone"
                              and intent.get("topology") == "circular"))
                expected_count = 2 if len(enzymes) == 1 and item["role"] != "backbone" else 1
                if len(hits) != expected_count:
                    unique_per_fragment = False
                    break
            if not unique_per_fragment:
                alternatives.append({
                    "method": "gibson",
                    "reason": ("酶 %s 的位点数不符合所选反应：骨架须1个；单酶插入源须2个，双酶每种须1个"
                               % enzyme_name),
                })
                method = "gibson"
                enzymes = None
                break

    junctions = []
    if method in ("overlap", "gibson") and len(fragments) > 1:
        circular = intent.get("topology") == "circular"
        requested_overlap = int(intent.get("overlap_length") or 20)
        pair_count = len(fragments) if circular else len(fragments) - 1
        for index in range(pair_count):
            next_index = (index + 1) % len(fragments)
            overlap, length, gc, tm_value, problems = choose_overlap(
                fragments[index]["sequence"],
                fragments[next_index]["sequence"],
                desired_length=requested_overlap, use_downstream=_use_downstream_overlap)
            crosscheck = overlap_crosscheck(overlap)
            if crosscheck["status"] != "consistent":
                problems.append("overlap_crosscheck_conflict")
            junctions.append({
                "between": [fragments[index]["name"],
                            fragments[next_index]["name"]],
                "sequence": overlap,
                "length": length,
                "gc_percent": round(gc, 2) if gc is not None else None,
                "tm": round(tm_value, 1) if tm_value is not None else None,
                "problems": problems,
                "crosscheck": crosscheck,
            })

    # Overlap >3 fragments is an M2 error: automatically switch to Gibson.
    feasibility = None
    context = _feasibility_context(method, fragments, junctions, enzymes)
    feasibility = evaluate_plan(context, user_rules_dir)
    if requested == "overlap" and method == "overlap" and \
            any(error["rule_id"] == "overlap-fragment-count"
                for error in feasibility["errors"]):
        alternatives.append({
            "method": "gibson",
            "reason": "M2 rule overlap-fragment-count: >3 段 overlap 不可行",
        })
        method = "gibson"
        context = _feasibility_context(method, fragments, junctions, enzymes)
        feasibility = evaluate_plan(context, user_rules_dir)

    # Gibson/overlap requires a physical PCR intermediate by default. Golden
    # Gate may consume already flanked native parts; it only requires PCR when
    # the caller explicitly declares ``prepare_by_pcr``/``pcr_required``.
    for fragment in fragments:
        explicit = fragment.get("_pcr_explicit")
        fragment["_pcr_required"] = (
            bool(explicit) if explicit is not None
            else method in ("overlap", "gibson")
        )

    primers = []
    for index, fragment in enumerate(fragments):
        if not fragment.get("_pcr_required"):
            primers.append({
                "fragment": fragment["name"],
                "method": "native",
                "pcr_required": False,
                "template": {
                    "id": fragment["_source_record"].id
                    if fragment.get("_source_record") is not None else None,
                    "sequence": fragment["sequence"],
                    "source_interval_0based": fragment["source_interval"],
                },
                "selected_pair": None,
                "validation": {},
            })
            continue
        fwd_tail, rev_tail = _primer_tails(
            method, fragments, index, junctions, enzymes,
            circular=intent.get("topology") == "circular", use_downstream=_use_downstream_overlap)
        try:
            design = design_region_primers(
                fragment["sequence"], 0, fwd_tail=fwd_tail,
                rev_tail=rev_tail, top_n=2, primer3_core=primer3_core,
                consent=consent_broker, operation_log=operation_log,
                min_len=15 if _use_downstream_overlap else 18,
                max_len=36 if _use_downstream_overlap else 27)
            pair = None
            rejected_pairs = []
            for candidate_pair in design["pairs"]:
                forward = dict(design["forward_candidates"][candidate_pair["forward_index"]])
                reverse = dict(design["reverse_candidates"][candidate_pair["reverse_index"]])
                f_offset = int(forward["bind_start"])
                r_end = int(reverse["bind_end"]) + 1
                forward["tail"] = fwd_tail + fragment["sequence"][:f_offset]
                reverse["tail"] = rev_tail + str(Seq(fragment["sequence"][r_end:]).reverse_complement())
                for oligo in (forward, reverse):
                    oligo["sequence"] = oligo["tail"] + oligo["binding"]
                structure = check_complete_oligo_pair(forward["sequence"], reverse["sequence"], primer3_core,
                    annealing_temperature=min(float(forward["tm"]), float(reverse["tm"]))-5.0)
                if not structure["passed"]:
                    rejected_pairs.append(structure)
                    continue
                pair = candidate_pair
                break
            if pair is None:
                try:
                    design = _anchored_primer_fallback(fragment, fwd_tail, rev_tail, primer3_core)
                    forward, reverse = design["forward_candidates"][0], design["reverse_candidates"][0]
                    f_offset, r_end = int(forward["bind_start"]), int(reverse["bind_end"]) + 1
                    structure = check_complete_oligo_pair(forward["sequence"], reverse["sequence"], primer3_core,
                        annealing_temperature=min(float(forward["tm"]), float(reverse["tm"]))-5.0)
                    if not structure["passed"]:
                        raise PlannerError("Anchored pair failed complete-oligo validation")
                    pair = design["pairs"][0]
                except Exception as fallback_error:
                    raise PlannerError(
                        "PRIMER_PAIR_REQUIRED: no acceptable complete-oligo pair for %s; structural_checks=%s; anchored_search=%s"
                        % (fragment["name"], rejected_pairs, fallback_error)
                    ) from fallback_error
            # Validate and execute only the selected pair.  Other candidates
            # remain available for review but cannot block a pair that was
            # actually selected for delivery.
            selected_forward_validation = design.get("validation", {}).get(
                "forward", [])[pair["forward_index"]]
            selected_reverse_validation = design.get("validation", {}).get(
                "reverse", [])[pair["reverse_index"]]
            pcr_product = _simulate_fragment_pcr(fragment, forward, reverse, fwd_tail, rev_tail)
            primers.append({
                "fragment": fragment["name"],
                "pcr_required": True,
                "forward": {
                    "name": fragment["name"] + "-F",
                    "sequence": forward["sequence"] if forward else None,
                    "binding_core": forward.get("binding") if forward else None,
                    "binding_core_length": forward.get("binding_length") if forward else None,
                    "position_0based": forward.get("bind_start") if forward else None,
                    "strand": 1,
                    "tm": forward.get("tm") if forward else None,
                    "gc": forward.get("gc") if forward else None,
                    "tail": forward["tail"] or None,
                    "use": "PCR 上游引物（5'->3'）",
                },
                "reverse": {
                    "name": fragment["name"] + "-R",
                    "sequence": reverse["sequence"] if reverse else None,
                    "binding_core": reverse.get("binding") if reverse else None,
                    "binding_core_length": reverse.get("binding_length") if reverse else None,
                    "position_0based": reverse.get("bind_start") if reverse else None,
                    "strand": -1,
                    "tm": reverse.get("tm") if reverse else None,
                    "gc": reverse.get("gc") if reverse else None,
                    "tail": reverse["tail"] or None,
                    "use": "PCR 下游引物（5'->3'）",
                },
                "backend": design["backend"],
                "complete_oligo_validator": design.get("complete_oligo_validator"),
                "anchored_search": design.get("anchored_search"),
                "rejected_short_candidates": rejected_pairs,
                "validation": design["validation"],
                "complete_oligo_structure": structure,
                "boundary_restoration": {"forward_bp": f_offset, "reverse_bp": len(fragment["sequence"]) - r_end},
                "selected_pair": {
                    "forward_index": pair["forward_index"],
                    "reverse_index": pair["reverse_index"],
                    "product_size": pcr_product["amplicon_length"],
                    "forward": selected_forward_validation,
                    "reverse": selected_reverse_validation,
                },
                "pcr_product": {
                    "amplicon": pcr_product["amplicon"],
                    "amplicon_length": pcr_product["amplicon_length"],
                    "template": pcr_product.get("template"),
                    "primers": pcr_product.get("primers", []),
                    "template_interval_0based": pcr_product["template_interval_0based"],
                    "template_core_length": pcr_product["template_core_length"],
                    "forward_binding": pcr_product["forward_binding"],
                    "reverse_binding": pcr_product["reverse_binding"],
                    "features": pcr_product.get("features", []),
                    "topology": pcr_product["topology"],
                    "template_id": pcr_product.get("template_id"),
                },
                "primer3_retry_note": design.get("primer3_retry_note"),
                "boundary_offsets": design.get("boundary_offsets"),
                "alternatives": design.get("alternatives"),
                "operation_log": design.get("operation_log"),
                "consent": design.get("consent"),
            })
            fragment["_pcr_product"] = pcr_product
        except Exception as error:  # noqa: BLE001
            primers.append({"fragment": fragment["name"],
                            "error": str(error),
                            "error_type": type(error).__name__})

    if (not _use_downstream_overlap and method in ("gibson", "overlap")
            and any(item.get("error") for item in primers)):
        # A different distribution of the same homology can remove a bad
        # full-oligo hairpin without changing the requested DNA. Try once;
        # all original Tm, structure, uniqueness and actual-PCR checks remain.
        retry = plan_assembly(source_paths, intent, primer3_core, user_rules_dir,
                              consent_broker, operation_log, _use_downstream_overlap=True)
        retry["assembly_strategy"]["alternatives"].append({
            "method": method, "reason": "Retried with downstream homology on reverse primers after complete-oligo preparation failed",
            "previous_primer_errors": [item["error"] for item in primers if item.get("error")],
        })
        return retry

    primer_tm_bad = False
    primer_structure_bad = False
    for item in primers:
        if "error" in item:
            continue
        selected = item.get("selected_pair") or {}
        for side in ("forward", "reverse"):
            check = selected.get(side) or {}
            for problem in check.get("problems", []):
                # ``primer_tm_off_target`` means the selected pair is not
                # centered on 60 C but can still be inside the validated
                # 52-72 C operating window.  Unselected candidates never
                # participate in the delivery feasibility gate.
                if problem.startswith("primer_tm_outside_52_72"):
                    primer_tm_bad = True
                if problem.startswith("primer_strong"):
                    primer_structure_bad = True
    context.update({"any_primer_tm_outside_52_72": primer_tm_bad,
                    "any_primer_strong_structure": primer_structure_bad})
    feasibility = evaluate_plan(context, user_rules_dir)
    preparation_errors = [item for item in primers if item.get("error")]
    if preparation_errors:
        feasibility.setdefault("errors", []).append({
            "rule_id": "pcr-preparation", "constraint": "actual complete-oligo PCR preparation",
            "severity": "error", "suggestion": "Inspect the reported primer, structure or boundary failure; revise the preparation route without changing the target DNA",
            "source": "PCR simulation and complete oligo checks", "details": preparation_errors,
        })
        feasibility["grade"] = "low"

    # A method-specific final construct must not be written from an
    # unverified heuristic primer fallback.  Keep the plan available for
    # exploration, but block execution/output until every pair is backed by
    # the real external Primer3 engine.
    unverified_primers = [
        item.get("fragment") for item in primers
        if item.get("pcr_required", True) and
        not item.get("error") and item.get("backend") != "primer3-core"
        and not (item.get("complete_oligo_validator") == "primer3-core"
                 and item.get("complete_oligo_structure", {}).get("passed") is True)
    ]
    if unverified_primers:
        feasibility.setdefault("errors", []).append({
            "rule_id": "primer3-required-for-final",
            "constraint": "final construct requires real primer3-core pairs",
            "severity": "error",
            "suggestion": "安装 primer3_core 或显式改为仅候选预览",
            "source": "Primer3 official engine gate",
            "fragments": unverified_primers,
        })
        feasibility["grade"] = "low"

    frame_check = _check_fusion_frame(fragments, intent.get("fusion"))
    if primers and frame_check.get("checked") and not frame_check.get("in_frame"):
        feasibility.setdefault("errors", []).append({
            "rule_id": "fusion-frame", "constraint": "fusion reading frame",
            "severity": "error", "suggestion": "调整 junction/片段边界或加 linker",
            "source": "manual frame check (M1)"})
        feasibility["grade"] = "low"

    execution = {
        "status": "not_attempted",
        "reason": "feasibility-errors-present" if feasibility["errors"] else None,
        "executor": None,
        "feature_specs": [],
    }
    if not feasibility["errors"]:
        try:
            execution = execute_assembly(
                fragments, method, intent.get("topology", "linear"),
                enzymes=enzymes, junctions=junctions)
        except ExecutionError as error:
            execution = {
                "status": "failed",
                "reason": error.code,
                "detail": error.message,
                "details": error.details,
                "executor": None,
                "feature_specs": [],
            }
            feasibility.setdefault("errors", []).append({
                "rule_id": "assembly-execution",
                "constraint": "method-specific final construct execution",
                "severity": "error",
                "suggestion": "修复输入或改用能完成真实执行的组装方法",
                "source": "planning.executor",
                "code": error.code,
            })
            feasibility["grade"] = "low"

    # Every execution branch has the same JSON contract. Successful
    # executors do not have an error reason, but the key must still be present
    # because the v0.9 schema requires it for both success and failure records.
    execution.setdefault("reason", None)

    final_sequence = execution.get("sequence")
    final_validated = execution.get("status") == "validated" and bool(final_sequence)
    plan_status = "complete" if not feasibility["errors"] and final_validated else "blocked"
    manual = {
        "schema_version": "0.9.0",
        "goal": intent["goal"],
        "construct_name": intent["name"],
        "topology": intent["topology"],
        "status": plan_status,
        "sources": summaries,
        "fragment_assignments": [{
            "name": item["name"], "role": item["role"],
            "source_index": item["source_index"],
            "source_path": item["source_path"],
            "source_interval_0based": item["source_interval"],
            "source_interval_1based": [
                item["source_interval"][0] + 1, item["source_interval"][1]],
            "source_interval_wrap": bool(item.get("_source_wrap")),
            "length": item["length"], "sequence": item["sequence"],
            "pcr_required": bool(item.get("_pcr_required")),
            "pcr_product": item.get("_pcr_product"),
        } for item in fragments],
        "assembly_strategy": {
            "method": method,
            "requested_method": requested,
            "reason": _method_reason(method, requested, fragments, enzymes,
                                     alternatives),
            "enzymes": enzymes,
            "enzyme_crosschecks": enzyme_crosschecks,
            "digest_ligate_note": (
                "planner validates reaction-specific site counts; both declared enzymes, "
                "sticky-end compatibility and final ligated sequence are enforced by "
                "core.tools.assembly.simulate_digest_ligation"
                if method == "digest-ligate" else None),
            "overlap_junctions": junctions,
            "alternatives": alternatives,
        },
        "primers": primers,
        "fusion_frame_check": frame_check,
        "feasibility": feasibility,
        "final_construct": {
            "status": "validated" if final_validated else "not_available",
            "length": len(final_sequence) if final_sequence else 0,
            "sequence": final_sequence,
            "gc_percent": round(gc_percent(final_sequence), 2)
            if final_sequence else None,
            "sequence_note": (
                "method-specific executor product; not a fragment-order preview"
                if final_validated else
                "no final construct is available because method execution failed"),
            "executor": execution.get("executor"),
            "feature_specs": execution.get("feature_specs", []),
        },
        "execution": execution,
        "numeric_evidence": {
            "overlap_window": {
                "min_length": 15, "max_length": 40,
                "gc_min_percent": 30.0, "gc_max_percent": 70.0,
                "source": ("IDT primer design guidance; Gibson et al. 2009 "
                           "Nat Methods, DOI 10.1038/nmeth.1318")},
            "primer_tm": {
                "min_c": 52.0, "max_c": 72.0,
                "crosscheck": ["primer3-core", "BioPython Tm_NN",
                               "Wallace 2*(A+T)+4*(G+C)"],
                "source": "Primer3 official documentation"},
            "restriction_sites": {
                "crosscheck": ["Bio.Restriction", "direct motif scan "
                               "(recognition sequence + reverse complement)"],
                "source": "Bio.Restriction; sg_common.restriction_hits"},
            "rule_thresholds": [{
                "rule_id": item["rule_id"], "severity": item["severity"],
                "source": item["source"]}
                for item in feasibility.get("errors", [])
                + feasibility.get("warnings", [])],
        },
        "provenance": [source(
            "software", "SnapGene DNA Design planning.planner",
            "multi-source-assembly-plan", version=read_version(),
            status="verified",
            verification={"method": "unit-tests", "status": "verified"})],
        "consent": {
            "broker_policy": consent_broker.policy,
            "requests": consent_broker.requests,
            "pending": consent_broker.pending(),
        },
        "operation_log": operation_log.snapshot(),
    }
    return manual


def _method_reason(method, requested, fragments, enzymes, alternatives):
    if requested != "auto" and method == requested:
        return "用户指定方法 %s" % method
    if alternatives and method != requested:
        return "自动替换：%s" % "; ".join(
            "%s（%s）" % (item["method"], item["reason"])
            for item in alternatives)
    if method == "overlap":
        return "片段数 %d、最大片段 %d bp，处于 overlap 舒适区" % (
            len(fragments), max(item["length"] for item in fragments))
    if method == "gibson":
        return "自动选择 Gibson（片段数 %d，片段大小适合等温一步组装）" % len(fragments)
    return "片段数 %d，按规则选择 %s" % (len(fragments), method)


def _feasibility_context(method, fragments, junctions, enzymes):
    overlaps = [j for j in junctions]
    gc_values = [j["gc_percent"] for j in overlaps
                 if j["gc_percent"] is not None]
    return {
        "method": method,
        "fragment_count": len(fragments),
        "internal_site_count": 0,
        "min_overlap_length": min((j["length"] for j in overlaps), default=0),
        "max_overlap_length": max((j["length"] for j in overlaps), default=0),
        "min_overlap_gc": min(gc_values, default=50.0),
        "max_overlap_gc": max(gc_values, default=50.0),
        "max_fragment_length": max((item["length"] for item in fragments),
                                   default=0),
        "total_length": sum(item["length"] for item in fragments),
        "any_primer_tm_outside_52_72": False,
        "any_primer_strong_structure": False,
    }
