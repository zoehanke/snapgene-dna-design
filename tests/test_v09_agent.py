# -*- coding: utf-8 -*-
"""v0.9.0-dev1 DesignSpec / Agent Core tests."""
import json
import os
import pathlib
import random
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from design.spec import (  # noqa: E402
    DesignSpecError, clone_spec, diff_specs, formal_blockers, new_spec,
    revise, set_status, spec_sha256,
)
import validate_design_spec as validate_design_spec_module  # noqa: E402
validate_design_spec = validate_design_spec_module.validate_design_spec
from agent.session import Session, file_sha256  # noqa: E402
from agent.nl_parser import parse_request  # noqa: E402
from planning.method_selector import select_methods  # noqa: E402
from agent.orchestrator import Orchestrator  # noqa: E402


def write_gb(path, name, length, circular=True, features=()):
    rng = random.Random(name)
    terminal_tails = {
        # The planner derives circular Gibson tails from the source ends.  Use
        # deterministic, non-palindromic terminal arms so this integration
        # fixture exercises a real Primer3 pair rather than a deliberate
        # homopolymer/secondary-structure failure.
        "pBACK": "GACTGACTGACTGACTGACT",
        "pDONOR": "TCGATCGTACGATCGTAGCA",
    }
    tail = terminal_tails.get(name, "")
    sequence = "".join(rng.choice("ACGT") for _ in range(length - len(tail))) + tail
    rec = SeqRecord(Seq(sequence),
                    id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = "circular" if circular else "linear"
    for start, end, kind, label, strand in features:
        rec.features.append(SeqFeature(
            FeatureLocation(start, end, strand=strand), type=kind,
            qualifiers={"label": [label], "gene": [label]}))
    SeqIO.write(rec, path, "genbank")
    return str(path)


class DesignSpecTests(unittest.TestCase):
    def test_illegal_transition_fails(self):
        spec = new_spec("x", mode="exploration")
        with self.assertRaises(DesignSpecError):
            set_status(spec, "executed")

    def test_confirmed_spec_requires_revision(self):
        spec = new_spec("x", mode="exploration")
        set_status(spec, "needs-clarification")
        set_status(spec, "user-confirmed")
        from design.spec import set_field
        with self.assertRaises(DesignSpecError):
            set_field(spec, ["objective", "type"], "changed")

    def test_revision_changes_sha(self):
        spec = new_spec("x", mode="exploration")
        old_hash = spec_sha256(spec)
        spec2 = revise(spec, "changed")
        self.assertEqual(spec2["revision"], 2)
        self.assertNotEqual(spec_sha256(spec2), old_hash)

    def test_unknown_field_schema_failure(self):
        spec = new_spec("x", mode="exploration")
        spec["surprise"] = True
        self.assertFalse(validate_design_spec(spec)["ok"])

    def test_source_hash_mismatch_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            path = pathlib.Path(write_gb(tmp / "a.gb", "pA", 200))
            session = Session.create("test", mode="formal", files=[str(path)])
            # mutate file bytes
            path.write_text("changed", encoding="utf-8")
            session.spec["questions"] = []
            session.spec["host"] = {"organism": "E. coli"}
            session.spec["approvals"]["primers-ready-to-order"] = {
                "value": True, "evidence_layer": "user-provided"}
            with self.assertRaises(DesignSpecError):
                Orchestrator(session).resolve_evidence()

    def test_formal_mode_blocks_missing_approval(self):
        spec = new_spec("x", mode="formal")
        spec["host"] = {"organism": "E. coli"}
        spec["questions"] = []
        spec["sources"].append({
            "source_id": "s1", "source_type": "user-file",
            "sha256": "A" * 64, "source_path": "x.gb"})
        blockers = formal_blockers(spec)
        self.assertIn("PRIMERS_NOT_APPROVED_FOR_ORDER", blockers)

    def test_exploration_never_ready_to_order(self):
        spec = new_spec("x", mode="exploration")
        spec["outputs"]["ready_to_order"] = True
        self.assertFalse(validate_design_spec(spec)["ok"])


class DesignSpecDeeperTests(unittest.TestCase):
    def test_spec_helpers_and_branches(self):
        from design import spec as dspec
        # invalid evidence layer / mode / path / status / source
        with self.assertRaises(dspec.DesignSpecError):
            dspec._evidence("bad-layer", "x")
        with self.assertRaises(dspec.DesignSpecError):
            dspec.new_spec("x", mode="bad")
        s = dspec.new_spec("x")
        with self.assertRaises(dspec.DesignSpecError):
            dspec.set_field(s, [], "x")
        with self.assertRaises(dspec.DesignSpecError):
            dspec.set_status(s, "bogus")
        dspec.needs_clarification(s, [
            {"question_id": "q1", "question": "q", "category": "must-ask",
             "reason": "r"}], [{"key": "k", "reason": "r"}], "because")
        with self.assertRaises(dspec.DesignSpecError):
            dspec.confirm_user(s)
        dspec.record_answer(s, "q1", "yes")
        dspec.confirm_user(s)
        dspec.add_evidence(s, "computed", "derived")
        dspec.add_evidence(s, "assumption", "assumed")
        dspec.add_question(s, "q2", "question", "default-visible", reason="r")
        dspec.add_missing(s, "k2", "r2")
        # force transitions and revision keep_id False
        dspec.set_status(s, "evidence-resolved", force=True)
        rev = dspec.revise(s, "why", keep_id=False)
        self.assertNotEqual(rev["spec_id"], s["spec_id"])
        dspec.set_status(rev, "executed", force=True)
        # source helper errors and add source
        with self.assertRaises(dspec.DesignSpecError):
            dspec.make_sequence_source("s", "bad-type", "A"*64)
        source = dspec.make_sequence_source("s", "user-file", "A"*64,
                                            source_path="x.gb")
        dspec.add_source(rev, source, force=True)
        rev["status"] = "user-confirmed"
        with self.assertRaises(dspec.DesignSpecError):
            dspec.add_source(rev, source)
        # formal blockers branches
        fs = dspec.new_spec("", mode="formal")
        self.assertTrue(dspec.formal_blockers(fs))
        fs["host"] = {"organism": "E. coli"}
        fs["questions"] = []
        fs["sources"].append({"source_id": "db", "source_type": "database-record",
                              "accession": None, "sha256": ""})
        self.assertTrue(any(b.startswith("SOURCE_HASH_MISSING")
                            or b.startswith("DATABASE_SOURCE")
                            for b in dspec.formal_blockers(fs)))
        self.assertEqual(dspec.delivery_flags(fs)["ready_to_order"], False)

    def test_diff_all_tracked_fields(self):
        from design import spec as dspec
        a = dspec.new_spec("a")
        b = dspec.clone_spec(a)
        for field in dspec.TRACKED_KEYS:
            b[field] = {"changed": True}
        diff = dspec.diff_specs(a, b)
        self.assertEqual(len(diff["changes"]), len(dspec.TRACKED_KEYS))
        self.assertNotEqual(diff["from_sha256"], diff["to_sha256"])


class NlParser30ScenarioTests(unittest.TestCase):
    def _summaries(self, tmp, names):
        files = {}
        for idx, name in enumerate(names):
            path = tmp / ("%s.gb" % name)
            features = [(10, 100, "promoter", "P%d" % idx, 1),
                        (110, 300, "CDS", "orf%d" % idx, 1)]
            write_gb(path, name, 400, features=features)
            from agent.session import summarize_file
            files[str(path)] = summarize_file(path)
        return files

    def test_30_review_scenarios(self):
        complete = [
            "把质粒 A 的启动子换成质粒 B 的启动子，宿主是酵母，优先考虑 Golden Gate",
            "Replace promoter in plasmid A with promoter from plasmid B, host is E. coli, use Gibson",
            "将 pBACK 的抗性基因替换为 pDONOR 的卡那霉素抗性，宿主大肠杆菌",
            "把文件一的 ORF 融合到文件二骨架上，加 6xHis 标签，E. coli",
            "用 Golden Gate 组装四个片段，宿主 E. coli，用 BsaI",
            "Gibson insert donor CDS into backbone, E. coli",
            "Gateway LR from entry to destination, E. coli",
            "对 pA 的 orf 做点突变 100:A，宿主 E. coli",
            "设计 CRISPR HDR donor 替换 pA 的 orf，哺乳动物细胞",
            "assemble two files into one plasmid, host yeast",
        ]
        ambiguous = [
            "把质粒 A 的启动子换掉",           # no donor/host
            "replace promoter with another promoter",  # no files/roles
            "把那个片段放进去",               # no file referent
            "用文件组装",                     # no method/fragment
            "插入 promoter 并表达",           # no host
            "替换抗性",                       # no target
            "做 Golden Gate",                # no files
            "mutate something",              # no target
            "构建一个质粒",                   # no files
            "clone the promoter",            # no files
        ]
        conflicts = [
            "用 Golden Gate，但片段里有 BsaI 位点，不要换酶",
            "使用 Gibson 和 digest-ligate 同时进行",
            "宿主是酵母，但要求用 Gateway LR",
            "要求无引物，但要求 Gibson PCR 组装",
            "要求片段超过 8 个，还要一锅 Golden Gate",
            "使用 Gateway，但输入没有 entry 载体",
            "要求点突变，又要求完全替换整个质粒",
            "要求同时使用 BsaI 和 BsmBI，但只允许一种酶",
            "要求 3kb 合成，但不允许合成",
            "要求上传 BLAST，但不允许上传序列",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            files = self._summaries(tmp, ["pBACK", "pDONOR", "pENTRY", "pDEST"])
            all_cases = ([("complete", text) for text in complete] +
                         [("ambiguous", text) for text in ambiguous] +
                         [("conflict", text) for text in conflicts])
            self.assertEqual(len(all_cases), 30)
            for category, text in all_cases:
                parsed = parse_request(text, files)
                self.assertEqual(parsed["spec"]["raw_objective"], text)
                self.assertEqual(parsed["spec"]["mode"], "exploration")
                if category == "complete":
                    self.assertTrue(parsed["questions"] or
                                    parsed["spec"]["objective"].get("type"),
                                    text)
                if category == "ambiguous":
                    self.assertTrue(parsed["questions"], text)

    def test_corrected_request_makes_new_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            files = self._summaries(tmp, ["pBACK", "pDONOR"])
            first = parse_request("替换启动子，宿主酵母", files)["spec"]
            second = parse_request("替换抗性基因，宿主大肠杆菌", files,
                                   previous_spec=first)["spec"]
            self.assertEqual(second["revision"], first["revision"] + 1)
            self.assertNotEqual(spec_sha256(first), spec_sha256(second))


class MethodSelectorTests(unittest.TestCase):
    def test_required_context_matrix(self):
        cases = [
            {"name": "multi-fragment no internal sites",
             "ctx": {"fragment_count": 3},
             "expect": ["gibson", "golden_gate"]},
            {"name": "internal BsaI",
             "ctx": {"internal_type_iis_sites": True},
             "expect": ["gibson"]},
            {"name": "unique two enzyme",
             "ctx": {"unique_two_enzyme": True},
             "expect": ["digest_ligate"]},
            {"name": "lab lacks enzyme",
             "ctx": {"fragment_count": 3, "unique_two_enzyme": True},
             "expect": []},
            {"name": "too many fragments",
             "ctx": {"fragment_count": 9},
             "expect": []},
            {"name": "high gc / long",
             "ctx": {"high_gc": True, "long_fragment": True},
             "expect": []},
            {"name": "gateway entry dest",
             "ctx": {"entry_destination": True},
             "expect": ["gateway"]},
            {"name": "point mutation",
             "ctx": {"point_mutation": True},
             "expect": ["site_directed_mutagenesis_pcr"]},
            {"name": "too large",
             "ctx": {"total_length": 40000},
             "expect": []},
            {"name": "primer failed",
             "ctx": {"primer_design_failed": True, "total_length": 2000},
             "expect": ["synthesis_or_staged"]},
        ]
        for case in cases:
            with self.subTest(case=case["name"]):
                result = select_methods({}, case["ctx"])
                self.assertTrue(result["candidates"])
                self.assertTrue(result["selected"] or result["excluded"])
                self.assertTrue(all(
                    "score" in c and "source_evidence" in c and
                    "hard_blockers" in c and "required_materials" in c
                    for c in result["candidates"]))


class AgentOrchestratorBranchTests(unittest.TestCase):
    def test_branch_helpers_and_failures(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            tmp=pathlib.Path(tmp)
            path=write_gb(tmp/"a.gb","pA",300)
            session=Session.create("test", mode="exploration", files=[path],
                                   workdir=tmp/"out")
            orch=Orchestrator(session, out_dir=tmp/"out")
            self.assertTrue(Orchestrator._primers_required(
                {"objective": {"type": "assembly"}}))
            self.assertFalse(Orchestrator._primers_required(
                {"objective": {"type": "gateway-lr"}}))
            ctx=Orchestrator._method_context(
                {"objective": {"type": "gateway-lr"}})
            self.assertTrue(ctx["entry_destination"])
            intent=orch._intent_for_plan(
                {"objective": {"type": "assembly", "target_feature": "EGFP",
                               "file_roles": [{"role": "backbone",
                                                "path": path}]},
                 "constraints": {}, "target": {}, "raw_objective": "x"},
                [path, path], "gibson", {path: 300})
            self.assertEqual(intent["backbone"]["source"], 0)
            self.assertIn("feature", intent["fragments"][0])
            actions=Orchestrator._recovery_for(
                {"constraints": {}}, "golden_gate",
                mock.Mock(stderr="BsaI site", stdout=""))
            self.assertTrue(actions)
            orch.block_with_recovery("test failure", ["do x"])
            self.assertEqual(session.spec["status"], "blocked")
            session.construct_gb = None
            with self.assertRaises(DesignSpecError):
                orch.verify()
            # plan with no selected route
            with mock.patch("agent.orchestrator.select_methods",
                            return_value={"candidates": [{"hard_blockers": ["x"]}],
                                          "selected": None}):
                result=orch.plan()
                self.assertIsNone(result["selected"])
            # formal execute without primer3
            session2=Session.create("test2", mode="formal", files=[path],
                                    workdir=tmp/"out2")
            orch2=Orchestrator(session2, out_dir=tmp/"out2")
            session2.spec["questions"]=[]
            session2.spec["approvals"]["primers-ready-to-order"]={"value": True}
            with mock.patch("primer3_core_backend.probe_primer3_core",
                            return_value={"status": "unavailable"}):
                with self.assertRaises(DesignSpecError):
                    orch2.execute()
            self.assertEqual(session2.spec["status"], "blocked")
            # deliver formal blockers before verified
            session2.spec["status"]="planned"
            session2.spec["mode"]="formal"
            session2.spec["sources"]=[]
            with self.assertRaises(DesignSpecError):
                orch2.deliver()
            self.assertEqual(session2.spec["status"], "blocked")


class AgentE2ETests(unittest.TestCase):
    def _run_chain(self, text, tmp, paths=None, mode="exploration",
                   answer=True, deliver=True):
        if paths is None:
            paths=[]
            for idx,name in enumerate(("pBACK","pDONOR")):
                paths.append(write_gb(tmp / ("%s.gb" % name), name,
                                      400+idx*40,
                                      features=[(10,120,"promoter","P%d"%idx,1),
                                                (130,320,"misc_feature","orf%d"%idx,1)]))
        session=Session.create(text, mode=mode, files=paths,
                               workdir=tmp/"out")
        orch=Orchestrator(session, out_dir=tmp/"out")
        parsed=orch.start(text, paths)
        if answer:
            for question in parsed["questions"]:
                orch.answer(question["question_id"], "auto-confirmed")
            orch.confirm()
            orch.resolve_evidence()
            orch.plan()
            orch.execute()
            orch.verify()
            delivery=orch.deliver() if deliver else None
            return session, delivery
        return session, orch, parsed

    def test_10_end_to_end_chains(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=pathlib.Path(tmp)
            coverage_mode = bool(os.environ.get("COVERAGE_PROCESS_START"))
            # 1..9 complete chains with appropriate files
            normal_tasks=[
                ("把质粒 A 的启动子换成质粒 B 的启动子，宿主是酵母，用 Gibson", None),
                ("将骨架的抗性基因替换为供体的卡那霉素抗性，宿主大肠杆菌，用 Gibson", None),
                ("在骨架上融合供体的 6xHis 标签，宿主大肠杆菌", None),
                ("用 Golden Gate 组装两个片段，宿主大肠杆菌", None),
                ("用 Gibson 插入供体片段，宿主大肠杆菌", None),
                ("组装两个质粒片段，宿主酵母", None),
            ]
            if coverage_mode:
                normal_tasks = normal_tasks[:2]
            for text,_ in normal_tasks:
                with self.subTest(text=text):
                    if "Golden Gate" in text:
                        # This fixture intentionally has no Type IIS sites. A
                        # user-explicit Golden Gate request must block rather
                        # than silently switch to Gibson or invent cut sites.
                        session = Session.create(text, mode="exploration",
                                                 files=[], workdir=tmp / "blocked")
                        orch = Orchestrator(session, out_dir=tmp / "blocked")
                        paths = []
                        for idx, name in enumerate(("pBACK", "pDONOR")):
                            paths.append(write_gb(
                                tmp / ("%s_blocked.gb" % name), name,
                                400 + idx * 40,
                                features=[(10, 120, "promoter", "P%d" % idx, 1),
                                          (130, 320, "misc_feature",
                                           "orf%d" % idx, 1)]))
                        parsed = orch.start(text, paths)
                        for question in parsed["questions"]:
                            orch.answer(question["question_id"], "auto-confirmed")
                        orch.confirm(); orch.resolve_evidence(); orch.plan()
                        with self.assertRaises(DesignSpecError):
                            orch.execute()
                        self.assertEqual(session.spec["status"], "blocked")
                        continue
                    session, delivery=self._run_chain(text, tmp)
                    self.assertIn(session.spec["status"], ("verified","delivered"))
                    self.assertTrue(delivery)
            if coverage_mode:
                return
            # Gateway LR with real Gateway fixtures
            gw_paths=[str(ROOT/"fixtures/golden/pENTR-EmGFP.gb"),
                      str(ROOT/"fixtures/golden/pDEST40.dna")]
            if not (ROOT/"fixtures/golden/pENTR-EmGFP.gb").exists() or not (ROOT/"fixtures/golden/pDEST40.dna").exists():
                self.skipTest("Gateway academic fixtures not packaged")
            with self.subTest(text="Gateway LR"):
                session,delivery=self._run_chain(
                    "Gateway LR 从 entry 到 destination，宿主大肠杆菌",
                    tmp, paths=gw_paths)
                self.assertIn(session.spec["status"], ("verified","delivered"))
            # point mutation with one template
            mut_path=write_gb(tmp/"template.gb","pTEMPLATE",600,
                              features=[(20,500,"CDS","orf",1)])
            with self.subTest(text="point mutation"):
                session,delivery=self._run_chain(
                    "对模板做定点突变 100:A，宿主大肠杆菌",
                    tmp, paths=[mut_path])
                self.assertIn(session.spec["status"], ("verified","delivered"))
            # CRISPR HDR donor as plan assembly
            with self.subTest(text="CRISPR HDR donor"):
                session,delivery=self._run_chain(
                    "为 CRISPR HDR 构建供体质粒，宿主哺乳动物细胞",
                    tmp, paths=None)
                self.assertIn(session.spec["status"], ("verified","delivered"))
            # formal mode chain: v0.9.1 legacy formal path is deprecated at
            # the orchestrator level too; only the ConstructionTask runtime
            # may run formal construction.
            with self.subTest(text="formal mode chain refuses"):
                formal_paths = [write_gb(tmp / "fa.gb", "pA", 300),
                                write_gb(tmp / "fb.gb", "pB", 300)]
                session = Session.create(
                    "把质粒 A 的启动子换成质粒 B 的启动子，宿主大肠杆菌，用 Gibson",
                    mode="formal", files=formal_paths,
                    workdir=tmp / "outformal")
                orch_f = Orchestrator(session, out_dir=tmp / "outformal")
                with self.assertRaises(DesignSpecError) as cm:
                    orch_f.start(
                        "把质粒 A 的启动子换成质粒 B 的启动子，宿主大肠杆菌，用 Gibson",
                        formal_paths)
                self.assertIn("LEGACY_AGENT_FORMAL_DEPRECATED",
                              str(cm.exception))
                self.assertEqual(session.spec["status"], "blocked")
            # 10: insufficient information must block, not guess
            with self.subTest(text="insufficient information blocks"):
                session,orch,parsed=self._run_chain(
                    "信息不足", tmp, paths=None, answer=False)
                self.assertEqual(session.spec["status"], "needs-clarification")
                orch.block_with_recovery(
                    "missing information not answered",
                    ["提供文件角色、宿主与构建目标后重新开始"])
                self.assertEqual(session.spec["status"], "blocked")


class DesignSpecCliTests(unittest.TestCase):
    def test_run_design_agent_cli_delivers(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            tmp=pathlib.Path(tmp)
            write_gb(tmp/"a.gb","pA",300)
            write_gb(tmp/"b.gb","pB",300)
            completed=subprocess.run(
                [sys.executable,"-X","utf8","-B",
                 str(SCRIPTS/"run_design_agent.py"),
                 "--text","把质粒 A 的启动子换成质粒 B 的启动子，宿主酵母，用 Gibson",
                 "--files",str(tmp/"a.gb"),str(tmp/"b.gb"),
                 "--mode","exploration","--auto-confirm","--deliver",
                 "--json","--out-dir",str(tmp/"out")],
                capture_output=True,text=True,encoding="utf-8",
                errors="replace",timeout=180)
            self.assertEqual(completed.returncode,0,
                             (completed.stdout+completed.stderr)[-2000:])
            payload=json.loads(completed.stdout)
            self.assertEqual(payload["status"],"delivered")
            self.assertTrue((tmp/"out"/"preview"/"DELIVERY-MANIFEST.json").exists())
            # v0.9.1: the legacy keyword-parser formal path is deprecated and
            # must refuse to execute.
            formal=subprocess.run(
                [sys.executable,"-X","utf8","-B",
                 str(SCRIPTS/"run_design_agent.py"),
                 "--text","把质粒 A 的启动子换成质粒 B 的启动子，宿主酵母，用 Gibson",
                 "--files",str(tmp/"a.gb"),str(tmp/"b.gb"),
                 "--mode","formal","--json","--out-dir",str(tmp/"formal")],
                capture_output=True,text=True,encoding="utf-8",
                errors="replace",timeout=180)
            self.assertEqual(formal.returncode,4)
            formal_payload=json.loads(formal.stdout)
            self.assertEqual(formal_payload["error_code"],
                             "LEGACY_AGENT_FORMAL_DEPRECATED")
            self.assertFalse((tmp/"formal"/"authoritative").exists())

    def test_diff_design_spec_cli(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            tmp=pathlib.Path(tmp)
            from design.spec import new_spec, revise
            old=new_spec("x")
            old["objective"]={"type":"a"}
            new=revise(old,"changed")
            new["objective"]={"type":"b"}
            (tmp/"old.json").write_text(json.dumps(old),encoding="utf-8")
            (tmp/"new.json").write_text(json.dumps(new),encoding="utf-8")
            completed=subprocess.run(
                [sys.executable,"-X","utf8","-B",
                 str(SCRIPTS/"diff_design_spec.py"),
                 "--old",str(tmp/"old.json"),"--new",str(tmp/"new.json"),
                 "--out",str(tmp/"diff.json")],
                capture_output=True,text=True,encoding="utf-8",errors="replace")
            self.assertEqual(completed.returncode,0,completed.stderr)
            diff=json.loads((tmp/"diff.json").read_text(encoding="utf-8"))
            self.assertEqual(diff["from_revision"],1)
            self.assertEqual(diff["to_revision"],2)
            self.assertTrue(any(c["field"]=="objective" for c in diff["changes"]))


class AgentSessionTests(unittest.TestCase):
    def test_session_branches(self):
        from agent.session import Session, summarize_file, file_sha256
        with tempfile.TemporaryDirectory() as tmp:
            tmp=pathlib.Path(tmp)
            path=write_gb(tmp/"a.gb","pA",300)
            summary=summarize_file(path)
            self.assertEqual(summary["length"],300)
            self.assertEqual(file_sha256(path),summary["sha256"])
            bad=tmp/"bad.fa"
            bad.write_text("no fasta here",encoding="utf-8")
            bad_summary=summarize_file(bad)
            self.assertTrue(bad_summary.get("error"))
            session=Session.create("x",mode="exploration",files=[path,bad])
            self.assertEqual(session.file_alias_candidates("pA")[0]["path"],str(path))
            self.assertEqual(session.check_file_hashes(),[])
            session.answer("q1","yes")
            snapshot=session.snapshot()
            self.assertIn("spec",snapshot)
            session.revise("changed")
            self.assertEqual(session.spec["revision"],2)
            self.assertEqual(len(session.log),4)


class ValidateDesignSpecCliTests(unittest.TestCase):
    def test_validate_function_branches(self):
        from design import spec as dspec
        # not object
        self.assertFalse(validate_design_spec([])["ok"])
        s = dspec.new_spec("x")
        s["schema_version"] = "0.9.0"
        self.assertFalse(validate_design_spec(s)["ok"])
        s = dspec.new_spec("x")
        s["status"] = "unknown"
        self.assertFalse(validate_design_spec(s)["ok"])
        s = dspec.new_spec("x")
        s["revision"] = "1"
        self.assertFalse(validate_design_spec(s)["ok"])
        s = dspec.new_spec("x")
        s["mode"] = "other"
        self.assertFalse(validate_design_spec(s)["ok"])
        s = dspec.new_spec("x", mode="formal")
        s["host"] = {"organism": "E. coli"}
        s["questions"] = []
        s["status"] = "delivered"
        s["sources"] = [{"source_id": "s1", "source_type": "user-file",
                         "sha256": "A"*64}]
        s["approvals"]["primers-ready-to-order"] = {"value": True}
        result = validate_design_spec(s)
        self.assertFalse(result["ok"])  # missing roundtrip verification
        s["outputs"]["roundtrip_verified"] = True
        result = validate_design_spec(s)
        self.assertTrue(result["ok"])
        self.assertTrue(result["warnings"])

    def test_validate_main_branches(self):
        import contextlib, io, json as _json
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            tmp=pathlib.Path(tmp)
            good=tmp/"good.json"
            spec=new_spec("x")
            good.write_text(_json.dumps(spec),encoding="utf-8")
            # valid path text + json
            buf=io.StringIO()
            with mock.patch.object(sys,"argv",["validate_design_spec.py",str(good)]), contextlib.redirect_stdout(buf):
                self.assertEqual(validate_design_spec_module.main(),0)
            # non-object invalid path
            bad=tmp/"bad.json"
            bad.write_text("[]",encoding="utf-8")
            with mock.patch.object(sys,"argv",["validate_design_spec.py",str(bad),"--json"]), contextlib.redirect_stdout(buf):
                self.assertEqual(validate_design_spec_module.main(),1)
            # missing file
            with mock.patch.object(sys,"argv",["validate_design_spec.py",str(tmp/"missing.json"),"--json"]), contextlib.redirect_stdout(buf):
                self.assertEqual(validate_design_spec_module.main(),2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
