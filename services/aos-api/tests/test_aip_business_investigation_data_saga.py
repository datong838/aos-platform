"""BI-W6-02 exact-ref AIP-to-DataRequirement saga tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceipt,
)
from aos_api.aip_business_investigation_data_requester import MissingFactDataSpec
from aos_api.aip_business_investigation_data_saga import (
    BusinessInvestigationDataRequirementSaga,
    BusinessInvestigationDataSagaConflict,
)
from aos_api.aip_contracts import TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import DataRequirementApplyResult
from aos_api.data_requirement_store import DataRequirementIdempotencyConflict
from aos_api.tenant_scope import TenantScope
from test_aip_business_investigation_data_requester import request, runtime


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 26, 14, 0, tzinfo=UTC)


def compilation_receipt(**changes) -> BusinessInvestigationCompilationReceipt:
    value = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "receiptId": "bi-compilation-receipt-1",
        "commandId": "bi-compile-1",
        "requestHash": "sha256:" + "a" * 64,
        "runRef": {
            "resourceType": "BusinessInvestigationRun",
            "resourceId": "investigation-run-1",
            "revision": 1,
            "contentHash": "sha256:" + "2" * 64,
        },
        "taskId": "task-1",
        "planRef": {
            "resourceType": "PlanRevision",
            "resourceId": "plan-1",
            "revision": 1,
            "contentHash": "4" * 64,
        },
        "profileRef": {
            "resourceType": "InvestigationProfileRevision",
            "resourceId": "profile-1",
            "revision": 1,
            "contentHash": "5" * 64,
        },
        "logicRef": {
            "resourceType": "LogicRevision",
            "resourceId": "logic-1",
            "revision": 1,
            "contentHash": "6" * 64,
        },
        "skillBindingSetRef": {
            "resourceType": "SkillBindingSetRevision",
            "resourceId": "bindings-1",
            "revision": 1,
            "contentHash": "7" * 64,
        },
        "responsibilityPlanRef": {
            "resourceType": "ResponsibilityPlanRevision",
            "resourceId": "roles-1",
            "revision": 1,
            "contentHash": "8" * 64,
        },
        "inputHash": "9" * 64,
        "stageCompilationHash": "b" * 64,
        "compilationHash": "3" * 64,
        "runtimeAuthorized": False,
        "createdAt": NOW,
    }
    value.update(changes)
    return BusinessInvestigationCompilationReceipt.model_validate(value)


def spec() -> MissingFactDataSpec:
    payload = request().model_dump(mode="json", by_alias=True)
    payload.pop("requirementId")
    payload.pop("idempotencyKey")
    return MissingFactDataSpec.model_validate(payload)


class FixedRequester:
    def __init__(self) -> None:
        self.calls = []
        self.replayed = False
        self.drift = False

    def request_missing_facts(self, scope, runtime_binding, item, actor, *, created_at):
        self.calls.append((scope, runtime_binding, item, actor, created_at))
        identity = "drift" if self.drift else item.requirement_id
        return DataRequirementApplyResult(
            exact_ref=InvestigationExactRef(
                resource_type="DataRequirementRevision",
                resource_id=identity,
                revision=1,
                content_hash="sha256:" + "c" * 64,
            ),
            version=1,
            etag="sha256:" + "c" * 64,
            replayed=self.replayed,
        )


class ConflictOnDriftRequester(FixedRequester):
    def __init__(self) -> None:
        super().__init__()
        self.payload_by_key = {}

    def request_missing_facts(self, scope, runtime_binding, item, actor, *, created_at):
        payload = item.model_dump(mode="json", by_alias=True)
        prior = self.payload_by_key.get(item.idempotency_key)
        if prior is not None and prior != payload:
            raise DataRequirementIdempotencyConflict("idempotency conflict")
        self.payload_by_key[item.idempotency_key] = payload
        return super().request_missing_facts(
            scope, runtime_binding, item, actor, created_at=created_at
        )


def test_compilation_receipt_exact_ref_and_data_command_are_stable() -> None:
    receipt = compilation_receipt()
    assert receipt.exact_ref.resource_type == "BusinessInvestigationCompilationReceipt"
    assert receipt.exact_ref == compilation_receipt().exact_ref

    requester = FixedRequester()
    saga = BusinessInvestigationDataRequirementSaga(requester)
    first = saga.execute(SCOPE, "owner", receipt, runtime(), spec(), created_at=NOW)
    requester.replayed = True
    second = saga.execute(SCOPE, "owner", receipt, runtime(), spec(), created_at=NOW)

    assert first.command_id == second.command_id
    assert first.request_hash == second.request_hash
    assert first.data_requirement_ref == second.data_requirement_ref
    assert first.replayed is False and second.replayed is True
    assert first.source_read_performed is False
    assert first.external_effect_authorized is False
    assert len(requester.calls) == 2
    sent = requester.calls[0][2]
    assert sent.idempotency_key == first.command_id
    assert sent.requirement_id == first.data_requirement_ref.resource_id
    assert sent.requirement_id.startswith("data-requirement-")


@pytest.mark.parametrize(
    ("receipt_changes", "message"),
    [
        ({"tenant": {"orgId": "dev-org", "projectId": "dev-project"}}, "tenant"),
        ({"taskId": "task-other"}, "Task lineage"),
        ({"compilationHash": "d" * 64}, "compilation hash"),
    ],
)
def test_receipt_lineage_drift_blocks_before_data_request(
    receipt_changes, message
) -> None:
    requester = FixedRequester()
    with pytest.raises(BusinessInvestigationDataSagaConflict, match=message):
        BusinessInvestigationDataRequirementSaga(requester).execute(
            SCOPE,
            "owner",
            compilation_receipt(**receipt_changes),
            runtime(),
            spec(),
            created_at=NOW,
        )
    assert requester.calls == []


def test_naive_created_at_blocks_before_data_request() -> None:
    requester = FixedRequester()
    with pytest.raises(BusinessInvestigationDataSagaConflict, match="timezone-aware"):
        BusinessInvestigationDataRequirementSaga(requester).execute(
            SCOPE,
            "owner",
            compilation_receipt(),
            runtime(),
            spec(),
            created_at=NOW.replace(tzinfo=None),
        )
    assert requester.calls == []


def test_checkpoint_run_plan_and_taskrun_state_drift_block() -> None:
    scenarios = []
    no_checkpoint = runtime(checkpoint=False)
    scenarios.append((no_checkpoint, "Checkpoint"))
    wrong_run = runtime()
    wrong_run.business_investigation_run_ref = wrong_run.business_investigation_run_ref.model_copy(
        update={"resource_id": "run-other"}
    )
    scenarios.append((wrong_run, "Run exact"))
    wrong_plan = runtime()
    wrong_plan.plan_ref = wrong_plan.plan_ref.model_copy(update={"resource_id": "plan-other"})
    scenarios.append((wrong_plan, "Plan exact"))
    running = runtime()
    running.task_run_status = "executing"
    scenarios.append((running, "PAUSED"))

    for runtime_binding, message in scenarios:
        requester = FixedRequester()
        with pytest.raises(BusinessInvestigationDataSagaConflict, match=message):
            BusinessInvestigationDataRequirementSaga(requester).execute(
                SCOPE,
                "owner",
                compilation_receipt(),
                runtime_binding,
                spec(),
                created_at=NOW,
            )
        assert requester.calls == []


def test_result_drift_fails_closed_and_spec_has_no_caller_identity() -> None:
    requester = FixedRequester()
    requester.drift = True
    with pytest.raises(BusinessInvestigationDataSagaConflict, match="result drifted"):
        BusinessInvestigationDataRequirementSaga(requester).execute(
            SCOPE, "owner", compilation_receipt(), runtime(), spec(), created_at=NOW
        )
    fields = MissingFactDataSpec.model_fields
    assert "requirement_id" not in fields and "idempotency_key" not in fields


def test_different_fact_spec_changes_command_identity_and_request_hash() -> None:
    first = BusinessInvestigationDataRequirementSaga(FixedRequester()).execute(
        SCOPE, "owner", compilation_receipt(), runtime(), spec(), created_at=NOW
    )
    changed_payload = spec().model_dump(mode="json", by_alias=True)
    changed_payload["expiresAt"] = NOW + timedelta(days=2)
    changed = MissingFactDataSpec.model_validate(changed_payload)
    second = BusinessInvestigationDataRequirementSaga(FixedRequester()).execute(
        SCOPE, "owner", compilation_receipt(), runtime(), changed, created_at=NOW
    )
    assert first.command_id != second.command_id
    assert first.data_requirement_ref.resource_id != second.data_requirement_ref.resource_id
    assert first.request_hash != second.request_hash
    assert first.source_read_performed is False and second.source_read_performed is False


def test_distinct_spec_does_not_reuse_canonical_data_idempotency_key() -> None:
    requester = ConflictOnDriftRequester()
    saga = BusinessInvestigationDataRequirementSaga(requester)
    saga.execute(SCOPE, "owner", compilation_receipt(), runtime(), spec(), created_at=NOW)
    changed_payload = spec().model_dump(mode="json", by_alias=True)
    changed_payload["expiresAt"] = NOW + timedelta(days=2)
    changed = saga.execute(
        SCOPE,
        "owner",
        compilation_receipt(),
        runtime(),
        MissingFactDataSpec.model_validate(changed_payload),
        created_at=NOW,
    )
    assert changed.command_id != requester.calls[0][2].idempotency_key
    assert requester.calls[0][2].idempotency_key != requester.calls[1][2].idempotency_key
    assert len(requester.calls) == 2
