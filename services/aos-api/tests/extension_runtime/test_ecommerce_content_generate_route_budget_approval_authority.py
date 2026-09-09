from datetime import UTC, datetime

import pytest

from aos_api.aip_budget_reservation_store import (
    AipBudgetReservationStore,
    BudgetExactRef,
    BudgetReservationBlocked,
    canonical_hash,
)
from aos_api.aip_model_runtime_store import canonical_hash as model_runtime_canonical_hash
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
HASH_A = "a" * 64


def _ref(kind: str, identity: str, digest: str = HASH_A):
    return InvestigationExactRef.model_validate(
        {
            "resourceType": kind,
            "resourceId": identity,
            "revision": 1,
            "contentHash": "sha256:" + digest,
        }
    )


def _route_payload():
    asset = lambda kind, identity: {
        "assetType": kind,
        "assetId": identity,
        "revision": 1,
        "contentHash": HASH_A,
    }
    content = {
        "routeId": "route-1",
        "taskTypes": ["content_campaign"],
        "requiredInputModality": "text",
        "requiredOutputModality": "text",
        "requiredCapabilities": ["capability-1"],
        "candidates": [{"model": asset("RegisteredModelRevision", "model-1"), "weight": 100}],
        "strategy": "failover",
        "runtimePolicyRef": asset("RuntimePolicyRevision", "policy-1"),
        "evalGateRef": asset("EvalGateDecision", "gate-1"),
        "lifecycle": "active",
    }
    digest = model_runtime_canonical_hash(content)
    return {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "revision": 1,
        "contentHash": digest,
        **content,
        "createdBy": "pytest",
        "createdAt": "2026-09-09T06:00:00+00:00",
    }


def _authorities(route_digest: str):
    return {
        "task": _ref("Task", "task-1"),
        "capability": _ref("CapabilityRevision", "capability-1"),
        "model_route": _ref("ModelRouteRevision", "route-1", route_digest),
        "budget": _ref("BudgetRevision", "budget-1"),
        "pricing": _ref("ModelPriceSnapshotRevision", "price-1"),
        "approval": _ref("ActionApprovalEvent", "approval-1"),
    }


class Transaction:
    def __init__(self):
        self.payload = _route_payload()
        self.head = {"current_revision": 1, "version": 1}
        self.checked_at = datetime(2026, 9, 9, 6, tzinfo=UTC)
        self.queries = []

    def execute(self, query, _params=()):
        self.queries.append(query)
        value = (
            self.head
            if "model_route_head" in query
            else {
                "content_hash": self.payload["contentHash"],
                "lifecycle": self.payload["lifecycle"],
                "payload": self.payload,
            }
            if "model_route_revision" in query
            else {"checked_at": self.checked_at}
        )

        class Result:
            def fetchone(self):
                return value

        return Result()


def _budget_spies(monkeypatch):
    calls = []
    monkeypatch.setattr(
        AipBudgetReservationStore,
        "_budget_authority",
        lambda _self, _tx, _scope, ref, cutoff: calls.append(("budget", ref, cutoff)),
    )
    monkeypatch.setattr(
        AipBudgetReservationStore,
        "_price_authority",
        lambda _self, _tx, _scope, ref, cutoff: calls.append(("price", ref, cutoff)),
    )
    monkeypatch.setattr(
        AipBudgetReservationStore,
        "_approval_authority",
        lambda _self, _tx, _scope, ref, cutoff, **kwargs: calls.append(
            ("approval", ref, cutoff, kwargs)
        ),
    )
    return calls


def test_content_generate_accepts_current_route_budget_price_and_approval(monkeypatch):
    transaction = Transaction()
    calls = _budget_spies(monkeypatch)
    ContentGenerateHostService._route_budget_approval_authority(
        transaction,
        SCOPE,
        _authorities(transaction.payload["contentHash"]),
        upper_bound_fen=500,
    )
    assert all("public." in query for query in transaction.queries[:-1])
    assert [call[0] for call in calls] == ["budget", "price", "approval"]
    assert calls[-1][3]["task_ref"].resource_id == "task-1"
    assert calls[-1][3]["operation_id"] == "ecommerce_growth_content_generate"
    assert calls[-1][3]["upper_bound_minor"] == 500


@pytest.mark.parametrize(
    "drift",
    (
        "head_bool",
        "head_current",
        "row_hash",
        "payload_hash",
        "payload_bool",
        "revision_bool",
        "tenant",
        "lifecycle",
        "task_type",
        "strategy",
        "multiple_candidates",
        "input_modality",
        "output_modality",
        "capability",
        "route_ref",
    ),
)
def test_content_generate_rejects_model_route_drift(monkeypatch, drift):
    transaction = Transaction()
    _budget_spies(monkeypatch)
    authorities = _authorities(transaction.payload["contentHash"])
    if drift == "head_bool":
        transaction.head["version"] = True
    elif drift == "head_current":
        transaction.head["current_revision"] = 2
    elif drift == "row_hash":
        transaction.payload["contentHash"] = HASH_A
    elif drift == "payload_hash":
        transaction.payload["taskTypes"] = ["other"]
    elif drift == "payload_bool":
        transaction.payload["candidates"][0]["weight"] = True
    elif drift == "revision_bool":
        transaction.payload["revision"] = True
    elif drift == "tenant":
        transaction.payload["tenant"] = {
            "orgId": "dev-org",
            "projectId": SCOPE.project_id,
        }
    elif drift == "lifecycle":
        transaction.payload["lifecycle"] = "validated"
    elif drift == "task_type":
        transaction.payload["taskTypes"] = ["other"]
        transaction.payload["contentHash"] = model_runtime_canonical_hash(
            {
                name: value
                for name, value in transaction.payload.items()
                if name not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
            }
        )
        authorities["model_route"] = _ref(
            "ModelRouteRevision", "route-1", transaction.payload["contentHash"]
        )
    elif drift == "strategy":
        transaction.payload["strategy"] = "weighted"
        transaction.payload["contentHash"] = model_runtime_canonical_hash(
            {
                name: value
                for name, value in transaction.payload.items()
                if name not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
            }
        )
        authorities["model_route"] = _ref(
            "ModelRouteRevision", "route-1", transaction.payload["contentHash"]
        )
    elif drift == "multiple_candidates":
        transaction.payload["candidates"].append(
            {
                "model": {
                    "assetType": "RegisteredModelRevision",
                    "assetId": "model-2",
                    "revision": 1,
                    "contentHash": HASH_A,
                },
                "weight": 100,
            }
        )
        transaction.payload["contentHash"] = model_runtime_canonical_hash(
            {
                name: value
                for name, value in transaction.payload.items()
                if name not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
            }
        )
        authorities["model_route"] = _ref(
            "ModelRouteRevision", "route-1", transaction.payload["contentHash"]
        )
    elif drift == "input_modality":
        transaction.payload["requiredInputModality"] = "image"
    elif drift == "output_modality":
        transaction.payload["requiredOutputModality"] = "image"
    elif drift == "capability":
        transaction.payload["requiredCapabilities"] = ["other"]
    elif drift == "route_ref":
        authorities["model_route"] = _ref("ModelRouteRevision", "route-1")
    with pytest.raises(ValueError, match="ModelRoute"):
        ContentGenerateHostService._route_budget_approval_authority(
            transaction, SCOPE, authorities, upper_bound_fen=500
        )


def test_content_generate_maps_budget_authority_failure_closed(monkeypatch):
    transaction = Transaction()
    monkeypatch.setattr(
        AipBudgetReservationStore,
        "_budget_authority",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            BudgetReservationBlocked("expired")
        ),
    )
    with pytest.raises(ValueError, match="Budget/Approval"):
        ContentGenerateHostService._route_budget_approval_authority(
            transaction,
            SCOPE,
            _authorities(transaction.payload["contentHash"]),
            upper_bound_fen=500,
        )


class ApprovalTransaction:
    def __init__(self, *, mutate_payload: bool = False, stable_bool_upper_bound: bool = False):
        self.checked_at = datetime(2026, 9, 9, 6, tzinfo=UTC)
        self.action_binding_hash = "b" * 64
        self.stable = {
            "tenantScope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "createdBy": "pytest",
            "actionType": {"id": "ecommerce_growth_content_generate"},
            "taskId": "task-1",
            "runId": None,
            "objectRef": None,
            "purpose": "approved content generation",
            "riskLevel": "R1",
            "policy": {"minimumApprovals": 1},
            "approvalPolicyHash": "c" * 64,
            "payload": {
                "budgetUpperBoundMinor": True if stable_bool_upper_bound else 500
            },
            "diff": {},
            "evidenceRefs": [],
            "impactPreviewRef": None,
            "actionBindingHash": self.action_binding_hash,
            "sourceDraftRef": None,
            "expiresAt": "2026-09-10T06:00:00+00:00",
        }
        self.proposal_hash = canonical_hash(self.stable)
        proposal_payload = dict(self.stable["payload"])
        if mutate_payload:
            proposal_payload["budgetUpperBoundMinor"] = 700
        elif stable_bool_upper_bound:
            proposal_payload["budgetUpperBoundMinor"] = 1
        self.proposal = {
            "proposal_id": "proposal-1",
            "action_type_id": "ecommerce_growth_content_generate",
            "action_type_snapshot": self.stable["actionType"],
            "task_id": "task-1",
            "run_id": None,
            "object_ref": None,
            "purpose": self.stable["purpose"],
            "risk_level": "R1",
            "policy_snapshot": self.stable["policy"],
            "payload": proposal_payload,
            "diff": {},
            "evidence_refs": [],
            "impact_preview_id": None,
            "impact_preview_revision": None,
            "impact_preview_hash": None,
            "action_binding_hash": self.action_binding_hash,
            "source_draft_id": None,
            "source_draft_revision": None,
            "source_draft_hash": None,
            "approval_policy_hash": self.stable["approvalPolicyHash"],
            "proposal_hash": self.proposal_hash,
            "status": "approved",
            "expires_at": datetime(2026, 9, 10, 6, tzinfo=UTC),
            "created_by": "pytest",
        }
        self.approval = {
            "approval_event_id": "approval-1",
            "proposal_id": "proposal-1",
            "proposal_version": 1,
            "proposal_hash": self.proposal_hash,
            "decision": "approved",
            "actor_id": "reviewer",
            "reason": "approved",
            "expires_at": datetime(2026, 9, 10, 5, tzinfo=UTC),
            "created_at": self.checked_at,
            "action_binding_hash": self.action_binding_hash,
        }

    def execute(self, query, _params=()):
        value = (
            self.approval
            if "aip_action_approval_event" in query
            else self.proposal
            if "aip_action_proposal" in query
            else {"proposal_hash": self.proposal_hash, "snapshot": self.stable}
        )

        class Result:
            def fetchone(self):
                return value

        return Result()


def _approval_refs(transaction):
    approval_ref = BudgetExactRef(
        resourceType="ActionApprovalEvent",
        resourceId="approval-1",
        revision=1,
        contentHash=canonical_hash(transaction.approval, prefixed=True),
    )
    task_ref = BudgetExactRef(
        resourceType="Task",
        resourceId="task-1",
        revision=1,
        contentHash="sha256:" + HASH_A,
    )
    return approval_ref, task_ref


def test_approval_accepts_action_store_stable_snapshot():
    transaction = ApprovalTransaction()
    approval_ref, task_ref = _approval_refs(transaction)
    AipBudgetReservationStore()._approval_authority(
        transaction,
        SCOPE,
        approval_ref,
        transaction.checked_at,
        task_ref=task_ref,
        operation_id="ecommerce_growth_content_generate",
        upper_bound_minor=500,
    )


def test_approval_rejects_proposal_payload_mutated_outside_stable_snapshot():
    transaction = ApprovalTransaction(mutate_payload=True)
    approval_ref, task_ref = _approval_refs(transaction)
    with pytest.raises(BudgetReservationBlocked, match="approval must bind"):
        AipBudgetReservationStore()._approval_authority(
            transaction,
            SCOPE,
            approval_ref,
            transaction.checked_at,
            task_ref=task_ref,
            operation_id="ecommerce_growth_content_generate",
            upper_bound_minor=700,
        )


def test_approval_rejects_bool_snapshot_changed_to_equal_integer():
    transaction = ApprovalTransaction(stable_bool_upper_bound=True)
    approval_ref, task_ref = _approval_refs(transaction)
    with pytest.raises(BudgetReservationBlocked, match="approval must bind"):
        AipBudgetReservationStore()._approval_authority(
            transaction,
            SCOPE,
            approval_ref,
            transaction.checked_at,
            task_ref=task_ref,
            operation_id="ecommerce_growth_content_generate",
            upper_bound_minor=1,
        )
