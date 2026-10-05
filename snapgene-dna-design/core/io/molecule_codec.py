"""External file metadata for the molecular contract; not a second DNA model."""
import base64
import copy
import json
import textwrap
import hashlib
import io
from Bio import SeqIO
from core.models.molecule import feature_data
from core.models.molecule import Molecule, json_metadata, restore_metadata

MARKER = 'MOLECULE-CONTRACT-V1:'


def _visible_comment(comment):
    if isinstance(comment, list):
        comment = '\n'.join(comment)
    return str(comment).split(MARKER, 1)[0].strip()


def file_metadata(material):
    if not isinstance(material, Molecule):
        return None
    # Sequence and features remain in their normal file sections. Never use
    # this metadata to replace an edited sequence or repair failed annotations.
    annotations = dict(material.annotations)
    if 'comment' in annotations:
        comment = _visible_comment(annotations['comment'])
        if comment:
            annotations['comment'] = comment
        else:
            annotations.pop('comment')
    return {'id': material.id, 'name': material.name, 'description': material.description,
            'strandedness': material.strandedness,
            'ends': None if material.topology == 'circular' or material.strandedness=='single' else {
                'left': material.left_end.to_dict() if material.left_end else None,
                'right': material.right_end.to_dict() if material.right_end else None},
            'source_refs': list(material.source_refs), 'operation': material.operation,
            'annotations': json_metadata(annotations), 'dbxrefs': list(material.dbxrefs),
            'letter_annotations': json_metadata(dict(material.letter_annotations)),
            'feature_ids':[f.id for f in material.features],
            'sequence_sha256': material.sequence_sha256}


def visible_fingerprint(record):
    annotations = dict(record.annotations)
    comment=_visible_comment(annotations.get('comment',''))
    if comment:annotations['comment']=comment
    else:annotations.pop('comment',None)
    content = {'sequence':str(record.seq), 'id':record.id,'name':record.name,
               'description':record.description,'dbxrefs':record.dbxrefs,
               'annotations':json_metadata(annotations),
               'features':[feature_data(f) for f in record.features]}
    return hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()


def metadata_text(material, visible_record=None, *, native=False):
    data = file_metadata(material)
    if data is None:
        return ''
    if visible_record is not None:
        data['visible_fingerprint'] = visible_fingerprint(visible_record)
        if native:
            data['native_feature_supplement'] = [feature_data(f) for f in material.features]
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return MARKER + base64.b64encode(payload).decode('ascii')


def genbank_record(material):
    record = copy.deepcopy(material)
    original = _visible_comment(record.annotations.get('comment', ''))
    if original:
        record.annotations['comment'] = original
    else:
        record.annotations.pop('comment', None)
    if record.annotations.get('topology') is None:
        record.annotations.pop('topology',None)
    # Bind to what the format actually writes, including its documented
    # formatting normalization, rather than overwriting later file edits.
    stream = io.StringIO()
    SeqIO.write(record,stream,'genbank')
    visible = SeqIO.read(io.StringIO(stream.getvalue()),'genbank')
    encoded = metadata_text(material, visible)
    if encoded:
        prefix, payload = encoded.split(MARKER, 1)
        record.annotations['comment'] = original + '\n' + MARKER + '\n' + '\n'.join(textwrap.wrap(payload, 60))
    return record


def restore_file_metadata(record, text=None):
    text = text if text is not None else record.annotations.get('comment', '')
    if isinstance(text, list):
        text = '\n'.join(text)
    if MARKER not in str(text):
        return record
    payload = str(text).split(MARKER, 1)[1]
    data = json.loads(base64.b64decode(''.join(payload.split()), validate=True))
    if data.get('visible_fingerprint') and data['visible_fingerprint'] != visible_fingerprint(record):
        raise ValueError('File-visible material information changed; regenerate molecular metadata')
    from core.models.assembly_model import FragmentEnd
    ends = data.get('ends') or {}
    current = copy.deepcopy(record)
    current.id, current.name = data['id'], data['name']
    current.description = data['description']
    # Keep the actual parsed topology. Metadata never overrides file geometry.
    topology = current.annotations.get('topology')
    current.annotations = restore_metadata(data['annotations'])
    current.annotations['topology'] = topology
    current.dbxrefs = data.get('dbxrefs', [])
    current.letter_annotations = data.get('letter_annotations', {})
    if 'feature_ids' in data:
        if len(current.features) != len(data['feature_ids']):
            raise ValueError('Feature identities no longer match the actual file')
        for feature,identifier in zip(current.features,data['feature_ids']):feature.id=identifier
    if 'native_feature_supplement' in data:
        # SGFF cannot encode fuzzy boundaries or every qualifier. Restore only
        # after checking ALL actually parsed native feature fields above.
        from core.io.input_resolution import resolve_sequence_record
        current.features = resolve_sequence_record({'sequence':str(current.seq),
            'record_version': None,'features':data['native_feature_supplement']}).features
    result = Molecule(current, strandedness=data.get('strandedness'),
                      left_end=FragmentEnd(**ends['left']) if ends.get('left') else None,
                      right_end=FragmentEnd(**ends['right']) if ends.get('right') else None,
                      source_refs=data.get('source_refs', []), operation=data.get('operation'), _owned=True)
    if result.sequence_sha256 != data['sequence_sha256']:
        raise ValueError('Saved molecular metadata belongs to another sequence version')
    return result
