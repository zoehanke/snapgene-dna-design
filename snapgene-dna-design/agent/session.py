# -*- coding: utf-8 -*-
"""agent/session.py - file summaries, revisions and hash-bound sessions."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

from Bio import SeqIO

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design.spec import (  # noqa: E402
    DesignSpecError, canonical_json, confirm_user, diff_specs, new_spec,
    record_answer, revise, set_status, sha256_text, spec_sha256,
)


def file_sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest().upper()


def summarize_file(path):
    """Read one sequence file and return a summary without mutating it."""
    path = pathlib.Path(path)
    summary = {
        "path": str(path),
        "sha256": file_sha256(path),
        "size": path.stat().st_size,
        "name": path.stem,
        "suffix": path.suffix.lower(),
    }
    try:
        fmt = "snapgene" if path.suffix == ".dna" else (
            "genbank" if path.suffix in (".gb", ".genbank") else "fasta")
        with open(path, "rb" if fmt == "snapgene" else "r",
                  encoding=None if fmt == "snapgene" else "utf-8-sig") as handle:
            rec = SeqIO.read(handle, fmt)
    except Exception:
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                rec = SeqIO.read(handle, "genbank")
        except Exception:
            try:
                with open(path, "r", encoding="utf-8-sig") as handle:
                    rec = SeqIO.read(handle, "fasta")
            except Exception as exc:
                summary["error"] = str(exc)
                return summary
    summary["name"] = str(rec.name or rec.id or summary["name"])
    summary.update({
        "record_id": rec.id,
        "length": len(rec.seq),
        "topology": str(rec.annotations.get("topology", "linear")),
        "features": [
            {
                "type": f.type,
                "name": f.qualifiers.get("label", [f.qualifiers.get("gene",
                                                                     ["?"])[0]])[0],
                "start0": int(f.location.start),
                "end0": int(f.location.end),
                "strand": f.location.strand,
                "parts": [
                    [int(p.start), int(p.end), p.strand]
                    for p in f.location.parts],
            }
            for f in rec.features
        ],
    })
    return summary


class Session:
    """Owns DesignSpec revisions, file summaries, answers and artifacts."""

    def __init__(self, spec=None, workdir=None):
        self.workdir = pathlib.Path(workdir or pathlib.Path.cwd())
        self.spec = spec
        self.revisions = [copy.deepcopy(spec)] if spec else []
        self.file_summaries = {}
        self.artifacts = []
        self.log = []

    @classmethod
    def create(cls, raw_objective, mode="exploration", files=(),
               workdir=None):
        session = cls(new_spec(raw_objective, mode=mode), workdir=workdir)
        for path in files:
            session.add_file(path)
        return session

    def add_file(self, path):
        summary = summarize_file(path)
        self.file_summaries[str(path)] = summary
        if summary.get("error"):
            self.log.append({"event": "file-summary-error", "path": str(path),
                             "error": summary["error"]})
        else:
            self.log.append({"event": "file-summary", "path": str(path),
                             "sha256": summary["sha256"],
                             "length": summary["length"],
                             "topology": summary["topology"]})
        return summary

    def file_alias_candidates(self, reference):
        """Return candidate summaries for a user file reference."""
        text = str(reference).strip().lower()
        matches = []
        for summary in self.file_summaries.values():
            if summary.get("error"):
                continue
            hay = (str(summary.get("path", "")) + " " +
                   str(summary.get("name", ""))).lower()
            if text and text in hay:
                matches.append(summary)
        if len(matches) == 1:
            return matches
        return matches

    def answer(self, question_id, value, description=None):
        record_answer(self.spec, question_id, value, "user-provided",
                      description)
        self.log.append({"event": "answer", "question_id": question_id,
                         "value": value})
        return self.spec

    def confirm(self):
        confirm_user(self.spec)
        self.log.append({"event": "user-confirmed",
                         "sha256": spec_sha256(self.spec)})
        return self.spec

    def revise(self, reason):
        old = self.spec
        new = revise(old, reason)
        self.revisions.append(copy.deepcopy(old))
        self.spec = new
        self.log.append({"event": "revision", "from": old["revision"],
                         "to": new["revision"], "reason": reason,
                         "diff": diff_specs(old, new)})
        return new

    def check_file_hashes(self):
        """Return list of mismatched paths vs session file summaries."""
        mismatches = []
        for path, summary in self.file_summaries.items():
            if not pathlib.Path(path).is_file() or \
                    file_sha256(path) != summary.get("sha256"):
                mismatches.append(path)
        return mismatches

    def snapshot(self):
        return {
            "spec": copy.deepcopy(self.spec),
            "file_summaries": copy.deepcopy(self.file_summaries),
            "artifacts": copy.deepcopy(self.artifacts),
            "log": copy.deepcopy(self.log),
        }
