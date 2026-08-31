# -*- coding: utf-8 -*-
"""v0.9.1-dev2 Architecture Recovery Regression Tests (TDD 先红后绿).

These 12 tests define the contract for resolving the three P0 findings
(interval semantics, goal validation rebuild, and untamperable delivery chain)
and critical P1 biological edge cases.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core import (
    execute,
    finalize,
    plan,
    validate,
    validate_construction_task,
)
from core.errors import (
    GateRejected,
    PlanningError,
    TaskBlockedError,
    TaskValidationError,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from simulate_advanced import ATTL1, ATTL2, ATTR1, ATTR2  # noqa: E402


def _record(seq: str, name: str, topology: str = "circular", features: tuple = ()) -> SeqRecord:
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = topology
    for f in features:
        rec.features.append(f)
    return rec


def _feat(label: str, start: int, end: int, ftype: str = "misc_feature", strand: int = 1, qualifiers: dict | None = None) -> SeqFeature:
    q = {"label": [label], "gene": [label]}
    if qualifiers:
        q.update(qualifiers)
    return SeqFeature(FeatureLocation(start, end, strand=strand), type=ftype, qualifiers=q)


def _sha256(path: pathlib.Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


class Dev2RecoveryRegressionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_gb(self, rec: SeqRecord, filename: str) -> tuple[pathlib.Path, str]:
        path = self.tmp / filename
        with open(path, "w", encoding="utf-8") as fh:
            SeqIO.write(rec, fh, "genbank")
        return path, _sha256(path)

    def _write_fa(self, seq: str, name: str, filename: str) -> tuple[pathlib.Path, str]:
        path = self.tmp / filename
        path.write_text(f">{name}\n{seq}\n", encoding="utf-8")
        return path, _sha256(path)

    def _base_task(self, kind: str, sources: list[dict], **overrides) -> dict:
        task = {
            "schema_version": "construction-task-v1",
            "task_id": f"task-dev2-{kind}",
            "revision": 1,
            "mode": "formal",
            "task_kind": kind,
            "raw_request": f"test request for {kind}",
            "sources": sources,
            "operation": {},
            "target": {"source_id": sources[0]["source_id"]},
            "product": {
                "topology": "circular" if kind not in ("component_amplification", "integration_donor", "crispr_editing") else "linear",
                "formats": ["gb", "fasta", "dna"],
                "required_components": [],
                "forbidden_components": [],
                "expected_topology": "circular" if kind not in ("component_amplification", "integration_donor", "crispr_editing") else "linear",
                "expected_operation": kind,
                "expected_junctions": [],
                "copy_count_constraints": {},
                "orientation_constraints": {},
                "frame_constraints": {},
            },
            "method_constraints": {},
            "approvals": {"user_confirmed_task": {"value": True}},
            "assumptions": [],
            "provenance": [],
        }
        task.update(overrides)
        return task

    # ----------------------------------------------------------------------
    # P0-01: 统一区间语义测试
    # ----------------------------------------------------------------------
    def test_linear_zero_width_interval_rejected(self):
        """P0-01: A zero-width interval [2, 2) on a linear record must be rejected,
        and NEVER interpreted as the whole template."""
        tmpl_rec = _record("A" * 50 + "C" * 50, "lin_tmpl", topology="linear")
        tmpl_path, tmpl_sha = self._write_gb(tmpl_rec, "lin_tmpl.gb")

        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(tmpl_path),
                "role": "template",
                "sha256": tmpl_sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [2, 2],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        with self.assertRaises((TaskValidationError, PlanningError)):
            vtask = validate_construction_task(task)
            plan(vtask)

    def test_linear_reverse_interval_rejected(self):
        """P0-01: A reverse interval [8, 3) on a linear record must be rejected
        without implicit modulo or circular wrapping."""
        tmpl_rec = _record("A" * 50 + "T" * 50, "lin_tmpl10", topology="linear")
        tmpl_path, tmpl_sha = self._write_gb(tmpl_rec, "lin_tmpl10.gb")

        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(tmpl_path),
                "role": "template",
                "sha256": tmpl_sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [8, 3],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        with self.assertRaises((TaskValidationError, PlanningError)):
            vtask = validate_construction_task(task)
            plan(vtask)

    # ----------------------------------------------------------------------
    # P0-02: Goal Validation 重构测试 (Decoy source isolation)
    # ----------------------------------------------------------------------
    def test_unused_source_cannot_satisfy_required_component(self):
        """P0-02: A required component name appearing in an unused decoy source feature
        must NOT satisfy goal validation if the product does not contain the component."""
        bb_rec = _record("A" * 40 + "TTTT" + "C" * 56, "bb", topology="circular")
        bb_path, bb_sha = self._write_gb(bb_rec, "bb.gb")

        decoy_rec = _record("G" * 80, "decoy", topology="linear", features=(
            _feat("RequiredX", 10, 50, "CDS"),
        ))
        decoy_path, decoy_sha = self._write_gb(decoy_rec, "decoy.gb")

        ins_rec = _record("GGGGGGGGGGGGGGGGGGGG", "insert_frag", topology="linear")
        ins_path, ins_sha = self._write_fa("GGGGGGGGGGGGGGGGGGGG", "insert_frag", "ins.fa")

        task = self._base_task(
            "plasmid_insert",
            sources=[
                {
                    "source_id": "bb-1",
                    "path": str(bb_path),
                    "role": "backbone",
                    "sha256": bb_sha,
                    "topology": "circular",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
                {
                    "source_id": "ins-1",
                    "path": str(ins_path),
                    "role": "insert",
                    "sha256": ins_sha,
                    "topology": "linear",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
                {
                    "source_id": "decoy-1",
                    "path": str(decoy_path),
                    "role": "reference",
                    "sha256": decoy_sha,
                    "topology": "linear",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
            ],
            operation={
                "insert": {
                    "boundary_0based": 40,
                    "insert_source_id": "ins-1",
                    "interval_0based": [0, 20],
                },
            },
            product={
                "topology": "circular",
                "formats": ["gb", "fasta", "dna"],
                "required_components": ["RequiredX"],  # RequiredX is NOT in product!
                "forbidden_components": [],
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec")
        val_res = validate(t, p, exec_res)

        # Goal validation MUST fail because RequiredX is not in the product
        self.assertFalse(val_res["goal_valid"], "Goal validation must be False when required component is missing from product")
        self.assertEqual(val_res["overall"], "failed")

        with self.assertRaises(GateRejected):
            finalize(t, p, exec_res, val_res, self.tmp / "out")
        self.assertFalse((self.tmp / "out" / "authoritative").exists())

    # ----------------------------------------------------------------------
    # P0-03: 不可伪造哈希链与篡改防御测试
    # ----------------------------------------------------------------------
    def test_plan_maturity_tamper_rejected(self):
        """P0-03: Tampering plan.method_maturity from experimental to validated
        must break hash chain and be rejected by finalize."""
        vector = _record("GGGGAATTCAAAAAGCTTCCC", "vector", "circular")
        insert = _record("TTAAGCTTAAAAAAGAATTCTT", "insert", "linear")
        v_path, v_sha = self._write_gb(vector, "vec.gb")
        i_path, i_sha = self._write_gb(insert, "ins.gb")

        task = self._base_task(
            "restriction_ligation",
            sources=[
                {
                    "source_id": "vector-1",
                    "path": str(v_path),
                    "role": "backbone",
                    "sha256": v_sha,
                    "topology": "circular",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
                {
                    "source_id": "insert-1",
                    "path": str(i_path),
                    "role": "insert",
                    "sha256": i_sha,
                    "topology": "linear",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
            ],
            operation={
                "vector_source_id": "vector-1",
                "insert_source_id": "insert-1",
                "vector_enzymes": ["EcoRI", "HindIII"],
                "orientation": "reverse",
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_tamper_mat")
        val_res = validate(t, p, exec_res)

        # Tamper plan maturity
        tampered_plan = dict(p)
        tampered_plan["method_maturity"] = "validated"

        with self.assertRaises(GateRejected):
            finalize(t, tampered_plan, exec_res, val_res, self.tmp / "out_tamper_mat")
        self.assertFalse((self.tmp / "out_tamper_mat" / "authoritative").exists())

    def test_validation_boolean_tamper_rejected(self):
        """P0-03: Tampering validation booleans (overall=verified, goal_valid=True)
        when a layer failed must be independently re-checked and rejected."""
        rec = _record("A" * 50 + "T" * 50, "tmpl", topology="linear")
        path, sha = self._write_gb(rec, "tmpl.gb")
        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [10, 40],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
            product={
                "topology": "linear",
                "formats": ["gb", "fasta", "dna"],
                "required_components": ["NonExistentFeature"],
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_val_tamper")
        val_res = validate(t, p, exec_res)
        self.assertEqual(val_res["overall"], "failed")

        # Tamper validation result
        tampered_val = dict(val_res)
        tampered_val["overall"] = "verified"
        tampered_val["goal_valid"] = True

        with self.assertRaises(GateRejected):
            finalize(t, p, exec_res, tampered_val, self.tmp / "out_val_tamper")
        self.assertFalse((self.tmp / "out_val_tamper" / "authoritative").exists())

    def test_source_changed_after_validation_rejected(self):
        """P0-03: Modifying a source file on disk after validation must be detected by
        finalize via re-hashing and rejected with GateRejected."""
        rec = _record("A" * 50 + "T" * 50, "tmpl_mod", topology="linear")
        path, sha = self._write_gb(rec, "tmpl_mod.gb")
        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [10, 40],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_src_mod")
        val_res = validate(t, p, exec_res)
        self.assertEqual(val_res["overall"], "verified")

        # Now tamper the source file on disk!
        path.write_text("GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG", encoding="utf-8")

        with self.assertRaises(GateRejected):
            finalize(t, p, exec_res, val_res, self.tmp / "out_src_mod")
        self.assertFalse((self.tmp / "out_src_mod" / "authoritative").exists())

    # ----------------------------------------------------------------------
    # P1-01: 三格式一致性核验
    # ----------------------------------------------------------------------
    def test_fasta_gb_mismatch_rejected(self):
        """P1-01: A mismatch between intermediate FASTA and GB sequence must be rejected
        during three-format verification at finalize."""
        rec = _record("A" * 50 + "T" * 50, "tmpl_fasta", topology="linear")
        path, sha = self._write_gb(rec, "tmpl_fasta.gb")
        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [10, 40],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_fa_mismatch")
        val_res = validate(t, p, exec_res)

        # Modify intermediate FASTA sequence
        fa_file = pathlib.Path(exec_res["product_fasta"])
        fa_file.write_text(">product\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC\n", encoding="utf-8")

        with self.assertRaises(GateRejected):
            finalize(t, p, exec_res, val_res, self.tmp / "out_fa_mismatch")
        self.assertFalse((self.tmp / "out_fa_mismatch" / "authoritative").exists())

    def test_dna_semantic_mismatch_rejected(self):
        """P1-01: Failure to produce semantically valid SnapGene .dna matching GB
        must fail finalize without delivering authoritative output."""
        rec = _record("A" * 50 + "T" * 50, "tmpl_dna", topology="linear")
        path, sha = self._write_gb(rec, "tmpl_dna.gb")
        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [10, 40],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_dna_mismatch")
        val_res = validate(t, p, exec_res)

        # Corrupt intermediate GB so that write_dna will produce corrupted output
        gb_file = pathlib.Path(exec_res["product_gb"])
        gb_file.write_text("NOT A VALID GENBANK FILE", encoding="utf-8")

        with self.assertRaises(GateRejected):
            finalize(t, p, exec_res, val_res, self.tmp / "out_dna_mismatch")
        self.assertFalse((self.tmp / "out_dna_mismatch" / "authoritative").exists())

    # ----------------------------------------------------------------------
    # P1-04: 生物学边界与细节修复测试
    # ----------------------------------------------------------------------
    def test_experimental_validation_failure_is_failed(self):
        """P1-04: In experimental task validation, if any validation layer fails,
        overall must be 'failed', NEVER unconditionally 'experimental-preview'."""
        vector = _record("GGGGAATTCAAAAAGCTTCCC", "vector", "circular")
        insert = _record("TTAAGCTTAAAAAAGAATTCTT", "insert", "linear")
        v_path, v_sha = self._write_gb(vector, "vec_exp.gb")
        i_path, i_sha = self._write_gb(insert, "ins_exp.gb")

        task = self._base_task(
            "restriction_ligation",
            sources=[
                {
                    "source_id": "vector-1",
                    "path": str(v_path),
                    "role": "backbone",
                    "sha256": v_sha,
                    "topology": "circular",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
                {
                    "source_id": "insert-1",
                    "path": str(i_path),
                    "role": "insert",
                    "sha256": i_sha,
                    "topology": "linear",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
            ],
            operation={
                "vector_source_id": "vector-1",
                "insert_source_id": "insert-1",
                "vector_enzymes": ["EcoRI", "HindIII"],
                "orientation": "reverse",
            },
            product={
                "topology": "circular",
                "formats": ["gb", "fasta", "dna"],
                "required_components": ["NonExistentMarker"],
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_exp_fail")
        val_res = validate(t, p, exec_res)

        # Must be "failed", not "experimental-preview"
        self.assertEqual(val_res["overall"], "failed")
        self.assertFalse(val_res["goal_valid"])

    def test_linear_integration_arm_boundary_no_wrap(self):
        """P1-04: Linear reference sequence boundary shortage must NOT modulo wrap."""
        ref_rec = _record("A" * 100, "chr1", topology="linear")
        ref_path, ref_sha = self._write_gb(ref_rec, "chr1.gb")

        donor_rec = _record("G" * 50, "donor", topology="linear")
        donor_path, donor_sha = self._write_gb(donor_rec, "donor.gb")

        task = self._base_task(
            "integration_donor",
            sources=[
                {
                    "source_id": "locus-1",
                    "path": str(ref_path),
                    "role": "locus",
                    "sha256": ref_sha,
                    "topology": "linear",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
                {
                    "source_id": "donor-1",
                    "path": str(donor_path),
                    "role": "template",
                    "sha256": donor_sha,
                    "topology": "linear",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
            ],
            target={
                "source_id": "donor-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [0, 50],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
            operation={
                "homology_arms": {
                    "left_arm": "A" * 20,
                    "right_arm": "A" * 20,
                },
                "locus": {
                    "source_id": "locus-1",
                    "interval_0based": [80, 130],  # 130 > 100 (linear chromosome length 100!)
                },
            },
        )
        with self.assertRaises((TaskValidationError, PlanningError)):
            vtask = validate_construction_task(task)
            plan(vtask)

    def test_gateway_stop_checked_in_declared_frame(self):
        """P1-04: Gateway stop policy must check target reading frame only."""
        body = "AAAACCCTTTTAA"
        entry = _record(ATTL1 + body + str(Seq(ATTL2).reverse_complement()) + "G" * 40, "entry", "circular")
        destination = _record(ATTR1 + "TTTTCCCC" + str(Seq(ATTR2).reverse_complement()) + "C" * 40, "destination", "circular")
        entry_path, entry_sha = self._write_gb(entry, "entry.gb")
        dest_path, dest_sha = self._write_gb(destination, "destination.gb")

        task = self._base_task(
            "gateway_recombination",
            sources=[
                {
                    "source_id": "entry-1",
                    "path": str(entry_path),
                    "role": "entry",
                    "sha256": entry_sha,
                    "topology": "circular",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
                {
                    "source_id": "dest-1",
                    "path": str(dest_path),
                    "role": "destination",
                    "sha256": dest_sha,
                    "topology": "circular",
                    "evidence": {"source_evidence_class": "user-provided"},
                },
            ],
            operation={
                "reaction": "lr",
                "stop_policy": "stop",
                "entry_source_id": "entry-1",
                "destination_source_id": "dest-1",
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_gw_stop")
        val_res = validate(t, p, exec_res)
        self.assertEqual(val_res["overall"], "verified")

    def test_translation_table_preserved(self):
        """P1-04: CDS translation table must come from feature qualifier /transl_table,
        host, or user confirmation, and not be hardcoded to table 11."""
        cds_seq = "ATGCTGTAA"  # Met-Ser-Stop in table 12; Met-Leu-Stop in table 11
        rec = _record("A" * 30 + cds_seq + "T" * 30, "yeast_gene", topology="linear", features=(
            _feat("test_cds", 30, 39, "CDS", qualifiers={"transl_table": ["12"]}),
        ))
        path, sha = self._write_gb(rec, "yeast_gene.gb")

        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [30, 39],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_table12")
        val_res = validate(t, p, exec_res)

        self.assertEqual(val_res["overall"], "verified")
        prod_rec = SeqIO.read(exec_res["product_gb"], "genbank")
        cds_features = [f for f in prod_rec.features if f.type == "CDS"]
        if cds_features:
            table_val = cds_features[0].qualifiers.get("transl_table", ["11"])[0]
            self.assertEqual(table_val, "12")

    def test_float_coordinate_rejected(self):
        """Interval coordinates with float values must be strictly rejected."""
        rec = _record("A" * 50 + "T" * 50, "tmpl_float", topology="linear")
        path, sha = self._write_gb(rec, "tmpl_float.gb")
        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [10.5, 40],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        with self.assertRaises((PlanningError, TaskValidationError)):
            vtask = validate_construction_task(task)
            plan(vtask)

    def test_cds_translation_mismatch_fails_artifact_validation(self):
        """A CDS whose claimed translation does not match the actual translated sequence must fail validation."""
        cds_seq = "ATGAAATAA"  # MK*
        rec = _record("A" * 20 + cds_seq + "T" * 20, "tmpl_cds_mismatch", topology="linear", features=(
            _feat("my_cds", 20, 29, "CDS", qualifiers={"translation": ["MV*"], "transl_table": ["11"]}),
        ))
        path, sha = self._write_gb(rec, "tmpl_cds_mismatch.gb")
        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "tmpl-1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "linear",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "tmpl-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [20, 29],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_cds_mismatch")
        val_res = validate(t, p, exec_res)
        self.assertFalse(val_res["artifact_valid"])
        self.assertEqual(val_res["overall"], "failed")

    def test_backbone_contamination_in_linear_amplicon(self):
        """Leaking unwanted backbone elements into linear amplicons must be caught by check_backbone_contamination."""
        template = _record("A" * 20 + "GGATCC" + "C" * 40, "pVec", "circular", features=(
            _feat("cassette", 20, 26, "misc_feature"),
            _feat("bla", 30, 40, "CDS"),
            _feat("ori", 5, 10, "rep_origin"),
        ))
        path, sha = self._write_gb(template, "pVec.gb")
        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "template-1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "circular",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "template-1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [20, 26],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_contam")
        # Contaminate product by replacing with full circular template sequence
        contaminated_seq = "A" * 20 + "GGATCC" + "C" * 40
        contam_rec = _record(contaminated_seq, "contam", topology="linear", features=(
            _feat("cassette", 20, 26, "misc_feature"),
            _feat("bla", 30, 40, "CDS"),
            _feat("ori", 5, 10, "rep_origin"),
        ))
        with open(exec_res["product_gb"], "w", encoding="utf-8") as fh:
            SeqIO.write(contam_rec, fh, "genbank")
        pathlib.Path(exec_res["product_fasta"]).write_text(f">{task['task_id']}\n{contaminated_seq}\n", encoding="utf-8")
        exec_res["product_sequence"] = contaminated_seq
        val_res = validate(t, p, exec_res)
        self.assertFalse(val_res["goal_valid"])
        self.assertIn("UNEXPECTED_VECTOR_BACKBONE_IN_DONOR", " ".join(val_res["error_codes"]))

    def test_unimplemented_task_kind_raises_blocked_error(self):
        """Unknown or unimplemented task kind must raise TaskBlockedError and not fall back to generic assembly."""
        from core.registry import get_task_handler
        with self.assertRaises(TaskBlockedError) as ctx:
            get_task_handler("non_existent_magic_task")
        self.assertIn("TASK_KIND_NOT_REGISTERED", ctx.exception.error_code)

    def test_independent_recompute_detects_tampered_plan_sequence(self):
        """If plan product sequence is tampered, independent recompute must fail computation validation."""
        path, sha = self._write_gb(_record("ATGCATGC" * 5, "p1"), "p1.gb")
        task = self._base_task(
            "component_amplification",
            sources=[{
                "source_id": "p1",
                "path": str(path),
                "role": "template",
                "sha256": sha,
                "topology": "circular",
                "evidence": {"source_evidence_class": "user-provided"},
            }],
            target={
                "source_id": "p1",
                "selection": {
                    "kind": "interval",
                    "interval_0based": [0, 8],
                    "resolution_status": "resolved",
                    "resolution_evidence": [{"kind": "user-interval"}],
                },
            },
        )
        vtask = validate_construction_task(task)
        t, p = plan(vtask)
        exec_res = execute(t, p, self.tmp / "exec_tamper_seq")
        # Tamper product files with a 1-bp mutation
        tampered_seq = "TTGCATGC"
        pathlib.Path(exec_res["product_fasta"]).write_text(f">{task['task_id']}\n{tampered_seq}\n", encoding="utf-8")
        tampered_rec = _record(tampered_seq, "tampered", topology="linear")
        with open(exec_res["product_gb"], "w", encoding="utf-8") as fh:
            SeqIO.write(tampered_rec, fh, "genbank")
        val_res = validate(t, p, exec_res)
        self.assertFalse(val_res["computation_valid"])
        self.assertIn("Recomputed sequence", " ".join(val_res["errors"]))


if __name__ == "__main__":
    unittest.main()
