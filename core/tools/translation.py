# -*- coding: utf-8 -*-
"""core/tools/translation.py - Atomic translation, reverse complement, and silent mutation tools.

Provides reverse complementation, 6-frame translation, and synonymous (silent)
mutagenesis to silence internal restriction enzyme sites without altering protein sequence.
"""
from __future__ import annotations

from Bio.Data import CodonTable
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.restriction import get_enzyme, restriction_hits


def reverse_complement(seq: str) -> str:
    """Compute the reverse complement of a DNA nucleotide string."""
    if isinstance(seq, SeqRecord):
        return seq.reverse_complement(id=True, name=True, description=True, annotations=True)
    return str(Seq(str(seq).strip().upper()).reverse_complement())


def translate_dna(seq: str, frame: int = 1, table: int = 1) -> str:
    """Translate DNA sequence into amino acid peptide in specified reading frame (1, 2, 3, -1, -2, -3)."""
    s = str(seq).strip().upper()
    if frame < 0:
        s = str(Seq(s).reverse_complement())
        shift = abs(frame) - 1
    else:
        shift = frame - 1

    sub = s[shift:]
    rem = len(sub) % 3
    if rem > 0:
        sub = sub[:-rem]

    return str(Seq(sub).translate(table=table))


def silent_mutation_remove_site(
    cds_seq: str,
    enzyme_name: str,
    frame_offset: int = 0,
    table: int = 1,
) -> dict:
    """Mutate internal restriction sites silently without altering translated amino acid sequence.

    Args:
        cds_seq: Coding sequence.
        enzyme_name: Restriction enzyme name (e.g. 'EcoRI', 'BsaI', 'BamHI').
        frame_offset: 0-based offset of the first base in the reading frame (0, 1, or 2).
        table: NCBI genetic code table ID (1 = standard).

    Returns:
        dict with mutated_seq, original_aa, mutated_aa, mutations_applied, and site_removed.
    """
    s = list(str(cds_seq).strip().upper())
    n = len(s)
    enz = get_enzyme(enzyme_name)

    # Initial translation
    orig_aa = translate_dna("".join(s), frame=frame_offset + 1, table=table)

    current_hits = restriction_hits(Seq("".join(s)), enz, circular=False)
    if not current_hits:
        return {
            "mutated_seq": "".join(s),
            "site_removed": True,
            "mutations_applied": [],
            "message": f"No {enzyme_name} sites found in sequence",
            "identical_translation": True,
        }

    mutations_applied = []
    forward_table = CodonTable.unambiguous_dna_by_id[table].forward_table

    # Continue attempting to silence sites while sites exist and progress is made
    max_rounds = len(current_hits) + 4
    round_count = 0
    while current_hits and round_count < max_rounds:
        round_count += 1
        progress_made = False

        for h in current_hits:
            site_start = h.get("recognition_start0", h.get("start", 0))
            site_len = len(str(getattr(enz, "site", "")))

            for pos in range(site_start, min(site_start + site_len, n)):
                codon_idx = (pos - frame_offset) // 3
                codon_start = frame_offset + codon_idx * 3
                codon_end = codon_start + 3
                if codon_end > n or codon_start < 0:
                    continue

                current_codon = "".join(s[codon_start:codon_end])
                orig_amino = forward_table.get(current_codon, "*")
                base_idx_in_codon = pos - codon_start

                for alt in ("A", "C", "G", "T"):
                    if alt == s[pos]:
                        continue
                    test_codon = list(current_codon)
                    test_codon[base_idx_in_codon] = alt
                    test_codon_str = "".join(test_codon)
                    test_amino = forward_table.get(test_codon_str, "*")

                    if test_amino == orig_amino:
                        # Synonymous! Test if this mutation reduces the count of restriction sites
                        test_seq = list(s)
                        test_seq[pos] = alt
                        new_hits = restriction_hits(Seq("".join(test_seq)), enz, circular=False)
                        if len(new_hits) < len(current_hits):
                            # Successfully eliminated at least one site!
                            s[pos] = alt
                            mutations_applied.append({
                                "position_0based": pos,
                                "original_base": current_codon[base_idx_in_codon],
                                "alt_base": alt,
                                "codon_change": f"{current_codon} -> {test_codon_str}",
                                "amino_acid": orig_amino,
                            })
                            current_hits = new_hits
                            progress_made = True
                            break
                if progress_made:
                    break
            if progress_made:
                break

        if not progress_made:
            # Cannot eliminate remaining sites with synonymous mutations
            break

    mutated_str = "".join(s)
    new_aa = translate_dna(mutated_str, frame=frame_offset + 1, table=table)
    final_hits = restriction_hits(Seq(mutated_str), enz, circular=False)

    return {
        "mutated_seq": mutated_str,
        "site_removed": len(final_hits) == 0,
        "mutations_applied": mutations_applied,
        "remaining_cut_count": len(final_hits),
        "identical_translation": (orig_aa == new_aa),
    }


def get_codon_synonyms(codon: str, table: int = 1) -> dict[str, Any]:
    """Return all synonymous codons that translate to the same amino acid under specified genetic code.

    Args:
        codon: 3-base nucleotide triplet (e.g. 'CTG', 'GAA').
        table: NCBI genetic code table ID (default: 1 standard).

    Returns:
        dict with amino_acid, original_codon, synonymous_codons list, and codon count.
    """
    c = str(codon).strip().upper()
    if len(c) != 3:
        raise ValueError(f"Codon must be exactly 3 nucleotides, got '{codon}'")

    codon_table = CodonTable.unambiguous_dna_by_id[table]
    forward_table = codon_table.forward_table
    stop_codons = codon_table.stop_codons

    if c in stop_codons:
        aa = "*"
        synonyms = [s for s in stop_codons if s != c]
    else:
        aa = forward_table.get(c)
        if not aa:
            raise ValueError(f"Unrecognized codon '{codon}' in translation table {table}")
        synonyms = [cod for cod, trans_aa in forward_table.items() if trans_aa == aa and cod != c]

    return {
        "original_codon": c,
        "amino_acid": aa,
        "synonymous_codons": sorted(synonyms),
        "synonym_count": len(synonyms),
        "is_stop_codon": (aa == "*"),
    }
