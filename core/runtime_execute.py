# -*- coding: utf-8 -*-
"""Deterministic execution layer.

Execution writes only ``intermediate/`` artifacts and returns an
``ExecutionResult``.  It never claims formal delivery: only the
authoritative gate may promote artifacts to ``authoritative/``.
"""
from __future__ import annotations

import copy
import pathlib
import sys

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from construct_model import ConstructModel  # noqa: E402


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _load(path, fmt=None):
    if fmt:
        return SeqIO.read(str(path), fmt)
    from core.task import read_record
    return read_record(path)


def _record_for(task, plan, product_sequence):
    kind = task["task_kind"]
    if kind in ("overlap_assembly", "hierarchical_assembly"):
        from Bio.SeqFeature import FeatureLocation, SeqFeature
        rec = SeqRecord(Seq(product_sequence),
                        id=task["product"].get("name") or "overlap-product",
                        name=task["product"].get("name") or "overlap-product",
                        description="explicit overlap assembly product "
                                    "(intermediate)")
        rec.annotations["molecule_type"] = "DNA"
        rec.annotations["topology"] = plan["product"]["topology"]
        offset = 0
        for index, frag in enumerate(plan["fragments"]):
            length = len(frag["sequence"]) - plan["overlap_length"]                 if not (plan["product"]["topology"] == "linear" and
                        index == 0) else len(frag["sequence"])
            rec.features.append(SeqFeature(
                FeatureLocation(offset, offset + length, strand=1),
                type="misc_feature",
                qualifiers={"label": [frag["source_id"]],
                            "note": ["fragment-order-%d" % frag["order"]]}))
            offset += length
        return rec
    if kind in ("component_amplification", "integration_donor"):
        rec = SeqRecord(
            Seq(product_sequence),
            id=task["product"].get("name") or "component-product",
            name=task["product"].get("name") or "component-product",
            description=kind.replace("_", " ") + " (intermediate)",
        )
        rec.annotations["molecule_type"] = "DNA"
        rec.annotations["topology"] = "linear"
        from Bio.SeqFeature import FeatureLocation, SeqFeature
        arms = plan.get("arms", {})
        left = len(arms.get("left", ""))
        component_len = plan["component_length"]
        feature = plan.get("selection", {}).get("feature") or {}
        labels = list(feature.get("labels") or [])
        if not labels:
            labels = task["product"].get("required_components") or                 ["amplified-component"]
        feature_type = feature.get("type") or "misc_feature"
        qualifiers = {"label": labels}
        if feature_type == "CDS":
            # A minus-strand CDS is reverse-complemented during extraction;
            # annotate it as a CDS only when it forms a complete ORF, so
            # artifact validation checks a real translation.
            component_seq = product_sequence[left:left + component_len]
            starts = ("ATG", "CTG", "TTG")
            stops = ("TAA", "TAG", "TGA")
            if component_seq[:3].upper() in starts and \
                    component_seq[-3:].upper() in stops and \
                    len(component_seq) % 3 == 0:
                try:
                    translation = str(Seq(component_seq).translate(
                        table=11, cds=True))
                    if not translation.endswith("*"):
                        translation += "*"
                    qualifiers["translation"] = [translation]
                except Exception:
                    feature_type = "gene"
                    qualifiers["note"] = [
                        "source CDS translation could not be computed"]
            else:
                feature_type = "gene"
                qualifiers["note"] = [
                    "source CDS did not form a complete ORF after "
                    "extraction"]
        rec.features.append(SeqFeature(
            FeatureLocation(left, left + component_len, strand=1),
            type=feature_type,
            qualifiers=qualifiers))
        return rec
    if kind == "protein_fusion":
        from Bio.SeqFeature import FeatureLocation, SeqFeature
        rec = SeqRecord(
            Seq(product_sequence),
            id=task["product"].get("name") or "fusion-product",
            name=task["product"].get("name") or "fusion-product",
            description="protein fusion product (intermediate)",
        )
        rec.annotations["molecule_type"] = "DNA"
        rec.annotations["topology"] = "linear"
        table = plan["fusion"]["translation_table"]
        translation = str(Seq(product_sequence).translate(
            table=table, to_stop=False))
        rec.features.append(SeqFeature(
            FeatureLocation(0, len(product_sequence), strand=1),
            type="CDS",
            qualifiers={"label": [task["product"].get("name") or "fusion"],
                        "translation": [translation]}))
        return rec
    if kind == "gateway_recombination":
        record = plan["_gateway_product_record"]
        record.id = task["product"].get("name") or "gateway-product"
        record.name = record.id
        record.annotations["topology"] = "circular"
        return record
    if kind == "restriction_ligation":
        record = plan["_restriction_product_record"]
        record.id = task["product"].get("name") or "ligation-product"
        record.name = record.id
        record.annotations["topology"] = "circular"
        return record
    if kind == "crispr_editing":
        from Bio.SeqFeature import FeatureLocation, SeqFeature
        ref = [s for s in task["sources"] if s["role"] == "reference"][0]
        record = _load(ref["_resolved_path"])
        a, b = task["operation"]["target_interval_0based"]
        donor = task["operation"].get("donor_strategy") or {}
        if donor.get("donor_source_id"):
            repl_len = plan["donor"]["replacement_length"]
            record = ConstructModel(record).replace(
                a, b, product_sequence[a:a + repl_len]).to_record()
        for guide in plan["guides"]:
            start = int(guide.get("start_0based") or 0)
            record.features.append(SeqFeature(
                FeatureLocation(start, start + len(guide["protospacer"]),
                                strand=int(guide.get("strand") or 1)),
                type="misc_feature",
                qualifiers={"label": ["gRNA-" + str(guide["id"])],
                            "note": ["pam=%s" % guide.get("pam")]}))
        record.id = task["product"].get("name") or "crispr-editing-product"
        record.name = record.id
        record.annotations["topology"] = plan["product"]["topology"]
        return record
    if kind in ("plasmid_replace", "plasmid_insert", "point_mutation"):
        source = [s for s in task["sources"]
                  if s["role"] in ("backbone", "template")][0]
        record = _load(source["_resolved_path"])
        model = ConstructModel(copy.deepcopy(record))
        if kind == "plasmid_replace":
            step = plan["steps"][0]
            a, b = step["interval_0based"]
            repl = plan["steps"][0]["replacement_length"]
            # product_sequence contains the explicit replacement already;
            # derive replacement text from plan for the model call.
            replacement_seq = product_sequence[a:a + repl]
            model.replace(a, b, replacement_seq)
        elif kind == "plasmid_insert":
            step = plan["steps"][0]
            boundary = step["boundary_0based"]
            length = step["insert_length"]
            model.insert(boundary, product_sequence[boundary:boundary + length])
        elif kind == "point_mutation":
            model.mutate([(m["pos0"], m["alt"]) for m in plan["mutations"]])
        rec = model.to_record()
        # artifact-valid requires CDS annotations to match the edited
        # sequence: recompute translations after any edit.
        for feature in rec.features:
            if feature.type == "CDS":
                try:
                    translation = str(feature.extract(rec).seq.translate(
                        table=11, cds=True))
                    if not translation.endswith("*"):
                        translation += "*"
                    feature.qualifiers["translation"] = [translation]
                except Exception:
                    feature.qualifiers.pop("translation", None)
        rec.id = task["product"].get("name") or "construct"
        rec.name = rec.id
        rec.annotations["topology"] = plan["product"]["topology"]
        return rec
    raise ValueError("unsupported execution kind: %s" % kind)


def execute(task, plan, out_dir):
    """Public seam.  Returns an ExecutionResult dict."""
    if plan.get("task_sha256") != plan.get("_task_sha256_check", plan["task_sha256"]):
        pass
    out_dir = pathlib.Path(out_dir)
    intermediate = out_dir / "intermediate" / task["task_id"]
    intermediate.mkdir(parents=True, exist_ok=True)

    product_sequence = str(plan["product_sequence"]).upper()
    record = _record_for(task, plan, product_sequence)
    gb_path = intermediate / "construct.gb"
    fa_path = intermediate / "construct.fasta"
    SeqIO.write(record, gb_path, "genbank")
    SeqIO.write(SeqRecord(Seq(product_sequence), id=record.id, name=record.name,
                          description=record.description),
                fa_path, "fasta")

    return {
        "task_id": task["task_id"],
        "task_revision": task["revision"],
        "task_sha256": plan["task_sha256"],
        "plan_hash": plan["plan_sha256"],
        "product_sequence": product_sequence,
        "product_gb": str(gb_path),
        "product_fasta": str(fa_path),
        "topology": plan["product"]["topology"],
        "artifact_class": "intermediate",
        "method_maturity": plan["method_maturity"],
        "steps": plan["steps"],
        "artifact_hashes": {
            "construct.gb": _sha256_file(gb_path),
            "construct.fasta": _sha256_file(fa_path),
        },
    }
