"""Locate, replace and check existing 20 nt guide cassettes from actual DNA."""
from __future__ import annotations

import copy
import re

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, ExactPosition, FeatureLocation, SeqFeature

from core.models.molecule import MoleculeInput, as_molecule, derived_molecule, feature_data
from core.tools.result import ToolResult, check_result

# SpCas9 scaffold prefix shared with the published pML104 method.
# Hu et al. 2018: https://pmc.ncbi.nlm.nih.gov/articles/PMC5868978/
# Domain anchor, not plasmid identity; variants accept an explicit scaffold_seq.
SPCAS9_SCAFFOLD_PREFIX = 'GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGC'


def _label(feature):
    for key in ('label', 'gene', 'product'):
        value = feature.qualifiers.get(key)
        if value:
            return str(value[0] if isinstance(value, list) else value)
    return feature.type


def _location(start, length, strand, n):
    """Convert transcription coordinates to biologically ordered reference parts."""
    runs = []
    for i in range(length):
        pos = (start+i) % n if strand == 1 else n-1-((start+i) % n)
        if runs and pos == runs[-1][-1] + strand:
            runs[-1].append(pos)
        else:
            runs.append([pos])
    parts = [FeatureLocation(min(run), max(run)+1, strand=strand) for run in runs]
    return parts[0] if len(parts) == 1 else CompoundLocation(parts)


def _parts(location):
    return [[int(p.start), int(p.end)] for p in location.parts]


def _overlaps(feature, location):
    return feature.location is not None and any(
        int(a.start) < int(b.end) and int(b.start) < int(a.end)
        for a in feature.location.parts for b in location.parts)


def _locate(record, promoter_name, promoter_end_0based, transcription_strand, scaffold_seq):
    sequence, n = str(record.seq), len(record)
    scaffold = str(scaffold_seq).strip().upper()
    if len(scaffold) < 20 or set(scaffold) - set('ACGT'):
        raise ValueError('scaffold_seq requires at least 20 explicit A/C/G/T bases')
    if transcription_strand not in (None, 1, -1):
        raise ValueError('transcription_strand must be +1 or -1')
    if promoter_end_0based is not None and not 0 <= promoter_end_0based <= n:
        raise ValueError('promoter_end_0based lies outside the vector')
    if n < 20 + len(scaffold):
        raise ValueError('Vector cannot contain a 20 nt guide cassette and scaffold anchor')
    promoters = []
    for feature in record.features:
        is_promoter = feature.type == 'promoter' or (
            feature.type in ('regulatory', 'misc_feature') and
            ('promoter' in _label(feature).lower() or
             'promoter' in feature.qualifiers.get('regulatory_class', [])))
        if promoter_name is not None:
            is_promoter = _label(feature).casefold() == promoter_name.casefold()
        if not is_promoter or feature.location is None:
            continue
        if any(type(p.start) is not ExactPosition or type(p.end) is not ExactPosition or p.ref
               for p in feature.location.parts):
            continue
        if any(not 0 <= int(p.start) < int(p.end) <= n for p in feature.location.parts):
            continue
        strand = transcription_strand or feature.location.strand
        if strand not in (1, -1):
            continue
        last = feature.location.parts[-1]
        boundary = int(last.end) if strand == 1 else int(last.start)
        if promoter_end_0based is None or boundary == promoter_end_0based:
            promoters.append((feature, boundary, strand))
    if promoter_name is not None and not promoters:
        raise ValueError('Named promoter is missing, undirected or has unsupported coordinates')
    if promoter_end_0based is not None and promoter_name is None:
        if transcription_strand is None:
            raise ValueError('An explicit promoter boundary requires transcription_strand')
        promoters = [(None, promoter_end_0based, transcription_strand)]
    candidates = []
    for feature, boundary, strand in promoters:
        oriented = sequence if strand == 1 else str(Seq(sequence).reverse_complement())
        start = boundary if strand == 1 else n-boundary
        if record.topology == 'circular':
            start %= n
            view = oriented + oriented[:20 + len(scaffold)]
        else:
            view = oriented
        if view[start+20:start+20+len(scaffold)] != scaffold:
            continue
        spacer = view[start:start+20]
        if len(spacer) != 20 or set(spacer) - set('ACGT'):
            continue
        location = _location(start, 20, strand, n)
        candidates.append({'promoter': _label(feature) if feature is not None else None,
            'promoter_end_0based': boundary, 'transcription_strand': strand,
            'spacer': spacer, 'spacer_parts_0based': _parts(location),
            'scaffold_anchor': scaffold,
            'scaffold_parts_0based': _parts(_location(start+20, len(scaffold), strand, n)),
            '_location': location})
    # Duplicate annotations at the same promoter describe one sequence cassette.
    unique = {tuple(tuple(p) for p in c['spacer_parts_0based']) + (c['transcription_strand'],): c
              for c in candidates}
    if not unique:
        raise ValueError('No cassette has exactly 20 nt after a directed promoter and before scaffold_seq')
    if len(unique) != 1:
        raise ValueError('Guide cassette is ambiguous; select promoter_name or an explicit directed boundary')
    return next(iter(unique.values()))


def _annotation_warnings(record, location, strand):
    warnings = []
    for feature in record.features:
        if not _overlaps(feature, location):
            continue
        if re.search(r'grna|sgrna|spacer|guide', _label(feature), re.I) and feature.location.strand in (1, -1) and feature.location.strand != strand:
            warnings.append({'code': 'GRNA_ANNOTATION_STRAND_CONFLICT',
                'message': 'Annotation may be incorrect (注释可能有误): guide strand conflicts with promoter-downstream sequence.',
                'feature': feature_data(feature), 'sequence_transcription_strand': strand})
    return warnings


def replace_grna_spacer(
    vector_record_or_seq: MoleculeInput, spacer_seq: str,
    promoter_name: str | None = None, promoter_end_0based: int | None = None,
    transcription_strand: int | None = None,
    scaffold_seq: str = SPCAS9_SCAFFOLD_PREFIX,
) -> ToolResult:
    """Replace only the existing 20 nt promoter-to-scaffold spacer.

    Auto-select a uniquely directed annotated promoter with the actual scaffold
    anchor 20 bases downstream. Unannotated templates need an explicit promoter
    3-prime boundary and transcription strand. Coordinates are 0-based half-open.
    This edits a sequence model; it does not establish physical preparation.
    """
    spacer = str(spacer_seq).strip().upper()
    if len(spacer) != 20 or set(spacer) - set('ACGT'):
        raise ValueError('Replacement spacer requires exactly 20 nt of A/C/G/T')
    source = as_molecule(vector_record_or_seq)
    cassette = _locate(source, promoter_name, promoter_end_0based, transcription_strand, scaffold_seq)
    location = cassette.pop('_location')
    strand = cassette['transcription_strand']
    warnings = _annotation_warnings(source, location, strand)
    product = copy.deepcopy(source)
    bases = list(str(source.seq))
    for pos, base in zip(location, spacer):
        bases[pos] = base if strand == 1 else str(Seq(base).complement())
    product.seq = Seq(''.join(bases))
    changes, kept = [], []
    for feature in product.features:
        if _overlaps(feature, location):
            if feature.type == 'source' and len(feature) > 20:
                kept.append(feature)
            else:
                changes.append({'feature': feature_data(feature), 'action': 'retired',
                    'reason': 'Overlaps replaced spacer; original annotation retained in operation log.'})
        else:
            kept.append(feature)
    product.features = kept
    product.features.append(SeqFeature(location, type='misc_RNA', qualifiers={
        'label': ['gRNA spacer'], 'original_spacer': [cassette['spacer']], 'spacer': [spacer],
        'note': [f"Replaced 20 nt spacer {cassette['spacer']} with {spacer}; other DNA unchanged."]}))
    for key, values in product.letter_annotations.items():
        updated = list(values)
        for pos in location:
            updated[pos] = None
        product.letter_annotations[key] = updated
    material = derived_molecule(product, [source], operation='replace_grna_spacer',
        strandedness=source.strandedness, left_end=source.left_end, right_end=source.right_end,
        mappings=[{'source_interval_0based': [0, len(source)], 'product_interval_0based': [0, len(source)],
                   'strand': 1, 'replaced_parts_0based': _parts(location)}])
    replacement = {'before': cassette['spacer'], 'after': spacer, 'parts_0based': _parts(location),
        'transcription_strand': strand, 'length_delta': 0, 'outside_window_unchanged': True}
    return ToolResult(products=[material], analysis={**cassette, 'spacer': spacer,
        'replacement': replacement, 'annotation_changes': changes, 'warnings': warnings,
        'scope_note': 'Sequence replacement; physical preparation is not established.'},
        checks=[check_result('spacer_replacement', subject=material, status='PASSED', scope='sequence_model',
            conditions={'source_version': source.record_version}, details=replacement)])


def _target_matches(target, spacer, pam_pattern, query_role):
    seq, n = str(target.seq), len(target)
    if n < 20:
        return []
    alphabet = {'A':'A', 'C':'C', 'G':'G', 'T':'T', 'R':'AG', 'Y':'CT', 'S':'GC', 'W':'AT',
                'K':'GT', 'M':'AC', 'B':'CGT', 'D':'AGT', 'H':'ACT', 'V':'ACG', 'N':'ACGT'}
    regex = ''.join('['+alphabet[c]+']' for c in pam_pattern)
    hits = []
    for strand in (1, -1):
        oriented = seq if strand == 1 else str(Seq(seq).reverse_complement())
        view = oriented + oriented[:19+len(pam_pattern)] if target.topology == 'circular' else oriented
        for match in re.finditer('(?='+spacer+')', view):
            start = match.start()
            if start >= n:
                break
            pam = view[start+20:start+20+len(pam_pattern)]
            hits.append({'query_role': query_role, 'strand': strand, 'rna_binding_strand': -strand,
                'protospacer_parts_0based': _parts(_location(start, 20, strand, n)),
                'pam_parts_0based': _parts(_location(start+20, len(pam), strand, n)) if pam else [],
                'pam': pam, 'pam_complete': len(pam) == len(pam_pattern),
                'pam_valid': re.fullmatch(regex, pam) is not None})
    return hits


def check_grna(
    vector_record_or_seq: MoleculeInput, target_seq_or_file: MoleculeInput,
    promoter_name: str | None = None, promoter_end_0based: int | None = None,
    transcription_strand: int | None = None,
    scaffold_seq: str = SPCAS9_SCAFFOLD_PREFIX, pam_pattern: str = 'NGG',
) -> ToolResult:
    """Check transcribed 20 nt DNA against both target strands and a 3-prime PAM.

    'strand' identifies target DNA identical to spacer; RNA binds its opposite.
    Default NGG is wild-type SpCas9. Retain all exact and reverse-insert hits;
    this does not predict mismatch/genome-wide effects or validate full scaffold.
    """
    pam = str(pam_pattern).strip().upper()
    if not pam or set(pam) - set('ACGTRYSWKMBDHVN'):
        raise ValueError('pam_pattern must be an explicit IUPAC DNA motif on the 3-prime side')
    vector, target = as_molecule(vector_record_or_seq), as_molecule(target_seq_or_file)
    cassette = _locate(vector, promoter_name, promoter_end_0based, transcription_strand, scaffold_seq)
    location = cassette.pop('_location')
    spacer = cassette['spacer']
    warnings = _annotation_warnings(vector, location, cassette['transcription_strand'])
    matches = _target_matches(target, spacer, pam, 'transcribed_spacer')
    reverse_hits = _target_matches(target, str(Seq(spacer).reverse_complement()), pam, 'reverse_complement_spacer')
    valid = [m for m in matches if m['pam_valid']]
    reverse_valid = [m for m in reverse_hits if m['pam_valid']]
    if valid:
        direction, correct, status = 'CORRECT', True, 'PASSED'
        if len(valid) > 1:
            warnings.append({'code': 'MULTIPLE_VALID_TARGETS', 'message': 'Multiple exact PAM-compatible loci occur in supplied target.'})
        if reverse_valid:
            warnings.append({'code': 'BOTH_ORIENTATIONS_HAVE_TARGETS', 'message': 'Both orientations have PAM-compatible targets; intended locus is not inferred.'})
    elif reverse_valid:
        direction, correct, status = 'REVERSED', False, 'FAILED'
    elif matches or reverse_hits:
        direction, correct, status = 'INVALID_PAM', None, 'FAILED'
    else:
        direction, correct, status = 'NO_TARGET_MATCH', None, 'INCOMPLETE'
    analysis = {**cassette, 'result_kind': 'verification', 'subject': vector, 'target_version': target.record_version,
        'target_matches': matches + reverse_hits, 'pam_pattern': pam,
        'direction_status': direction, 'direction_correct': correct, 'warnings': warnings,
        'scope_note': 'Exact matching in supplied target with a 3-prime PAM; scaffold anchor is not full scaffold/function validation.'}
    return ToolResult(analysis=analysis, checks=[check_result('existing_grna', subject=vector,
        status=status, scope='sequence_model', conditions={'target_version': target.record_version,
            'pam_pattern': pam, 'scaffold_seq': scaffold_seq}, details=analysis)])
