"""Reproducible Q3-derived Trace demo; uses a supplied complete pBP-eGFP record."""
import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--template", required=True, help="Complete 2808 bp pBP-eGFP GenBank, see tests/data/README.md")
    p.add_argument("--out-dir", required=True, help="New demo directory")
    args = p.parse_args()
    template, out = pathlib.Path(args.template).resolve(), pathlib.Path(args.out_dir).resolve()
    from Bio import SeqIO
    with template.open(encoding="utf-8") as handle:
        original = SeqIO.read(handle, "genbank")
    if len(original) != 2808 or str(original.seq[198:201]) != "TAT" or str(original.seq[435:438]) != "TAT":
        raise ValueError("This demo requires the unchanged Q3 pBP-eGFP record; do not substitute coordinates")
    if out.exists():
        raise ValueError("Use a new output directory to preserve previous demo evidence")
    out.mkdir(parents=True)
    trace = out / "evidence-trace"
    commands = []

    def write(name, value):
        path = out / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def run(script, *parts):
        command = [sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts" / script), *map(str, parts)]
        target = str(parts[parts.index("--out-dir") + 1]) if "--out-dir" in parts else ""
        level = "off" if target.endswith("-off") else "full"
        config = write("demo-trace-settings.json", {"trace_level": level})
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env={**os.environ, "SNAPGENE_TRACE_CONFIG": config})
        commands.append({"command": command, "exit_code": done.returncode, "stderr": done.stderr})
        write("commands.json", commands)
        if done.returncode:
            raise RuntimeError(done.stderr + done.stdout)
        return json.loads(done.stdout)

    source_url = "https://www.addgene.org/kits/freemont-ecoflex-moclo/"
    bundle = {"actor": "demo-author:host-assistant", "nodes": [
        {"id": "R-GFP", "kind": "requirement", "text": "演示任务：从完整 pBP-eGFP 制备 Y66H，随后追加 Y145F 作为比较变体；保留骨架并交付引物与正式文件。", "origin": "Q3-derived authored demonstration, not a new wet-lab result"},
        {"id": "S-EcoFlex", "kind": "source", "title": "Addgene EcoFlex MoClo Kit", "source_type": "reference-database", "url": source_url,
         "verification_status": "verified", "verification": {"verifier": "host-assistant, external page inspection", "method": "Official kit page read", "checked_at": "2026-09-10", "locator": source_url, "scope": "Kit identity, E. coli context and public GenBank resource; not current file identity or phenotype"}},
        {"id": "S-Heim", "kind": "source", "title": "Engineering green fluorescent protein for improved brightness, longer wavelengths and fluorescence resonance energy transfer", "source_type": "published-paper", "pmid": "8673464", "verification_status": "verified",
         "verification": {"verifier": "host-assistant, external PubMed search", "method": "PubMed bibliographic record and abstract", "checked_at": "2026-09-10", "locator": "https://pubmed.ncbi.nlm.nih.gov/8673464/", "scope": "Title, authors, year and abstract; no validation of this construct's fluorescence"}},
        {"id": "E-kit", "kind": "statement", "text": "EcoFlex 提供面向 E. coli 的模块化部件与 GenBank 资源。", "source_id": "S-EcoFlex", "locator": "Description / Depositor-provided Files", "context": {"host": "E. coli"}},
        {"id": "E-mutation", "kind": "statement", "text": "GFP 发色团酪氨酸的替换可改变发射颜色；论文研究进一步突变对变体的影响。", "source_id": "S-Heim", "locator": "Abstract", "limitations": ["不能据此认定本任务完整质粒的荧光表现"]},
        {"id": "C-source", "kind": "claim", "text": "采用提供的完整 EcoFlex 记录，避免只保留 CDS 而丢掉骨架。", "context": {"host": "E. coli", "evidence_limit": "实际模板身份另由文件和序列核对"}},
        {"id": "C-edit", "kind": "claim", "text": "先构建 Y66H，作为后续追加突变的实际模板；表型仍需实验确认。", "limitations": ["文献支持研究动机，不替代当前构建的表型实验"]},
        {"id": "D-source", "kind": "decision", "text": "选择完整 pBP-eGFP 作为源模板", "rationale": "保留 2808 bp 环形模板及骨架注释，用实际 PCR 产物完成改造。", "responds_to": ["R-GFP"], "claim_ids": ["C-source"], "decision_kind": "component_selection", "targets": {"parameter": "template_seq_or_file", "file": str(template)}},
        {"id": "D-edit", "kind": "decision", "text": "采用 inverse PCR 引入 Y66H", "rationale": "指定原始记录的 198:201 区间由 TAT 改为 CAT；完整引物和扩增结果由现有 Recipe 计算。", "responds_to": ["R-GFP"], "claim_ids": ["C-edit"], "decision_kind": "method_selection", "targets": {"start_0based": 198, "end_0based": 201, "alt_seq": "CAT"}}
    ], "links": [
        {"statement_id": "E-kit", "claim_id": "C-source", "relation": "contextualize", "strength": "context only", "applicability": "direct", "conditions": ["E. coli design context"], "limitations": ["Kit page does not validate this local file"]},
        {"statement_id": "E-mutation", "claim_id": "C-edit", "relation": "support", "aspect": "GFP variant comparison motivation", "strength": "partial", "applicability": "partial", "conditions": ["source protein numbering checked against Q3 reference"]},
        {"statement_id": "E-mutation", "claim_id": "C-edit", "relation": "constrain", "aspect": "phenotype prediction", "strength": "not established", "applicability": "unknown", "limitations": ["当前宿主、培养条件和表达背景未实测；不承诺颜色或亮度"]}
    ]}
    run("trace_design.py", "record", "--trace-dir", trace, "--input", write("decisions-v1.json", bundle))
    params = {"template_seq_or_file": str(template), "start_0based": 198, "end_0based": 201,
              "alt_seq": "CAT", "target_flank_bp": 25, "method": "inverse_pcr"}
    outputs = []
    for mode in ("off", "on"):
        target = out / ("y66h-" + mode)
        result = run("run_recipe.py", "--recipe", "site_directed_mutagenesis", "--params-json", write("params-y66h.json", params),
                     "--out-dir", target, "--finalize", "--confirmed", "--json", *(["--trace-dir", trace] if mode == "on" else []))
        outputs.append(result)
    # An explicit design revision, recorded before running the second construct.
    revision = {"actor": "demo-author:host-assistant", "nodes": [
        {"id": "C-edit", "kind": "claim", "text": "保留 Y66H，再加入 Y145F 形成比较候选；不把文献背景外推为本构建已验证亮度。", "limitations": ["候选选择来自演示任务要求，表型收益未验证"]},
        {"id": "D-edit", "kind": "decision", "text": "修订：使用真实 Y66H 产物追加 Y145F", "rationale": "从第一轮已生成的完整模板进行第二次 inverse PCR；435:438 改为 TTT，保持前一突变和其余骨架。", "responds_to": ["R-GFP"], "claim_ids": ["C-edit"], "decision_kind": "mutation_selection", "targets": {"start_0based": 435, "end_0based": 438, "alt_seq": "TTT"}}
    ], "links": [{"statement_id": "E-mutation", "claim_id": "C-edit", "relation": "contextualize", "strength": "motivation only", "applicability": "partial", "limitations": ["未证明这一源背景下 Y145F 的效应"]}]}
    run("trace_design.py", "record", "--trace-dir", trace, "--input", write("decisions-v2.json", revision))
    first = out / "y66h-on/authoritative/construct.gb"
    revised = {**params, "template_seq_or_file": str(first), "start_0based": 435, "end_0based": 438, "alt_seq": "TTT"}
    run("run_recipe.py", "--recipe", "site_directed_mutagenesis", "--params-json", write("params-double.json", revised),
        "--out-dir", out / "double", "--finalize", "--confirmed", "--json", "--trace-dir", trace)
    # Separate physical PCR workflow exercises the Pipeline route and primer-source artifacts.
    pipeline = {"task_id": "gfp-fragment", "topology": "linear", "output_step": "pcr",
        "sources": [{"source_id": "source", "path": str(template)}], "steps": [
            {"step_id": "pcr", "tool": "prepare_pcr_fragment", "params": {"template": "$source", "start": 6, "end": 720, "name": "gfp-fragment"}},
            {"step_id": "inspect", "tool": "calc_primer_tm", "params": {"primer_seq": "ATGGCTAGCAAAGGAGAAGAA"}}]}
    for mode in ("off", "on"):
        run("run_pipeline.py", "--pipeline", write("pipeline.json", pipeline), "--out-dir", out / ("pipeline-" + mode),
            "--confirmed", "--json", *(["--trace", "--trace-input", write("pipeline-context.json", {
                "actor": "demo-author:host-assistant", "nodes": [
                    {"id": "R-PCR", "kind": "requirement", "text": "从完整来源制备 GFP 片段并交付完整引物和源注释。"},
                    {"id": "D-PCR", "kind": "decision", "text": "扩增原始模板 6:720 区间", "rationale": "边界来自当前源记录；后续分析步骤不改变选定 PCR 产物。", "responds_to": ["R-PCR"], "decision_kind": "boundary_selection"}]
            })] if mode == "on" else []))
    checks = {}
    for route in ("y66h", "pipeline"):
        for ext in ("gb", "dna", "fasta"):
            a = (out / (route + "-off") / "authoritative" / ("construct." + ext)).read_bytes()
            b = (out / (route + "-on") / "authoritative" / ("construct." + ext)).read_bytes()
            checks[route + "." + ext] = a == b
    with (out / "double/authoritative/construct.gb").open(encoding="utf-8") as h:
        final = SeqIO.read(h, "genbank")
    expected = str(original.seq[:198]) + "CAT" + str(original.seq[201:435]) + "TTT" + str(original.seq[438:])
    checks["double_mutant_sequence"] = str(final.seq) == expected
    if not all(checks.values()):
        raise AssertionError(checks)
    summary = {"checks": checks, "view": str(trace / "index.html"), "final_construct": str(out / "double/authoritative/construct.dna"),
               "scope": "Q3-derived computational demonstration; no fluorescence or safety claim; source checks recorded 2026-09-10 are historical, not rechecked by this script."}
    write("demo-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
