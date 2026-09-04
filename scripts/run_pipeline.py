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

from agent.pipeline_agent import execute_agent_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Execute a multi-step composite DNA pipeline using atomic tools."
    )
    parser.add_argument("--pipeline", required=True, help="Path to JSON file defining pipeline steps")
    parser.add_argument("--task-id", help="Optional task ID identifier (default: derived from pipeline filename)")
    parser.add_argument("--sources", nargs="*", help="Source sequence files (.gb, .dna, .fasta)")
    parser.add_argument("--topology", default="circular", choices=["circular", "linear"], help="Product topology (default: circular)")
    parser.add_argument("--out-dir", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--confirmed", action="store_true", help="Explicit user confirmation for authoritative delivery")
    parser.add_argument("--open-snapgene", action="store_true", help="Launch desktop SnapGene viewer on generated construct")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    pipe_path = pathlib.Path(args.pipeline)
    if not pipe_path.exists():
        print(f"Error: pipeline file not found: {args.pipeline}", file=sys.stderr)
        sys.exit(1)

    try:
        pipe_data = json.loads(pipe_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error parsing pipeline JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    steps = pipe_data.get("steps") if isinstance(pipe_data, dict) else pipe_data
    if not isinstance(steps, list):
        print("Error: pipeline must contain a list of steps or an object with a 'steps' key", file=sys.stderr)
        sys.exit(1)

    # Resolve source files: CLI --sources overrides pipeline JSON sources
    source_files = args.sources or pipe_data.get("sources", [])
    if isinstance(source_files, list) and source_files and isinstance(source_files[0], dict):
        source_files = [s.get("path") or s.get("file") for s in source_files]

    task_id = args.task_id or pipe_data.get("task_id") or pipe_path.stem
    topo = args.topology or pipe_data.get("topology", "circular")

    try:
        result = execute_agent_pipeline(
            task_id=task_id,
            pipeline_steps=steps,
            source_files=source_files,
            product_topology=topo,
            out_dir=args.out_dir,
            auto_open_snapgene=args.open_snapgene,
            user_confirmed=args.confirmed,
        )

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
                print("- **Authoritative Delivery**: Skipped or Pending user confirmation (--confirmed)")

    except Exception as exc:
        print(f"Pipeline execution failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
