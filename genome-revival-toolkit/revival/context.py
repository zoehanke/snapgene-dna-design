"""Declared project knowledge and checked local reference identities remain separate."""
from __future__ import annotations

import gzip
import json
import copy
from pathlib import Path

from revival.bootstrap import CORE_VERSION
from Bio import SeqIO
from core.models.molecule import as_molecule
from core.tools.sequence_ops import extract_subsequence
from evidence_trace.models import file_digest


def read_json(path):
    with Path(path).open(encoding='utf-8-sig', errors='replace') as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError('Input must be a JSON object.')
    return value


class ProjectContext:
    def __init__(self, data, base_dir='.', source_path=None):
        if data.get('schema_version', 'genome-revival-context-v1') != 'genome-revival-context-v1':
            raise ValueError('Unsupported Project Context version.')
        self.data = copy.deepcopy(data)
        data = self.data
        self.base_dir = Path(base_dir).resolve()
        self.source_path = Path(source_path).resolve() if source_path else None
        self.context_file_sha256 = file_digest(self.source_path) if self.source_path else None
        self.project = data.get('project', {})
        self.strains = data.get('strains', {})
        self.facts = data.get('facts', [])
        self.routes = data.get('routes', [])
        if not isinstance(self.project, dict) or not isinstance(self.strains, dict):
            raise ValueError('project and strains must be objects.')
        if not isinstance(self.facts, list) or not isinstance(self.routes, list):
            raise ValueError('facts and routes must be lists.')
        self.references = {}
        self._loaded = {}
        self._identities = {}
        references = data.get('references', {})
        if not isinstance(references, dict):
            raise ValueError('references must map material IDs to reference objects.')
        for key, value in references.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(value, dict):
                raise ValueError('Each reference needs a nonempty ID and an object.')
            entry = dict(value, id=key)
            if not isinstance(entry.get('path'), str) or not entry['path'].strip():
                raise ValueError(f'Reference {key}: provide its actual DNA file path.')
            entry['path'] = str((self.base_dir / entry['path']).resolve())
            if entry.get('strain_id') and entry['strain_id'] not in self.strains:
                raise ValueError(f'Reference {key}: unknown declared strain_id.')
            self.references[key] = entry

    @classmethod
    def load(cls, path):
        path = Path(path).resolve()
        before = file_digest(path)
        result = cls(read_json(path), path.parent, path)
        if result.context_file_sha256 != before:
            raise ValueError('Context file changed while loading; reload the current file.')
        return result

    def _check_context_version(self):
        if self.source_path and (not self.source_path.is_file() or file_digest(self.source_path) != self.context_file_sha256):
            raise ValueError('Context file changed after loading; reload and recheck its current references/regions.')

    def material(self, reference_id):
        self._check_context_version()
        if reference_id not in self.references:
            raise ValueError(f'Unknown reference {reference_id}; available: {", ".join(self.references)}')
        entry = self.references[reference_id]
        path = Path(entry['path'])
        if not path.is_file():
            raise ValueError(f'Reference {reference_id}: file unavailable: {path.name}')
        actual_sha = file_digest(path)
        if entry.get('sha256') and str(entry['sha256']).lower() != actual_sha.lower():
            raise ValueError(f'Reference {reference_id}: file differs from the declared SHA-256.')
        if reference_id in self._loaded:
            if self._identities[reference_id]['file_sha256'] != actual_sha:
                raise ValueError(f'Reference {reference_id}: file changed during this context; reload and recheck.')
            return self._loaded[reference_id]
        suffixes = ''.join(path.suffixes).lower()
        fasta = suffixes.endswith(('.fa', '.fasta', '.fna', '.fa.gz', '.fasta.gz', '.fna.gz'))
        genbank = suffixes.endswith(('.gb', '.gbk', '.gbff', '.gb.gz', '.gbk.gz', '.gbff.gz'))
        if fasta or (genbank and entry.get('record_id')):
            uncompressed = suffixes[:-3] if suffixes.endswith('.gz') else suffixes
            format_name = 'genbank' if uncompressed.endswith(('.gb', '.gbk', '.gbff')) else 'fasta'
            opener = gzip.open if suffixes.endswith('.gz') else open
            with opener(path, 'rt', encoding='utf-8', errors='replace') as handle:
                records = SeqIO.parse(handle, format_name)
                selected = None
                count = 0
                for record in records:
                    count += 1
                    if entry.get('record_id'):
                        if record.id == entry['record_id']:
                            if selected is not None:
                                raise ValueError(f'Reference {reference_id}: duplicate record_id.')
                            selected = record
                    elif selected is None:
                        selected = record
                    else:
                        raise ValueError(f'Reference {reference_id}: multiple records; supply record_id.')
                if selected is None:
                    raise ValueError(f'Reference {reference_id}: no requested sequence record.')
            material = as_molecule(selected)
        else:
            material = as_molecule(path)
        if entry.get('record_id') and material.id != entry['record_id']:
            raise ValueError(f'Reference {reference_id}: requested record_id does not match the actual record.')
        declared_topology = entry.get('topology')
        if declared_topology is not None:
            if declared_topology not in ('linear', 'circular'):
                raise ValueError(f'Reference {reference_id}: topology must be linear or circular.')
            if material.topology is not None and material.topology != declared_topology:
                raise ValueError(f'Reference {reference_id}: topology contradicts the actual file.')
            if material.topology is None:
                material = copy.deepcopy(material)
                material.annotations['topology'] = declared_topology
        parent_version = material.record_version
        region = entry.get('region')
        if region is not None:
            if not isinstance(region, dict) or any(type(region.get(k)) is not int for k in ('start0', 'end0')):
                raise ValueError(f'Reference {reference_id}: region requires integer start0/end0.')
            if not 0 <= region['start0'] < region['end0'] <= len(material):
                raise ValueError(f'Reference {reference_id}: region is outside the actual record.')
            if region.get('strand', 1) not in (1, -1):
                raise ValueError(f'Reference {reference_id}: strand must be 1 or -1.')
            material = extract_subsequence(material, region['start0'], region['end0'],
                                          strand=region.get('strand', 1), wraps_origin=False).only_product()
        self._loaded[reference_id] = material
        self._identities[reference_id] = {
            'id': reference_id, 'path': str(path), 'file_sha256': actual_sha,
            'record_id': material.id, 'record_version': material.record_version,
            'parent_record_version': parent_version, 'length_bp': len(material), 'topology': material.topology,
            'region': region, 'coordinate_system': '0-based-half-open on the selected record',
            'declared_version': entry.get('declared_version'), 'source': entry.get('source'),
            'strain_id': entry.get('strain_id'),
            'strain_identity_scope': 'Declared metadata; not independently established by a reference filename.',
        }
        return material

    def materials(self, ids=None):
        return {key: self.material(key) for key in (ids if ids is not None else self.references)}

    def reference_info(self, reference_id):
        self.material(reference_id)
        return dict(self._identities[reference_id])

    def describe(self, ids=None):
        self._check_context_version()
        return {'schema_version': 'genome-revival-context-v1', 'project': self.project,
                'strains': self.strains, 'routes': self.routes, 'facts': self.facts,
                'references': [self.reference_info(key) for key in (ids if ids is not None else self.references)],
                'context_file_sha256': self.context_file_sha256,
                'core_version': CORE_VERSION,
                'experimental_status': 'Only source-labelled records establish actual experimental observations.'}
