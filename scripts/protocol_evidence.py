# -*- coding: utf-8 -*-
"""protocol_evidence.py - Loaded protocol sources with provenance.

The evidence file is populated from real manufacturer web pages. Search
summaries are never used as evidence for exact experimental conditions.
"""
import json
import pathlib

from provenance import source

EVIDENCE_PATH = pathlib.Path(__file__).resolve().parents[1] / "references" / "protocol-evidence-dev2.json"


def load_sources(path=None):
    path = pathlib.Path(path or EVIDENCE_PATH)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["sources"]


def source_object(item):
    item = item if isinstance(item, dict) else {}
    required = ("source_type", "provider", "title", "url")
    missing = [key for key in required if not item.get(key)]
    if missing:
        return source(
            "software", "Invalid protocol evidence", "protocol-recommendation",
            status="unavailable",
            verification={"method": "evidence-schema-check", "status": "invalid"},
            additional={"invalid_fields": missing},
        )
    source_verified = item.get("verification_status") in (
        "current-page-read", "official-url-checked")
    return source(
        item["source_type"], "%s protocol" % item["provider"],
        "protocol-recommendation", url=item["url"], version=item.get("document_revision"),
        license_value=None, status="verified" if source_verified else "unknown",
        verification={"method": "web-page-read", "status": item.get("verification_status", "unknown")},
        retrieved_at=item.get("retrieved_at"),
        additional={"provider": item["provider"], "title": item["title"],
                    "catalog_number": item.get("catalog_number")})


def usable_source(item):
    """Return True only for evidence records safe for a recommendation."""
    if not isinstance(item, dict):
        return False
    if any(not item.get(key) for key in ("source_type", "provider", "title", "url")):
        return False
    return item.get("verification_status") in (
        "current-page-read", "official-url-checked")
