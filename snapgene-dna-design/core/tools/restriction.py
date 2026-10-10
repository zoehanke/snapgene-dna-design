# -*- coding: utf-8 -*-
"""core/tools/restriction.py - Atomic restriction endonuclease analysis tool.

Scans sequences or files for restriction sites, determines cut coordinates,
cut counts, overhang types (5', 3', blunt), and recognizes Type IIS enzymes.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record
from core.models.molecule import MoleculeInput, as_molecule, derived_molecule
from core.models.assembly_model import FragmentEnd, compatible_sticky
from core.tools.result import ToolResult, reaction_checks

# Enzyme properties, not material-specific exceptions. NEB product records,
# checked 2026-10-10; other enzymes/conditional inhibition remain UNKNOWN.
# Values concern dam/dcm only. CpG and actual substrate methylation are not inferred.
METHYLATION_RESPONSES = {
    'PvuI': ({'dam': 'insensitive', 'dcm': 'insensitive'}, 'r0150-pvui'),
    'SspI': ({'dam': 'insensitive', 'dcm': 'insensitive'}, 'r0132-sspi'),
    'BclI': ({'dam': 'blocked', 'dcm': 'insensitive'}, 'r0160-bcli'),
    'XbaI': ({'dam': 'blocked', 'dcm': 'insensitive'}, 'r0145-xbai'),
    'BamHI': ({'dam': 'insensitive', 'dcm': 'insensitive'}, 'r0136-bamhi'),
    'NotI': ({'dam': 'insensitive', 'dcm': 'insensitive'}, 'r0189-noti'),
    'BsaI': ({'dam': 'insensitive', 'dcm': 'conditional'}, 'r3733-bsai-hf-v2'),
    'BsmBI': ({'dam': 'insensitive', 'dcm': 'insensitive'}, 'r0739-bsmbi-v2'),
}


def get_enzyme(enzyme_name: str):
    """Resolve a restriction enzyme name case-insensitively.

    Returns a Bio.Restriction enzyme class, or raises ValueError.
    """
    import Bio.Restriction as restr
    name = enzyme_name.strip()
    # exact attribute lookup first (handles EcoRI, BamHI, etc.)
    for candidate in (name, name.capitalize()):
        try:
            return getattr(restr, candidate)
        except AttributeError:
            continue
    # case-insensitive fallback over all known enzymes
    lower = name.lower()
    for attr in dir(restr):
        if attr.lower() == lower:
            return getattr(restr, attr)
    raise ValueError(f"Unknown restriction enzyme: {enzyme_name}")


def enzyme_sites(seq: str | Seq, enzyme: Any, circular: bool = False) -> list[int]:
    """Return 1-based first-base-after-top-cut positions.

    Follows Bio.Restriction.search semantics. Cut coordinate, not recognition start.
    """
    try:
        positions = list(enzyme.search(Seq(str(seq)), linear=not circular))
        if circular and len(seq):
            positions = [((int(pos) - 1) % len(seq)) + 1 for pos in positions]
        return sorted(set(int(pos) for pos in positions))
    except Exception:
        return []


def restriction_hits(seq: str | Seq, enzyme: Any, circular: bool = False) -> list[dict[str, Any]]:
    """Return recognition sites and explicit double-strand cut boundaries.

    Circular hits may have ``end < start`` and ``wraps_origin=True``.
    Non-palindromic sites are searched on both orientations.
    """
    s = str(seq).upper()
    site = str(enzyme.site).upper()
    n, width = len(s), len(site)
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
    if not n or not width:
        return []

    rc_site = str(Seq(site).reverse_complement())
    if circular:
        repeats = ((width - 1) // n) + 2
        searchable = (s * repeats)[:n + width - 1]
        starts = range(n)
    else:
        searchable = s
        starts = range(max(n - width + 1, 0))

    hits = []
    for start0 in starts:
        window = searchable[start0:start0 + width]
        orientations = []
        if matches(window, site):
            orientations.append(1)
        if rc_site != site and matches(window, rc_site):
            orientations.append(-1)
        for strand in orientations:
            end0 = start0 + width
            wraps = circular and end0 > n
            end_1based = ((end0 - 1) % n) + 1 if circular else end0
            fst5 = int(enzyme.fst5)
            fst3 = int(enzyme.fst3)
            if strand == 1:
                top_cut = start0 + fst5
                bottom_cut = start0 + width + fst3
            else:
                top_cut = start0 - fst3
                bottom_cut = start0 + width - fst5
            raw_top_cut, raw_bottom_cut = top_cut, bottom_cut
            cuts_within = circular or (0 <= top_cut <= n and 0 <= bottom_cut <= n)
            lo, hi = sorted((raw_top_cut, raw_bottom_cut))
            overhang_type = "blunt" if lo == hi else ("5prime" if raw_top_cut < raw_bottom_cut else "3prime")
            # Report the reference top-strand motif, including an origin-spanning cut.
            overhang_seq = ("".join(s[i % n] for i in range(lo, hi)) if circular else s[lo:hi]) if cuts_within else None
            if circular:
                top_cut %= n
                bottom_cut %= n
            hits.append({
                "start": start0 + 1,
                "end": end_1based,
                "strand": strand,
                "wraps_origin": wraps,
                "recognition_start0": start0,
                "recognition_end0": end0,
                "top_cut_boundary_0based": top_cut,
                "bottom_cut_boundary_0based": bottom_cut,
                "raw_top_cut_boundary_0based": raw_top_cut,
                "raw_bottom_cut_boundary_0based": raw_bottom_cut,
                "overhang_type": overhang_type,
                "overhang_sequence": overhang_seq,
                "top_cut_after_base_1based": top_cut,
                "bottom_cut_after_base_1based": bottom_cut,
                "cuts_within_sequence": (
                    circular or (
                        0 <= raw_top_cut <= n and 0 <= raw_bottom_cut <= n
                    )
                ),
            })
    return hits


COMMON_CLONING_ENZYMES = [
    "EcoRI", "BamHI", "HindIII", "XhoI", "NdeI", "NotI", "NcoI", "SalI", "SacI",
    "KpnI", "PstI", "SpeI", "XbaI", "BglII", "ClaI", "DpnI", "SmaI", "EcoRV",
    "BsaI", "BsmBI", "Esp3I", "BbsI", "SapI", "AarI",
]


def find_restriction_sites(
    file_path_or_seq: str | pathlib.Path | SeqRecord,
    enzymes: list[str] | None = None,
    topology: str | None = None,
) -> ToolResult:
    """Analyze restriction endonuclease sites in DNA sequence.

    Args:
        file_path_or_seq: Path to sequence file, SeqRecord, or raw DNA string.
        enzymes: List of enzyme names. Defaults to COMMON_CLONING_ENZYMES.
        topology: "circular" or "linear". If None, inferred from record.

    Returns:
        dict containing per-enzyme site locations, counts, overhang geometries,
        and single-cutter / unique-cutter classifications.
    """
    from core.io.input_resolution import resolve_sequence_input
    rec, seq_str = resolve_sequence_input(file_path_or_seq, default_topology=topology or "linear")
    topo = topology or rec.annotations.get("topology", "linear")

    is_circular = (topo.lower() == "circular")
    n = len(seq_str)
    query_enzymes = list(enzymes) if enzymes else COMMON_CLONING_ENZYMES

    results: dict[str, Any] = {}
    unique_cutters = []
    double_cutters = []
    non_cutters = []
    unknown_enzymes = []
    warnings = []

    for name in query_enzymes:
        try:
            enz = get_enzyme(name)
        except Exception:
            unknown_enzymes.append(name)
            warnings.append(f"Restriction enzyme '{name}' is unrecognized by REBASE database; site scan omitted.")
            continue

        raw_hits = restriction_hits(Seq(seq_str), enz, circular=is_circular)
        sites = []
        for h in raw_hits:
            recog_start = h.get("recognition_start0", h.get("site_start_0based", h.get("start", 1) - 1))
            recog_seq = h.get("site", str(getattr(enz, "site", "")))
            top_cut = h.get("top_cut_boundary_0based", 0)
            bottom_cut = h.get("bottom_cut_boundary_0based", 0)
            overhang_type = h["overhang_type"]
            overhang_seq = h["overhang_sequence"]
            cuts_within = h.get("cuts_within_sequence", True)

            # A motif overlap is observable geometry, not enzyme sensitivity.
            recog_len = len(recog_seq) if recog_seq else 6
            blocked_by, overlaps, unresolved = [], [], []
            response, product = METHYLATION_RESPONSES.get(enz.__name__, ({}, None))
            searchable = seq_str + seq_str[:12] if is_circular else seq_str
            site_positions = {(recog_start+i) % n for i in range(recog_len)}
            for m_name, m_pat in [("dam", "GATC"), ("dcm", "CC[AT]GG"), ("ecoki", "AAC[ACGT]{6}GTGC")]:
                for m in re.finditer(m_pat, searchable):
                    if m.start() >= n: continue
                    motif_positions = {(i % n if is_circular else i) for i in range(m.start(),m.end())}
                    if site_positions.intersection(motif_positions):
                        overlap = f"{m_name} overlap ({m.group(0)} at bp {m.start()})"
                        overlaps.append(overlap)
                        if response.get(m_name) == 'blocked': blocked_by.append(overlap)
                        elif response.get(m_name) != 'insensitive': unresolved.append(overlap)

            sites.append({
                "recognition_start_0based": recog_start,
                "recognition_sequence": recog_seq,
                "top_cut_boundary_0based": top_cut,
                "bottom_cut_boundary_0based": bottom_cut,
                "overhang_type": overhang_type,
                "overhang_sequence": overhang_seq,
                "cuts_within_sequence": cuts_within,
                "strand": h.get("strand", 1),
                "methylation_warnings": blocked_by,
                "methylation_overlaps": overlaps,
                "methylation_unresolved": unresolved,
                "methylation_status": 'BLOCKED_IF_METHYLATED' if blocked_by else 'UNKNOWN' if unresolved else 'NO_PREDICTED_DAM_DCM_BLOCKADE',
                "methylation_source": 'https://www.neb.com/en-us/products/'+product if product else None,
            })

        count = sum(site["cuts_within_sequence"] for site in sites)
        is_type_iis = name in ("BsaI", "BsmBI", "Esp3I", "BbsI", "SapI", "AarI", "PaqCI", "FokI", "BtsI") or getattr(enz, "fst5", 0) > len(str(getattr(enz, "site", "")))
        recog_pattern = str(enz.site) if hasattr(enz, "site") else ""

        results[name] = {
            "enzyme": name,
            "recognition_sequence": recog_pattern,
            "is_type_iis": is_type_iis,
            "cut_count": count,
            "recognition_count": len(sites),
            "cuts": sites,
        }

        if count == 1:
            unique_cutters.append(name)
        elif count == 2:
            double_cutters.append(name)
        elif count == 0:
            non_cutters.append(name)

    return ToolResult(analysis={
        "sequence_length": n,
        "topology": topo,
        "enzymes_analyzed": len(results),
        "unique_cutters": unique_cutters,
        "double_cutters": double_cutters,
        "non_cutters": non_cutters,
        "unknown_enzymes": unknown_enzymes,
        "warnings": warnings,
        "enzymes": results,
    })


def check_overhang_compatibility(
    overhang1: str,
    overhang2: str,
    type1: str = "5prime",
    type2: str = "5prime",
    representation: str = "actual_5to3",
) -> ToolResult:
    """Compare actual 5'-to-3' extensions, or explicitly selected junction labels.

    Label equality is a design convention, not evidence of physical ligation.
    Actual reactions use Molecule ends through ligate_fragments.
    """
    if representation not in ('actual_5to3', 'junction_label'):
        raise ValueError('Overhang representation must be actual_5to3 or junction_label')
    context = {'representation': representation, 'scope':
               'physical_overhang_complementarity' if representation == 'actual_5to3' else 'junction_label_equality'}
    o1 = str(overhang1 or "").strip().upper()
    o2 = str(overhang2 or "").strip().upper()
    t1 = str(type1).lower()
    t2 = str(type2).lower()

    if t1 == "blunt" and t2 == "blunt":
        return ToolResult(analysis={
            **context,
            "compatible": True,
            "type": "blunt-blunt",
            "message": "Both ends are blunt; non-directional ligation possible",
        })

    if t1 != t2:
        return ToolResult(analysis={
            **context,
            "compatible": False,
            "type": f"{t1}-{t2}",
            "message": f"End geometry mismatch: {t1} cannot ligate with {t2}",
        })

    o2_rc = str(Seq(o2).reverse_complement()) if o2 else ""
    if representation == 'actual_5to3':
        kind = {'5prime': "5'-overhang", '3prime': "3'-overhang"}[t1]
        is_compat = bool(o1 and o2) and compatible_sticky(FragmentEnd(kind, o1), FragmentEnd(kind, o2))
    else:
        is_compat = bool(o1) and o1 == o2
    message = ("Actual sticky extensions are complementary" if is_compat else f"Actual sticky extensions are not complementary: {o1} vs {o2}")
    if representation == 'junction_label':
        message = 'Junction labels match; this does not establish physical ligation' if is_compat else f'Junction labels differ: {o1} vs {o2}'

    return ToolResult(analysis={
        **context,
        "compatible": is_compat,
        "type": f"{t1}-{t2}",
        "overhang1": o1,
        "overhang2": o2,
        "overhang2_rc": o2_rc,
        "message": message,
    })


def digest_sequence(seq: MoleculeInput, enzyme: str, circular: bool | None = None) -> ToolResult:
    """Digest the actual annotated material, carrying each cleavage geometry."""
    source = as_molecule(seq)
    enz = get_enzyme(enzyme)
    sequence = str(source.seq).upper()
    if source.topology is None and circular is None:
        raise ValueError('Digest topology is unknown; declare linear or circular explicitly')
    is_circular = source.topology == 'circular' if circular is None else circular
    if source.strandedness == 'single':
        raise ValueError('Restriction digestion requires a double-stranded substrate')
    hits = sorted((h for h in restriction_hits(Seq(sequence), enz, circular=is_circular)
                   if h['cuts_within_sequence']), key=lambda h: h['top_cut_boundary_0based'])
    if not hits:
        return ToolResult(products=[source], analysis={'enzyme': enzyme, 'cut_count': 0, 'fragment_count': 1})
    from core.tools.sequence_ops import slice_record_interval
    n = len(source)
    boundaries = [h['top_cut_boundary_0based'] for h in hits]
    intervals = [(boundaries[i], (boundaries[(i+1) % len(boundaries)] - boundaries[i]) % n or n,
                  hits[i], hits[(i+1) % len(hits)]) for i in range(len(hits))] if is_circular else [
                  (start, end-start, hits[i-1] if i else None, hits[i] if i < len(hits) else None)
                  for i, (start, end) in enumerate(zip([0]+boundaries, boundaries+[n]))]
    products = []
    for start, length, left, right in intervals:
        record = slice_record_interval(source, start, length, circular=is_circular)
        def cut_end(hit, boundary, side):
            if hit is None:
                return None
            kind = {'5prime': "5'-overhang", '3prime': "3'-overhang", 'blunt': 'blunt'}[hit['overhang_type']]
            extension = hit['overhang_sequence'] or ''
            if (kind == "5'-overhang" and side == 'right') or (kind == "3'-overhang" and side == 'left'):
                extension = str(Seq(extension).reverse_complement())
            return FragmentEnd(kind, extension, cut_boundary=boundary,
                               source_cut_boundary=hit['top_cut_boundary_0based'])
        import copy
        retained_left, retained_right = copy.deepcopy(source.left_end), copy.deepcopy(source.right_end)
        if retained_left is not None:
            retained_left.cut_boundary = 0
        if retained_right is not None:
            retained_right.cut_boundary = length
        products.append(derived_molecule(record, [source], operation='digest_sequence', strandedness='double',
                        left_end=cut_end(left, 0, 'left') if left else retained_left,
                        right_end=cut_end(right, length, 'right') if right else retained_right,
                        mappings=[{'start0': start, 'length': length, 'circular_source': is_circular}]))
    return ToolResult(products=products, checks=reaction_checks(products,'restriction_digest'), analysis={'enzyme': enzyme, 'cut_count': len(hits),
                                                  'fragment_count': len(products), 'cut_sites': hits})


def digest_type_iis(
    fragment_seq: MoleculeInput,
    enzyme: str = "BsaI",
) -> ToolResult:
    """Perform single-fragment Type IIS digestion (e.g. BsaI, BsmBI), stripping recognition sites and liberating cohesive overhangs."""
    enz = get_enzyme(enzyme)
    source = as_molecule(fragment_seq)
    if source.strandedness == 'single':
        raise ValueError('Type IIS digestion requires a double-stranded substrate')
    s = str(source.seq)
    hits = restriction_hits(Seq(s), enz, circular=source.topology=="circular")

    hits = [h for h in hits if h.get("cuts_within_sequence", True)]
    if len(hits) != 2:
        detail = "internal Type IIS site(s) require explicit redesign" if len(hits) > 2 else "two in-sequence flanking sites are required"
        raise ValueError(f"Type IIS fragment requires exactly 2 in-sequence flanking sites; found {len(hits)} ({detail})")

    forward=[h for h in hits if h['strand']==1]
    reverse=[h for h in hits if h['strand']==-1]
    if len(forward)!=1 or len(reverse)!=1:
        raise ValueError('Type IIS excision requires one forward and one reverse flanking site')
    h_left,h_right=forward[0],reverse[0]

    if h_left.get("strand", 1) != 1 or h_right.get("strand", -1) != -1:
        raise ValueError("Type IIS sites must face inward: forward site on the left and reverse site on the right")

    t_left = h_left["top_cut_boundary_0based"]
    b_left = h_left["bottom_cut_boundary_0based"]
    t_right = h_right["top_cut_boundary_0based"]
    b_right = h_right["bottom_cut_boundary_0based"]

    left_cut = min(t_left, b_left)
    left_cut_max = max(t_left, b_left)
    left_ov = h_left['overhang_sequence'] or ''

    right_cut = min(t_right, b_right)
    right_cut_max = max(t_right, b_right)
    right_ov = h_right['overhang_sequence'] or ''

    from core.tools.sequence_ops import slice_record_interval
    span=(t_right-t_left)%len(source) if source.topology=='circular' else t_right-t_left
    if span<=0:raise ValueError('Linear Type IIS flanking sites must face inward')
    record = slice_record_interval(source,t_left,span,circular=source.topology=='circular')
    def terminus(hit,boundary,side):
        kind = {'5prime':"5'-overhang",'3prime':"3'-overhang",'blunt':'blunt'}[hit['overhang_type']]
        extension = hit['overhang_sequence'] or ''
        if (side=='right' and kind=="5'-overhang") or (side=='left' and kind=="3'-overhang"):
            extension = str(Seq(extension).reverse_complement())
        return FragmentEnd(kind,extension,cut_boundary=boundary,source_cut_boundary=hit['top_cut_boundary_0based'])
    product = derived_molecule(record,[source],operation='digest_type_iis',strandedness='double',
             left_end=terminus(h_left,0,'left'),right_end=terminus(h_right,len(record),'right'),
             mappings=[{'start0':t_left,'end0':t_right}])
    insert_core = str(product.seq)
    if str(enz.site) in insert_core or str(Seq(enz.site).reverse_complement()) in insert_core:
        raise ValueError('Excised Type IIS fragment contains an intact recognition site')

    return ToolResult(products=[product],checks=reaction_checks([product],product.operation),analysis={
        "original_sequence": s,
        "insert_length": len(insert_core),
        "left_overhang": left_ov,
        "right_overhang": right_ov,
        "enzyme": enzyme,
        "stripped_5prime_site": s[:left_cut],
        "stripped_3prime_site": s[t_right:],
    })


def fill_or_chew_overhang(seq: MoleculeInput, left_overhang: str | None = None,
                         right_overhang: str | None = None, overhang_type: str | None = None,
                         action: str = 'fill_in') -> ToolResult:
    """Repair known termini. Wrong geometry cannot silently become blunt."""
    source = as_molecule(seq)
    if source.topology == 'circular' or source.strandedness == 'single':
        raise ValueError('End repair requires linear double-stranded material')
    if action not in ('fill_in','chew_back'):
        raise ValueError('Unknown end-repair action')
    def choose(existing, declared, side):
        if declared is None:
            if existing is None:
                raise ValueError('End geometry is unknown; supply explicit substrate ends')
            return existing
        kind = {'5prime':"5'-overhang",'3prime':"3'-overhang",'blunt':'blunt'}.get(overhang_type)
        if not declared:
            kind = 'blunt'
        if kind is None:
            raise ValueError('Explicit overhangs require an explicit geometry')
        end = FragmentEnd(kind, declared, cut_boundary=0 if side=='left' else len(source))
        if existing and (existing.kind,existing.overhang_sequence)!=(end.kind,end.overhang_sequence):
            raise ValueError('Declared overhang conflicts with the molecular substrate')
        return end
    left, right = choose(source.left_end,left_overhang,'left'), choose(source.right_end,right_overhang,'right')
    sequence = str(source.seq)
    if left.kind == "5'-overhang" and not sequence.startswith(left.overhang_sequence):
        raise ValueError('Reference-top strand does not contain its declared left 5-prime extension')
    if right.kind == "3'-overhang" and not sequence.endswith(right.overhang_sequence):
        raise ValueError('Reference-top strand does not contain its declared right 3-prime extension')
    from core.tools.sequence_ops import slice_record_interval
    length = len(source)
    if action == 'fill_in':
        if left.kind == "3'-overhang" or right.kind == "3'-overhang":
            raise ValueError('Fill-in cannot blunt a protruding 3-prime terminus')
        addition = str(Seq(right.overhang_sequence).reverse_complement()) if right.kind=="5'-overhang" else ''
        # Own every mutable field; SeqRecord slicing/concatenation may share qualifiers.
        import copy
        record = SeqRecord(Seq(sequence + addition), id=source.id, name=source.name,
                           description=source.description, dbxrefs=list(source.dbxrefs),
                           features=copy.deepcopy(source.features),
                           annotations=copy.deepcopy(source.annotations))
        for key, values in source.letter_annotations.items():
            record.letter_annotations[key] = copy.deepcopy(list(values)) + [None] * len(addition)
        record.annotations['topology'] = 'linear'
    else:
        if left.kind == "5'-overhang" or right.kind == "5'-overhang":
            raise ValueError('3-to-5 exonuclease trimming cannot remove a protruding 5-prime terminus')
        length -= len(right.overhang_sequence) if right.kind=="3'-overhang" else 0
        record = slice_record_interval(source,0,length)
    product = derived_molecule(record,[source],operation='fill_or_chew_overhang',strandedness='double',
             left_end=FragmentEnd('blunt',cut_boundary=0),right_end=FragmentEnd('blunt',cut_boundary=len(record)),
             mappings=[{'retained_start0':0,'retained_length':length,'action':action}])
    return ToolResult(products=[product],checks=reaction_checks([product],product.operation),analysis={'original_length':len(source),'blunted_length':len(product),
                            'action_applied':action,'end_type':'blunt'})
