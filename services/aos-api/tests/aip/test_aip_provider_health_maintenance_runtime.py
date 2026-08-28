"""Explicit Provider Health maintenance runtime assembly acceptance."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import uuid

import pytest

from aos_api.aip_action_adapters import ACTION_ADAPTERS, ActionAdapterRegistry
from aos_api.aip_action_store import AipActionNotFound
from aos_api.aip_provider_health_action import PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
from aos_api.aip_provider_health_action_authority import (
    PROVIDER_HEALTH_ACTION_PURPOSE,
    provider_health_action_type_snapshot,
)
from aos_api.aip_provider_health_maintenance_runtime import (
    ProviderHealthRuntimeAssemblyError,
    build_provider_health_maintenance_runtime,
)
from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
# Keep expiry-sensitive API fixtures ahead of the database clock while retaining
# one stable instant for every assertion in this test process.
NOW = datetime.now(UTC)


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
               ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name,
                 object_type=EXCLUDED.object_type,parameters=EXCLUDED.parameters,
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


def _create_approved_lease(client, executor: Principal) -> tuple[dict, dict]:
    suffix = uuid.uuid4().hex
    client.app.dependency_overrides[require_principal] = lambda: _principal(
        f"runtime-maker-{suffix}", "admin"
    )
    response = client.post(
        "/v1/aip/action-proposals",
        headers=_headers(f"runtime-proposal-{suffix}"),
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
    client.app.dependency_overrides[require_principal] = lambda: _principal(
        f"runtime-checker-{suffix}", "approver"
    )
    response = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/decision",
        headers=_headers(f"runtime-approval-{suffix}"),
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
        headers=_headers(f"runtime-lease-{suffix}"),
        json={
            "expectedProposalVersion": approved["version"],
            "expectedProposalHash": approved["proposalHash"],
            "leaseSeconds": 600,
        },
    )
    assert response.status_code == 200, response.text
    return approved, response.json()["lease"]


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
            "observationId": "provider-health-runtime-assembly-test",
            "expiresAt": "2099-01-01T00:00:00Z",
            "providerCalls": 3,
            "secretPayloadReadsReported": 0,
            "promptOrAnswerBodiesReported": 0,
        }


class SnapshotStore:
    def __init__(self, snapshot=None, error=None) -> None:
        self.snapshot = snapshot
        self.error = error

    def action_type_snapshot(self, _scope, _action_type_id):
        if self.error is not None:
            raise self.error
        return self.snapshot


def test_runtime_assembly_requires_exact_installed_action_type() -> None:
    principal = _principal("runtime-executor", "aip_executor")
    refresh = CountingRefresh()
    with pytest.raises(ProviderHealthRuntimeAssemblyError) as missing:
        build_provider_health_maintenance_runtime(
            principal=principal,
            refresh_health=refresh,
            refresh_readiness=lambda **_: {},
            action_store=SnapshotStore(error=AipActionNotFound("missing")),
        )
    assert missing.value.code == "PROVIDER_HEALTH_ACTION_TYPE_NOT_INSTALLED"
    drift = {**provider_health_action_type_snapshot(), "name": "drifted"}
    with pytest.raises(ProviderHealthRuntimeAssemblyError) as drifted:
        build_provider_health_maintenance_runtime(
            principal=principal,
            refresh_health=refresh,
            refresh_readiness=lambda **_: {},
            action_store=SnapshotStore(snapshot=drift),
        )
    assert drifted.value.code == "PROVIDER_HEALTH_ACTION_TYPE_REVISION_DRIFTED"
    assert refresh.calls == 0


def test_runtime_assembly_rejects_foreign_identity_and_global_registry() -> None:
    exact = SnapshotStore(snapshot=provider_health_action_type_snapshot())
    refresh = CountingRefresh()
    with pytest.raises(ProviderHealthRuntimeAssemblyError) as global_registry:
        build_provider_health_maintenance_runtime(
            principal=_principal("runtime-executor", "aip_executor"),
            refresh_health=refresh,
            refresh_readiness=lambda **_: {},
            action_store=exact,
            registry=ACTION_ADAPTERS,
        )
    assert global_registry.value.code == "GLOBAL_ACTION_ADAPTER_REGISTRY_FORBIDDEN"
    with pytest.raises(Exception) as foreign:
        build_provider_health_maintenance_runtime(
            principal=_principal(
                "runtime-executor",
                "aip_executor",
                scope=TenantScope("dev-org", "dev-project"),
            ),
            refresh_health=refresh,
            refresh_readiness=lambda **_: {},
            action_store=exact,
        )
    assert getattr(foreign.value, "code", "") == (
        "PROVIDER_HEALTH_MAINTENANCE_TENANT_FORBIDDEN"
    )
    assert refresh.calls == 0


def test_explicit_runtime_assembly_executes_one_approved_lease_only(client) -> None:
    _seed_action_type()
    suffix = uuid.uuid4().hex
    executor = _principal(f"runtime-executor-{suffix}", "aip_executor")
    refresh = CountingRefresh()
    readiness_calls = []
    registry = ActionAdapterRegistry()
    runtime = build_provider_health_maintenance_runtime(
        principal=executor,
        refresh_health=refresh,
        refresh_readiness=lambda **_: (
            readiness_calls.append(1)
            or {
                "status": "R12_ECOMMERCE_RUNTIME_READINESS_REFRESH_GREEN",
                "completedRoles": ["a", "b", "c", "d", "e", "f"],
            }
        ),
        model_runtime_store=DueHealthStore(),
        registry=registry,
        clock=lambda: NOW,
    )
    assert runtime.registry is registry
    assert runtime.conformance_report.green is True
    assert refresh.calls == 0
    assert ACTION_ADAPTERS.get(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID) is None
    no_lease = runtime.maintainer.run_once()
    assert no_lease["errorCode"] == "EXACT_APPROVAL_LEASE_REQUIRED"
    assert refresh.calls == 0
    proposal, lease = _create_approved_lease(client, executor)
    first = runtime.maintainer.run_once()
    second = runtime.maintainer.run_once()
    assert first["status"] == "TEXT_PROVIDER_HEALTH_MAINTENANCE_GREEN"
    assert first["observationId"] == "provider-health-runtime-assembly-test"
    assert second["errorCode"] == "EXACT_APPROVAL_LEASE_REQUIRED"
    assert refresh.calls == 1
    assert readiness_calls == [1]
    with connect(SCOPE) as conn:
        counts = conn.execute(
            """SELECT
                 (SELECT COUNT(*) FROM aip_action_execution_attempt
                   WHERE proposal_id=%s) AS attempts,
                 (SELECT COUNT(*) FROM aip_action_receipt
                   WHERE proposal_id=%s) AS receipts""",
            (proposal["id"], proposal["id"]),
        ).fetchone()
    assert dict(counts) == {"attempts": 1, "receipts": 1}
    assert lease["id"]
    assert ACTION_ADAPTERS.get(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID) is None
    client.app.dependency_overrides.pop(require_principal, None)
