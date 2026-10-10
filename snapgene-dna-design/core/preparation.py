"""Shared preparation replay and file writing, independent of Recipe CLI."""
from __future__ import annotations
import csv
import json
import pathlib
from core.models.molecule import as_molecule as resolve_sequence_record
from core.tools.snapgene_io import export_plasmid

def _check_quikchange_preparation(item, template, product):
    """Replay a mutagenic replacement from the original window and actual oligos."""
    from Bio.Seq import Seq
    forward, reverse = item["primers"]
    sequence = str(template.seq).upper()
    fwd = str(forward.get("sequence") or forward.get("seq") or forward.get("full_sequence") or "").upper()
    rev = str(reverse.get("sequence") or reverse.get("seq") or reverse.get("full_sequence") or "").upper()
    evidence = item.get('evidence') or (item["product"].get("evidence", {}) if isinstance(item["product"], dict) else {})
    reference = str(evidence.get("reference_segment") or "").upper()
    left, right = str(forward.get("left_flank") or "").upper(), str(forward.get("right_flank") or "").upper()
    if (not reference or not left or not right or len(reference) < len(left)+len(right)
            or not fwd.startswith(left) or not fwd.endswith(right)
            or not reference.startswith(left) or not reference.endswith(right)
            or rev != str(Seq(fwd).reverse_complement())):
        raise ValueError("PREPARATION_PRODUCT_MISMATCH: incomplete or contradictory mutagenic oligos/source window")
    circular = template.annotations.get("topology", "linear") == "circular"
    search = sequence+sequence if circular else sequence
    positions = [i for i in range(len(sequence)) if search[i:i+len(reference)] == reference]
    position = forward.get("position_0based")
    if isinstance(position, dict) and "start_0based" in position:
        start = int(position["start_0based"])-len(left)
        if circular:
            start %= len(sequence)
        positions = [i for i in positions if i == start]
    if len(positions) != 1 or (circular and len(reference) > len(sequence)):
        raise ValueError("PREPARATION_PRODUCT_MISMATCH: source window is missing or ambiguous at the declared mutation")
    start = positions[0]
    if circular:
        rotated = sequence[start:]+sequence[:start]
        expected = fwd+rotated[len(reference):]
        actual = str(product.seq).upper()
        matches = len(actual) == len(expected) and actual in expected+expected
    else:
        expected = sequence[:start]+fwd+sequence[start+len(reference):]
        matches = str(product.seq).upper() == expected
    if not matches:
        raise ValueError("PREPARATION_PRODUCT_MISMATCH: QuikChange product does not follow from source and actual oligos")


def check_preparation(preparation: list[dict]) -> None:
    """Replay actual templates and complete oligos before accepting a prepared product."""
    from core.tools.amplification import simulate_pcr
    # Check all declared PCRs before writing products or order tables. A desired
    # sequence supplied as "product" is not proof of preparation from these oligos.
    for item in preparation:
        method = str(item.get("method", "PCR")).strip().lower()
        if method not in {"pcr", "inverse_pcr", "quikchange"}:
            raise ValueError(f"PREPARATION_METHOD_UNSUPPORTED: cannot verify '{method}'")
        primers = item.get("primers", [])
        if len(primers) != 2:
            raise ValueError(f"PREPARATION_PRIMERS: '{item.get('id')}' requires its actual pair")
        fwd, rev = primers
        template = resolve_sequence_record(item["template"])
        product = resolve_sequence_record(item["product"])
        if method == "quikchange":
            _check_quikchange_preparation(item, template, product)
            continue
        if fwd.get("strand") in (-1, "-1", "-") and rev.get("strand") in (1, "1", "+"):
            # The row is expressed on the source's reverse strand (e.g. a
            # guide cassette). Keep that declared orientation when replaying.
            template = template.reverse_complement(id=True, name=True, annotations=True)
        def sequence(primer):
            return primer.get("sequence") or primer.get("seq") or primer.get("full_sequence")
        def core_length(primer):
            core = primer.get("binding_sequence") or primer.get("binding_core") or primer.get("core")
            return len(core) if core else None
        actual = simulate_pcr(template, sequence(fwd), sequence(rev),
                              forward_binding_core_length=core_length(fwd),
                              reverse_binding_core_length=core_length(rev))
        if str(actual.only_product().seq) != str(product.seq).upper():
            raise ValueError(f"PREPARATION_PRODUCT_MISMATCH: '{item.get('id')}' does not match actual template and primers")


def check_preparation_quality(preparation: list[dict]) -> dict:
    """Measure actual complete preparation pairs using their known method/conditions."""
    from core.tools.primer3_backend import check_complete_oligo_pair, Primer3CoreError
    import math
    checks = []
    for item in preparation:
        product = resolve_sequence_record(item['product'])
        template = resolve_sequence_record(item['template']) if item.get('template') is not None else None
        method = str(item.get('method', 'PCR')).lower()
        primers = item.get('primers', [])
        entry = {'id': item.get('id'), 'subject_version': product.record_version, 'method': method,
                 'template_version': template.record_version if template is not None else None,
                 'binding_context_status': 'PROVIDED' if template is not None else 'NOT_PROVIDED',
                 'oligos': [{'name': p.get('name', side),
                            'sequence_5to3': p.get('sequence') or p.get('seq') or p.get('full_sequence'),
                            'binding_sequence_5to3': p.get('binding_sequence') or p.get('binding_core') or p.get('core'),
                            'binding_interval_0based': p.get('binding_interval_0based'),
                            'strand': p.get('strand')}
                           for p, side in zip(primers, ('F', 'R'))],
                 'scope': 'complete preparation oligo structure, not experimental amplification efficiency'}
        try:
            if len(primers) != 2:
                raise ValueError('Quality check needs the actual pair')
            sequences = [p.get('sequence') or p.get('seq') or p.get('full_sequence') for p in primers]
            if any(not isinstance(s, str) or not s for s in sequences):
                raise ValueError('Quality check needs complete sequences')
            temperature = item.get('annealing_temperature_hint_C')
            if temperature is not None and (type(temperature) not in (int, float)
                    or not math.isfinite(temperature) or not 0 < temperature < 100):
                raise ValueError('Invalid declared annealing-temperature condition')
            result = check_complete_oligo_pair(*sequences, annealing_temperature=temperature, primer_method=method)
            entry.update(status='PASSED' if result['passed'] else 'FAILED', result=result)
            if result['passed'] and template is None:
                entry.update(status='INCOMPLETE', error_code='PREPARATION_TEMPLATE_NOT_PROVIDED',
                             reason='Complete oligo structure was measured, but the current binding template was not provided')
            entry['failed_metrics'] = [
                {'oligo': section, 'metric': metric, 'value_C': value,
                 'limit_C': result['structure_limit_C']}
                for section, metrics in result['metrics'].items()
                for metric, value in metrics.items()
                if value >= result['structure_limit_C']]
        except Primer3CoreError as exc:
            entry.update(status='INCOMPLETE', error_code=exc.error_code, reason=str(exc))
        except (ValueError, TypeError) as exc:
            entry.update(status='FAILED', error_code='PREPARATION_QUALITY_INPUT_INVALID', reason=str(exc))
        checks.append(entry)
    status = ('FAILED' if any(c['status'] == 'FAILED' for c in checks) else
              'INCOMPLETE' if any(c['status'] == 'INCOMPLETE' for c in checks) else
              'PASSED' if checks else 'NOT_APPLICABLE')
    return {'status': status, 'checks': checks, 'wet_lab': 'NOT_CHECKED'}


def preparation_feedback(preparation: list[dict]) -> dict:
    """Current oligo preparation facts; assembly/goal completion remains separate."""
    from core.errors import CoreError
    quality = check_preparation_quality(preparation)
    replay = []
    for item in preparation:
        method = str(item.get('method', 'PCR')).lower()
        row = {'id': item.get('id'), 'method': method,
               'template_version': resolve_sequence_record(item['template']).record_version,
               'subject_version': resolve_sequence_record(item['product']).record_version,
               'binding_scope': ('complete wild-type flanks and complementary mutagenic oligos'
                                 if method == 'quikchange' else 'exact 3prime cores on the actual template'),
               'reaction_scope': ('template-driven mutagenic replacement model'
                                  if method == 'quikchange' else 'actual primer-driven PCR product')}
        try:
            check_preparation([item])
            row['status'] = 'PASSED'
        except (CoreError, ValueError, TypeError, KeyError) as exc:
            row.update(status='FAILED', reason=str(exc),
                       error_code=getattr(exc, 'error_code', 'PREPARATION_REPLAY_FAILED'))
        replay.append(row)
    replay_status = ('FAILED' if any(r['status'] == 'FAILED' for r in replay) else
                     'PASSED' if replay else 'NOT_APPLICABLE')
    status = ('FAILED' if 'FAILED' in (replay_status, quality['status']) else
              'INCOMPLETE' if quality['status'] == 'INCOMPLETE' else
              'PASSED' if replay_status == quality['status'] == 'PASSED' else 'NOT_APPLICABLE')
    actions = []
    if replay_status == 'FAILED':
        actions.append('Recheck the actual template, complete oligos and intended product boundaries; retain the candidate until the reaction is corrected.')
    if quality['status'] == 'FAILED':
        actions.append('Review the failed complete-oligo metric and its conditions; adjust binding/flank boundaries or tail placement without changing the requested DNA goal.')
        if any(r['method'] == 'quikchange' for r in replay):
            actions.append('An existing inverse_pcr route can be evaluated as an alternative; the selected QuikChange method has not been changed.')
    elif quality['status'] == 'INCOMPLETE':
        actions.append('Resolve the reported backend availability/length limit before treating structural quality as established; another supported preparation route may be evaluated.')
    return {'status': status, 'ready_for_preparation': status == 'PASSED',
            'scope': 'declared PCR/mutagenic oligo reaction replay and full-oligo structure only; assembly, whole-task completion and experimental efficiency are separate',
            'reaction_replay': {'status': replay_status, 'checks': replay}, 'quality': quality,
            'suggested_actions': actions, 'wet_lab': 'NOT_CHECKED'}


def enrich_recipe_preparation(result):
    """Shared immediate Recipe feedback, reused without recomputing imported results."""
    rows = result.details.get('preparation', [])
    if not rows or 'preparation_feedback' in result.analysis:
        return result
    feedback = preparation_feedback(rows)
    result.analysis['preparation_feedback'] = feedback
    result.quality_checks['preparation_replay_status'] = feedback['reaction_replay']['status']
    result.quality_checks['complete_oligo_structure_status'] = feedback['quality']['status']
    if feedback['status'] != 'PASSED':
        result.warnings.append('PREPARATION_' + feedback['status'] + ': the retained DNA is a candidate; current reaction/complete-oligo checks are not ready. ' + ' '.join(feedback['suggested_actions']))
    return result


def check_verification_quality(primers, subject, steps=()):
    """Final QC orders bind the delivered template and retain screening conditions."""
    from core.models.molecule import as_molecule
    from core.io.primer_annotation import find_unique_binding_site
    from core.tools.primer3_backend import check_complete_oligo_pair, Primer3CoreError
    material = as_molecule(subject)
    checks, assays = [], []
    ordered = [p for p in primers or [] if p.get('role') == 'qc']
    sequences = {p.get('sequence') or p.get('sequence_5to3') or p.get('seq') for p in ordered}
    for primer in ordered:
        sequence = primer.get('sequence') or primer.get('sequence_5to3') or primer.get('seq')
        row = {'name': primer.get('name'), 'sequence': sequence, 'status': 'PASSED', 'errors': []}
        try:
            start, strand = find_unique_binding_site(str(material.seq), sequence, material.topology == 'circular')
            row.update(binding_interval_0based=[start, start + len(sequence)], strand=1 if strand == '+' else -1)
        except ValueError:
            row['errors'].append('NO_UNIQUE_BINDING_ON_FINAL_SUBJECT')
        try:
            row['structure'] = check_complete_oligo_pair(sequence)
            if not row['structure']['passed']: row['errors'].append('STRUCTURE_SCREEN_FAILED')
        except Primer3CoreError as exc:
            row.update(status='INCOMPLETE', reason=str(exc))
        if row['errors'] and row['status'] != 'INCOMPLETE': row['status'] = 'FAILED'
        checks.append(row)
    for step in steps:
        analysis = step.result.analysis
        if analysis.get('result_kind') != 'verification': continue
        details = analysis.get('details', {})
        declared = {p.get('sequence') for p in analysis.get('primers', [])}
        if not sequences.intersection(declared): continue
        source = as_molecule(analysis['subject'])
        row = {'step_id': step.step_id, 'subject_version': source.record_version,
               'status': 'PASSED', 'parental_pcr': details.get('parental_pcr', {'status': 'NOT_CHECKED'}),
               'sequencing_coverage': details.get('sequencing_coverage', {'status': 'NOT_CHECKED'}),
               'junction_pcr': details.get('junction_pcr_primers')}
        # Annotation-only versions may share an assay; sequence or topology changes cannot.
        if str(source.seq) != str(material.seq) or source.topology != material.topology:
            row.update(status='FAILED', reason='QC_SUBJECT_CHANGED')
        pair = details.get('junction_pcr_primers', {})
        forward, reverse = pair.get('forward_primer_in_vector'), pair.get('reverse_primer_in_insert')
        if forward in sequences and reverse in sequences:
            try:
                row['pair_structure'] = check_complete_oligo_pair(forward, reverse)
                if not row['pair_structure']['passed']: row.update(status='FAILED', reason='PAIR_STRUCTURE_SCREEN_FAILED')
            except Primer3CoreError as exc:
                row.update(status='INCOMPLETE', reason=str(exc))
        assays.append(row)
    statuses = [r['status'] for r in checks + assays]
    status = ('FAILED' if 'FAILED' in statuses else 'INCOMPLETE' if 'INCOMPLETE' in statuses else
              'PASSED' if checks else 'NOT_APPLICABLE')
    return {'status': status, 'subject_version': material.record_version, 'checks': checks, 'assays': assays,
            'scope': 'exact binding and default full-oligo structural screen; not experimental performance',
            'wet_lab': 'NOT_CHECKED'}


def write_preparation_artifacts(preparation: list[dict], out_dir: str | pathlib.Path) -> dict:
    """Write the actual prepared fragments, source primer maps and order table."""
    from Bio import SeqIO
    from core.tools.snapgene_io import annotate_record_primers
    from core.tools.amplification import simulate_pcr
    out = pathlib.Path(out_dir)
    outputs, orders = [], []
    check_preparation(preparation)
    quality = check_preparation_quality(preparation)
    out.mkdir(parents=True, exist_ok=True)
    quality_file = out / 'preparation_quality.json'
    quality_file.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding='utf-8')
    for index, item in enumerate(preparation, 1):
        product = resolve_sequence_record(item["product"])
        template = resolve_sequence_record(item["template"])
        primers = item.get("primers", [])
        if not primers:
            raise ValueError(f"Preparation '{item.get('id', index)}' has no actual primers")
        prefix = f"preparation_{index:02d}"
        fragment = export_plasmid(product, out / "intermediates", prefix,
                                  product.annotations.get("topology", "linear")).analysis
        source_copy = annotate_record_primers(template, primers)
        if str(item.get("method", "PCR")).strip().lower() == "quikchange":
            for feature in source_copy.features[-len(primers):]:
                feature.qualifiers.setdefault("note", []).append(
                    "QuikChange: location marks the exact 3-prime wild-type anchor; remaining primer sequence includes a 5-prime matching flank and intended internal mutation, not solely an unpaired overhang.")
        source_files = export_plasmid(source_copy, out / "annotated_sources", prefix + "_source",
                                      template.annotations.get("topology", "linear")).analysis
        # When the input is Native, preserve its non-modeled packets as well.
        original = item["template"]
        if isinstance(original, (str, pathlib.Path)) and pathlib.Path(original).suffix.lower() == ".dna":
            from core.io.primer_annotation import annotate_primers_dna
            annotate_primers_dna(original, source_files["dna_file"], "add", primers)
        fa = out / "intermediates" / (prefix + ".fasta")
        with fa.open("w", encoding="utf-8", errors="replace") as handle:
            SeqIO.write(product, handle, "fasta")
        outputs.append({"id": item.get("id", prefix), "method": item.get("method", "PCR"),
                        "product": fragment, "fasta": str(fa), "annotated_source": source_files})
        for primer in primers:
            orders.append({"preparation": item.get("id", prefix), "template": template.id,
                           "coordinate_reference": str(pathlib.Path(source_files["gb_file"]).resolve().relative_to(out.resolve())),
                           "coordinate_system": "0-based half-open on annotated source",
                           "name": primer.get("name", "primer"),
                           "sequence_5to3": primer.get("sequence") or primer.get("seq"),
                           "binding_sequence_5to3": primer.get("binding_sequence") or primer.get("binding_core", ""),
                           "binding_interval_0based": json.dumps(primer.get("binding_interval_0based")),
                           "strand": primer.get("strand"),
                           "tm_C": primer.get("binding_core_tm", primer.get("tm", primer.get("qc_tm", ""))),
                           "annealing_hint_C": item.get("annealing_temperature_hint_C", "")})
    if not orders:
        return {"steps": [], "primer_order_table": None, "quality": quality, "quality_file": str(quality_file)}
    order_file = out / "primer_order_table.tsv"
    with order_file.open("w", encoding="utf-8", errors="replace", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(orders[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(orders)
    return {"steps": outputs, "primer_order_table": str(order_file), "quality": quality, "quality_file": str(quality_file)}
