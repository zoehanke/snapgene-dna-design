# -*- coding: utf-8 -*-
"""check_env.py - Verify the skill's Python environment and real backends.

Exit code 0 only when every core dependency and bundled model artifact is
present and the required primer3_core backend is available. Optional backends (Cas-OFFinder v2/v3,
SnapGene, online connectivity) is reported explicitly; it never prints
"All required deps present" when a release-real dependency is missing.
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys
from importlib.metadata import PackageNotFoundError, version

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

REQUIRED = [
    ("Bio", "biopython"),
    ("snapgene_reader", "snapgene_reader"),
    ("sgffp", "sgffp"),
    ("jsonschema", "jsonschema"),
]

OPTIONAL = [
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("matplotlib", "matplotlib"),
    ("sklearn", "scikit-learn"),
    ("torch", "torch"),
    ("h5py", "h5py"),
]

MODEL_ARTIFACTS = [
    ("third_party/azimuth/saved_models/V3_model_nopos.pickle",
     "AF933634BE494336BC95BF657B07F7599AF842A2E9601797C88A49158D040214",
     "Azimuth V3 model"),
    ("third_party/deepcpf1/Seq_deepCpf1_weights.h5",
     "DD79C3B349E409745624DB009CD8845A3991217BD8FF3A744860C4ACF696BDA3",
     "DeepCpf1 sequence weights"),
    ("third_party/deepcpf1/DeepCpf1_weights.h5",
     "946E84A2D30CEEBC57E01F00E9D4CFD396CC9B4C0B8B4A55364B0246F7343E77",
     "DeepCpf1 chromatin weights"),
]


def probe(module, dist_name):
    try:
        mod = __import__(module)
        try:
            installed_version = version(dist_name)
        except PackageNotFoundError:
            installed_version = getattr(mod, "__version__", "unknown")
        return {"module": module, "dist": dist_name, "status": "ok",
                "version": str(installed_version)}
    except ImportError as e:
        return {"module": module, "dist": dist_name, "status": "missing",
                "version": None, "error": str(e)}


def probe_model_artifacts():
    results = []
    for rel, expected_sha, label in MODEL_ARTIFACTS:
        path = ROOT / rel
        if not path.exists():
            results.append({"path": rel, "label": label, "status": "missing",
                            "expected_sha256": expected_sha})
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        results.append({
            "path": rel, "label": label,
            "status": "ok" if actual == expected_sha else "hash-mismatch",
            "expected_sha256": expected_sha,
            "actual_sha256": actual,
        })
    return results


def probe_snapgene():
    candidates = [
        os.environ.get("SNAPGENE_EXE"),
        r"D:\SnapGene\SnapGene.exe",
        r"C:\Program Files\SnapGene\SnapGene.exe",
        r"C:\Program Files (x86)\SnapGene\SnapGene.exe",
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).exists():
            return {"status": "available", "path": candidate}
    return {"status": "missing", "path": None}


def probe_online(timeout=5):
    import urllib.request
    from online_sources import NCBI_EUTILS
    try:
        url = (NCBI_EUTILS + "/"
               "esearch.fcgi?db=nucleotide&term=EGFP&retmax=1&retmode=json")
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read(256)
        return {"status": "available", "url": url}
    except Exception as error:  # noqa: BLE001
        return {"status": "offline", "error": str(error)}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Check skill environment")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check-online", action="store_true", help="Explicitly probe public NCBI connectivity")
    args = parser.parse_args()

    pyver = "%d.%d.%d" % (sys.version_info.major, sys.version_info.minor,
                          sys.version_info.micro)
    required = [probe(m, d) for m, d in REQUIRED]
    optional = [probe(m, d) for m, d in OPTIONAL]
    artifacts = probe_model_artifacts()

    from primer3_core_backend import probe_primer3_core
    primer3_core = probe_primer3_core()

    from cas_offinder_adapter import detect
    cas_v2 = detect(os.environ.get("CAS_OFFINDER_EXE"))
    cas_v3 = detect(os.environ.get("CAS_OFFINDER_EXE_V3"))

    snapgene = probe_snapgene()
    online = probe_online() if args.check_online else {"status":"not-requested", "reason":"Use --check-online for an explicit connectivity probe."}

    missing_required = [r for r in required if r["status"] == "missing"]
    bad_artifacts = [a for a in artifacts if a["status"] != "ok"]
    core_ok = not missing_required and not bad_artifacts and primer3_core['status'] == 'available'
    optional_missing = [r for r in optional if r["status"] == "missing"]
    release_real_ok = (
        core_ok and not optional_missing
        and primer3_core["status"] == "available"
        and cas_v2["installed"] and cas_v3["installed"]
    )

    report = {
        "python": pyver,
        "python_executable": sys.executable,
        "required": required,
        "optional": optional,
        "model_artifacts": artifacts,
        "primer3_core": primer3_core,
        "cas_offinder_v2": {k: cas_v2[k] for k in (
            "installed", "executable", "version", "opencl_detected")},
        "cas_offinder_v3": {k: cas_v3[k] for k in (
            "installed", "executable", "version", "opencl_detected")},
        "snapgene": snapgene,
        "online": online,
        "core_ok": core_ok,
        "release_real_ok": release_real_ok,
        "missing_required": [r["dist"] for r in missing_required] + ([] if primer3_core['status'] == 'available' else ['primer3_core']),
        "missing_optional": [r["dist"] for r in optional_missing],
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("python: %s (%s)" % (pyver, sys.executable))
        print("required dependencies:")
        for item in required:
            print("  [%s] %s %s" % (
                "OK" if item["status"] == "ok" else "MISSING",
                item["dist"], item["version"] or "-"))
        print("bundled model artifacts:")
        for item in artifacts:
            print("  [%s] %s (%s)" % (item["status"], item["label"],
                                      item["path"]))
        print("optional/real-backend dependencies:")
        for item in optional:
            print("  [%s] %s %s" % (
                "OK" if item["status"] == "ok" else "MISSING",
                item["dist"], item["version"] or "-"))
        if primer3_core["status"] == "available":
            print("primer3_core: OK (version %s, %s)" % (primer3_core.get("version"), primer3_core.get("path")))
        else:
            print("primer3_core: NOT INSTALLED")
            print("  [Auto-Fix Tip] Run 'python scripts/install_primer3.py' or 'pip install primer3-py'")
        print("cas-offinder v2: installed=%s version=%s opencl=%s" % (
            cas_v2["installed"], cas_v2["version"], cas_v2["opencl_detected"]))
        print("cas-offinder v3: installed=%s version=%s opencl=%s" % (
            cas_v3["installed"], cas_v3["version"], cas_v3["opencl_detected"]))
        print("SnapGene: %s" % snapgene["status"])
        print("NCBI online: %s" % online["status"])
        missing_names = [item["dist"] for item in optional_missing]
        print("\nCORE_ENV_OK" if core_ok else
              "CORE_ENV_MISSING: %s" % (", ".join(report['missing_required'] +
              [a["path"] for a in bad_artifacts]) or "-"))
        print("RELEASE_REAL_OK" if release_real_ok else
              "RELEASE_REAL_INCOMPLETE: %s" % ", ".join(
                  missing_names + (
                      ["primer3_core"] if primer3_core["status"] != "available" else [])
                  + (["cas-offinder-v2"] if not cas_v2["installed"] else [])
                  + (["cas-offinder-v3"] if not cas_v3["installed"] else [])))

    sys.exit(0 if core_ok else 1)


if __name__ == "__main__":
    main()
