"""Public DNA material: SeqRecord plus physical ends and explicit derivation.

SeqRecord is the sequence/annotation representation. Tools treat inputs as
read-only and construct new records; this is not Python access control.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, TypeAlias
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import Reference
from core.models.assembly_model import FragmentEnd
from core.models.construct_model import feature_to_dict


class ProteinSequence(str):
    """A protein analysis value; deliberately not accepted as DNA material."""


def position_data(position):
    data = {'kind': type(position).__name__, 'value': None}
    if data['kind'] != 'UnknownPosition':
        data['value'] = int(position)
    for key in ('_left', '_right'):
        if hasattr(position, key):
            data[key[1:]] = int(getattr(position, key))
    if hasattr(position, 'position_choices'):
        data['choices'] = [position_data(p) for p in position.position_choices]
    return data


def position_from_data(data):
    from Bio import SeqFeature as sf
    name, value = data['kind'], data['value']
    if name == 'UnknownPosition':
        return sf.UnknownPosition()
    if name in ('ExactPosition', 'BeforePosition', 'AfterPosition', 'UncertainPosition'):
        return getattr(sf, name)(value)
    if name in ('WithinPosition', 'BetweenPosition'):
        return getattr(sf, name)(value, data['left'], data['right'])
    if name == 'OneOfPosition':
        return sf.OneOfPosition(value, [position_from_data(p) for p in data['choices']])
    raise ValueError(f'Unsupported coordinate position: {name}')


def feature_data(feature):
    def integer(position):
        return None if type(position).__name__ == 'UnknownPosition' else int(position)
    parts = [{'start0': integer(p.start), 'end0': integer(p.end), 'strand': p.strand,
              'start_position': position_data(p.start), 'end_position': position_data(p.end),
              'ref': p.ref, 'ref_db': p.ref_db} for p in feature.location.parts]
    labels = feature.qualifiers.get('label', feature.qualifiers.get('gene', [feature.id]))
    name = labels[0] if isinstance(labels, list) else labels
    return {'name': name, 'type': feature.type, 'id': feature.id,
            'strand': feature.location.strand, 'qualifiers': copy.deepcopy(feature.qualifiers),
            'location': {'coordinate_system': '0-based-half-open',
                         'operator': getattr(feature.location, 'operator', None), 'parts': parts}}


def json_metadata(value):
    if isinstance(value, Reference):
        return {'__bio_reference__': True, 'authors': value.authors, 'title': value.title,
                'journal': value.journal, 'medline_id': value.medline_id,
                'pubmed_id': value.pubmed_id, 'comment': value.comment,
                'location': [feature_data(__import__('Bio.SeqFeature', fromlist=['SeqFeature']).SeqFeature(loc))['location']
                             for loc in value.location]}
    if isinstance(value, dict):
        return {key: json_metadata(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_metadata(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f'Unsupported molecular metadata type: {type(value).__name__}')


def restore_metadata(value):
    from Bio.SeqFeature import FeatureLocation, CompoundLocation
    if isinstance(value, dict) and value.get('__bio_reference__'):
        reference = Reference()
        for field in ('authors', 'title', 'journal', 'medline_id', 'pubmed_id', 'comment'):
            setattr(reference, field, value[field])
        for loc in value['location']:
            parts = [FeatureLocation(position_from_data(p['start_position']), position_from_data(p['end_position']),
                                     strand=p['strand'], ref=p['ref'], ref_db=p['ref_db']) for p in loc['parts']]
            reference.location.append(parts[0] if len(parts) == 1 else CompoundLocation(parts, operator=loc['operator']))
        return reference
    if isinstance(value, dict):
        return {key: restore_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_metadata(item) for item in value]
    return value


class Molecule(SeqRecord):
    def __init__(self, record, *record_args, strandedness=None, left_end=None,
                 right_end=None, source_refs=(), operation=None, _owned=False, **record_kwargs):
        # Biopython constructs subclasses through the standard SeqRecord
        # signature during slicing/reversal. Native intermediates have unknown
        # physical metadata until the public transformation sets it explicitly.
        if not isinstance(record, SeqRecord):
            record = SeqRecord(record, *record_args, **record_kwargs)
            _owned = True
        elif record_args or record_kwargs:
            raise TypeError('SeqRecord material accepts molecular metadata only')
        bases = str(record.seq).upper()
        if record.annotations.get('molecule_type', 'DNA').upper() not in ('DNA', 'DS-DNA', 'SS-DNA'):
            raise ValueError('Molecule requires DNA, not protein or RNA')
        if any(base not in 'ACGTRYSWKMBDHVN' for base in bases):
            raise ValueError('Molecule contains non-DNA characters')
        normalized_sequence = record.seq if str(record.seq) == bases else Seq(bases)
        super().__init__(normalized_sequence, id=record.id, name=record.name,
                         description=record.description, dbxrefs=list(record.dbxrefs),
                         features=record.features if _owned else copy.deepcopy(record.features),
                         annotations=record.annotations if _owned else copy.deepcopy(record.annotations),
                         letter_annotations=record.letter_annotations if _owned else copy.deepcopy(record.letter_annotations))
        self.annotations.setdefault('molecule_type', 'DNA')
        self.annotations.setdefault('topology', None)
        topology = self.annotations.get('topology')
        if topology not in (None, 'linear', 'circular'):
            raise ValueError('Molecule topology must be linear, circular or unknown')
        if strandedness not in (None, 'single', 'double'):
            raise ValueError('Molecule strandedness must be single, double or unknown')
        if topology == 'circular' and (left_end is not None or right_end is not None):
            raise ValueError('Circular molecules have no exposed ends')
        if strandedness == 'single' and (left_end is not None or right_end is not None):
            raise ValueError('Single strands do not have double-strand restriction ends')
        for end in (left_end, right_end):
            if end is not None and not isinstance(end, FragmentEnd):
                raise TypeError('Molecule ends must use FragmentEnd')
            if end is not None and end.cut_boundary is not None and not 0 <= end.cut_boundary <= len(record):
                raise ValueError('Molecular end cut boundary lies outside the product')
        text=str(record.seq)
        if left_end is not None and left_end.kind=="5'-overhang" and not text.startswith(left_end.overhang_sequence):
            raise ValueError('Reference top strand does not contain its declared left 5-prime extension')
        if right_end is not None and right_end.kind=="3'-overhang" and not text.endswith(right_end.overhang_sequence):
            raise ValueError('Reference top strand does not contain its declared right 3-prime extension')
        self.strandedness = strandedness
        self.left_end = copy.deepcopy(left_end)
        self.right_end = copy.deepcopy(right_end)
        self.source_refs = tuple(copy.deepcopy(list(source_refs)))
        self.operation = operation

    @property
    def topology(self):
        return self.annotations.get('topology')

    @property
    def sequence_sha256(self):
        return hashlib.sha256(str(self.seq).upper().encode('ascii')).hexdigest().upper()

    @property
    def record_version(self):
        data = {'sequence': str(self.seq), 'id': self.id, 'name': self.name,
                'description': self.description, 'annotations': self.annotations,
                'features': [(f.type, str(f.location), f.id, f.qualifiers) for f in self.features],
                'dbxrefs': self.dbxrefs, 'letter_annotations': dict(self.letter_annotations),
                'strandedness': self.strandedness, 'source_refs': self.source_refs,
                'left_end': self.left_end.to_dict() if self.left_end else None,
                'right_end': self.right_end.to_dict() if self.right_end else None,
                'operation': self.operation}
        return hashlib.sha256(json.dumps(json_metadata(data), sort_keys=True, ensure_ascii=False,
                                        separators=(',', ':')).encode('utf-8')).hexdigest().upper()

    @property
    def molecule_id(self):
        # A reproducible model-version anchor, not authenticated sample identity.
        return f'{self.id}:{self.record_version}'

    def to_dict(self, include_version=True):
        result = {
            'id': self.id, 'name': self.name, 'description': self.description,
            'sequence': str(self.seq), 'topology': self.topology,
            'strandedness': self.strandedness,
            'coordinate_system': '0-based-half-open',
            'ends': None if self.topology == 'circular' or self.strandedness=='single' else {
                'left': self.left_end.to_dict() if self.left_end is not None else None,
                'right': self.right_end.to_dict() if self.right_end is not None else None},
            'features': [feature_data(f) for f in self.features],
            'annotations': json_metadata(self.annotations), 'dbxrefs': list(self.dbxrefs),
            'letter_annotations': copy.deepcopy(dict(self.letter_annotations)),
            'source_refs': copy.deepcopy(list(self.source_refs)), 'operation': self.operation,
        }
        if include_version:
            result['record_version'] = self.record_version
        return result


MoleculeInput: TypeAlias = Molecule | SeqRecord | Seq | str | Path | dict[str, Any]


def as_molecule(value: MoleculeInput, *, default_topology=None) -> Molecule:
    """Import legacy/file/wire inputs once; internal material reuse is by reference."""
    if isinstance(value, Molecule):
        return value
    if isinstance(value, ProteinSequence):
        raise ValueError('Protein analysis cannot be used as DNA material')
    if isinstance(value,dict) and value.get('coordinate_system','0-based-half-open') != '0-based-half-open':
        raise ValueError('Convert external coordinates explicitly before creating a Molecule')
    from core.io.input_resolution import resolve_sequence_record
    if isinstance(value, Seq):
        value = SeqRecord(value, annotations={'molecule_type': 'DNA'})
    record = value if isinstance(value, SeqRecord) else resolve_sequence_record(value, default_topology=default_topology)
    if isinstance(record, Molecule):
        return record
    metadata = value if isinstance(value, dict) else {}
    ends = metadata.get('ends') or {}
    def end(key):
        info = ends.get(key)
        return FragmentEnd(**info) if info else None
    molecule = Molecule(record, strandedness=metadata.get('strandedness', record.annotations.get('strandedness')),
                        left_end=end('left'), right_end=end('right'),
                        source_refs=metadata.get('source_refs', ()), operation=metadata.get('operation'))
    if 'record_version' in metadata and metadata['record_version'] != molecule.record_version:
        raise ValueError('Serialized molecule version does not match its material information')
    return molecule


def derived_molecule(record: SeqRecord, sources=(), *, operation: str,
                     strandedness=None, left_end=None, right_end=None, mappings=None) -> Molecule:
    refs = []
    for index, source in enumerate(sources):
        material = as_molecule(source)
        version = material.record_version
        refs.append({'molecule_id': f'{material.id}:{version}', 'record_version': version,
                     'sequence_sha256': material.sequence_sha256, 'input_index': index,
                     'mapping': mappings[index] if mappings else None})
    return Molecule(record, strandedness=strandedness, left_end=left_end,
                    right_end=right_end, source_refs=refs, operation=operation, _owned=True)
