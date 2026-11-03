"""Consolidation subsystem."""

from .engine import DreamEngine, DreamResult
from .gates import ConsolidationGates, GateReport, GateResult
from .lock import ConsolidationLock, LockState
from .schema import (
    ConsolidationOperation,
    ConsolidationPlan,
    CreateOperation,
    MergeOperation,
    PromoteOperation,
    ResolveOperation,
    parse_consolidation_plan,
)

__all__ = [
    "ConsolidationGates",
    "ConsolidationLock",
    "ConsolidationOperation",
    "ConsolidationPlan",
    "CreateOperation",
    "DreamEngine",
    "DreamResult",
    "GateReport",
    "GateResult",
    "LockState",
    "MergeOperation",
    "PromoteOperation",
    "ResolveOperation",
    "parse_consolidation_plan",
]
