# -*- coding: utf-8 -*-
"""primer_design_engine.py - M3 primer design engine.

Prefers a real ``primer3_core`` process; when it is unavailable the
heuristic scanner from ``design_primers.py`` is used and clearly labelled as
NOT Primer3.  Tails (overlap homology or restriction sites + protective
bases) are appended after the binding region has been selected.
"""
import pathlib
import sys

from Bio.Seq import Seq
from validation_crosscheck import primer_tm_crosscheck

from provenance import source, read_version
from primer3_core_backend import (
    Primer3CoreError, design_anchored_pairs, probe_primer3_core,
)
from operation_consent import (
    ConsentBroker, ConsentRequiredError, TransparencyLog, make_request,
    sha256_prefix,
)
from design_primers import (
    PROTECTIVE_BASES, SITE_SEQS, ThermoEngine, build_pairs, scan_side,
)

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


RESTRICTION_TAIL_SOURCE = (
    "NEB: Cleavage Close to the End of DNA Fragments, "
    "https://www.neb.com/en/faqs/cleavage-close-to-the-end-of-dna-fragments "
    "(minimal common 5' flanks; add >=4 bases for PCR primers per NEB)"
)


def restriction_tail(enzyme_names):
    """Build a 5' tail: NEB protective bases + recognition sequence(s)."""
    extra = ""
    for name in enzyme_names:
        key = next((k for k in SITE_SEQS if k.lower() == str(name).lower()),
                   None)
        if key is None:
            raise ValueError("UNKNOWN_RESTRICTION_ENZYME: %s" % name)
        extra += PROTECTIVE_BASES.get(key, "G") + SITE_SEQS[key]
    return extra


def _validate_primer(primer, side, tail="", target_tm=60.0):
    binding = str(primer.get("binding") or primer.get("sequence") or "")
    if tail:
        binding = binding[len(tail):] if binding.startswith(tail) else binding
    tm = float(primer.get("tm") or 0.0)
    gc = float(primer.get("gc") or 0.0)
    hairpin = primer.get("hairpin") or {}
    self_dimer = primer.get("self_dimer") or {}
    heterodimer = primer.get("heterodimer") or {}
    problems = []
    if not (52.0 <= tm <= 72.0):
        problems.append("primer_tm_outside_52_72: %.1f" % tm)
    if abs(tm - target_tm) > 5.0:
        problems.append("primer_tm_off_target: %.1f vs %.1f" % (tm, target_tm))
    if not (30.0 <= gc <= 70.0):
        problems.append("primer_gc_outside_30_70: %.1f" % gc)
    if binding and binding[-1] not in "GC":
        problems.append("primer_3prime_lacks_gc_clamp")
    hairpin_tm = float(hairpin.get("tm") or hairpin.get("score") or 0.0)
    self_any = float(self_dimer.get("tm_any") or self_dimer.get("score") or 0.0)
    hetero_any = float(heterodimer.get("tm_any") or heterodimer.get("score") or 0.0)
    # Primer3 defaults: PRIMER_MAX_HAIRPIN_TH=47.0,
    # PRIMER_MAX_SELF_ANY_TH=47.0.
    if hairpin_tm >= tm-10.0 or self_any >= tm-10.0 or hetero_any >= tm-10.0:
        problems.append("primer_strong_secondary_structure")
    crosscheck = None
    if binding:
        mg = 1.5 if primer.get("_backend") == "primer3-core" else 0.0
        crosscheck = primer_tm_crosscheck(
            binding, tm, primer.get("_backend", "unknown"), mg=mg)
        if crosscheck["status"] == "conflict-error":
            problems.append("primer_tm_crosscheck_failed")
        elif crosscheck["status"] == "conflict-warn":
            problems.append("primer_tm_crosscheck_warn")
    return {
        "passed": not problems,
        "problems": problems,
        "backend": primer.get("_backend", "unknown"),
        "source": ((primer.get("_backend_source") or "primer3-core")
                   if primer.get("_backend") == "primer3-core"
                   else "heuristic scanner; NOT Primer3"),
        "tm_crosscheck": crosscheck,
        "validation_windows": {
            "tm_c": [52.0, 72.0],
            "gc_percent": [30.0, 70.0],
            "note": ("independent QC gate; stricter than the consented "
                     "Primer3 design window (GC 20-80, Tm 50-72)"),
        },
    }



def json_like_explain(explain):
    return "; ".join("%s=%s" % (key, value)
                     for key, value in (explain or {}).items() if value)


def _resolve_consent_broker(consent, consent_policy, confirm_callback):
    if consent is None:
        return ConsentBroker(policy=consent_policy,
                             confirm_callback=confirm_callback)
    if isinstance(consent, ConsentBroker):
        return consent
    if isinstance(consent, dict):
        return ConsentBroker(
            policy=consent.get("policy", "ask"),
            confirm_callback=consent.get("confirm_callback"),
            pre_approved=consent.get("pre_approved", ()))
    raise TypeError("consent must be None, a ConsentBroker, or a dict")


def _explain_alternatives(explain):
    """Turn Primer3 explain counts into actionable, human-readable paths."""
    text = json_like_explain(explain).lower()
    alternatives = []
    if "high hairpin" in text:
        alternatives.append({
            "code": "EXTEND_FLANK_OUTSIDE_AMPLICON",
            "action": ("扩增子端部 5' 外扩 20-40 bp，避开高发夹端部序列后重新设计；"
                       "或改用内部引物对。"),
        })
    if "high tm" in text or "low tm" in text:
        alternatives.append({
            "code": "ADJUST_TM_WINDOW_OR_PRIMER_LENGTH",
            "action": ("Tm 超窗集中在边界强制位置：放宽长度窗口或提供更多侧翼序列；"
                       "避免在 52-72 C 之外硬选。"),
        })
    if ("high gc" in text or "low gc" in text or
            "gc content failed" in text):
        alternatives.append({
            "code": "GC_WINDOW_NEEDS_USER_CONSENT",
            "action": ("GC 超界时不要静默放宽：扩增子 5' 端外扩 20-40 bp 避开 "
                       "poly-G/C 端部，或改用内部引物对；也可加入 DMSO/甜菜碱/"
                       "GC Enhancer 方案，或经询问后放宽 GC 窗口。"),
        })
    if "high any compl" in text or "high end compl" in text:
        alternatives.append({
            "code": "REDESIGN_OR_EXTEND_REGION",
            "action": "端部互补性过高：5' 外扩 20-40 bp 或改用内部引物对。",
        })
    alternatives.append({
        "code": "USE_INTERNAL_PRIMER_PAIR",
        "action": ("若必须保留扩增子坐标，可采用内部引物对（不强制覆盖边界），"
                   "产物会短于原目标区间；或人工检查端部序列。"),
    })
    return alternatives


def design_region_primers(sequence, region_start=0, fwd_tail="", rev_tail="",
                          target_tm=60.0, min_len=18, max_len=27, top_n=3,
                          primer3_core=None, timeout=30, require_primer3=False,
                          consent=None, consent_policy="ask",
                          confirm_callback=None, operation_log=None,
                          allow_slide=True):
    """Design exact-boundary primers for ``sequence[start:end]``.

    Release-iteration behavior:

    * every run first confirms the parameter window through a structured
      ``ConsentBroker`` request (regular confirmation);
    * layer-1..3 retries (tailed -> binding-only -> relaxed Tm) are kept;
    * layer 4 ``slide-retry`` releases Primer3's forced starts within
      ``min(25, n//4)`` nt, widens the product window to +/-100 bp and keeps
      GC at Primer3's 20-80 default; it runs only after explicit relaxation
      consent;
    * degradation to heuristic fallback and every abnormal relaxation require
      explicit consent; without it ``ConsentRequiredError`` is raised and
      nothing is executed.
    """
    sequence = str(sequence).upper()
    region_end = len(sequence)
    if not (0 <= region_start < region_end):
        raise ValueError("invalid primer region: %d..%d" %
                         (region_start, region_end))
    region = sequence[region_start:region_end]
    if len(region) < min_len * 2:
        raise ValueError("region too short for two primers")
    broker = _resolve_consent_broker(consent, consent_policy, confirm_callback)
    log = operation_log if operation_log is not None else broker.log
    log.append({
        "operation": "primer-design-start",
        "backend": "primer3-core-or-heuristic",
        "parameters": {
            "region_start": region_start, "region_length": len(region),
            "target_tm": target_tm, "min_len": min_len, "max_len": max_len,
            "top_n": top_n, "fwd_tail": fwd_tail, "rev_tail": rev_tail,
            "require_primer3": require_primer3,
        },
        "input_sequence_sha256_prefix": sha256_prefix(sequence),
    })
    broker.request(make_request(
        "primer-design-parameters", "parameter-confirmation",
        "确认引物设计参数窗口与后端策略后执行",
        parameters={
            "target_tm": target_tm,
            "tm_window": [max(0.0, target_tm - 5.0), target_tm + 5.0],
            "gc_range": [20.0, 80.0],
            "length_range": [min_len, max_len],
            "product_size_mode": "exact-boundary, slide only after consent",
            "backend_preference": "primer3_core; heuristic only after consent",
        }))
    probe = probe_primer3_core(primer3_core)
    log.append({
        "operation": "backend-probe",
        "backend": "primer3-core",
        "status": probe["status"],
        "path": probe.get("path"),
        "version": probe.get("version"),
        "detail": probe.get("detail"),
    })
    use_primer3 = probe["status"] == "available"
    failure = None if use_primer3 else probe.get("detail") or "primer3_core unavailable"
    if require_primer3 and not use_primer3:
        raise Primer3CoreError(failure)
    if not use_primer3 and not require_primer3:
        broker.request(make_request(
            "primer3-unavailable-fallback", "degradation",
            "primer3_core 不可用；拟降级为热力学启发式扫描（候选将标注 NOT Primer3）",
            parameters={"probe": probe},
            alternatives=[{
                "code": "INSTALL_PRIMER3_OR_SET_PRIMER3_CORE",
                "action": "安装 primer3_core 或设置 PRIMER3_CORE 环境变量后重试；"
                          "或使用 --require-primer3 让流程失败关闭。"}],
            risk="启发式结果未经 Primer3 验证，不得声称 Primer3 设计"))
    retry_note = None
    alternatives = []
    slide_offsets = None
    if use_primer3:
        attempts = []
        if fwd_tail or rev_tail:
            attempts.append(("tailed", fwd_tail, rev_tail,
                             (target_tm - 5.0, target_tm + 5.0), False))
            attempts.append(("binding-only-retry", "", "",
                             (target_tm - 5.0, target_tm + 5.0), False))
        else:
            attempts.append(("tailed", "", "",
                             (target_tm - 5.0, target_tm + 5.0), False))
        attempts.append(("relaxed-tm-retry", "", "", (50.0, 72.0), False))
        if allow_slide:
            attempts.append(("slide-retry", "", "", (50.0, 72.0), True))
        last_explain = ""
        primer3_succeeded = False
        for attempt_name, use_fwd_tail, use_rev_tail, tm_range, use_slide in attempts:
            if use_slide:
                broker.request(make_request(
                    "slide-retry", "relaxation",
                    "前 3 层精确边界设计无解；拟释放 Primer3 强制起点，允许引物 "
                    "5' 端在 0..min(25, len/4) nt 内滑动，产物窗口放宽为 n-100..n+100，"
                    "Tm 窗口 50-72 C；GC 仍保持 20-80%",
                    parameters={"slide_budget": min(25, max(0, len(region) // 4)),
                                "product_size_range": [len(region) - 100,
                                                       len(region) + 100],
                                "tm_range": [50.0, 72.0],
                                "gc_range": [20.0, 80.0]},
                    risk="boundary_offset_5p/3p 会被报告；边界语义由精确变为滑动"))
            log.append({
                "operation": "primer3-attempt",
                "attempt": attempt_name,
                "backend": "primer3-core",
                "parameters": {"tm_range": list(tm_range),
                               "fwd_tail": use_fwd_tail,
                               "rev_tail": use_rev_tail,
                               "slide": use_slide},
            })
            try:
                designed = design_anchored_pairs(
                    probe["path"], region, region_start, target_tm, min_len,
                    max_len, top_n, fwd_tail=use_fwd_tail,
                    rev_tail=use_rev_tail, timeout=timeout, tm_range=tm_range,
                    slide=use_slide)
                fwd = designed["forward_candidates"]
                rev = designed["reverse_candidates"]
                pairs = designed["pairs"]
                last_explain = json_like_explain(designed["explain"])
                log.append({
                    "operation": "primer3-attempt-result",
                    "attempt": attempt_name,
                    "returned_pairs": len(pairs),
                    "explain": designed["explain"],
                })
                if not pairs:
                    continue
                if attempt_name in ("binding-only-retry", "slide-retry"):
                    # Primer3 ranked the binding region alone; reattach the
                    # PCR tails afterward and validate the full oligo.
                    for item in fwd:
                        item["tail"] = fwd_tail
                        item["sequence"] = fwd_tail + item["binding"]
                        item["length"] = len(item["sequence"])
                    for item in rev:
                        item["tail"] = rev_tail
                        item["sequence"] = rev_tail + item["binding"]
                        item["length"] = len(item["sequence"])
                if attempt_name == "binding-only-retry":
                    retry_note = (
                        "primer3_core found no acceptable pair when the "
                        "tails were scored as part of the primer; retried "
                        "binding-only and reattached tails post-design. "
                        "Full-primer structural QC is reported in validation.")
                elif attempt_name == "relaxed-tm-retry":
                    retry_note = (
                        "primer3_core retried with a relaxed 50-72 C Tm "
                        "window because the default +/-5 C window produced "
                        "no acceptable exact-boundary pair. This layer only "
                        "covers Tm out-of-window failures; GC/structural "
                        "failures are handled by slide-retry or user consent.")
                elif attempt_name == "slide-retry":
                    retry_note = (
                        "primer3_core exhausted exact-boundary layers and "
                        "succeeded in slide-retry: forced starts were "
                        "released within min(25, n//4) nt, product window "
                        "was n-100..n+100, Tm window 50-72 C, GC unchanged "
                        "20-80%. boundary_offset_5p/3p report the inward "
                        "shift of each primer 5' end relative to the "
                        "requested amplicon boundary.")
                    slide_offsets = {
                        "boundary_offset_5p": pairs[0]["boundary_offset_5p"],
                        "boundary_offset_3p": pairs[0]["boundary_offset_3p"],
                    }
                for item in fwd + rev:
                    item["_backend"] = "primer3-core"
                    item["_backend_source"] = ("Primer3 Core %s"
                                                % probe.get("version"))
                backend = "primer3-core"
                primer3_succeeded = True
                log.append({"operation": "primer3-attempt-success",
                            "attempt": attempt_name,
                            "retry_note": retry_note})
                break
            except Primer3CoreError as error:
                failure = str(error)
                last_explain = failure
                log.append({"operation": "primer3-attempt-error",
                            "attempt": attempt_name, "error": failure})
                if require_primer3:
                    raise
        if not primer3_succeeded:
            alternatives = _explain_alternatives(
                {"text": last_explain} if last_explain else {})
            failure = (
                "primer3_core returned no acceptable pair after %d "
                "attempt(s) including slide-retry: %s" %
                (len(attempts), last_explain or "no explanation"))
            if require_primer3:
                error = Primer3CoreError(
                    "%s; alternatives=%s" % (failure, alternatives))
                error.alternatives = alternatives
                raise error
            broker.request(make_request(
                "primer3-heuristic-fallback", "degradation",
                "primer3_core 全部重试（含 slide-retry）无解；拟降级为热力学启发式 "
                "扫描，候选会明确标注 NOT Primer3",
                parameters={"primer3_failure": failure,
                            "alternatives": alternatives},
                alternatives=alternatives,
                risk="启发式 Tm/结构评分未经验证，不得声称 Primer3 结果"))
            use_primer3 = False
        elif failure is None:
            failure = None
    if not use_primer3:
        engine = ThermoEngine("heuristic", probe.get("detail") or failure)
        fwd = scan_side(region, target_tm, min_len, max_len, engine, "forward",
                        tail=fwd_tail, product_size=len(region))
        rev = scan_side(str(Seq(region).reverse_complement()), target_tm,
                        min_len, max_len, engine, "reverse", tail=rev_tail,
                        product_size=len(region))
        pairs = build_pairs(fwd, rev, engine, len(region), top_n)
        for item in fwd + rev:
            item["_backend"] = "heuristic"
            item["_backend_source"] = "heuristic scanner; NOT Primer3"
        for candidate in rev:
            candidate["bind_start"] = region_start + len(region) - candidate["binding_length"]
            candidate["bind_end"] = region_start + len(region) - 1
        for candidate in fwd:
            candidate["bind_start"] = region_start
            candidate["bind_end"] = region_start + candidate["binding_length"] - 1
        backend = "heuristic"
        log.append({
            "operation": "heuristic-fallback-executed",
            "backend": "thermodynamic-fallback",
            "candidate_count": {"forward": len(fwd), "reverse": len(rev)},
            "input_sequence_sha256_prefix": sha256_prefix(region),
        })

    for item in fwd + rev:
        mg = 1.5 if item.get("_backend") == "primer3-core" else 0.0
        item["tm_crosscheck"] = primer_tm_crosscheck(
            item.get("binding") or item.get("sequence") or "",
            item.get("tm"), item.get("_backend", backend), mg=mg)

    result = {
        "schema_version": "0.9.0",
        "backend": backend,
        "backend_status": ("available" if use_primer3 else "fallback"),
        "primer3_version": probe.get("version") if use_primer3 else None,
        "primer3_failure": failure,
        "primer3_retry_note": retry_note,
        "alternatives": alternatives,
        "boundary_offsets": slide_offsets,
        "region": {"start": region_start, "end": region_end,
                   "length": len(region)},
        "fwd_tail": fwd_tail,
        "rev_tail": rev_tail,
        "tail_sources": ([RESTRICTION_TAIL_SOURCE]
                         if (fwd_tail or rev_tail) else []),
        "forward_candidates": fwd[:top_n],
        "reverse_candidates": rev[:top_n],
        "pairs": pairs[:top_n],
        "validation": {
            "forward": [_validate_primer(item, "forward", fwd_tail, target_tm)
                        for item in fwd[:top_n]],
            "reverse": [_validate_primer(item, "reverse", rev_tail, target_tm)
                        for item in rev[:top_n]],
        },
        "provenance": [source(
            "software", "SnapGene DNA Design primer_design_engine",
            "primer-design-engine", version=read_version(),
            status="verified" if use_primer3 else "partial",
            verification={"method": "unit-tests", "status": "verified"})],
        "consent": {
            "broker_policy": broker.policy,
            "requests": broker.requests,
            "pending": broker.pending(),
        },
        "operation_log": log.snapshot(),
        "input_sequence": {"sha256_prefix": sha256_prefix(sequence)},
    }
    return result


def best_pair(primer_result):
    if not primer_result.get("pairs"):
        return None
    pair = primer_result["pairs"][0]
    fwd = primer_result["forward_candidates"][pair["forward_index"]]
    rev = primer_result["reverse_candidates"][pair["reverse_index"]]
    return {"forward": fwd, "reverse": rev, "pair": pair}


if __name__ == "__main__":
    print("primer_design_engine module (use plan_assembly.py or design_primers.py)")
    sys.exit(0)
