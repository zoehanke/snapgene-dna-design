# -*- coding: utf-8 -*-
"""parts_library.py - M5 structured parts library lookup."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PARTS_PATH = ROOT / "parts" / "parts_library.json"


def load_parts(path=None):
    data = json.loads((pathlib.Path(path or PARTS_PATH)).read_text(
        encoding="utf-8"))
    return data["parts"]


def find_parts(name=None, part_type=None, path=None):
    parts = load_parts(path)
    result = []
    for part in parts:
        if name and name.lower() not in part["name"].lower():
            continue
        if part_type and part_type.lower() != part["type"].lower():
            continue
        result.append(part)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    parser.add_argument("--type")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = find_parts(args.name, args.type)
    payload = {"schema_version": "0.9.0", "parts": result,
               "count": len(result)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for part in result:
            print("%s [%s] %s (%s)" % (
                part["name"], part["type"], part["accession"],
                part["source"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
