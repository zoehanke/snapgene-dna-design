# -*- coding: utf-8 -*-
"""diff_design_spec.py - DesignSpec revision diff (v0.9.0-dev1 P1-1)."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design.spec import diff_specs  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    old = json.loads(pathlib.Path(args.old).read_text(encoding="utf-8"))
    new = json.loads(pathlib.Path(args.new).read_text(encoding="utf-8"))
    diff = diff_specs(old, new)
    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(diff, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
