"""AIP-3B execution authority acceptance tests."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from aos_api.aip_action_adapters import ACTION_ADAPTERS, AdapterOutcome
from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope
import pytest

SCOPE = TenantScope("org-org", "dev-project")


class AppliedAdapter:
    calls = 0

    def execute(self, *, payload, idempotency_key):
        self.calls += 1
        return AdapterOutcome("applied", f"provider-{idempotency_key[-12:]}", {"echo": payload})

    def reconcile(self, *, provider_request_id, request_fingerprint):
        return AdapterOutcome("applied", provider_request_id, {"verified": request_fingerprint})


class ProviderTimeout(TimeoutError):
    provider_request_id = "provider-timeout-known"


class UnknownThenAppliedAdapter:
    def execute(self, *, payload, idempotency_key):
        raise ProviderTimeout("response lost")

    def reconcile(self, *, provider_request_id, request_fingerprint):
        return AdapterOutcome("applied", provider_request_id, {"reread": True})


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
        "Idempotency-Key": key,
    }


def _principal(subject: str, role: str) -> Principal:
    return Principal(subject=subject, org_id=SCOPE.org_id, project_id=SCOPE.project_id, roles=[role], markings=["public", "restricted"])


def _create_approved(client, action_id: str) -> dict:
    suffix = uuid.uuid4().hex
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO meta_action_type
               (id,name,object_type,parameters,required_markings,submission_criteria)
               VALUES (%s,'发送已审内容','WorkOrder','[]'::jsonb,'[]'::jsonb,'[]'::jsonb)
               ON CONFLICT (id) DO NOTHING""",
            (action_id,),
        )
        conn.commit()
    proposal = client.post(
        "/v1/aip/action-proposals",
        headers=_headers(f"proposal-{suffix}"),
        json={"actionTypeId": action_id, "purpose": "受控执行验证", "payload": {"message": "真实控制链"}},
    ).json()["proposal"]
    client.app.dependency_overrides[require_principal] = lambda: _principal("reviewer-a", "approver")
    response = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/decision",
        headers=_headers(f"approval-{suffix}"),
        json={
            "expectedProposalVersion": proposal["version"],
            "expectedProposalHash": proposal["proposalHash"],
            "decision": "approved",
            "approvalExpiresAt": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        },
    )
    client.app.dependency_overrides.pop(require_principal, None)
    assert response.status_code == 200, response.text
    return response.json()["proposal"]


def _lease(client, proposal: dict, executor: str = "executor-a") -> dict:
    client.app.dependency_overrides[require_principal] = lambda: _principal(executor, "aip_executor")
    response = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/lease",
        headers=_headers(f"lease-{uuid.uuid4().hex}"),
        json={"expectedProposalVersion": proposal["version"], "expectedProposalHash": proposal["proposalHash"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_single_attempt_lease_executes_once_and_receipt_is_authoritative(client) -> None:
    action_id = f"send_controlled_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    adapter = AppliedAdapter()
    ACTION_ADAPTERS.register(action_id, adapter)
    try:
        leased = _lease(client, proposal)
        lease = leased["lease"]
        first = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"execute-{uuid.uuid4().hex}"),
            json={"expectedProposalHash": proposal["proposalHash"]},
        )
        assert first.status_code == 200, first.text
        assert first.json()["proposal"]["status"] == "applied"
        assert [item["status"] for item in first.json()["receipts"]] == ["applied"]
        replay = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"execute-replay-{uuid.uuid4().hex}"),
            json={"expectedProposalHash": proposal["proposalHash"]},
        )
        assert replay.status_code == 200
        assert len(replay.json()["receipts"]) == 1
        assert adapter.calls == 1
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_timeout_is_unknown_and_only_reread_appends_reconcile_receipt(client) -> None:
    action_id = f"send_timeout_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    ACTION_ADAPTERS.register(action_id, UnknownThenAppliedAdapter())
    try:
        lease = _lease(client, proposal)["lease"]
        unknown = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"execute-{uuid.uuid4().hex}"),
            json={"expectedProposalHash": proposal["proposalHash"]},
        )
        assert unknown.status_code == 200
        receipt = unknown.json()["receipts"][0]
        assert receipt["status"] == "unknown"
        reconciled = client.post(
            f"/v1/aip/action-receipts/{receipt['id']}/reconcile",
            headers=_headers(f"reconcile-{uuid.uuid4().hex}"),
            json={"reason": "授权只读回查"},
        )
        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.json()["proposal"]["status"] == "reconciled"
        assert [item["receiptKind"] for item in reconciled.json()["receipts"]] == ["initial", "reconcile"]
        assert reconciled.json()["receipts"][1]["supersedesReceiptId"] == receipt["id"]
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_executor_separation_kill_switch_and_budget_fail_closed(client) -> None:
    action_id = f"send_guarded_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    client.app.dependency_overrides[require_principal] = lambda: _principal("reviewer-a", "aip_executor")
    separated = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/lease",
        headers=_headers(f"lease-separated-{uuid.uuid4().hex}"),
        json={"expectedProposalVersion": proposal["version"], "expectedProposalHash": proposal["proposalHash"]},
    )
    assert separated.status_code == 422

    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_action_guardrail
               (org_id,project_id,guardrail_id,level,action_type_id,kill_enabled,updated_by)
               VALUES (%s,%s,%s,'action_type',%s,TRUE,'security-test')""",
            (*SCOPE.key, f"guard-{uuid.uuid4().hex}", action_id),
        )
        conn.commit()
    client.app.dependency_overrides[require_principal] = lambda: _principal("executor-b", "aip_executor")
    killed = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/lease",
        headers=_headers(f"lease-killed-{uuid.uuid4().hex}"),
        json={"expectedProposalVersion": proposal["version"], "expectedProposalHash": proposal["proposalHash"]},
    )
    assert killed.status_code == 422
    client.app.dependency_overrides.pop(require_principal, None)


def test_legacy_direct_write_paths_are_closed(client) -> None:
    headers = _headers(f"legacy-{uuid.uuid4().hex}")
    execute = client.post("/v1/actions/execute", headers=headers, json={"actionTypeId": "anything", "autoApprove": True})
    assert execute.status_code == 410
    assert execute.json()["code"] == "AIP_LEGACY_WRITE_PATH_DISABLED"
    approve = client.post("/v1/aip/drafts/legacy-draft/approve", headers=headers)
    assert approve.status_code == 410
    assert approve.json()["code"] == "AIP_LEGACY_WRITE_PATH_DISABLED"


def test_budget_and_cross_tenant_lease_fail_closed(client) -> None:
    action_id = f"send_budget_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_action_guardrail
               (org_id,project_id,guardrail_id,level,action_type_id,daily_budget,updated_by)
               VALUES (%s,%s,%s,'action_type',%s,0,'security-test')""",
            (*SCOPE.key, f"guard-{uuid.uuid4().hex}", action_id),
        )
        conn.commit()
    client.app.dependency_overrides[require_principal] = lambda: _principal("executor-budget", "aip_executor")
    exhausted = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/lease",
        headers=_headers(f"lease-budget-{uuid.uuid4().hex}"),
        json={"expectedProposalVersion": proposal["version"], "expectedProposalHash": proposal["proposalHash"]},
    )
    assert exhausted.status_code == 429
    assert exhausted.json()["code"] == "AIP_BUDGET_EXCEEDED"
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="executor-canary", org_id="dev-org", project_id="dev-project", roles=["aip_executor"], markings=["public"]
    )
    invisible = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/lease",
        headers={**_headers(f"lease-canary-{uuid.uuid4().hex}"), "X-Org-Id": "dev-org"},
        json={"expectedProposalVersion": proposal["version"], "expectedProposalHash": proposal["proposalHash"]},
    )
    assert invisible.status_code == 404
    client.app.dependency_overrides.pop(require_principal, None)


def test_compensation_is_a_new_proposal_not_a_rollback(client) -> None:
    action_id = f"send_original_{uuid.uuid4().hex}"
    compensate_id = f"compensate_notice_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO meta_action_type
               (id,name,object_type,parameters,required_markings,submission_criteria)
               VALUES (%s,'补偿通知','WorkOrder','[]'::jsonb,'[]'::jsonb,'[]'::jsonb)""",
            (compensate_id,),
        )
        conn.commit()
    ACTION_ADAPTERS.register(action_id, AppliedAdapter())
    try:
        lease = _lease(client, proposal)["lease"]
        applied = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"execute-{uuid.uuid4().hex}"),
            json={"expectedProposalHash": proposal["proposalHash"]},
        ).json()
        receipt_id = applied["receipts"][0]["id"]
        compensation = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/compensation",
            headers=_headers(f"compensation-{uuid.uuid4().hex}"),
            json={
                "actionTypeId": compensate_id,
                "receiptId": receipt_id,
                "purpose": "以新提案执行补偿",
                "payload": {"message": "补偿草稿"},
            },
        )
        assert compensation.status_code == 201, compensation.text
        assert compensation.json()["proposal"]["id"] != proposal["id"]
        assert compensation.json()["proposal"]["status"] == "drafted"
        assert compensation.json()["draft"]["evidenceRefs"][0]["resourceId"] == receipt_id
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_concurrent_lease_replay_is_single_attempt(client) -> None:
    action_id = f"send_lease_concurrent_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    client.app.dependency_overrides[require_principal] = lambda: _principal("executor-concurrent", "aip_executor")
    headers = _headers(f"lease-concurrent-{uuid.uuid4().hex}")
    body = {"expectedProposalVersion": proposal["version"], "expectedProposalHash": proposal["proposalHash"]}
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _i: client.post(f"/v1/aip/action-proposals/{proposal['id']}/lease", headers=headers, json=body), range(2)))
        assert [response.status_code for response in responses] == [200, 200]
        assert len({response.json()["lease"]["id"] for response in responses}) == 1
        with connect(SCOPE) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                (*SCOPE.key, proposal["id"]),
            ).fetchone()["n"]
        assert count == 1
    finally:
        client.app.dependency_overrides.pop(require_principal, None)


def test_receipt_rows_are_database_immutable(client) -> None:
    action_id = f"send_receipt_immutable_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    ACTION_ADAPTERS.register(action_id, AppliedAdapter())
    try:
        lease = _lease(client, proposal)["lease"]
        applied = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"execute-{uuid.uuid4().hex}"),
            json={"expectedProposalHash": proposal["proposalHash"]},
        ).json()
        receipt_id = applied["receipts"][0]["id"]
        with pytest.raises(Exception, match="AIP_ACTION_RECEIPT_IMMUTABLE"):
            with connect(SCOPE) as conn:
                conn.execute(
                    "UPDATE aip_action_receipt SET status='failed' WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
                    (*SCOPE.key, receipt_id),
                )
                conn.commit()
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_missing_adapter_does_not_consume_lease(client) -> None:
    action_id = f"send_missing_adapter_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    try:
        lease = _lease(client, proposal)["lease"]
        blocked = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"execute-{uuid.uuid4().hex}"),
            json={"expectedProposalHash": proposal["proposalHash"]},
        )
        assert blocked.status_code == 503
        assert blocked.json()["code"] == "AIP_DEPENDENCY_UNAVAILABLE"
        with connect(SCOPE) as conn:
            row = conn.execute(
                "SELECT status,consumed_at FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s",
                (*SCOPE.key, lease["id"]),
            ).fetchone()
        assert row["status"] == "active"
        assert row["consumed_at"] is None
    finally:
        client.app.dependency_overrides.pop(require_principal, None)
