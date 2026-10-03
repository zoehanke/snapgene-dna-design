"""Legacy preview contracts: actual handoff, source identity and safe failure."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from agent.orchestrator import Orchestrator
from agent.session import Session, summarize_file
from agent.delivery import write_delivery
from design.spec import DesignSpecError, new_spec, spec_sha256

ROOT= SKILL_ROOT


class LegacyPreviewContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='preview-中文-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'source.gb'
        self.source.write_bytes((ROOT/'fixtures/synthetic/pSynthetic-GFP.gb').read_bytes())
        self.spec=new_spec('inspect supplied construct',mode='exploration')
        self.spec['status']='verified'
        self.session=Session(self.spec,workdir=self.root/'work')
        self.session.add_file(self.source)
        self.session.construct_gb=self.source

    def assert_manifest(self,result):
        directory=Path(result['directory'])
        manifest=json.loads((directory/'DELIVERY-MANIFEST.json').read_text(encoding='utf-8'))
        saved=json.loads((directory/'DESIGN-SPEC.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['spec_sha256'],spec_sha256(saved))
        self.assertEqual((directory/'DESIGN-SPEC-SHA256.txt').read_text(encoding='utf-8').strip(),spec_sha256(saved))
        for name,digest in manifest['output_files'].items():
            self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest().upper(),digest,name)
        self.assertEqual(set(result['files']),set(manifest['output_files'])|{'DELIVERY-MANIFEST.json'})
        self.assertEqual(manifest['artifact_class'],'preview')
        self.assertFalse(saved['outputs']['delivery_flags']['ready_to_order'])
        return directory,saved

    def test_snapshot_contains_omission_reason_without_mutating_input(self):
        before=copy.deepcopy(self.spec)
        result=write_delivery(self.spec,self.session,self.root/'export',self.source)
        directory,saved=self.assert_manifest(result)
        self.assertIn('dna_note',saved['outputs'])
        self.assertEqual(self.spec,before)
        self.assertFalse((directory/'construct.dna').exists())
        self.assertEqual(str(SeqIO.read(directory/'construct.preview.gb','genbank').seq),str(SeqIO.read(self.source,'genbank').seq))

    def test_existing_package_is_immutable_and_working_files_are_separate(self):
        out=self.root/'working'
        workspace=out/'preview';workspace.mkdir(parents=True)
        (workspace/'stale.dna').write_bytes(b'old working artifact')
        result=write_delivery(self.spec,self.session,out,self.source)
        directory,_=self.assert_manifest(result)
        self.assertEqual(directory,workspace/'delivery')
        self.assertNotIn('stale.dna',result['files'])
        original={p.name:p.read_bytes() for p in directory.iterdir()}
        with self.assertRaises(FileExistsError):write_delivery(self.spec,self.session,out,self.source)
        self.assertEqual(original,{p.name:p.read_bytes() for p in directory.iterdir()})

    def test_plan_and_primers_are_exported_or_fail_as_one_package(self):
        source_plan=self.root/'plan.json'
        source_plan.with_suffix('.md').write_text('actual plan text',encoding='utf-8')
        plan={'primers':[{'fragment':'insert','forward':{'name':'F','sequence':'ACGTACGTACGT'},'reverse':{}}]}
        source_plan.write_text(json.dumps(plan),encoding='utf-8')
        self.spec['constraints']['method_selection']={'selected':{'required_materials':['declared reagent'],'source_evidence':['declared source']}}
        self.spec['constraints']['polymerase_preference']='declared polymerase'
        self.spec['assumptions']=[{'evidence_layer':'user-provided','description':'explicit assumption'}]
        artifact={'command':['plan_assembly.py','--out-json',str(source_plan)],'stdout':'not primer data'}
        result=write_delivery(self.spec,self.session,self.root/'valid-plan',self.source,[artifact])
        directory,_=self.assert_manifest(result)
        with (directory/'primers.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
        self.assertEqual([r['sequence'] for r in rows],['ACGTACGTACGT'])
        self.assertEqual((directory/'construction-plan.md').read_text(encoding='utf-8'),'actual plan text')
        source_plan.write_text('{broken',encoding='utf-8')
        with self.assertRaises(ValueError):write_delivery(self.spec,self.session,self.root/'bad-plan',self.source,[artifact])
        self.assertFalse((self.root/'bad-plan/preview/delivery').exists())
        self.assertFalse(list((self.root/'bad-plan/preview').glob('.delivery-*')))

    def test_native_and_report_only_exports_keep_precise_scope(self):
        record=SeqIO.read(self.source,'genbank')
        # Use the actual exporter, not a fake file merely named .dna.
        from core.tools.snapgene_io import export_snapgene
        exported=export_snapgene(record,self.root/'native','source')
        source=Path(exported['gb_file'])
        with source.with_suffix('.fa').open('w',encoding='utf-8') as f:SeqIO.write(record,f,'fasta')
        for force in (False,True):
            result=write_delivery(self.spec,self.session,self.root/str(force),source,force_dna=force)
            directory,saved=self.assert_manifest(result)
            self.assertEqual((directory/'construct.dna').exists(),force)
            if not force:self.assertIn('dna_note',saved['outputs'])
        result=write_delivery(self.spec,self.session,self.root/'report-only')
        _,saved=self.assert_manifest(result)
        self.assertIn('construct_note',saved['outputs'])
        with self.assertRaises(FileNotFoundError):
            write_delivery(self.spec,self.session,self.root/'missing',self.root/'absent.gb')

    def test_missing_source_and_unknown_strand_do_not_become_valid_evidence(self):
        record=SeqIO.read(self.source,'genbank')
        record.features.append(SeqFeature(CompoundLocation([FeatureLocation(20,30,strand=1),FeatureLocation(40,50,strand=-1)]),type='misc_feature',qualifiers={'label':['mixed-strand']}))
        with self.source.open('w',encoding='utf-8') as f:SeqIO.write(record,f,'genbank')
        self.assertIsNone(summarize_file(self.source)['features'][-1]['strand'])
        self.source.unlink()
        self.assertIn(str(self.source),self.session.check_file_hashes())
        with self.assertRaises(DesignSpecError):Orchestrator(self.session).resolve_evidence()

    def test_unverified_and_formal_handoff_leave_no_package(self):
        for mode,status in (('exploration','executed'),('exploration','blocked'),('formal','verified')):
            self.session.spec=new_spec('do not deliver',mode=mode)
            self.session.spec['status']=status
            out=self.root/(mode+status)
            with self.subTest(mode=mode,status=status),self.assertRaises(DesignSpecError):
                Orchestrator(self.session,out).deliver()
            self.assertFalse((out/'preview/delivery').exists())

    def test_failed_execution_clears_previous_candidate_and_keeps_diagnostics(self):
        spec=self.session.spec
        spec['status']='planned'
        spec['objective']={'type':'point-mutation','mutation':'999999:A','selected_method':'gibson'}
        self.session.artifacts=[{'old':'result'}]
        with self.assertRaises(DesignSpecError):Orchestrator(self.session).execute()
        self.assertEqual(spec['status'],'blocked')
        self.assertIsNone(self.session.construct_gb)
        self.assertTrue(self.session.artifacts)
        self.assertNotEqual(self.session.artifacts[0],{'old':'result'})
        self.assertNotEqual(self.session.artifacts[0]['returncode'],0)

    def test_cli_real_mutation_delivers_exact_preview(self):
        sequence=str(SeqIO.read(self.source,'genbank').seq)
        alternate='C' if sequence[99]!='C' else 'A'
        out=self.root/'cli'
        cmd=[sys.executable,'-X','utf8','-B',str(ROOT/'scripts/run_design_agent.py'),
             '--text',f'对模板做定点突变 100:{alternate}，宿主大肠杆菌','--files',str(self.source),
             '--mode','exploration','--auto-confirm','--deliver','--json','--out-dir',str(out)]
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        payload=json.loads(result.stdout)
        directory,saved=self.assert_manifest(payload['delivery'])
        self.assertEqual(str(SeqIO.read(directory/'construct.preview.gb','genbank').seq),sequence[:99]+alternate+sequence[100:])
        self.assertFalse((out/'authoritative').exists())

    def test_cold_delivery_import_does_not_require_another_module_to_patch_paths(self):
        env=dict(os.environ);env.pop('PYTHONPATH',None)
        run=subprocess.run([sys.executable,'-c','from agent.delivery import os_probe_summary; print(os_probe_summary()["status"])'],cwd=ROOT,env=env,
                           capture_output=True,text=True,encoding='utf-8',errors='replace')
        self.assertEqual(run.returncode,0,run.stderr)
        from scripts.primer3_core_backend import probe_primer3_core
        self.assertEqual(run.stdout.strip(),probe_primer3_core()['status'])


if __name__=='__main__':unittest.main()
