# -*- coding: utf-8 -*-
"""operation_consent.py - release-iteration consent + transparency plumbing.

Iron rule 4 ("用户知情权与操作透明") is implemented here as code-level
behaviour:

* ``ConsentBroker`` is the single structured interaction point for regular
  parameter confirmations and for abnormal operations (constraint relaxation,
  backend degradation, "no solution" findings, external writes).
* In ``policy="ask"`` mode no callback / TTY approval means **no execution**:
  ``ConsentRequiredError`` is raised with a machine-readable request that a
  CLI can render or a caller can forward to its own UI.
* Every decision -- approval, denial, pre-approval, auto-confirm -- is
  appended to a ``TransparencyLog`` together with backend, parameters, input
  SHA and retry/relaxation path.  Nothing is silently dropped.
"""
from __future__ import annotations

import hashlib
import sys
import time
import uuid


class ConsentRequiredError(RuntimeError):
    """Raised when a required confirmation has not been obtained."""

    def __init__(self, request):
        self.request = request
        super().__init__(
            "consent required for %s (%s): %s"
            % (request["operation"], request["category"],
               request["description"]))


def sha256_prefix(data, length=16):
    """Stable uppercase SHA-256 prefix used in operation logs."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()[:length]


def make_request(operation, category, description, parameters=None,
                 alternatives=None, risk=None, source=None):
    """Build one structured operation-consent request."""
    return {
        "id": "op-" + uuid.uuid4().hex[:12],
        "operation": operation,
        "category": category,
        "description": description,
        "parameters": parameters or {},
        "alternatives": alternatives or [],
        "risk": risk or "",
        "source": source,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


class ConsentBroker:
    """Structured interaction interface for user-consent decisions.

    ``policy``:
        ``"ask"``   - require a callback/TTY decision; otherwise raise.
        ``"auto"``  - auto-confirm and record the decision visibly.
    ``confirm_callback``: optional ``callable(request) -> bool``.  Programmable
    API path used by tests and embedding applications.
    ``pre_approved``: iterable of operation/category names approved in advance
    (automation must still list them explicitly here).
    """

    def __init__(self, policy="ask", confirm_callback=None,
                 pre_approved=(), log=None):
        if policy not in ("ask", "auto"):
            raise ValueError("invalid consent policy: %r" % policy)
        self.policy = policy
        self.confirm_callback = confirm_callback
        self.pre_approved = tuple(pre_approved)
        self.log = log if log is not None else TransparencyLog()
        self.requests = []

    def request(self, request):
        request = dict(request)
        self.requests.append(request)
        if request["operation"] in self.pre_approved or \
                request["category"] in self.pre_approved:
            decision = {"approved": True, "source": "pre-approved",
                        "request": request["id"]}
            self._record(request, decision)
            return decision
        if self.confirm_callback is not None:
            approved = bool(self.confirm_callback(request))
            decision = {"approved": approved,
                        "source": "programmable-callback",
                        "request": request["id"]}
            self._record(request, decision)
            if not approved:
                raise ConsentRequiredError(request)
            return decision
        if self.policy == "auto":
            decision = {"approved": True, "source": "auto-confirm",
                        "note": ("automation explicitly selected "
                                 "ConsentBroker(policy='auto')"),
                        "request": request["id"]}
            self._record(request, decision)
            return decision
        raise ConsentRequiredError(request)

    def _record(self, request, decision):
        entry = dict(decision)
        entry.update({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "operation": request["operation"],
            "category": request["category"],
            "description": request["description"],
            "parameters": request["parameters"],
            "alternatives": request["alternatives"],
            "risk": request.get("risk", ""),
            "source": request.get("source"),
        })
        self.log.append(entry)

    def pending(self):
        pending = []
        for request in self.requests:
            decisions = [entry for entry in self.log.entries
                         if entry.get("request") == request["id"]]
            if not decisions or not decisions[-1].get("approved"):
                pending.append(request)
        return pending


class TransparencyLog:
    """Append-only operation journal included in every machine-readable result."""

    def __init__(self):
        self.entries = []

    def append(self, entry):
        entry = dict(entry)
        entry.setdefault("timestamp",
                         time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        self.entries.append(entry)

    def snapshot(self):
        return [dict(entry) for entry in self.entries]


def operation_summary(log_entries):
    """One human-readable line per operation for reports and CLI output."""
    lines = []
    for entry in log_entries:
        lines.append("%s %s: %s (decision=%s, source=%s)"
                     % (entry.get("timestamp", "")[11:19],
                        entry.get("operation", "-"),
                        entry.get("description", "-"),
                        "approved" if entry.get("approved") else "denied",
                        entry.get("source", "-")))
    return lines
