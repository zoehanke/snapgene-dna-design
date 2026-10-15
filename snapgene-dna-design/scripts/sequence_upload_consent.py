# -*- coding: utf-8 -*-
"""sequence_upload_consent.py - Per-upload consent state machine.

Default behavior is NO upload.  Approval creates a **binding receipt** that
fixes destination, purpose, sequence SHA-256 and scope.  ``allowed()``
compares a proposed upload against the receipt item by item; any mismatch
invalidates the receipt.  A matching check consumes the receipt (one-time
use).  The full sequence is never stored.
"""
import datetime
import json

from provenance import sha256_of_text, now_iso


def _normalize_sequence(value):
    """Hash the exact uppercase whitespace-free string the adapters submit."""
    return "".join(str(value or "").split()).upper()


def _default_retention_policy(destination):
    """Return an honest, destination-specific retention statement.

    No fixed retention period is asserted: third-party policies change and
    several services publish only partial statements.
    """
    destination = str(destination or "").lower()
    if "blast.ncbi.nlm.nih.gov" in destination or "ncbi" in destination:
        return ("unverified: review the current NCBI privacy/security policy "
                "for retention terms")
    if "crispor" in destination:
        return ("unverified: the CRISPOR manual reports that results have not "
                "been deleted in the past two years and that the service "
                "aims to retain results for at least one year; no fixed "
                "retention period is independently confirmed")
    return "unverified: review the destination service's current retention policy"


class SequenceUploadConsent:
    def __init__(self, sequence_scope="unknown"):
        self.scope = sequence_scope
        self.state = {
            "sequence_upload": {
                "requested": False,
                "consent": False,
                "scope": sequence_scope,
                "sequence_sha256": None,
                "destination": None,
                "purpose": None,
                "requested_at": None,
                "approved_at": None,
                "retention_notice_shown": False,
                "retention_policy": "unverified",
                "receipt": None,
            }
        }

    def request(self, destination, purpose, sequence=None, retention_notice=True,
            retention_policy=None):
        """Bind a new upload request.

        A new request always supersedes any previous receipt: the old
        approval cannot be reused for different parameters.
        """
        item = self.state["sequence_upload"]
        item["destination"] = destination
        item["purpose"] = purpose
        item["retention_notice_shown"] = bool(retention_notice)
        item["retention_policy"] = (
            retention_policy or _default_retention_policy(destination))
        normalized = _normalize_sequence(sequence) or None
        item["sequence_sha256"] = (
            sha256_of_text(normalized) if normalized is not None else None)
        item["requested"] = True
        item["requested_at"] = now_iso()
        item["consent"] = False
        item["approved_at"] = None
        item["receipt"] = None
        return self.state

    def approve(self):
        """Approve the currently-bound request and issue a binding receipt."""
        item = self.state["sequence_upload"]
        if not item.get("requested"):
            return self.state
        if (not item.get("destination") or not item.get("purpose")
                or not item.get("sequence_sha256")):
            return self.state
        item["consent"] = True
        item["approved_at"] = now_iso()
        item["receipt"] = {
            "destination": item["destination"],
            "purpose": item["purpose"],
            "sequence_sha256": item["sequence_sha256"],
            "scope": item["scope"],
            "approved_at": item["approved_at"],
            "consumed": False,
        }
        return self.state

    def deny(self):
        item = self.state["sequence_upload"]
        item["consent"] = False
        item["approved_at"] = None
        item["receipt"] = None
        return self.state

    def peek_allowed(self):
        """Non-consuming check: is an unconsumed matching receipt present?"""
        item = self.state["sequence_upload"]
        return bool(item.get("consent") and item.get("receipt")
                    and not item["receipt"].get("consumed"))

    def allowed(self, destination=None, purpose=None, sequence=None,
                scope=None, consume=True):
        """Binding, one-time authorization check.

        Every authorization decision must carry the full upload identity:
        ``destination``, ``purpose`` and ``sequence`` are mandatory.  A
        missing argument is a denial, never a legacy authorization peek —
        use ``peek_allowed()`` for the explicit non-consuming check.
        """
        item = self.state["sequence_upload"]
        if not item.get("consent") or not item.get("receipt"):
            return False
        receipt = item["receipt"]
        if receipt.get("consumed"):
            return False
        if (destination is None or purpose is None or sequence is None
                or not str(sequence).strip()):
            return False
        current_sha = sha256_of_text(_normalize_sequence(sequence))
        checks = {
            "destination": (destination, receipt.get("destination")),
            "purpose": (purpose, receipt.get("purpose")),
            "sequence_sha256": (current_sha, receipt.get("sequence_sha256")),
            "scope": (scope if scope is not None else self.scope,
                      receipt.get("scope")),
        }
        mismatch = [name for name, (value, expected) in checks.items()
                    if value != expected]
        if mismatch:
            self.deny()
            return False
        if consume:
            receipt["consumed"] = True
            item["consent"] = False
        return True

    def consent_message(self, sequence_length=None, local_alternative=""):
        item = self.state["sequence_upload"]
        message = (
            "准备访问：%s\n"
            "准备上传：%s"
        ) % (item["destination"], item.get("scope") or "目标区域DNA序列")
        if sequence_length:
            message += "，长度%d bp" % sequence_length
        message += (
            "\n上传目的：%s\n"
            "留存政策：%s\n"
            "本地替代：%s\n"
            "是否允许本次上传？"
        ) % (item["purpose"], item.get("retention_policy", "unverified"),
             local_alternative or "无可用本地替代")
        return message

    def to_json(self):
        serializable = json.loads(json.dumps(self.state, default=str))
        serializable["sequence_upload"].pop("sequence", None)
        return json.dumps(serializable, ensure_ascii=False, indent=2)
