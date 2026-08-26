"""BI-W6-05 cross-layer UNKNOWN/RECONCILING coordinator tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_business_investigation_reconcile_saga import (
    BusinessInvestigationReconciliationConflict,
    BusinessInvestigationReconciliationCoordinator,
)
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl,
    BusinessInvestigationRunLifecycle,
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationRunStateWrite,
    BusinessInvestigationRunView,
    BusinessInvestigationUncertainCommand,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 26, tzinfo=UTC)
HASH_A = f"sha256:{'a' * 64}"


def state(
    version: int,
    control: BusinessInvestigationRunControl,
    *,
    command: BusinessInvestigationUncertainCommand | None = None,
) -> BusinessInvestigationRunStateRevision:
    prior = None
    if version > 1:
        prior = {
            "resourceType": "BusinessInvestigationRunStateRevision",
            "resourceId": "run-1",
            "revision": version - 1,
            "contentHash": HASH_A,
        }
    return BusinessInvestigationRunStateRevision.model_validate(
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "runId": "run-1",
            "version": version,
            "priorRef": prior,
            "lifecycle": BusinessInvestigationRunLifecycle.PREPARING,
            "control": control,
            "eventSequence": version,
            "contentHash": HASH_A,
            "uncertainCommand": command,
            "createdBy": "owner",
            "createdAt": NOW,
        }
    )


def ref(item: BusinessInvestigationRunStateRevision) -> InvestigationExactRef:
    return InvestigationExactRef(
        resource_type="BusinessInvestigationRunStateRevision",
        resource_id=item.run_id,
        revision=item.version,
        content_hash=item.content_hash,
    )


def command(operation: str = "data_requirement.fulfill") -> BusinessInvestigationUncertainCommand:
    return BusinessInvestigationUncertainCommand(
        command_id="command-1", operation=operation, request_hash=HASH_A
    )


class FakeRuns:
    def __init__(self, current: BusinessInvestigationRunStateRevision) -> None:
        self.current = current
        self.calls: list[tuple[str, int, str]] = []
        self.receipts: dict[tuple[str, str], BusinessInvestigationRunStateRevision] = {}

    def get(self, scope, run_id):
        assert scope == SCOPE and run_id == "run-1"
        return BusinessInvestigationRunView.model_construct(authority=None, state=self.current)

    def mark_unknown(self, scope, run_id, uncertain_command, **kwargs):
        key = ("unknown", kwargs["idempotency_key"])
        replayed = key in self.receipts
        successor = self.receipts.get(key) or state(
            kwargs["expected_version"] + 1,
            BusinessInvestigationRunControl.UNKNOWN,
            command=uncertain_command,
        )
        self.receipts[key] = successor
        self.current = successor
        self.calls.append(("unknown", kwargs["expected_version"], kwargs["idempotency_key"]))
        return BusinessInvestigationRunStateWrite(authority=successor, replayed=replayed)

    def begin_reconcile(self, scope, run_id, **kwargs):
        key = ("reconciling", kwargs["idempotency_key"])
        replayed = key in self.receipts
        successor = self.receipts.get(key) or state(
            kwargs["expected_version"] + 1,
            BusinessInvestigationRunControl.RECONCILING,
            command=self.current.uncertain_command,
        )
        self.receipts[key] = successor
        self.current = successor
        self.calls.append(("reconciling", kwargs["expected_version"], kwargs["idempotency_key"]))
        return BusinessInvestigationRunStateWrite(authority=successor, replayed=replayed)


def test_timeout_to_unknown_then_reconciling_and_replay() -> None:
    runs = FakeRuns(state(1, BusinessInvestigationRunControl.RUNNING))
    coordinator = BusinessInvestigationReconciliationCoordinator(runs)
    original = ref(runs.current)
    uncertain = command()

    unknown = coordinator.record_timeout(
        SCOPE, "run-1", original, uncertain, actor="owner", occurred_at=NOW
    )
    replay = coordinator.record_timeout(
        SCOPE, "run-1", original, uncertain, actor="owner", occurred_at=NOW
    )
    assert unknown.phase == "UNKNOWN" and not unknown.replayed
    assert replay.replayed and replay.current_state_ref == unknown.current_state_ref
    assert not unknown.original_command_replayed and not unknown.outcome_resolved

    unknown_ref = unknown.current_state_ref
    reconciling = coordinator.begin_reconcile(
        SCOPE, "run-1", unknown_ref, uncertain, actor="owner", occurred_at=NOW
    )
    reconcile_replay = coordinator.begin_reconcile(
        SCOPE, "run-1", unknown_ref, uncertain, actor="owner", occurred_at=NOW
    )
    assert reconciling.phase == "RECONCILING" and not reconciling.replayed
    assert reconcile_replay.replayed
    assert reconciling.current_state_ref.revision == unknown_ref.revision + 1
    assert runs.calls[0][2] == runs.calls[1][2]
    assert runs.calls[2][2] == runs.calls[3][2]


@pytest.mark.parametrize(
    ("observed", "uncertain", "actor", "occurred_at", "message"),
    [
        (
            InvestigationExactRef(
                resource_type="BusinessInvestigationRunStateRevision",
                resource_id="other-run",
                revision=1,
                content_hash=HASH_A,
            ),
            command(),
            "owner",
            NOW,
            "exact Run state ref",
        ),
        (None, command("provider.send"), "owner", NOW, "allowlist"),
        (None, command(), "", NOW, "run id and actor"),
        (None, command(), "owner", datetime(2026, 8, 26), "timezone"),
    ],
)
def test_timeout_validation_blocks_before_state_write(
    observed, uncertain, actor, occurred_at, message
) -> None:
    runs = FakeRuns(state(1, BusinessInvestigationRunControl.RUNNING))
    coordinator = BusinessInvestigationReconciliationCoordinator(runs)
    observed = observed or ref(runs.current)
    with pytest.raises(BusinessInvestigationReconciliationConflict, match=message):
        coordinator.record_timeout(
            SCOPE,
            "run-1",
            observed,
            uncertain,
            actor=actor,
            occurred_at=occurred_at,
        )
    assert not runs.calls


def test_stale_timeout_and_invalid_reconcile_are_fail_closed() -> None:
    stable = state(1, BusinessInvestigationRunControl.RUNNING)
    runs = FakeRuns(stable)
    coordinator = BusinessInvestigationReconciliationCoordinator(runs)
    stale = InvestigationExactRef(
        resource_type="BusinessInvestigationRunStateRevision",
        resource_id="run-1",
        revision=1,
        content_hash=f"sha256:{'b' * 64}",
    )
    with pytest.raises(BusinessInvestigationReconciliationConflict, match="drifted"):
        coordinator.record_timeout(
            SCOPE, "run-1", stale, command(), actor="owner", occurred_at=NOW
        )
    with pytest.raises(BusinessInvestigationReconciliationConflict, match="UNKNOWN"):
        coordinator.begin_reconcile(
            SCOPE, "run-1", ref(stable), command(), actor="owner", occurred_at=NOW
        )
    assert not runs.calls


def test_reconcile_rejects_uncertain_command_drift() -> None:
    original = command()
    unknown = state(2, BusinessInvestigationRunControl.UNKNOWN, command=original)
    runs = FakeRuns(unknown)
    coordinator = BusinessInvestigationReconciliationCoordinator(runs)
    different = BusinessInvestigationUncertainCommand(
        command_id="command-2",
        operation=original.operation,
        request_hash=original.request_hash,
    )
    with pytest.raises(BusinessInvestigationReconciliationConflict, match="command drifted"):
        coordinator.begin_reconcile(
            SCOPE, "run-1", ref(unknown), different, actor="owner", occurred_at=NOW
        )
    assert not runs.calls


def test_canonical_transition_result_drift_is_rejected() -> None:
    class DriftedRuns(FakeRuns):
        def mark_unknown(self, scope, run_id, uncertain_command, **kwargs):
            result = super().mark_unknown(
                scope, run_id, uncertain_command, **kwargs
            )
            result.authority.prior_ref = InvestigationExactRef(
                resource_type="BusinessInvestigationRunStateRevision",
                resource_id="other-run",
                revision=1,
                content_hash=HASH_A,
            )
            return result

    stable = state(1, BusinessInvestigationRunControl.RUNNING)
    runs = DriftedRuns(stable)
    with pytest.raises(BusinessInvestigationReconciliationConflict, match="result drifted"):
        BusinessInvestigationReconciliationCoordinator(runs).record_timeout(
            SCOPE, "run-1", ref(stable), command(), actor="owner", occurred_at=NOW
        )
