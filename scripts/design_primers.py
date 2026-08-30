# -*- coding: utf-8 -*-
"""design_primers.py - Primer design with candidate ranking (v0.7.0-dev).

Designs forward/reverse primers for a target region on a template and
returns the **top ``--top-n`` candidate pairs** (default 5). Every candidate
reports:

    binding          the PCR annealing region (3' part)
    5' tail/overlap  restriction-site tail (PCR mode) or Gibson overlap
                     tail (--gibson mode)
    sequence         the full primer (tail + binding)
    tm / gc          computed on the BINDING region only (PCR annealing
                     parameters)
    hairpin / self_dimer / heterodimer
                     structural checks on the FULL primer sequence
    end_stability_3p 3' end stability of the binding region
    product_size     expected amplicon length
    penalties        human-readable reasons for score deductions
    recommended      high / medium / low

Optional Primer3 integration (primer3_core)
--------------------------------------------
The real Primer3 design engine runs as an external ``primer3_core`` process.
This program never imports primer3-py's native extension, so a native crash
cannot terminate the DNA-design tool.  When no external engine is available,
the tool can either use a clearly labelled heuristic fallback (default) or
fail closed with ``--require-primer3``.

Gibson mode sends the 5' tails as Primer3 overhangs.  Primer3 therefore
calculates annealing Tm/GC from the 3' binding region while checking secondary
structure on the complete tailed oligo, matching Primer3 2.6.x semantics.
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Bio.Seq import Seq
from Bio.SeqUtils import MeltingTemp as mt

from primer3_core_backend import (Primer3CoreError, design_anchored_pairs,
                                  probe_primer3_core)
from operation_consent import (
    ConsentBroker, ConsentRequiredError, TransparencyLog, make_request,
    sha256_prefix,
)
from primer_qc import analyze_primers, flag_risks, score_hairpin, score_pair_dimer, score_self_dimer
from sg_common import gc_percent, jprint, load_seq, normalize_dna

sg_normalize = normalize_dna  # local alias used by the Gibson primer builder

# Minimal common 5' protective-base table used by the legacy CLI. NEB's
# 'Cleavage Close to the End of DNA Fragments' guidance adds 4 more bases
# when these flanks are used for PCR primers; consult the current NEB
# table before claiming optimal cleavage.
PROTECTIVE_BASES = {
    "EcoRI": "G", "BamHI": "GG", "HindIII": "AA", "XbaI": "T",
    "SalI": "G", "PstI": "G", "NdeI": "G", "NcoI": "C",
    "KpnI": "GGTAC", "SacI": "G", "SmaI": "G", "XhoI": "T",
    "SpeI": "T", "NotI": "GC", "AgeI": "C", "BglII": "G",
    "PvuII": "C", "SphI": "G", "EcoRV": "G", "SacII": "CC",
    "MfeI": "G", "AvrII": "G", "BsaI": "GG", "BbsI": "GA",
    "BsmBI": "C", "HpaI": "G", "ClaI": "A", "SapI": "G",
}

# Recognition sequences for the same enzymes (5'->3').
SITE_SEQS = {
    "EcoRI": "GAATTC", "BamHI": "GGATCC", "HindIII": "AAGCTT",
    "XbaI": "TCTAGA", "SalI": "GTCGAC", "PstI": "CTGCAG",
    "NdeI": "CATATG", "NcoI": "CCATGG", "KpnI": "GGTACC",
    "SacI": "GAGCTC", "SmaI": "CCCGGG", "XhoI": "CTCGAG",
    "SpeI": "ACTAGT", "NotI": "GCGGCCGC", "AgeI": "ACCGGT",
    "BglII": "AGATCT", "PvuII": "CAGCTG", "SphI": "GCATGC",
    "EcoRV": "GATATC", "SacII": "CCGCGG", "MfeI": "CAATTG",
    "AvrII": "CCTAGG", "BsaI": "GGTCTC", "BbsI": "GAAGAC",
    "BsmBI": "CGTCTC", "HpaI": "GTTAAC", "ClaI": "ATCGAT",
    "SapI": "GCTCTTC",
}

# Penalty thresholds for heuristic structural scores (primer_qc units).
HAIRPIN_STRONG = 40
DIMER_STRONG = 40
HAIRPIN_MODERATE = 20
DIMER_MODERATE = 20
GC_OK_MIN = 40.0
GC_OK_MAX = 60.0
TM_TOLERANCE = 2.0


# ---------------------------------------------------------------------------
# Backward-compatible helper (used by design_gene_replacement.py)
# ---------------------------------------------------------------------------

def best_primer(template, target_tm, min_len, max_len, gc_clamp=True):
    """Backward-compatible single-best primer picker.

    Returns (score, sequence, tm, gc, offset) like the v0.6 picker, or None
    when no candidate fits. Uses the same ranking as the candidate scan.
    """
    # Backward-compatible helper remains deterministic and cannot import a
    # native extension. The CLI's real Primer3 path uses primer3_core below.
    engine = ThermoEngine("heuristic", "legacy helper")
    candidates = scan_side(str(template).upper(), target_tm, min_len,
                           max_len, engine, "fwd")
    if not candidates:
        return None
    best = candidates[0]
    return (0, best["binding"], best["tm"], best["gc"], 0)


# ---------------------------------------------------------------------------
# Primer3-backed and heuristic calculators
# ---------------------------------------------------------------------------

class ThermoEngine:
    """Deterministic heuristic fallback used only when Primer3 is not used."""

    def __init__(self, status="heuristic", detail=None):
        self.status = status
        self.detail = detail

    @property
    def available(self):
        return False

    def tm(self, binding):
        return round(float(mt.Tm_NN(str(binding))), 1)

    def hairpin(self, full):
        score, stem, loop, _s, _e = score_hairpin(str(full))
        return {"score": score, "stem": stem, "loop": loop,
                "structure": None, "source": "heuristic"}

    def self_dimer(self, full):
        score, length, _a, _b = score_self_dimer(str(full))
        return {"score": score, "length": length, "structure": None,
                "source": "heuristic"}

    def heterodimer(self, fwd_full, rev_full):
        score, length, _f, _r = score_pair_dimer(str(fwd_full), str(rev_full))
        return {"score": score, "length": length, "structure": None,
                "source": "heuristic"}

    def end_stability_3p(self, binding):
        """3' end stability of the binding region (more negative dG = the 3'
        end is more prone to form secondary structure / mispriming)."""
        window = str(binding)[-5:]
        gc_count = sum(1 for base in window if base in "GC")
        return {"dg": None, "gc_anchor_5bp": gc_count, "source": "heuristic"}


# ---------------------------------------------------------------------------
# Candidate scanning and scoring
# ---------------------------------------------------------------------------

def _binding_penalties(binding, tm, target_tm, min_len, max_len, engine):
    penalties = []
    deviation = abs(tm - target_tm)
    if deviation > TM_TOLERANCE:
        penalties.append("Tm deviates %.1f degC from target %.1f"
                         % (deviation, target_tm))
    gc = gc_percent(binding)
    if gc < GC_OK_MIN or gc > GC_OK_MAX:
        penalties.append("GC content %.1f%% outside 40-60%%" % gc)
    if binding[-1] not in "GC":
        penalties.append("3' end lacks GC clamp")
    if len(binding) < min_len:
        penalties.append("shorter than min length %d" % min_len)
    if len(binding) > max_len:
        penalties.append("longer than max length %d" % max_len)
    stability = engine.end_stability_3p(binding)
    if stability["gc_anchor_5bp"] <= 1:
        penalties.append("weak 3' GC anchor (%d GC in last 5 bp)"
                         % stability["gc_anchor_5bp"])
    return penalties


def _structure_penalties(hairpin, self_dimer):
    penalties = []
    strong = False
    if hairpin["score"] >= HAIRPIN_STRONG:
        penalties.append("strong hairpin (stem %d, loop %d)"
                         % (hairpin.get("stem", 0), hairpin.get("loop", 0)))
        strong = True
    elif hairpin["score"] >= HAIRPIN_MODERATE:
        penalties.append("moderate hairpin (score %d)" % hairpin["score"])
    if self_dimer["score"] >= DIMER_STRONG:
        penalties.append("self-dimer (%d bp)" % self_dimer.get("length", 0))
        strong = True
    elif self_dimer["score"] >= DIMER_MODERATE:
        penalties.append("moderate self-dimer (score %d)"
                         % self_dimer["score"])
    return penalties, strong


def _heterodimer_penalties(heterodimer):
    penalties = []
    strong = False
    if heterodimer["score"] >= DIMER_STRONG:
        penalties.append("cross-dimer (%d bp)" % heterodimer.get("length", 0))
        strong = True
    elif heterodimer["score"] >= DIMER_MODERATE:
        penalties.append("moderate cross-dimer (score %d)"
                         % heterodimer["score"])
    return penalties, strong


def _recommendation(penalties, binding_penalties, structural_strong):
    """Map a candidate's penalty list to a recommendation level."""
    weight = 0.0
    for penalty in binding_penalties:
        if penalty.startswith("Tm deviates"):
            weight += 1.0
        elif penalty.startswith("GC content"):
            weight += 1.0
        elif penalty.startswith("3' end lacks"):
            weight += 1.0
        elif penalty.startswith("strong 3' end") or penalty.startswith("weak 3' GC"):
            weight += 1.0
        else:
            weight += 0.5
    if structural_strong:
        return "low"
    if weight <= 1.0:
        return "high"
    if weight <= 3.0:
        return "medium"
    return "low"


def scan_side(sequence, target_tm, min_len, max_len, engine, side,
              tail="", product_size=None):
    """Scan anchor-fixed candidate windows for one primer side.

    Forward: windows start at the region start (bind_start = region start).
    Reverse: the sequence passed in is the region's reverse complement, so
    candidates are anchored to its start (which maps to the region end).

    Returns a list of candidate dicts sorted by ascending penalty weight.
    """
    candidates = []
    for length in range(min_len, max_len + 1):
        if length > len(sequence):
            continue
        binding = sequence[:length]
        full = tail + binding
        tm = engine.tm(binding)
        binding_penalties = _binding_penalties(
            binding, tm, target_tm, min_len, max_len, engine)
        hairpin = engine.hairpin(full)
        self_dimer = engine.self_dimer(full)
        struct_penalties, strong = _structure_penalties(hairpin, self_dimer)
        all_penalties = binding_penalties + struct_penalties
        candidates.append({
            "side": side,
            "binding": binding,
            "tail": tail,
            "sequence": full,
            "tm": tm,
            "gc": round(gc_percent(binding), 1),
            "length": len(full),
            "binding_length": len(binding),
            "hairpin": hairpin,
            "self_dimer": self_dimer,
            "heterodimer": None,  # filled at pair level
            "end_stability_3p": engine.end_stability_3p(binding),
            "product_size": product_size,
            "penalties": all_penalties,
            "recommended": _recommendation(all_penalties, binding_penalties,
                                           strong),
        })
    # Sort by a simple weight so the best candidates come first.
    def weight(candidate):
        base = 0.0
        for penalty in candidate["penalties"]:
            if "strong" in penalty or "hairpin dG" in penalty or \
                    "self-dimer dG" in penalty or "cross-dimer" in penalty:
                base += 5.0
            elif "moderate" in penalty:
                base += 2.0
            else:
                base += 1.0
        return base
    candidates.sort(key=weight)
    return candidates


def build_pairs(fwd_candidates, rev_candidates, engine, product_size, top_n):
    """Pair forward/reverse candidates, score cross-dimers, rank and cut."""
    pairs = []
    for fwd in fwd_candidates:
        for rev in rev_candidates:
            heterodimer = engine.heterodimer(fwd["sequence"], rev["sequence"])
            penalties, strong = _heterodimer_penalties(heterodimer)
            combined = list(fwd["penalties"]) + list(rev["penalties"]) + penalties
            weight = 0.0
            for penalty in combined:
                if "strong" in penalty or "dG=" in penalty:
                    weight += 5.0
                elif "moderate" in penalty:
                    weight += 2.0
                else:
                    weight += 1.0
            pairs.append({
                "forward_index": fwd_candidates.index(fwd),
                "reverse_index": rev_candidates.index(rev),
                "product_size": product_size,
                "heterodimer": heterodimer,
                "penalties": penalties,
                "combined_penalties": combined,
                "weight": weight,
                "recommended": ("low" if strong else
                                "high" if weight <= 2.0 else
                                "medium" if weight <= 5.0 else "low"),
            })
    pairs.sort(key=lambda pair: pair["weight"])
    return pairs[:top_n]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Design primers for a template region")
    p.add_argument("source")
    p.add_argument("--start", type=int, default=1, help="region start (1-based, default 1)")
    p.add_argument("--end", type=int, default=None, help="region end (1-based, default = full length)")
    p.add_argument("--target-tm", type=float, default=60.0)
    p.add_argument("--min-len", type=int, default=18)
    p.add_argument("--max-len", type=int, default=30)
    p.add_argument("--top-n", type=int, default=5,
                   help="number of candidate pairs to report (default 5)")
    p.add_argument("--add-site", action="append", default=[],
                   help="restriction enzyme site(s) appended to BOTH primers (shortcut)")
    p.add_argument("--fwd-site", action="append", default=[],
                   help="restriction enzyme site(s) appended to the forward primer only")
    p.add_argument("--rev-site", action="append", default=[],
                   help="restriction enzyme site(s) appended to the reverse primer only")
    p.add_argument("--gibson", action="store_true",
                   help="Gibson primer mode: separate 5' overlap tail and 3' binding region")
    p.add_argument("--fwd-overlap", default="",
                   help="Gibson: overlap tail of the forward primer (matches the "
                        "upstream fragment end in the final product)")
    p.add_argument("--rev-overlap", default="",
                   help="Gibson: overlap between this fragment and the downstream "
                         "fragment in the final product; the reverse primer carries "
                         "its reverse complement")
    p.add_argument("--engine", choices=("auto", "primer3-core", "heuristic"),
                   default="auto",
                   help="design engine: auto prefers primer3_core; heuristic "
                        "is an explicitly unverified fallback")
    p.add_argument("--primer3-core", default=None,
                   help="path to an external primer3_core executable; may also "
                        "be set with the PRIMER3_CORE environment variable")
    p.add_argument("--require-primer3", action="store_true",
                   help="fail instead of using heuristic design when a real "
                        "primer3_core engine is unavailable or fails")
    p.add_argument("--primer3-timeout", type=int, default=30,
                   help="maximum seconds for one primer3_core design call")
    p.add_argument("--json", action="store_true")
    p.add_argument("--consent", choices=("ask", "auto"),
                   default=("ask" if sys.stdin.isatty() else "auto"),
                   help="ask: interactive confirmation for relaxations/"
                        "degradations (no confirmation = no execution); "
                        "auto: explicit non-interactive auto-confirm and "
                        "record every decision")
    p.add_argument("--yes", action="store_true",
                   help="approve every pending consent request")
    p.add_argument("--primer-role", choices=("assembly", "validation"),
                   default="assembly",
                   help="validation primers require an explicit user request")
    p.add_argument("--user-requested-design", action="store_true",
                   help="record that the user explicitly asked to design new "
                        "validation primers; --yes/auto-consent do not replace it")
    p.add_argument("--user-rules-dir", default=str(ROOT / "user_rules"))
    p.add_argument("--project-id")
    args = p.parse_args()

    if args.primer_role == "validation" and not args.user_requested_design:
        from agent.rule_capture import evaluate_experience, load_preloaded_experience
        from rules.experience import ExperienceRuleStore
        from sg_common import jfail
        experience = evaluate_experience(
            "before_validation_primer_design",
            {"primer": {"role": "validation", "request_explicit": False,
                        "user_supplied": False}},
            ExperienceRuleStore(args.user_rules_dir),
            project_id=args.project_id,
            preloaded_rules=load_preloaded_experience(
                ROOT / "rules" / "preloaded_experience_rules.json"))
        confirmation_hits = [
            hit for hit in experience["hits"]
            if hit.get("action", {}).get("type") in
            ("ask", "warn_and_confirm", "block")
        ]
        if confirmation_hits:
            jfail(
                "VALIDATION_PRIMER_CONFIRMATION_REQUIRED",
                "validation primers must not be designed until the user explicitly "
                "states that new primers should be designed",
                details={"experience_rules": experience,
                         "required_next_step":
                         "ask whether the user already has validation primers; "
                         "rerun with --user-requested-design only after yes"})

    if args.top_n < 1:
        raise SystemExit("invalid --top-n %d (must be >= 1)" % args.top_n)
    if args.min_len < 1 or args.max_len < args.min_len:
        raise SystemExit("invalid primer lengths: min=%d max=%d" % (
            args.min_len, args.max_len))
    if args.primer3_timeout < 1:
        raise SystemExit("invalid --primer3-timeout %d (must be >= 1)" %
                         args.primer3_timeout)

    def _interactive_confirm(request):
        print("[需要确认] %s (%s)" % (request["operation"],
                                      request["category"]))
        print("  说明：%s" % request["description"])
        for index, alternative in enumerate(request.get("alternatives", []), 1):
            print("  替代方案 %d：%s" % (index, alternative.get("action", "")))
        try:
            answer = input("是否继续？[y/N] ").strip().lower()
        except EOFError:
            raise ConsentRequiredError(request)
        return answer in ("y", "yes")

    if args.consent == "auto":
        broker = ConsentBroker(policy="auto")
    elif args.yes:
        broker = ConsentBroker(policy="ask",
                               confirm_callback=lambda request: True)
    else:
        broker = ConsentBroker(policy="ask",
                               confirm_callback=_interactive_confirm)


    def _consent(request):
        try:
            return broker.request(request)
        except ConsentRequiredError as error:
            from sg_common import jfail
            jfail("CONSENT_REQUIRED",
                  "an abnormal operation needs confirmation and was not "
                  "confirmed; nothing was executed",
                  details={"pending_request": error.request})

    core_info = probe_primer3_core(args.primer3_core)
    if args.engine == "heuristic":
        core_info = dict(core_info)
        core_info["status"] = "disabled"
        core_info["detail"] = "real Primer3 was explicitly disabled with --engine heuristic"
    use_primer3 = (args.engine != "heuristic" and
                   core_info["status"] == "available")
    if args.engine == "primer3-core" and not use_primer3:
        args.require_primer3 = True
    if args.require_primer3 and not use_primer3:
        from sg_common import jfail
        jfail("PRIMER3_REQUIRED",
              "a real primer3_core engine is required but unavailable",
              details={"engine": core_info})

    # The fallback engine is deliberately heuristic-only. No native Python
    # extension is imported into the main process.
    engine = ThermoEngine("heuristic", core_info.get("detail"))

    record, _fmt = load_seq(args.source)
    seq = str(record.seq)
    end = args.end if args.end else len(seq)
    if not (1 <= args.start <= end <= len(seq)):
        raise SystemExit("invalid region: start=%d end=%d len=%d" % (args.start, end, len(seq)))

    if args.gibson:
        fwd_overlap = sg_normalize(args.fwd_overlap, "forward overlap")
        rev_overlap = sg_normalize(args.rev_overlap, "reverse overlap")
        if not fwd_overlap or not rev_overlap:
            raise SystemExit(
                "gibson mode requires --fwd-overlap and --rev-overlap "
                "(the homology arms of the adjacent fragments)")
        rev_overlap_tail = str(Seq(rev_overlap).reverse_complement())
    else:
        fwd_overlap = rev_overlap = rev_overlap_tail = ""

    fwd_sites = list(args.add_site) + list(args.fwd_site)
    rev_sites = list(args.add_site) + list(args.rev_site)

    def with_sites(primer_seq, sites):
        extra = ""
        for s in sites:
            sname = s.strip()
            site_key = next((k for k in SITE_SEQS if k.lower() == sname.lower()), None)
            if not site_key:
                raise SystemExit("unknown site: %s" % s)
            site_seq = SITE_SEQS[site_key]
            prot = PROTECTIVE_BASES.get(site_key, "G")
            extra += prot + site_seq
        return extra + primer_seq

    region = seq[args.start - 1: end]
    fwd_tail = with_sites(fwd_overlap, fwd_sites)
    rev_tail = with_sites(rev_overlap_tail, rev_sites)
    product_size = end - args.start + 1

    operation_log = broker.log
    operation_log.append({
        "operation": "primer-design-start",
        "backend": "primer3-core-or-heuristic",
        "parameters": {"region_1based": [args.start, end],
                       "target_tm": args.target_tm,
                       "min_len": args.min_len, "max_len": args.max_len,
                       "fwd_tail": fwd_tail, "rev_tail": rev_tail},
        "input_sequence_sha256_prefix": sha256_prefix(seq),
    })
    _consent(make_request(
        "primer-design-parameters", "parameter-confirmation",
        "确认引物设计参数窗口（Tm/GC/长度/后端策略）后执行",
        parameters={"target_tm": args.target_tm,
                    "tm_window": [max(0.0, args.target_tm - 5.0),
                                  args.target_tm + 5.0],
                    "gc_range": [20.0, 80.0],
                    "length_range": [args.min_len, args.max_len],
                    "backend_preference": args.engine}))

    # Reverse candidates are scanned on the region's reverse complement.
    rev_region = str(Seq(region).reverse_complement())

    primer3_explain = None
    primer3_failure = None
    primer3_retry_note = None
    alternatives = []
    slide_offsets = None
    if use_primer3:
        attempts = []
        if fwd_tail or rev_tail:
            attempts.append(("tailed", fwd_tail, rev_tail,
                             (args.target_tm - 5.0, args.target_tm + 5.0),
                             False))
            attempts.append(("binding-only-retry", "", "",
                             (args.target_tm - 5.0, args.target_tm + 5.0),
                             False))
        else:
            attempts.append(("tailed", "", "",
                             (args.target_tm - 5.0, args.target_tm + 5.0),
                             False))
        attempts.append(("relaxed-tm-retry", "", "", (50.0, 72.0), False))
        attempts.append(("slide-retry", "", "", (50.0, 72.0), True))
        last_explain = ""
        primer3_succeeded = False
        for attempt_name, use_fwd_tail, use_rev_tail, tm_range, use_slide in attempts:
            if use_slide:
                _consent(make_request(
                    "slide-retry", "relaxation",
                    "精确边界/Tm 重试无解；拟释放 Primer3 强制起点，允许引物 5' "
                    "端在 0..min(25, len/4) nt 内滑动，产物窗口 n-100..n+100，"
                    "Tm 50-72 C，GC 保持 20-80%",
                    parameters={"slide_budget": min(25, max(0, len(region) // 4)),
                                "product_size_range": [len(region) - 100,
                                                       len(region) + 100]},
                    risk="边界偏移会被写入 boundary_offset_5p/3p"))
            operation_log.append({
                "operation": "primer3-attempt", "attempt": attempt_name,
                "backend": "primer3-core",
                "parameters": {"tm_range": list(tm_range),
                               "fwd_tail": use_fwd_tail,
                               "rev_tail": use_rev_tail, "slide": use_slide},
            })
            try:
                designed = design_anchored_pairs(
                    core_info["path"], region, args.start - 1, args.target_tm,
                    args.min_len, args.max_len, args.top_n,
                    fwd_tail=use_fwd_tail, rev_tail=use_rev_tail,
                    timeout=args.primer3_timeout, tm_range=tm_range,
                    slide=use_slide)
                fwd_candidates = designed["forward_candidates"]
                rev_candidates = designed["reverse_candidates"]
                pairs = designed["pairs"]
                primer3_explain = designed["explain"]
                last_explain = "; ".join(
                    "%s=%s" % (key, value)
                    for key, value in primer3_explain.items() if value)
                operation_log.append({
                    "operation": "primer3-attempt-result",
                    "attempt": attempt_name, "returned_pairs": len(pairs),
                    "explain": primer3_explain})
                if not pairs:
                    continue
                if attempt_name in ("binding-only-retry", "slide-retry"):
                    for item in fwd_candidates:
                        item["tail"] = fwd_tail
                        item["sequence"] = fwd_tail + item["binding"]
                        item["length"] = len(item["sequence"])
                    for item in rev_candidates:
                        item["tail"] = rev_tail
                        item["sequence"] = rev_tail + item["binding"]
                        item["length"] = len(item["sequence"])
                if attempt_name == "binding-only-retry":
                    primer3_retry_note = (
                        "primer3_core 尾巴参与评分时无解，binding-only 重试后"
                        "重新接尾巴；完整引物结构 QC 见 validation")
                elif attempt_name == "relaxed-tm-retry":
                    primer3_retry_note = (
                        "relaxed-tm-retry: Tm 窗口放宽为 50-72 C；仅覆盖 Tm "
                        "超窗失败，GC 失败由 slide-retry 或用户同意处理")
                elif attempt_name == "slide-retry":
                    primer3_retry_note = "slide-retry"
                    slide_offsets = {
                        "boundary_offset_5p": pairs[0].get("boundary_offset_5p"),
                        "boundary_offset_3p": pairs[0].get("boundary_offset_3p"),
                    }
                primer3_succeeded = True
                break
            except Primer3CoreError as error:
                primer3_failure = str(error)
                last_explain = primer3_failure
                operation_log.append({"operation": "primer3-attempt-error",
                                      "attempt": attempt_name,
                                      "error": primer3_failure})
                if args.require_primer3:
                    from sg_common import jfail
                    jfail("PRIMER3_EXECUTION_FAILED",
                          "the required primer3_core design call failed",
                          details={"engine": core_info,
                                   "primer3_error": primer3_failure})
        if not primer3_succeeded:
            alternatives = [{
                "code": "EXTEND_FLANK_OUTSIDE_AMPLICON",
                "action": ("扩增子 5' 端外扩 20-40 bp 后重新设计，或改用内部引物对；"
                           "纯 poly-G/C 端部建议替换目标边界或人工合成侧翼")}]
            primer3_failure = (
                "primer3_core returned no acceptable pair after all retries "
                "including slide-retry: %s" % (last_explain or "no explanation"))
            if args.require_primer3:
                from sg_common import jfail
                jfail("PRIMER3_NO_CANDIDATES",
                      "Primer3 found no acceptable primer pair",
                      details={"engine": core_info,
                               "primer3_explain": primer3_explain,
                               "alternatives": alternatives,
                               "primer3_failure": primer3_failure})
            _consent(make_request(
                "primer3-heuristic-fallback", "degradation",
                "primer3_core 全部重试（含 slide-retry）无解；拟降级为热力学启发式 "
                "扫描，候选将标注 NOT Primer3",
                parameters={"primer3_failure": primer3_failure,
                            "alternatives": alternatives},
                alternatives=alternatives,
                risk="启发式结果未经 Primer3 验证"))
            use_primer3 = False
    elif not args.require_primer3:
        _consent(make_request(
            "primer3-unavailable-fallback", "degradation",
            "primer3_core 不可用；拟降级为热力学启发式扫描（NOT Primer3 标注）",
            parameters={"probe": core_info},
            alternatives=[{
                "code": "INSTALL_PRIMER3_OR_SET_PRIMER3_CORE",
                "action": "安装 primer3_core 或设置 PRIMER3_CORE 后重试"}]))
        operation_log.append({
            "operation": "backend-probe", "backend": "primer3-core",
            "status": core_info["status"], "detail": core_info.get("detail")})

    if not use_primer3:
        fwd_candidates = scan_side(
            region, args.target_tm, args.min_len, args.max_len, engine,
            "forward", tail=fwd_tail, product_size=product_size)
        rev_candidates = scan_side(
            rev_region, args.target_tm, args.min_len, args.max_len, engine,
            "reverse", tail=rev_tail, product_size=product_size)
        pairs = build_pairs(fwd_candidates, rev_candidates, engine,
                            product_size, args.top_n)

    # Map candidate indices back to template coordinates (0-based fields were
    # used internally; legacy output keeps the original 1-based contract).
    for candidate in fwd_candidates:
        offset = candidate.get("boundary_offset") or 0
        candidate["bind_start"] = args.start + offset
        candidate["bind_end"] = (args.start + offset +
                                 candidate["binding_length"] - 1)
    for candidate in rev_candidates:
        offset = candidate.get("boundary_offset") or 0
        binding_len = candidate["binding_length"]
        five_prime_1based = args.start + len(region) - 1 - offset
        candidate["bind_start"] = five_prime_1based - binding_len + 1
        candidate["bind_end"] = five_prime_1based

    # Backward-compatible overlap fields (v0.6 output contract).
    for candidate in fwd_candidates:
        candidate["overlap"] = fwd_overlap
        candidate["overlap_length"] = len(fwd_overlap)
    for candidate in rev_candidates:
        candidate["overlap"] = rev_overlap
        candidate["overlap_tail"] = rev_overlap_tail
        candidate["overlap_length"] = len(rev_overlap)

    warnings = []
    if not use_primer3:
        warnings.append(
            "Primer3 design was NOT used; candidates and structural scores "
            "are heuristic and Tm uses Biopython MeltingTemp. Do not claim "
            "Primer3 design or verification.")
        if core_info.get("detail"):
            warnings.append("primer3_core detail: %s" % core_info["detail"])
        if primer3_failure:
            warnings.append("primer3_core execution failed: %s" %
                            primer3_failure)
    else:
        warnings.append(
            "Primer3 selected and ranked these primer pairs. "
            "Recommendation labels reflect Primer3 rank only; they do not "
            "predict wet-lab success or check genome-wide specificity.")
        if primer3_retry_note:
            warnings.append("primer3_retry_note: %s" % primer3_retry_note)
        if slide_offsets:
            warnings.append(
                "slide-retry boundary offsets: 5p=%s nt, 3p=%s nt"
                % (slide_offsets["boundary_offset_5p"],
                   slide_offsets["boundary_offset_3p"]))
    if len(fwd_candidates) < args.top_n:
        warnings.append(
            "only %d forward candidate(s) found (requested %d)"
            % (len(fwd_candidates), args.top_n))
    if len(rev_candidates) < args.top_n:
        warnings.append(
            "only %d reverse candidate(s) found (requested %d)"
            % (len(rev_candidates), args.top_n))

    if not fwd_candidates or not rev_candidates:
        jfail_candidates = {
            "template": record.name or record.id,
            "method": "gibson" if args.gibson else "pcr",
            "primer3_status": "available" if use_primer3 else "unavailable",
            "primer3_detail": core_info.get("detail"),
            "design_engine": {
                "requested": args.engine,
                "selected": "primer3-core" if use_primer3 else "heuristic",
                "status": "available" if use_primer3 else "fallback",
                "version": core_info.get("version") if use_primer3 else None,
                "verification": ("real-external-engine" if use_primer3 else
                                 "unverified-heuristic"),
            },
            "warnings": warnings,
            "forward_candidates": fwd_candidates,
            "reverse_candidates": rev_candidates,
            "pairs": [],
            "reason": "no primer candidate(s) fit the requested region "
                      "(region length %d, min_len %d)" % (len(region), args.min_len),
        }
        from sg_common import jfail
        jfail("NO_PRIMER_CANDIDATES", jfail_candidates["reason"],
              details=jfail_candidates)

    best_fwd = fwd_candidates[0]
    best_rev = rev_candidates[0]

    result = {
        "template": record.name or record.id,
        "method": "gibson" if args.gibson else "pcr",
        "primer3_status": "available" if use_primer3 else "unavailable",
        "primer3_detail": core_info.get("detail"),
        "primer3_note": (
            "Primer3 Core %s selected and ranked the primer pairs in an "
            "isolated process." % core_info.get("version") if use_primer3 else
            "Primer3 Core was not used; design and structural scores are "
            "heuristic. No Primer3 design or verification is claimed."),
        "design_engine": {
            "requested": args.engine,
            "selected": "primer3-core" if use_primer3 else "heuristic",
            "status": "available" if use_primer3 else "fallback",
            "version": core_info.get("version") if use_primer3 else None,
            "verification": ("real-external-engine" if use_primer3 else
                             "unverified-heuristic"),
            "failure": primer3_failure,
        },
        "region": {"start": args.start, "end": end, "length": product_size},
        "product_size": product_size,
        "top_n": args.top_n,
        "candidate_count": {"forward": len(fwd_candidates),
                            "reverse": len(rev_candidates)},
        "added_sites": {"forward": fwd_sites, "reverse": rev_sites},
        "forward_candidates": fwd_candidates,
        "reverse_candidates": rev_candidates,
        "pairs": pairs,
        "primer3_explain": primer3_explain,
        "primer3_retry_note": primer3_retry_note,
        "alternatives": alternatives,
        "boundary_offsets": slide_offsets,
        "warnings": warnings,
        "consent": {
            "broker_policy": broker.policy,
            "requests": broker.requests,
            "pending": broker.pending(),
        },
        "operation_log": broker.log.snapshot(),
        "input_sequence": {"sha256_prefix": sha256_prefix(seq)},
    }
    if args.gibson:
        result["overlaps"] = {"forward_tail": fwd_overlap,
                              "reverse_tail": rev_overlap,
                              "reverse_primer_tail": rev_overlap_tail}

    # Backward-compatible best-candidate fields.
    result["forward"] = best_fwd
    result["reverse"] = best_rev

    if args.json:
        # Legacy QC object (full-primer structural check) for compatibility.
        qc = analyze_primers(best_fwd["sequence"], best_rev["sequence"])
        result["quality"] = flag_risks(qc)
        result["quality"]["source"] = "legacy-heuristic"
        result["quality"]["note"] = (
            "Backward-compatible summary only; use candidate Primer3 metrics "
            "when design_engine.selected is primer3-core.")
        jprint(result)
    else:
        print("template: %s  region %d..%d  product=%dbp  engine=%s" % (
            result["template"], args.start, end, result["product_size"],
            result["design_engine"]["selected"]))
        print("top %d candidate pair(s):" % len(pairs))
        for idx, pair in enumerate(pairs, 1):
            fwd = fwd_candidates[pair["forward_index"]]
            rev = rev_candidates[pair["reverse_index"]]
            print("  #%d %s (recommended=%s)" % (
                idx, pair["recommended"].upper(), pair["recommended"]))
            for side, candidate in (("fwd", fwd), ("rev", rev)):
                print("    %s: %s  [binding %s | tail %s | Tm=%s GC=%s%% len=%d binds~%d]"
                      % (side, candidate["sequence"], candidate["binding"],
                         candidate["tail"] or "-", candidate["tm"],
                         candidate["gc"], candidate["length"],
                         candidate.get("bind_start")))
                print("        hairpin=%s self-dimer=%s 3'stability=%s"
                      % (candidate["hairpin"].get("score", candidate["hairpin"].get("dg")),
                         candidate["self_dimer"].get("score", candidate["self_dimer"].get("dg")),
                         candidate["end_stability_3p"]))
                if candidate["penalties"]:
                    print("        penalties: %s" % "; ".join(candidate["penalties"]))
            if pair["penalties"]:
                print("    cross-dimer penalties: %s" % "; ".join(pair["penalties"]))
        for warning in warnings:
            print("WARNING: %s" % warning)


if __name__ == "__main__":
    main()
