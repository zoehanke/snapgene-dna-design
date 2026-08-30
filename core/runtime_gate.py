# -*- coding: utf-8 -*-
"""The single authoritative gate.

Only this module may create ``authoritative/`` products.  A product is
authoritative only when: task/plan/execution/validation hash chain is
intact, the three validation layers all pass, the method is mature, the
user has confirmed the task, and no unresolved assumption remains.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import GateRejected
from core.evidence import stamp_product

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _check_chain(task, plan, execution, validation):
    from core.task import task_sha256
    current_task_hash = task_sha256(task)
    if plan.get("task_id") != task.get("task_id") or \
            plan.get("task_revision") != task.get("revision"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN",
                           "plan does not describe this task revision")
    if plan.get("task_sha256") != current_task_hash:
        raise GateRejected(
            "GATE_HASH_CHAIN_BROKEN",
            "plan task hash %s does not match the recomputed task hash %s"
            % (plan.get("task_sha256"), current_task_hash))
    if execution.get("task_sha256") != current_task_hash or \
            execution.get("task_id") != task.get("task_id"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN",
                           "execution task hash does not match task")
    if execution.get("plan_hash") != plan.get("plan_sha256"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN",
                           "execution plan hash does not match plan")
    if validation.get("task_sha256") != current_task_hash or \
            validation.get("plan_hash") != plan.get("plan_sha256"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN",
                           "validation hash chain does not match plan")
    if execution.get("artifact_class") != "intermediate":
        raise GateRejected(
            "GATE_ARTIFACT_CLASS_INVALID",
            "execution artifacts must be intermediate-class, got %s"
            % execution.get("artifact_class"))
    if execution.get("method_maturity") != plan.get("method_maturity"):
        raise GateRejected("GATE_HASH_CHAIN_BROKEN",
                           "execution method maturity does not match plan")
    exec_hashes = execution.get("artifact_hashes") or {}
    validation_hashes = validation.get("artifact_hashes") or {}
    if not exec_hashes or exec_hashes != validation_hashes:
        raise GateRejected(
            "GATE_HASH_CHAIN_BROKEN",
            "execution artifact hashes do not match the files that "
            "validation actually read")
    for rel in ("construct.gb", "construct.fasta"):
        on_disk = _sha256_file(pathlib.Path(execution[{
            "construct.gb": "product_gb",
            "construct.fasta": "product_fasta"}[rel]]))
        if on_disk != exec_hashes.get(rel):
            raise GateRejected(
                "GATE_ARTIFACT_TAMPERED",
                "intermediate file %s changed after validation: "
                "validated %s, on disk now %s"
                % (rel, exec_hashes.get(rel), on_disk))


def finalize(task, plan, execution, validation, out_dir):
    """Public seam: promote a fully verified execution to authoritative."""
    if task.get("mode") != "formal":
        raise GateRejected(
            "GATE_REQUIRES_FORMAL_MODE",
            "authoritative products require task.mode == formal")
    _check_chain(task, plan, execution, validation)

    if plan.get("method_maturity") != "validated":
        raise GateRejected(
            "GATE_EXPERIMENTAL_METHOD",
            "experimental methods can never produce authoritative products")

    if validation.get("overall") != "verified":
        raise GateRejected(
            "GATE_VALIDATION_FAILED",
            "three-layer validation did not reach verified",
            details={"overall": validation.get("overall"),
                     "error_codes": validation.get("error_codes")})

    approval = task.get("approvals", {}).get("user_confirmed_task") or {}
    if not approval.get("value"):
        raise GateRejected(
            "GATE_APPROVAL_MISSING",
            "formal delivery requires approvals.user_confirmed_task.value")

    for assumption in task.get("assumptions", []):
        if assumption.get("resolution_status") != "accepted-by-user":
            raise GateRejected(
                "GATE_UNRESOLVED_ASSUMPTION",
                "unresolved assumption blocks authoritative delivery",
                details={"assumption": assumption})

    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    authoritative = out_dir / "authoritative"
    if authoritative.exists():
        raise GateRejected(
            "GATE_AUTHORITATIVE_ALREADY_EXISTS",
            "refusing to overwrite an existing authoritative directory")
    tmp = out_dir / (".authoritative-%s.tmp" % task["task_id"])
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    try:
        gb_src = pathlib.Path(execution["product_gb"])
        gb_dst = tmp / "construct.gb"
        shutil.copyfile(gb_src, gb_dst)

        fa_src = pathlib.Path(execution["product_fasta"])
        fa_dst = tmp / "construct.fasta"
        shutil.copyfile(fa_src, fa_dst)

        dna_dst = tmp / "construct.dna"
        write_dna = subprocess.run(
            [sys.executable, "-X", "utf8", "-B",
             str(ROOT / "scripts" / "write_dna.py"),
             str(gb_dst), "--out", str(dna_dst), "--format", "dna",
             "--name", "construct", "--json"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        if write_dna.returncode != 0:
            raise GateRejected("GATE_DNA_WRITE_FAILED",
                               write_dna.stderr[-500:])

        manifest = {
            "schema_version": "delivery-manifest-v1",
            "artifact_class": "authoritative",
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
                task, plan, plan["sources"], method_maturity="validated",
                artifact_class="authoritative", execution=execution,
                validation=validation),
            "files": {},
        }
        for rel in ("construct.gb", "construct.fasta", "construct.dna"):
            manifest["files"][rel] = {
                "sha256": _sha256_file(tmp / rel),
                "class": "authoritative",
            }
        (tmp / "DELIVERY-MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8")

        # atomic promotion: no partial authoritative directory is observable
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
        "manifest_sha256": _sha256_file(authoritative /
                                        "DELIVERY-MANIFEST.json"),
        "files": sorted(str(p.relative_to(authoritative))
                        for p in authoritative.iterdir()),
    }
