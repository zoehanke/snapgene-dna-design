# -*- coding: utf-8 -*-
"""plan_assembly.py - M1 multi-source assembly planner CLI."""
import argparse
import json
import os
import pathlib
import tempfile
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sg_common import jprint  # noqa: E402
from planning.intent import normalize_intent, parse_intent_text  # noqa: E402
from planning.planner import plan_assembly  # noqa: E402
from planning.manual_render import render_html, render_markdown  # noqa: E402
from operation_consent import ConsentBroker, ConsentRequiredError  # noqa: E402


def _interactive_confirm(request):
    print("[需要确认] %s (%s)" % (request["operation"], request["category"]))
    print("  说明：%s" % request["description"])
    for index, alternative in enumerate(request.get("alternatives", []), 1):
        print("  替代方案 %d：%s" % (index, alternative.get("action", "")))
    try:
        answer = input("是否继续？[y/N] ").strip().lower()
    except EOFError:
        raise ConsentRequiredError(request)
    return answer in ("y", "yes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="+")
    parser.add_argument("--intent-json")
    parser.add_argument("--intent-text")
    parser.add_argument("--primer3-core")
    parser.add_argument("--out-json")
    parser.add_argument("--out-markdown")
    parser.add_argument("--out-html")
    parser.add_argument("--out-construct", help="write final construct .gb/.fa/.dna (path stem)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--consent", choices=("ask", "auto"), default="ask",
                        help="ask: interactive confirmation (default, "
                             "no confirmation = no execution); "
                             "auto: explicitly auto-confirm and record")
    parser.add_argument("--yes", action="store_true",
                        help="confirm every pending request (same as "
                             "--consent ask with an all-yes callback)")
    args = parser.parse_args()

    try:
        if args.intent_json:
            intent = normalize_intent(json.loads(
                pathlib.Path(args.intent_json).read_text(encoding="utf-8")))
        elif args.intent_text:
            intent = parse_intent_text(args.intent_text)
        else:
            raise ValueError("INTENT_REQUIRED: --intent-json or --intent-text")
        if args.consent == "auto":
            broker = ConsentBroker(policy="auto")
        elif args.yes:
            broker = ConsentBroker(policy="ask",
                                   confirm_callback=lambda request: True)
        else:
            broker = ConsentBroker(policy="ask",
                                   confirm_callback=_interactive_confirm)
        plan = plan_assembly(args.sources, intent, args.primer3_core,
                             consent_broker=broker)
    except Exception as error:  # noqa: BLE001 - structured failure for CLI
        failure = {
            "schema_version": "0.9.0",
            "status": "failed",
            "reason": str(error).split(":")[0],
            "detail": str(error),
        }
        if args.out_json:
            pathlib.Path(args.out_json).write_text(
                json.dumps(failure, ensure_ascii=False, indent=2),
                encoding="utf-8")
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 1

    plan["steps"] = _steps_list(plan)
    pending = plan.get("consent", {}).get("pending", [])
    markdown = render_markdown(plan)

    def _record_write(path):
        plan.setdefault("operation_log", []).append({
            "operation": "write-file",
            "category": "external-write",
            "path": str(path),
            "approved": True,
            "source": "explicit CLI output path",
        })

    if args.out_json:
        _record_write(args.out_json)
        pathlib.Path(args.out_json).write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.out_markdown:
        _record_write(args.out_markdown)
        pathlib.Path(args.out_markdown).write_text(markdown, encoding="utf-8")
    if args.out_html:
        _record_write(args.out_html)
        pathlib.Path(args.out_html).write_text(
            render_html(plan), encoding="utf-8")
    if pending and args.consent == "ask" and not args.yes:
        # Informed-consent gate: never write the final construct while any
        # abnormal operation is still unconfirmed.
        print(markdown)
        print("PENDING-CONFIRMATION: %d request(s) not confirmed" % len(pending))
        return 1
    if args.out_construct:
        try:
            _write_construct_files(plan, pathlib.Path(args.out_construct))
        except (OSError, ValueError) as error:
            failure = {
                "schema_version": "0.9.0",
                "status": "failed",
                "reason": str(error).split(":")[0],
                "detail": str(error),
            }
            print(json.dumps(failure, ensure_ascii=False, indent=2))
            return 1
        # Record every synchronized deliverable, including the metadata
        # sidecar.  The operation log must not imply that only the GenBank
        # file was written when --out-construct creates four files.
        for suffix in (".gb", ".fa", ".dna", ".provenance.json"):
            _record_write(str(args.out_construct) + suffix)
    if args.json:
        jprint(plan)
    else:
        print(markdown)
    return 0


def _write_construct_files(plan, stem):
    """Write the final construct as GenBank/FASTA/native SnapGene .dna."""
    from Bio.Seq import Seq as BioSeq
    from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
    from Bio.SeqRecord import SeqRecord
    import Bio.SeqIO as SeqIO
    from write_dna import _ensure_annotations, write_native_dna

    # ``out-construct`` promises three synchronized files, including native
    # .dna.  Check the required writer before creating even a partial .gb/.fa
    # pair; a missing optional dependency must be a loud, atomic failure.
    try:
        import sgffp  # noqa: F401
    except ImportError as error:
        raise ValueError(
            "NATIVE_DNA_DEPENDENCY_MISSING: install sgffp==0.21.0 before "
            "requesting --out-construct") from error

    final = plan.get("final_construct") or {}
    if (plan.get("status") != "complete" or
            final.get("status") != "validated" or
            not final.get("sequence")):
        execution = plan.get("execution") or {}
        raise ValueError(
            "FINAL_CONSTRUCT_NOT_VALIDATED: method execution must succeed "
            "before writing construct files (status=%s reason=%s)"
            % (execution.get("status"), execution.get("reason")))
    sequence = final["sequence"]
    construct_name = plan.get("construct_name", "assembled")
    record = SeqRecord(BioSeq(sequence), id=construct_name,
                       name=construct_name)
    record.annotations["molecule_type"] = "DNA"
    record.annotations["topology"] = plan.get("topology", "circular")
    assembly = plan.get("assembly_strategy") or {}
    execution = plan.get("execution") or {}
    provenance = {
        "schema_version": "0.9.0",
        "assembly_method": assembly.get("method"),
        "requested_method": assembly.get("requested_method"),
        "executor": execution.get("executor"),
        "execution_status": execution.get("status"),
        "validation_status": final.get("status"),
        "input_files": [
            {"path": item.get("path"), "sha256": item.get("sha256"),
             "sequence_sha256": item.get("sequence_sha256")}
            for item in (plan.get("sources") or [])
        ],
        "junctions": (execution.get("junctions") or
                      assembly.get("overlap_junctions") or []),
    }
    provenance_json = json.dumps(provenance, ensure_ascii=False,
                                 sort_keys=True, separators=(",", ":"))
    # GenBank can carry a machine-readable COMMENT; FASTA has a description
    # line. Native .dna has no stable arbitrary-metadata channel in sgffp, so
    # the same record is also emitted as an atomic sidecar below.
    comment_text = "snapgene-dna-design provenance: " + provenance_json
    # INSDC COMMENT lines are short fixed-width fields in Biopython's
    # GenBank writer. Split deterministically so export does not emit a
    # truncation warning; the sidecar remains the canonical complete JSON.
    record.annotations["comment"] = [
        comment_text[offset:offset + 58]
        for offset in range(0, len(comment_text), 58)]
    record.description = (
        "%s | assembly_method=%s | validation=%s | executor=%s" %
        (construct_name, provenance["assembly_method"],
         provenance["validation_status"], provenance["executor"]))
    feature_specs = final.get("feature_specs") or []
    for spec in feature_specs:
        segments = []
        for part in spec.get("segments", []):
            start0, end0 = int(part["start0"]), int(part["end0"])
            if not (0 <= start0 < end0 <= len(sequence)):
                raise ValueError(
                    "FEATURE_COORDINATE_OUT_OF_RANGE: %s %d..%d len=%d"
                    % (spec.get("label"), start0, end0, len(sequence)))
            strand = part.get("strand")
            strand = None if strand in (None, 0) else int(strand)
            segments.append(FeatureLocation(start0, end0, strand=strand))
        if not segments:
            continue
        location = segments[0] if len(segments) == 1 else CompoundLocation(
            segments, operator=spec.get("operator") or "join")
        qualifiers = {str(key): [str(value) for value in values]
                      for key, values in (spec.get("qualifiers") or {}).items()}
        qualifiers.setdefault("label", [str(spec.get("label", "feature"))])
        record.features.append(SeqFeature(
            location=location, type=str(spec.get("type", "misc_feature")),
            qualifiers=qualifiers))
    record = _ensure_annotations(record)
    stem = pathlib.Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = pathlib.Path(tempfile.mkdtemp(
        prefix=".construct-write-", dir=str(stem.parent)))
    temp_stem = temp_dir / stem.name
    try:
        with open(str(temp_stem) + ".gb", "w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "genbank")
        with open(str(temp_stem) + ".fa", "w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "fasta")
        write_native_dna(record, str(temp_stem) + ".dna")
        with open(str(temp_stem) + ".provenance.json", "w",
                  encoding="utf-8") as handle:
            json.dump(provenance, handle, ensure_ascii=False, indent=2)
        for suffix in (".gb", ".fa", ".dna"):
            os.replace(str(temp_stem) + suffix, str(stem) + suffix)
        os.replace(str(temp_stem) + ".provenance.json",
                   str(stem) + ".provenance.json")
    finally:
        for path in temp_dir.glob("*"):
            try:
                path.unlink()
            except OSError:
                pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def _steps_list(plan):
    from planning.manual_render import _default_steps
    return _default_steps(plan)


if __name__ == "__main__":
    sys.exit(main())
