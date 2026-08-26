"""BI-W8-03 Receipt-first workbench data command tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_business_investigation_data_requester import (
    BusinessInvestigationDataRequester,
)
from aos_api.aip_business_investigation_data_saga import (
    BusinessInvestigationDataRequirementSaga,
)
from aos_api.aip_contracts import TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import (
    DataRequirementApplyResult,
    DataRequirementCommandReceipt,
)
from aos_api.ecommerce_business_investigation_data_command import (
    ConfirmBusinessInvestigationDataRequirementCommand,
    EcommerceBusinessInvestigationDataCommandService,
    RequestBusinessInvestigationMissingDataCommand,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationRunStateWrite,
)
from aos_api.tenant_scope import TenantScope
from test_aip_business_investigation_data_requester import request, runtime
from test_aip_business_investigation_data_saga import compilation_receipt


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)


def exact(kind: str, identity: str, fill: str, revision: int = 1):
    return InvestigationExactRef(
        resource_type=kind,
        resource_id=identity,
        revision=revision,
        content_hash=f"sha256:{fill * 64}",
    )


def command() -> RequestBusinessInvestigationMissingDataCommand:
    payload = request().model_dump(mode="json", by_alias=True)
    for key in ("requirementId", "idempotencyKey", "channelRef", "entityRef"):
        payload.pop(key)
    return RequestBusinessInvestigationMissingDataCommand.model_validate(payload)


def state(
    version: int = 1,
    *,
    pending: InvestigationExactRef | None = None,
) -> BusinessInvestigationRunStateRevision:
    payload = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "runId": "investigation-run-1",
        "version": version,
        "priorRef": (
            None
            if version == 1
            else exact(
                "BusinessInvestigationRunStateRevision",
                "investigation-run-1",
                "d",
                version - 1,
            ).model_dump(mode="json", by_alias=True)
        ),
        "lifecycle": "PREPARING" if pending is None else "WAITING_DATA",
        "control": "RUNNING",
        "eventSequence": version,
        "contentHash": "sha256:" + "0" * 64,
        "pendingRequirementRef": (
            None if pending is None else pending.model_dump(mode="json", by_alias=True)
        ),
        "createdBy": "user:data-owner",
        "createdAt": NOW,
    }
    parsed = BusinessInvestigationRunStateRevision.model_validate(payload)
    return parsed.model_copy(update={"content_hash": parsed.calculated_content_hash()})


class FakeCases:
    def get(self, scope, case_id):
        assert scope == SCOPE and case_id == "case-1"
        return SimpleNamespace(
            tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
            case_id="case-1",
            revision=1,
            content_hash="sha256:" + "1" * 64,
            channel_ref=request().channel_ref,
            business_entity_ref=request().entity_ref,
        )


class FakeReceipts:
    def get_for_run(self, scope, run_ref):
        assert scope == SCOPE and run_ref == compilation_receipt().run_ref
        return compilation_receipt()


class FakeRuntime:
    def bind_receipt(self, scope, receipt, domain_run):
        assert scope == SCOPE and receipt == compilation_receipt()
        return runtime()


class FakeData:
    def __init__(self) -> None:
        self.receipts = {}
        self.current = None

    def request(self, scope, actor, key, item, *, expected_version):
        assert scope == SCOPE and expected_version == 0
        return self._record("request", key, item)

    def accept(self, scope, actor, key, item, *, expected_version):
        assert expected_version == item.revision - 1
        return self._record("accept", key, item)

    def reject(self, scope, actor, key, item, *, expected_version):
        assert expected_version == item.revision - 1
        return self._record("reject", key, item)

    def _record(self, operation, key, item):
        exact_ref = InvestigationExactRef(
            resource_type="DataRequirementRevision",
            resource_id=item.requirement_id,
            revision=item.revision,
            content_hash=item.content_hash,
        )
        result = DataRequirementApplyResult(
            exact_ref=exact_ref,
            version=item.revision,
            etag=item.content_hash,
            replayed=False,
        )
        self.receipts[(operation, key)] = DataRequirementCommandReceipt(item, result)
        self.current = item
        return result

    def find_command_receipt(self, scope, operation, key):
        receipt = self.receipts.get((operation, key))
        if receipt is None:
            return None
        return DataRequirementCommandReceipt(
            authority=receipt.authority,
            result=receipt.result.__class__(
                exact_ref=receipt.result.exact_ref,
                version=receipt.result.version,
                etag=receipt.result.etag,
                replayed=True,
            ),
        )

    def get_current(self, scope, requirement_id):
        assert self.current is not None and self.current.requirement_id == requirement_id
        return self.current


class FakeRuns:
    def __init__(self) -> None:
        self.view = SimpleNamespace(
            authority=SimpleNamespace(
                tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
                run_id="investigation-run-1",
                version=1,
                content_hash="sha256:" + "2" * 64,
                case_ref=exact("BusinessInvestigationCaseRevision", "case-1", "1"),
            ),
            state=state(),
        )
        self.receipts = {}
        self.fail_once = False

    def get(self, scope, run_id):
        assert scope == SCOPE and run_id == "investigation-run-1"
        return self.view

    def request_data(
        self,
        scope,
        run_id,
        requirement_ref,
        *,
        expected_version,
        idempotency_key,
        actor,
        occurred_at,
    ):
        if idempotency_key in self.receipts:
            return BusinessInvestigationRunStateWrite(
                authority=self.receipts[idempotency_key], replayed=True
            )
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("transient Run transition failure")
        assert expected_version == self.view.state.version
        authority = state(expected_version + 1, pending=requirement_ref)
        self.receipts[idempotency_key] = authority
        self.view.state = authority
        return BusinessInvestigationRunStateWrite(authority=authority, replayed=False)


def service(runs: FakeRuns, data: FakeData):
    return EcommerceBusinessInvestigationDataCommandService(
        case_store=FakeCases(),
        run_store=runs,
        receipt_store=FakeReceipts(),
        runtime_binder=FakeRuntime(),
        data_store=data,
        data_saga=BusinessInvestigationDataRequirementSaga(
            BusinessInvestigationDataRequester(data)
        ),
    )


def test_request_is_receipt_first_and_partial_failure_reentry_reuses_data() -> None:
    runs, data = FakeRuns(), FakeData()
    runs.fail_once = True
    with pytest.raises(RuntimeError, match="transient"):
        service(runs, data).request_missing_data(
            SCOPE,
            "investigation-run-1",
            command(),
            expected_version=1,
            idempotency_key="web-command-1",
            actor="user:data-owner",
            occurred_at=NOW,
        )
    assert data.current is not None and runs.view.state.version == 1

    result = service(runs, data).request_missing_data(
        SCOPE,
        "investigation-run-1",
        command(),
        expected_version=1,
        idempotency_key="web-command-1",
        actor="user:data-owner",
        occurred_at=NOW,
    )
    assert result.data_replayed is True and result.run_replayed is False
    assert result.run_authority.pending_requirement_ref.resource_id == data.current.requirement_id
    assert result.source_read_performed is False
    assert result.external_effect_authorized is False


def test_request_rejects_same_web_key_with_different_body_before_second_data_write() -> None:
    runs, data = FakeRuns(), FakeData()
    service(runs, data).request_missing_data(
        SCOPE,
        "investigation-run-1",
        command(),
        expected_version=1,
        idempotency_key="web-command-conflict",
        actor="user:data-owner",
        occurred_at=NOW,
    )
    changed = command().model_copy(update={"required_facts": ["different.fact"]})
    with pytest.raises(RuntimeError, match="Receipt drifted"):
        service(runs, data).request_missing_data(
            SCOPE,
            "investigation-run-1",
            changed,
            expected_version=1,
            idempotency_key="web-command-conflict",
            actor="user:data-owner",
            occurred_at=NOW,
        )
    assert len(data.receipts) == 1


def test_manual_accept_and_reject_append_successor_and_rebind_run() -> None:
    for decision in ("accept", "reject"):
        runs, data = FakeRuns(), FakeData()
        created = service(runs, data).request_missing_data(
            SCOPE,
            "investigation-run-1",
            command(),
            expected_version=1,
            idempotency_key=f"create-{decision}",
            actor="user:data-owner",
            occurred_at=NOW,
        )
        confirmed = service(runs, data).confirm_requirement(
            SCOPE,
            "investigation-run-1",
            ConfirmBusinessInvestigationDataRequirementCommand(
                decision=decision,
                reason="人工范围复核完成" if decision == "reject" else None,
            ),
            expected_version=created.run_authority.version,
            idempotency_key=f"confirm-{decision}",
            actor="user:data-owner",
            occurred_at=NOW,
        )
        assert confirmed.requirement_ref.revision == 2
        assert confirmed.requirement_status.value == (
            "accepted" if decision == "accept" else "rejected"
        )
        assert bool(data.current.blockers) is (decision == "reject")
        assert confirmed.run_authority.pending_requirement_ref.revision == 2


def test_confirmation_rejects_same_key_with_opposite_decision_without_new_revision() -> None:
    runs, data = FakeRuns(), FakeData()
    created = service(runs, data).request_missing_data(
        SCOPE,
        "investigation-run-1",
        command(),
        expected_version=1,
        idempotency_key="create-confirm-conflict",
        actor="user:data-owner",
        occurred_at=NOW,
    )
    service(runs, data).confirm_requirement(
        SCOPE,
        "investigation-run-1",
        ConfirmBusinessInvestigationDataRequirementCommand(decision="accept"),
        expected_version=created.run_authority.version,
        idempotency_key="confirm-conflict",
        actor="user:data-owner",
        occurred_at=NOW,
    )
    with pytest.raises(RuntimeError, match="idempotency conflict"):
        service(runs, data).confirm_requirement(
            SCOPE,
            "investigation-run-1",
            ConfirmBusinessInvestigationDataRequirementCommand(
                decision="reject", reason="改为驳回"
            ),
            expected_version=created.run_authority.version,
            idempotency_key="confirm-conflict",
            actor="user:data-owner",
            occurred_at=NOW,
        )
    assert data.current.revision == 2 and data.current.status.value == "accepted"


def test_confirmation_body_has_one_canonical_accept_shape_and_bounded_reject_reason() -> None:
    assert ConfirmBusinessInvestigationDataRequirementCommand(decision="accept").reason is None
    with pytest.raises(ValueError, match="accept does not persist a reason"):
        ConfirmBusinessInvestigationDataRequirementCommand(
            decision="accept", reason="不会落入 authority 的说明"
        )
    with pytest.raises(ValueError, match="rejection reason is required"):
        ConfirmBusinessInvestigationDataRequirementCommand(decision="reject")
