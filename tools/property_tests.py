# -*- coding: utf-8 -*-
"""property_tests.py - Full-scale seeded property tests for the v0.5 gate.

Required scale (release gate):
    gibson, infusion, golden-gate, digest-ligate: 1,000 success + 300 failure
    gateway, ta:                                  500 success + 200 failure

Every success case asserts biological/structural invariants on the product;
every failure case asserts a structured, stable AssemblyError code. All
generators are seeded (deterministic runs) and in-process for speed. A JSON
report is written to ``reports/property/property-tests.json``.

Usage::

    python -X utf8 tools/property_tests.py             # full gate scale
    python -X utf8 tools/property_tests.py --quick     # 5% for CI/smoke
    python -X utf8 tools/property_tests.py --methods gibson,ta
    python -X utf8 tools/property_tests.py --json
"""

from project_paths import PROJECT_ROOT as REPOSITORY_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS, TESTS_ROOT
import argparse
import io
import json
import math
import pathlib
import random
import sys
import tempfile
import time
import zlib

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
sys.path.insert(0, str(HERE))

from assembly_model import AssemblyError  # noqa: E402
from sg_common import get_enzyme  # noqa: E402
import golden_gate  # noqa: E402
import simulate_advanced  # noqa: E402
import simulate_cloning  # noqa: E402

SEED = 20260816
REPORT_DIR = ROOT / "reports" / "property"

SCALE = {
    "gibson": (1000, 300),
    "infusion": (1000, 300),
    "golden-gate": (1000, 300),
    "digest-ligate": (1000, 300),
    "gateway": (500, 200),
    "ta": (500, 200),
}

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_BASES = "ACGT"
_SITE_BPAI = ("GGTCTC", "GAGACC")  # BsaI and its reverse complement
_SITE_ECORI = "GAATTC"
_SITE_SMAI = "CCCGGG"


def _record(sequence, name, circular=False, features=()):
    rec = SeqRecord(Seq(sequence), id=name, name=name)
    rec.annotations = {"molecule_type": "DNA",
                       "topology": "circular" if circular else "linear"}
    for feature in features:
        rec.features.append(feature)
    return rec


def _random_dna(rng, length, avoid=()):
    """Random DNA of given length that avoids every forbidden substring."""
    for _attempt in range(50):
        candidate = "".join(rng.choice(_BASES) for _ in range(length))
        if not any(site in candidate for site in avoid):
            return candidate
    raise AssertionError("could not generate %d bp avoiding %r" % (length, avoid))


def _label_feature(start, end, label, strand=1, compound=False, operator="join"):
    if compound:
        location = CompoundLocation([
            FeatureLocation(max(start, end - 2), end, strand=strand),
            FeatureLocation(start, min(end, start + 2), strand=strand),
        ], operator=operator)
    else:
        location = FeatureLocation(start, end, strand=strand)
    return SeqFeature(location, type="misc_feature",
                      qualifiers={"label": [label]})


def _add_random_features(rec, rng, case_index, fragment_index, min_start=0,
                         force=False):
    count = rng.randint(1, 3) if (force or rng.random() < 0.6) else 0
    seq_len = len(rec.seq)
    for idx in range(count):
        start = rng.randint(min_start, seq_len - 1)
        end = rng.randint(start + 1, seq_len)
        strand = rng.choice([1, -1])
        compound = rng.random() < 0.25
        rec.features.append(_label_feature(
            start, end, "f%d_case%d_feat%d" % (fragment_index, case_index, idx),
            strand=strand, compound=compound,
            operator=rng.choice(["join", "order"])))


def _verify_features(product, records, case_index, circular):
    """Every migrated feature must preserve extract() against its source.

    In linear assemblies a feature lying inside a removed overlap is dropped
    by design (with a warning); only its *absence from the product* is
    permitted, never a changed extract. Circular assemblies must keep every
    feature.
    """
    for source_index, rec in enumerate(records):
        for source_feature in rec.features:
            label = source_feature.qualifiers["label"][0]
            migrated = next(
                (f for f in product.features
                 if label in f.qualifiers.get("label", [])), None)
            if migrated is None:
                if circular:
                    raise AssertionError(
                        "case %d: feature %r lost from fragment %d"
                        % (case_index, label, source_index))
                continue
            source_extract = str(source_feature.extract(rec.seq)).upper()
            product_extract = str(migrated.extract(product.seq)).upper()
            if source_extract != product_extract:
                raise AssertionError(
                    "case %d: feature %r extract changed: %r vs %r"
                    % (case_index, label, source_extract, product_extract))


def _gb_roundtrip(product, case_index, every=10):
    if case_index % every != 0:
        return
    with tempfile.TemporaryDirectory(prefix="prop-gb-") as td:
        path = pathlib.Path(td) / "product.gb"
        with open(path, "w", encoding="utf-8") as handle:
            SeqIO.write(product, handle, "genbank")
        reread = SeqIO.read(str(path), "genbank")
        if str(reread.seq) != str(product.seq):
            raise AssertionError("case %d: GenBank round trip changed sequence"
                                 % case_index)


# ---------------------------------------------------------------------------
# gibson / infusion
# ---------------------------------------------------------------------------

def _overlap_parts(rng, case_index, circular, n=None, ov=None, method="gibson"):
    """Generate fragments with guaranteed-matching overlaps."""
    n = n if n is not None else rng.randint(2, 6)
    # The release gate models executable Gibson/overlap designs.  Values below
    # 12 bp are intentionally reserved for explicit failure tests, not
    # generated as successful products.
    ov = ov if ov is not None else rng.randint(12, 20)
    overlaps = ["".join(rng.choice(_BASES) for _ in range(ov))
                for _ in range(n)]
    unique = [rng.randint(1, 12) for _ in range(n)]
    records = []
    for i in range(n):
        if circular:
            body = _random_dna(rng, unique[i])
            seq = overlaps[i - 1] + body + overlaps[i]
        else:
            left = overlaps[i - 1] if i > 0 else ""
            right = overlaps[i] if i < n - 1 else ""
            seq = left + _random_dna(rng, unique[i]) + right
        rec = _record(seq, "f%d" % i, circular=circular)
        min_start = 0 if (circular or i == 0) else ov
        _add_random_features(rec, rng, case_index, i, min_start=min_start)
        records.append(rec)
    expected = "".join(str(rec.seq[ov:]) for rec in records) if circular else (
        str(records[0].seq)
        + "".join(str(rec.seq[ov:]) for rec in records[1:]))
    return records, ov, expected


def run_gibson_success(rng, count, method="gibson"):
    if method == "gibson":
        fn = simulate_cloning.gibson
    else:
        def fn(records, overlap, circular):
            product, fragments, warnings = simulate_advanced.infusion(
                records, overlap=overlap, circular=circular)
            contributions = [
                len(rec.seq) - overlap if (i > 0 or circular) else len(rec.seq)
                for i, rec in enumerate(records)]
            return product, fragments, contributions, warnings
    for case in range(count):
        circular = bool(rng.randint(0, 1))
        records, ov, expected = _overlap_parts(
            rng, case, circular, method=method)
        product, fragments, contributions, warnings = fn(
            records, overlap=ov, circular=circular)
        if str(product.seq) != expected:
            raise AssertionError(
                "%s case %d: product mismatch" % (method, case))
        if len(product.seq) != sum(contributions):
            raise AssertionError(
                "%s case %d: contributions do not sum to product"
                % (method, case))
        _verify_features(product, records, case, circular)
        _gb_roundtrip(product, case)
    return count


def run_gibson_failure(rng, count, method="gibson"):
    modes = ("mismatch", "zero-contribution", "too-long", "short-product")
    seen = set()
    for case in range(count):
        mode = modes[case % len(modes)]
        circular = bool(rng.randint(0, 1))
        n = rng.randint(2, 4)
        ov = rng.randint(12, 20)
        records, _o, _e = _overlap_parts(
            rng, case, circular, n=n, ov=ov, method=method)
        if mode == "mismatch":
            # Corrupt the first inter-fragment overlap.
            seq = str(records[1].seq)
            bad = "".join(rng.choice(_BASES) for _ in range(ov))
            records[1].seq = Seq(bad + seq[ov:])
            expected_code = "OVERLAP_MISMATCH"
        elif mode == "zero-contribution":
            # A fragment whose length equals the overlap contributes nothing.
            # The construction keeps every overlap intact so the pairwise
            # checks pass and only the contribution check can fire.
            ov_c = rng.randint(12, 20)
            ov_seq = "".join(rng.choice(_BASES) for _ in range(ov_c))
            if circular:
                frag0 = _record(
                    ov_seq + _random_dna(rng, rng.randint(1, 8)) + ov_seq,
                    "f0", circular=True)
            else:
                frag0 = _record(
                    _random_dna(rng, rng.randint(1, 8)) + ov_seq,
                    "f0", circular=False)
            frag1 = _record(ov_seq, "f1", circular=False)
            records = [frag0, frag1]
            ov = ov_c  # the assembly call below must use the same overlap
            expected_code = "ZERO_CONTRIBUTION_FRAGMENT"
        elif mode == "too-long":
            records[1].seq = Seq(records[1].seq[:ov - 1])
            expected_code = "OVERLAP_TOO_LONG"
        else:  # short-product: circular, every fragment exactly `ov` long
            # All-A fragments guarantee every pairwise overlap matches, so
            # only the contribution-length check can fire.
            records = []
            for i in range(n):
                records.append(_record("A" * ov, "f%d" % i, circular=True))
            expected_code = "PRODUCT_SHORTER_THAN_OVERLAP"
        fn = simulate_cloning.gibson if method == "gibson" else simulate_advanced.infusion
        try:
            fn(records, overlap=ov, circular=circular)
        except AssemblyError as error:
            if error.code != expected_code:
                # short-product can also surface as ZERO_CONTRIBUTION first;
                # accept either for that mode.
                if not (mode == "short-product"
                        and error.code == "ZERO_CONTRIBUTION_FRAGMENT"):
                    raise AssertionError(
                        "%s failure case %d (%s): got %r, expected %r"
                        % (method, case, mode, error.code, expected_code))
        else:
            raise AssertionError(
                "%s failure case %d (%s): no error raised (expected %r)"
                % (method, case, mode, expected_code))
        seen.add(mode)
    if len(seen) != len(modes):
        raise AssertionError("%s failure modes not all exercised: %s"
                             % (method, sorted(seen)))
    return count


# ---------------------------------------------------------------------------
# golden gate (BsaI)
# ---------------------------------------------------------------------------

def _gg_part(rng, name, left_overhang, right_overhang, body_len=None,
             circular=False):
    """BsaI part: forward site + 5'-overhang `left`, body, reverse site with
    5'-overhang `right`. The excised fragment is left+body and is free
    of BsaI recognition sites. Returns (record, body).

    The random body must not create extra recognition sites at its
    boundaries with the overhangs (a site spanning left+body or
    body+right would change the cut geometry), so the final sequence is
    verified to contain exactly the two designed sites; otherwise the
    body is regenerated.
    """
    body_len = body_len if body_len is not None else rng.randint(10, 120)
    for _attempt in range(50):
        body = _random_dna(rng, body_len, avoid=_SITE_BPAI)
        seq = ("GGTCTC" + "A" + left_overhang + body + right_overhang
               + "A" + "GAGACC")
        if seq.count("GGTCTC") + seq.count("GAGACC") == 2:
            return _record(seq, name, circular=circular), body
    raise AssertionError(
        "could not build a clean BsaI part for overhangs %r/%r"
        % (left_overhang, right_overhang))


def _gg_overhang(rng):
    return "".join(rng.choice(_BASES) for _ in range(4))


def run_golden_gate_success(rng, count):
    enzyme = get_enzyme("BsaI")
    for case in range(count):
        n_inserts = rng.randint(1, 3)
        overhangs = [_gg_overhang(rng) for _ in range(n_inserts + 1)]
        # vector: L = closing overhang, R = first junction overhang
        vector, vec_body = _gg_part(
            rng, "vector", overhangs[-1], overhangs[0], circular=True)
        inserts = []
        for i in range(n_inserts):
            rec, body = _gg_part(rng, "ins%d" % (i + 1),
                                 overhangs[i], overhangs[i + 1])
            inserts.append((rec, body))
        records = [vector] + [rec for rec, _body in inserts]
        names = ["vector"] + ["ins%d" % (i + 1) for i in range(n_inserts)]
        final, junctions, parts, notes, fragments = golden_gate.assemble(
            records, names, enzyme, vector_idx=0, vector_topology="circular")
        # Independent expectation from construction geometry: each excised
        # fragment runs between the two top-cut boundaries, so it contains the
        # LEFT overhang but not the RIGHT overhang (the right overhang is the
        # single-stranded extension beyond the cut and is re-created by the
        # next part's left overhang at the junction).
        expected = overhangs[-1] + vec_body
        for i, (_rec, body) in enumerate(inserts):
            expected += overhangs[i] + body
        if final != expected:
            raise AssertionError(
                "golden-gate case %d: product mismatch\n got: %s\nexp: %s"
                % (case, final, expected))
        for junction in junctions:
            if junction["compatibility"] != "ok":
                raise AssertionError(
                    "golden-gate case %d: unexpected mismatch %s"
                    % (case, junction["between"]))
        if len(set(p["overhang_length"] for p in parts)) != 1:
            raise AssertionError("golden-gate case %d: overhang lengths differ"
                                 % case)
        # Junction overhang sequences must be exactly the designed ones: a
        # junction between part k and k+1 (assembly order, closing junction
        # included) carries overhang O_k on both sides; the left fragment
        # stores its right-end overhang as reverse complement.
        junction_lookup = {j["between"]: j for j in junctions}
        for k in range(n_inserts + 1):
            if k == 0:
                between = "vector->ins1" if n_inserts >= 1 else "vector->vector"
            elif k == n_inserts:
                between = "ins%d->vector" % k
            else:
                between = "ins%d->ins%d" % (k, k + 1)
            junction = junction_lookup.get(between)
            if junction is None:
                continue
            expected_junction = "%s/%s" % (
                str(Seq(overhangs[k]).reverse_complement()), overhangs[k])
            if junction["junction"] != expected_junction:
                raise AssertionError(
                    "golden-gate case %d: junction %s overhangs %s != designed %s"
                    % (case, between, junction["junction"], expected_junction))
    return count


def run_golden_gate_failure(rng, count):
    enzyme = get_enzyme("BsaI")
    modes = ("too-few-sites", "site-in-fragment", "overhang-mismatch")
    seen = set()
    for case in range(count):
        mode = modes[case % len(modes)]
        if mode == "too-few-sites":
            # One BsaI site on a circular vector: no fragment can be excised.
            vector = _record("GGTCTC" + "A" * 40, "v", circular=True)
            insert = _record("A" * 60, "i", circular=False)
            expected_code = "PART_EXCISION_FAILED"
        elif mode == "site-in-fragment":
            # Linear insert with three BsaI sites: the only recognition-free
            # fragment is a wrap-around join, which is invalid for a linear
            # part -> no clean fragment exists.
            vector = _record(
                "GGTCTC" + "A" * 40 + "GAGACC", "v", circular=True)
            insert = _record(
                "GGTCTC" + "A" * 30 + "GGTCTC" + "A" * 30 + "GGTCTC",
                "i", circular=False)
            expected_code = "PART_EXCISION_FAILED"
        else:  # overhang mismatch
            vector, _vbody = _gg_part(rng, "v", "AAAA", "TTTT", circular=True)
            insert, _ibody = _gg_part(rng, "i", "CCCC", "GGGG", circular=False)
            expected_code = "OVERHANG_MISMATCH"
        records = [vector, insert]
        names = ["v", "i"]
        with io.StringIO() as buffer:
            import contextlib
            try:
                with contextlib.redirect_stdout(buffer):
                    golden_gate.assemble(
                        records, names, enzyme, vector_idx=0,
                        vector_topology="circular")
            except SystemExit:
                payload = buffer.getvalue()
                import json as _json
                try:
                    error = _json.loads(payload)["error"]
                except Exception:
                    raise AssertionError(
                        "golden-gate failure case %d: unparseable failure "
                        "output %r" % (case, payload[-300:]))
                if error["code"] != expected_code:
                    raise AssertionError(
                        "golden-gate failure case %d (%s): got %r, expected %r"
                        % (case, mode, error["code"], expected_code))
            else:
                raise AssertionError(
                    "golden-gate failure case %d (%s): no failure raised"
                    % (case, mode))
        seen.add(mode)
    if len(seen) != len(modes):
        raise AssertionError("golden-gate failure modes not all exercised")
    return count


# ---------------------------------------------------------------------------
# digest-ligate
# ---------------------------------------------------------------------------

def _dl_vector(rng, enzyme_name="EcoRI"):
    site = _SITE_ECORI if enzyme_name == "EcoRI" else _SITE_SMAI
    seq = ("AAA" + site + _random_dna(rng, rng.randint(20, 160), avoid=(site,))
           + "TTT")
    return _record(seq, "vector", circular=True)


def _dl_insert(rng, enzyme_name="EcoRI"):
    site = _SITE_ECORI if enzyme_name == "EcoRI" else _SITE_SMAI
    body = _random_dna(rng, rng.randint(10, 120), avoid=(site,))
    seq = "TTT" + site + body + site + "GGG"
    return _record(seq, "insert", circular=False)


def run_digest_ligate_success(rng, count):
    for case in range(count):
        enzyme_name = "EcoRI" if case % 2 == 0 else "SmaI"
        site = _SITE_ECORI if enzyme_name == "EcoRI" else _SITE_SMAI
        vector = _dl_vector(rng, enzyme_name)
        insert = _dl_insert(rng, enzyme_name)
        product, fragments, junctions = simulate_cloning.digest_ligate(
            vector, insert, enzyme_name)
        # Independent expectation from construction geometry:
        #   vector: "AAA" + site at 3..8 + body + "TTT", single site.
        #   insert: "TTT" + site at 3..8 + body + site at (9+L)..(14+L) + "GGG"
        # Excised insert fragment runs between the two top cuts; the vector is
        # opened at its own top cut.
        ins_seq = str(insert.seq)
        L = len(ins_seq) - 18  # body length: TTT(3)+site(6)+body+site(6)+GGG(3)
        if enzyme_name == "EcoRI":
            ins_fragment = ins_seq[4:10 + L]
            vector_cut = 4
        else:  # SmaI, blunt
            ins_fragment = ins_seq[6:12 + L]
            vector_cut = 6
        expected = (str(vector.seq[:vector_cut]) + ins_fragment
                    + str(vector.seq[vector_cut:]))
        if str(product.seq) != expected:
            raise AssertionError(
                "digest-ligate case %d: product sequence mismatch" % case)
        if len(product.seq) != len(vector.seq) + len(fragments[1].sequence):
            raise AssertionError(
                "digest-ligate case %d: product length mismatch" % case)
        if product.annotations.get("topology") != "circular":
            raise AssertionError(
                "digest-ligate case %d: product not circular" % case)
        for junction in junctions:
            if junction["compatibility"] != "ok":
                raise AssertionError(
                    "digest-ligate case %d: junction mismatch %s"
                    % (case, junction["between"]))
        if not any("insert" in f.qualifiers.get("label", [])
                   for f in product.features):
            raise AssertionError(
                "digest-ligate case %d: insert feature missing" % case)
    return count


def run_digest_ligate_failure(rng, count):
    modes = ("vector-no-site", "vector-two-sites", "insert-one-site",
             "insert-three-sites", "vector-linear")
    seen = set()
    for case in range(count):
        mode = modes[case % len(modes)]
        enzyme_name = "EcoRI"
        if mode == "vector-no-site":
            vector = _record("A" * 60, "v", circular=True)
            insert = _dl_insert(rng, enzyme_name)
            expected_code = "SITE_COUNT"
        elif mode == "vector-two-sites":
            vector = _record(
                "AAA" + _SITE_ECORI + "CCCCGGGG" + _SITE_ECORI + "TTT",
                "v", circular=True)
            insert = _dl_insert(rng, enzyme_name)
            expected_code = "SITE_COUNT"
        elif mode == "insert-one-site":
            vector = _dl_vector(rng, enzyme_name)
            insert = _record("TTT" + _SITE_ECORI + "AAAA", "i",
                             circular=False)
            expected_code = "SITE_COUNT"
        elif mode == "insert-three-sites":
            vector = _dl_vector(rng, enzyme_name)
            insert = _record(
                "TTT" + _SITE_ECORI + "AAAA" + _SITE_ECORI + "CCCC"
                + _SITE_ECORI + "GGG", "i", circular=False)
            expected_code = "SITE_COUNT"
        else:  # vector-linear
            vector = _record(
                "AAA" + _SITE_ECORI + "CCCCGGGG" + "TTT", "v", circular=False)
            insert = _dl_insert(rng, enzyme_name)
            expected_code = "INVALID_TOPOLOGY"
        try:
            simulate_cloning.digest_ligate(vector, insert, enzyme_name)
        except AssemblyError as error:
            if error.code != expected_code:
                raise AssertionError(
                    "digest-ligate failure case %d (%s): got %r, expected %r"
                    % (case, mode, error.code, expected_code))
        else:
            raise AssertionError(
                "digest-ligate failure case %d (%s): no error raised"
                % (case, mode))
        seen.add(mode)
    if len(seen) != len(modes):
        raise AssertionError("digest-ligate failure modes not all exercised")
    return count


# ---------------------------------------------------------------------------
# gateway (BP + LR)
# ---------------------------------------------------------------------------

def _gw_donor(rng):
    body = _random_dna(rng, rng.randint(20, 100),
                       avoid=(simulate_advanced.ATTP1, simulate_advanced.ATTP2,
                              str(Seq(simulate_advanced.ATTP1).reverse_complement()),
                              str(Seq(simulate_advanced.ATTP2).reverse_complement())))
    seq = (simulate_advanced.ATTP1 + body
           + str(Seq(simulate_advanced.ATTP2).reverse_complement()))
    return _record(seq, "donor", circular=True)


def _gw_attb_insert(rng, body_len=None):
    body_len = body_len if body_len is not None else rng.randint(10, 100)
    body = _random_dna(rng, body_len,
                       avoid=(simulate_advanced.ATTB1, simulate_advanced.ATTB2,
                              str(Seq(simulate_advanced.ATTB1).reverse_complement()),
                              str(Seq(simulate_advanced.ATTB2).reverse_complement())))
    return _record(simulate_advanced.ATTB1 + body + simulate_advanced.ATTB2,
                   "insert", circular=False)


def _gw_entry(rng):
    body = _random_dna(rng, rng.randint(10, 80),
                       avoid=(simulate_advanced.ATTL1, simulate_advanced.ATTL2,
                              str(Seq(simulate_advanced.ATTL1).reverse_complement()),
                              str(Seq(simulate_advanced.ATTL2).reverse_complement())))
    seq = (simulate_advanced.ATTL1 + body
           + str(Seq(simulate_advanced.ATTL2).reverse_complement()))
    return _record(seq, "entry", circular=True)


def _gw_destination(rng):
    body = _random_dna(rng, rng.randint(20, 100),
                       avoid=(simulate_advanced.ATTR1, simulate_advanced.ATTR2,
                              str(Seq(simulate_advanced.ATTR1).reverse_complement()),
                              str(Seq(simulate_advanced.ATTR2).reverse_complement())))
    seq = (simulate_advanced.ATTR1 + body
           + str(Seq(simulate_advanced.ATTR2).reverse_complement()))
    return _record(seq, "destination", circular=True)


def run_gateway_success(rng, count):
    for case in range(count):
        if case % 2 == 0:
            donor = _gw_donor(rng)
            body = _random_dna(
                rng, rng.randint(10, 100),
                avoid=(simulate_advanced.ATTB1, simulate_advanced.ATTB2,
                       str(Seq(simulate_advanced.ATTB1).reverse_complement()),
                       str(Seq(simulate_advanced.ATTB2).reverse_complement())))
            insert = _record(
                simulate_advanced.ATTB1 + body + simulate_advanced.ATTB2,
                "insert", circular=False)
            product, product_body, notes = simulate_advanced.gateway_bp(
                donor, insert)
            expected = (simulate_advanced.ATTL1 + body
                        + str(Seq(simulate_advanced.ATTL2).reverse_complement()))
        else:
            entry = _gw_entry(rng)
            destination = _gw_destination(rng)
            body = _random_dna(
                rng, rng.randint(10, 80),
                avoid=(simulate_advanced.ATTL1, simulate_advanced.ATTL2,
                       str(Seq(simulate_advanced.ATTL1).reverse_complement()),
                       str(Seq(simulate_advanced.ATTL2).reverse_complement())))
            entry = _record(
                simulate_advanced.ATTL1 + body
                + str(Seq(simulate_advanced.ATTL2).reverse_complement()),
                "entry", circular=True)
            product, product_body, notes = simulate_advanced.gateway_lr(
                entry, destination)
            expected = (simulate_advanced.ATTB1 + body
                        + str(Seq(simulate_advanced.ATTB2).reverse_complement()))
        if str(product.seq) != expected:
            raise AssertionError(
                "gateway case %d: product sequence mismatch" % case)
        if product_body != body:
            raise AssertionError(
                "gateway case %d: reported insert body mismatch" % case)
        if product.annotations.get("topology") != "circular":
            raise AssertionError("gateway case %d: product not circular" % case)
        labels = {f.qualifiers.get("label", [""])[0] for f in product.features}
        if "insert" not in labels:
            raise AssertionError("gateway case %d: insert feature missing" % case)
        _gb_roundtrip(product, case, every=20)
    return count


def run_gateway_failure(rng, count):
    modes = (
        "missing-attb", "duplicate-attb", "wrong-orientation",
        "att-order", "empty-body", "donor-linear", "donor-no-topology",
    )
    seen = set()
    for case in range(count):
        mode = modes[case % len(modes)]
        if mode == "missing-attb":
            donor = _gw_donor(rng)
            insert = _record("A" * 60, "i", circular=False)
            expected_code = "ATT_SITE_MISSING"
        elif mode == "duplicate-attb":
            donor = _gw_donor(rng)
            insert = _record(
                "AAA" + simulate_advanced.ATTB1 + "CCCC"
                + simulate_advanced.ATTB1 + "GGGG"
                + simulate_advanced.ATTB2 + "TTT", "i", circular=False)
            expected_code = "ATT_SITE_NOT_UNIQUE"
        elif mode == "wrong-orientation":
            donor = _gw_donor(rng)
            insert = _record(
                simulate_advanced.ATTB1 + "A" * 20
                + str(Seq(simulate_advanced.ATTB1).reverse_complement())
                + "C" * 20 + simulate_advanced.ATTB2, "i", circular=False)
            # forward attB1 AND reverse attB1 -> orientation error
            expected_code = "ATT_SITE_ORIENTATION"
        elif mode == "att-order":
            donor = _gw_donor(rng)
            insert = _record(
                simulate_advanced.ATTB2 + "A" * 20 + simulate_advanced.ATTB1,
                "i", circular=False)
            expected_code = "ATT_SITE_ORDER"
        elif mode == "empty-body":
            donor = _gw_donor(rng)
            insert = _record(simulate_advanced.ATTB1 + simulate_advanced.ATTB2,
                             "i", circular=False)
            expected_code = "ATT_SITE_EMPTY"
        elif mode == "donor-linear":
            donor = _gw_donor(rng)
            donor.annotations["topology"] = "linear"
            insert = _gw_attb_insert(rng)
            expected_code = "INVALID_TOPOLOGY"
        else:  # donor-no-topology
            donor = _gw_donor(rng)
            del donor.annotations["topology"]
            insert = _gw_attb_insert(rng)
            expected_code = "MISSING_TOPOLOGY"
        try:
            simulate_advanced.gateway_bp(donor, insert)
        except AssemblyError as error:
            if error.code != expected_code:
                raise AssertionError(
                    "gateway failure case %d (%s): got %r, expected %r"
                    % (case, mode, error.code, expected_code))
        else:
            raise AssertionError(
                "gateway failure case %d (%s): no error raised"
                % (case, mode))
        seen.add(mode)
    if len(seen) != len(modes):
        raise AssertionError("gateway failure modes not all exercised")
    return count


# ---------------------------------------------------------------------------
# ta / topo
# ---------------------------------------------------------------------------

def run_ta_success(rng, count):
    for case in range(count):
        vector = _record(_random_dna(rng, rng.randint(30, 200)), "vector",
                         circular=True)
        insert = _record(_random_dna(rng, rng.randint(10, 100)), "insert",
                         circular=False)
        cut = rng.randint(1, len(vector.seq) - 1)
        product, fragments, junctions = simulate_advanced.ta_topo_clone(
            vector, insert, cut, method="ta")
        expected = str(vector.seq[:cut]) + str(insert.seq) + str(vector.seq[cut:])
        if str(product.seq) != expected:
            raise AssertionError("ta case %d: product mismatch" % case)
        if product.annotations.get("topology") != "circular":
            raise AssertionError("ta case %d: product not circular" % case)
        for junction in junctions:
            if junction["compatibility"] != "ok":
                raise AssertionError("ta case %d: junction mismatch" % case)
    return count


def run_ta_failure(rng, count):
    modes = ("missing-cut", "cut-negative", "cut-too-large")
    seen = set()
    for case in range(count):
        mode = modes[case % len(modes)]
        vector = _record(_random_dna(rng, 60), "vector", circular=True)
        insert = _record(_random_dna(rng, 20), "insert", circular=False)
        if mode == "missing-cut":
            cut = None
            expected_code = "MISSING_VECTOR_CUT"
        elif mode == "cut-negative":
            cut = -1
            expected_code = "INVALID_VECTOR_CUT"
        else:
            cut = len(vector.seq) + 5
            expected_code = "INVALID_VECTOR_CUT"
        try:
            simulate_advanced.ta_topo_clone(vector, insert, cut, method="ta")
        except AssemblyError as error:
            if error.code != expected_code:
                raise AssertionError(
                    "ta failure case %d (%s): got %r, expected %r"
                    % (case, mode, error.code, expected_code))
        else:
            raise AssertionError(
                "ta failure case %d (%s): no error raised" % (case, mode))
        seen.add(mode)
    if len(seen) != len(modes):
        raise AssertionError("ta failure modes not all exercised")
    return count


RUNNERS = {
    "gibson": (run_gibson_success, run_gibson_failure),
    "infusion": (lambda rng, n: run_gibson_success(rng, n, method="infusion"),
                 lambda rng, n: run_gibson_failure(rng, n, method="infusion")),
    "golden-gate": (run_golden_gate_success, run_golden_gate_failure),
    "digest-ligate": (run_digest_ligate_success, run_digest_ligate_failure),
    "gateway": (run_gateway_success, run_gateway_failure),
    "ta": (run_ta_success, run_ta_failure),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--methods", default=",".join(SCALE),
                        help="comma-separated methods (default: all)")
    parser.add_argument("--quick", action="store_true",
                        help="run 5%% of the full scale (CI/smoke)")
    parser.add_argument("--seed", type=int, default=SEED,
                        help="deterministic random seed (default: %d)" % SEED)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out-dir", default=str(REPORT_DIR))
    args = parser.parse_args(argv)

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    for method in methods:
        if method not in SCALE:
            raise SystemExit("unknown method %r (choose from %s)"
                             % (method, ", ".join(sorted(SCALE))))
    factor = 0.05 if args.quick else 1.0
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {"gate": "property-tests", "seed": args.seed,
              "scale_factor": factor, "methods": {}, "ok": True}
    started = time.time()
    for method in methods:
        success_target, failure_target = SCALE[method]
        success_target = max(1, int(success_target * factor))
        failure_target = max(1, int(failure_target * factor))
        # Deterministic per-method seed: hash() is randomized per process, so
        # use a stable checksum instead.
        method_seed = args.seed + (zlib.crc32(method.encode("utf-8")) & 0x7FFFFFFF)
        rng = random.Random(method_seed)
        success_runner, failure_runner = RUNNERS[method]
        method_started = time.time()
        try:
            success_ok = success_runner(rng, success_target)
            failure_ok = failure_runner(rng, failure_target)
            ok = True
            detail = "ok"
        except AssertionError as error:
            ok = False
            detail = str(error)
        report["methods"][method] = {
            "success_target": success_target,
            "failure_target": failure_target,
            "success_passed": success_ok if ok else 0,
            "failure_passed": failure_ok if ok else 0,
            "ok": ok,
            "detail": detail,
            "elapsed_seconds": round(time.time() - method_started, 2),
        }
        report["ok"] = report["ok"] and ok
        print("%-14s success %4d/%4d  failure %4d/%4d  %s"
              % (method,
                 report["methods"][method]["success_passed"],
                 report["methods"][method]["success_target"],
                 report["methods"][method]["failure_passed"],
                 report["methods"][method]["failure_target"],
                 "PASS" if ok else "FAIL: " + detail))
    report["elapsed_seconds"] = round(time.time() - started, 2)
    (out_dir / "property-tests.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    print("property tests: %s (%d s)"
          % ("PASS" if report["ok"] else "FAIL", report["elapsed_seconds"]))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
