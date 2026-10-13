"""Actual outer-step preparation ownership, independent materials and strict orders."""
from repository_paths import SKILL_ROOT
import csv
import json
import pathlib
import random
import sys
import tempfile
import unittest
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

sys.path.insert(0,str(SKILL_ROOT))
from core.errors import ValidationError, GateRejected
from core.models.molecule import as_molecule
from core.workflow import run_step
from core.workflow_delivery import deliver_result, preparation_rows
from core.tools.primer3_backend import discover_primer3_core

def source(sequence,name):
    return as_molecule(SeqRecord(Seq(sequence),id=name,name=name,annotations={'molecule_type':'DNA','topology':'linear'}))

def two_pcrs(tail=None):
    rng=random.Random(788759)
    raw=''.join(rng.choice('ACGT') for _ in range(650))
    original=source(raw,'independent_source')
    first=run_step('simulate_pcr',{'template_path_or_seq':'$source','f_primer':raw[100:122],
        'r_primer':str(Seq(raw[380:402]).reverse_complement()),'forward_binding_core_length':22,'reverse_binding_core_length':22},
        sources={'source':original},step_id='first')
    forward=raw[140:162] if tail is None else tail+raw[100:122]
    reverse=str(Seq(raw[340:362] if tail is None else raw[380:402]).reverse_complement())
    expected=raw[140:362] if tail is None else tail+raw[100:402]
    second=run_step('simulate_pcr',{'template_path_or_seq':'$first','f_primer':forward,
        'r_primer':reverse,'forward_binding_core_length':22,'reverse_binding_core_length':22},
        sources={'source':original},previous=[first],step_id='second')
    assert first.error is None and second.error is None
    assert str(second.result.only_product().seq)==expected
    return original,[first,second],expected

@unittest.skipUnless(discover_primer3_core(),'Real primer3_core required')
class PreparationOrderOwnershipTests(unittest.TestCase):
    def test_two_public_pcrs_auto_deliver_without_duplicate_generic_orders(self):
        original,steps,expected=two_pcrs(tail='ACTAGCT')
        with tempfile.TemporaryDirectory(prefix='多步订单_') as temp:
            result=deliver_result({'expected_sequence':expected,'topology':'linear'},{'source':original},
                steps,steps[-1].result.only_product(),temp)
            directory=pathlib.Path(result['directory'])
            with (directory/'oligo_order_table.tsv').open(encoding='utf-8') as handle:orders=list(csv.DictReader(handle,delimiter='\t'))
            with (directory/'primer_order_table.tsv').open(encoding='utf-8') as handle:detail=list(csv.DictReader(handle,delimiter='\t'))
            self.assertEqual(len(orders),4)
            self.assertEqual(len({r['name'] for r in orders}),4)
            self.assertEqual([(r['name'],r['sequence_5to3']) for r in orders],[(r['name'],r['sequence_5to3']) for r in detail])
            self.assertEqual([r['source_step'] for r in detail],['first','first','second','second'])
            self.assertEqual(detail[0]['template_version'],original.record_version)
            self.assertEqual(detail[2]['template_version'],steps[0].result.only_product().record_version)
            self.assertEqual(detail[2]['product_version'],steps[1].result.only_product().record_version)
            self.assertEqual(result['validation']['overall'],'verified')

    def test_original_bad_pair_is_retained_and_rejected_by_actual_quality(self):
        # This original fixture's second pair was incorrectly assumed valid.
        # Independent raw primer3_core metrics show hairpins 53.37/63.49 C.
        # Keep the input and expected refusal, instead of relaxing its screen.
        original,steps,expected=two_pcrs()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(GateRejected) as caught:
                deliver_result({'expected_sequence':expected,'topology':'linear'},{'source':original},
                    steps,steps[-1].result.only_product(),temp)
            self.assertEqual(caught.exception.error_code,'GATE_WORKFLOW_INCOMPLETE')
            self.assertIn('OLIGO_QUALITY_FAILED',str(caught.exception.details['validation']['errors']))

    def test_preparation_projection_has_real_owner_and_never_edits_run_inputs(self):
        original,steps,_=two_pcrs()
        before=json.dumps([s.to_dict() for s in steps],sort_keys=True)
        rows=preparation_rows(steps,steps[-1].result.only_product())
        self.assertEqual(len(rows),2)
        self.assertEqual([r['source_step'] for r in rows],['first','second'])
        self.assertEqual(len({r['id'] for r in rows}),2)
        self.assertEqual(len({p['name'] for r in rows for p in r['primers']}),4)
        self.assertEqual(json.dumps([s.to_dict() for s in steps],sort_keys=True),before)

    def test_wrong_explicit_shared_identifier_is_still_rejected(self):
        original,steps,expected=two_pcrs()
        orders=[{**p,'name':'same','role':'preparation'} for step in steps for p in step.result.analysis['primers']]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValidationError) as caught:
                deliver_result({'expected_sequence':expected,'topology':'linear'},{'source':original},steps,
                    steps[-1].result.only_product(),temp,primers=orders)
            self.assertEqual(caught.exception.error_code,'ORDER_IDENTIFIER_CONFLICT')

    def test_preparation_detail_owner_and_versions_are_checked_not_just_displayed(self):
        from core.workflow_validation import validate_candidate
        original,steps,expected=two_pcrs(tail='ACTAGCT')
        product=steps[-1].result.only_product()
        with tempfile.TemporaryDirectory() as temp:
            result=deliver_result({'expected_sequence':expected,'topology':'linear'},{'source':original},steps,product,temp)
            detail=pathlib.Path(result['directory'])/'primer_order_table.tsv'
            with detail.open(encoding='utf-8') as handle:rows=list(csv.DictReader(handle,delimiter='\t'))
            for field in ('source_step','template_version','product_version','coordinate_reference'):
                changed=[dict(r) for r in rows]
                changed[0][field]='incorrect-current-fact'
                candidate=pathlib.Path(temp)/(field+'.tsv')
                with candidate.open('w',encoding='utf-8',newline='') as handle:
                    writer=csv.DictWriter(handle,fieldnames=list(rows[0]),delimiter='\t')
                    writer.writeheader();writer.writerows(changed)
                report=validate_candidate({'expected_sequence':expected,'topology':'linear'},{'source':original},steps,product,
                    primers=result['validation']['primers'],files={'primer_order_table.tsv':str(candidate)})
                self.assertEqual(report['overall'],'failed',field)
                self.assertIn('PREPARATION_ORDER_TABLE_MISMATCH',report['errors'],field)

    def test_single_public_pcr_has_one_pair_and_matching_detail(self):
        original,steps,_=two_pcrs()
        first=steps[0]
        with tempfile.TemporaryDirectory() as temp:
            result=deliver_result({'expected_sequence':str(first.result.only_product().seq),'topology':'linear'},
                {'source':original},[first],first.result.only_product(),temp)
            directory=pathlib.Path(result['directory'])
            with (directory/'oligo_order_table.tsv').open(encoding='utf-8') as handle:orders=list(csv.DictReader(handle,delimiter='\t'))
            self.assertEqual(len(orders),2)
            self.assertEqual(len(preparation_rows([first],first.result.only_product())),1)

    def test_two_actual_recipes_reuse_generic_local_ids_without_collision(self):
        rng=random.Random(349862)
        raw=''.join(rng.choice('ACGT') for _ in range(600))
        left=source(''.join(rng.choice('ACGT') for _ in range(40))+raw[:320]+''.join(rng.choice('ACGT') for _ in range(50)),'left')
        right=source(''.join(rng.choice('ACGT') for _ in range(45))+raw[300:]+''.join(rng.choice('ACGT') for _ in range(55)),'right')
        sources={'left':left,'right':right}
        first=run_step('recipe_gibson_assembly',{'fragments':[{'id':'part1','template':'$left','start':40,'end':360},
            {'id':'part2','template':'$right','start':45,'end':345}],'overlap_length':20,'circular_product':False},sources=sources,step_id='build')
        self.assertIsNone(first.error,first.error)
        second=run_step('recipe_gibson_assembly',{'fragments':[{'id':'part1','template':'$build','start':0,'end':320},
            {'id':'part2','template':'$build','start':300,'end':600}],'overlap_length':20,'circular_product':False},sources=sources,previous=[first],step_id='reuse')
        self.assertIsNone(second.error,second.error)
        self.assertEqual(str(second.result.only_product().seq),raw)
        rows=preparation_rows([first,second],second.result.only_product())
        self.assertEqual(len(rows),4)  # Rich rows and repeated check operations represent the same four PCRs.
        self.assertEqual([r['source_step'] for r in rows],['build','build','reuse','reuse'])
        self.assertEqual(len({r['id'] for r in rows}),4)
        with tempfile.TemporaryDirectory() as temp:
            result=deliver_result({'expected_sequence':raw,'topology':'linear'},sources,[first,second],second.result.only_product(),temp)
            with (pathlib.Path(result['directory'])/'oligo_order_table.tsv').open(encoding='utf-8') as handle:orders=list(csv.DictReader(handle,delimiter='\t'))
            self.assertEqual(len(orders),8)
            self.assertEqual(len({r['name'] for r in orders}),8)

if __name__=='__main__':unittest.main()
