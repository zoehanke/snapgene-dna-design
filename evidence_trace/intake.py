"""Explicit text observations and delivery-file observations. No scientific inference."""
from __future__ import annotations

import pathlib

from evidence_trace.models import file_digest, snapshot
from evidence_trace.recorder import project


def observe_material(recorder, item, actor="host-assistant"):
    if not isinstance(item, dict):
        raise ValueError("Each material observation must be an object")
    kind = item.get("kind")
    if kind == "local_text":
        path = pathlib.Path(item["path"]).resolve()
        content = path.read_text(encoding="utf-8-sig")
        lines = content.splitlines(keepends=True)
        start, end = item.get("start_line", 1), item.get("end_line", len(lines))
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise ValueError("Text line range must be inclusive, 1-based and within the file")
        payload = {"kind": kind, "path": str(path), "start_line": start, "end_line": end,
                   "text": "".join(lines[start-1:end]), "capture_channel": "local_file_read",
                   "source_sha256": file_digest(path)}
    elif kind == "submitted_text":
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError("submitted_text needs text")
        payload = {"kind": kind, "text": item["text"], "capture_channel": "explicit_submission"}
    else:
        raise ValueError("Observation kind must be local_text or submitted_text")
    payload.update({k: item[k] for k in ("source_uri", "declared_role", "declared_occurred_at") if k in item})
    protected = snapshot(payload)
    if protected != payload:
        protected["omission_notice"] = "Raw sequences/secrets follow existing snapshot policy."
    return recorder.append("material_observed", protected, actor)["event_id"]


def record_handoff(recorder, items, actor="host-assistant"):
    if not isinstance(items, list) or not items:
        raise ValueError("handoff requires a nonempty files list")
    with recorder.writing():
        artifacts = [n for n in project(recorder.events)["nodes"] if n["kind"] == "artifact"]
        files = []
        for item in items:
            path = pathlib.Path(item["path"]).resolve()
            if path.is_relative_to(recorder.directory):
                raise ValueError("Trace's own files are not DNA delivery evidence")
            sha = file_digest(path) if path.is_file() else None
            by_path = [a for a in artifacts if pathlib.Path(a["path"]).resolve() == path]
            matches = [a for a in by_path if a["sha256"] == sha and a.get("generation_observation") != "presence_only"
                       and a.get("result_event_ref")]
            status = "missing" if sha is None else "linked" if len(matches) == 1 else "ambiguous" if len(matches) > 1 else "changed" if any(a["sha256"] != sha for a in by_path) else "untraced"
            files.append({"path": str(path), "sha256": sha, "purpose": item.get("purpose", ""),
                          "status": status, "artifact_refs": [a["key"] for a in matches]})
        return recorder.append("handoff_recorded", {"files": files, "scope": "Explicit supplied file list only"}, actor)["payload"]
