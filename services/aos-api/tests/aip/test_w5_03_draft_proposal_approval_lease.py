"""W5-03 explicit Draft -> Proposal -> Approval -> Lease acceptance tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "w5_002_action_draft_approval_lease.py"
)


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
        "Idempotency-Key": key,
    }


def _principal(subject: str, role: str) -> Principal:
    return Principal(
        subject=subject,
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=[role],
        markings=["public", "restricted"],
    )


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


def test_explicit_draft_revision_submit_approval_and_lease_are_exact(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"send_w5_draft_{suffix}"
    _seed_action(action_id)
    created = client.post(
        "/v1/aip/action-drafts",
        headers=_headers(f"draft-create-{suffix}"),
        json={
            "actionTypeId": action_id,
            "purpose": "先起草再提交的受控通知",
            "payload": {"message": "初稿"},
            "diff": {"message": {"from": None, "to": "初稿"}},
        },
    )
    assert created.status_code == 201, created.text
    first = created.json()
    assert first["revision"] == 1
    assert first["lifecycle"] == "editable"
    assert first["submittedProposalId"] is None

    revised = client.post(
        f"/v1/aip/action-drafts/{first['draftId']}/revisions",
        headers=_headers(f"draft-revise-{suffix}"),
        json={
            "actionTypeId": action_id,
            "purpose": "先起草再提交的受控通知",
            "payload": {"message": "审阅稿"},
            "diff": {"message": {"from": "初稿", "to": "审阅稿"}},
            "expectedRevision": first["revision"],
            "expectedContentHash": first["contentHash"],
        },
    )
    assert revised.status_code == 200, revised.text
    second = revised.json()
    assert second["revision"] == 2
    assert second["contentHash"] != first["contentHash"]

    stale = client.post(
        f"/v1/aip/action-drafts/{first['draftId']}/revisions",
        headers=_headers(f"draft-stale-{suffix}"),
        json={
            "actionTypeId": action_id,
            "purpose": "过期写入必须失败",
            "expectedRevision": first["revision"],
            "expectedContentHash": first["contentHash"],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "AIP_VERSION_CONFLICT"

    submit_headers = _headers(f"draft-submit-{suffix}")
    submitted = client.post(
        f"/v1/aip/action-drafts/{first['draftId']}/submit",
        headers=submit_headers,
        json={
            "expectedRevision": second["revision"],
            "expectedContentHash": second["contentHash"],
        },
    )
    assert submitted.status_code == 201, submitted.text
    bundle = submitted.json()
    proposal = bundle["proposal"]
    source_ref = proposal["sourceDraftRef"]
    assert source_ref["resourceType"] == "ActionDraftRevision"
    assert source_ref["resourceId"] == first["draftId"]
    assert source_ref["revision"] == 3
    assert proposal["approvalPolicyHash"] == second["approvalPolicyHash"]

    replay = client.post(
        f"/v1/aip/action-drafts/{first['draftId']}/submit",
        headers=submit_headers,
        json={
            "expectedRevision": second["revision"],
            "expectedContentHash": second["contentHash"],
        },
    )
    assert replay.status_code == 201
    assert replay.json()["proposal"]["id"] == proposal["id"]

    after_submit = client.post(
        f"/v1/aip/action-drafts/{first['draftId']}/revisions",
        headers=_headers(f"draft-after-submit-{suffix}"),
        json={
            "actionTypeId": action_id,
            "purpose": "提交后不可改",
            "expectedRevision": second["revision"],
            "expectedContentHash": second["contentHash"],
        },
    )
    assert after_submit.status_code == 422

    client.app.dependency_overrides[require_principal] = lambda: _principal(
        "reviewer-w5", "approver"
    )
    try:
        approved = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/decision",
            headers=_headers(f"draft-approve-{suffix}"),
            json={
                "expectedProposalVersion": proposal["version"],
                "expectedProposalHash": proposal["proposalHash"],
                "decision": "approved",
            },
        )
    finally:
        client.app.dependency_overrides.pop(require_principal, None)
    assert approved.status_code == 200, approved.text
    approval = approved.json()["approvals"][0]
    assert approval["proposalHash"] == proposal["proposalHash"]
    assert approval["approvalPolicyHash"] == proposal["approvalPolicyHash"]
    assert approval["slotId"] == "checker.1"
    assert len(approval["eligibilitySnapshotHash"]) == 64
    assert approval["expiresAt"] is not None
    assert datetime.fromisoformat(approval["expiresAt"]) > datetime.now(timezone.utc)

    approved_proposal = approved.json()["proposal"]
    client.app.dependency_overrides[require_principal] = lambda: _principal(
        "executor-w5", "aip_executor"
    )
    try:
        leased = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/lease",
            headers=_headers(f"draft-lease-{suffix}"),
            json={
                "expectedProposalVersion": approved_proposal["version"],
                "expectedProposalHash": approved_proposal["proposalHash"],
            },
        )
    finally:
        client.app.dependency_overrides.pop(require_principal, None)
    assert leased.status_code == 200, leased.text
    lease = leased.json()["lease"]
    assert lease["proposalHash"] == proposal["proposalHash"]
    assert len(lease["approvalSetHash"]) == 64
    assert lease["reservationRef"] is None

    with connect(SCOPE) as conn:
        head = conn.execute(
            """SELECT current_revision,lifecycle,submitted_proposal_id
               FROM aip_action_draft_head
               WHERE org_id=%s AND project_id=%s AND draft_id=%s""",
            (*SCOPE.key, first["draftId"]),
        ).fetchone()
        revision_count = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_action_draft_revision
               WHERE org_id=%s AND project_id=%s AND draft_id=%s""",
            (*SCOPE.key, first["draftId"]),
        ).fetchone()["count"]
        command_count = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_action_draft_command
               WHERE org_id=%s AND project_id=%s AND draft_id=%s""",
            (*SCOPE.key, first["draftId"]),
        ).fetchone()["count"]
    assert dict(head) == {
        "current_revision": 3,
        "lifecycle": "submitted",
        "submitted_proposal_id": proposal["id"],
    }
    assert revision_count == 3
    assert command_count == 3


def test_draft_only_policy_and_revision_rows_fail_closed(client) -> None:
    suffix = uuid.uuid4().hex
    action_id = f"internal_note_{suffix}"
    _seed_action(action_id, "内部备注")
    created = client.post(
        "/v1/aip/action-drafts",
        headers=_headers(f"draft-only-create-{suffix}"),
        json={"actionTypeId": action_id, "purpose": "仅保存草稿"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    client.app.dependency_overrides[require_principal] = lambda: _principal(
        "other-maker", "admin"
    )
    try:
        foreign_revision = client.post(
            f"/v1/aip/action-drafts/{draft['draftId']}/revisions",
            headers=_headers(f"foreign-revise-{suffix}"),
            json={
                "actionTypeId": action_id,
                "purpose": "不能修改他人草稿",
                "expectedRevision": draft["revision"],
                "expectedContentHash": draft["contentHash"],
            },
        )
    finally:
        client.app.dependency_overrides.pop(require_principal, None)
    assert foreign_revision.status_code == 422
    assert "only the Action Draft maker" in foreign_revision.text

    blocked = client.post(
        f"/v1/aip/action-drafts/{draft['draftId']}/submit",
        headers=_headers(f"draft-only-submit-{suffix}"),
        json={
            "expectedRevision": draft["revision"],
            "expectedContentHash": draft["contentHash"],
        },
    )
    assert blocked.status_code == 422
    assert "ACTION_DRAFT_ONLY_POLICY" in blocked.text

    with connect(SCOPE) as conn:
        with pytest.raises(
            Exception,
            match="permission denied for table aip_action_draft_revision|AIP_ACTION_DRAFT_REVISION_IMMUTABLE",
        ):
            conn.execute(
                """UPDATE aip_action_draft_revision SET lifecycle='superseded'
                   WHERE org_id=%s AND project_id=%s AND draft_id=%s AND revision=1""",
                (*SCOPE.key, draft["draftId"]),
            )


def test_w5_external_family_cannot_use_legacy_proposal_entry(client) -> None:
    _seed_action("order.remark", "订单备注")
    blocked = client.post(
        "/v1/aip/action-proposals",
        headers=_headers(f"legacy-external-{uuid.uuid4().hex}"),
        json={
            "actionTypeId": "order.remark",
            "purpose": "受控订单备注",
            "impactPreviewRef": {
                "resourceType": "ImpactPreviewRevision",
                "resourceId": "preview-contract-only",
                "revision": 1,
                "contentHash": "a" * 64,
            },
        },
    )
    assert blocked.status_code == 422
    assert "EXTERNAL_ACTION_EXPLICIT_DRAFT_REQUIRED" in blocked.text


def test_w5_002_migration_is_additive_tenant_safe_and_downgrade_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "w5_002"' in source
    assert 'down_revision: str | Sequence[str] | None = "w5_001"' in source
    assert "CREATE TABLE aip_action_draft_head" in source
    assert "CREATE TABLE aip_action_draft_revision" in source
    assert "CREATE TABLE aip_action_draft_command" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REVOKE UPDATE,DELETE ON aip_action_draft_revision" in source
    assert "AIP_ACTION_DRAFT_REVISION_IMMUTABLE" in source
    assert "cannot downgrade w5_002 with Draft/Approval/Lease facts" in source
    upgrade_source = source.split("def downgrade()", maxsplit=1)[0]
    assert "UPDATE AIP_ACTION_" not in upgrade_source.upper()
