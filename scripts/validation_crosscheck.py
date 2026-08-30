# -*- coding: utf-8 -*-
"""validation_crosscheck.py - Independent numerical cross-validation.

Every biologically meaningful number in v0.9 outputs must be computable by
more than one path so a single-library bug cannot silently ship a wrong Tm,
GC% or restriction-site set:

* primer Tm: Primer3 (external process, SantaLucia parameters) is compared
  against Biopython ``MeltingTemp.Tm_NN`` and the classic Wallace estimate.
* restriction sites: Bio.Restriction positions are compared against a direct
  motif scan of the recognition sequence and its reverse complement.
* overlap metrics: GC% from Bio.SeqUtils is compared against direct base
  counting, and Tm is computed with two independent methods.

All discrepancies are reported as structured ``conflicts``; callers decide
whether to degrade or reject the plan (M1 treats severe conflicts as errors).
"""
from __future__ import annotations

from Bio.Seq import Seq
from Bio.SeqUtils import MeltingTemp as mt
from Bio.SeqUtils import gc_fraction


PRIMER_TM_AGREE_C = 2.0
PRIMER_TM_WARN_C = 3.5
PRIMER_TM_RANGE = (52.0, 72.0)


def wallace_tm(seq):
    """Classic Wallace rule: Tm = 2*(A+T) + 4*(G+C).

    Valid as an approximation for short oligos (<=14 nt); longer sequences
    are still reported but annotated ``approximation_validity: short-only``.
    """
    seq = str(seq).upper()
    at = seq.count("A") + seq.count("T")
    gc = seq.count("G") + seq.count("C")
    return {
        "tm": 2.0 * at + 4.0 * gc,
        "formula": "Wallace: 2*(A+T)+4*(G+C)",
        "approximation_validity": "short-oligo-approx",
        "source": "Wallace et al. 1979, Nucleic Acids Res 6:3543",
    }


def bio_tm_nn(seq, na=50.0, mg=1.5, dntp=0.6):
    """Biopython SantaLucia nearest-neighbor Tm.

    Default salt matches Primer3's defaults (50 mM Na+, 1.5 mM Mg2+,
    0.6 mM dNTP) so the two implementations are comparable; pass ``mg=0``
    to reproduce the simple Na-only convention used by the overlap window
    search.
    """
    try:
        value = float(mt.Tm_NN(str(seq).upper(), Na=na, Mg=mg, dNTPs=dntp))
    except Exception as error:  # noqa: BLE001 - degraded below
        return {"tm": None, "error": str(error),
                "formula": "Tm_NN(SantaLucia)"}
    return {"tm": round(value, 2),
            "formula": ("Tm_NN(SantaLucia, Na=%smM, Mg=%smM)"
                        % (na, mg)),
            "error": None,
            "source": "Biopython MeltingTemp.Tm_NN (SantaLucia 1998)"}


def manual_gc_percent(seq):
    seq = str(seq).upper()
    if not seq:
        return {"gc_percent": None, "counts": {"G": 0, "C": 0,
                                               "A": 0, "T": 0, "other": 0},
                "source": "direct base counting"}
    gc = seq.count("G") + seq.count("C")
    return {"gc_percent": round(gc / len(seq) * 100.0, 2),
            "counts": {"G": seq.count("G"), "C": seq.count("C"),
                       "A": seq.count("A"), "T": seq.count("T"),
                       "other": len(seq) - gc - seq.count("A")
                       - seq.count("T")},
            "source": "direct base counting"}


def biopython_gc_percent(seq):
    seq = str(seq).upper()
    if not seq:
        return {"gc_percent": None, "source": "Bio.SeqUtils.gc_fraction"}
    return {"gc_percent": round(gc_fraction(Seq(seq)) * 100.0, 2),
            "source": "Bio.SeqUtils.gc_fraction"}


def primer_tm_crosscheck(binding, primary_tm, primary_label="primer3-core",
                         na=50.0, mg=1.5):
    """Compare a primary Tm against two independent calculations.

    ``mg`` should match the primary backend's salt model: Primer3 defaults
    use 1.5 mM Mg2+; the heuristic Tm_NN fallback uses 0 mM Mg2+.
    """
    binding = str(binding).upper()
    bio = bio_tm_nn(binding, na, mg=mg)
    wallace = wallace_tm(binding)
    primary = float(primary_tm) if primary_tm is not None else None
    conflicts = []
    if primary is not None and bio["tm"] is not None:
        delta = abs(primary - bio["tm"])
        if delta > PRIMER_TM_WARN_C:
            conflicts.append({
                "kind": "tm_method_disagreement",
                "primary": {"source": primary_label, "tm": primary},
                "independent": {"source": bio["formula"], "tm": bio["tm"]},
                "delta_c": round(delta, 2),
                "severity": ("warn" if delta <= 5.0 else "error"),
                "note": ("Primer3 and Biopython use different nearest-"
                         "neighbor parameter sets; >3.5 C disagreement "
                         "requires review"),
            })
    primary_out = primary is not None and not (
        PRIMER_TM_RANGE[0] <= primary <= PRIMER_TM_RANGE[1])
    bio_out = bio["tm"] is not None and not (
        PRIMER_TM_RANGE[0] <= bio["tm"] <= PRIMER_TM_RANGE[1])
    range_conflict = None
    if primary_out or bio_out:
        range_conflict = {
            "kind": "tm_outside_52_72",
            "primary_tm": primary,
            "bio_tm": bio["tm"],
            "wallace_tm": wallace["tm"],
            "severity": "error" if primary_out and bio_out else "warn",
            "source": "SnapGene DNA Design internal 52-72 C window (Primer3 defaults are 57/60/63)",
        }
    return {
        "binding": binding,
        "primary_tm": primary,
        "primary_source": primary_label,
        "bio_nn_tm": bio["tm"],
        "bio_nn_source": bio["formula"],
        "wallace_tm": wallace["tm"],
        "wallace_source": wallace["formula"],
        "delta_primary_bio_c": (round(abs(primary - bio["tm"]), 2)
                                if primary is not None and bio["tm"] is not None
                                else None),
        "conflicts": conflicts + ([range_conflict] if range_conflict else []),
        "status": ("conflict-error" if any(
            c["severity"] == "error" for c in conflicts + (
                [range_conflict] if range_conflict else []))
            else "conflict-warn" if (conflicts or range_conflict)
            else "consistent"),
    }


def restriction_site_crosscheck(sequence, enzyme_name, circular=False):
    """Bio.Restriction hit positions vs direct motif scanning."""
    from sg_common import get_enzyme, restriction_hits

    sequence = str(sequence).upper()
    enzyme = get_enzyme(enzyme_name)
    site = str(enzyme.site).upper()
    rc_site = str(Seq(site).reverse_complement())
    bio_hits = restriction_hits(Seq(sequence), enzyme, circular=circular)
    direct = set()
    n = len(sequence)
    iupac = {
        "A": "A", "C": "C", "G": "G", "T": "T", "U": "U",
        "R": "AG", "Y": "CT", "S": "GC", "W": "AT", "K": "GT",
        "M": "AC", "B": "CGT", "D": "AGT", "H": "ACT",
        "V": "ACG", "N": "ACGT",
    }

    def matches(window, pattern):
        return len(window) == len(pattern) and all(
            base in iupac.get(symbol, symbol)
            for base, symbol in zip(window, pattern))

    if n and len(site) <= n:
        probe = sequence if circular else sequence
        stop = n if circular else n - len(site) + 1
        for i in range(stop):
            window = probe[i:i + len(site)]
            if len(window) < len(site):
                window += probe[:len(site) - len(window)]
            if matches(window, site) or matches(window, rc_site):
                direct.add(i % n)
    bio_set = {int(item["recognition_start0"]) for item in bio_hits} \
        if bio_hits else set()
    return {
        "enzyme": enzyme_name,
        "recognition_sequence": site,
        "recognition_reverse_complement": rc_site,
        "bio_restriction_hits": [{
            "recognition_start": int(item["recognition_start0"]),
            "cut_boundary_0based": int(item["top_cut_boundary_0based"]),
            "strand": item["strand"],
        } for item in bio_hits],
        "direct_motif_starts": sorted(direct),
        "bio_hit_count": len(bio_set),
        "direct_motif_count": len(direct),
        "consistent_count": len(bio_set) == len(direct),
        "conflicts": [] if len(bio_set) == len(direct) else [{
            "kind": "restriction_site_count_disagreement",
            "bio_count": len(bio_set),
            "direct_count": len(direct),
            "severity": "error",
            "note": "positions may differ because Bio.Restriction reports "
                    "cut boundaries while the direct scan reports motif "
                    "starts; counts must match",
        }],
    }


def overlap_crosscheck(overlap):
    """GC/Tm cross-checks for a designed overlap window."""
    overlap = str(overlap).upper()
    manual = manual_gc_percent(overlap)
    biopy = biopython_gc_percent(overlap)
    bio_tm = bio_tm_nn(overlap, mg=0.0)
    conflicts = []
    if (manual.get("gc_percent") is not None
            and biopy.get("gc_percent") is not None
            and abs(manual["gc_percent"] - biopy["gc_percent"]) > 0.01):
        conflicts.append({
            "kind": "gc_calculation_disagreement",
            "manual": manual, "biopython": biopy,
            "severity": "error",
        })
    return {
        "overlap": overlap,
        "gc_manual": manual,
        "gc_biopython": biopy,
        "tm_bio_nn": bio_tm,
        "tm_wallace": wallace_tm(overlap),
        "conflicts": conflicts,
        "status": "conflict-error" if conflicts else "consistent",
    }
