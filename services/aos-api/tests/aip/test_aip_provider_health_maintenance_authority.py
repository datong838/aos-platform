"""Canonical Lease -> Receipt -> maintenance bridge acceptance."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import uuid

from aos_api.aip_action_adapters import ACTION_ADAPTERS
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_store import AipActionNotFound, AipActionStore
from aos_api.aip_provider_health_action import PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
from aos_api.aip_provider_health_action_authority import (
    PROVIDER_HEALTH_ACTION_PURPOSE,
    provider_health_action_type_snapshot,
    register_provider_health_action_adapter,
)
from aos_api.aip_provider_health_maintenance import AipTextProviderHealthMaintainer
from aos_api.aip_provider_health_maintenance_authority import (
    ProviderHealthActionLeaseConsumer,
    ProviderHealthLeaseExecution,
)
from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 28, 13, 0, tzinfo=UTC)


def _principal(subject: str, role: str, *, scope: TenantScope = SCOPE) -> Principal:
    return Principal(
        subject=subject,
        org_id=scope.org_id,
        project_id=scope.project_id,
        roles=[role],
        markings=["public", "restricted"],
    )


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
        "Idempotency-Key": key,
    }


def _seed_action_type() -> None:
    snapshot = provider_health_action_type_snapshot()
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO meta_action_type
               (id,name,object_type,parameters,required_markings,submission_criteria)
               VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
               ON CONFLICT (id) DO UPDATE SET
                 name=EXCLUDED.name,
                 object_type=EXCLUDED.object_type,
                 parameters=EXCLUDED.parameters,
                 required_markings=EXCLUDED.required_markings,
                 submission_criteria=EXCLUDED.submission_criteria""",
            (
                snapshot["id"],
                snapshot["name"],
                snapshot["objectType"],
                json.dumps(snapshot["parameters"]),
                json.dumps(snapshot["requiredMarkings"]),
                json.dumps(snapshot["submissionCriteria"]),
            ),
        )
        conn.commit()


class DueHealthStore:
    def list_latest_provider_health(self, _scope):
        return []


class CountingRefresh:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> dict:
        self.calls += 1
        return {
            "status": "PROVIDER_HEALTH_REFRESH_GREEN",
            "observationId": "provider-health-maintenance-action-test",
            "expiresAt": "2099-01-01T00:00:00Z",
            "providerCalls": 3,
            "secretPayloadReadsReported": 0,
            "promptOrAnswerBodiesReported": 0,
        }


def _approved_lease(client) -> tuple[Principal, dict, dict]:
    suffix = uuid.uuid4().hex
    maker = _principal(f"maintenance-maker-{suffix}", "admin")
    checker = _principal(f"maintenance-checker-{suffix}", "approver")
    executor = _principal(f"maintenance-executor-{suffix}", "aip_executor")
    client.app.dependency_overrides[require_principal] = lambda: maker
    response = client.post(
        "/v1/aip/action-proposals",
        headers=_headers(f"maintenance-proposal-{suffix}"),
        json={
            "actionTypeId": PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
            "purpose": PROVIDER_HEALTH_ACTION_PURPOSE,
            "payload": {
                "providerId": "agnes-text-qyh-dev",
                "providerRevision": 7,
                "probeCount": 3,
                "outputPolicy": "metadata-only",
            },
        },
    )
    assert response.status_code == 201, response.text
    proposal = response.json()["proposal"]
    client.app.dependency_overrides[require_principal] = lambda: checker
    response = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/decision",
        headers=_headers(f"maintenance-approval-{suffix}"),
        json={
            "expectedProposalVersion": proposal["version"],
            "expectedProposalHash": proposal["proposalHash"],
            "decision": "approved",
            "approvalExpiresAt": (NOW + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    approved = response.json()["proposal"]
    client.app.dependency_overrides[require_principal] = lambda: executor
    response = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/lease",
        headers=_headers(f"maintenance-lease-{suffix}"),
        json={
            "expectedProposalVersion": approved["version"],
            "expectedProposalHash": approved["proposalHash"],
            "leaseSeconds": 600,
        },
    )
    assert response.status_code == 200, response.text
    return executor, approved, response.json()["lease"]


def test_maintainer_consumes_one_exact_receipt_without_double_refresh(client) -> None:
    _seed_action_type()
    executor, proposal, lease = _approved_lease(client)
    refresh = CountingRefresh()
    canary_execution = ProviderHealthLeaseExecution(
        principal=_principal(
            "maintenance-canary-executor",
            "aip_executor",
            scope=TenantScope("dev-org", "dev-project"),
        ),
        lease_id=lease["id"],
        expected_proposal_hash=proposal["proposalHash"],
    )
    try:
        ProviderHealthActionLeaseConsumer(
            AipActionExecutionService(AipActionStore(), ACTION_ADAPTERS),
            canary_execution,
        )(NOW)
    except AipActionNotFound:
        pass
    else:
        raise AssertionError("cross-tenant lease consumption must fail closed")
    assert refresh.calls == 0
    _adapter, revision, report = register_provider_health_action_adapter(
        ACTION_ADAPTERS, refresh
    )
    readiness_calls = []
    legacy_calls = []
    try:
        consumer = ProviderHealthActionLeaseConsumer(
            AipActionExecutionService(AipActionStore(), ACTION_ADAPTERS),
            ProviderHealthLeaseExecution(
                principal=executor,
                lease_id=lease["id"],
                expected_proposal_hash=proposal["proposalHash"],
            ),
        )
        maintainer = AipTextProviderHealthMaintainer(
            store=DueHealthStore(),
            refresh_health=lambda: legacy_calls.append("legacy"),
            refresh_readiness=lambda **_: (
                readiness_calls.append(1)
                or {
                    "status": "R12_ECOMMERCE_RUNTIME_READINESS_REFRESH_GREEN",
                    "completedRoles": ["a", "b", "c", "d", "e", "f"],
                }
            ),
            execute_authorized_refresh=consumer,
            clock=lambda: NOW,
        )
        first = maintainer.run_once()
        second = maintainer.run_once()
        assert first["status"] == second["status"] == (
            "TEXT_PROVIDER_HEALTH_MAINTENANCE_GREEN"
        )
        assert first["observationId"] == (
            "provider-health-maintenance-action-test"
        )
        assert refresh.calls == 1
        assert legacy_calls == []
        assert readiness_calls == [1, 1]
        assert report.green is True
        with connect(SCOPE) as conn:
            counts = conn.execute(
                """SELECT
                     (SELECT COUNT(*) FROM aip_action_execution_attempt
                       WHERE org_id=%s AND project_id=%s AND proposal_id=%s) AS attempts,
                     (SELECT COUNT(*) FROM aip_action_receipt
                       WHERE org_id=%s AND project_id=%s AND proposal_id=%s) AS receipts""",
                (*SCOPE.key, proposal["id"], *SCOPE.key, proposal["id"]),
            ).fetchone()
        assert dict(counts) == {"attempts": 1, "receipts": 1}
    finally:
        ACTION_ADAPTERS.unregister(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
        ACTION_ADAPTERS.unregister_conformant(revision.exact_ref())
        client.app.dependency_overrides.pop(require_principal, None)


def test_lease_execution_rejects_invalid_hash_before_service_call() -> None:
    try:
        ProviderHealthLeaseExecution(
            principal=_principal("executor", "aip_executor"),
            lease_id="lease-1",
            expected_proposal_hash="not-a-hash",
        )
    except ValueError as exc:
        assert "sha256" in str(exc)
    else:
        raise AssertionError("invalid expected hash must fail closed")
