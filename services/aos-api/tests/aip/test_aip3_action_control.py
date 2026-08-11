"""AIP-3A proposal/draft/approval safety acceptance tests."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")


def _headers(key: str, scope: TenantScope = SCOPE) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": scope.org_id,
        "X-Project-Id": scope.project_id,
        "Idempotency-Key": key,
    }


def _seed_action(action_id: str, name: str = "发送单次通知") -> None:
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO meta_action_type
               (id,name,object_type,parameters,required_markings,submission_criteria)
               VALUES (%s,%s,'WorkOrder','[]'::jsonb,'[]'::jsonb,'[]'::jsonb)
               ON CONFLICT (id) DO NOTHING""",
            (action_id, name),
        )
        conn.commit()


def _reviewer(subject: str) -> Principal:
    return Principal(
        subject=subject,
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["approver"],
        markings=["public", "restricted"],
    )


def test_proposal_is_persistent_idempotent_and_maker_cannot_self_approve(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"send_contact_{suffix}"
    _seed_action(action_id)
    headers = _headers(f"proposal-{suffix}")
    body = {
        "actionTypeId": action_id,
        "purpose": "向单个客户发送已审阅通知",
        "payload": {"message": "已审阅内容"},
        "diff": {"message": {"from": None, "to": "已审阅内容"}},
    }
    created = client.post("/v1/aip/action-proposals", headers=headers, json=body)
    assert created.status_code == 201, created.text
    bundle = created.json()
    assert bundle["proposal"]["riskLevel"] == "R2"
    assert bundle["proposal"]["status"] == "drafted"
    assert bundle["draft"]["status"] == "awaiting_approval"
    with connect(SCOPE) as conn:
        snapshot = conn.execute(
            "SELECT snapshot FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
            (*SCOPE.key, bundle["proposal"]["id"]),
        ).fetchone()["snapshot"]
    assert snapshot["tenantScope"] == {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id}
    assert snapshot["createdBy"] == "user:dev"

    replay = client.post("/v1/aip/action-proposals", headers=headers, json=body)
    assert replay.status_code == 201
    assert replay.json()["proposal"]["id"] == bundle["proposal"]["id"]

    conflict = client.post(
        "/v1/aip/action-proposals",
        headers=headers,
        json={**body, "payload": {"message": "不同内容"}},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "AIP_IDEMPOTENCY_CONFLICT"

    self_approval = client.post(
        f"/v1/aip/action-proposals/{bundle['proposal']['id']}/decision",
        headers={**headers, "Idempotency-Key": f"self-{suffix}"},
        json={
            "expectedProposalVersion": 1,
            "expectedProposalHash": bundle["proposal"]["proposalHash"],
            "decision": "approved",
        },
    )
    assert self_approval.status_code == 422
    assert self_approval.json()["code"] == "AIP_INVALID_TRANSITION"


def test_expired_proposal_and_non_approver_are_rejected(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"publish_expiry_{suffix}"
    _seed_action(action_id, "发布内容")
    headers = _headers(f"proposal-{suffix}")
    expired = client.post(
        "/v1/aip/action-proposals",
        headers=headers,
        json={
            "actionTypeId": action_id,
            "purpose": "过期提案",
            "expiresAt": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        },
    )
    assert expired.status_code == 422

    proposal = client.post(
        "/v1/aip/action-proposals",
        headers={**headers, "Idempotency-Key": f"active-{suffix}"},
        json={"actionTypeId": action_id, "purpose": "待审批提案"},
    ).json()["proposal"]
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="viewer-a",
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["viewer"],
        markings=["public"],
    )
    try:
        denied = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/decision",
            headers={**headers, "Idempotency-Key": f"deny-{suffix}"},
            json={
                "expectedProposalVersion": proposal["version"],
                "expectedProposalHash": proposal["proposalHash"],
                "decision": "approved",
            },
        )
        assert denied.status_code == 403
        assert denied.json()["code"] == "AIP_SCOPE_FORBIDDEN"
    finally:
        client.app.dependency_overrides.pop(require_principal, None)


def test_checker_approval_binds_exact_hash_and_cross_tenant_cannot_discover(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"publish_notice_{suffix}"
    _seed_action(action_id, "发布单次通知")
    headers = _headers(f"proposal-{suffix}")
    created = client.post(
        "/v1/aip/action-proposals",
        headers=headers,
        json={"actionTypeId": action_id, "purpose": "单次发布", "payload": {"text": "内容"}},
    ).json()
    proposal = created["proposal"]

    client.app.dependency_overrides[require_principal] = lambda: _reviewer("reviewer-a")
    try:
        stale = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/decision",
            headers={**headers, "Idempotency-Key": f"stale-{suffix}"},
            json={
                "expectedProposalVersion": 1,
                "expectedProposalHash": "0" * 64,
                "decision": "approved",
            },
        )
        assert stale.status_code == 409
        approved = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/decision",
            headers={**headers, "Idempotency-Key": f"approve-{suffix}"},
            json={
                "expectedProposalVersion": 1,
                "expectedProposalHash": proposal["proposalHash"],
                "decision": "approved",
                "reason": "checker approved exact snapshot",
            },
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["proposal"]["status"] == "approved"
        assert approved.json()["draft"]["status"] == "approved"
        assert len(approved.json()["approvals"]) == 1
    finally:
        client.app.dependency_overrides.pop(require_principal, None)

    canary = client.get(
        "/v1/aip/action-proposals",
        headers=_headers(f"canary-{suffix}", TenantScope("dev-org", "dev-project")),
    )
    assert canary.status_code == 200
    assert proposal["id"] not in {item["proposal"]["id"] for item in canary.json()["items"]}


def test_r4_is_server_classified_and_requires_two_checkers(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"refund_payment_{suffix}"
    _seed_action(action_id, "退款支付")
    headers = _headers(f"proposal-{suffix}")
    proposal = client.post(
        "/v1/aip/action-proposals",
        headers=headers,
        json={
            "actionTypeId": action_id,
            "purpose": "退款提案",
            "riskHint": "R0",
            "payload": {"refundAmount": 1},
        },
    ).json()["proposal"]
    assert proposal["riskLevel"] == "R4"
    assert proposal["policySnapshot"]["executionAllowed"] is False

    current = proposal
    for index, reviewer in enumerate(("reviewer-a", "reviewer-b"), start=1):
        client.app.dependency_overrides[require_principal] = lambda reviewer=reviewer: _reviewer(reviewer)
        response = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/decision",
            headers={**headers, "Idempotency-Key": f"approve-{index}-{suffix}"},
            json={
                "expectedProposalVersion": current["version"],
                "expectedProposalHash": proposal["proposalHash"],
                "decision": "approved",
            },
        )
        assert response.status_code == 200, response.text
        current = response.json()["proposal"]
    client.app.dependency_overrides.pop(require_principal, None)
    assert current["status"] == "approved"
    assert current["version"] == 3


def test_concurrent_approval_replay_creates_one_event(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"send_concurrent_{suffix}"
    _seed_action(action_id)
    headers = _headers(f"proposal-{suffix}")
    proposal = client.post(
        "/v1/aip/action-proposals",
        headers=headers,
        json={"actionTypeId": action_id, "purpose": "并发审批验证"},
    ).json()["proposal"]
    client.app.dependency_overrides[require_principal] = lambda: _reviewer("reviewer-concurrent")
    request_headers = {**headers, "Idempotency-Key": f"approve-{suffix}"}
    request_body = {
        "expectedProposalVersion": proposal["version"],
        "expectedProposalHash": proposal["proposalHash"],
        "decision": "approved",
    }
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda _index: client.post(
                        f"/v1/aip/action-proposals/{proposal['id']}/decision",
                        headers=request_headers,
                        json=request_body,
                    ),
                    range(2),
                )
            )
        assert [response.status_code for response in responses] == [200, 200]
        assert {response.json()["proposal"]["version"] for response in responses} == {2}
        assert {len(response.json()["approvals"]) for response in responses} == {1}
    finally:
        client.app.dependency_overrides.pop(require_principal, None)


def test_concurrent_proposal_replay_creates_one_snapshot(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"send_proposal_concurrent_{suffix}"
    _seed_action(action_id)
    headers = _headers(f"proposal-{suffix}")
    body = {"actionTypeId": action_id, "purpose": "并发提案验证"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _index: client.post(
                    "/v1/aip/action-proposals", headers=headers, json=body
                ),
                range(2),
            )
        )
    assert [response.status_code for response in responses] == [201, 201]
    proposal_ids = {response.json()["proposal"]["id"] for response in responses}
    assert len(proposal_ids) == 1
    with connect(SCOPE) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
            (*SCOPE.key, headers["Idempotency-Key"]),
        ).fetchone()["n"]
    assert count == 1
