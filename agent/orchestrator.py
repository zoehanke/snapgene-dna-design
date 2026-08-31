# -*- coding: utf-8 -*-
"""agent/orchestrator.py - unified DesignSpec scheduler.

The orchestrator owns only the DesignSpec lifecycle and invokes existing
deterministic tools as child processes. It contains no Primer3, restriction,
reverse-complement, feature-migration, off-target or SnapGene-writing logic.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from design.spec import (  # noqa: E402
    DesignSpecError, add_evidence, canonical_json, delivery_flags, diff_specs,
    formal_blockers, make_sequence_source, now_iso, set_field, set_status,
    sha256_text, spec_sha256,
)
from agent.session import Session, file_sha256  # noqa: E402
from planning.method_selector import select_methods  # noqa: E402
from provenance import read_version  # noqa: E402


def _run(cmd, cwd=None, timeout=1800):
    completed = subprocess.run(
        [str(x) for x in cmd], cwd=str(cwd or ROOT), capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return completed


def _python():
    return sys.executable


class Orchestrator:
    def __init__(self, session, out_dir=None):
        self.session = session
        self.out_dir = pathlib.Path(out_dir or session.workdir)
        self.report = {"events": [], "recovery_actions": []}

    # ------------------------------------------------------------------
    def start(self, user_text, files):
        if self.session.spec.get("mode") == "formal":
            set_status(self.session.spec, "blocked",
                       "LEGACY_AGENT_FORMAL_DEPRECATED", force=True)
            raise DesignSpecError(
                "LEGACY_AGENT_FORMAL_DEPRECATED: v0.9.1 formal construction "
                "must use the ConstructionTask runtime "
                "(core.validate_construction_task / plan / execute / "
                "validate / finalize); the v0.9.0 keyword-parser formal "
                "path is deprecated and no longer executes")
        for path in files:
            self.session.add_file(path)
        from agent.nl_parser import parse_request
        parsed = parse_request(user_text, self.session.file_summaries,
                                mode=self.session.spec.get("mode", "exploration"))
        self.session.spec = parsed["spec"]
        self.session.revisions = [copy.deepcopy(parsed["spec"])]
        if parsed["questions"]:
            set_status(self.session.spec, "needs-clarification",
                       "must-ask questions pending")
        self.report["events"].append({"event": "parsed", **{
            k: v for k, v in parsed.items() if k != "spec"}})
        return parsed

    # ------------------------------------------------------------------
    def answer(self, question_id, value, description=None):
        self.session.answer(question_id, value, description)
        self.report["events"].append({"event": "answered",
                                      "question_id": question_id})
        return self.session.spec

    def confirm(self):
        self.session.confirm()
        if self.session.spec.get("mode") == "formal":
            self.session.spec["approvals"]["primers-ready-to-order"] = {
                "value": True,
                "evidence_layer": "user-provided",
                "description": "user confirmed formal ordering conditions",
            }
        return self.session.spec

    def resolve_evidence(self):
        spec = self.session.spec
        mismatches = self.session.check_file_hashes()
        if mismatches:
            set_status(spec, "blocked", "input file hash mismatch",
                       force=True)
            raise DesignSpecError("SOURCE_HASH_MISMATCH: %s" % mismatches)
        spec["sources"] = []
        for idx, (path, summary) in enumerate(
                sorted(self.session.file_summaries.items()), 1):
            if summary.get("error"):
                continue
            spec["sources"].append(make_sequence_source(
                "source-%02d" % idx, "user-file", summary["sha256"],
                source_path=path, interval_0based=[0, summary["length"]],
                strand=1, transformations=["read-from-file"]))
        add_evidence(spec, "computed", "file hashes bound to spec sources")
        set_status(spec, "evidence-resolved", "evidence resolved")
        return spec

    def plan(self):
        spec = self.session.spec
        context = self._method_context(spec)
        context.update(self._sequence_method_context())
        selection = select_methods(spec, context)
        spec["constraints"]["method_selection"] = selection
        chosen = selection["selected"]
        if chosen is None:
            actions = [c["hard_blockers"] for c in selection["candidates"]]
            set_status(spec, "blocked",
                       "no compatible method: %s" % actions, force=True)
            self.report["recovery_actions"] = actions
            return selection
        spec["objective"]["selected_method"] = chosen["method"]
        add_evidence(spec, "heuristic",
                     "method selector score is ranking aid, not success "
                     "probability", method=chosen["method"],
                     score=chosen["score"])
        set_status(spec, "planned", "method selected")
        return selection

    def execute(self):
        spec = self.session.spec
        if spec.get("status") == "blocked":
            raise DesignSpecError(
                "EXECUTION_BLOCKED: planning status is blocked; resolve the "
                "reported biological/method prerequisites before execution")
        if not (spec.get("objective", {}) or {}).get("selected_method"):
            set_status(spec, "blocked", "method selection is missing", force=True)
            raise DesignSpecError(
                "EXECUTION_BLOCKED: no compatible method was selected")
        if spec["mode"] == "formal":
            if self._primers_required(spec):
                from primer3_core_backend import probe_primer3_core
                probe = probe_primer3_core()
                if probe["status"] != "available":
                    set_status(spec, "blocked", "primer3_core unavailable",
                               force=True)
                    raise DesignSpecError(
                        "formal mode requires real primer3_core")
        artifacts = self._run_existing_tools(spec)
        self.session.artifacts.extend(artifacts)
        set_status(spec, "executed", "existing tools executed")
        return artifacts

    def verify(self):
        spec = self.session.spec
        construct = self.session.construct_gb
        if not construct or not pathlib.Path(construct).exists():
            set_status(spec, "blocked", "construct.gb missing", force=True)
            raise DesignSpecError("NO_CONSTRUCT_FOR_VERIFY")
        results = {}
        for cmd in (
            [_python(), "-X", "utf8", "-B",
             str(ROOT / "scripts" / "validate_construct.py"),
             str(construct), "--json"],
            [_python(), "-X", "utf8", "-B",
             str(ROOT / "scripts" / "validate_roundtrip.py"),
             str(construct), "--format", "snapgene-gb", "--strict", "--json"],
        ):
            completed = _run(cmd)
            results[pathlib.Path(cmd[-3]).name] = {
                "returncode": completed.returncode,
                "stdout": (completed.stdout or "")[:2000],
                "stderr": (completed.stderr or "")[:2000],
            }
            if completed.returncode != 0:
                set_status(spec, "blocked", "verification failed", force=True)
                self.report["recovery_actions"].append(
                    "验证失败：检查 QC 错误并修正构建方案；交付前必须重跑验证")
                raise DesignSpecError("VERIFICATION_FAILED")
        spec["outputs"]["roundtrip_verified"] = True
        spec["outputs"]["validation"] = results
        set_status(spec, "verified", "construct validated")
        return results

    def deliver(self, delivery_dir=None):
        from agent.delivery import write_delivery
        spec = self.session.spec
        if spec.get("mode") == "formal":
            blockers = formal_blockers(spec)
            if blockers:
                set_status(spec, "blocked",
                            "formal delivery blockers: %s" % blockers,
                            force=True)
                raise DesignSpecError("FORMAL_BLOCKERS: %s" % blockers)
        spec["outputs"]["delivery_flags"] = delivery_flags(spec)
        delivery = write_delivery(
            spec, self.session, delivery_dir or self.out_dir,
            construct_gb=self.session.construct_gb,
            artifacts=self.session.artifacts)
        spec["outputs"]["delivery_dir"] = str(delivery["directory"])
        spec["outputs"]["delivery_manifest_sha256"] = delivery["manifest_sha"]
        set_status(spec, "delivered", "delivery package written")
        return delivery

    def block_with_recovery(self, error, actions=None):
        spec = self.session.spec
        set_status(spec, "blocked", str(error), force=True)
        self.report["recovery_actions"] = list(actions or [])
        return spec

    # ------------------------------------------------------------------
    @staticmethod
    def _primers_required(spec):
        obj = spec.get("objective", {})
        return obj.get("type") not in ("gateway-lr",)

    @staticmethod
    def _method_context(spec):
        obj = spec.get("objective", {})
        ctx = {
            "fragment_count": int(obj.get("fragment_count", 2)),
            "internal_type_iis_sites": bool(
                obj.get("internal_type_iis_sites")),
            "unique_two_enzyme": bool(obj.get("unique_two_enzyme")),
            "entry_destination": bool(obj.get("entry_destination")),
            "point_mutation": obj.get("type") == "point-mutation",
            "high_gc": bool(obj.get("high_gc")),
            "long_fragment": bool(obj.get("long_fragment")),
            "total_length": int(obj.get("total_length", 0)),
            "primer_design_failed": bool(obj.get("primer_design_failed")),
        }
        if obj.get("type") == "gateway-lr":
            ctx["entry_destination"] = True
        if obj.get("type") == "point-mutation":
            ctx["point_mutation"] = True
        return ctx

    def _sequence_method_context(self):
        """Derive method prerequisites from the actual input sequences.

        Golden Gate is not executable merely because the user said its name:
        every source fragment needs two usable Type IIS cut sites.  The agent
        therefore inspects the local records before method selection and
        blocks that route when the evidence is absent, while leaving Gibson or
        another compatible route available when the user did not explicitly
        constrain the method.
        """
        result = {}
        try:
            from Bio.Seq import Seq
            from sg_common import get_enzyme, load_seq, restriction_hits
            counts = []
            for path in self.session.file_summaries:
                record, _fmt = load_seq(path)
                per_fragment = {}
                for enzyme_name in ("BsaI", "BsmBI", "Esp3I", "BbsI"):
                    per_fragment[enzyme_name] = len(restriction_hits(
                        Seq(str(record.seq)), get_enzyme(enzyme_name),
                        circular=True))
                counts.append(per_fragment)
            result["type_iis_site_counts"] = counts
            # The executor needs one unambiguous flanking pair per source
            # record. More than two sites can indicate an internal site or
            # multiple possible excisions, so do not call that executable
            # evidence.
            result["type_iis_sites_available"] = bool(counts) and any(
                all(item.get(enzyme, 0) == 2 for item in counts)
                for enzyme in ("BsaI", "BsmBI", "Esp3I", "BbsI"))
        except Exception as error:  # noqa: BLE001
            # Unknown sequence evidence must not be interpreted as a usable
            # Golden Gate substrate.
            result["type_iis_sites_available"] = False
            result["type_iis_site_check_error"] = type(error).__name__
        return result

    def _run_existing_tools(self, spec):
        """Invoke existing CLI tools; never reimplement their algorithms.

        v0.9.1: construct artifacts are written under ``preview/`` only;
        the legacy path can never produce authoritative products.
        """
        obj = spec.get("objective", {})
        files = list(self.session.file_summaries.keys())
        method = (spec.get("objective", {}).get("selected_method")
                  or spec.get("constraints", {}).get("method")
                  or "gibson")
        artifacts = []
        preview_dir = self.out_dir / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        (preview_dir / "LEGACY-PREVIEW.txt").write_text(
            "legacy v0.9.0 exploration output; artifact_class=preview; "
            "not authoritative; formal construction must use "
            "scripts/run_construction_task.py\n", encoding="utf-8")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        if obj.get("type") == "point-mutation":
            mutation = obj.get("mutation")
            if not mutation:
                set_status(spec, "blocked", "MUTATION_SPEC_REQUIRED",
                           force=True)
                raise DesignSpecError(
                    "MUTATION_SPEC_REQUIRED: point_mutation needs an explicit "
                    "mutation spec such as 100:A; the historical default "
                    "100:A has been removed")
            out = preview_dir / "construct.fa"
            cmd = [_python(), "-X", "utf8", "-B",
                   str(ROOT / "scripts" / "mutagenesis.py"),
                   files[0], "--op", obj.get("op", "point"),
                   "--mutation", mutation,
                   "--out", str(out), "--json"]
        elif obj.get("type") == "gateway-lr":
            out = preview_dir / "construct.gb"
            cmd = [_python(), "-X", "utf8", "-B",
                   str(ROOT / "scripts" / "simulate_advanced.py"),
                   "--method", "gateway-lr", "--entry", files[0],
                   "--destination", files[1], "--out", str(out), "--json"]
        else:
            out = preview_dir / "construct"
            lengths = {
                path: int(self.session.file_summaries[path].get("length", 0))
                for path in files}
            intent = self._intent_for_plan(spec, files, method, lengths)
            intent_path = self.out_dir / "construction-intent.json"
            intent_path.write_text(json.dumps(intent, ensure_ascii=False,
                                              indent=2), encoding="utf-8")
            cmd = [_python(), "-X", "utf8", "-B",
                   str(ROOT / "scripts" / "plan_assembly.py"),
                   *files, "--intent-json", str(intent_path),
                   "--out-json", str(self.out_dir / "construction-plan.json"),
                   "--out-markdown",
                   str(self.out_dir / "construction-plan.md"),
                   "--out-construct", str(out), "--consent", "auto"]
        completed = _run(cmd)
        artifacts.append({"command": [str(x) for x in cmd],
                          "returncode": completed.returncode,
                          "stdout": (completed.stdout or "")[-4000:],
                          "stderr": (completed.stderr or "")[-4000:]})
        if completed.returncode != 0:
            actions = self._recovery_for(spec, method, completed)
            set_status(spec, "blocked", "existing tool failed", force=True)
            self.report["recovery_actions"] = actions
            raise DesignSpecError(
                "TOOL_FAILED: %s; recovery=%s"
                % (completed.stderr[-500:], actions))
        if obj.get("type") == "point-mutation" or \
                obj.get("type") == "gateway-lr":
            self.session.construct_gb = out
        else:
            self.session.construct_gb = str(out) + ".gb"
            self.session.construct_fasta = str(out) + ".fa"
            self.session.construct_dna = str(out) + ".dna"
        return artifacts

    @staticmethod
    def _intent_for_plan(spec, files, method, lengths):
        obj = spec.get("objective", {})
        roles = obj.get("file_roles", [])
        backbone_role = next((r for r in roles if r.get("role") == "backbone"), None)
        if backbone_role:
            backbone = backbone_role.get("path")
        elif len(files) == 1:
            backbone = files[0]
        elif spec.get("approvals", {}).get("clarify-backbone-file", {}).get("value"):
            ans = spec.get("approvals", {}).get("clarify-backbone-file", {}).get("value")
            backbone = ans if ans in files else (files[0] if files else None)
        elif spec.get("mode") == "exploration":
            backbone = files[0] if files else None
        else:
            raise DesignSpecError(
                "INTENT_BACKBONE_UNDEFINED: backbone file is not defined and cannot default to the first file"
            )
        backbone_index = files.index(backbone) if backbone in files else 0
        inserts = []
        whole_approved = bool(spec.get("approvals", {}).get("whole_record", {}).get("value"))
        for idx, path in enumerate(files):
            if idx == backbone_index:
                continue
            spec_entry = {"source": idx}
            feature = obj.get("target_feature") or obj.get("feature")
            if feature:
                spec_entry["feature"] = feature
            elif obj.get("interval"):
                spec_entry["interval"] = obj["interval"]
            elif whole_approved or spec.get("mode") == "exploration":
                spec_entry["interval"] = [0, int(lengths.get(path, 0) or 0)]
            else:
                raise DesignSpecError(
                    "INTENT_INTERVAL_UNDEFINED: fragment interval or feature must be explicitly provided; "
                    "whole-record default is forbidden without explicit approval"
                )
            inserts.append(spec_entry)
        return {
            "goal": obj.get("text", spec.get("raw_objective", "")),
            "method": method,
            "backbone": {"source": backbone_index},
            "fragments": inserts,
            "topology": spec.get("target", {}).get("topology", "circular"),
            "name": spec.get("target", {}).get("name", "construct"),
        }

    @staticmethod
    def _recovery_for(spec, method, completed):
        actions = []
        stderr = (completed.stderr or "") + (completed.stdout or "")
        if "BsaI" in stderr and "site" in stderr.lower():
            actions.append("尝试 BsmBI 或回退 Gibson")
        if "Primer3" in stderr or "NO_PRIMER" in stderr:
            actions.append("显示 Primer3 explain 与可批准的放宽项（slide/GC/Tm）")
        if method == "golden_gate":
            actions.append("检查片段内部 Type IIS 位点；换 BsmBI/Esp3I 或 Gibson")
        if method == "digest_ligate":
            actions.append("检查每片段唯一酶切位点与粘性端兼容性")
        actions.append("读取 construction-plan.json 与工具 stderr；修正后重跑 execute")
        return actions
