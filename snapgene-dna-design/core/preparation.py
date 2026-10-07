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
        method = str(item.get('method', 'PCR')).lower()
        primers = item.get('primers', [])
        entry = {'id': item.get('id'), 'subject_version': product.record_version, 'method': method,
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
        except Primer3CoreError as exc:
            entry.update(status='INCOMPLETE', error_code=exc.error_code, reason=str(exc))
        except (ValueError, TypeError) as exc:
            entry.update(status='FAILED', error_code='PREPARATION_QUALITY_INPUT_INVALID', reason=str(exc))
        checks.append(entry)
    status = ('FAILED' if any(c['status'] == 'FAILED' for c in checks) else
              'INCOMPLETE' if any(c['status'] == 'INCOMPLETE' for c in checks) else
              'PASSED' if checks else 'NOT_APPLICABLE')
    return {'status': status, 'checks': checks, 'wet_lab': 'NOT_CHECKED'}


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
