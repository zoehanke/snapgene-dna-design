# -*- coding: utf-8 -*-
"""generate_crispr_design_report.py - Unified v0.8 CRISPR design report.

JSON and Markdown now carry the same core content.  Intermediate failures
produce a structured failed report (written to disk when an output path was
requested) and a non-zero exit code instead of a bare traceback.
"""
import argparse
import json
import pathlib
import sys

from Bio import SeqIO

from sg_common import load_seq
from design_guides import scan_guides, load_registry
from guide_scoring import score_guides
from characterize_reaction import characterize_fragment
from protocol_evidence import load_sources
from recommend_protocol import recommend
from cas_offinder_adapter import detect as offinder_detect, search_offtargets
from annotate_offtargets import annotate_hits
from provenance import source, sha256_of_file, now_iso, read_version


def _input_records(paths):
    records = []
    for path in paths:
        try:
            records.append({
                "path": str(path),
                "sha256": sha256_of_file(path),
                "size": pathlib.Path(path).stat().st_size,
            })
        except (OSError, ValueError):
            records.append({"path": str(path), "sha256": None})
    return records


def _merge_hits(search_results):
    merged = {}
    order = []
    for candidate, result in search_results:
        if result.get("status") != "complete":
            continue
        for hit in result.get("hits", []):
            key = (hit.get("chromosome"), hit.get("start"), hit.get("end"),
                   hit.get("strand"), hit.get("sequence"))
            if key not in merged:
                merged[key] = dict(hit)
                merged[key]["query_guide_ids"] = []
                order.append(key)
            if candidate.get("id") not in merged[key]["query_guide_ids"]:
                merged[key]["query_guide_ids"].append(candidate.get("id"))
    return [merged[key] for key in order]


def _offtarget_analysis(record, candidates, args):
    candidates = list(candidates or [])
    candidate_total = len(candidates)
    try:
        candidate_limit = int(getattr(args, "max_offtarget_candidates", 50))
    except (TypeError, ValueError):
        raise ValueError("MAX_OFFTARGET_CANDIDATES_INVALID")
    if candidate_limit <= 0:
        raise ValueError("MAX_OFFTARGET_CANDIDATES_MUST_BE_POSITIVE")
    selected_candidates = candidates[:candidate_limit]
    truncated = candidate_total > candidate_limit
    skipped_by_limit = max(0, candidate_total - len(selected_candidates))
    if not getattr(args, "reference_fasta", None):
        return {
            "schema_version": "0.8.0",
            "status": "unavailable",
            "reason": "no-complete-reference-genome-provided",
            "reference_genome": None,
            "hits": [],
            "provenance": [],
            "coverage": {
                "candidate_total": candidate_total,
                "candidate_searched": 0,
                "candidate_skipped": candidate_total,
                "candidate_skipped_by_limit": skipped_by_limit,
                "candidate_invalid": 0,
                "truncated": truncated,
            },
        }
    detection = offinder_detect(getattr(args, "cas_offinder", None))
    if not detection["installed"]:
        return {
            "schema_version": "0.8.0",
            "status": "unavailable",
            "reason": "CAS_OFFINDER_NOT_INSTALLED",
            "reference_genome": None,
            "hits": [],
            "provenance": detection["provenance"],
            "coverage": {
                "candidate_total": candidate_total,
                "candidate_searched": 0,
                "candidate_skipped": candidate_total,
                "candidate_skipped_by_limit": skipped_by_limit,
                "candidate_invalid": 0,
                "truncated": truncated,
            },
        }
    params = {
        "mismatches": int(getattr(args, "mismatches", 3)),
        "dna_bulge": int(getattr(args, "dna_bulge", 0)),
        "rna_bulge": int(getattr(args, "rna_bulge", 0)),
        "label": "crispr-design",
    }
    search_results = []
    invalid_candidates = 0
    for candidate in selected_candidates:
        query = str(candidate.get("protospacer_sequence", "")).upper()
        if not query or any(base not in "ACGT" for base in query):
            invalid_candidates += 1
            continue
        try:
            result = search_offtargets(
                query, args.reference_fasta, params,
                executable=getattr(args, "cas_offinder", None),
                device=getattr(args, "offinder_device", "C0"),
                nuclease_id=args.nuclease,
                annotation_path=getattr(args, "annotation", None),
                rebuild_stale=getattr(args, "rebuild_stale_index", True))
        except (ValueError, OSError) as error:
            result = {
                "schema_version": "0.8.0",
                "status": "failed",
                "reason": str(error).split(":")[0],
                "reference_genome": None,
                "hits": [],
                "provenance": detection["provenance"],
            }
        search_results.append((candidate, result))
    merged_hits = _merge_hits(search_results)
    if getattr(args, "annotation", None) and merged_hits:
        try:
                annotate_hits(merged_hits, args.annotation,
                              getattr(args, "target_gene", None))
        except (OSError, ValueError) as error:
            return {
                "schema_version": "0.8.0",
                "status": "failed",
                "reason": "OFFTARGET_ANNOTATION_FAILED",
                "detail": str(error),
                "reference_genome": (search_results[0][1].get("reference_genome")
                                     if search_results else None),
                "hits": merged_hits,
                "provenance": detection["provenance"],
                "coverage": {
                    "candidate_total": candidate_total,
                    "candidate_searched": len(search_results),
                    "candidate_skipped": skipped_by_limit + invalid_candidates,
                    "candidate_skipped_by_limit": skipped_by_limit,
                    "candidate_invalid": invalid_candidates,
                    "truncated": truncated,
                },
            }
    statuses = {result.get("status") for _candidate, result in search_results}
    if "failed" in statuses:
        status = "failed"
        reason = "CAS_OFFINDER_PARTIAL_FAILURE"
    elif not statuses:
        status = "incomplete"
        reason = "NO_SCORABLE_GUIDE_QUERIES"
    elif statuses == {"complete"} and not truncated and \
            invalid_candidates == 0 and len(search_results) == candidate_total:
        status = "complete"
        reason = None
    elif statuses == {"complete"}:
        status = "partial"
        reason = "OFFTARGET_CANDIDATES_TRUNCATED" if truncated else \
            "OFFTARGET_CANDIDATES_SKIPPED"
    else:
        status = "incomplete"
        reason = "OFFTARGET_SEARCH_NOT_COMPLETE"
    return {
        "schema_version": "0.8.0",
        "status": status,
        "reason": reason,
        "reference_genome": (search_results[0][1].get("reference_genome")
                             if search_results else None),
        "hits": merged_hits,
        "provenance": detection["provenance"],
        "coverage": {
            "candidate_total": candidate_total,
            "candidate_searched": len(search_results),
            "candidate_skipped": skipped_by_limit + invalid_candidates,
            "candidate_skipped_by_limit": skipped_by_limit,
            "candidate_invalid": invalid_candidates,
            "truncated": truncated,
        },
    }


def make_report(target_path, nuclease, fragment_paths=None,
                protocol_source_path=None, off_target_options=None):
    version = read_version()
    record, _ = load_seq(target_path)
    candidates = scan_guides(record, nuclease)
    scoring = score_guides(candidates, nuclease)
    fragments = []
    for path in fragment_paths or []:
        rec, _ = load_seq(path)
        fragments.append(characterize_fragment(rec, pathlib.Path(path).stem))
    sources = load_sources(protocol_source_path)
    protocol = recommend(fragments, sources)

    args = argparse.Namespace(**off_target_options or {})
    args.nuclease = nuclease
    if not hasattr(args, "reference_fasta"):
        args.reference_fasta = None
    if not hasattr(args, "annotation"):
        args.annotation = None
    off_target = _offtarget_analysis(record, candidates, args)

    available_scores = [item for scoring_item in scoring
                        for item in scoring_item["on_target_scores"]
                        if item.get("status") == "available"]
    partial_reasons = []
    if not available_scores:
        partial_reasons.append("on-target-model-unavailable")
    if off_target.get("status") != "complete":
        partial_reasons.append("off-target-search-" + str(off_target.get("status")))
    if protocol.get("status") == "unavailable":
        partial_reasons.append("protocol-recommendation-unavailable")
    if not fragments:
        partial_reasons.append("no-reaction-profiles-provided")

    unfinished = []
    if not available_scores:
        unfinished.append("on-target-model-execution")
    if off_target.get("status") != "complete":
        unfinished.append("off-target-search")
    unfinished += ["primer-specificity", "wet-lab-validation"]

    if available_scores and off_target.get("status") == "complete" and fragments:
        status = "complete"
    elif available_scores or off_target.get("status") == "complete":
        status = "partial"
    else:
        status = "partial"

    report = {
        "schema_version": "0.8.0",
        "status": status,
        "task_summary": "CRISPR guide candidate scan, on-target scoring and off-target analysis",
        "partial_reasons": partial_reasons,
        "inputs": _input_records([target_path] + list(fragment_paths or [])),
        "nuclease": nuclease,
        "guide_candidates": candidates,
        "on_target": {"candidates": scoring},
        "off_target": off_target,
        "reaction_profiles": fragments,
        "protocol_recommendation": protocol,
        "sequence_upload": {"requested": False, "approved": False,
                            "destination": None, "sequence_sha256": None},
        "unfinished_analysis": unfinished,
        "limitations": [
            "计算候选不等同于实验验证",
            "模型适用性未经酵母宿主验证",
        ],
        "human_review_required": [
            "gRNA排序",
            "脱靶位点生物学意义",
            "协议条件最终复核",
        ],
        "provenance": [source(
            "software", "SnapGene DNA Design generate_crispr_design_report",
            "unified-report", version=version, status="verified",
            verification={"method": "unit-tests", "status": "verified"})],
    }
    return report


def _failed_report(error, target_path=None, nuclease=None, args=None):
    report = {
        "schema_version": "0.8.0",
        "status": "failed",
        "task_summary": "CRISPR design report generation failed",
        "partial_reasons": [str(error)],
        "inputs": _input_records([target_path]) if target_path else [],
        "nuclease": nuclease,
        "guide_candidates": [],
        "on_target": {"candidates": []},
        "off_target": {"status": "failed", "reason": str(error),
                       "reference_genome": None, "hits": [],
                       "provenance": []},
        "reaction_profiles": [],
        "protocol_recommendation": {
            "schema_version": "0.8.0", "status": "unavailable",
            "reason": "REPORT_GENERATION_FAILED",
            "recommendations": [], "provenance": []},
        "sequence_upload": {"requested": False, "approved": False,
                            "destination": None, "sequence_sha256": None},
        "unfinished_analysis": ["report-generation"],
        "limitations": ["报告生成失败，所有分析均未完成"],
        "human_review_required": [],
        "provenance": [source(
            "software", "SnapGene DNA Design generate_crispr_design_report",
            "unified-report", version=read_version(), status="unavailable",
            verification={"method": "exception-handler", "status": "failed"})],
    }
    return report


def _markdown(report):
    lines = ["# CRISPR Design Report", ""]
    lines.append("status: %s" % report.get("status"))
    lines.append("schema_version: %s" % report.get("schema_version"))
    if report.get("partial_reasons"):
        lines.append("partial_reasons: %s" % ", ".join(
            report["partial_reasons"]))
    lines.append("nuclease: %s" % report.get("nuclease"))
    lines.append("candidates: %d" % len(report.get("guide_candidates", [])))
    lines.append("")
    lines.append("## guide_candidates")
    for item in report.get("guide_candidates", []):
        score_parts = []
        for scoring in report.get("on_target", {}).get("candidates", []):
            if scoring.get("guide_id") == item.get("id"):
                for entry in scoring.get("on_target_scores", []):
                    if entry.get("status") == "available":
                        score_parts.append("%s=%.4f" % (
                            entry.get("model"), entry.get("score")))
                    else:
                        score_parts.append("%s=%s(%s)" % (
                            entry.get("model"), entry.get("status"),
                            entry.get("reason")))
        score_text = " ".join(score_parts) if score_parts else "no-score"
        lines.append("- %s %s PAM=%s strand=%s coords=%s..%s[0bho) %s" % (
            item.get("id"), item.get("protospacer_sequence"),
            item.get("pam_sequence"), item.get("strand"),
            item.get("coordinates", {}).get("protospacer_start"),
            item.get("coordinates", {}).get("protospacer_end"), score_text))
    lines.append("")
    off = report.get("off_target", {})
    lines.append("## off_target")
    lines.append("status: %s" % off.get("status"))
    if off.get("reason"):
        lines.append("reason: %s" % off.get("reason"))
    lines.append("hits: %d" % len(off.get("hits", [])))
    for hit in off.get("hits", [])[:20]:
        ann = hit.get("annotation") or {}
        lines.append("- %s:%d-%d %s mm=%d feature=%s/%s" % (
            hit.get("chromosome"), hit.get("start"), hit.get("end"),
            hit.get("strand"), hit.get("mismatches"),
            ann.get("feature_type"), ann.get("feature_name")))
    lines.append("")
    lines.append("## reaction_profiles")
    for profile in report.get("reaction_profiles", []):
        lines.append("- %s length=%d gc=%.2f%%" % (
            profile.get("fragment_id"), profile.get("length"),
            profile.get("gc_percent")))
    lines.append("")
    lines.append("## protocol_recommendation")
    proto = report.get("protocol_recommendation", {})
    lines.append("status: %s" % proto.get("status"))
    if proto.get("reason"):
        lines.append("reason: %s" % proto.get("reason"))
    for rec in proto.get("recommendations", []):
        lines.append("- %s: %s (%s)" % (
            rec.get("reaction_id"), rec.get("recommended_system"),
            rec.get("status")))
    lines.append("")
    lines.append("## sequence_upload")
    upload = report.get("sequence_upload", {})
    lines.append("requested=%s approved=%s destination=%s" % (
        upload.get("requested"), upload.get("approved"),
        upload.get("destination")))
    lines.append("")
    lines.append("## unfinished_analysis")
    for item in report.get("unfinished_analysis", []):
        lines.append("- %s" % item)
    lines.append("")
    lines.append("## limitations")
    for item in report.get("limitations", []):
        lines.append("- %s" % item)
    lines.append("")
    lines.append("## human_review_required")
    for item in report.get("human_review_required", []):
        lines.append("- %s" % item)
    lines.append("")
    return "\n".join(lines) + "\n"


def _write_design_files(record, out_dir, stem):
    from write_dna import _ensure_annotations, _snapgene_annotated, write_native_dna
    out_dir.mkdir(parents=True, exist_ok=True)
    record = _ensure_annotations(record)
    gb_path = out_dir / ("%s.gb" % stem)
    fa_path = out_dir / ("%s.fa" % stem)
    dna_path = out_dir / ("%s.dna" % stem)
    with open(gb_path, "w", encoding="utf-8") as handle:
        from core.io.molecule_codec import genbank_record
        SeqIO.write(genbank_record(_snapgene_annotated(record)), handle, "genbank")
    with open(fa_path, "w", encoding="utf-8") as handle:
        SeqIO.write(record, handle, "fasta")
    write_native_dna(record, dna_path)
    return [{"path": str(gb_path), "format": "genbank"},
            {"path": str(fa_path), "format": "fasta"},
            {"path": str(dna_path), "format": "snapgene-dna"}]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--nuclease", required=True)
    parser.add_argument("--fragments", nargs="*")
    parser.add_argument("--protocol-evidence")
    parser.add_argument("--out-json")
    parser.add_argument("--out-markdown")
    parser.add_argument("--out-dir", help="write GenBank+FASTA+.dna design files")
    parser.add_argument("--reference-fasta")
    parser.add_argument("--annotation")
    parser.add_argument("--target-gene")
    parser.add_argument("--cas-offinder")
    parser.add_argument(
        "--offinder-device", default="auto",
        help="Cas-OFFinder device (auto selects a detected GPU, then CPU; "
             "default: auto)")
    parser.add_argument("--mismatches", type=int, default=3)
    parser.add_argument("--dna-bulge", type=int, default=0)
    parser.add_argument("--rna-bulge", type=int, default=0)
    parser.add_argument("--max-offtarget-candidates", type=int, default=50)
    parser.add_argument("--rebuild-stale-index", action="store_true", default=True)
    args = parser.parse_args()

    options = {key: getattr(args, key) for key in (
        "reference_fasta", "annotation", "target_gene", "cas_offinder",
        "offinder_device", "mismatches", "dna_bulge", "rna_bulge",
        "max_offtarget_candidates", "rebuild_stale_index")}
    try:
        report = make_report(args.target, args.nuclease, args.fragments,
                             args.protocol_evidence, options)
        failed = False
    except Exception as error:  # noqa: BLE001 - report must degrade structurally
        report = _failed_report(error, args.target, args.nuclease)
        failed = True

    if args.out_dir:
        try:
            record, _ = load_seq(args.target)
            report["output_files"] = _write_design_files(
                record, pathlib.Path(args.out_dir),
                pathlib.Path(args.target).stem or "target")
        except (ValueError, OSError) as error:
            report.setdefault("partial_reasons", []).append(
                "output-file-generation-failed: %s" % error)

    if args.out_json:
        pathlib.Path(args.out_json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = _markdown(report)
    if args.out_markdown:
        pathlib.Path(args.out_markdown).write_text(markdown, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
