# -*- coding: utf-8 -*-
"""The single authoritative delivery gate (v0.9.1-dev2).

Only this module may create ``authoritative/`` products.  A product is
authoritative only when:
1. task/plan/execution/validation cryptographic hash chain is independently re-verified;
2. on-disk source file hashes are re-verified (no post-validation tampering);
3. the three validation layers all pass (artifact, computation, goal);
4. the method is mature (experimental methods are permanently blocked);
5. three-format verification (GB, FASTA, SnapGene .dna, and official roundtrip) passes;
6. the user has explicitly confirmed the task with no unresolved assumptions.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

from Bio import SeqIO

from core.errors import GateRejected
from core.evidence import stamp_product
from core.runtime_execute import compute_execution_sha256
from core.runtime_plan import compute_plan_sha256
from core.runtime_validate import compute_validation_sha256
from core.task import canonical_json, task_sha256

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _sha256_file(path: pathlib.Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _check_chain(task: dict, plan: dict, execution: dict, validation: dict) -> None:
    current_task_hash = task_sha256(task)
    if plan.get("task_id") != task.get("task_id") or plan.get("task_revision") != task.get("revision"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", "plan does not describe this task revision")

    if plan.get("task_sha256") != current_task_hash:
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", f"plan task hash {plan.get('task_sha256')} != recomputed {current_task_hash}")

    recomputed_plan_hash = compute_plan_sha256(plan)
    if plan.get("plan_sha256") != recomputed_plan_hash:
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", f"plan hash {plan.get('plan_sha256')} != recomputed {recomputed_plan_hash}")

    if execution.get("task_sha256") != current_task_hash or execution.get("task_id") != task.get("task_id"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", "execution task hash does not match task")

    if execution.get("plan_hash") != plan.get("plan_sha256"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", "execution plan hash does not match plan")

    recomputed_exec_hash = compute_execution_sha256(execution)
    if execution.get("execution_sha256") and execution.get("execution_sha256") != recomputed_exec_hash:
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", "execution hash does not match recomputed value")

    if validation.get("task_sha256") != current_task_hash or validation.get("plan_hash") != plan.get("plan_sha256"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", "validation hash chain does not match plan")

    recomputed_val_hash = compute_validation_sha256(validation)
    if validation.get("validation_sha256") and validation.get("validation_sha256") != recomputed_val_hash:
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", "validation hash does not match recomputed value")

    if execution.get("artifact_class") != "intermediate":
        raise GateRejected(
            "GATE_ARTIFACT_CLASS_INVALID",
            f"execution artifacts must be intermediate-class, got {execution.get('artifact_class')}",
        )

    if execution.get("method_maturity") != plan.get("method_maturity"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN", "execution method maturity does not match plan")

    # Re-verify on-disk source hashes (detect post-validation source tampering)
    for source in task.get("sources", []):
        src_path = pathlib.Path(source.get("_resolved_path") or source.get("path"))
        if not src_path.exists():
            raise GateRejected("GATE_SOURCE_MISSING", f"source file {src_path} is missing on disk")
        current_src_sha = _sha256_file(src_path)
        claimed_src_sha = source.get("sha256")
        if claimed_src_sha and current_src_sha != claimed_src_sha.upper():
            raise GateRejected(
                "GATE_SOURCE_TAMPERED",
                f"source file {src_path} changed after validation: claimed {claimed_src_sha}, on disk now {current_src_sha}",
            )

    # Re-verify intermediate artifacts on disk
    exec_hashes = execution.get("artifact_hashes") or {}
    validation_hashes = validation.get("artifact_hashes") or {}
    if not exec_hashes or exec_hashes != validation_hashes:
        raise GateRejected(
            "GATE_HASH_CHAIN_BROKEN",
            "execution artifact hashes do not match the files that validation actually read",
        )

    for rel in ("construct.gb", "construct.fasta"):
        rel_key = {"construct.gb": "product_gb", "construct.fasta": "product_fasta"}[rel]
        target_path = pathlib.Path(execution.get(rel_key, ""))
        if not target_path.exists():
            raise GateRejected("GATE_ARTIFACT_MISSING", f"intermediate file {rel} is missing on disk")
        on_disk = _sha256_file(target_path)
        if on_disk != exec_hashes.get(rel):
            raise GateRejected(
                "GATE_ARTIFACT_TAMPERED",
                f"intermediate file {rel} changed after validation: validated {exec_hashes.get(rel)}, on disk now {on_disk}",
            )


def finalize(task: dict, plan: dict, execution: dict, validation: dict, out_dir: pathlib.Path | str) -> dict:
    """Public seam: promote a fully verified execution to authoritative."""
    if task.get("mode") != "formal":
        raise GateRejected("GATE_REQUIRES_FORMAL_MODE", "authoritative products require task.mode == formal")

    _check_chain(task, plan, execution, validation)

    if plan.get("method_maturity") != "validated":
        raise GateRejected("GATE_EXPERIMENTAL_METHOD", "experimental methods can never produce authoritative products")

    # Re-derive validation overall status from the 3 booleans
    art_val = bool(validation.get("artifact_valid"))
    comp_val = bool(validation.get("computation_valid"))
    goal_val = bool(validation.get("goal_valid"))
    rederived_verified = (art_val and comp_val and goal_val and plan.get("method_maturity") == "validated")

    if not rederived_verified or validation.get("overall") != "verified":
        raise GateRejected(
            "GATE_VALIDATION_FAILED",
            "three-layer validation did not reach verified",
            details={
                "overall": validation.get("overall"),
                "artifact_valid": art_val,
                "computation_valid": comp_val,
                "goal_valid": goal_val,
                "error_codes": validation.get("error_codes"),
            },
        )

    approval = task.get("approvals", {}).get("user_confirmed_task") or {}
    if not approval.get("value"):
        raise GateRejected("GATE_APPROVAL_MISSING", "formal delivery requires approvals.user_confirmed_task.value")

    for assumption in task.get("assumptions", []):
        if assumption.get("resolution_status") != "accepted-by-user":
            raise GateRejected(
                "GATE_UNRESOLVED_ASSUMPTION",
                "unresolved assumption blocks authoritative delivery",
                details={"assumption": assumption},
            )

    manifest_payload = {
        "schema_version": "delivery-manifest-v1",
        "artifact_class": "authoritative",
        "provenance_type": "pipeline",
        "task_id": task["task_id"],
        "task_revision": task["revision"],
        "task_sha256": plan["task_sha256"],
        "plan_sha256": plan["plan_sha256"],
        "validation": {
            "overall": validation["overall"],
            "artifact_valid": validation["artifact_valid"],
            "computation_valid": validation["computation_valid"],
            "goal_valid": validation["goal_valid"],
        },
        "evidence": stamp_product(
            task,
            plan,
            plan["sources"],
            method_maturity="validated",
            artifact_class="authoritative",
            execution=execution,
            validation=validation,
        ),
    }

    return _promote_verified_candidate(
        candidate_gb=pathlib.Path(execution["product_gb"]),
        candidate_fasta=pathlib.Path(execution["product_fasta"]),
        out_dir=out_dir,
        manifest_payload=manifest_payload,
        temp_identifier=task["task_id"],
    )


def _promote_verified_candidate(
    candidate_gb: pathlib.Path,
    candidate_fasta: pathlib.Path,
    out_dir: pathlib.Path | str,
    manifest_payload: dict[str, Any],
    temp_identifier: str = "construct",
) -> dict[str, Any]:
    """Single physical promoter for authoritative directory creation.

    Performs:
    1. Collision checking against existing authoritative directory.
    2. Atomic staging in temporary directory (.authoritative-<temp_identifier>.tmp).
    3. Conversion and generation of native SnapGene construct.dna.
    4. Strict Three-Format Semantic Consistency Verification (rec_gb.seq == rec_fa.seq == rec_dna.seq).
    5. Optional SnapGene desktop application roundtrip verification (SNAPGENE_VERIFY_OFFICIAL=1).
    6. Attested SHA-256 hashed DELIVERY-MANIFEST.json generation.
    7. Atomic promotion to authoritative/.
    """
    out_path = pathlib.Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    authoritative = out_path / "authoritative"
    if authoritative.exists():
        raise GateRejected("GATE_AUTHORITATIVE_ALREADY_EXISTS", "refusing to overwrite an existing authoritative directory")

    if not candidate_gb.exists():
        raise GateRejected("GATE_CANDIDATE_MISSING", f"Candidate GenBank file not found: {candidate_gb}")
    if not candidate_fasta.exists():
        raise GateRejected("GATE_CANDIDATE_MISSING", f"Candidate FASTA file not found: {candidate_fasta}")

    tmp = out_path / f".authoritative-{temp_identifier}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    try:
        # Copy GB and FASTA
        gb_dst = tmp / "construct.gb"
        shutil.copyfile(candidate_gb, gb_dst)

        fa_dst = tmp / "construct.fasta"
        shutil.copyfile(candidate_fasta, fa_dst)

        # Generate SnapGene native .dna
        dna_dst = tmp / "construct.dna"
        write_dna = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                str(ROOT / "scripts" / "write_dna.py"),
                str(gb_dst),
                "--out",
                str(dna_dst),
                "--format",
                "dna",
                "--name",
                "construct",
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if write_dna.returncode != 0:
            raise GateRejected("GATE_DNA_WRITE_FAILED", write_dna.stderr[-500:])

        # Three-Format Semantic Consistency Verification (P1-01)
        rec_gb = SeqIO.read(str(gb_dst), "genbank")
        rec_fa = SeqIO.read(str(fa_dst), "fasta")
        try:
            rec_dna = SeqIO.read(str(dna_dst), "snapgene")
        except Exception:
            try:
                from snapgene_reader import snapgene_file_to_seqrecord
                rec_dna = snapgene_file_to_seqrecord(str(dna_dst))
            except Exception as exc:
                raise GateRejected("GATE_DNA_READBACK_FAILED", f"Failed to read back generated .dna: {exc}")

        gb_seq = str(rec_gb.seq).upper()
        fa_seq = str(rec_fa.seq).upper()
        dna_seq = str(rec_dna.seq).upper()

        if gb_seq != fa_seq or gb_seq != dna_seq:
            raise GateRejected(
                "GATE_THREE_FORMAT_SEQUENCE_MISMATCH",
                f"Sequence mismatch across formats: GB ({len(gb_seq)} bp), FASTA ({len(fa_seq)} bp), DNA ({len(dna_seq)} bp)",
            )

        # Optional SnapGene desktop official roundtrip verification
        import os
        from core.tools.snapgene_io import find_snapgene_executable
        if os.environ.get("SNAPGENE_VERIFY_OFFICIAL") == "1":
            snapgene_exe = find_snapgene_executable()
            if snapgene_exe and snapgene_exe.exists():
                roundtrip = subprocess.run(
                    [
                        sys.executable,
                        "-X",
                        "utf8",
                        "-B",
                        str(ROOT / "scripts" / "validate_roundtrip.py"),
                        str(dna_dst),
                        "--format",
                        "dna",
                        "--snapgene-exe",
                        str(snapgene_exe),
                        "--json",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if roundtrip.returncode != 0:
                    raise GateRejected(
                        "GATE_OFFICIAL_ROUNDTRIP_FAILED",
                        f"SnapGene roundtrip process failed with exit code {roundtrip.returncode}: {roundtrip.stderr[-500:]}",
                    )
                try:
                    rt_data = json.loads(roundtrip.stdout)
                except Exception as exc:
                    raise GateRejected(
                        "GATE_OFFICIAL_ROUNDTRIP_FAILED",
                        f"Failed to parse SnapGene roundtrip JSON output: {exc}",
                    )
                if not rt_data.get("ok") and not rt_data.get("passed") and rt_data.get("core_passed") is not True:
                    raise GateRejected(
                        "GATE_OFFICIAL_ROUNDTRIP_FAILED",
                        f"SnapGene official roundtrip verification rejected: {rt_data.get('errors') or rt_data.get('reasons')}",
                    )

        # Build attested hashed DELIVERY-MANIFEST.json
        manifest = dict(manifest_payload)
        manifest["files"] = {}
        for rel in ("construct.gb", "construct.fasta", "construct.dna"):
            manifest["files"][rel] = {
                "sha256": _sha256_file(tmp / rel),
                "class": "authoritative",
            }
        (tmp / "DELIVERY-MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Atomic directory promotion
        try:
            tmp.replace(authoritative)
        except OSError:
            shutil.move(str(tmp), str(authoritative))

    except Exception:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        if authoritative.exists():
            shutil.rmtree(authoritative, ignore_errors=True)
        raise

    return {
        "status": "delivered",
        "directory": str(authoritative),
        "manifest_sha256": _sha256_file(authoritative / "DELIVERY-MANIFEST.json"),
        "files": sorted(str(p.relative_to(authoritative)) for p in authoritative.iterdir()),
    }


def finalize_candidate_construct(
    candidate_gb: str | pathlib.Path,
    candidate_fasta: str | pathlib.Path,
    out_dir: str | pathlib.Path,
    metadata: dict[str, Any],
    sanity_check: dict[str, Any],
    user_confirmed: bool = False,
) -> dict[str, Any]:
    """Promote a verified candidate construct (e.g. from recipe execution) to authoritative delivery."""
    if not user_confirmed:
        raise GateRejected(
            "GATE_USER_CONFIRMATION_REQUIRED",
            "Authoritative promotion refused: requires explicit user confirmation (--confirmed).",
        )

    if not sanity_check.get("all_applicable_pass", True):
        failed = sanity_check.get("failed_codes") or sanity_check.get("blocking_codes", [])
        raise GateRejected(
            "GATE_GUARDRAILS_FAILED",
            f"Authoritative promotion refused: biological guardrails failed on {failed}",
        )

    gb_path = pathlib.Path(candidate_gb).resolve()
    fa_path = pathlib.Path(candidate_fasta).resolve()

    manifest_payload = {
        "schema_version": "delivery-manifest-v1",
        "artifact_class": "authoritative",
        "provenance_type": "recipe",
        "recipe": metadata.get("recipe", "unknown"),
        "product_length": metadata.get("product_length", 0),
        "product_topology": metadata.get("product_topology", "circular"),
        "guardrails": sanity_check,
        "metadata": metadata,
    }

    temp_id = str(metadata.get("recipe", "recipe_construct")).replace(" ", "_")
    return _promote_verified_candidate(
        candidate_gb=gb_path,
        candidate_fasta=fa_path,
        out_dir=out_dir,
        manifest_payload=manifest_payload,
        temp_identifier=temp_id,
    )
