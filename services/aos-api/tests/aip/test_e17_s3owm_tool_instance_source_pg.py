"""E17-s3o-w-m: active ToolBinding issuance needs a current scoped Agent."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aos_api.aip_assignee_resolution import (
    ResolveAssigneeRequest, UpsertToolBindingRequest,
)
from aos_api.aip_assignee_resolution_store import (
    AipAssigneeResolutionBlocked, AipAssigneeResolutionStore,
)
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.routers.aip_assignee_authority import upsert_tool_binding
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 10, 3, 4, 0, tzinfo=UTC)


def seed_agent(instance_id: str, status: str = "active") -> None:
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_agent_template_revision(
                 template_id,revision,display_name,role_key,lifecycle,source_ref,
                 source_license,manifest,content_hash,created_by)
               VALUES('template-s3owm',1,'S3OWM','tester','published','{}',
                      'internal','{}',%s,'tester') ON CONFLICT DO NOTHING""",
            ("e" * 64,),
        )
        conn.execute(
            """INSERT INTO aip_agent_instance(
                 org_id,project_id,instance_id,template_id,template_revision,status,
                 overlay,version,created_by)
               VALUES(%s,%s,%s,'template-s3owm',1,%s,'{}',1,'tester')""",
            (*SCOPE.key, instance_id, status),
        )
        conn.commit()


def request(binding_id: str, agent_id: str, *, version: int = 1,
            status: str = "active") -> UpsertToolBindingRequest:
    return UpsertToolBindingRequest(
        binding_id=binding_id, tool_id="test-only-tool", version=version,
        agent_instance_id=agent_id, status=status,
    )


def stored(binding_id: str) -> dict | None:
    with connect(SCOPE) as conn:
        return conn.execute(
            """SELECT version,status FROM aip_tool_binding
                WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
            (*SCOPE.key, binding_id),
        ).fetchone()


@pytest.mark.parametrize("agent_status", [None, "provisioning", "suspended", "deleted"])
def test_active_binding_rejects_missing_or_inactive_scoped_agent(agent_status: str | None):
    binding_id, agent_id = f"s3owm-{uuid4().hex}", f"s3owm-agent-{uuid4().hex}"
    if agent_status is not None:
        seed_agent(agent_id, agent_status)
    with pytest.raises(AipAssigneeResolutionBlocked, match="TOOL_BINDING_INSTANCE_NOT_ACTIVE"):
        AipAssigneeResolutionStore().upsert_tool_binding(
            SCOPE, request(binding_id, agent_id), now=NOW,
        )
    assert stored(binding_id) is None


def test_http_active_binding_missing_agent_returns_conflict_without_write():
    binding_id = f"s3owm-{uuid4().hex}"
    principal = Principal(
        subject="test-only", org_id="org-org", project_id="dev-project",
        roles=["admin"], token_kind="oidc",
    )
    with pytest.raises(ApiError) as error:
        upsert_tool_binding(
            request(binding_id, f"s3owm-agent-{uuid4().hex}"),
            principal=principal, store=AipAssigneeResolutionStore(),
        )
    assert error.value.status_code == 409
    assert error.value.code == "TOOL_BINDING_INSTANCE_NOT_ACTIVE"
    assert stored(binding_id) is None


def test_active_agent_binding_then_revocation_after_agent_suspended():
    binding_id, agent_id = f"s3owm-{uuid4().hex}", f"s3owm-agent-{uuid4().hex}"
    seed_agent(agent_id)
    store = AipAssigneeResolutionStore()
    created = store.upsert_tool_binding(SCOPE, request(binding_id, agent_id), now=NOW)
    assert created.status == "active"
    assert stored(binding_id) == {"version": 1, "status": "active"}
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_agent_instance SET status='suspended'
                WHERE org_id=%s AND project_id=%s AND instance_id=%s""",
            (*SCOPE.key, agent_id),
        )
        conn.commit()
    stale = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"s3owm-stale-{uuid4().hex}",
            assignee=AssigneeRef(
                kind=AssigneeKind.TOOL_BINDING, resource_id=binding_id, version=1,
            ),
        ),
        "tester", now=NOW,
    )
    assert "TOOL_BINDING_INSTANCE_NOT_ACTIVE" in stale.blocker_codes
    revoked = store.upsert_tool_binding(
        SCOPE, request(binding_id, agent_id, version=2, status="disabled"), now=NOW,
    )
    assert revoked.status == "disabled"
    assert stored(binding_id) == {"version": 2, "status": "disabled"}
    receipt = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"s3owm-subject-{uuid4().hex}",
            assignee=AssigneeRef(
                kind=AssigneeKind.TOOL_BINDING, resource_id=binding_id, version=2,
            ),
        ),
        "tester", now=NOW,
    )
    assert "TOOL_BINDING_DISABLED" in receipt.blocker_codes
