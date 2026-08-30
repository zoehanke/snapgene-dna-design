# -*- coding: utf-8 -*-
"""v0.9.1 architecture-recovery core runtime.

Public seams (the only interfaces tests and Skill flows may rely on):

    validate_construction_task(task)          -> validated task
    plan(task)                                -> explicit plan
    execute(task, plan)                       -> execution artifacts
    validate(task, plan, execution)           -> three-layer report
    finalize(task, plan, execution, validation) -> authoritative delivery
"""
from core.task import validate_construction_task
from core.session import ConstructionTaskSession, collect_task_questions
from core.runtime_plan import plan
from core.runtime_execute import execute
from core.runtime_validate import validate
from core.runtime_gate import finalize

__all__ = [
    "validate_construction_task",
    "ConstructionTaskSession",
    "collect_task_questions",
    "plan",
    "execute",
    "validate",
    "finalize",
]
