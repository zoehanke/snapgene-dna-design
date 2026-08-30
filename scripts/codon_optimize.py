# -*- coding: utf-8 -*-
"""codon_optimize.py - Explicitly heuristic codon recoding.

Back-translates an amino-acid sequence (or re-codes a coding DNA sequence)
using one preferred codon for each amino acid in the chosen host.  This is
not a full expression-optimization model: no CAI/tAI, codon-pair, mRNA
structure, repeats, restriction sites, or host-strain constraints are solved.

Input mode defaults to ``auto``: sequences built only from DNA/IUPAC letters
are treated as DNA, anything else as protein. Use ``--mode protein`` or
``--mode dna`` to override the detection. Re-coding a DNA sequence preserves
the terminal stop codon.
"""
import argparse
import io
import os

from Bio import SeqIO
from Bio.Seq import Seq

from sg_common import DNA_IUPAC, jprint, load_seq, looks_like_path

# Most frequent codon per amino acid (standard genetic code), per host.
CODON_TABLES = {
    "ecoli": {
        "A": "GCG", "R": "CGC", "N": "AAC", "D": "GAT", "C": "TGC",
        "Q": "CAG", "E": "GAA", "G": "GGC", "H": "CAT", "I": "ATT",
        "L": "CTG", "K": "AAA", "M": "ATG", "F": "TTT", "P": "CCG",
        "S": "AGC", "T": "ACC", "W": "TGG", "Y": "TAT", "V": "GTG",
        "*": "TAA",
    },
    "yeast": {
        "A": "GCT", "R": "AGA", "N": "AAT", "D": "GAT", "C": "TGT",
        "Q": "CAA", "E": "GAA", "G": "GGT", "H": "CAT", "I": "ATT",
        "L": "TTG", "K": "AAA", "M": "ATG", "F": "TTT", "P": "CCA",
        "S": "TCT", "T": "ACT", "W": "TGG", "Y": "TAT", "V": "GTT",
        "*": "TAA",
    },
    "human": {
        "A": "GCC", "R": "AGA", "N": "AAC", "D": "GAC", "C": "TGC",
        "Q": "CAG", "E": "GAG", "G": "GGC", "H": "CAC", "I": "ATC",
        "L": "CTG", "K": "AAG", "M": "ATG", "F": "TTC", "P": "CCC",
        "S": "AGC", "T": "ACC", "W": "TGG", "Y": "TAC", "V": "GTG",
        "*": "TGA",
    },
}

CODON_TABLE_METADATA = {
    "ecoli": {
        "source": "Kazusa Codon Usage Database, Escherichia coli K-12",
        "url": "https://www.kazusa.or.jp/codon/cgi-bin/showcodon.cgi?aa=1&species=83333&style=N",
        "retrieved_at": "2026-08-22",
        "dataset_note": "public table is historical GenBank-derived usage; not a strain-specific expression model",
        "status": "source-backed-preferred-codon-only",
    },
    "yeast": {
        "source": "Kazusa Codon Usage Database, Saccharomyces cerevisiae",
        "url": "https://www.kazusa.or.jp/codon/cgi-bin/showcodon.cgi?species=4932",
        "retrieved_at": "2026-08-22",
        "dataset_note": "public table is historical GenBank-derived usage; not a strain-specific expression model",
        "status": "source-backed-preferred-codon-only",
    },
    "human": {
        "source": "Kazusa Codon Usage Database, Homo sapiens",
        "url": "https://www.kazusa.or.jp/codon/cgi-bin/showcodon.cgi?species=9606",
        "retrieved_at": "2026-08-22",
        "dataset_note": "public table is historical GenBank-derived usage; not a tissue-specific expression model",
        "status": "source-backed-preferred-codon-only",
    },
}

AA_SYMBOLS = frozenset("ARNDCQEGHILKMFPSTWYV*XUOJBZ-")


def _first_fasta_sequence(text):
    records = list(SeqIO.parse(io.StringIO(text), "fasta"))
    if not records:
        raise ValueError("FASTA input contains no records")
    if len(records) != 1:
        raise ValueError(
            "FASTA input must contain exactly one record; found %d" % len(records)
        )
    return str(records[0].seq).upper()


def _read_source_text(source):
    """Return the raw text payload for a protein / auto-mode source.

    Path-like arguments are treated as files: a missing file is an error
    instead of being translated as a protein string.
    """
    s = str(source).strip()
    if looks_like_path(s):
        if not os.path.isfile(s):
            raise FileNotFoundError("sequence file not found: %s" % source)
        with open(s, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    else:
        text = s
    if text.lstrip().startswith(">"):
        return _first_fasta_sequence(text)
    return text


def detect_mode(raw, explicit_mode=None):
    """Heuristic input-type detection.

    DNA/IUPAC-only input is treated as DNA (the v0.3.0 default of silently
    translating A/C/G/T as amino acids produced useless NNN output). Protein
    input is detected when amino-acid-only symbols are present. The detection
    is advisory and can be overridden with --mode.
    """
    clean = "".join(str(raw).split()).upper()
    if explicit_mode in ("protein", "dna"):
        return explicit_mode, []
    if not clean:
        raise ValueError("empty input sequence")

    aa_only = set(clean) - DNA_IUPAC
    if aa_only:
        return "protein", [
            "auto-detected protein input (non-DNA symbol(s): %s)" % ", ".join(sorted(aa_only)),
        ]
    return "dna", [
        "auto-detected DNA input (all symbols are DNA/IUPAC); "
        "use --mode protein to force amino-acid translation",
    ]


def optimize_aa(aa_seq, table):
    aa = "".join(str(aa_seq).upper().split())
    unknown = sorted(set(aa) - set(table))
    return "".join(table.get(x, "NNN") for x in aa), unknown


def recode_dna(dna_seq, table):
    """Re-code a coding DNA sequence to optimal codons.

    The translated protein (including the terminal stop codon, when present)
    is preserved exactly; non-multiple-of-3 input is rejected instead of
    being silently trimmed.
    """
    dna = str(dna_seq).upper()
    if len(dna) % 3 != 0:
        raise ValueError(
            "coding DNA length must be a multiple of 3 (got %d bp); "
            "use --mode protein if this is an amino-acid sequence" % len(dna)
        )
    aa = str(Seq(dna).translate())
    optimized, unknown = optimize_aa(aa, table)
    return optimized, aa, unknown


def main():
    p = argparse.ArgumentParser(description="Codon optimization / back-translation")
    p.add_argument("source", help="protein sequence or coding DNA file/raw seq")
    p.add_argument("--host", choices=list(CODON_TABLES.keys()), default="ecoli")
    p.add_argument("--mode", choices=["auto", "protein", "dna"], default="auto",
                   help="input type; auto detects DNA/IUPAC vs protein (default: auto)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    warnings = []
    table = CODON_TABLES[args.host]

    try:
        if args.mode == "dna":
            rec, _fmt = load_seq(args.source)
            raw = str(rec.seq).upper()
            mode = "dna"
            warnings.append("mode dna: input treated as coding DNA")
            optimized, original_protein, unknown_aa = recode_dna(raw, table)
            warnings.extend("unknown amino-acid symbol %r -> NNN" % x for x in unknown_aa)
        else:
            raw = _read_source_text(args.source)
            mode, detect_warnings = detect_mode(raw, args.mode)
            warnings.extend(detect_warnings)
            if mode == "dna":
                rec, _fmt = load_seq(args.source if os.path.isfile(str(args.source).strip()) else raw)
                dna = str(rec.seq).upper()
                optimized, original_protein, unknown_aa = recode_dna(dna, table)
                warnings.extend("unknown amino-acid symbol %r -> NNN" % x for x in unknown_aa)
            else:
                clean = "".join(str(raw).upper().split())
                if args.mode == "protein" and set(clean) <= DNA_IUPAC and len(clean) % 3 == 0:
                    warnings.append(
                        "protein mode requested, but the input looks like coding DNA; "
                        "verify that A/C/G/T should be read as amino acids"
                    )
                optimized, unknown_aa = optimize_aa(raw, table)
                original_protein = clean
                unknown_input = sorted(set(clean) - AA_SYMBOLS)
                if unknown_input:
                    warnings.append(
                        "input contains non-standard symbols %s; they are translated as NNN"
                        % ", ".join(unknown_input)
                    )
                if unknown_aa:
                    warnings.extend(
                        "unknown amino-acid symbol %r -> NNN" % x for x in unknown_aa
                    )
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))

    result = {
        "host": args.host,
        "mode": mode,
        "status": "heuristic-recoding",
        "optimization_method": "single-preferred-codon",
        "provenance": CODON_TABLE_METADATA[args.host],
        "biological_limitations": [
            "not a CAI/tAI or codon-pair optimization",
            "no mRNA folding, repeat, restriction-site, splice, or host-strain constraint model",
            "do not transfer this table between species or strains",
        ],
        "input_length": len("".join(str(raw).split())),
        "optimized_dna": optimized,
        "optimized_length": len(optimized),
        "warnings": warnings,
    }
    if mode == "dna":
        result["original_protein"] = original_protein
        result["optimized_protein"] = str(Seq(optimized).translate())

    if args.json:
        jprint(result)
    else:
        print("host=%s mode=%s: %d -> %d bp" % (
            args.host, mode, result["input_length"], len(optimized)))
        for w in warnings:
            print("  warning: %s" % w)
        print(optimized)


if __name__ == "__main__":
    main()
