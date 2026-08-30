# -*- coding: utf-8 -*-
"""Three-layer validation: artifact-valid, computation-valid, goal-valid.

``verified`` is derived exclusively as:
    verified = artifact_valid AND computation_valid AND goal_valid

``goal_valid`` starts false and becomes true only after every mandatory
goal check for the task kind has actually executed and passed.  Goal
checks must use independent evidence (the input records and the task
contract), never labels that the executor itself stamped from the task.
"""
from __future__ import annotations

import pathlib

from Bio import SeqIO
from Bio.Seq import Seq

from core.errors import ValidationError
from core.registry import NEAR_FULL_RATIO  # noqa: F401 (single source)


def _load(path, fmt=None):
    if fmt:
        return SeqIO.read(str(path), fmt)
    from core.task import read_record
    return read_record(path)


def _circular_equal(a, b):
    a, b = str(a).upper(), str(b).upper()
    if len(a) != len(b):
        return False
    double = a + a
    if any(double[i:i + len(a)] == b for i in range(len(a))):
        return True
    rc = str(Seq(a).reverse_complement())
    double = rc + rc
    return any(double[i:i + len(a)] == b for i in range(len(a)))


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(str(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _arc(record, start0, end0):
    seq = str(record.seq)
    n = len(seq)
    start0 = int(start0) % n
    end0 = int(end0) % n
    if start0 == end0:
        return seq
    if start0 < end0:
        return seq[start0:end0]
    return seq[start0:] + seq[:end0]


def _find_feature(record, selection):
    """Locate the unique feature referenced by the task selection.

    Mirrors the planner's matching rule but re-reads the file, so the
    computation layer does not reuse planner state.
    """
    wanted_id = selection.get("feature_id")
    wanted_name = selection.get("feature_name")
    candidates = []
    for feature in record.features:
        q = feature.qualifiers
        fid = (q.get("id") or [None])[0]
        labels = list(q.get("label") or []) + list(q.get("note") or [])
        fname = (q.get("name") or q.get("gene") or [None])[0]
        if wanted_id and fid == wanted_id:
            candidates.append(feature)
        elif wanted_name and (fname == wanted_name or
                              wanted_name in labels or
                              feature.type == wanted_name):
            candidates.append(feature)
    if len(candidates) != 1:
        raise ValidationError(
            "COMPONENT_BOUNDARY_REQUIRED",
            "feature selection did not resolve to exactly one feature",
            details={"candidates": len(candidates)})
    return candidates[0]


def _extract_selection_sequence(record, selection):
    """Independent extraction for the computation layer."""
    if selection.get("kind") == "feature":
        feature = _find_feature(record, selection)
        return str(feature.extract(record).seq)
    interval = selection.get("interval_0based")
    if not isinstance(interval, list) or len(interval) != 2:
        raise ValidationError("COMPONENT_BOUNDARY_REQUIRED",
                              "selection lacks interval_0based")
    seq = _arc(record, interval[0], interval[1])
    if int(selection.get("strand", 1)) == -1:
        seq = str(Seq(seq).reverse_complement())
    return seq


def _recompute(task):
    kind = task["task_kind"]
    if kind == "component_amplification":
        template = [s for s in task["sources"] if s["role"] == "template"][0]
        record = _load(template["_resolved_path"])
        sel = task["target"]["selection"]
        component = _extract_selection_sequence(record, sel)
        arms = task.get("operation", {}).get("homology_arms") or {}
        return str(arms.get("left_arm") or "") + component + \
            str(arms.get("right_arm") or "")
    if kind == "integration_donor":
        template = [s for s in task["sources"] if s["role"] == "template"][0]
        record = _load(template["_resolved_path"])
        sel = task["target"]["selection"]
        component = _extract_selection_sequence(record, sel)
        arms = task["operation"]["homology_arms"]
        return str(arms.get("left_arm") or "") + component + \
            str(arms.get("right_arm") or "")
    if kind == "plasmid_replace":
        backbone = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bseq = str(_load(backbone["_resolved_path"]).seq)
        op = task["operation"]["replace"]
        a, b = op["interval_0based"]
        replacement = [s for s in task["sources"]
                       if s["role"] in ("replacement", "insert")][0]
        rseq = str(_load(replacement["_resolved_path"]).seq)
        ra, rb = op["replacement_interval_0based"]
        repl = rseq[ra:rb]
        return bseq[:a] + repl + bseq[b:]
    if kind == "plasmid_insert":
        backbone = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bseq = str(_load(backbone["_resolved_path"]).seq)
        op = task["operation"]["insert"]
        pos = op["boundary_0based"]
        insert = [s for s in task["sources"] if s["role"] == "insert"][0]
        iseq = str(_load(insert["_resolved_path"]).seq)
        ia, ib = op["interval_0based"]
        return bseq[:pos] + iseq[ia:ib] + bseq[pos:]
    if kind == "point_mutation":
        template = [s for s in task["sources"] if s["role"] == "template"][0]
        bases = list(str(_load(template["_resolved_path"]).seq))
        for mut in task["operation"]["mutations"]:
            bases[int(mut["position_1based"]) - 1] = mut["alt"]
        return "".join(bases)
    if kind == "overlap_assembly":
        overlap = int(task["operation"]["overlap_length"])
        fragments = []
        for spec in sorted(task["operation"]["fragments"],
                           key=lambda item: int(item["order"])):
            source = next(s for s in task["sources"]
                          if s["source_id"] == spec["source_id"])
            record = _load(source["_resolved_path"])
            seq = _arc(record, spec["interval_0based"][0],
                       spec["interval_0based"][1])
            if int(spec.get("strand", 1)) == -1:
                seq = str(Seq(seq).reverse_complement())
            fragments.append(seq)
        circular = task["product"]["topology"] == "circular"
        if circular:
            return "".join(f[overlap:] for f in fragments)
        return fragments[0] + "".join(f[overlap:] for f in fragments[1:])
    if kind == "protein_fusion":
        op = task["operation"]
        host = str(task.get("host") or "").lower()
        table = int(op.get("translation_table") or
                    (11 if "coli" in host else 1))
        linker = str((op.get("linker") or {}).get("dna") or "")

        def load_partner(key):
            spec = op[key]
            source = next(s for s in task["sources"]
                          if s["source_id"] == spec["source_id"])
            record = _load(source["_resolved_path"])
            a, b = spec["interval_0based"]
            seq = _arc(record, a, b)
            if int(spec.get("strand", 1)) == -1:
                seq = str(Seq(seq).reverse_complement())
            return seq

        p5 = load_partner("partner5")
        p3 = load_partner("partner3")
        if p5[-3:].upper() in ("TAA", "TAG", "TGA"):
            p5 = p5[:-3]
        if op["stop_policy"] == "no-stop" and \
                p3[-3:].upper() in ("TAA", "TAG", "TGA"):
            p3 = p3[:-3]
        return p5 + linker + p3
    if kind == "gateway_recombination":
        import sys
        root = pathlib.Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "scripts"))
        from simulate_advanced import (ATTB1, ATTB2, ATTL1, ATTL2,
                                       ATTP1, ATTP2, ATTR1, ATTR2)
        op = task["operation"]

        def find_site(seq, site, reverse=False):
            query = str(Seq(site).reverse_complement()) if reverse else site
            positions = []
            start = 0
            while True:
                pos = seq.find(query, start)
                if pos == -1:
                    break
                positions.append(pos)
                start = pos + 1
            if len(positions) != 1:
                raise ValidationError(
                    "ATT_SITE_NOT_UNIQUE",
                    "expected exactly one oriented site; found %d"
                    % len(positions))
            return positions[0], positions[0] + len(query)

        if op["reaction"] == "lr":
            entry = next(s for s in task["sources"]
                         if s["source_id"] == op["entry_source_id"])
            dest = next(s for s in task["sources"]
                        if s["source_id"] == op["destination_source_id"])
            eseq = str(_load(entry["_resolved_path"]).seq).upper()
            dseq = str(_load(dest["_resolved_path"]).seq).upper()
            l1s, l1e = find_site(eseq, ATTL1)
            l2s, l2e = find_site(eseq, ATTL2, reverse=True)
            r1s, r1e = find_site(dseq, ATTR1)
            r2s, r2e = find_site(dseq, ATTR2, reverse=True)
            if l1e > l2s:
                raise ValidationError("ATT_SITE_ORDER",
                                      "entry att sites out of order")
            body = eseq[l1e:l2s]
            replacement = ATTB1 + body + str(Seq(ATTB2).reverse_complement())
            return dseq[:r1s] + replacement + dseq[r2e:]
        insert = next(s for s in task["sources"]
                      if s["source_id"] == op["entry_source_id"])
        donor = next(s for s in task["sources"]
                     if s["source_id"] == op["donor_vector_source_id"])
        iseq = str(_load(insert["_resolved_path"]).seq).upper()
        dseq = str(_load(donor["_resolved_path"]).seq).upper()
        b1s, b1e = find_site(iseq, ATTB1)
        b2s, b2e = find_site(iseq, ATTB2)
        p1s, p1e = find_site(dseq, ATTP1)
        p2s, p2e = find_site(dseq, ATTP2, reverse=True)
        if b1e > b2s:
            raise ValidationError("ATT_SITE_ORDER",
                                  "insert attB sites out of order")
        body = iseq[b1e:b2s]
        replacement = ATTL1 + body + str(Seq(ATTL2).reverse_complement())
        return dseq[:p1s] + replacement + dseq[p2e:]
    if kind == "restriction_ligation":
        import sys
        root = pathlib.Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "scripts"))
        from sg_common import get_enzyme, restriction_hits
        op = task["operation"]
        vector = next(s for s in task["sources"]
                      if s["source_id"] == op["vector_source_id"])
        insert = next(s for s in task["sources"]
                      if s["source_id"] == op["insert_source_id"])
        vrec = _load(vector["_resolved_path"])
        irec = _load(insert["_resolved_path"])
        if op["orientation"] == "reverse":
            irec = irec.reverse_complement(id=True, name=True,
                                           description=True)
        vseq = str(vrec.seq).upper()
        iseq = str(irec.seq).upper()
        enzymes = [str(e) for e in op["vector_enzymes"]]
        insert_enzymes = [str(e) for e in (op.get("insert_enzymes")
                                           or enzymes)]
        if len(enzymes) == 1 and insert_enzymes == enzymes:
            enzyme = get_enzyme(enzymes[0])
            vhits = [h for h in restriction_hits(vseq, enzyme, circular=True)
                     if h["cuts_within_sequence"]]
            if len(vhits) != 1:
                raise ValidationError("RESTRICTION_SITE_COUNT",
                                      "vector must cut exactly once")
            cut0 = vhits[0]["top_cut_boundary_0based"] % len(vseq)
            ihits = [h for h in restriction_hits(iseq, enzyme,
                                                 circular=False)
                     if h["cuts_within_sequence"]]
            if len(ihits) != 2:
                raise ValidationError("RESTRICTION_SITE_COUNT",
                                      "insert must cut exactly twice")
            site = str(enzyme.site).upper()
            rc_site = str(Seq(site).reverse_complement()).upper()
            t1 = ihits[0]["top_cut_boundary_0based"] % len(iseq)
            t2 = ihits[1]["top_cut_boundary_0based"] % len(iseq)
            frag_a = iseq[t1:t2] if t1 < t2 else iseq[t1:] + iseq[:t2]
            frag_b = iseq[t2:t1] if t2 < t1 else iseq[t2:] + iseq[:t1]
            chosen = None
            for fragment in (frag_a, frag_b):
                if fragment and site not in fragment and \
                        rc_site not in fragment:
                    chosen = fragment
                    break
            if chosen is None:
                raise ValidationError("INSERT_EXCISION_FAILED",
                                      "no clean insert fragment")
            return vseq[:cut0] + chosen + vseq[cut0:]
        vhits = []
        for enzyme_name in enzymes:
            hits = [h for h in restriction_hits(
                vseq, get_enzyme(enzyme_name), circular=True)
                if h["cuts_within_sequence"]]
            if len(hits) != 1:
                raise ValidationError("RESTRICTION_SITE_COUNT",
                                      "vector enzyme %s must cut once"
                                      % enzyme_name)
            vhits.append(hits[0])
        n = len(vseq)
        t1 = vhits[0]["top_cut_boundary_0based"] % n
        t2 = vhits[1]["top_cut_boundary_0based"] % n
        if t1 > t2:
            raise ValidationError("RESTRICTION_WRAP_UNSUPPORTED",
                                  "wrapped vector cuts")
        ihits = []
        for enzyme_name in insert_enzymes:
            hits = [h for h in restriction_hits(
                iseq, get_enzyme(enzyme_name), circular=False)
                if h["cuts_within_sequence"]]
            if len(hits) != 1:
                raise ValidationError("RESTRICTION_SITE_COUNT",
                                      "insert enzyme %s must cut once"
                                      % enzyme_name)
            ihits.append(hits[0])
        i1 = ihits[0]["top_cut_boundary_0based"] % len(iseq)
        i2 = ihits[1]["top_cut_boundary_0based"] % len(iseq)
        if i1 > i2:
            i1, i2 = i2, i1
        ins_frag = iseq[i1:i2]
        return vseq[:t1] + ins_frag + vseq[t2:]
    if kind == "hierarchical_assembly":
        stage_products = {}

        def string_arc(seq, a, b):
            n = len(seq)
            a, b = int(a) % n, int(b) % n
            return seq[a:b] if a <= b else seq[a:] + seq[:b]

        for stage in task["operation"]["stages"]:
            overlap = int(stage["overlap_length"])
            circular = stage["product_topology"] == "circular"
            fragments = []
            for spec in sorted(stage["fragments"],
                               key=lambda item: int(item["order"])):
                if spec.get("source_id"):
                    source = next(s for s in task["sources"]
                                  if s["source_id"] == spec["source_id"])
                    record = _load(source["_resolved_path"])
                    seq = _arc(record, spec["interval_0based"][0],
                               spec["interval_0based"][1])
                else:
                    if spec["stage_id"] not in stage_products:
                        raise ValidationError(
                            "HIERARCHICAL_STAGE_REFERENCE_MISSING",
                            "unknown stage %s" % spec["stage_id"])
                    parent = stage_products[spec["stage_id"]]
                    interval = spec.get("interval_0based")
                    seq = string_arc(parent, interval[0], interval[1]) \
                        if interval else parent
                if int(spec.get("strand", 1)) == -1:
                    seq = str(Seq(seq).reverse_complement())
                fragments.append(seq)
            pairs = (list(range(len(fragments))) if circular
                     else list(range(len(fragments) - 1)))
            for idx in pairs:
                left = fragments[idx][-overlap:]
                right = fragments[(idx + 1) % len(fragments)][:overlap]
                if left.upper() != right.upper():
                    raise ValidationError(
                        "OVERLAP_MISMATCH",
                        "stage %s fragment overlaps do not match"
                        % stage["stage_id"])
            if circular:
                product = "".join(f[overlap:] for f in fragments)
            else:
                product = fragments[0] + "".join(
                    f[overlap:] for f in fragments[1:])
            stage_products[stage["stage_id"]] = product
        return stage_products[task["operation"]["stages"][-1]["stage_id"]]
    if kind == "crispr_editing":
        op = task["operation"]
        ref = next(s for s in task["sources"] if s["role"] == "reference")
        ref_seq = str(_load(ref["_resolved_path"]).seq).upper()
        a, b = op["target_interval_0based"]
        donor = op.get("donor_strategy") or {}
        if not donor.get("donor_source_id"):
            return ref_seq
        dsrc = next(s for s in task["sources"]
                    if s["source_id"] == donor["donor_source_id"])
        drec = _load(dsrc["_resolved_path"])
        ra, rb = donor["replacement_interval_0based"]
        repl = _arc(drec, ra, rb)
        return ref_seq[:a] + repl + ref_seq[b:]
    raise ValidationError("TASK_KIND_NOT_IMPLEMENTED",
                          "no independent recompute for %s" % kind)


def _feature_text(feature):
    parts = []
    for key in ("label", "gene", "name", "note", "product", "locus_tag"):
        parts.extend(str(v) for v in feature.qualifiers.get(key, []))
    parts.append(feature.type)
    return " ".join(parts)


def _feature_labels(record):
    out = set()
    for feature in record.features:
        q = feature.qualifiers
        for key in ("label", "gene", "name", "note", "product"):
            for value in q.get(key, []):
                out.add(str(value))
        out.add(feature.type)
    return out


_VECTOR_BACKBONE_PATTERNS = (
    "bla", "amp", "ampr", "ampicillin", "beta-lactamase",
    "ori", "origin", "rep_origin", "pbr322", "cole1", "pmb1",
    "lacz", "lac", "ccdb", "cmr", "chloramphenicol",
)


def _overlaps(start, end, a, b, n):
    """True when feature [start,end) overlaps wrapped interval [a,b)."""
    if a <= b:
        return start < b and end > a
    return not (end <= a and start >= b)


def _required_evidence(task, product_record, product_seq):
    """Independent required-component evidence, per task kind."""
    required = list(task["product"].get("required_components") or [])
    if not required:
        return []
    kind = task["task_kind"]
    product_labels = _feature_labels(product_record)
    evidence = []
    if kind == "component_amplification":
        template = [s for s in task["sources"] if s["role"] == "template"][0]
        record = _load(template["_resolved_path"])
        sel = task["target"]["selection"]
        if sel.get("kind") == "interval":
            a, b = sel["interval_0based"]
            n = len(record)
            inside_text = " ".join(
                _feature_text(f) for f in record.features
                if f.type != "source"
                and _overlaps(int(f.location.start), int(f.location.end),
                              a, b, n)).lower()
        else:
            feature = _find_feature(record, sel)
            inside_text = _feature_text(feature).lower()
        for name in required:
            # Independent evidence only: the product's own labels are
            # stamped by the executor from this same list, so consulting
            # them here would be circular.
            ok = name.lower() in inside_text
            evidence.append({"name": name, "present": bool(ok),
                             "source": "template-feature-overlap" if ok
                             else "not-found"})
    elif kind == "protein_fusion":
        texts = []
        for key in ("partner5", "partner3"):
            spec = task["operation"][key]
            source = next(s for s in task["sources"]
                          if s["source_id"] == spec["source_id"])
            record = _load(source["_resolved_path"])
            a, b = spec["interval_0based"]
            n = len(record)
            for feature in record.features:
                if feature.type == "source":
                    continue
                if _overlaps(int(feature.location.start),
                             int(feature.location.end), a, b, n):
                    texts.append(_feature_text(feature))
        joined = " ".join(texts).lower()
        for name in required:
            ok = name.lower() in joined or \
                name.lower() in " ".join(sorted(product_labels)).lower()
            evidence.append({"name": name, "present": bool(ok),
                             "source": "partner-feature-overlap" if ok
                             else "not-found"})
    else:
        # Independent evidence: input record ids/names and transferred
        # features.  A required name must trace to a real input record.
        texts = []
        for source in task.get("sources", []):
            try:
                record = _load(source["_resolved_path"])
                texts.append(record.id or "")
                texts.append(record.name or "")
                for feature in record.features:
                    texts.append(_feature_text(feature))
            except Exception:  # noqa: BLE001
                continue
        joined = " ".join(texts).lower()
        for name in required:
            ok = name.lower() in joined or \
                name.lower() in " ".join(sorted(product_labels)).lower()
            evidence.append({"name": name, "present": bool(ok),
                             "source": "input-record-features" if ok
                             else "not-found"})
    return evidence


def _donor_contamination_checks(task, check, product_seq):
    """Vector-backbone contamination checks shared by component_amplification
    and integration_donor."""
    template = [s for s in task["sources"] if s["role"] == "template"][0]
    record = _load(template["_resolved_path"])
    sel = task["target"]["selection"]
    if sel.get("kind") == "interval":
        a, b = sel["interval_0based"]
    else:
        feature = _find_feature(record, sel)
        a = min(int(p.start) for p in feature.location.parts)
        b = max(int(p.end) for p in feature.location.parts)
    n = len(record)
    required_texts = {
        r.lower() for r in task["product"].get("required_components", [])}
    for feature in record.features:
        if feature.type == "source":
            continue
        loc = feature.location
        start, end = int(loc.start), int(loc.end)
        text = _feature_text(feature).lower()
        if not any(pattern in text for pattern in
                   _VECTOR_BACKBONE_PATTERNS):
            continue
        if _overlaps(start, end, a, b, n):
            if any(r and r in text for r in required_texts):
                continue
            check(False, "CONTAMINATION_FEATURE_INSIDE_COMPONENT",
                  "selected component interval contains a vector-backbone "
                  "feature that is not a required component: %s %s"
                  % (feature.type, loc))
            continue
        fseq = str(feature.extract(record).seq).upper()
        if len(fseq) >= 12 and fseq in product_seq:
            check(False, "UNEXPECTED_VECTOR_BACKBONE_IN_DONOR",
                  "product contains template feature outside the "
                  "selected component: %s %s" % (feature.type, loc))


def _goal_check(task, plan, product_seq, product_record):
    kind = task["task_kind"]
    executed = []
    failures = []

    def check(ok, code, message, details=None):
        entry = {"ok": bool(ok), "code": code, "message": message}
        if details is not None:
            entry["details"] = details
        executed.append(entry)
        if not ok:
            failures.append(entry)
        return bool(ok)

    expected_topo = plan["product"]["topology"]
    check(str(product_record.annotations.get("topology", "linear")) ==
          expected_topo, "TOPOLOGY_MISMATCH",
          "product topology %r does not match plan %r" % (
              product_record.annotations.get("topology", "linear"),
              expected_topo))

    expected = plan["product"].get("expected_length")
    if expected is not None:
        check(len(product_seq) == expected, "LENGTH_MISMATCH",
              "length %d != expected %d" % (len(product_seq), expected))

    labels = _feature_labels(product_record)

    # ---- required components (independent evidence) -----------------------
    for evidence in _required_evidence(task, product_record, product_seq):
        check(evidence["present"], "REQUIRED_COMPONENT_MISSING",
              "required component not present: %s (%s)" % (
                  evidence["name"], evidence["source"]))
    for name in task["product"].get("forbidden_components", []):
        check(name not in labels and name not in product_seq,
              "FORBIDDEN_COMPONENT_PRESENT",
              "forbidden component present: %s" % name)

    # ---- per-kind goal checks -------------------------------------------
    if kind in ("component_amplification", "integration_donor"):
        template = [s for s in task["sources"] if s["role"] == "template"][0]
        record = _load(template["_resolved_path"])
        sel = task["target"]["selection"]
        component = _extract_selection_sequence(record, sel)
        check(component.upper() in product_seq,
              "COMPONENT_SEQUENCE_MISSING",
              "product does not contain the selected component sequence")
        _donor_contamination_checks(task, check, product_seq)
        if kind == "integration_donor":
            arms = task["operation"]["homology_arms"]
            left = str(arms.get("left_arm") or "")
            right = str(arms.get("right_arm") or "")
            locus_spec = task["operation"]["locus"]
            ref_source = next(s for s in task["sources"]
                              if s["source_id"] == locus_spec["source_id"])
            ref = _load(ref_source["_resolved_path"])
            la, lb = locus_spec["interval_0based"]
            strand = int(locus_spec.get("strand", 1))
            upstream = _arc(ref, la - len(left), la) if left else ""
            downstream = _arc(ref, lb, lb + len(right)) if right else ""
            expected_left = (upstream if strand == 1
                             else str(Seq(downstream).reverse_complement())
                             if downstream else "")
            expected_right = (downstream if strand == 1
                              else str(Seq(upstream).reverse_complement())
                              if upstream else "")
            if left:
                check(left.upper() == expected_left.upper(),
                      "INTEGRATION_ARM_MISMATCH",
                      "left homology arm does not match the locus flank")
            if right:
                check(right.upper() == expected_right.upper(),
                      "INTEGRATION_ARM_MISMATCH",
                      "right homology arm does not match the locus flank")
            check(str(product_seq).startswith(left + component),
                  "DONOR_LAYOUT_MISMATCH",
                  "donor must start with left arm + component")

    if kind == "plasmid_replace":
        backbone = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bseq = str(_load(backbone["_resolved_path"]).seq)
        a, b = task["operation"]["replace"]["interval_0based"]
        removed = bseq[a:b]
        repl_len = plan["steps"][0]["replacement_length"]
        replacement_seq = product_seq[a:a + repl_len]
        if len(removed) >= 6 and removed not in replacement_seq:
            check(removed not in product_seq, "REPLACED_INTERVAL_REMAINS",
                  "replaced interval still present in product")
        check(replacement_seq in product_seq, "REPLACEMENT_MISSING",
              "replacement sequence not present in product")

    if kind == "plasmid_insert":
        backbone = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bseq = str(_load(backbone["_resolved_path"]).seq)
        pos = task["operation"]["insert"]["boundary_0based"]
        insert = [s for s in task["sources"] if s["role"] == "insert"][0]
        iseq = str(_load(insert["_resolved_path"]).seq)
        ia, ib = task["operation"]["insert"]["interval_0based"]
        insert_seq = iseq[ia:ib]
        check(product_seq[pos:pos + len(insert_seq)] == insert_seq,
              "INSERT_NOT_AT_BOUNDARY",
              "insert sequence is not present at the declared boundary")
        remainder = product_seq[:pos] + product_seq[pos + len(insert_seq):]
        check(_circular_equal(remainder, bseq), "BACKBONE_SEQUENCE_LOST",
              "backbone sequence was not preserved around the insert")

    if kind == "overlap_assembly":
        expected_labels = [f["source_id"] for f in plan["fragments"]]
        for label in expected_labels:
            check(label in labels, "REQUIRED_FRAGMENT_MISSING",
                  "fragment not annotated in product: %s" % label)
        for junction in plan.get("junctions", []):
            check(junction["overlap"].upper() in product_seq,
                  "OVERLAP_JUNCTION_MISSING",
                  "junction overlap missing from product")

    if kind == "protein_fusion":
        table = plan["fusion"]["translation_table"]
        translation = str(Seq(product_seq).translate(
            table=table, to_stop=False))
        expected = plan["fusion"]["translation"]
        check(translation == expected, "FUSION_TRANSLATION_MISMATCH",
              "product translation does not match the planned fusion")
        check(len(product_seq) % 3 == 0, "FUSION_NOT_IN_FRAME",
              "fusion product is not a multiple of 3 nt")
        stops = [i for i, aa in enumerate(translation) if aa == "*"]
        if plan["fusion"]["stop_policy"] == "no-stop":
            check(not stops, "FUSION_INTERNAL_STOP",
                  "no-stop fusion contains an internal stop codon")
        else:
            check(not any(i != len(translation) - 1 for i in stops),
                  "FUSION_INTERNAL_STOP",
                  "fusion contains an internal stop codon")
            check(bool(stops) and stops[-1] == len(translation) - 1,
                  "FUSION_STOP_CODON_REQUIRED",
                  "stop fusion lacks a terminal stop codon")
        cdss = [f for f in product_record.features if f.type == "CDS"]
        check(bool(cdss), "FUSION_CDS_ANNOTATION_MISSING",
              "product lacks a CDS annotation")
        for cds in cdss:
            qual_translation = (cds.qualifiers.get("translation") or [None])[0]
            check(qual_translation == translation,
                  "FUSION_CDS_TRANSLATION_INCONSISTENT",
                  "CDS translation qualifier does not match the sequence")

    if kind == "gateway_recombination":
        import sys as _sys
        _sys.path.insert(0, str(pathlib.Path(
            __file__).resolve().parents[1] / "scripts"))
        from simulate_advanced import (ATTB1, ATTB2, ATTL1, ATTL2,
                                       ATTR1, ATTR2)
        body = plan["gateway"]["body"].upper()
        check(body in product_seq, "GATEWAY_INSERT_MISSING",
              "recombined insert body missing from product")
        if plan["gateway"]["reaction"] == "lr":
            check(ATTB1 in product_seq and
                  str(Seq(ATTB2).reverse_complement()) in product_seq,
                  "GATEWAY_ATTB_SITES_MISSING",
                  "attB1/attB2 junctions missing from LR product")
            check(ATTL1 not in product_seq and ATTL2 not in product_seq,
                  "GATEWAY_ATTL_SITES_REMAIN",
                  "attL sites must not remain after LR")
            check(ATTR1 not in product_seq and ATTR2 not in product_seq,
                  "GATEWAY_ATTR_SITES_REMAIN",
                  "attR sites must not remain after LR")
        else:
            check(ATTL1 in product_seq and
                  str(Seq(ATTL2).reverse_complement()) in product_seq,
                  "GATEWAY_ATTL_SITES_MISSING",
                  "attL1/attL2 junctions missing from BP product")
            check(ATTB1 not in product_seq and ATTB2 not in product_seq,
                  "GATEWAY_ATTB_SITES_REMAIN",
                  "attB sites must not remain after BP")
        if plan["gateway"]["stop_policy"] == "stop":
            frames = [body[i:] for i in range(3)]
            has_stop = any(any(codon in frame[j:j + 3] for j in
                               range(0, len(frame) - 2, 3))
                           for frame in frames
                           for codon in ("TAA", "TAG", "TGA"))
            check(has_stop, "GATEWAY_STOP_CODON_MISSING",
                  "stop_policy=stop but the insert body has no in-frame "
                  "stop codon in any of the three frames")

    if kind == "restriction_ligation":
        import sys as _sys
        _sys.path.insert(0, str(pathlib.Path(
            __file__).resolve().parents[1] / "scripts"))
        from sg_common import get_enzyme
        op = task["operation"]
        insert = next(s for s in task["sources"]
                      if s["source_id"] == op["insert_source_id"])
        irec = _load(insert["_resolved_path"])
        if op["orientation"] == "reverse":
            irec = irec.reverse_complement(id=True, name=True,
                                           description=True)
        iseq = str(irec.seq).upper()
        enzymes = [str(e) for e in op["vector_enzymes"]]
        insert_enzymes = [str(e) for e in (op.get("insert_enzymes")
                                           or enzymes)]
        if len(enzymes) == 1 and insert_enzymes == enzymes:
            from sg_common import restriction_hits
            enzyme = get_enzyme(enzymes[0])
            hits = [h for h in restriction_hits(iseq, enzyme,
                                                circular=False)
                    if h["cuts_within_sequence"]]
            t1 = hits[0]["top_cut_boundary_0based"] % len(iseq)
            t2 = hits[1]["top_cut_boundary_0based"] % len(iseq)
            frag_a = iseq[t1:t2] if t1 < t2 else iseq[t1:] + iseq[:t2]
            frag_b = iseq[t2:t1] if t2 < t1 else iseq[t2:] + iseq[:t1]
            site = str(enzyme.site).upper()
            rc_site = str(Seq(site).reverse_complement()).upper()
            insert_seq = next((f for f in (frag_a, frag_b)
                               if f and site not in f and
                               rc_site not in f), "")
            check(insert_seq and insert_seq in product_seq,
                  "INSERT_FRAGMENT_MISSING",
                  "excised insert fragment not present in product")
            check(product_seq.count(site) == 1, "RESTRICTION_SITE_COUNT",
                  "ligation product must restore exactly one %s site at "
                  "the junction" % enzymes[0])
        else:
            ihits = []
            for enzyme_name in insert_enzymes:
                from sg_common import restriction_hits
                hits = [h for h in restriction_hits(
                    iseq, get_enzyme(enzyme_name), circular=False)
                    if h["cuts_within_sequence"]]
                ihits.append(hits[0])
            i1 = ihits[0]["top_cut_boundary_0based"] % len(iseq)
            i2 = ihits[1]["top_cut_boundary_0based"] % len(iseq)
            if i1 > i2:
                i1, i2 = i2, i1
            insert_seq = iseq[i1:i2]
            check(insert_seq in product_seq, "INSERT_FRAGMENT_MISSING",
                  "excised insert fragment not present in product")
            for enzyme_name in enzymes:
                site = str(get_enzyme(enzyme_name).site).upper()
                rc_site = str(Seq(site).reverse_complement()).upper()
                count = product_seq.count(site) + \
                    product_seq.count(rc_site) - \
                    (product_seq.count(site) if site == rc_site else 0)
                check(count == 1, "RESTRICTION_SITE_COUNT",
                      "ligation product must restore exactly one %s site "
                      "at the junction (found %d)"
                      % (enzyme_name, count))

    if kind == "hierarchical_assembly":
        for stage in plan["stages"]:
            stage_seq = stage["product_sequence"]
            for junction in stage["junctions"]:
                check(junction["overlap"].upper() in stage_seq,
                      "OVERLAP_JUNCTION_MISSING",
                      "stage %s junction overlap missing"
                      % stage["stage_id"])
        check(plan["product_sequence"] ==
              plan["stages"][-1]["product_sequence"],
              "HIERARCHICAL_FINAL_STAGE_MISMATCH",
              "final product is not the last stage product")

    if kind == "crispr_editing":
        op = task["operation"]
        ref = next(s for s in task["sources"] if s["role"] == "reference")
        ref_seq = str(_load(ref["_resolved_path"]).seq).upper()
        a, b = op["target_interval_0based"]
        n = len(ref_seq)

        def ref_window(start, end):
            if start is None or end is None:
                return ""
            if start <= end:
                return ref_seq[start:end]
            return ref_seq[start:] + ref_seq[:end]

        for guide in plan["guides"]:
            start = guide.get("start_0based")
            end = guide.get("end_0based")
            if guide.get("reference_sequence"):
                check(ref_window(start, end) ==
                      str(guide["reference_sequence"]).upper(),
                      "CRISPR_GUIDE_NOT_IN_REFERENCE",
                      "guide %s protospacer region does not match the "
                      "reference" % guide["id"])
            pam_start = guide.get("pam_start")
            pam_end = guide.get("pam_end")
            if pam_start is not None and pam_end is not None:
                observed = ref_window(pam_start, pam_end)
                expected = str(guide["pam"]).upper() \
                    if guide["strand"] == 1 \
                    else str(Seq(str(guide["pam"])).reverse_complement()) \
                    .upper()
                check(observed == expected, "CRISPR_PAM_MISMATCH",
                      "guide %s PAM does not match the reference"
                      % guide["id"])
        donor = op.get("donor_strategy") or {}
        if donor.get("donor_source_id"):
            dsrc = next(s for s in task["sources"]
                        if s["source_id"] == donor["donor_source_id"])
            drec = _load(dsrc["_resolved_path"])
            ra, rb = donor["replacement_interval_0based"]
            repl = _arc(drec, ra, rb).upper()
            check(repl in product_seq, "CRISPR_REPLACEMENT_MISSING",
                  "donor replacement sequence not present in product")
            arms = donor.get("homology_arms") or {}
            left = str(arms.get("left_arm") or "")
            right = str(arms.get("right_arm") or "")
            upstream = ref_window(max(0, a - len(left)), a) if left else ""
            downstream = ref_window(b, min(n, b + len(right))) \
                if right else ""
            if left:
                check(left.upper() == upstream.upper(),
                      "CRISPR_ARM_MISMATCH",
                      "left donor arm does not match the reference flank")
            if right:
                check(right.upper() == downstream.upper(),
                      "CRISPR_ARM_MISMATCH",
                      "right donor arm does not match the reference flank")
            original = ref_seq[a:b]
            check(original not in product_seq or original in repl,
                  "CRISPR_TARGET_NOT_REPLACED",
                  "original target region still present in product")
        check(plan["crispr"]["offtarget_assessment"] == "not-assessed",
              "CRISPR_OFFTARGET_UNVERIFIED_CLAIM",
              "off-target status must stay not-assessed without a real "
              "cas-offinder run")

    if kind == "point_mutation":
        template = [s for s in task["sources"] if s["role"] == "template"][0]
        tseq = str(_load(template["_resolved_path"]).seq).upper()
        declared = {int(m["position_1based"]) - 1
                    for m in plan["mutations"]}
        offset = 0
        if len(tseq) != len(product_seq):
            check(False, "LENGTH_MISMATCH",
                  "product length differs from template")
        else:
            diffs = [i for i in range(len(tseq))
                     if tseq[i] != product_seq[i]]
            if set(diffs) == declared:
                offset = 0
            elif expected_topo == "circular":
                # product may be a rotation of the edited template; align
                # via a 24 nt seed far from the mutation sites, then verify
                # that every difference is a declared mutation.
                far = [i for i in range(len(tseq))
                       if all(abs(i - d) >= 12 for d in declared)]
                seed_start = far[0] if far else 0
                seed = tseq[seed_start:seed_start + 24]
                hit = product_seq.find(seed)
                if hit >= 0:
                    candidate = (seed_start - hit) % len(tseq)
                    rotated_diffs = {
                        i for i in range(len(tseq))
                        if tseq[i] != product_seq[(i + candidate) %
                                                  len(tseq)]}
                    if rotated_diffs == declared:
                        offset = candidate
            for mut in plan["mutations"]:
                pos1 = mut["position_1based"]
                check(product_seq[(pos1 - 1 + offset) % len(tseq)] ==
                      mut["alt"], "MUTATION_NOT_APPLIED",
                      "mutation at %d not applied" % pos1)
            if set(diffs) == declared or offset:
                check(True, "NO_UNINTENDED_MUTATION",
                      "product differs from template only at declared "
                      "mutation positions")
            else:
                check(False, "UNINTENDED_MUTATION",
                      "product differs from template outside declared "
                      "mutation positions: %s"
                      % sorted(set(diffs) - declared))

    return executed, failures


def validate(task, plan, execution):
    """Public seam: three-layer validation report."""
    report = {
        "task_sha256": plan["task_sha256"],
        "plan_hash": plan["plan_sha256"],
        "artifact_valid": False,
        "computation_valid": False,
        "goal_valid": False,
        "overall": "failed",
        "checks": [],
        "error_codes": [],
    }

    # ---- layer 1: artifact ------------------------------------------------
    try:
        product_record = _load(execution["product_gb"])
        import subprocess
        import sys
        cp = subprocess.run(
            [sys.executable, "-X", "utf8", "-B",
             str(pathlib.Path(__file__).resolve().parents[1] / "scripts" /
                 "validate_construct.py"),
             execution["product_gb"], "--json"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        if cp.returncode != 0:
            report["artifact_valid"] = False
            report["error_codes"].append("ARTIFACT_VALIDATION_FAILED")
            report["checks"].append({"layer": "artifact",
                                     "message": (cp.stderr or
                                                 cp.stdout)[-500:]})
        else:
            report["artifact_valid"] = True
        product_seq = str(product_record.seq).upper()
        if not product_seq:
            report["artifact_valid"] = False
            report["error_codes"].append("EMPTY_PRODUCT")
        for feature in product_record.features:
            for part in getattr(feature.location, "parts",
                                [feature.location]):
                if not (0 <= int(part.start) < int(part.end) <=
                        len(product_record)):
                    report["artifact_valid"] = False
                    report["error_codes"].append(
                        "FEATURE_COORDINATE_OUT_OF_RANGE")
        if report["artifact_valid"]:
            report["checks"].append({
                "layer": "artifact", "ok": True,
                "message": "construct file readable, coordinates valid"})
        report["artifact_hashes"] = {
            "construct.gb": _sha256_file(pathlib.Path(
                execution["product_gb"])),
            "construct.fasta": _sha256_file(pathlib.Path(
                execution["product_fasta"])),
        }
    except Exception as exc:  # noqa: BLE001
        report["artifact_valid"] = False
        report["error_codes"].append("PRODUCT_FILE_UNREADABLE")
        report["checks"].append({"layer": "artifact",
                                 "message": str(exc)})
        report["overall"] = "failed"
        return report

    # ---- layer 2: independent recomputation ------------------------------
    try:
        expected = _recompute(task)
        topology = plan["product"]["topology"]
        same = _circular_equal(expected, product_seq) if topology == \
            "circular" else expected.upper() == product_seq
        if not same:
            report["computation_valid"] = False
            report["error_codes"].append("COMPUTATION_RECONSTRUCTION_MISMATCH")
            report["checks"].append({"layer": "computation", "ok": False,
                                     "message": "independent recomputation "
                                                "does not match product"})
        else:
            report["computation_valid"] = True
            report["checks"].append({"layer": "computation", "ok": True,
                                     "message": "product matches independent "
                                                "recomputation"})
    except Exception as exc:  # noqa: BLE001
        report["computation_valid"] = False
        report["error_codes"].append("COMPUTATION_RECOMPUTE_FAILED")
        report["checks"].append({"layer": "computation", "ok": False,
                                 "message": str(exc)})

    # ---- layer 3: goal ----------------------------------------------------
    executed, problems = _goal_check(task, plan, product_seq, product_record)
    for entry in executed:
        report["checks"].append({"layer": "goal", **entry})
    if problems:
        report["goal_valid"] = False
        for p in problems:
            report["error_codes"].append(p["code"])
    elif not executed:
        report["goal_valid"] = False
        report["error_codes"].append("GOAL_VALIDATION_NOT_EXECUTED")
    else:
        report["goal_valid"] = True

    if plan.get("method_maturity") == "experimental":
        report["overall"] = "experimental-preview"
    else:
        report["overall"] = "verified" if (
            report["artifact_valid"] and report["computation_valid"] and
            report["goal_valid"]) else "failed"
    return report
