"""Version-bound sequence similarity and coding differences, without phenotype inference."""
from __future__ import annotations
from Bio.Align import PairwiseAligner
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from core.models.molecule import MoleculeInput, as_molecule
from core.tools.result import ToolResult
from core.tools.feature_ops import get_feature
from core.tools.sequence_ops import DNA_IUPAC_ALPHABET, validate_cds_feature


def _region(source, feature_name, coding, table):
    if feature_name is None and coding and any(f.type == 'CDS' for f in source.features):
        feature_name = 'CDS'  # The existing selector rejects multiple candidates.
    feature = None
    if feature_name is not None:
        selected = get_feature(source, feature_name)
        index = selected.analysis['matches'][0]['feature_index']
        feature = source.features[index]
        text = str(feature.extract(source.seq)).upper()
        parts = [[int(p.start), int(p.end), p.strand] for p in feature.location.parts]
    else:
        text = str(source.seq).upper()
        parts = [[0, len(source), 1]]
    audit = None
    if coding:
        if feature is not None and feature.type != 'CDS':
            raise ValueError('Coding comparison requires a CDS feature')
        if feature is None:
            feature = SeqFeature(FeatureLocation(0, len(source), strand=1), type='CDS',
                qualifiers={'transl_table': [str(table)]} if table is not None else {})
        elif table is not None and feature.qualifiers.get('transl_table'):
            declared = feature.qualifiers['transl_table']
            if declared != [str(table)] and declared != [table]:
                raise ValueError('CDS translation table conflicts with original annotation')
        elif table is not None:
            import copy
            feature = copy.deepcopy(feature)
            feature.qualifiers['transl_table'] = [str(table)]
        audit = validate_cds_feature(feature, source.seq)
        if not audit['valid'] or audit['partial']:
            raise ValueError('CDS comparison requires complete validated coding sequences: ' +
                             ', '.join(error['code'] for error in audit['errors']))
        text = audit['coding_sequence']
    return text, {'feature': feature_name, 'source_parts': parts,
                  'alignment_coordinates': '0-based half-open on the selected/extracted sequence'}, audit


def compare_sequences(query: MoleculeInput, reference: MoleculeInput, mode: str = 'local',
                      query_feature: str | None = None, reference_feature: str | None = None,
                      coding: bool = False, table: int | None = None,
                      search_reverse_complement: bool = True,
                      max_alignment_cells: int = 25_000_000) -> ToolResult:
    """Compare actual regions; local mode answers short-region-in-long-reference questions.

    Reports the best alignment, not unique placement or experimental function.
    Coding mode uses the shared complete-CDS frame/table contract. Coordinates
    refer to the supplied record or extracted feature, never an assumed genome.
    The explicit cell limit rejects large requests without truncating sequences.
    """
    if mode not in ('local', 'global'):
        raise ValueError('Alignment mode must be local or global')
    if type(max_alignment_cells) is not int or max_alignment_cells <= 0:
        raise ValueError('Alignment cell limit must be a positive integer')
    original_query, original_reference = as_molecule(query), as_molecule(reference)
    q, q_region, q_cds = _region(original_query, query_feature, coding, table)
    r, r_region, r_cds = _region(original_reference, reference_feature, coding, table)
    if not q or not r or set(q + r) - DNA_IUPAC_ALPHABET:
        raise ValueError('Comparison needs nonempty IUPAC DNA sequences')
    if len(q) * len(r) > max_alignment_cells:
        raise ValueError(f'Alignment cells exceed explicit limit {max_alignment_cells}; select a smaller actual reference region')
    aligner = PairwiseAligner(mode=mode, match_score=2, mismatch_score=-1,
                             open_gap_score=-5, extend_gap_score=-1)
    choices = [(1, q)]
    if search_reverse_complement and not coding:
        choices.append((-1, str(Seq(q).reverse_complement())))
    best = None
    for orientation, text in choices:
        alignment = next(iter(aligner.align(r, text)), None)
        if alignment is not None and (best is None or alignment.score > best[2].score):
            best = orientation, text, alignment
    matches = mismatches = gaps = covered = uncertain = 0
    reference_interval = query_interval = None
    score = 0.0
    orientation = 1
    if best is not None:
        orientation, text, alignment = best
        coordinates = [[int(n) for n in row] for row in alignment.coordinates]
        reference_interval = [coordinates[0][0], coordinates[0][-1]]
        query_interval = [coordinates[1][0], coordinates[1][-1]]
        score = float(alignment.score)
        for i in range(len(coordinates[0]) - 1):
            a, b = coordinates[0][i:i+2]
            c, d = coordinates[1][i:i+2]
            if b > a and d > c:
                covered += d - c
                for left, right in zip(r[a:b], text[c:d]):
                    if left not in 'ACGT' or right not in 'ACGT': uncertain += 1
                    elif left == right: matches += 1
                    else: mismatches += 1
            else:
                gaps += (b - a) + (d - c)
        if orientation == -1:
            query_interval = [len(q) - query_interval[1], len(q) - query_interval[0]]
    columns = matches + mismatches + gaps + uncertain
    analysis = {
        'mode': mode, 'query_version': original_query.record_version,
        'reference_version': original_reference.record_version,
        'query_region': q_region, 'reference_region': r_region,
        'query_length': len(q), 'reference_length': len(r), 'query_orientation': orientation,
        'query_interval_0based': query_interval, 'reference_interval_0based': reference_interval,
        'matches': matches, 'mismatches': mismatches, 'gap_bases': gaps, 'uncertain_bases': uncertain,
        'query_coverage_pct': round(100.0 * covered / len(q), 4),
        'identity_pct': round(100.0 * matches / columns, 4) if columns else 0.0,
        'alignment_score': score, 'max_alignment_cells': max_alignment_cells,
        'placement_uniqueness': 'NOT_CHECKED', 'experimental_function': 'NOT_CHECKED',
        'interpretation': 'A global score includes unmatched flanks; use local mode for region-in-reference similarity. '
                          'Alignment uses supplied sequence coordinates, without circular-origin wrapping.',
    }
    if coding:
        changed = []
        comparable = len(q) == len(r) and q_cds['transl_table'] == r_cds['transl_table']
        if comparable:
            for start in range(0, len(q), 3):
                left, right = q[start:start+3], r[start:start+3]
                if left == right: continue
                position = start // 3
                qa = q_cds['translation'][position] if position < len(q_cds['translation']) else '*'
                ra = r_cds['translation'][position] if position < len(r_cds['translation']) else '*'
                changed.append({'codon_1based': position + 1, 'query_codon': left, 'reference_codon': right,
                    'query_amino_acid': qa, 'reference_amino_acid': ra, 'synonymous': qa == ra})
        analysis['coding_comparison'] = {
            'query_table': q_cds['transl_table'], 'reference_table': r_cds['transl_table'],
            'query_frame_offset': q_cds['frame_offset'], 'reference_frame_offset': r_cds['frame_offset'],
            'protein_identical': q_cds['translation'] == r_cds['translation'],
            'query_translation': q_cds['translation'], 'reference_translation': r_cds['translation'],
            'changed_codons': changed,
            'all_changed_codons_synonymous': all(item['synonymous'] for item in changed) if comparable else None,
            'codon_comparison': 'positionwise complete-CDS comparison' if comparable else 'INCOMPLETE: length or code differs',
            'phenotype': 'NOT_CHECKED',
        }
    return ToolResult(analysis=analysis)
