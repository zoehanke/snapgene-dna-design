"""Construct redistributable full-template engineering inputs without DNA Core.

The fixed seeds, lengths, edit intervals and feature geometry are test design,
not biological material identities. Random locators do not certify function.
"""
from pathlib import Path
import random

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord


CASES = ((75, 3100), (971, 4200))
EDIT_STARTS = (229, 547)
PCR_INTERVAL = (103, 827)


def _edit_window(rng):
    """Construct an uncomplicated positive-test locus, independent of Core.

    Balanced 25 nt boundary windows and absence of seven-base inverted repeats
    are sequence construction rules, not a claim that every primer is suitable.
    Real complete-primer checks still run and may reject any generated design.
    """
    complement = str.maketrans("ACGT", "TGCA")
    while True:
        window = "".join(rng.choices("ACGT", k=83))
        window = window[:40] + "TAT" + window[43:]
        if any(base * 4 in window for base in "ACGT"):
            continue
        if any(not 11 <= sum(base in "GC" for base in core) <= 15
               for core in (window[15:40], window[43:68])):
            continue
        if any(window[i:i + 7].translate(complement)[::-1] in window[i + 10:]
               for i in range(len(window) - 7)):
            continue
        return window


def build_template(seed=75, length=3100):
    """Return independently constructed circular sequence and source features."""
    if length < 2200:
        raise ValueError("Full-template synthetic input must be at least 2200 bp")
    rng = random.Random(seed)
    sequence = list("".join(rng.choices("ACGT", k=length)))
    # Controlled codons and simple flanks establish positive edit inputs without
    # consulting the implementation under test for sequences or expected answers.
    for start in EDIT_STARTS:
        sequence[start - 40:start + 43] = _edit_window(rng)
    # A synthetic complete CDS tests annotation preservation. It is not GFP or
    # an asserted functional gene; its independently constructed ORF has no stop
    # before the terminal TAA. Edits and PCR boundaries lie outside this CDS.
    codons = [a + b + c for a in "ACGT" for b in "ACGT" for c in "ACGT"
              if a + b + c not in ("TAA", "TAG", "TGA")]
    coding = "ATG" + "".join(rng.choices(codons, k=100)) + "TAA"
    sequence[1080:1386] = coding
    record = SeqRecord(Seq("".join(sequence)), id=f"synthetic-full-{seed}",
                       name=f"synthetic-{seed}",
                       description="Fixed-seed synthetic engineering template; no biological function certified",
                       annotations={"molecule_type": "DNA", "topology": "circular"})
    record.features = [
        SeqFeature(FeatureLocation(80, 900, strand=1), type="misc_feature",
                   qualifiers={"label": ["synthetic edit and PCR region"]}),
        SeqFeature(FeatureLocation(1080, 1386, strand=1), type="CDS",
                   qualifiers={"label": ["synthetic ORF"], "codon_start": ["1"],
                               "transl_table": ["1"], "product": ["uncharacterized synthetic peptide"]}),
        SeqFeature(FeatureLocation(1450, 1730, strand=-1), type="misc_feature",
                   qualifiers={"label": ["synthetic reverse locator"]}),
        SeqFeature(CompoundLocation([FeatureLocation(length - 80, length, strand=1),
                                     FeatureLocation(0, 80, strand=1)]), type="misc_feature",
                   qualifiers={"label": ["synthetic origin-spanning locator"]}),
    ]
    return record


def write_template(path, seed=75, length=3100):
    """Write explicit UTF-8 GenBank from the construction, returning its record."""
    record = build_template(seed, length)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        SeqIO.write(record, handle, "genbank")
    return record
