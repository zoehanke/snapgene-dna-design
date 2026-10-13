"""Synthetic full-template PCR revision and declared context change; no wet-lab claim."""
import argparse
import json
import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.pipeline_agent import execute_agent_pipeline
from evidence_trace.recorder import Recorder, project
from evidence_trace.chain import build_chains
from evidence_trace.settings import set_level
from scripts.synthetic_trace_template import PCR_INTERVAL, write_template


def run_demo():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", help="Optional legally supplied complete GenBank; default is synthetic")
    parser.add_argument("--pcr-start", type=int, default=PCR_INTERVAL[0])
    parser.add_argument("--pcr-end", type=int, default=PCR_INTERVAL[1])
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    out = Path(args.out_dir).resolve()
    if out.exists():
        raise ValueError("Use a new output directory")
    out.mkdir(parents=True)
    template = Path(args.template).resolve() if args.template else out / "synthetic-input.gb"
    if not args.template:
        write_template(template)
    from Bio import SeqIO
    with template.open(encoding="utf-8") as handle:
        original = SeqIO.read(handle, "genbank")
    start, first_end = args.pcr_start, args.pcr_end
    if not 0 <= start < first_end < first_end + 3 <= len(original):
        raise ValueError("PCR intervals lie outside supplied template")
    trace = out / "evidence-trace"
    r = Recorder(trace)
    context = {"host": "E. coli", "construct_context": "PCR donor fragment", "intended_use": "cloning preparation"}
    source_decision = {"id": "D01", "kind": "decision", "text": "从完整来源制备工程片段",
        "rationale": "以完整输入为模板，让程序计算真实扩增产物并保留源注释，不把目标片段冒充现成材料。",
        "responds_to": ["R01"], "claim_ids": ["C01"], "targets": {"step_id": "pcr", "template": "$src"}}
    boundary_decision = {"id": "D02", "kind": "decision", "text": f"先制备 {start}:{first_end} 区间的对照片段",
        "rationale": "第一版保留指定片段边界作为对照；随后显式修订末端，并检查旧验证与依据的适用范围。",
        "responds_to": ["R01"], "claim_ids": ["C01"], "targets": {"step_id": "pcr", "start": start, "end": first_end}}
    r.ingest({"actor": "demo-author", "nodes": [
        {"id": "R01", "kind": "requirement", "text": "软件演示：从完整来源扩增片段，修订尾端并追踪旧证据与验证。基因功能、表达和安全性不在本演示中实测。"},
        {"id": "S01", "kind": "source", "title": "完整工程输入记录", "source_type": "user-material" if args.template else "synthetic-construction", "path": str(template)},
        {"id": "E01", "kind": "statement", "source_id": "S01", "text": "源记录提供注释和完整模板，可用于定位扩增区间；默认合成材料的坐标来自固定构造。", "context": context},
        {"id": "C01", "kind": "claim", "text": "该记录可作为当前片段制备的来源，后续用途需按实际上下文复核。", "context": context},
        source_decision, boundary_decision], "links": [
        {"statement_id": "E01", "claim_id": "C01", "relation": "support", "aspect": "来源定位", "applicability": "partial", "strength": "declared", "limitations": ["源注释不是湿实验结果"]},
        {"statement_id": "E01", "claim_id": "C01", "relation": "constrain", "aspect": "用途外推", "applicability": "unknown", "limitations": ["不能从序列文件推出表达表现"]}]})

    def run(end, mode):
        set_level("off" if mode == "off" else "full")
        output = out / f"end-{end}-{mode}"
        result = execute_agent_pipeline("synthetic-fragment", [
            {"step_id": "pcr", "tool": "prepare_pcr_fragment", "params": {"template": "$src", "start": start, "end": end, "name": "synthetic-fragment"}}],
            [{"source_id": "src", "path": str(template)}], product_topology="linear", out_dir=output,
            user_confirmed=True, **({"trace_dir": trace} if mode == "on" else {}))
        if result["status"] != "delivered":
            raise AssertionError(result)
        return output

    first_off, first_on = run(first_end, "off"), run(first_end, "on")
    r = Recorder(trace)
    r.record({"id": "C01", "kind": "claim", "text": "该记录可作为当前片段制备的来源，后续用途需按实际上下文复核。",
              "context": {**context, "host": "Saccharomyces cerevisiae", "intended_use": "donor for a future yeast construct"}}, actor="demo-author")
    # Explicitly associate the revised claim; old links remain bound to C01@1.
    r.link({"statement_id": "E01", "claim_id": "C01", "relation": "support", "aspect": "来源坐标",
            "applicability": "extrapolated", "limitations": ["转用序列来源，不宣称酵母表达已验证"]}, actor="demo-author")
    r.record(source_decision, actor="demo-author")
    r.record({**boundary_decision, "text": f"修订尾端为 {start}:{first_end + 3}",
        "rationale": "这是本次明确的边界修订：增加末端 3 bp。沿用源模板，交由原 PCR 工具重新设计并验证，不由 Trace 修改 DNA。",
        "targets": {"step_id": "pcr", "start": start, "end": first_end + 3}}, actor="demo-author")
    second_off, second_on = run(first_end + 3, "off"), run(first_end + 3, "on")
    checks = {}
    for name, a, b in (("initial", first_off, first_on), ("revised", second_off, second_on)):
        for ext in ("gb", "dna", "fasta"):
            checks[name + "." + ext] = (a / f"authoritative/construct.{ext}").read_bytes() == (b / f"authoritative/construct.{ext}").read_bytes()
        checks[name + ".primers"] = (a / "primer_order_table.tsv").read_bytes() == (b / "primer_order_table.tsv").read_bytes()
        expected_end = first_end if name == "initial" else first_end + 3
        with (b / "authoritative/construct.gb").open(encoding="utf-8") as handle:
            checks[name + ".sequence"] = str(SeqIO.read(handle, "genbank").seq) == str(original.seq[start:expected_end])
    graph = build_chains(project(Recorder(trace).events))
    checks["formal_changes"] = bool(graph["changes"])
    checks["validation_rerun_recommended"] = any("RERUN" in i["actions"] for i in graph["impacts"])
    checks["unknown_retained"] = any(i["judgment"] == "UNKNOWN" for i in graph["impacts"])
    if not all(checks.values()):
        raise AssertionError(checks)
    summary = {"checks": checks, "view": str(trace / "index.html"), "changes": len(graph["changes"]),
               "scope": "Declared context changes and actual PCR boundary revision; no automatic scientific conclusion."}
    (out / "demo-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    # Demonstrate actual global modes in an isolated installation, never user settings.
    previous = os.environ.get("SNAPGENE_TRACE_CONFIG")
    with tempfile.TemporaryDirectory(prefix="trace-demo-config-") as temporary:
        os.environ["SNAPGENE_TRACE_CONFIG"] = str(Path(temporary) / "trace.json")
        try:
            run_demo()
        finally:
            if previous is None:
                os.environ.pop("SNAPGENE_TRACE_CONFIG", None)
            else:
                os.environ["SNAPGENE_TRACE_CONFIG"] = previous


if __name__ == "__main__":
    main()
