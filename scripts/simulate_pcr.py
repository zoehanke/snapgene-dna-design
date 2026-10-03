# -*- coding: utf-8 -*-
"""simulate_pcr.py - PCR amplification simulation.

Given a template and forward/reverse primer sequences, locate primer binding
sites (exact or with mismatches) and predict the amplicon product.
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from sg_common import jprint, load_seq, normalize_dna, topology


def find_binding(template, primer, allow_mismatch=0, circular=False):
    """Find 0-based start positions where primer binds (primer or its RC).

    Returns (start0, strand, mismatches), with strand=+1 when primer equals
    the top-strand window and -1 when its reverse complement does.
    """
    t = str(template).upper()
    p = str(primer).upper()
    rc = str(Seq(p).reverse_complement())
    if not p or allow_mismatch < 0:
        return []
    if circular:
        if not t or len(p) > len(t):
            return []
        searchable = t + t[:len(p) - 1]
        starts = range(len(t))
    else:
        searchable = t
        starts = range(max(len(t) - len(p) + 1, 0))

    hits = []
    for pos in starts:
        sub = searchable[pos:pos + len(p)]
        fwd_mm = sum(a != b for a, b in zip(sub, p))
        rev_mm = sum(a != b for a, b in zip(sub, rc))
        if fwd_mm <= allow_mismatch:
            hits.append((pos, +1, fwd_mm))
        if rev_mm <= allow_mismatch:
            hits.append((pos, -1, rev_mm))
    return hits


def simulate(template, fwd, rev, allow_mismatch=0, circular=False):
    """Return amplicon (5'->3' on top strand) and binding annotations."""
    if allow_mismatch == 0:
        from core.tools.amplification import simulate_pcr
        record = template if isinstance(template, SeqRecord) else SeqRecord(Seq(str(template)))
        try:
            result = simulate_pcr(record, fwd, rev,
                                  topology="circular" if circular else "linear",
                                  min_binding_len=min(15, len(fwd), len(rev)))
        except ValueError as error:
            return None, [str(error)]
        def binding(hit, strand):
            return {"start": hit["template_start_0based"] + 1,
                    "end": hit["template_end_0based"],
                    "strand": strand, "mismatches": 0}
        return {**result, "length": result["amplicon_length"],
                "forward_bind": binding(result["forward_binding"], "+"),
                "reverse_bind": binding(result["reverse_binding"], "-")}, []
    t = str(getattr(template, "seq", template))
    fwd_hits = find_binding(t, fwd, allow_mismatch, circular)
    rev_hits = find_binding(t, rev, allow_mismatch, circular)
    # forward primer must bind top strand (+1): 5' end of amplicon
    # reverse primer must bind bottom strand (-1): its 3' end defines amplicon end
    fwd_top = [h for h in fwd_hits if h[1] == +1]
    rev_bot = [h for h in rev_hits if h[1] == -1]
    notes = []
    if not fwd_top:
        notes.append("forward primer has no top-strand binding site")
    if not rev_bot:
        notes.append("reverse primer has no bottom-strand binding site")
    if not fwd_top or not rev_bot:
        return None, notes

    candidates = []
    n = len(t)
    for f_hit in fwd_top:
        for r_hit in rev_bot:
            start, rev_start = f_hit[0], r_hit[0]
            if circular:
                distance = (rev_start - start) % n
                if distance < len(fwd):
                    continue
                product_len = distance + len(rev)
                if product_len > n:
                    continue
                amplicon = (t + t)[start:start + product_len]
                wraps = start + product_len > n
            else:
                if rev_start < start + len(fwd):
                    continue
                product_len = rev_start + len(rev) - start
                amplicon = t[start:start + product_len]
                wraps = False
            candidates.append((product_len, start, rev_start, f_hit, r_hit,
                               amplicon, wraps))

    if not candidates:
        notes.append("primer sites exist but do not face inward in a valid order")
        return None, notes

    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    product_len, start, rev_start, f_hit, r_hit, amplicon, wraps = candidates[0]
    if len(candidates) > 1:
        notes.append(
            "%d valid products found; reporting the shortest (%d bp)"
            % (len(candidates), product_len)
        )

    def end_coord(start0, width):
        if circular:
            return ((start0 + width - 1) % n) + 1
        return start0 + width

    return {
        "amplicon": amplicon,
        "length": len(amplicon),
        "candidate_count": len(candidates),
        "wraps_origin": wraps,
        "forward_bind": {
            "start": start + 1, "end": end_coord(start, len(fwd)),
            "strand": "+", "mismatches": f_hit[2],
        },
        "reverse_bind": {
            "start": rev_start + 1, "end": end_coord(rev_start, len(rev)),
            "strand": "-", "mismatches": r_hit[2],
        },
    }, notes


def main():
    p = argparse.ArgumentParser(description="Simulate PCR amplification")
    p.add_argument("template", help="template file / raw seq")
    p.add_argument("--fwd", required=True, help="forward primer sequence")
    p.add_argument("--rev", required=True, help="reverse primer sequence")
    p.add_argument("--allow-mismatch", type=int, default=0,
                   help="maximum mismatches per binding site (default 0)")
    p.add_argument("--out", help="write amplicon FASTA")
    p.add_argument("--json", action="store_true")
    p.add_argument("--pcr-type", choices=("standard", "colony", "boiled_colony"),
                   default="standard")
    p.add_argument("--acknowledge-experience-warning", action="store_true",
                   help="explicitly continue after a warn_and_confirm rule")
    p.add_argument("--user-rules-dir", default=str(ROOT / "user_rules"))
    p.add_argument("--project-id")
    args = p.parse_args()

    rec, _fmt = load_seq(args.template)
    try:
        fwd = normalize_dna(args.fwd, "forward primer")
        rev = normalize_dna(args.rev, "reverse primer")
    except ValueError as e:
        raise SystemExit(str(e))
    if args.allow_mismatch < 0:
        raise SystemExit("--allow-mismatch must be >= 0")
    result, notes = simulate(
        rec, fwd, rev, args.allow_mismatch,
        circular=(topology(rec) == "circular"))

    out = {
        "template": rec.name or rec.id,
        "template_length": len(rec.seq),
        "forward_primer": fwd,
        "reverse_primer": rev,
        "notes": notes,
    }
    if result:
        out.update(result)
    else:
        out["amplicon"] = None
        out["length"] = 0

    out["pcr_type"] = args.pcr_type
    out["simulation_mode"] = "exact" if args.allow_mismatch == 0 else "approximate-full-primer"
    out["experience_rules"] = {"hits": [], "diagnostics": [],
                               "rules_evaluated": 0}
    if result and args.pcr_type in ("colony", "boiled_colony"):
        from agent.rule_capture import evaluate_experience, load_preloaded_experience
        from rules.experience import ExperienceRuleStore
        experience = evaluate_experience(
            "after_pcr_plan",
            {"pcr": {"type": args.pcr_type,
                     "amplicon_bp": result["length"]}},
            ExperienceRuleStore(args.user_rules_dir),
            project_id=args.project_id,
            preloaded_rules=load_preloaded_experience(
                ROOT / "rules" / "preloaded_experience_rules.json"))
        out["experience_rules"] = experience
        pending = [hit for hit in experience["hits"]
                   if hit.get("action", {}).get("type") in
                   ("ask", "warn_and_confirm", "block")]
        hard_blocks = [hit for hit in pending
                       if hit.get("action", {}).get("type") == "block"]
        confirmation_hits = [hit for hit in pending
                             if hit.get("action", {}).get("type") in
                             ("ask", "warn_and_confirm")]
        if pending:
            out["experience_warning"] = {
                "requires_confirmation": bool(confirmation_hits) and
                not args.acknowledge_experience_warning,
                "blocked": bool(hard_blocks),
                "actual_amplicon_bp": result["length"],
                "messages": [hit["action"].get("message") for hit in pending],
            }
            notes.extend("experience rule %s: %s" %
                         (hit["rule_id"], hit["action"].get("message"))
                         for hit in pending)

    hard_blocked = bool(out.get("experience_warning", {}).get("blocked"))
    requires_confirmation = bool(
        out.get("experience_warning", {}).get("requires_confirmation"))
    if args.out and result and not hard_blocked and not requires_confirmation:
        amp = SeqRecord(Seq(result["amplicon"]), id="amplicon", name="amplicon",
                        description="PCR product %d bp" % result["length"])
        from Bio import SeqIO
        output_path = pathlib.Path(args.out)
        if output_path.suffix.lower() in {".gb", ".gbk", ".dna"}:
            from core.io.input_resolution import resolve_sequence_record
            from core.tools.snapgene_io import export_plasmid, annotate_record_primers
            amp = resolve_sequence_record({**result, "sequence": result["amplicon"], "topology": "linear"})
            amp.id = amp.name = output_path.stem
            if result.get("primers"):
                forward, reverse = result["primers"]
                offset = len(result["forward_binding"]["tail_5prime"])
                core_length = result["template_core_length"]
                mapped = [
                    {**forward, "binding_interval_0based": [offset, offset+forward["binding_core_length"]]},
                    {**reverse, "binding_interval_0based": [offset+core_length-reverse["binding_core_length"], offset+core_length]},
                ]
                amp = annotate_record_primers(amp, mapped)
                source = annotate_record_primers(rec, result["primers"])
                out["annotated_source"] = export_plasmid(source, output_path.parent/"annotated_sources",
                                                        output_path.stem+"_source", topology(rec))
            files = export_plasmid(amp, output_path.parent, output_path.stem, "linear")
            if output_path.suffix.lower()==".gbk":
                pathlib.Path(files["gb_file"]).replace(output_path)
                files["gb_file"] = str(output_path)
            out["product_files"] = files
        else:
            with output_path.open("w", encoding="utf-8", errors="replace") as fh:
                SeqIO.write(amp, fh, "fasta")
        out["out_file"] = args.out
    elif args.out and (hard_blocked or requires_confirmation):
        out["out_file"] = None
        out["write_blocked"] = (
            "experience rule block cannot be overridden" if hard_blocked else
            "experience warning requires explicit "
            "--acknowledge-experience-warning")

    if args.json:
        jprint(out, ok=bool(result) and not hard_blocked and not requires_confirmation)
    else:
        if result:
            print("amplicon %d bp (fwd binds %s, rev binds %s)" % (
                result["length"], result["forward_bind"]["start"],
                result["reverse_bind"]["end"]))
            print("sequence:")
            print(result["amplicon"])
        for n in notes:
            print("  note: %s" % n)

    if hard_blocked:
        raise SystemExit(2)
    if result is None:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
