"""W8-06 batch prepare/start/Partial-Unknown-Reconcile scenario tests."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_batch_scenario import (
    BatchScenarioObservation,
    EcommerceWorkshopBatchScenario,
    batch_start_binding_hash,
)
from aos_api.ecommerce_workshop_batch_scenario_contracts import (
    BatchScenarioBlocker,
    BatchScenarioChildOutcome,
    BatchScenarioComposition,
    BatchScenarioExactRef,
    BatchScenarioLedger,
    BatchScenarioOutcomeAxis,
    BatchScenarioOutcomeAxisId,
    BatchScenarioPreparationDecision,
    BatchScenarioRoleBinding,
    BatchScenarioStage,
    BatchScenarioStageId,
)
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 8, 26, 7, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
HASH = "sha256:" + "a" * 64


def ref(resource_type: str, resource_id: str) -> BatchScenarioExactRef:
    return BatchScenarioExactRef(resourceType=resource_type, resourceId=resource_id, revision=1, contentHash=HASH)


def blocker(code: str = "CHILD_OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED") -> BatchScenarioBlocker:
    return BatchScenarioBlocker(code=code, dependency="workshop.batch-scenario", requiredAction="reread same fingerprint and append exact reconcile receipt")


def composition() -> BatchScenarioComposition:
    return BatchScenarioComposition(
        atomicSkillRefs=[ref("SkillRevision", "freeze-batch"), ref("SkillRevision", "reconcile-attempt")],
        logicRevisionRef=ref("LogicRevision", "batch-control-loop"),
        roleBindings=[BatchScenarioRoleBinding(roleRef=ref("AgentTemplate", "operations-lead"), assigneeRef=ref("AgentInstance", "operations-lead-1"), skillBindingRef=ref("SkillBinding", "batch-binding-1"))],
    )


def decisions() -> tuple[BatchScenarioPreparationDecision, ...]:
    values = (("item-1", "included", []), ("item-2", "included", []), ("item-3", "excluded", []), ("item-4", "unknown", ["SOURCE_FACT_UNKNOWN"]))
    return tuple(BatchScenarioPreparationDecision(itemKey=key, disposition=status, originalRefs=[ref("BusinessItemRevision", key)], decisionRef=ref("ItemPreparationDecision", f"decision-{key}"), reasonCodes=reasons) for key, status, reasons in values)


def children() -> tuple[BatchScenarioChildOutcome, ...]:
    return (
        BatchScenarioChildOutcome(itemKey="item-1", status="succeeded", requestFingerprint="1" * 64, attemptRef=ref("Attempt", "attempt-1"), authorityRefs=[ref("ActionReceipt", "receipt-1")]),
        BatchScenarioChildOutcome(itemKey="item-2", status="unknown", requestFingerprint="2" * 64, attemptRef=ref("Attempt", "attempt-2"), authorityRefs=[ref("ProviderRequestReceipt", "provider-request-2")]),
    )


def stages(preparation: BatchScenarioExactRef, start: BatchScenarioExactRef, *, root_drift: bool = False) -> tuple[BatchScenarioStage, ...]:
    refs = ([ref("BatchPreparationRevision", "drift") if root_drift else preparation, start], [ref("ImpactPreviewRevision", "preview-1")], [start], [ref("ChildDispatchPlanRevision", "dispatch-plan-1")], [ref("ActionReceipt", "receipt-1")], [], [])
    result = []
    for index, stage_id in enumerate(BatchScenarioStageId):
        if stage_id in {BatchScenarioStageId.UNKNOWN_RECONCILE, BatchScenarioStageId.RESTART_REBUILD}:
            result.append(BatchScenarioStage(stageId=stage_id, status="unknown" if stage_id == BatchScenarioStageId.UNKNOWN_RECONCILE else "blocked", contribution="等待 same-fingerprint exact reconcile/rebuild", blockers=[blocker()]))
        else:
            result.append(BatchScenarioStage(stageId=stage_id, status="ready", exactRefs=refs[index], contribution=f"stage {stage_id.value}"))
    return tuple(result)


def axes() -> tuple[BatchScenarioOutcomeAxis, ...]:
    return (
        BatchScenarioOutcomeAxis(axisId="business_item", status="partial", exactRefs=[ref("ActionReceipt", "receipt-1")], blockers=[blocker()]),
        BatchScenarioOutcomeAxis(axisId="external_action", status="unknown", blockers=[blocker()]),
        BatchScenarioOutcomeAxis(axisId="usage_settlement", status="not_started", blockers=[blocker("USAGE_SETTLEMENT_NOT_STARTED")]),
        BatchScenarioOutcomeAxis(axisId="effect_maturity", status="unknown", blockers=[blocker()]),
        BatchScenarioOutcomeAxis(axisId="handoff_decision", status="blocked", blockers=[blocker("HANDOFF_DECISION_REQUIRED")]),
    )


def ledger() -> BatchScenarioLedger:
    return BatchScenarioLedger(frozenTotal=4, included=2, excluded=1, blocked=0, preparationUnknown=1, childrenExpected=2, childrenObserved=2, succeeded=1, failed=0, cancelled=0, childUnknown=1, reconciled=0, reconcileReceiptsObserved=0)


def observation(*, scope: TenantScope = SCOPE, root_drift: bool = False, binding: str | None = None) -> BatchScenarioObservation:
    preparation = ref("BatchPreparationRevision", "batch-prepare-1")
    start = ref("BatchStartDecision", "batch-start-1")
    item = BatchScenarioObservation(scope=scope, cutoff=CUTOFF, batch_preparation_revision_ref=preparation, batch_start_decision_ref=start, batch_start_binding_hash="0" * 64, composition=composition(), preparation_decisions=decisions(), child_outcomes=children(), stages=stages(preparation, start, root_drift=root_drift), ledger=ledger(), outcome_axes=axes())
    return replace(item, batch_start_binding_hash=binding or batch_start_binding_hash(item))


class Reader:
    def __init__(self, item: BatchScenarioObservation) -> None:
        self.item = item

    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> BatchScenarioObservation:
        return self.item


def test_missing_roots_are_structured_and_all_commands_stay_closed() -> None:
    result = EcommerceWorkshopBatchScenario().read(scope=SCOPE, cutoff=CUTOFF)
    assert result.batch_preparation_revision_ref is None
    assert [item.stage_id for item in result.stages] == list(BatchScenarioStageId)
    assert [item.axis_id for item in result.outcome_axes] == list(BatchScenarioOutcomeAxisId)
    assert result.commands.model_dump() == {"prepare": False, "start": False, "cancel": False, "reconcile": False}
    assert result.side_effect_ledger.model_dump() == {"prepare_external_calls": 0, "provider_calls": 0, "action_attempts": 0, "external_effects": 0}
    assert result.automatic_retry_allowed is result.external_effects_allowed is result.release_allowed is False


def test_exact_binding_preserves_four_layers_partial_and_unknown_separately() -> None:
    result = EcommerceWorkshopBatchScenario(reader=Reader(observation())).read(scope=SCOPE, cutoff=CUTOFF)
    assert result.batch_preparation_revision_ref and result.batch_start_decision_ref
    assert result.composition and len(result.composition.atomic_skill_refs) == 2
    assert [item.disposition for item in result.preparation_decisions] == ["included", "included", "excluded", "unknown"]
    assert [item.status for item in result.child_outcomes] == ["succeeded", "unknown"]
    assert result.ledger.frozen_total == 4 and result.ledger.children_observed == 2
    assert result.status == "blocked"


def test_scope_binding_and_root_drift_fail_closed_without_refs() -> None:
    other = TenantScope(org_id="dev-org", project_id="dev-project")
    tenant = EcommerceWorkshopBatchScenario(reader=Reader(observation(scope=other))).read(scope=SCOPE, cutoff=CUTOFF)
    binding = EcommerceWorkshopBatchScenario(reader=Reader(observation(binding="f" * 64))).read(scope=SCOPE, cutoff=CUTOFF)
    root = EcommerceWorkshopBatchScenario(reader=Reader(observation(root_drift=True))).read(scope=SCOPE, cutoff=CUTOFF)
    assert [tenant.blockers[0].code, binding.blockers[0].code, root.blockers[0].code] == ["BATCH_SCENARIO_SCOPE_OR_CUTOFF_DRIFT", "BATCH_START_BINDING_DRIFT", "BATCH_ROOT_STAGE_DRIFT"]
    assert tenant.batch_preparation_revision_ref is binding.batch_preparation_revision_ref is root.batch_preparation_revision_ref is None


def test_ledger_drift_and_non_included_child_are_rejected() -> None:
    with pytest.raises(ValidationError):
        BatchScenarioLedger(frozenTotal=4, included=2, excluded=1, blocked=0, preparationUnknown=0, childrenExpected=2, childrenObserved=0, succeeded=0, failed=0, cancelled=0, childUnknown=0, reconciled=0, reconcileReceiptsObserved=0)
    with pytest.raises(ValidationError):
        BatchScenarioChildOutcome(itemKey="item-1", status="reconciled", requestFingerprint="3" * 64, attemptRef=ref("Attempt", "attempt-3"), authorityRefs=[ref("ActionReceipt", "receipt-3")])
