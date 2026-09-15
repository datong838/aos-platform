"""N4 phase/action invariants independent from the canonical host runtime."""

from .ecommerce_business_investigation_run import (
    ALLOWED_PHASES_BY_MODE,
    AnalysisPhase,
    RecoverableAction,
)


def validate_runtime_phase(*, mode: str, phase: AnalysisPhase, action: RecoverableAction) -> None:
    if phase not in ALLOWED_PHASES_BY_MODE[mode]:
        raise ValueError("runtime response phase does not match recovery mode")
    if phase is AnalysisPhase.WAITING_DATA and action is not RecoverableAction.WAIT_FOR_DATA:
        raise ValueError("WAITING_DATA must expose WAIT_FOR_DATA")
    if phase in {AnalysisPhase.UNKNOWN, AnalysisPhase.RECONCILING} and action is not RecoverableAction.RECONCILE_RECEIPT:
        raise ValueError("unknown runtime must reconcile a target Receipt")
    if phase in {AnalysisPhase.PREPARING, AnalysisPhase.RUNNING} and action is not RecoverableAction.CONTINUE:
        raise ValueError("active runtime must expose CONTINUE")


__all__ = ["validate_runtime_phase"]
