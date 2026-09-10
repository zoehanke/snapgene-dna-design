#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/run_pipeline.py - CLI Runner for Multi-Step Composite Pipelines.

Usage:
    python scripts/run_pipeline.py --pipeline pipeline.json --out-dir ./build
    python scripts/run_pipeline.py --pipeline pipeline.json --sources vector.gb insert.fasta --out-dir ./build --confirmed

Runs multi-step DNA assembly/manipulation workflows using atomic tools from TOOL_REGISTRY.
Executes task validation, planning, deterministic step execution, 3-layer verification,
and promotes to authoritative delivery upon user confirmation.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

# Ensure project root is on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_trace.runtime import (observe, observe_value, traced_run, add_trace_arguments, trace_options, TraceStopped)

from agent.pipeline_agent import execute_agent_pipeline


def _pipeline_source_map(source_files: list[Any] | None) -> dict[str, Any]:
    """Build the same source-id map used by the agent task wrapper."""
    source_map: dict[str, Any] = {}
    for index, source in enumerate(source_files or []):
        if isinstance(source, dict):
            source_id = source.get("source_id") or f"src_{index + 1}"
            source_value = source.get("path") or source.get("file") or source.get("filepath")
        else:
            source_id = f"src_{index + 1}"
            source_value = source
        if source_value is None:
            raise ValueError(f"Source '{source_id}' has no file path")
        source_map[source_id] = source_value
    return source_map


def _infer_pipeline_topology(
    steps: list[dict[str, Any]],
    source_files: list[Any] | None,
    output_step: str | None,
) -> str:
    """Infer topology from the selected in-memory sequence output."""
    from core.handlers.composite_pipeline import _output_topology, run_pipeline_steps

    selected = output_step or steps[-1].get("step_id")
    _, _, environment = run_pipeline_steps(
        steps,
        _pipeline_source_map(source_files),
        output_step=selected,
    )
    topology = _output_topology(environment.get(selected))
    if topology is None:
        # Plain string outputs carry no topology metadata. Sequence-only tools
        # use linear as their safe default; explicit CLI metadata can still
        # request and validate a different topology.
        topology = "linear"
    return topology


def _historical_outputs(out_path: pathlib.Path) -> list[dict[str, str]]:
    """Describe pre-existing delivery artifacts without modifying them."""
    authoritative = out_path / "authoritative"
    if authoritative.exists():
        return [{
            "path": "authoritative",
            "status": "historical-not-current",
        }]
    return []


def _write_failure_result(
    out_path: pathlib.Path,
    error: BaseException,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Persist a failed invocation so a prior success cannot remain current."""
    error_payload = {
        "type": type(error).__name__,
        "message": str(error),
    }
    details = getattr(error, "details", None)
    if details:
        error_payload["details"] = details
    result = {
        "status": "failed",
        "task_id": task_id,
        "product_length": 0,
        "product_topology": None,
        "validation_report": None,
        "delivery": None,
        "authoritative_dir": None,
        "error": error_payload,
        "historical_outputs": _historical_outputs(out_path),
    }
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "pipeline_result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result


def _report_failure(
    args,
    out_path: pathlib.Path,
    error: BaseException,
    task_id: str | None = None,
) -> int:
    """Write and emit structured failure state for every handled CLI error."""
    result = _write_failure_result(out_path, error, task_id=task_id)
    observe_value("outcome", result)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Pipeline execution failed: {error}", file=sys.stderr)
    return 1


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Execute a multi-step composite DNA pipeline using atomic tools."
    )
    parser.add_argument("--pipeline", required=True, help="Path to JSON file defining pipeline steps")
    parser.add_argument("--task-id", help="Optional task ID identifier (default: derived from pipeline filename)")
    parser.add_argument("--sources", nargs="*", help="Source sequence files (.gb, .dna, .fasta)")
    parser.add_argument("--topology", default=None, choices=["circular", "linear"], help="Product topology (default: inferred from selected output or specified in pipeline JSON)")
    parser.add_argument("--out-dir", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--confirmed", action="store_true", help="Explicit user confirmation for authoritative delivery")
    parser.add_argument("--output-step", help="Sequence-producing step to deliver when later steps perform analysis")
    parser.add_argument("--open-snapgene", action="store_true", help="Launch desktop SnapGene viewer on generated construct")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    add_trace_arguments(parser)
    args = parser.parse_args()

    out_path = pathlib.Path(args.out_dir).resolve()
    try:
        return _run(args, out_path, **trace_options(args))
    except TraceStopped as exc:
        print(str(exc), file=sys.stderr)
        return 4


@traced_run("pipeline")
def _run(args, out):
    out_path = out
    out_path.mkdir(parents=True, exist_ok=True)

    pipe_path = pathlib.Path(args.pipeline)
    if not pipe_path.exists():
        return _report_failure(
            args,
            out_path,
            FileNotFoundError(f"pipeline file not found: {args.pipeline}"),
            task_id=pipe_path.stem,
        )

    try:
        pipe_data = json.loads(pipe_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _report_failure(args, out_path, exc, task_id=pipe_path.stem)

    metadata = pipe_data if isinstance(pipe_data, dict) else {}
    steps = metadata.get("steps") if isinstance(pipe_data, dict) else pipe_data
    if not isinstance(steps, list):
        return _report_failure(
            args,
            out_path,
            ValueError(
                "pipeline must contain a list of steps or an object with a 'steps' key"
            ),
            task_id=metadata.get("task_id") or pipe_path.stem,
        )

    # Resolve source files: CLI --sources overrides pipeline JSON sources
    source_files = args.sources or metadata.get("sources", [])
    if args.sources:
        parsed_sources = []
        for s in args.sources:
            if "=" in s:
                sid, spath = s.split("=", 1)
                parsed_sources.append({"source_id": sid.strip(), "path": spath.strip()})
            else:
                parsed_sources.append(s)
        source_files = parsed_sources

    task_id = args.task_id or metadata.get("task_id") or pipe_path.stem
    requested_topology = args.topology or metadata.get("topology")

    try:
        topo = requested_topology
        if topo is None:
            topo = _infer_pipeline_topology(
                steps,
                source_files,
                args.output_step or metadata.get("output_step"),
            )
        result = execute_agent_pipeline(
            task_id=task_id,
            pipeline_steps=steps,
            source_files=source_files,
            product_topology=topo,
            out_dir=out_path,
            auto_open_snapgene=args.open_snapgene,
            user_confirmed=args.confirmed,
            expected_components=metadata.get("expected_components", []),
            forbidden_components=metadata.get("forbidden_components", []),
            output_step=args.output_step or metadata.get("output_step"),
        )
        result["requested_topology"] = requested_topology
        result["actual_topology"] = result.get("actual_topology", result.get("product_topology"))

        observe_value("outcome", result)
        (out_path / "pipeline_result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            print(f"## Pipeline Execution: `{task_id}`")
            print(f"- **Status**: `{result['status']}`")
            print(f"- **Product Length**: {result['product_length']} bp ({result['product_topology']})")
            val = result.get("validation_report", {})
            print(f"- **Three-Layer Validation**: Artifacts={val.get('artifact_valid')}, Computation={val.get('computation_valid')}, Goal={val.get('goal_valid')}")
            deliv = result.get("delivery")
            if deliv:
                print(f"- **Authoritative Delivery**: `{deliv.get('directory')}`")
                print(f"- **Manifest SHA256**: `{deliv.get('manifest_sha256')}`")
                for f in deliv.get("files", []):
                    print(f"  * {f}")
            else:
                print("- **Authoritative Delivery**: Not produced; see validation and confirmation status above")
        return 0 if result.get("validation_report", {}).get("overall") == "verified" else 1

    except TraceStopped:
        raise
    except Exception as exc:
        return _report_failure(
            args,
            out_path,
            exc,
            task_id=metadata.get("task_id") or pipe_path.stem,
        )


if __name__ == "__main__":
    sys.exit(main())
