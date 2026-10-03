# -*- coding: utf-8 -*-
"""Unified error model for the v0.9.1 architecture-recovery runtime.

Every refusal is machine-readable and can never be confused with a
successful plan.  ``write_authoritative_artifact`` is always false for
errors raised before the authoritative gate.
"""


class CoreError(Exception):
    status = "blocked"

    def __init__(self, error_code, message, status=None,
                 missing_fields=None, questions=None, details=None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        if status is not None:
            self.status = status
        self.missing_fields = list(missing_fields or [])
        self.questions = list(questions or [])
        self.details = details or {}

    def to_dict(self):
        return {
            "status": self.status,
            "error_code": self.error_code,
            "message": self.message,
            "missing_fields": self.missing_fields,
            "questions": self.questions,
            "details": self.details,
            "write_authoritative_artifact": False,
        }


class TaskValidationError(CoreError):
    """ConstructionTask failed schema or semantic validation."""
    status = "needs-clarification"


class TaskBlockedError(CoreError):
    """Task is valid but must not proceed (unsupported kind, conflict...)."""
    status = "blocked"


class PlanningError(CoreError):
    """A specialized planner could not produce an explicit, safe plan."""
    status = "needs-clarification"


class ExecutionError(CoreError):
    status = "blocked"


class ValidationError(CoreError):
    status = "blocked"


class GateRejected(CoreError):
    """The authoritative gate refused to emit a formal product."""
    status = "blocked"
