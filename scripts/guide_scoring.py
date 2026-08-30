# -*- coding: utf-8 -*-
"""guide_scoring.py - Real on-target efficiency scoring gate.

* SpCas9  -> Doench-2016 / Azimuth V3 (real pickled model, real features).
* AsCas12a -> DeepCpf1 / Kim 2018 (real Keras weights evaluated by PyTorch,
  34 bp context semantics).
* LbCas12a -> no reviewed model selected; always unavailable.

No result ever claims a prediction when a backend or the required sequence
context is unavailable.
"""
import json
import sys

from provenance import source, read_version

APPLICABILITY_WARNINGS = {
    "spcas9-wt": [
        "Azimuth/Doench-2016 was trained and validated in mammalian contexts; "
        "it is not specifically validated for yeast or other species."],
    "ascas12a-wt": [
        "DeepCpf1/Kim-2018 applies to AsCas12a, NOT LbCas12a.",
        "DeepCpf1 scores the first 20 PAM-proximal bases; full 23-nt "
        "AsCas12a candidates are scored on that truncated context."],
    "lbcas12a-wt": [
        "No reviewed on-target model is selected for LbCas12a."],
}

MODEL_APPLICABILITY = {
    "spcas9-wt": {
        "Doench-2016": {"backend": "azimuth", "context_key": "azimuth_30mer",
                        "context_length": 30},
    },
    "ascas12a-wt": {
        "DeepCpf1": {"backend": "deepcpf1", "context_key": "deepcpf1_34mer",
                     "context_length": 34},
    },
    "lbcas12a-wt": {},
}


def _unavailable(model_name, reason):
    return {
        "model": model_name,
        "status": "unavailable",
        "reason": reason,
    }


def _run_azimuth(contexts):
    if not contexts:
        return None, "AZIMUTH_CONTEXT_UNAVAILABLE"
    try:
        from azimuth_backend import score_30mers
        score = float(score_30mers([contexts])[0])
        return {
            "score": score,
            "score_range": [0.0, 1.0],
            "model": "Doench-2016",
            "model_version": "Azimuth-V3",
            "context_sequence": contexts,
            "context_length": 30,
            "context_semantics": "4-upstream+20-protospacer+NGG+3-downstream",
            "warnings": APPLICABILITY_WARNINGS.get("spcas9-wt", []),
        }, None
    except Exception as error:  # noqa: BLE001 - model failures degrade to unavailable
        return None, "AZIMUTH_BACKEND_UNAVAILABLE: %s" % error


def _run_deepcpf1(contexts, strand):
    if not contexts:
        return None, "DEEPCPF1_CONTEXT_UNAVAILABLE"
    try:
        from deepcpf1_model import predict_sequence_only
        score = float(predict_sequence_only([contexts])[0])
        return {
            "score": score,
            "score_range": [0.0, 1.0],
            "model": "DeepCpf1",
            "model_version": "DeepCpf1-Kim-2018",
            "context_sequence": contexts,
            "context_length": 34,
            "context_semantics": "4-upstream+TTTV-PAM+20-gRNA+6-downstream",
            "strand_direction": strand,
            "warnings": APPLICABILITY_WARNINGS.get("ascas12a-wt", []),
        }, None
    except Exception as error:  # noqa: BLE001
        return None, "DEEPCPF1_BACKEND_UNAVAILABLE: %s" % error


def _heuristic_qc(sequence):
    seq = str(sequence or "").upper()
    if not seq:
        return {"gc_percent": None, "homopolymer_risk": None}
    gc = round((seq.count("G") + seq.count("C")) / len(seq) * 100, 2)
    longest = 0
    current = seq[0]
    run = 1
    for base in seq[1:]:
        if base == current:
            run += 1
        else:
            longest = max(longest, run)
            current = base
            run = 1
    longest = max(longest, run)
    return {
        "gc_percent": gc,
        "homopolymer_risk": "high" if longest >= 4 else
                            ("medium" if longest == 3 else "low"),
    }


def score_guides(candidates, nuclease_id):
    applicability = MODEL_APPLICABILITY.get(nuclease_id, {})
    version = read_version()
    results = []
    for candidate in candidates:
        scores = []
        contexts = candidate.get("context_sequences") or {}
        guide_id = candidate.get("id")
        strand = candidate.get("strand")
        for model_name, spec in applicability.items():
            if spec["backend"] == "azimuth":
                payload, error = _run_azimuth(contexts.get(spec["context_key"]))
            elif spec["backend"] == "deepcpf1":
                payload, error = _run_deepcpf1(contexts.get(spec["context_key"]),
                                               strand)
            else:
                payload, error = None, "backend-not-configured"
            if error:
                scores.append(_unavailable(model_name, error))
            else:
                payload["status"] = "available"
                scores.append(payload)
        if nuclease_id == "lbcas12a-wt" and not scores:
            scores.append({
                "model": None,
                "status": "unavailable",
                "reason": "no-reviewed-model-selected-for-lbcas12a",
                "warnings": APPLICABILITY_WARNINGS.get("lbcas12a-wt", []),
            })
        results.append({
            "guide_id": guide_id,
            "on_target_scores": scores,
            "applicability_warnings": APPLICABILITY_WARNINGS.get(nuclease_id, []),
            "heuristic_qc": _heuristic_qc(
                candidate.get("protospacer_sequence")),
            "provenance": [source(
                "software", "SnapGene DNA Design guide_scoring",
                "on-target-scoring-gate", version=version, status="verified",
                verification={"method": "unit-tests", "status": "verified"})],
        })
    return results


def main():
    print(json.dumps(score_guides([{"id": "gRNA-001"}], "lbcas12a-wt"),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
