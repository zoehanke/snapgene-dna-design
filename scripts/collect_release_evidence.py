# -*- coding: utf-8 -*-
"""collect_release_evidence.py - Write RC dependency/real-backend evidence."""
import json
import pathlib
import sys
from importlib.metadata import version as dist_version

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _version(dist, fallback=None):
    try:
        return dist_version(dist)
    except Exception:  # noqa: BLE001
        return fallback


def main():
    out = ROOT / "reports" / "release-dependency-evidence.json"
    evidence = {
        "schema_version": "0.9.0-dev1",
        "project_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "python": "%d.%d.%d" % sys.version_info[:3],
        "python_executable": sys.executable,
        "core_dependencies": {
            "biopython": _version("biopython"),
            "snapgene_reader": _version("snapgene_reader"),
            "sgffp": _version("sgffp"),
            "jsonschema": _version("jsonschema"),
        },
        "real_backend_dependencies": {
            "numpy": _version("numpy"),
            "pandas": _version("pandas"),
            "matplotlib": _version("matplotlib"),
            "scikit-learn": _version("scikit-learn"),
            "torch": _version("torch"),
            "h5py": _version("h5py"),
        },
        "expected_reference_values": {
            "azimuth_30mer_score": 0.31682680735151075,
            "deepcpf1_seq_only_scores": [0.5346983671188354,
                                         0.5569930672645569],
            "deepcpf1_chromatin_scores": [0.0793292298913002,
                                          0.46077480912208557,
                                          0.4409549832344055,
                                          0.08181221783161163],
        },
        "instructions": [
            "Install requirements.txt and requirements-optional.txt.",
            "Run `python scripts/check_env.py --json`; archive `release_real_ok: true`.",
            "Run the real-backend gate with SNAPGENE_RUN_REAL_MODELS=1, "
            "SNAPGENE_RUN_PRIMER3=1, SNAPGENE_RUN_ONLINE=1, PRIMER3_CORE, "
            "CAS_OFFINDER_EXE and CAS_OFFINDER_EXE_V3.",
            "Archive `coverage_gate.py --mode release-real` output; it must "
            "show gate PASS.",
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
