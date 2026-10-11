"""Pure stage runtime matching; current Run and Evidence authority stay host-owned."""

from __future__ import annotations

from .ecommerce_analyst_authority_contracts import AnalystExactRef
from .ecommerce_analyst_stage_decision import EvalStageAttemptRef


_OUTPUTS = {
    "portrait": ("InsightRevision", "insightRef"),
    "diagnosis": ("DecisionSummaryRevision", "decisionRef"),
    "solution-design": ("GrowthPlanRevision", "growthPlanRef"),
}


def require_stage_runtime_references(
    *,
    task_run_id: str,
    plan_ref: AnalystExactRef,
    stage: str,
    stage_attempt_ref: EvalStageAttemptRef,
    subject_ref: AnalystExactRef,
) -> AnalystExactRef:
    """Match exact values after the host has resolved the current Run."""

    if (
        type(task_run_id) is not str
        or not task_run_id
        or task_run_id.strip() != task_run_id
        or len(task_run_id) > 200
        or type(stage) is not str
        or stage not in _OUTPUTS
        or not isinstance(plan_ref, AnalystExactRef)
        or not isinstance(stage_attempt_ref, EvalStageAttemptRef)
        or not isinstance(subject_ref, AnalystExactRef)
        or type(stage_attempt_ref.attempt) is not int
    ):
        raise ValueError("exact stage runtime references required")
    plan_ref = AnalystExactRef.model_validate(plan_ref.model_dump(mode="python"))
    stage_attempt_ref = EvalStageAttemptRef.model_validate(
        stage_attempt_ref.model_dump(mode="python")
    )
    subject_ref = AnalystExactRef.model_validate(subject_ref.model_dump(mode="python"))
    if (
        plan_ref.resource_type != "PlanRevision"
        or subject_ref.resource_type != _OUTPUTS[stage][0]
        or stage_attempt_ref.run_id != task_run_id
        or stage_attempt_ref.step_key != stage
    ):
        raise ValueError("exact stage runtime references required")
    return subject_ref


def require_observed_stage_subject(
    *,
    stage: str,
    step_run_id: str,
    subject_ref: AnalystExactRef,
    observation_payload: dict[str, object],
) -> AnalystExactRef:
    """Match a payload only after the host proves its Evidence body current."""

    if (
        type(stage) is not str
        or stage not in _OUTPUTS
        or type(step_run_id) is not str
        or not step_run_id
        or step_run_id.strip() != step_run_id
        or len(step_run_id) > 200
        or not isinstance(subject_ref, AnalystExactRef)
        or type(observation_payload) is not dict
    ):
        raise ValueError("stage observed a different subject")
    subject_ref = AnalystExactRef.model_validate(subject_ref.model_dump(mode="python"))
    output_key = _OUTPUTS[stage][1]
    payload = observation_payload.get("payload")
    if (
        observation_payload.get("stepRunId") != step_run_id
        or observation_payload.get("stepKey") != stage
        or type(payload) is not dict
        or payload.get(output_key)
        != subject_ref.model_dump(mode="json", by_alias=True)
    ):
        raise ValueError("stage observed a different subject")
    return subject_ref


__all__ = ["require_observed_stage_subject", "require_stage_runtime_references"]
