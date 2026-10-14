"""Source-labelled selection mapping from actual, complete annotated CDSs."""
import re
import hashlib
from functools import lru_cache

from core.tools.inspection import inspect_dna
from core.kits import KitCatalog
from pathlib import Path
from core.tools.sequence_ops import validate_cds_feature



# These are documented gene/cassette aliases, not plasmid identities. Selection
# is host-dependent; CDS structure never proves expression or resistance.




def mapping_rows():
    directory=Path(__file__).resolve().parents[1]
    digest=hashlib.sha256((directory/'rules/selection.json').read_bytes()).hexdigest()
    return _mapping_rows(digest)


@lru_cache(maxsize=1)
def _mapping_rows(rule_file_sha256):
    directory=Path(__file__).resolve().parents[1]
    catalog=KitCatalog([directory])
    entries=catalog.rules('genome-crispr','selection')
    mappings=[]
    for rule in entries[0]['rows']:
        marker=rule['action']['value']['marker_id']
        evaluated=catalog.evaluate_rules('genome-crispr','selection','before_culture_plan',{'marker_id':marker})
        if evaluated['diagnostics']:raise ValueError('Selection rules have unresolved diagnostics.')
        mappings.extend(hit['action']['value'] for hit in evaluated['hits'])
    return mappings


def marker_mappings():
    return [(row['marker_id'],row['pattern'],row['hosts'],row['auxotrophy']) for row in mapping_rows()]


def mapping_sources():
    return {key:value for row in mapping_rows() for key,value in row['sources'].items()}


def marker_ids(name):
    return [key for key, pattern, _, _ in marker_mappings()
            if re.search(r'(?<![a-z0-9])(?:' + pattern + r')(?![a-z0-9])', name, re.I)]


def selection_report(vector, genotype=None):
    observed = inspect_dna(vector).analysis
    conflicts = list(observed['warnings'])
    unmapped = [row for row in observed['selection_markers'] if not marker_ids(row['name'])]
    if genotype is not None and not isinstance(genotype, dict):
        raise ValueError('strain_genotype must be an explicit object, not an inferred strain name')
    genotype = genotype or {}
    unknown = set(genotype) - {'description', 'organism', 'existing_markers', 'auxotrophies'}
    if unknown:
        raise ValueError('Unsupported strain_genotype fields: ' + ', '.join(sorted(unknown)))
    for field in ('existing_markers', 'auxotrophies'):
        if field in genotype and (not isinstance(genotype[field], list) or
                                 any(not isinstance(item, str) or not item.strip() for item in genotype[field])):
            raise ValueError(field + ' must be an explicit list of marker names')
    organism = str(genotype.get('organism', '')).strip().lower()
    host = ('ecoli' if organism in ('e. coli', 'escherichia coli', 'ecoli') else
            'yeast' if organism in ('s. cerevisiae', 'saccharomyces cerevisiae') else None)
    existing = {key for value in genotype.get('existing_markers', []) for key in marker_ids(value)}
    unmapped_existing = [value for value in genotype.get('existing_markers', []) if not marker_ids(value)]
    aux = {value.lower() for value in genotype.get('auxotrophies', [])}
    rows = []
    for index, feature in enumerate(vector.features):
        if feature.type != 'CDS' or feature.location is None:
            continue
        name = next((str(feature.qualifiers[key][0]) for key in ('label', 'gene', 'product')
                     if feature.qualifiers.get(key)), '')
        keys = marker_ids(name)
        if not keys:
            # Known cassette labels absent from Core's antibiotic catalogue must
            # remain visible without assigning an unsupported drug/host mapping.
            if re.search(r'(?<![a-z0-9])(?:patmx\d*|natnt\d*)(?![a-z0-9])', name, re.I):
                unmapped.append({'name': name, 'feature_index': index,
                                 'reason': 'No supported drug/host mapping for this annotated cassette.'})
            continue
        audit = validate_cds_feature(feature, vector.seq)
        if not audit['valid'] or audit['partial'] or len(keys) != 1:
            conflicts.append({'code': 'SELECTION_MARKER_ANNOTATION_CONFLICT', 'name': name,
                              'feature_index': index, 'message': 'Annotation may be incorrect; no plate inferred.'})
            continue
        key, _, alternatives, requirement = next(row for row in marker_mappings() if row[0] == keys[0])
        compatibility = 'UNKNOWN'
        reason = '未提供基因型，无法判断兼容性' if not genotype else 'Declared host or relevant marker background is incomplete.'
        if host is not None and host not in alternatives:
            compatibility, reason = 'NOT_APPLICABLE', 'This marker is mapped to another host, not the declared recipient.'
        elif host in alternatives and 'existing_markers' in genotype and not unmapped_existing:
            if key in existing:
                compatibility, reason = 'CONFLICT', 'The declared strain already carries this selectable marker.'
            elif requirement and 'auxotrophies' not in genotype:
                reason = 'Auxotrophy status was not explicitly provided.'
            elif requirement and requirement not in aux:
                compatibility, reason = 'CONFLICT', 'The declared background does not supply the required auxotrophy.'
            else:
                compatibility, reason = 'DECLARED_COMPATIBLE', 'Conditional on the user-declared background; phenotype NOT_TESTED.'
        choices = [{'host': species, 'plate': plate, 'source': mapping_sources()[source],
                    'compatibility': compatibility if species == host else 'UNKNOWN',
                    'reason': reason if species == host else 'No explicit genotype for this host was supplied.'}
                   for species, (plate, source) in alternatives.items()]
        rows.append({'name': name, 'marker_id': key, 'feature_index': index,
                     'parts_0based': [[int(part.start), int(part.end)] for part in feature.location.parts],
                     'annotation_status': 'CDS_SUPPORTED', 'functional_status': 'NOT_TESTED',
                     'plate_options': choices, 'compatibility': compatibility, 'reason': reason})
    applicable = [row for row in rows if row['compatibility'] != 'NOT_APPLICABLE']
    status = ('CONFLICT' if conflicts or any(row['compatibility'] == 'CONFLICT' for row in applicable)
              else 'DECLARED_COMPATIBLE' if applicable and not unmapped and all(row['compatibility'] == 'DECLARED_COMPATIBLE' for row in applicable)
              else 'UNKNOWN')
    return {'status': status, 'markers': rows, 'annotation_conflicts': conflicts,
            'unmapped_markers': unmapped,
            'genotype_source': 'user supplied; not experimentally authenticated' if genotype else 'NOT_PROVIDED',
            'genotype': genotype, 'message': '未提供基因型，无法判断兼容性' if not genotype else
            'Only explicitly declared organism, existing markers and auxotrophies are used.',
            'recipient_host': host,
            'scope': 'Annotated complete CDS and literature mapping only; no expression, resistance or growth assay.'}
