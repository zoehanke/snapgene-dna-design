# -*- coding: utf-8 -*-
"""online_sources.py - M6 online authoritative-source adapters.

Offline/failure is explicit: ``status=offline-unverified``, never a
silently fabricated sequence.  CRISPOR upload requests reuse the hardened
``SequenceUploadConsent`` full-parameter authorization from dev3.
"""
import hashlib
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from Bio import SeqIO
from sg_common import normalize_dna

from sequence_upload_consent import SequenceUploadConsent

NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ADDGENE_BASE = "https://www.addgene.org"
CRISPOR_URL = "https://crispor.org"


def _get(url, timeout=20):
    request = urllib.request.Request(
        url, headers={"User-Agent": "snapgene-dna-design/0.9"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _normalize_sequence(text):
    return "".join(str(text or "").split()).upper()


def _looks_like_sequence(term):
    """Conservative heuristic: a term is a sequence, not a keyword, when it
    is long enough and consists almost entirely of IUPAC nucleotide letters.
    """
    text = _normalize_sequence(term)
    if len(text) < 4:
        return False
    if not text:
        return False
    allowed = set("ACGTRYSWKMBDHVNU")
    fraction = sum(1 for char in text if char in allowed) / len(text)
    return fraction >= 0.75


def _sequence_sha256(sequence):
    text = _normalize_sequence(sequence)
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def ncbi_search(term, database="nucleotide", retmax=5, timeout=20):
    """Return NCBI eUtils esearch/esummary results; offline-safe.

    Raw nucleotide queries are refused here: sequence submission must go
    through the consent-bound BLAST path (`ncbi_blast_consent_request`).
    """
    if _looks_like_sequence(term):
        return {
            "status": "refused-consent-required",
            "reason": ("term looks like a raw nucleotide sequence; use an "
                       "accession/keyword with ncbi_search or use the "
                       "consent-bound BLAST request path"),
            "term_sha256": _sequence_sha256(term),
        }
    try:
        params = urllib.parse.urlencode({
            "db": database, "term": term, "retmax": retmax,
            "retmode": "json",
        })
        payload = json.loads(_get(
            "%s/esearch.fcgi?%s" % (NCBI_EUTILS, params), timeout))
        if not isinstance(payload, dict) or not isinstance(payload.get("esearchresult"), dict):
            raise ValueError("Invalid NCBI search response")
        ids = payload.get("esearchresult", {}).get("idlist", [])
        if not isinstance(ids, list) or any(not isinstance(uid, str) for uid in ids):
            raise ValueError("Invalid NCBI id list")
        if not ids:
            return {"status": "offline-unverified",
                    "reason": "NCBI returned no matching ids"}
        summary = json.loads(_get(
            "%s/esummary.fcgi?db=%s&id=%s&retmode=json"
            % (NCBI_EUTILS, database, ",".join(ids)), timeout))
        if not isinstance(summary, dict) or not isinstance(summary.get("result"), dict):
            raise ValueError("Invalid NCBI summary response")
        records = []
        for uid in ids:
            item = summary.get("result", {}).get(uid, {})
            if not isinstance(item, dict) or not (item.get("caption") or item.get("accessionversion")):
                raise ValueError("NCBI summary is missing record %s" % uid)
            records.append({
                "id": uid,
                "accession": item.get("caption") or item.get("accessionversion"),
                "title": item.get("title"),
                "organism": item.get("organism"),
                "url": "https://www.ncbi.nlm.nih.gov/nuccore/%s"
                       % (item.get("accessionversion") or uid),
            })
        return {"status": "verified-online", "database": database,
                "term": term, "records": records}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return {"status": "offline-unverified",
                "reason": "NCBI query failed: %s" % error}


def fetch_genbank(accession, timeout=30):
    """Fetch one GenBank record through efetch; never fabricates on failure."""
    try:
        params = urllib.parse.urlencode({
            "db": "nucleotide", "id": accession, "rettype": "gbwithparts",
            "retmode": "text",
        })
        text = _get("%s/efetch.fcgi?%s" % (NCBI_EUTILS, params), timeout)
        record = SeqIO.read(io.StringIO(text), "genbank")
        sequence = normalize_dna(record.seq, "NCBI GenBank sequence")
        requested = str(accession).strip()
        # Numeric UIDs may resolve to an accession. Accession queries must
        # match the actual returned record, including an explicitly requested version.
        if not requested.isdigit():
            matches = record.id == requested if "." in requested else record.id.split(".")[0] == requested
            if not matches:
                raise ValueError("Returned accession does not match requested accession")
        return {"status": "verified-online", "accession": accession,
                "resolved_accession": record.id, "sequence_length": len(sequence),
                "verification_scope": "One parsed non-empty GenBank DNA record; no experimental or scientific validation.",
                "format": "genbank", "text": text}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return {"status": "offline-unverified",
                "reason": "NCBI efetch failed: %s" % error}


def addgene_lookup(addgene_id):
    """Addgene official-page link helper.

    This is NOT a record-query/sequence-verification adapter: no anonymous
    JSON API or credentials are bundled, so it only produces the official
    page URL and explicitly reports `offline-unverified`.
    """
    return {
        "adapter_kind": "official-page-link-helper",
        "status": "offline-unverified",
        "reason": ("Addgene record lookup and sequence verification are not "
                   "implemented; this returns the official page link only"),
        "url": "%s/%s/" % (ADDGENE_BASE, addgene_id),
        "addgene_id": addgene_id,
    }


BLAST_URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"


def ncbi_blast_hint(sequence=None):
    """Privacy-safe BLAST hint.

    This function never puts raw sequence in a URL, field, report or log.
    It may compute the real SHA-256 prefix of a sequence for audit purposes,
    but the returned URL is always the bare official BLAST form.
    """
    sha = None
    if sequence is not None:
        sha = _sequence_sha256(sequence)
    return {
        "status": "offline-unverified",
        "reason": ("NCBI BLAST needs an asynchronous RID and an explicit, "
                   "one-time, destination/purpose/sequence-bound consent "
                   "before any sequence can be submitted"),
        "url": BLAST_URL + "?PROGRAM=blastn&PAGE_TYPE=BlastSearch",
        "sequence_sha256_prefix": sha[:16] if sha else None,
        "contains_sequence_in_url": False,
    }


def ncbi_blast_consent_request(sequence, purpose, scope,
                               retention_notice=True):
    """Create a consent-bound BLAST request; no sequence leaves this call."""
    consent = SequenceUploadConsent(scope)
    consent.request(BLAST_URL, purpose, sequence=_normalize_sequence(sequence),
                    retention_notice=retention_notice)
    return {
        "consent": consent,
        "request": {
            "destination": BLAST_URL,
            "purpose": purpose,
            "scope": scope,
            "sequence_sha256": _sequence_sha256(sequence),
            "sequence_sha256_prefix": _sequence_sha256(sequence)[:16],
            "contains_sequence": False,
        },
    }


def authorized_blast_url(consent, sequence, purpose, scope):
    """Return a BLAST submission URL only after a one-time bound consent.

    The raw sequence is placed in the URL only when `consent.allowed(...)`
    returns True for the exact destination/purpose/sequence/scope tuple.

    Limitation: this link helper supports at most 100 nt. Larger sequences
    are refused rather than silently searching only a prefix.
    """
    normalized = _normalize_sequence(sequence)
    if len(normalized) > 100:
        return {"status": "unsupported", "reason": "BLAST_URL_SEQUENCE_TOO_LONG_USE_FILE_UPLOAD",
                "url": None, "contains_sequence": False}
    if consent is None or not consent.allowed(BLAST_URL, purpose, normalized,
                                              scope):
        return {"status": "denied", "reason": "BLAST_CONSENT_REQUIRED",
                "url": None, "contains_sequence": False}
    normalized = _normalize_sequence(sequence)
    query = urllib.parse.quote(normalized, safe="")
    return {
        "status": "authorized",
        "reason": "one-time bound consent verified",
        "url": ("%s?PROGRAM=blastn&PAGE_TYPE=BlastSearch&QUERY=%s"
                % (BLAST_URL, query)),
        "contains_sequence": True,
    }


def request_crispor_query(target_sequence, organism, purpose, scope,
                          retention_notice=True):
    """Build a bound consent request; no network is touched here."""
    consent = SequenceUploadConsent(scope)
    consent.request(CRISPOR_URL, purpose, sequence=target_sequence,
                    retention_notice=retention_notice)
    # The upload caller must pass the full identity again to authorized().
    return consent


if __name__ == "__main__":
    print(json.dumps({"ncbi": ncbi_search("EGFP"),
                      "addgene": addgene_lookup(42230)},
                     ensure_ascii=False, indent=2))
    sys.exit(0)
