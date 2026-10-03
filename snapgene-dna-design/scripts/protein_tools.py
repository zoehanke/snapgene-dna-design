# -*- coding: utf-8 -*-
"""protein_tools.py - Protein / oligo utilities.

Subcommands:
  reverse-translate  back-translate a protein to degenerate DNA (IUPAC)
  anneal             anneal two complementary oligos into dsDNA (with overhang)
"""
import argparse

from Bio.Seq import Seq

from sg_common import jprint, load_seq

# Degenerate back-translation codons (IUPAC). For six-codon amino acids, use
# an exact four-codon family rather than a broader pattern that introduces a
# different amino acid (for example, CTN for Leu rather than YTN).
AA_CODONS = {
    "A": "GCN", "R": "CGN", "N": "AAY", "D": "GAY", "C": "TGY",
    "Q": "CAR", "E": "GAR", "G": "GGN", "H": "CAY", "I": "ATH",
    "L": "CTN", "K": "AAR", "M": "ATG", "F": "TTY", "P": "CCN",
    "S": "TCN", "T": "ACN", "W": "TGG", "Y": "TAY", "V": "GTN",
    "*": "TAR",
}


def reverse_translate(protein):
    aa = str(protein).upper().replace(" ", "")
    return "".join(AA_CODONS.get(x, "NNN") for x in aa)


def anneal(top, bottom):
    """Anneal two oligos. bottom is given 5'->3'; it must be the reverse
    complement of top (or a subset, allowing a 5' overhang)."""
    top = str(top).upper()
    bottom = str(bottom).upper()
    rc_bottom = str(Seq(bottom).reverse_complement())
    # find where top and rc_bottom overlap
    # try full-length and shifted
    for shift in range(0, len(top)):
        overlap = min(len(top) - shift, len(rc_bottom))
        if top[shift:shift + overlap] == rc_bottom[:overlap] and overlap >= 4:
            # build double strand
            full_top = top
            full_bottom = str(Seq(top).reverse_complement())
            return {
                "top": full_top,
                "bottom": full_bottom,
                "length": len(full_top),
                "overhang_5p": top[:shift] if shift > 0 else "",
                "overhang_type": "5'" if shift > 0 else "blunt",
            }
    raise ValueError("oligos do not anneal (no complementary overlap >= 4 bp)")


def main():
    p = argparse.ArgumentParser(description="Protein / oligo utilities")
    p.add_argument("command", choices=["reverse-translate", "anneal"])
    p.add_argument("source", help="protein sequence (reverse-translate) or top oligo (anneal)")
    p.add_argument("--bottom", help="bottom oligo 5'->3' (anneal)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.command == "reverse-translate":
        protein = args.source
        dna = reverse_translate(protein)
        result = {"protein": protein.upper(), "degenerate_dna": dna, "length": len(dna)}
    else:
        if not args.bottom:
            raise SystemExit("anneal requires --bottom")
        result = anneal(args.source, args.bottom)

    if args.json:
        jprint(result)
    else:
        for k, v in result.items():
            print("%s: %s" % (k, v))


if __name__ == "__main__":
    main()
