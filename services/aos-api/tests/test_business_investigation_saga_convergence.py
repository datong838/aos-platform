"""BI-W6-06 cumulative duplicate/order/late/partial-failure convergence matrix."""

from __future__ import annotations

import pytest

from aos_api.aip_business_investigation_artifact_saga import (
    BusinessInvestigationArtifactPublicationSaga,
)
from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompileSaga,
)
from aos_api.aip_business_investigation_data_saga import (
    BusinessInvestigationDataRequirementSaga,
)
from aos_api.aip_business_investigation_fulfillment_saga import (
    BusinessInvestigationFulfillmentResumeBlocked,
    BusinessInvestigationFulfillmentResumeSaga,
)
from aos_api.aip_business_investigation_reconcile_saga import (
    BusinessInvestigationReconciliationCoordinator,
)
from aos_api.ecommerce_business_investigation_artifact_publication import (
    ArtifactPublicationWrite,
    BusinessInvestigationArtifactPublisher,
)
from aos_api.source_readiness_contracts import SourceReadinessStatus
from test_aip_business_investigation_artifact_saga import (
    SCOPE,
    artifact,
    binding,
    gate,
    stage_attempt,
)
from test_aip_business_investigation_compile_saga import (
    FixedCompiler,
    MemoryReceipts,
    request_for,
    run_view,
)
from test_aip_business_investigation_data_saga import (
    FixedRequester,
    compilation_receipt,
    spec,
)
from test_aip_business_investigation_data_requester import runtime as data_runtime
from test_aip_business_investigation_fulfillment_saga import (
    NOW,
    FixedResumer,
    data_command,
    evidence_response,
    fulfillment,
    hydration,
    readiness,
    runtime,
)
from test_aip_business_investigation_reconcile_saga import (
    FakeRuns,
    command,
    ref,
    state,
)
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunControl


class IdempotentResumer(FixedResumer):
    def __init__(self) -> None:
        super().__init__()
        self.by_command = {}
        self.transition_count = 0

    def resume_run(self, *args, **kwargs):
        command_id = kwargs["idempotency_key"]
        if command_id in self.by_command:
            self.calls.append(("replay", command_id))
            return self.by_command[command_id]
        result = super().resume_run(*args, **kwargs)
        self.by_command[command_id] = result
        self.transition_count += 1
        return result


class ReplayPublicationAuthority:
    def __init__(self) -> None:
        self.by_command = {}
        self.revision_count = 0

    def publish(self, _scope, **kwargs):
        receipt = kwargs["receipt"]
        existing = self.by_command.get(receipt.command_id)
        if existing is not None:
            assert existing == receipt
            return ArtifactPublicationWrite(authority=existing, replayed=True)
        self.by_command[receipt.command_id] = receipt
        self.revision_count += 1
        return ArtifactPublicationWrite(authority=receipt, replayed=False)


class FailOnceCompleter:
    def __init__(self) -> None:
        self.attempts = 0
        self.checkpoints = []

    def complete_step(self, _scope, _step_run_id, _worker_id, _fence, _actor):
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("simulated process interruption after publication Receipt")
        if not self.checkpoints:
            self.checkpoints.append("checkpoint-after-reentry")
        return self.checkpoints[0]


def test_duplicate_compile_and_data_commands_keep_single_authority() -> None:
    compiler = FixedCompiler()
    compile_receipts = MemoryReceipts()
    compile_saga = BusinessInvestigationCompileSaga(compiler, compile_receipts)
    run = run_view()
    request = request_for(run)
    first_compile = compile_saga.execute(SCOPE, "owner", "trigger-1", run, request)
    replay_compile = compile_saga.execute(SCOPE, "owner", "trigger-1", run, request)
    assert replay_compile.replayed
    assert replay_compile.authority == first_compile.authority
    assert len(compiler.calls) == len(compile_receipts.by_command) == 1

    requester = FixedRequester()
    data_saga = BusinessInvestigationDataRequirementSaga(requester)
    first_data = data_saga.execute(
        SCOPE, "owner", compilation_receipt(), data_runtime(), spec(), created_at=NOW
    )
    requester.replayed = True
    replay_data = data_saga.execute(
        SCOPE, "owner", compilation_receipt(), data_runtime(), spec(), created_at=NOW
    )
    assert replay_data.replayed
    assert replay_data.command_id == first_data.command_id
    assert replay_data.data_requirement_ref == first_data.data_requirement_ref


def test_out_of_order_receipt_waits_then_late_exact_receipt_converges_once() -> None:
    resumer = IdempotentResumer()
    saga = BusinessInvestigationFulfillmentResumeSaga(resumer)
    stale_readiness = readiness().model_copy(
        update={"status": SourceReadinessStatus.STALE}
    )
    args = (
        SCOPE,
        "aip:investigation",
        data_command(),
        fulfillment(),
        hydration(),
        stale_readiness,
        evidence_response(),
        runtime(),
    )
    with pytest.raises(BusinessInvestigationFulfillmentResumeBlocked) as raised:
        saga.execute(*args, created_at=NOW)
    assert raised.value.code == "READINESS_NOT_READY"
    assert resumer.transition_count == 0 and not resumer.calls

    late_args = (*args[:5], readiness(), *args[6:])
    first = saga.execute(*late_args, created_at=NOW)
    replay = saga.execute(*late_args, created_at=NOW)
    assert first.command_id == replay.command_id
    assert first.task_run_ref == replay.task_run_ref
    assert resumer.transition_count == 1
    assert len(resumer.by_command) == 1


def test_publication_receipt_survives_partial_failure_and_reentry() -> None:
    authority = ReplayPublicationAuthority()
    completer = FailOnceCompleter()
    saga = BusinessInvestigationArtifactPublicationSaga(
        BusinessInvestigationArtifactPublisher(authority), completer
    )
    item = artifact()
    kwargs = {
        "actor": "analyst",
        "worker_id": "worker-1",
        "fence": 7,
        "expected_head_revision": 0,
        "artifact": item,
        "binding": binding(item),
        "quality_gate": gate(item),
        "stage_attempt": stage_attempt(),
        "published_at": NOW,
    }
    with pytest.raises(RuntimeError, match="process interruption"):
        saga.execute(SCOPE, **kwargs)
    assert authority.revision_count == len(authority.by_command) == 1
    assert completer.checkpoints == []

    accepted = saga.execute(SCOPE, **kwargs)
    persisted = next(iter(authority.by_command.values()))
    assert accepted.publication_receipt_ref.resource_id == persisted.receipt_id
    assert authority.revision_count == 1
    assert completer.attempts == 2 and completer.checkpoints == [accepted.checkpoint_id]


def test_repeated_unknown_and_reconcile_keep_monotonic_history() -> None:
    runs = FakeRuns(state(1, BusinessInvestigationRunControl.RUNNING))
    coordinator = BusinessInvestigationReconciliationCoordinator(runs)
    original_ref = ref(runs.current)
    uncertain = command()

    unknown = coordinator.record_timeout(
        SCOPE, "run-1", original_ref, uncertain, actor="owner", occurred_at=NOW
    )
    coordinator.record_timeout(
        SCOPE, "run-1", original_ref, uncertain, actor="owner", occurred_at=NOW
    )
    reconciling = coordinator.begin_reconcile(
        SCOPE,
        "run-1",
        unknown.current_state_ref,
        uncertain,
        actor="owner",
        occurred_at=NOW,
    )
    coordinator.begin_reconcile(
        SCOPE,
        "run-1",
        unknown.current_state_ref,
        uncertain,
        actor="owner",
        occurred_at=NOW,
    )
    assert [original_ref.revision, unknown.current_state_ref.revision, reconciling.current_state_ref.revision] == [1, 2, 3]
    assert len(runs.receipts) == 2
    assert not unknown.original_command_replayed and not reconciling.outcome_resolved
