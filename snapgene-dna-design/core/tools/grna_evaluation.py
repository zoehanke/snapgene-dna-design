"""Sequence evidence for guide screening, without an invented activity score."""
from __future__ import annotations

import re
from Bio.Seq import Seq
from core.models.molecule import MoleculeInput, as_molecule
from core.tools.result import ToolResult


SOURCES = {
    'crisprDesign': {
        'source_type': 'official_software_documentation',
        'name': 'crisprDesign introduction, sequence features and off-target search',
        'version': '2026-04-28 vignette',
        'url': 'https://bioconductor.org/packages/release/bioc/vignettes/crisprDesign/inst/doc/intro.html',
        'retrieved_at': '2026-10-13', 'verification_status': 'verified',
        'supports': 'GC preference 20–80%; >=4 T warning; exact and <=3 substitution site screening, not cleavage probability',
    },
    'human_U6': {
        'source_type': 'peer_reviewed_protocol',
        'name': 'A Golden Gate-based Protocol for Assembly of Multiplexed gRNA Expression Arrays for CRISPR/Cas9',
        'version': 'Bio-protocol 6(24), e2059 (2016), procedure B1',
        'url': 'https://www.bio-protocol.org/en/bpdetail?id=2059&pos=q&type=0',
        'retrieved_at': '2026-10-13', 'verification_status': 'verified',
        'supports': 'Human U6 first nucleotide preferably G; not a universal nuclease or promoter requirement',
    },
}


def validate_mismatch_limit(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
        raise ValueError('max_mismatches must be an integer from 0 to 3 (substitution-only screening bound)')


def _parts(start: int, length: int, n: int) -> list[list[int]]:
    start %= n
    if start + length <= n:
        return [[start, start + length]]
    return [[start, n], [0, start + length - n]]


def pam_sites(seq: str, circular: bool, cas12: bool = False) -> list[dict]:
    """Enumerate canonical PAM sites on both reference strands; coordinates 0-based."""
    n = len(seq)
    size = 27 if cas12 else 23
    if n < size:
        return []
    search = seq + seq[:size-1] if circular else seq
    patterns = (r'TTT[ACG][ACGT]{23}', r'[ACGT]{23}[CGT]AAA') if cas12 else (
        r'[ACGT]{20}[ACGT]GG', r'CC[ACGT][ACGT]{20}')
    sites = []
    for strand, pattern in zip((1, -1), patterns):
        for match in re.finditer('(?=(' + pattern + '))', search):
            pos = match.start()
            if pos >= n:
                break
            full = match.group(1)
            oriented = full if strand == 1 else str(Seq(full).reverse_complement())
            spacer, pam = (oriented[4:], oriented[:4]) if cas12 else (oriented[:20], oriented[20:])
            # Reference-order parts, with strand reported separately.
            spacer_offset = (4 if strand == 1 else 0) if cas12 else (0 if strand == 1 else 3)
            pam_offset = (0 if strand == 1 else 23) if cas12 else (20 if strand == 1 else 0)
            sites.append({'site_start_0based': pos, 'strand': strand, 'protospacer': spacer,
                          'protospacer_parts_0based': _parts(pos + spacer_offset, len(spacer), n),
                          'pam': pam, 'pam_parts_0based': _parts(pos + pam_offset, len(pam), n)})
    return sites


def matching_sites(spacer: str, sites: list[dict], limit: int) -> list[dict]:
    matches = []
    for site in sites:
        mismatch_positions = [i+1 for i, (a, b) in enumerate(zip(spacer, site['protospacer'])) if a != b]
        if len(site['protospacer']) == len(spacer) and len(mismatch_positions) <= limit:
            matches.append({**site, 'mismatches': len(mismatch_positions),
                            'mismatch_positions_1based': mismatch_positions,
                            'evidence_kind': 'sequence_prediction_not_measured_cleavage'})
    return sorted(matches, key=lambda h: (h['mismatches'], h['site_start_0based'], -h['strand']))


def vector_report(spacer: str, sites: list[dict], limit: int, ambiguous: int) -> dict:
    matches = matching_sites(spacer, sites, limit)
    exact = sum(h['mismatches'] == 0 for h in matches)
    near = len(matches) - exact
    status = ('EXACT_MATCH' if exact else 'NEAR_MATCH_RISK' if near else
              'INCOMPLETE' if ambiguous else 'NO_MATCH_IN_SEARCH_SCOPE')
    warnings = []
    if exact:
        warnings.append('会切到质粒自身：存在完全匹配+NGG，属于序列预测，未实测切割。')
    if near:
        warnings.append('可能会切到质粒自身：存在少量错配+NGG；错配数量不是切割概率。')
    if ambiguous:
        warnings.append('载体含未确定碱基，涉及这些碱基的位点未评估。')
    return {'self_target_status': status, 'matches': matches, 'exact_match_count': exact,
            'near_match_count': near, 'search_complete': not ambiguous,
            'max_mismatches': limit, 'pam': 'NGG', 'warnings': warnings,
            'scope': 'Provided vector only; both strands; substitutions only, no bulges or non-NGG PAMs',
            'source_ids': ['crisprDesign']}


def check_grna_vector(spacer_seq: str, vector_seq_or_file: MoleculeInput,
                      max_mismatches: int = 3) -> ToolResult:
    """Screen a supplied vector for SpCas9 self-target sites with NGG PAMs.

    Reports sequence predictions, not measured cleavage. Circularity comes from
    the supplied molecule/file; a raw sequence is linear. No vector is assumed.
    """
    validate_mismatch_limit(max_mismatches)
    spacer = str(spacer_seq).strip().upper()
    if len(spacer) != 20 or set(spacer) - set('ACGT'):
        raise ValueError('SpCas9 vector screening requires a 20 nt A/C/G/T spacer')
    vector = as_molecule(vector_seq_or_file)
    seq = str(vector.seq).upper()
    if not seq:
        raise ValueError('Vector sequence must not be empty')
    report = vector_report(spacer, pam_sites(seq, vector.topology == 'circular'), max_mismatches,
                           sum(base not in 'ACGT' for base in seq))
    return ToolResult(analysis={**report, 'vector_version': vector.record_version,
                                'vector_length': len(seq), 'sources': SOURCES})


def exact_loci(seq: str, spacer: str, circular: bool) -> list[list[list[int]]]:
    """Count physical duplex loci even without PAM; palindromes count once."""
    n = len(seq)
    if n < len(spacer):
        return []
    search = seq + seq[:len(spacer)-1] if circular else seq
    loci = {}
    for query in {spacer, str(Seq(spacer).reverse_complement())}:
        for match in re.finditer('(?=(' + query + '))', search):
            if match.start() >= n:
                break
            parts = _parts(match.start(), len(spacer), n)
            loci[tuple(tuple(p) for p in parts)] = parts
    return [loci[key] for key in sorted(loci)]


def evaluate_candidates(candidates: list[dict], seq: str, circular: bool, cas12: bool,
                        vector: MoleculeInput | None, limit: int, promoter: str) -> dict:
    validate_mismatch_limit(limit)
    if promoter not in ('unspecified', 'human_U6', 'other_pol_III', 'non_pol_III'):
        raise ValueError('transcription_promoter must be unspecified, human_U6, other_pol_III or non_pol_III')
    if cas12 and vector is not None:
        raise ValueError('NGG vector self-target screening supports SpCas9; do not apply it to AsCas12a')
    target_sites = pam_sites(seq, circular, cas12)
    vec = as_molecule(vector) if vector is not None else None
    vec_seq = str(vec.seq).upper() if vec is not None else ''
    if vec is not None and not vec_seq:
        raise ValueError('Vector sequence must not be empty')
    vector_sites = pam_sites(vec_seq, vec.topology == 'circular') if vec is not None else []
    ambiguous_target = sum(base not in 'ACGT' for base in seq)
    ambiguous_vector = sum(base not in 'ACGT' for base in vec_seq)
    for candidate in candidates:
        spacer = candidate['spacer']
        loci = exact_loci(seq, spacer, circular)
        matches = [h for h in matching_sites(spacer, target_sites, limit)
                   if (h['site_start_0based'], h['strand']) !=
                   (candidate['target_interval_0based'][0], candidate['strand'])]
        self_target = vector_report(spacer, vector_sites, limit, ambiguous_vector) if vec is not None else {
            'self_target_status': 'NOT_SUPPLIED', 'exact_match_count': None, 'near_match_count': None,
            'matches': [], 'search_complete': False, 'warnings': ['No vector supplied; self-targeting not checked.']}
        gc_extreme = not 20 <= candidate['gc_percent'] <= 80
        u6_non_g = promoter == 'human_U6' and spacer[0] != 'G'
        poly_risk = candidate['has_poly_t'] and promoter != 'non_pol_III'
        candidate['evaluation'] = {
            'gc': {'percent': candidate['gc_percent'], 'preferred_range_percent': [20, 80],
                   'outside_preferred_range': gc_extreme, 'source_ids': ['crisprDesign']},
            'pol_iii_poly_t': {'present': candidate['has_poly_t'], 'risk_flag': poly_risk,
                               'promoter_context': promoter, 'source_ids': ['crisprDesign']},
            'five_prime_base': {'base': spacer[0], 'preferred_base': 'G' if promoter == 'human_U6' else None,
                                 'preference_applied': promoter == 'human_U6', 'source_ids': ['human_U6']},
            'target_uniqueness': {'exact_locus_count': len(loci), 'unique': len(loci) == 1 and not ambiguous_target,
                                  'loci_parts_0based': loci, 'search_complete': not ambiguous_target,
                                  'scope': 'Entire supplied target, both strands, PAM-independent', 'source_ids': ['crisprDesign']},
            'target_secondary_sites': {'matches': matches, 'max_mismatches': limit,
                                      'search_complete': not ambiguous_target, 'source_ids': ['crisprDesign']},
            'vector_self_target': self_target,
        }
        candidate['warnings'].extend(self_target['warnings'])
        if poly_risk:
            candidate['warnings'].append('TTTT may terminate Pol III transcription; promoter-dependent risk, sequence not changed.')
        if gc_extreme:
            candidate['warnings'].append('GC outside crisprDesign preferred 20–80% range; not a measured activity prediction.')
        if u6_non_g:
            candidate['warnings'].append('Human U6 prefers a 5-prime G; spacer is reported unchanged.')
        if len(loci) > 1 or matches:
            candidate['warnings'].append('Additional target-sequence loci found; inspect exact and near-match evidence.')
        if ambiguous_target:
            candidate['warnings'].append('Target contains ambiguous bases; specificity screening is incomplete.')
        candidate['screening_key'] = [bool(self_target['exact_match_count']), bool(self_target['near_match_count']),
            not candidate['evaluation']['target_uniqueness']['unique'],
            sum(h['mismatches'] == 0 for h in matches), sum(h['mismatches'] > 0 for h in matches),
            bool(poly_risk), gc_extreme, u6_non_g]
    candidates.sort(key=lambda c: c['screening_key'])
    previous, rank = None, 0
    for candidate in candidates:
        if candidate['screening_key'] != previous:
            rank += 1
        candidate['screening_rank'] = rank
        previous = candidate['screening_key']
    return {'candidates': candidates, 'sources': SOURCES,
            'vector_version': vec.record_version if vec is not None else None,
            'ranking_policy': {'kind': 'lexicographic_screening_not_activity_prediction',
                'lower_is_preferred': True, 'ties_retained': True,
                'priority': ['vector_exact_match', 'vector_near_match', 'target_not_unique',
                    'target_exact_secondary_count', 'target_near_secondary_count', 'pol_iii_poly_t',
                    'gc_outside_20_to_80_percent', 'human_U6_non_G_start'],
                'basis': 'Explicit software screening policy, no empirical efficacy weights or cut-probability score'},
            'quality_score_status': 'UNAVAILABLE_UNCALIBRATED_LEGACY_HEURISTIC_REMOVED',
            'scope': 'Supplied sequences only; <=3 substitutions; no whole-genome guarantee, bulges, or wet-lab validation'}
