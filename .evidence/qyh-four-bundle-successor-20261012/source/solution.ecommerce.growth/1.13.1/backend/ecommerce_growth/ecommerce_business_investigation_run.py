"""Package-owned N4 run phases; platform stores remain behind SDK ports."""

from enum import StrEnum


class AnalysisPhase(StrEnum):
    PREPARING = "PREPARING"
    WAITING_DATA = "WAITING_DATA"
    RUNNING = "RUNNING"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"


class RecoverableAction(StrEnum):
    CONTINUE = "CONTINUE"
    WAIT_FOR_DATA = "WAIT_FOR_DATA"
    RECONCILE_RECEIPT = "RECONCILE_RECEIPT"


ALLOWED_PHASES_BY_MODE = {
    "START": frozenset(
        {
            AnalysisPhase.PREPARING,
            AnalysisPhase.WAITING_DATA,
            AnalysisPhase.RUNNING,
            AnalysisPhase.UNKNOWN,
        }
    ),
    "RESUME_DATA": frozenset({AnalysisPhase.RUNNING, AnalysisPhase.UNKNOWN}),
    "RECONCILE_UNKNOWN": frozenset(
        {
            AnalysisPhase.RECONCILING,
            AnalysisPhase.WAITING_DATA,
            AnalysisPhase.RUNNING,
            AnalysisPhase.UNKNOWN,
        }
    ),
}


__all__ = ["ALLOWED_PHASES_BY_MODE", "AnalysisPhase", "RecoverableAction"]
