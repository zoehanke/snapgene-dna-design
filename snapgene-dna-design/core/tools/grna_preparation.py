"""Source-derived inverse-PCR design followed by separate reaction simulations."""
from __future__ import annotations

from Bio.Seq import Seq
from core.errors import CoreError
from core.tools.result import check_result

NEB_SOURCE = {'source_type': 'manufacturer_protocol', 'name': 'NEB Q5 SDM E0554 manual',
    'version': '2.0_7/20', 'url': 'https://www.neb.com/en/-/media/nebus/files/manuals/manuale0554.pdf',
    'retrieved_at': '2026-10-13', 'verification_status': 'verified'}
IDT_SOURCE = {'source_type': 'manufacturer_guidance', 'name': 'IDT oligo purification guidance',
    'version': 'RUO23-1848_001',
    'url': 'https://www.idtdna.com/page/support-and-education/decoded-plus/which-type-of-purification-should-i-choose/',
    'retrieved_at': '2026-10-13', 'verification_status': 'verified'}
TM_CONDITIONS = {'monovalent_mM': 50.0, 'Mg_mM': 1.5, 'total_dNTP_mM': 0.6,
    'effective_oligo_nM': 50.0, 'K_mM': 0.0, 'Tris_mM': 0.0,
    'accepted_core_tm_C': [52.0, 72.0], 'max_pair_delta_tm_C': 3.0,
    'min_core_nt': 15, 'max_core_nt': 40, 'max_complete_oligo_nt': 60}


def _hits(sequence, query):
    n = len(sequence)
    search = sequence + sequence[:len(query)-1]
    return [p for p in range(n) if search[p:p+len(query)] == query]


def preparation_warnings(source, location, spacer):
    positions = list(location)
    start = positions[0] if location.strand == 1 else positions[-1]
    n = len(source)
    warnings = []
    if start+20 > n:
        warnings.append({'code': 'GRNA_ORIGIN_CROSSING',
            'message': 'Replacement crosses reference origin; PCR coordinates wrap and simulated circle restores that origin.'})
    if 'TTTT' in spacer:
        warnings.append({'code': 'GRNA_POL_III_POLY_T',
            'message': 'Spacer contains TTTT; premature Pol III termination is possible. Requested DNA remains unchanged.'})
    text = str(source.seq)
    other = []
    for strand, query in ((1, spacer), (-1, str(Seq(spacer).reverse_complement()))):
        for pos in _hits(text, query):
            if pos != start:
                other.append({'start_0based': pos, 'strand': strand})
    if other:
        warnings.append({'code': 'GRNA_SPACER_REPEATED_IN_TEMPLATE', 'matches': other,
            'message': 'New spacer occurs elsewhere in template. A 5-prime tail alone is not an annealing core; whole-template core uniqueness is checked separately.'})
    return warnings


def plan_and_simulate(source, location, spacer, expected_sequence, target_tm):
    """Generate oligos first; rederive DNA using public PCR/ligation tools afterward."""
    from core.tools import design_overhang_primers, simulate_pcr, ligate_fragments, rotate_sequence
    n = len(source)
    positions = list(location)
    start = positions[0] if location.strand == 1 else positions[-1]
    end = (start+20) % n
    payload = spacer if location.strand == 1 else str(Seq(spacer).reverse_complement())
    route = {'status': 'PLANNED', 'simulation_status': 'NOT_RUN', 'wet_lab': 'NOT_PERFORMED',
        'method': 'inverse_pcr_DpnI_KLD', 'template_version': source.record_version,
        'replacement_parts_0based': [[int(p.start), int(p.end)] for p in location.parts],
        'tm_conditions': {**TM_CONDITIONS, 'target_core_tm_C': target_tm},
        'parental_template_methylation': 'UNKNOWN', 'sources': [NEB_SOURCE, IDT_SOURCE],
        'dpni_scope': 'Planned removal of Dam-methylated parental DNA; effectiveness not simulated or measured.',
        'end_chemistry': 'High-fidelity blunt PCR product; KLD kinase supplies 5-prime phosphorylation before ligation.'}
    unavailable = lambda reason: ({**route, 'status': 'UNAVAILABLE', 'reason': reason}, [], None, [])
    if source.topology != 'circular' or source.strandedness == 'single':
        return unavailable('Inverse PCR requires a complete circular duplex plasmid template; linear/single-stranded input is not silently circularized.')
    # Tail placement is a real design choice; try opposite end if full-oligo QC fails.
    designed = None
    failures = []
    for placement, f_tail, r_tail in (
        ('reverse', '', str(Seq(payload).reverse_complement())), ('forward', payload, '')):
        try:
            candidate = design_overhang_primers(source, start=end, end=start,
                fwd_5prime_overhang=f_tail, rev_5prime_overhang=r_tail,
                target_tm=target_tm, min_core_len=15, max_core_len=40, circular=True).analysis
            fwd, rev = candidate['forward_primer'], candidate['reverse_primer']
            # Verify exact requested boundaries rather than accepting moved primers.
            if (fwd['binding']['template_start_0based'] != end or
                (rev['binding']['template_start_0based'] + rev['binding_core_length']) % n != start):
                raise ValueError('Designed cores do not flank the exact spacer boundaries')
            designed = candidate
            route['spacer_tail_primer'] = placement
            break
        except (CoreError, ValueError) as exc:
            failures.append({'tail_primer': placement, 'reason': str(exc)})
    if designed is None:
        route['design_attempts'] = failures
        return unavailable('No unique full-oligo pair meets binding, Tm and structure limits: ' + '; '.join(f['reason'] for f in failures))
    route['design_attempts'] = failures + [{'tail_primer': route['spacer_tail_primer'], 'status': 'PASSED'}]
    engine = designed['primer3_metrics']['engine']
    route['tm_method'] = ('Primer3 Core; SantaLucia 1998 NN (TM_FORMULA=1, SALT_CORRECTIONS=1), von Ahsen Mg/dNTP correction'
        if engine.startswith('primer3') else
        'Biopython Tm_NN DNA_NN3 (Allawi/SantaLucia), saltcorr=5; von Ahsen Mg/dNTP correction; dnac1=dnac2=25 nM')
    route['primer_design_engine'] = engine
    route['pair_quality'] = designed['primer3_metrics']['selected_pair_quality']
    primers = []
    for name, side, info in (('grna_inverse_F', 1, designed['forward_primer']),
                             ('grna_inverse_R', -1, designed['reverse_primer'])):
        tail = info['overhang_5prime']
        purification = {'required': False,
            'recommendation': 'Consider PAGE (HPLC if yield is limiting)' if tail else 'Standard desalting',
            'reason': ('A full-length 5-prime spacer payload matters for mutagenesis; truncation/deletion products can change the edit. '
                       'NEB accepts standard desalted oligos, while IDT recommends considering PAGE for mutagenesis.')
                      if tail else 'NEB Q5/KLD accepts ordinary desalted primers; kinase supplies phosphorylation.',
            'source': IDT_SOURCE if tail else NEB_SOURCE}
        binding = info['binding']
        primers.append({'name': name, 'sequence': info['full_sequence'], 'seq': info['full_sequence'],
            'binding_sequence': info['binding_core'], 'binding_core': info['binding_core'],
            'binding_core_tm': info['binding_core_tm'], 'tm': info['binding_core_tm'], 'qc_tm': info['binding_core_tm'],
            'five_prime_tail': tail, 'tail_length': len(tail), 'full_length': len(info['full_sequence']),
            'binding_interval_0based': [binding['template_start_0based'], binding['template_end_0based']],
            'strand': side, 'unique_binding': info['unique_binding'], 'binding_match_count': info['binding_match_count'],
            'role': 'gRNA inverse PCR', 'tm_method': route['tm_method'], 'tm_conditions': route['tm_conditions'],
            'purification': purification, 'five_prime_phosphorylation_required_for_order': False})
    route['primers'] = primers
    # No expected/product string is passed to these public reaction calculations.
    # Core length selectors expose the designed annealing core, never hide other hits.
    try:
        fwd, rev = primers
        pcr = simulate_pcr(source, fwd['sequence'], rev['sequence'], topology='circular',
            forward_binding_core_length=len(fwd['binding_core']), reverse_binding_core_length=len(rev['binding_core']))
        circle = ligate_fragments([pcr.only_product()], circular=True)
        origin = ((n-end) + (20 if route['spacer_tail_primer'] == 'forward' else 0)) % n
        restored = rotate_sequence(circle.only_product(), origin).only_product() if origin else circle.only_product()
        if str(restored.seq) != expected_sequence:
            raise ValueError('PREPARATION_PRODUCT_MISMATCH: independently simulated circle differs from spacer edit')
    except (CoreError, ValueError) as exc:
        return unavailable(str(exc))
    route.update(simulation_status='PASSED', simulation_scope='Exact annealing-core PCR and blunt intramolecular ligation sequence model',
        simulation_versions={'PCR': pcr.only_product().record_version, 'circle': circle.only_product().record_version,
                             'restored': restored.record_version}, origin_restore_0based=origin,
        sequence_identical_to_edit=True)
    annealing = min(p['binding_core_tm'] for p in primers) - 5.0
    row = {'id': 'grna_inverse_PCR', 'method': 'inverse_pcr', 'template': source,
           'product': pcr.only_product(), 'primers': primers, 'annealing_temperature_hint_C': annealing,
           'laboratory_status': 'PLANNED', 'wet_lab': 'NOT_PERFORMED'}
    return route, [row], restored, pcr.checks + circle.checks


def protocol_steps(route, length):
    if route['status'] != 'PLANNED':
        return []
    conditions = route['tm_conditions']
    order_guidance = ' '.join(f"{p['name']}: {p['full_length']} nt, annealing core {len(p['binding_sequence'])} nt, core Tm {p['binding_core_tm']} C; {p['purification']['recommendation']} (extra purification required: no). {p['purification']['reason']}" for p in route['primers'])
    return [
        {'step': 1, 'status': 'PLANNED', 'action': 'PLANNED, wet experiment NOT_PERFORMED: order the complete inverse-PCR oligos. KLD supplies phosphorylation. ' + order_guidance},
        {'step': 2, 'status': 'PLANNED', 'action': f"PLANNED: amplify the original complete {length} bp circular template with high-fidelity blunt-end PCR. Tm method: {route['tm_method']}; model salts: monovalent {conditions['monovalent_mM']} mM, Mg {conditions['Mg_mM']} mM, total dNTP {conditions['total_dNTP_mM']} mM, effective oligo {conditions['effective_oligo_nM']} nM. Model conditions are not a measured kit-buffer composition. Use polymerase-specific annealing/cycling guidance; NEB Q5 reference uses 20-30 s/kb extension."},
        {'step': 3, 'status': 'PLANNED', 'action': 'PLANNED: DpnI removes Dam-methylated parental template during KLD. Confirm parental methylation before lab work; DpnI performance/background removal is NOT_VERIFIED. An unmethylated/PCR-derived parent needs another validated removal route.'},
        {'step': 4, 'status': 'PLANNED', 'action': 'PLANNED: use kinase plus ligase and DpnI (KLD) for phosphorylation, intramolecular circularization and template removal according to NEB E0554. Reference KLD incubation is 5 min at room temperature. Sequence circularization was SIMULATED, not performed in the laboratory.'},
        {'step': 5, 'status': 'PLANNED', 'action': 'PLANNED: transform according to competent-cell protocol, select using supported template marker evidence, and confirm the spacer/scaffold junction by sequencing. Colonies, sequence reads and gRNA activity have NOT_BEEN_MEASURED.'},
    ]
