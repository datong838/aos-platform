from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from aos_api import ttl_job
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.retention_jobs import archive_one, list_candidates
from aos_api.routers.drafts import ensure_draft_schema
from aos_api.routers.runtime_write import apply_draft_approval
from aos_api.tenant_scope import TenantScope


def _principal(scope: TenantScope) -> Principal:
    return Principal(
        subject="tenant-test",
        org_id=scope.org_id,
        project_id=scope.project_id,
        roles=["admin"],
        markings=["public"],
    )


def _ensure_workspace(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) "
            "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (scope.org_id, scope.project_id, scope.project_id),
        )
        conn.commit()


def _insert_draft(
    *,
    scope: TenantScope,
    draft_id: str,
    object_type: str,
    object_id: str,
    proposed: dict,
    action_type_id: str = "UpdateWikiCard",
) -> None:
    ensure_draft_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO draft_dataset
              (id, action_type_id, object_type, object_id, title, proposed, status,
               created_by, org_id, project_id)
            VALUES (%s,%s,%s,%s,'tenant test',%s::jsonb,
                    'proposed','tenant-test',%s,%s)
            """,
            (
                draft_id,
                action_type_id,
                object_type,
                object_id,
                json.dumps(proposed),
                scope.org_id,
                scope.project_id,
            ),
        )
        conn.commit()


def test_draft_approval_cannot_take_over_cross_tenant_wiki_key() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    object_type = f"WikiType-{suffix}"
    object_id = "same-id"
    draft_id = f"draft-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO wiki_page (object_type,object_id,body,org_id,project_id) "
            "VALUES (%s,%s,%s::jsonb,%s,%s)",
            (object_type, object_id, '{"owner":"a"}', *scope_a.key),
        )
        conn.commit()
    _insert_draft(
        scope=scope_b,
        draft_id=draft_id,
        object_type=object_type,
        object_id=object_id,
        proposed={"wikiBody": {"owner": "b"}},
    )

    with pytest.raises(ApiError) as conflict:
        apply_draft_approval(
            draft_id=draft_id, principal=_principal(scope_b), allow_conflicts=False
        )
    assert conflict.value.status_code == 409
    with connect() as conn:
        wiki = conn.execute(
            "SELECT body,org_id,project_id FROM wiki_page "
            "WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
        draft = conn.execute(
            "SELECT status FROM draft_dataset WHERE id=%s", (draft_id,)
        ).fetchone()
    assert wiki["body"]["owner"] == "a"
    assert (wiki["org_id"], wiki["project_id"]) == scope_a.key
    assert draft["status"] == "proposed"


def test_draft_approval_cannot_take_over_cross_tenant_object_key() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    object_type = f"ObjectType-{suffix}"
    object_id = "same-id"
    draft_id = f"draft-object-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type (id,name,properties) "
            "VALUES (%s,%s,'[]'::jsonb)",
            (object_type, object_type),
        )
        conn.execute(
            "INSERT INTO obj_instance (object_type,object_id,props,org_id,project_id) "
            "VALUES (%s,%s,%s::jsonb,%s,%s)",
            (object_type, object_id, '{"owner":"a"}', *scope_a.key),
        )
        conn.commit()
    _insert_draft(
        scope=scope_b,
        draft_id=draft_id,
        object_type=object_type,
        object_id=object_id,
        proposed={"owner": "b"},
        action_type_id="UpdateObject",
    )

    with pytest.raises(ApiError) as conflict:
        apply_draft_approval(
            draft_id=draft_id, principal=_principal(scope_b), allow_conflicts=False
        )
    assert conflict.value.status_code == 409
    with connect() as conn:
        obj = conn.execute(
            "SELECT props,org_id,project_id FROM obj_instance "
            "WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
    assert obj["props"]["owner"] == "a"
    assert (obj["org_id"], obj["project_id"]) == scope_a.key


def test_retention_and_in_memory_ttl_are_scoped() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    object_type = f"Insight-{suffix}"
    old = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES (%s,%s)",
            (object_type, object_type),
        )
        for scope, object_id in ((scope_a, "a"), (scope_b, "b")):
            conn.execute(
                "INSERT INTO obj_instance "
                "(object_type,object_id,props,org_id,project_id) "
                "VALUES (%s,%s,%s::jsonb,%s,%s)",
                (
                    object_type,
                    object_id,
                    json.dumps({"createdAt": old, "retentionCandidate": True}),
                    *scope.key,
                ),
            )
        conn.commit()

    assert {item["objectId"] for item in list_candidates(scope_a)} == {"a"}
    assert {item["objectId"] for item in list_candidates(scope_b)} == {"b"}
    with connect() as conn:
        archive_one(
            conn,
            scope=scope_a,
            object_type=object_type,
            object_id="a",
            reason="test",
            ttl=90,
        )
        conn.commit()
    with connect() as conn:
        row = conn.execute(
            "SELECT org_id,project_id FROM object_lifecycle "
            "WHERE object_type=%s AND object_id='a'",
            (object_type,),
        ).fetchone()
    assert (row["org_id"], row["project_id"]) == scope_a.key

    ttl_job.reset_insight_store()
    ttl_job.upsert_insight(scope_a, {"id": "same", "status": "proposed"})
    ttl_job.upsert_insight(scope_b, {"id": "same", "status": "proposed"})
    assert ttl_job.list_insights(scope_a)[0]["orgId"] == scope_a.org_id
    assert ttl_job.list_insights(scope_b)[0]["orgId"] == scope_b.org_id
