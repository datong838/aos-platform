"""P5B fail-closed Action Proposal withdrawal acceptance tests."""
from __future__ import annotations

import uuid
from pathlib import Path

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "aip_p5_001_action_withdrawal.py"
)


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
        "Idempotency-Key": key,
    }


def _principal(subject: str) -> Principal:
    return Principal(
        subject=subject,
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["admin"],
        markings=["public", "restricted"],
    )


def _seed_action(action_id: str) -> None:
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO meta_action_type
               (id,name,object_type,parameters,required_markings,submission_criteria)
               VALUES (%s,'内部运营备注','WorkOrder','[]'::jsonb,'[]'::jsonb,'[]'::jsonb)
               ON CONFLICT (id) DO NOTHING""",
            (action_id,),
        )
        conn.commit()


def test_maker_withdraws_exact_unexecuted_proposal_idempotently(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"internal_withdraw_{suffix}"
    _seed_action(action_id)
    created = client.post(
        "/v1/aip/action-proposals",
        headers=_headers(f"create-{suffix}"),
        json={
            "actionTypeId": action_id,
            "purpose": "撤销已经不再需要的内部运营备注",
            "diff": {"status": {"from": "待处理", "to": "已记录"}},
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()["proposal"]

    withdrawal_headers = _headers(f"withdraw-{suffix}")
    body = {
        "expectedProposalVersion": proposal["version"],
        "expectedProposalHash": proposal["proposalHash"],
        "reason": "业务范围调整，不再需要该备注",
    }
    withdrawn = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/withdraw",
        headers=withdrawal_headers,
        json=body,
    )
    assert withdrawn.status_code == 200, withdrawn.text
    bundle = withdrawn.json()
    assert bundle["proposal"]["status"] == "withdrawn"
    assert bundle["proposal"]["version"] == proposal["version"] + 1
    assert bundle["draft"]["status"] == "withdrawn"

    replay = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/withdraw",
        headers=withdrawal_headers,
        json=body,
    )
    assert replay.status_code == 200
    assert replay.json()["proposal"]["version"] == bundle["proposal"]["version"]

    timeline = client.get(
        f"/v1/aip/action-proposals/{proposal['id']}/timeline",
        headers=_headers(f"timeline-{suffix}"),
    )
    assert timeline.status_code == 200
    assert [event["event_type"] for event in timeline.json()["events"]].count("withdrawn") == 1

    with connect(SCOPE) as conn:
        event = conn.execute(
            """SELECT actor_id,reason,proposal_version FROM aip_action_withdrawal_event
               WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*SCOPE.key, proposal["id"]),
        ).fetchone()
    assert dict(event) == {
        "actor_id": "user:dev",
        "reason": "业务范围调整，不再需要该备注",
        "proposal_version": proposal["version"] + 1,
    }


def test_non_maker_and_stale_revision_cannot_withdraw(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"internal_withdraw_guard_{suffix}"
    _seed_action(action_id)
    created = client.post(
        "/v1/aip/action-proposals",
        headers=_headers(f"create-guard-{suffix}"),
        json={"actionTypeId": action_id, "purpose": "验证撤回责任边界"},
    )
    proposal = created.json()["proposal"]
    body = {
        "expectedProposalVersion": proposal["version"],
        "expectedProposalHash": proposal["proposalHash"],
        "reason": "责任边界验证",
    }

    client.app.dependency_overrides[require_principal] = lambda: _principal("other-maker")
    try:
        forbidden = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/withdraw",
            headers=_headers(f"foreign-{suffix}"),
            json=body,
        )
    finally:
        client.app.dependency_overrides.pop(require_principal, None)
    assert forbidden.status_code == 422
    assert forbidden.json()["code"] == "AIP_INVALID_TRANSITION"

    stale = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/withdraw",
        headers=_headers(f"stale-{suffix}"),
        json={**body, "expectedProposalVersion": proposal["version"] + 1},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "AIP_VERSION_CONFLICT"


def test_aip_p5_withdrawal_migration_is_tenant_safe_and_additive() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "aip_p5_001"' in source
    assert 'down_revision = "aip_p4_001"' in source
    assert "CREATE TABLE aip_action_withdrawal_event" in source
    assert "UNIQUE (org_id,project_id,idempotency_key)" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "current_setting('aos.org_id', true)" in source
    assert "current_setting('aos.project_id', true)" in source
    assert "GRANT SELECT,INSERT ON aip_action_withdrawal_event TO aos_runtime" in source
    assert "UPDATE aip_action_proposal SET status='withdrawn'" not in source
